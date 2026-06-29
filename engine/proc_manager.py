"""子进程管理器 — 跨模块子进程注册与清理（线程安全 + 跨平台）"""
import atexit
import signal
import sys
import threading

_lock = threading.Lock()
_procs: list = []
_should_cleanup = threading.Event()

def register(proc):
    """注册需跟踪的子进程。自动清理已结束的进程。"""
    with _lock:
        _procs[:] = [p for p in _procs if p.poll() is None]
        _procs.append(proc)

def cleanup():
    """终止所有注册的子进程（分批持锁）"""
    with _lock:
        pending = [p for p in _procs if p.poll() is None]
        _procs.clear()
    for proc in pending:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

def _signal_handler(*_):
    """信号处理回调：仅设置标志位，由监控线程执行清理"""
    _should_cleanup.set()

def _monitor_cleanup():
    """监控线程：循环检测清理标志，支持多次触发"""
    while True:
        _should_cleanup.wait()
        _should_cleanup.clear()
        cleanup()

_monitor_thread = threading.Thread(target=_monitor_cleanup, daemon=True)
_monitor_thread.start()

atexit.register(cleanup)

if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _signal_handler)

if sys.platform == 'win32':
    try:
        import win32api
        def _win_handler(ctrl_type):
            _should_cleanup.set()
            return True
        win32api.SetConsoleCtrlHandler(_win_handler, True)
    except ImportError:
        pass
