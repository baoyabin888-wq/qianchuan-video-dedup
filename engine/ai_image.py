"""AI 生图 — 多模型引擎（MiniMax / 通义万相 / 豆包 / 智谱）"""
import os
import base64
import threading
import requests
from config.constants import HTTP_API_TIMEOUT_IMAGE, HTTP_API_TIMEOUT_PROMPT

# ─── 模型配置注册表 ───
MODELS = {
    "minimax": {
        "name": "MiniMax image-01",
        "api_url": "https://api.minimax.chat/v1/image_generation",
        "headers": lambda key: {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        "build_payload": lambda prompt, n, size: {
            "model": "image-01", "prompt": prompt, "n": n,
            "size": size, "response_format": "base64",
        },
        "parse_response": lambda data: [
            {"index": i, "data": b64}
            for i, b64 in enumerate((data.get("data") or {}).get("image_base64", []) if isinstance(data.get("data"), dict) else data.get("data", []) or [])
            if b64
        ],
        "text_api": "https://api.minimax.chat/v1/text/chatcompletion_v2",
        "text_payload": lambda prompt: {
            "model": "MiniMax-M2.7", "messages": [
                {"role": "system", "content": "你是电商广告视觉优化师。把用户输入优化成专业 AI 生图提示词（中文），添加光影/色彩/构图描述。只输出优化后的提示词，不加任何解释。"},
                {"role": "user", "content": prompt},
            ], "max_tokens": 200,
        },
        "parse_text": lambda data: next((c.get("message", {}).get("content", "") for c in (data.get("choices") or []) if c.get("message", {}).get("content")), None),
    },
    "tongyi": {
        "name": "通义万相",
        "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        "headers": lambda key: {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-DashScope-Async": "enable"},
        "build_payload": lambda prompt, n, size: {
            "model": "wanx-v1", "input": {"prompt": prompt},
            "parameters": {"n": n, "size": size},
        },
        "parse_response": lambda data: [
            {"index": i, "data": url}
            for i, url in enumerate(data.get("output", {}).get("results", []) or [])
            if url and isinstance(url, str) and url.get("url") is None
        ],
        "is_url": True,  # 返回 URL 而非 base64
        "text_api": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "text_payload": lambda prompt: {
            "model": "qwen-plus", "messages": [
                {"role": "system", "content": "你是电商广告视觉优化师。把用户输入优化成专业 AI 生图提示词（中文），添加光影/色彩/构图描述。只输出优化后的提示词，不加任何解释。"},
                {"role": "user", "content": prompt},
            ], "max_tokens": 200,
        },
        "parse_text": lambda data: next((c.get("message", {}).get("content", "") for c in (data.get("choices") or []) if c.get("message", {}).get("content")), None),
    },
    "zhipu": {
        "name": "智谱 CogView",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/images/generations",
        "headers": lambda key: {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        "build_payload": lambda prompt, n, size: {
            "model": "cogview-3", "prompt": prompt, "n": n,
            "size": size,
        },
        "parse_response": lambda data: [
            {"index": i, "data": img.get("url", "")}
            for i, img in enumerate(data.get("data", []) or [])
            if img.get("url")
        ],
        "is_url": True,
        "text_api": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "text_payload": lambda prompt: {
            "model": "glm-4", "messages": [
                {"role": "system", "content": "你是电商广告视觉优化师。把用户输入优化成专业 AI 生图提示词（中文），添加光影/色彩/构图描述。只输出优化后的提示词，不加任何解释。"},
                {"role": "user", "content": prompt},
            ], "max_tokens": 200,
        },
        "parse_text": lambda data: next((c.get("message", {}).get("content", "") for c in (data.get("choices") or []) if c.get("message", {}).get("content")), None),
    },
}

_thread_local = threading.local()

def _get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
    return _thread_local.session

def generate_image(prompt: str, api_key: str, n: int = 1,
                   size: str = "1024x1024", provider: str = "minimax") -> dict:
    """调用指定模型生图"""
    cfg = MODELS.get(provider)
    if not cfg:
        return {"status": "error", "error": f"不支持的模型: {provider}"}

    headers = cfg["headers"](api_key)
    payload = cfg["build_payload"](prompt, n, size)
    session = _get_session()
    try:
        resp = session.post(cfg["api_url"], json=payload, headers=headers, timeout=HTTP_API_TIMEOUT_IMAGE)
    except requests.RequestException as e:
        return {"status": "error", "error": f"网络请求失败: {str(e)[:100]}"}

    if resp.status_code != 200:
        try:
            err_data = resp.json()
            return {"status": "error", "error": str(err_data)[:200]}
        except Exception:
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
    try:
        data = resp.json()
    except Exception:
        return {"status": "error", "error": "响应解析失败"}

    images = cfg["parse_response"](data)
    if cfg.get("is_url"):
        # URL 输出模型：下载到 base64
        resolved = []
        for img in images:
            try:
                r = _get_session().get(img["data"], timeout=60)
                if r.status_code == 200:
                    resolved.append({"index": img["index"], "data": base64.b64encode(r.content).decode()})
            except Exception:
                continue
        images = resolved
    return {"status": "done", "images": images}

def save_images(result: dict, output_dir: str, prefix: str = "ai") -> list:
    """保存到磁盘，单张失败不影响整体"""
    saved = []
    images = result.get("images")
    if not images:
        return saved
    os.makedirs(output_dir, exist_ok=True)
    for img in images:
        try:
            fname = f"{prefix}_{img['index']+1}.png"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(img["data"]))
            saved.append(fpath)
        except Exception:
            continue
    return saved

def optimize_prompt(raw_prompt: str, api_key: str, provider: str = "minimax") -> str:
    """用对应模型的对话 API 优化提示词"""
    cfg = MODELS.get(provider)
    if not cfg or not cfg.get("text_api"):
        return raw_prompt

    headers = cfg["headers"](api_key)
    payload = cfg["text_payload"](raw_prompt)
    session = _get_session()
    try:
        resp = session.post(cfg["text_api"], json=payload, headers=headers, timeout=HTTP_API_TIMEOUT_PROMPT)
    except requests.RequestException:
        return raw_prompt
    if resp.status_code != 200:
        return raw_prompt
    try:
        data = resp.json()
    except Exception:
        return raw_prompt
    result = cfg["parse_text"](data)
    return result if result else raw_prompt
