"""In-app Windows audio playback. No shell association or external player."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import uuid


class AudioPlayer:
    def __init__(self, command=None):
        self.alias = 'zcc_' + uuid.uuid4().hex
        self.path = None
        self.length = 0
        self.volume = 80
        self.speed = 1.0
        self.command = command or self._native_command

    @staticmethod
    def _native_command(text):
        dll = ctypes.WinDLL('winmm')
        send = dll.mciSendStringW
        send.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HWND]
        send.restype = wintypes.DWORD
        result = ctypes.create_unicode_buffer(1024)
        error = send(text, result, len(result), None)
        if error:
            dll.mciGetErrorStringW(error, result, len(result))
            raise RuntimeError(result.value or f'Audio error {error}')
        return result.value

    def load(self, path):
        self.close()
        path = Path(path).resolve(strict=True)
        try:
            self.command(f'open "{path}" type mpegvideo alias {self.alias}')
        except Exception:
            # Fall back to Windows 8.3 short path if MCI parser struggles with Unicode
            buf = ctypes.create_unicode_buffer(1024)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            res = kernel32.GetShortPathNameW(str(path), buf, len(buf))
            short_path = buf.value if res > 0 else str(path)
            self.command(f'open "{short_path}" type mpegvideo alias {self.alias}')
        self.path = path
        try:
            self.command(f'set {self.alias} time format milliseconds')
            self.length = int(self.command(f'status {self.alias} length'))
            self.set_volume(self.volume)
            self.set_speed(self.speed)
        except Exception:
            self.close()
            raise

    def status(self):
        if not self.path:
            return 'stopped', 0
        return (self.command(f'status {self.alias} mode'),
                int(self.command(f'status {self.alias} position')))

    def toggle(self):
        if not self.path:
            return
        mode, position = self.status()
        if mode == 'playing':
            self.command(f'pause {self.alias}')
        else:
            if position >= self.length - 50:
                position = 0
            self.command(f'play {self.alias} from {position}')

    def seek(self, milliseconds):
        if self.path:
            mode, _ = self.status()
            position = max(0, min(int(milliseconds), self.length))
            self.command(f'seek {self.alias} to {position}')
            if mode == 'playing':
                self.command(f'play {self.alias} from {position}')

    def set_volume(self, percent):
        value = max(0, min(100, int(percent)))
        if self.path:
            self.command(f'setaudio {self.alias} volume to {value * 10}')
        self.volume = value

    def set_speed(self, factor):
        value = max(0.5, min(2.0, float(factor)))
        self.speed = value
        if self.path:
            try:
                self.command(f'set {self.alias} speed {int(round(value * 1000))}')
            except Exception:
                pass

    def skip(self, seconds):
        if self.path:
            self.seek(self.status()[1] + int(seconds * 1000))

    def close(self):
        if self.path:
            self.command(f'close {self.alias}')
            self.path = None
            self.length = 0
