"""Best-effort, non-invasive Zalo desktop call/window detection.

Zalo does not expose a verified public desktop call event interface to this app.
Windows enumeration is heuristic, and a diagnostic snapshot helps calibrate it.
No call audio is accessed by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import re
import sys
import unicodedata

try:
    import psutil
except ImportError:
    psutil = None


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    klass: str
    width: int
    height: int
    process_name: str = ''


@dataclass(frozen=True)
class CallSignal:
    key: int
    kind: str
    reason: str


def plain(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text.lower()).replace('đ', 'd')
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


CALL_PATTERNS = (
    'cuoc goi den', 'cuoc goi di', 'dang goi', 'goi thoai', 'goi video',
    'cuoc goi video', 'cuoc goi thoai',
    'incoming call', 'outgoing call', 'video call', 'voice call',
    'zalo call', 'calling', 'ringing', 'in a call',
)
EXCLUDE_PATTERNS = (
    'cuoc goi ket thuc', 'da ket thuc', 'ket thuc cuoc goi', 'call ended',
    'call finished', 'missed call', 'khong tra loi', 'khong bat may',
    'lich su cuoc goi', 'lich su goi', 'call history', 'cuoc goi nho',
    'cai dat', 'settings', 'tin nhan', 'contact', 'danh ba',
    'trang ca nhan', 'profile', 'nhom chat', 'group chat',
    'thong tin tai khoan', 'thong tin ca nhan', 'thong tin lien he',
    'thong tin nhom', 'account info', 'user info', 'contact info',
    'xem anh', 'trinh xem anh', 'photo viewer', 'image viewer',
    'chia se', 'share', 'chon tep', 'file picker', 'dang nhap', 'login',
)


def looks_like_call_title(title: str) -> bool:
    s = plain(title)
    return bool(s) and not any(t in s for t in EXCLUDE_PATTERNS) and any(
        re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', s) for t in CALL_PATTERNS)


def is_call_process_window(window: WindowInfo) -> bool:
    """A generic Zalo/chat window is never enough evidence to record."""
    return (window.process_name.lower() == 'zalocall.exe'
            and window.width >= 275 and window.height >= 170
            and not any(t in plain(window.title) for t in EXCLUDE_PATTERNS))


def is_zalo_process(name: str) -> bool:
    name = name.lower().removesuffix('.exe')
    return name in ('zalo', 'zalopc', 'zalodesktop', 'zalocall', 'zalomedia') or (
        name.startswith('zalo') and 'companion' not in name and 'recorder' not in name
    )


def zalo_processes() -> dict[int, str]:
    if psutil is None:
        return {}
    found = {}
    try:
        for p in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                nm = p.info.get('name') or ''
                if is_zalo_process(nm):
                    found[p.pid] = p.info.get('exe') or ''
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        return {}
    return found


def windows_for_pids(pids: set[int]) -> list[WindowInfo]:
    if sys.platform != 'win32' or not pids:
        return []
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_callback, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [('length', wintypes.UINT), ('flags', wintypes.UINT), ('showCmd', wintypes.UINT),
                    ('ptMinPosition', wintypes.POINT), ('ptMaxPosition', wintypes.POINT),
                    ('rcNormalPosition', wintypes.RECT)]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
    user32.GetWindowPlacement.restype = wintypes.BOOL
    items: list[WindowInfo] = []
    process_names = {}
    if psutil is not None:
        for pid in pids:
            try:
                process_names[pid] = psutil.Process(pid).name()
            except psutil.Error:
                pass

    @enum_callback
    def cb(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids or not user32.IsWindowVisible(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        if user32.IsIconic(hwnd):
            placement = WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(placement)
            if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                rect = placement.rcNormalPosition
        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)
        if width < 100 or height < 65:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(max(1, n + 1))
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
        items.append(WindowInfo(int(hwnd), int(pid.value), title_buffer.value,
                                class_buffer.value, width, height, process_names.get(pid.value, '')))
        return True
    user32.EnumWindows(cb, 0)
    return items


class ZaloCallDetector:
    """Track stable Zalo windows, avoid reprompting on a declined active call."""
    def __init__(self):
        self.baseline: set[int] = set()
        self.seen: dict[int, int] = {}
        self.absent: dict[int, int] = {}
        self.active_keys: set[int] = set()
        self.ignored: set[int] = set()
        self.named_keys: set[int] = set()
        self.connected = False
        self.allow_new_windows = True
        self._new_window_age = 0

    def reset(self):
        self.baseline.clear()
        self.seen.clear()
        self.absent.clear()
        self.active_keys.clear()
        self.ignored.clear()
        self.named_keys.clear()
        self.connected = False

    def update(self, windows: list[WindowInfo], running: bool) -> tuple[list[CallSignal], set[int]]:
        """Return new call signals, and current call-signal window handles.

        Need two polls for a call title, three for a dedicated call-process window.
        Generic Zalo windows are never evidence of a call, including new windows.
        """
        if not running:
            self.reset()
            return [], set()
        current = {w.hwnd: w for w in windows}
        if not self.connected:
            if not current:
                return [], set()
            self.connected = True
            self.baseline = set(current)
            # A window explicitly titled as a call may already be active.
            self.seen = {key: 1 for key, w in current.items() if looks_like_call_title(w.title)
                         or (self.allow_new_windows and is_call_process_window(w))}
            self.named_keys.update(key for key, w in current.items() if looks_like_call_title(w.title))
            return [], set()

        signals = []
        valid: set[int] = set()
        for w in windows:
            named = looks_like_call_title(w.title)
            if named:
                self.named_keys.add(w.hwnd)
            generic_candidate = self.allow_new_windows and is_call_process_window(w)
            if not (named or generic_candidate):
                self.seen.pop(w.hwnd, None)
                continue
            age = self.seen.get(w.hwnd, 0) + 1
            self.seen[w.hwnd] = age
            if age < (2 if named else 3):
                continue
            valid.add(w.hwnd)
            if w.hwnd not in self.active_keys and w.hwnd not in self.ignored:
                kind = 'Gọi Zalo' if not named else ('Gọi video/thoại Zalo')
                reason = ('Tiêu đề cửa sổ Zalo có dấu hiệu cuộc gọi'
                          if named else 'Cửa sổ thuộc tiến trình gọi ZaloCall')
                signals.append(CallSignal(w.hwnd, kind, reason))
                self.active_keys.add(w.hwnd)
        # If a named window becomes untitled while call ongoing, don't drop it
        # on the first poll (e.g. switch between video and audio).
        for hwnd in (self.active_keys | self.ignored):
            if hwnd not in valid:
                self.absent[hwnd] = self.absent.get(hwnd, 0) + 1
            else:
                self.absent.pop(hwnd, None)
        for hwnd, count in list(self.absent.items()):
            if count >= 5:
                self.absent.pop(hwnd, None)
                self.active_keys.discard(hwnd)
                self.ignored.discard(hwnd)
                self.seen.pop(hwnd, None)
        for hwnd in list(self.seen):
            if hwnd not in current and hwnd not in self.active_keys and hwnd not in self.ignored:
                self.seen.pop(hwnd, None)
        self.named_keys.intersection_update(current)
        return signals, valid

    def dismiss(self, key: int):
        self.ignored.add(key)
        self.active_keys.discard(key)


def find_zalo_launcher(running_processes: dict[int, str]) -> Path | None:
    for exe in running_processes.values():
        if exe and Path(exe).is_file():
            return Path(exe)
    base = Path.home()
    env = os.environ
    roots = [
        base / 'Desktop',
        base / 'OneDrive' / 'Desktop',
        Path(env.get('APPDATA', base)) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
        Path(env.get('PROGRAMDATA', 'C:/ProgramData')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
        Path(env.get('LOCALAPPDATA', base)) / 'Programs' / 'Zalo',
        Path(env.get('LOCALAPPDATA', base)) / 'Zalo',
    ]
    for root in roots:
        if not root.exists():
            continue
        for pattern in ('Zalo.lnk', 'Zalo.exe', 'Zalo*/Zalo.lnk', 'Zalo*/Zalo.exe'):
            matches = list(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def describe_windows(windows: list[WindowInfo], processes: dict[int, str]) -> str:
    lines = [
        'Ghi Âm Zalo PC - chẩn đoán nhận diện cửa sổ',
        'Chỉ gồm thông tin cửa sổ, không chứa tin nhắn hay bản ghi.',
        'Nếu cần nhờ hỗ trợ, hãy kiểm tra tên cửa sổ trước khi chia sẻ.', '',
        'Tiến trình:',
    ]
    lines.extend(f'  PID={pid} path={path or "(ẩn)"}' for pid, path in processes.items())
    lines.extend(['', 'Cửa sổ đang hiển thị:'])
    lines.extend(f'  HWND={w.hwnd} PID={w.pid} {w.width}x{w.height} '
                 f'class={w.klass!r} process={w.process_name!r} title={w.title!r}' for w in windows)
    if not windows:
        lines.append('  (Không tìm thấy cửa sổ Zalo thuộc tiến trình nhận diện)')
    return '\n'.join(lines) + '\n'
