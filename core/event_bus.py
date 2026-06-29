"""事件总线 — 跨模块通信"""

import threading
from collections import defaultdict


class EventBus:
    """简单的 pub/sub 事件总线"""

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: str, callback):
        """订阅事件"""
        with self._lock:
            self._subscribers[event].append(callback)

    def emit(self, event: str, data=None):
        """触发事件"""
        with self._lock:
            callbacks = list(self._subscribers.get(event, []))
        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                print(f"EventBus error [{event}]: {e}")


bus = EventBus()
