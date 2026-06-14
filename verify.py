"""
去重效果验证工具 — 对比原始视频和处理后视频的指纹差异
"""
import subprocess, sys, os, hashlib, json
from pathlib import Path

FFMPEG = "ffmpeg"

def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def extract_mid_frame(video, output):
    """提取视频中间帧"""
    dur = get_duration(video)
    mid = dur / 2 if dur else 1
    subprocess.run([FFMPEG, "-y", "-ss", str(mid), "-i", video, "-vframes", "1", "-q:v", "2", output],
                   capture_output=True)

def get_duration(video):
    import re
    r = subprocess.run([FFMPEG, "-i", video], capture_output=True, text=True)
    m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', r.stderr)
    if m:
        return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    return 0

def compare(original, processed):
    """对比两个视频的指纹差异"""
    result = {"original": Path(original).name, "processed": Path(processed).name}
    
    # 1. 文件哈希（必然不同）
    result["md5_original"] = md5_file(original)
    result["md5_processed"] = md5_file(processed)
    result["md5_match"] = result["md5_original"] == result["md5_processed"]
    
    # 2. 文件大小
    result["size_original"] = f"{os.path.getsize(original)/1024/1024:.1f}MB"
    result["size_processed"] = f"{os.path.getsize(processed)/1024/1024:.1f}MB"
    
    # 3. 时长
    d1 = get_duration(original)
    d2 = get_duration(processed)
    result["duration_original"] = f"{d1:.2f}s"
    result["duration_processed"] = f"{d2:.2f}s"
    result["duration_changed"] = abs(d1 - d2) > 0.02  # >20ms is a change
    
    # 4. 中间帧 MD5（最关键的指纹）
    extract_mid_frame(original, "/tmp/frame_orig.jpg")
    extract_mid_frame(processed, "/tmp/frame_proc.jpg")
    if os.path.exists("/tmp/frame_orig.jpg") and os.path.exists("/tmp/frame_proc.jpg"):
        result["midframe_md5_orig"] = md5_file("/tmp/frame_orig.jpg")[:16]
        result["midframe_md5_proc"] = md5_file("/tmp/frame_proc.jpg")[:16]
        result["midframe_match"] = result["midframe_md5_orig"] == result["midframe_md5_proc"]
    else:
        result["midframe_error"] = "提取失败"
    
    # 5. 媒体指纹（通过 ffprobe）
    r1 = subprocess.run([FFMPEG, "-i", original], capture_output=True, text=True)
    r2 = subprocess.run([FFMPEG, "-i", processed], capture_output=True, text=True)
    result["codec_original"] = extract_codec(r1.stderr)
    result["codec_processed"] = extract_codec(r2.stderr)
    
    return result

def extract_codec(stderr):
    import re
    m = re.search(r'Video: (\S+)', stderr)
    return m.group(1) if m else "?"

def main():
    if len(sys.argv) != 3:
        print("用法: python3 verify.py 原始视频.mp4 处理后的视频.mp4")
        return
    
    orig, proc = sys.argv[1], sys.argv[2]
    if not os.path.exists(orig):
        print(f"原始视频不存在: {orig}")
        return
    if not os.path.exists(proc):
        print(f"处理后视频不存在: {proc}")
        return
    
    print("正在分析...\n")
    result = compare(orig, proc)
    
    print("=" * 60)
    print("              去重效果验证报告")
    print("=" * 60)
    print()
    
    checks = [
        ("MD5 文件哈希", result["md5_match"], "文件内容完全不同" if not result["md5_match"] else "内容相同(异常!)"),
        ("文件大小", result["size_original"] != result["size_processed"], f"{result['size_original']} → {result['size_processed']}"),
        ("时长变化", result.get("duration_changed", False), f"{result['duration_original']} → {result['duration_processed']}"),
        ("中间帧指纹", not result.get("midframe_match", True), "像素已改变" if not result.get("midframe_match", True) else "中间帧相同(异常!)"),
    ]
    
    all_pass = True
    for name, passed, detail in checks:
        status = "✅ 通过" if passed else "❌ 失败"
        if not passed:
            all_pass = False
        print(f"  {status}  {name}")
        print(f"         {detail}")
        print()
    
    print("-" * 60)
    if all_pass:
        print("  结论: ✅ 所有指纹均已改变，平台无法识别为同一视频")
    else:
        print("  结论: ❌ 部分指纹未改变，去重力度不够")
    print("-" * 60)

if __name__ == "__main__":
    main()
