"""统一配置中心 — 所有用户偏好持久化管理"""
import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from engine.paths import user_data_dir

_CONFIG_FILE = user_data_dir() / "config.json"
_LOCK = threading.RLock()  # 可重入锁
_LOCK_TIMEOUT = 3  # 获取锁超时秒数


# 创建线程安全的上下文管理器包装
class _LockGuard:
    def __enter__(self):
        if not _LOCK.acquire(timeout=_LOCK_TIMEOUT):
            raise RuntimeError("配置读写超时")
        return self

    def __exit__(self, *args):
        _LOCK.release()
_DEFAULT_CONFIG = {
    "_version": 1,
    "minimax_api_key": "",
    "tongyi_api_key": "",
    "zhipu_api_key": "",
    "ai_model": "minimax",
    "output": {
        "ai_image": str(Path.home() / "Desktop" / "AI生图"),
        "dedup": str(Path.home() / "Desktop" / "去重输出"),
        "download": str(Path.home() / "Desktop" / "素材下载"),
        "transcribe": str(Path.home() / "Desktop" / "转写文案"),
    },
    "dedup": {
        "mode": "自动",
        "intensity": "标准",
        "selected_ops": [True, True, True, True, True, False, False],
    },
    "transcribe": {
        "model": "base",
    },
}


class AppConfig:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:  # 双重检查
                    cls._instance = super().__new__(cls)
                    cls._instance._data = cls._instance._load()
        return cls._instance

    def _load(self) -> dict:
        """加载配置，深拷贝默认值避免污染"""
        data = deepcopy(_DEFAULT_CONFIG)
        if _CONFIG_FILE.exists():
            try:
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                data = self._deep_merge(data, user_data)
            except Exception:
                import sys
                print("[电商工具箱] 配置文件损坏，已恢复默认设置", file=sys.stderr)
                pass
        return data

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def save(self):
        """保存到磁盘（原子写入，IO异常不崩溃）"""
        with _LockGuard():
            _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = str(_CONFIG_FILE) + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, _CONFIG_FILE)
            except Exception:
                import sys
                print("[电商工具箱] 配置保存失败（磁盘满/权限不足）", file=sys.stderr)
                # 清理可能残留的临时文件
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def get(self, key_path: str, default=None):
        """按路径取值（持锁防并发读写脏数据）"""
        with _LockGuard():
            keys = key_path.split(".")
            val = self._data
            for k in keys:
                if isinstance(val, dict) and k in val:
                    val = val[k]
                else:
                    return default
            return deepcopy(val) if isinstance(val, (dict, list)) else val

    def set(self, key_path: str, value, auto_save: bool = True):
        """按路径设值（全程持锁，防止并发数据撕裂）"""
        with _LockGuard():
            keys = key_path.split(".")
            d = self._data
            for k in keys[:-1]:
                if k not in d:
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = deepcopy(value) if isinstance(value, (dict, list)) else value
            if auto_save:
                self.save()


# 全局单例
config = AppConfig()
