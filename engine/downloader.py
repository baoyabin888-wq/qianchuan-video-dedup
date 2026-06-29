"""视频下载 — Playwright 持久化浏览器 + 流式进度"""
import atexit
import os
import json
import time
import re
import ssl
import subprocess
import threading
import urllib.request
from pathlib import Path
from engine.paths import user_data_dir
from engine.proc_manager import register as _reg_proc
from config.logger import log
from config.constants import PLAYWRIGHT_GOTO_TIMEOUT, HTTP_DOWNLOAD_TIMEOUT

_PLAYWRIGHT_PROFILE = user_data_dir() / "playwright_profile"
_PLAYWRIGHT_PROFILE.mkdir(parents=True, exist_ok=True)
_PW_LOCK = threading.Lock()
_PW_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

_COOKIE_DIR = user_data_dir() / "browser_cookies"
_COOKIE_DIR.mkdir(parents=True, exist_ok=True)

def _cookie_path(platform): return _COOKIE_DIR / f"{platform}.json"
def _save_cookies(platform, cookies):
    with open(_cookie_path(platform), 'w', encoding='utf-8') as f: json.dump(cookies, f)
def _load_cookies(platform):
    p = _cookie_path(platform)
    if not p.exists():
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

_CTX_CACHE = None
_CTX_CACHE_LOCK = threading.Lock()
_PW_INSTANCE = None

def _get_or_create_ctx():
    global _CTX_CACHE, _PW_INSTANCE
    if _CTX_CACHE is not None:
        try:
            _CTX_CACHE.browser.is_connected()
        except Exception:
            _CTX_CACHE = None
    if _CTX_CACHE is None:
        with _CTX_CACHE_LOCK:
            if _CTX_CACHE is None:
                from playwright.sync_api import sync_playwright as _sp
                _PW_INSTANCE = _sp().start()
                _CTX_CACHE = _PW_INSTANCE.chromium.launch_persistent_context(
                    str(_PLAYWRIGHT_PROFILE),
                    headless=True,
                    user_agent=_PW_UA,
                    viewport={'width': 1280, 'height': 800},
                )
    return _CTX_CACHE

def _cleanup_playwright():
    global _CTX_CACHE, _PW_INSTANCE
    if _CTX_CACHE is not None:
        try:
            _CTX_CACHE.close()
        except Exception:
            pass
        _CTX_CACHE = None
    if _PW_INSTANCE is not None:
        try:
            _PW_INSTANCE.stop()
        except Exception:
            pass
        _PW_INSTANCE = None

atexit.register(_cleanup_playwright)

PLATFORMS = {
    "douyin": {"name": "抖音", "url": "https://www.douyin.com/"},
    "kuaishou": {"name": "快手", "url": "https://www.kuaishou.com/"},
    "bilibili": {"name": "B站", "url": "https://www.bilibili.com/"},
    "tiktok": {"name": "TikTok", "url": "https://www.tiktok.com/"},
}

def login_platform(platform: str) -> bool:
    """打开持久化浏览器登录，复用全局上下文，登录态自动持久化"""
    info = PLATFORMS.get(platform)
    if not info:
        return False
    try:
        with _PW_LOCK:
            ctx = _get_or_create_ctx()
            page = ctx.new_page()
            page.goto(info["url"], timeout=PLAYWRIGHT_GOTO_TIMEOUT)
            page.wait_for_timeout(2000)
            evt = threading.Event()
            page.on('close', lambda: evt.set())
            ctx.on('close', lambda: evt.set())
            evt.wait(timeout=300)
            try:
                cookies = ctx.cookies()
                if cookies:
                    _save_cookies(platform, cookies)
            except Exception:
                pass
            page.close()
            return True
    except ImportError:
        return False
    except Exception:
        return False

def download_video(url: str, output_dir: str, progress_cb=None, stop_event=None) -> dict:
    """下载视频，支持进度回调 + 真实停止"""
    platform = None
    if 'douyin.com' in url: platform = 'douyin'
    elif 'kuaishou.com' in url: platform = 'kuaishou'
    elif 'bilibili.com' in url or 'b23.tv' in url: platform = 'bilibili'
    elif 'tiktok.com' in url: platform = 'tiktok'

    if platform in ('douyin', 'kuaishou'):
        result = _playwright_extract(url, platform)
        if result["status"] != "done":
            return result
        return _stream_download(result["video_url"], output_dir, result["title"],
                                progress_cb, stop_event)
    return _ytdlp_extract(url, output_dir, progress_cb, stop_event)

def _playwright_extract(url, platform):
    """Playwright 提取视频地址"""
    name = PLATFORMS.get(platform, {}).get('name', platform)
    video_url = None
    title = "video"

    with _PW_LOCK:
        ctx = _get_or_create_ctx()
        page = ctx.new_page()
        
        try:
            ctx.clear_cookies()
        except Exception:
            pass
        
        cookies = _load_cookies(platform)
        if cookies:
            try:
                ctx.add_cookies(cookies)
            except Exception:
                pass

        def _block(route):
            if route.request.resource_type in ('image','stylesheet','font','media'):
                route.abort()
            else:
                route.continue_()
        page.route('**/*', _block)

        def on_response(resp):
            nonlocal video_url, title
            try:
                data = resp.json()
                if 'aweme/detail' in resp.url or 'iteminfo' in resp.url:
                    aweme = data.get('aweme_detail') or (data.get('item_list', [{}])[0])
                    if aweme:
                        title = aweme.get('desc', '')[:50] or title
                        play = aweme.get('video', {}).get('play_addr', {}).get('url_list', [])
                        if play: video_url = play[0]
                if 'photo/info' in resp.url:
                    video_url = _deep_find(data, lambda v: isinstance(v, str) and v.startswith('http') and 'mp4' in v)
                    if video_url:
                        t = _deep_find(data, lambda v: isinstance(v, str) and len(v) > 2,
                                       keys=('caption', 'desc', 'title'))
                        if t: title = t[:50]
            except Exception: pass

        page.on('response', on_response)
        page.goto(url, timeout=PLAYWRIGHT_GOTO_TIMEOUT, wait_until='domcontentloaded')
        
        start = time.time()
        while time.time() - start < 4:
            if video_url:
                break
            page.wait_for_timeout(150)
        page.close()

    if not video_url:
        return {"status": "error", "error": f"请先点击 [{name}登录]"}
    return {"status": "done", "video_url": video_url, "title": title}

def _deep_find(data, predicate, keys=None, depth=20):
    """递归搜索数据结构"""
    if depth <= 0: return None
    if isinstance(data, dict):
        if keys:
            for k in keys:
                if k in data and predicate(data[k]): return data[k]
        for v in data.values():
            r = _deep_find(v, predicate, None, depth-1)
            if r: return r
    elif isinstance(data, list):
        for v in data:
            r = _deep_find(v, predicate, None, depth-1)
            if r: return r
    return None

def _stream_download(video_url, output_dir, title, progress_cb=None, stop_event=None):
    """流式下载，支持停止事件中断"""
    safe_name = re.sub(r'[\\/:*?"<>|]', '', title)[:50]
    safe_name = f"{safe_name}_{int(time.time()*1000)}"
    filepath = os.path.join(output_dir, f"{safe_name}.mp4")
    cancelled = False

    try:
        from urllib.parse import urlparse
        parsed = urlparse(video_url)
        referer = f"{parsed.scheme}://{parsed.netloc}/"
        ctx = ssl.create_default_context()
        req = urllib.request.Request(video_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': referer,
        })
        resp = urllib.request.urlopen(req, timeout=HTTP_DOWNLOAD_TIMEOUT, context=ctx)
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0

        with open(filepath, 'wb') as f:
            last_report = 0
            while True:
                if stop_event and stop_event.is_set():
                    cancelled = True
                    break
                try:
                    chunk = resp.read(8192)
                except Exception:
                    chunk = None
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and (downloaded - last_report > 524288 or downloaded == 0):
                    last_report = downloaded
                    pct = downloaded / total if total > 0 else 0
                    progress_cb(pct, downloaded, total)

        if cancelled:
            try:
                resp.close()
            except Exception:
                pass
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            return {"status": "error", "error": "已取消"}

        actual_size = os.path.getsize(filepath)
        return {"status": "done", "title": title, "filepath": filepath,
                "size": actual_size, "downloaded": downloaded}
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        log.error(f"流式下载失败: {str(e)[:200]}", exc_info=True)
        return {"status": "error", "error": str(e)[:100]}

def _ytdlp_extract(url, output_dir, progress_cb=None, stop_event=None):
    """yt-dlp 下载，支持停止事件强制杀进程"""
    from engine.paths import get_ytdlp
    out_template = f"{output_dir}/%(title)s.%(ext)s"
    cmd = [get_ytdlp(), "--no-playlist", "--restrict-filenames",
           "-o", out_template,
           "--print", "after_move:filepath",
           "--newline",
           "--progress-template", "PROGRESS:%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.percent)s",
           url]
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1,
        )
        _reg_proc(proc)
        title, fpath = None, None
        import re as _re
        progress_re = _re.compile(r'^PROGRESS:(\d+)\|(\d+)\|([\d.]+)%?')

        def _read_loop():
            nonlocal title, fpath
            try:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if not line:
                        continue
                    pm = progress_re.search(line)
                    if pm and progress_cb:
                        try:
                            dl_bytes = int(pm.group(1))
                            total_bytes = int(pm.group(2))
                            pct_str = pm.group(3)
                            pct = float(pct_str) / 100 if float(pct_str) > 1 else float(pct_str)
                            progress_cb(pct, dl_bytes, total_bytes)
                        except Exception:
                            pass
                        continue
                    if os.path.sep in line and line.endswith((".mp4", ".flv", ".webm", ".mkv", ".m4a", ".mp3")):
                        fpath = line
                        continue
                    if (("\\" in line or "/" in line)
                          and line.endswith((".mp4", ".flv", ".webm", ".mkv", ".m4a", ".mp3"))
                          and not line.startswith("[")):
                        fpath = line
                    elif (not title and not line.startswith("[")
                          and "%" not in line and len(line) < 200
                          and not line.startswith(" ")
                          and not line.endswith("KiB")
                          and not line.endswith("MiB")):
                        title = line
            except Exception:
                pass

        reader = threading.Thread(target=_read_loop, daemon=True)
        reader.start()

        while True:
            try:
                proc.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if stop_event and stop_event.is_set():
                    proc.kill()
                    proc.wait()
                    reader.join(timeout=1)
                    if fpath and os.path.exists(fpath):
                        try: os.remove(fpath)
                        except Exception: pass
                    return {"status": "error", "error": "已取消"}
        reader.join(timeout=2)
        if proc.returncode != 0:
            return {"status": "error", "error": "yt-dlp 下载失败"}
        if not fpath or not os.path.exists(fpath):
            files = [(f, f.stat().st_mtime) for f in Path(output_dir).glob("*.*")
                     if f.suffix.lower() in (".mp4", ".flv", ".webm", ".mkv", ".m4a", ".mp3")]
            if files:
                fpath = str(max(files, key=lambda x: x[1])[0])
        if fpath and os.path.exists(fpath):
            return {"status": "done", "title": title or Path(fpath).stem,
                    "filepath": fpath, "size": os.path.getsize(fpath)}
        return {"status": "error", "error": "未获取到文件路径"}
    except Exception as e:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait()
        log.error(f"yt-dlp下载失败: {str(e)[:200]}", exc_info=True)
        return {"status": "error", "error": str(e)}

def batch_extract(urls: list, platform: str, progress_cb=None) -> list:
    """批量解析视频链接，每20条重建Page防内存泄漏"""
    results = []
    with _PW_LOCK:
        ctx = _get_or_create_ctx()
        
        try:
            ctx.clear_cookies()
        except Exception:
            pass
        
        cookies = _load_cookies(platform)
        if cookies:
            try:
                ctx.add_cookies(cookies)
            except Exception:
                pass

        page = ctx.new_page()
        for i, url in enumerate(urls):
            if i > 0 and i % 20 == 0:
                page.close()
                page = ctx.new_page()
            
            if progress_cb:
                progress_cb(f"解析 {i+1}/{len(urls)}")
            video_url = None
            title = "video"

            def on_response(resp):
                nonlocal video_url, title
                try:
                    data = resp.json()
                    if 'aweme/detail' in resp.url or 'iteminfo' in resp.url:
                        aweme = data.get('aweme_detail') or (data.get('item_list', [{}])[0])
                        if aweme:
                            title = aweme.get('desc', '')[:50] or title
                            play = aweme.get('video', {}).get('play_addr', {}).get('url_list', [])
                            if play:
                                video_url = play[0]
                except Exception:
                    pass

            page.on('response', on_response)
            try:
                page.goto(url, timeout=PLAYWRIGHT_GOTO_TIMEOUT, wait_until='domcontentloaded')
                start = time.time()
                while time.time() - start < 3:
                    if video_url:
                        break
                    page.wait_for_timeout(150)
                if video_url:
                    results.append({"status": "done", "video_url": video_url, "title": title})
                else:
                    results.append({"status": "error", "error": "未获取到视频地址"})
            except Exception as e:
                results.append({"status": "error", "error": str(e)[:50]})
            finally:
                page.remove_listener('response', on_response)
        page.close()
    return results
