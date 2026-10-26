"""Windows single-instance signalling, tray, and rotating diagnostic logs."""
import ctypes
from ctypes import wintypes
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logger(folder):
    logger = logging.getLogger('zcc')
    if not logger.handlers:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'companion.log', maxBytes=1_000_000,
                                      backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class SingleInstance:
    def __init__(self, name='ZaloCallCompanion'):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateEventW.restype = wintypes.HANDLE
        self.api.SetEvent.argtypes = [wintypes.HANDLE]
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.mutex = self.api.CreateMutexW(None, False, f'Local\\{name}.Instance')
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.primary = ctypes.get_last_error() != 183
        self.event = self.api.CreateEventW(None, False, False, f'Local\\{name}.Show')
        if not self.event:
            self.api.CloseHandle(self.mutex)
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.primary:
            self.api.SetEvent(self.event)

    def requested_show(self):
        return self.api.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        for handle in (self.event, self.mutex):
            if handle:
                self.api.CloseHandle(handle)
        self.event = self.mutex = None


def create_tray(events, icon_path):
    import pystray
    from PIL import Image
    icon = pystray.Icon('ZaloCallCompanion', Image.open(icon_path), 'Ghi Âm Zalo PC',
        pystray.Menu(
            pystray.MenuItem('Mở ứng dụng', lambda *_: events.put(('show', '')), default=True),
            pystray.MenuItem('Dừng & lưu', lambda *_: events.put(('stop', ''))),
            pystray.MenuItem('Thoát ứng dụng', lambda *_: events.put(('quit', '')))))
    icon.run_detached()
    return icon


def set_autostart(enabled):
    import winreg
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Chỉ bật khởi động cùng Windows trong bản EXE đã cài.')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            winreg.SetValueEx(key, 'ZaloCallCompanion', 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(key, 'ZaloCallCompanion')
            except FileNotFoundError:
                pass


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return bool(winreg.QueryValueEx(key, 'ZaloCallCompanion')[0])
    except OSError:
        return False


TRAY_STATES = {
    'idle': ('Đang chờ cuộc gọi', '#0A84FF'),
    'starting': ('Đang mở thiết bị', '#FF9F0A'),
    'recording': ('Đang thu âm', '#FF453A'),
    'saving': ('Đang lưu bản ghi', '#FF9F0A'),
    'error': ('Có lỗi — mở ứng dụng để kiểm tra', '#BF5AF2'),
}


def tray_state_image(state):
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = TRAY_STATES.get(state, TRAY_STATES['idle'])[1]
    draw.rounded_rectangle((4, 4, 60, 60), radius=18, fill=color)
    if state == 'recording':
        draw.ellipse((20, 20, 44, 44), fill='white')
    elif state == 'error':
        draw.line((32, 17, 32, 35), fill='white', width=6)
        draw.ellipse((29, 42, 35, 48), fill='white')
    elif state in ('starting', 'saving'):
        draw.line((32, 15, 32, 38), fill='white', width=5)
        draw.line((22, 29, 32, 39, 42, 29), fill='white', width=5)
        draw.line((19, 47, 45, 47), fill='white', width=5)
    else:
        draw.rounded_rectangle((25, 14, 39, 35), radius=7, fill='white')
        draw.arc((19, 23, 45, 43), 0, 180, fill='white', width=4)
        draw.line((32, 43, 32, 50), fill='white', width=4)
    return image


def update_tray_state(icon, state):
    state = state if state in TRAY_STATES else 'error'
    if getattr(icon, '_companion_state', None) == state:
        return
    icon.icon = tray_state_image(state)
    icon.title = 'Ghi Âm Zalo PC — ' + TRAY_STATES[state][0]
    icon._companion_state = state
