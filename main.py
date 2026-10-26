"""Ghi Am Zalo PC - local call audio recorder for Windows.

The app does NOT intercept Zalo's network traffic, modify Zalo, or access
other users' messages. It heuristically detects call windows and offers a
30-second user decision when automatic recording is disabled. The user must have informed all participants and
obtained any consent required before starting recording.
"""
from __future__ import annotations

import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()

import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from recording_names import caller_from_title
from recording_library import atomic_json, recovery_candidates, read_json, cleanup_old_recordings
from library_window import LibraryWindow
from ui_effects import ManagedToplevel, cancel_root_callbacks, MiniOverlay
from desktop_support import SingleInstance, setup_logger, create_tray, set_autostart, autostart_enabled, update_tray_state, GlobalHotkeyListener
import logging
from app_paths import app_root, resolve_recording_folder, stored_recording_folder

from audio_engine import AudioSession, scan_devices, find_ffmpeg
from zalo_detector import (
    ZaloCallDetector, describe_windows, find_zalo_launcher,
    windows_for_pids, zalo_processes, looks_like_call_title, is_call_process_window, plain,
)

APP = 'Ghi Âm Zalo PC'
VERSION = '2.8.0 • Windows'
BG = ('#F2F2F7', '#111114')
SURFACE = ('#FFFFFF', '#1C1C1E')
SURFACE_2 = ('#E5E5EA', '#38383A')
TEXT = ('#1C1C1E', '#F5F5F7')
MUTED = ('#636366', '#AEAEB2')
BLUE = ('#007AFF', '#0A84FF')
GREEN = ('#248A3D', '#30D158')
RED = ('#D93025', '#FF6961')
GOLD = ('#9C6500', '#FFD60A')
CONFIG = app_root() / 'Data' / 'settings.json'
DEFAULT_FOLDER = app_root() / 'Recordings'


def load_settings():
    try:
        data = json.loads(CONFIG.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def save_settings(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(CONFIG, data)


def device_name(dev):
    return f"{dev['name']}  [#{int(dev['index'])}]"


def resolve_device(devices, selection):
    selected_name = selection.rsplit('[#', 1)[0].strip()
    matches = [d for d in devices if d['name'].strip() == selected_name]
    if len(matches) != 1:
        raise RuntimeError('Thiết bị đã thay đổi hoặc trùng tên. Mở Cài đặt, làm mới và chọn lại micro/loa.')
    return int(matches[0]['index'])


class ConfirmPopup(ManagedToplevel):
    def __init__(self, parent, reason, on_accept, on_decline, caller_name=''):
        super().__init__(parent)
        self.title('Xác nhận ghi âm cuộc gọi')
        self.geometry('460x430')
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.remaining = 30
        self.on_accept = on_accept
        self.on_decline = on_decline
        self.active = True
        self.protocol('WM_DELETE_WINDOW', self.decline)
        self.attributes('-topmost', True)
        self.transient(parent)
        self.after(50, self._front)
        body = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=22)
        body.pack(fill='both', expand=True, padx=14, pady=14)
        self._icon = ctk.CTkLabel(body, text='☎', width=68, height=68, corner_radius=34,
                                   fg_color=SURFACE_2, text_color=BLUE, font=('Segoe UI Symbol', 31))
        self._icon.pack(pady=(20, 9))
        ctk.CTkLabel(body, text='Ghi âm cuộc gọi Zalo?', font=('Segoe UI', 21, 'bold'),
                     text_color=TEXT).pack()
        ctk.CTkLabel(body, text=reason, text_color=MUTED, font=('Segoe UI', 12),
                     wraplength=375).pack(pady=(4, 5))
        ctk.CTkLabel(body, text='Chỉ bấm Đồng ý khi các bên đã được thông báo và đồng ý ghi âm.',
                     text_color=GOLD, font=('Segoe UI', 11), wraplength=375).pack(pady=(3, 13))
        row = ctk.CTkFrame(body, fg_color='transparent')
        ctk.CTkLabel(body, text='Tên người gọi để lưu tệp (có thể sửa):',
                     text_color=MUTED, font=('Segoe UI', 12)).pack(anchor='w', padx=25)
        self.name_entry = ctk.CTkEntry(body, height=34,
            placeholder_text='Chưa đọc được tên — nhập tên hoặc để trống')
        self.name_entry.pack(fill='x', padx=25, pady=(3, 12))
        if caller_name:
            self.name_entry.insert(0, caller_name)
        row.pack(padx=25, fill='x')
        ctk.CTkButton(row, text='Không ghi', width=178, height=43, corner_radius=12,
                      fg_color=SURFACE_2, hover_color=('#D1D1D6', '#48484A'), text_color=TEXT,
                      font=('Segoe UI', 13, 'bold'), command=self.decline).pack(side='left')
        ctk.CTkButton(row, text='Đồng ý ghi âm', width=178, height=43,
                      corner_radius=12, fg_color=BLUE, hover_color='#396bd8',
                      font=('Segoe UI', 13, 'bold'), command=self.accept).pack(side='right')
        self.counter = ctk.CTkLabel(body, text='', text_color=MUTED,
                                    font=('Segoe UI', 12))
        self.counter.pack(pady=(13, 10))
        self._tick()

    def _front(self):
        if self.active:
            self.lift()
            self.focus_force()

    def _tick(self):
        if not self.active:
            return
        self.counter.configure(text=f'Tự động bỏ qua sau {self.remaining} giây')
        if self.remaining <= 0:
            self.decline()
        else:
            self.remaining -= 1
            self.after(1000, self._tick)

    def accept(self):
        if self.active:
            name = self.name_entry.get().strip()
            self.active = False
            self.destroy()
            self.on_accept(name)

    def decline(self):
        if self.active:
            self.active = False
            self.destroy()
            self.on_decline()


class Companion(ctk.CTk):
    def __init__(self, instance=None):
        ctk.set_appearance_mode('Light')
        ctk.set_default_color_theme('blue')
        super().__init__(fg_color=BG)
        self.instance = instance
        self.tray = None
        self._tray_error = False
        self._test_mode = False
        self._test_deadline = None
        self.library = None
        self.pending_signals = {}
        try:
            self.logger = setup_logger(CONFIG.parent / 'logs')
        except OSError:
            self.logger = logging.getLogger('zcc')
        self.title(f'{APP} — {VERSION}')
        self.geometry(f'{min(980, self.winfo_screenwidth()-60)}x{min(840, self.winfo_screenheight()-90)}')
        self.minsize(820, 680)
        self.protocol('WM_DELETE_WINDOW', self.hide_to_tray)
        self.settings = load_settings()
        self.reduce_motion = bool(self.settings.get('reduce_motion', False))
        self.appearance = self.settings.get('appearance', 'Light')
        if self.appearance not in ('Light', 'Dark'):
            self.appearance = 'Light'
        ctk.set_appearance_mode(self.appearance)
        self.auto_record = bool(self.settings.get('auto_record', True))
        self.events = queue.Queue()
        self.recorder = AudioSession(self.events)
        self.detector = ZaloCallDetector()
        self.detector.allow_new_windows = bool(self.settings.get('detect_new_windows', True))
        self.last_processes = {}
        self.last_windows = []
        self.pending_popup: ConfirmPopup | None = None
        self.current_call_key: int | None = None
        self.current_caller_name = ''
        self.active_call_keys: set[int] = set()
        self.lost_call_since = None
        self.last_status_running = None
        self.folder = str(resolve_recording_folder(self.settings.get('folder', DEFAULT_FOLDER)))
        self.chosen_format = str(self.settings.get('format', 'MP3'))
        self.mics = []
        self.speakers = []
        self.logs = []
        self.close_requested = False
        self.mini_overlay = None
        self.channel_mode = self.settings.get('channel_mode', 'mixed')
        self.normalize = bool(self.settings.get('normalize', False))
        self.retention_days = int(self.settings.get('retention_days', 0))
        self.backup_folder = str(self.settings.get('backup_folder', ''))
        self.enable_hotkey = bool(self.settings.get('enable_hotkey', True))
        self.floating_widget = bool(self.settings.get('floating_widget', True))
        self.gemini_api_key = str(self.settings.get('gemini_api_key', ''))

        self.hotkey_listener = None
        if self.enable_hotkey:
            try:
                self.hotkey_listener = GlobalHotkeyListener(self.events)
                self.hotkey_listener.start()
            except Exception as ex:
                self.logger.debug('Hotkey error: %s', ex)

        if self.retention_days > 0:
            self.after(3000, self._run_retention_cleanup)

        self._build_ui()
        self.reload_devices()
        self.after(400, self._poll)
        self.after(500, self._clock)
        self.after(1500, self._initial_zalo_check)
        self.after(800, self._check_ffmpeg)
        self.after(2000, self._offer_recovery)
        self.after(250, self._desktop_poll)

    def report_callback_exception(self, exc, value, tb):
        self.logger.error('Lỗi giao diện', exc_info=(exc, value, tb))
        messagebox.showerror('Ứng dụng gặp lỗi', str(value), parent=self)

    def _offer_recovery(self):
        try:
            if recovery_candidates(self.folder):
                self.log('Có phiên chưa lưu. Mở Bản ghi & khôi phục để lấy lại âm thanh.')
        except OSError as ex:
            self.log('Chưa kiểm tra được phiên cũ: ' + str(ex))

    def _desktop_poll(self):
        if self.instance and self.instance.requested_show():
            self.show_window()
        self.after(250, self._desktop_poll)

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_to_tray(self):
        try:
            if self.tray is None:
                self.tray = create_tray(self.events, Path(__file__).parent / 'assets' / 'companion.ico')
            self._sync_tray()
            self.withdraw()
            self._notify('Đang chạy nền và theo dõi Zalo. ' + ('Tự ghi cuộc gọi đang bật.' if self.auto_record else 'Sẽ hỏi trước khi ghi.'))
        except Exception as ex:
            messagebox.showerror('Không thu xuống khay được', str(ex), parent=self)

    def _notify(self, message):
        if self.tray:
            try:
                self.tray.notify(message, APP)
            except Exception:
                pass

    def update_auto_hint(self):
        self.auto_hint.configure(text=('Tự ghi đã bật, kể cả khi chạy nền. Hãy thông báo cho người tham gia trước cuộc gọi.'
                                      if self.auto_record else 'App hỏi xác nhận trước mỗi lần ghi, kể cả khi chạy nền.'))

    def toggle_auto_record(self):
        self.auto_record = bool(self.auto_switch.get())
        self.persist()
        self.update_auto_hint()
        self.log('Tự ghi cuộc gọi: ' + ('BẬT' if self.auto_record else 'TẮT'))

    def _handle_signal(self, signal):
        if self.recorder.state != 'idle' or signal.key not in self.active_call_keys:
            return
        if self.auto_record:
            self.current_call_key = signal.key
            self.current_caller_name = next((caller_from_title(w.title) for w in self.last_windows if w.hwnd == signal.key), '')
            self.lost_call_since = None
            self.log('Tự ghi: ' + signal.reason)
            self._start_recording(automatic=True)
        else:
            self._show_decision(signal.key, signal.reason)

    def toggle_autostart(self):
        try:
            set_autostart(bool(self.autostart_switch.get()))
        except Exception as ex:
            self.autostart_switch.select() if autostart_enabled() else self.autostart_switch.deselect()
            messagebox.showerror('Khởi động cùng Windows', str(ex), parent=self)

    def open_library(self):
        if self.library and self.library.winfo_exists() and self.library.folder == Path(self.folder):
            self.library.deiconify()
            self.library.lift()
            return
        if self.library and self.library.winfo_exists():
            self.library.destroy()
        self.library = LibraryWindow(self, self.folder, self.recover_recording)

    def recover_recording(self, temp):
        try:
            self.recorder.recover(temp, self.format_menu.get())
            self.record_btn.configure(state='disabled')
            self.recording_state.configure(text='● ĐANG KHÔI PHỤC', text_color=GOLD)
            self.log('Đang khôi phục: ' + str(temp))
        except Exception as ex:
            messagebox.showerror('Khôi phục', str(ex), parent=self)

    def export_logs(self):
        target = filedialog.asksaveasfilename(parent=self, title='Xuất nhật ký hỗ trợ',
                  initialfile='companion-log.txt', defaultextension='.txt')
        if target:
            try:
                files = sorted((CONFIG.parent / 'logs').glob('companion.log*'), reverse=True)
                Path(target).write_text('\n'.join(p.read_text(encoding='utf-8') for p in files), encoding='utf-8')
                self.log('Đã xuất nhật ký hỗ trợ. Xem lại tên và đường dẫn trước khi chia sẻ.')
            except OSError as ex:
                messagebox.showerror('Xuất nhật ký', str(ex), parent=self)

    def _run_retention_cleanup(self):
        try:
            count = cleanup_old_recordings(self.folder, self.retention_days)
            if count > 0:
                self.log(f'Tự động dọn dẹp: đã xóa {count} bản ghi cũ hơn {self.retention_days} ngày.')
        except Exception as ex:
            self.logger.debug('Cleanup error: %s', ex)

    def change_channel_mode(self, choice):
        self.channel_mode = 'split' if 'Tách' in choice else 'mixed'
        self.persist()
        self.log('Chế độ âm thanh: ' + ('TÁCH KÊNH (Trái: Bạn / Phải: Khách)' if self.channel_mode == 'split' else 'TRỘN CHUNG'))

    def toggle_normalize(self):
        self.normalize = bool(self.normalize_switch.get())
        self.persist()
        self.log('Cân bằng âm lượng (Normalize): ' + ('BẬT' if self.normalize else 'TẮT'))

    def change_retention(self, choice):
        self.retention_days = int(choice.split()[0]) if choice != 'Vĩnh viễn' else 0
        self.persist()
        self.log(f'Thời gian lưu trữ bản ghi: {choice}')

    def choose_backup_folder(self):
        chosen = filedialog.askdirectory(parent=self, title='Chọn thư mục sao lưu phụ (OneDrive / Google Drive / USB)')
        if chosen:
            self.backup_folder = chosen
            self.backup_label.configure(text='Sao lưu sang: ' + chosen)
            self.persist()
            self.log('Đã đặt thư mục sao lưu phụ: ' + chosen)

    def clear_backup_folder(self):
        self.backup_folder = ''
        self.backup_label.configure(text='Chưa chọn thư mục sao lưu phụ')
        self.persist()
        self.log('Đã bỏ thư mục sao lưu phụ.')

    def toggle_hotkey(self):
        self.enable_hotkey = bool(self.hotkey_switch.get())
        if self.enable_hotkey and not self.hotkey_listener:
            try:
                self.hotkey_listener = GlobalHotkeyListener(self.events)
                self.hotkey_listener.start()
                self.log('Phím tắt Ctrl+Shift+R: BẬT')
            except Exception as ex:
                self.log('Không kích hoạt được phím tắt: ' + str(ex))
        elif not self.enable_hotkey and self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None
            self.log('Phím tắt Ctrl+Shift+R: TẮT')
        self.persist()

    def toggle_floating(self):
        self.floating_widget = bool(self.mini_switch.get())
        self.persist()
        self.log('Thanh nổi Mini: ' + ('BẬT' if self.floating_widget else 'TẮT'))

    def save_gemini_key(self):
        key = self.gemini_key_entry.get().strip()
        self.gemini_api_key = key
        self.persist()
        self.log('Đã lưu Gemini API Key.')
        messagebox.showinfo('Trợ lý AI', 'Đã lưu Gemini API Key thành công!', parent=self)

    def clear_gemini_key(self):
        self.gemini_api_key = ''
        self.gemini_key_entry.delete(0, 'end')
        self.persist()
        self.log('Đã xóa Gemini API Key.')
        messagebox.showinfo('Trợ lý AI', 'Đã xóa API Key.', parent=self)

    def destroy(self):
        self._destroyed = True
        cancel_root_callbacks(self)
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None
        if hasattr(self, 'mini_overlay') and self.mini_overlay and self.mini_overlay.winfo_exists():
            try:
                self.mini_overlay.destroy()
            except Exception:
                pass
            self.mini_overlay = None
        if self.tray:
            self.tray.stop()
            self.tray = None
        super().destroy()

    def _check_ffmpeg(self):
        if not find_ffmpeg():
            self.log('Thiếu FFmpeg: chưa thể ghi và lưu MP3/WAV.')
            messagebox.showwarning('Thiếu FFmpeg',
                'Cần FFmpeg để ghi và lưu cả MP3 lẫn WAV.\n'
                'Cài bằng lệnh: winget install -e --id Gyan.FFmpeg\n'
                'Sau đó mở lại ứng dụng.', parent=self)

    def _lbl(self, parent, text, size=13, color=TEXT, weight='normal', **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color,
                            font=('Segoe UI', size, weight), **kwargs)

    def _card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=18, **kwargs)

    def _build_ui(self):
        from ui_layout import build_ui
        build_ui(self)

    def log(self, text):
        self.logger.info(text)
        self.logs.append(f'{datetime.now():%H:%M:%S}   {text}')
        self.logs = self.logs[-100:]
        self.log_view.configure(state='normal')
        self.log_view.delete('1.0', 'end')
        self.log_view.insert('end', '\n'.join(self.logs))
        self.log_view.configure(state='disabled')

    def persist(self):
        data = {'reduce_motion': getattr(self, 'reduce_motion', False) is True, 'appearance': self.appearance, 'format': self.format_menu.get(), 'folder': stored_recording_folder(self.folder),
                'microphone': self.mic_combo.get(),
                'speaker': self.out_combo.get(),
                'detect_new_windows': bool(self.detector.allow_new_windows),
                'auto_record': self.auto_record,
                'channel_mode': getattr(self, 'channel_mode', 'mixed'),
                'normalize': getattr(self, 'normalize', False) is True,
                'retention_days': int(getattr(self, 'retention_days', 0)),
                'backup_folder': getattr(self, 'backup_folder', ''),
                'enable_hotkey': getattr(self, 'enable_hotkey', True) is True,
                'floating_widget': getattr(self, 'floating_widget', True) is True,
                'gemini_api_key': getattr(self, 'gemini_api_key', '')}
        self.settings = data
        try:
            save_settings(data)
        except OSError as ex:
            self.log('Không lưu được cài đặt: ' + str(ex))

    def toggle_new_windows(self):
        self.detector.allow_new_windows = bool(self.detector_switch.get())
        self.persist()
        self.log('Nhận diện tiến trình gọi chuyên biệt: ' + ('BẬT' if self.detector.allow_new_windows else 'TẮT'))

    def toggle_motion(self):
        self.reduce_motion = bool(self.motion_switch.get())
        self.persist()

    def _sync_tray(self):
        if self.tray:
            state = self.recorder.state
            if state == 'blocked' or (state == 'idle' and self._tray_error):
                state = 'error'
            try:
                update_tray_state(self.tray, state)
            except Exception as ex:
                self.logger.debug('Tray update failed: %s', ex)

    def test_audio(self):
        if self.recorder.state != 'idle' or self.pending_popup or self.active_call_keys:
            messagebox.showinfo('Kiểm tra âm thanh', 'Hãy chờ cuộc gọi và phiên ghi hiện tại kết thúc.', parent=self)
            return
        self._test_mode = True
        self._test_deadline = None
        self.current_call_key = None
        self.current_caller_name = 'Kiểm tra âm thanh'
        if not self._start_recording():
            self._test_mode = False
            return
        self.current_file_label.configure(text='Thu thử 8 giây khi thiết bị sẵn sàng. Hãy nói và phát âm thanh qua loa/tai nghe.')

    def change_theme(self, choice):
        self.appearance = 'Dark' if choice == 'Tối' else 'Light'
        ctk.set_appearance_mode(self.appearance)
        self.persist()

    def change_format(self, value):
        self.chosen_format = value
        self.persist()

    def reload_devices(self):
        if self.recorder.state != 'idle':
            return
        try:
            mics, speakers, default_mic, default_speaker = scan_devices()
            self.mics, self.speakers = mics, speakers
            mic_options = [device_name(d) for d in mics]
            speaker_options = [device_name(d) for d in speakers]
            self.mic_combo.configure(values=mic_options)
            self.out_combo.configure(values=speaker_options)
            prefer_mic = self.settings.get('microphone')
            prefer_speaker = self.settings.get('speaker')
            self.mic_combo.set(prefer_mic if prefer_mic in mic_options else
                               next((device_name(d) for d in mics if d['index'] == default_mic), mic_options[0]))
            self.out_combo.set(prefer_speaker if prefer_speaker in speaker_options else
                               next((device_name(d) for d in speakers if d['index'] == default_speaker), speaker_options[0]))
            self.persist()
            self.log('Đã đọc danh sách thiết bị micro / tai nghe.')
        except Exception as ex:
            self.log('Không đọc được thiết bị: ' + str(ex))
            messagebox.showwarning('Cấu hình âm thanh', str(ex), parent=self)

    def choose_folder(self):
        chosen = filedialog.askdirectory(parent=self, title='Chọn thư mục lưu bản ghi',
                                         initialdir=str(Path(self.folder).parent))
        if chosen:
            self.folder = chosen
            self.folder_label.configure(text='Lưu tại: ' + self.folder)
            self.persist()

    def open_folder(self):
        try:
            path = Path(self.folder)
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception as ex:
            messagebox.showerror('Không mở được thư mục', str(ex), parent=self)

    def open_zalo(self):
        launcher = find_zalo_launcher(self.last_processes)
        if launcher:
            try:
                os.startfile(str(launcher))
                self.log('Đã yêu cầu Windows mở Zalo.')
            except Exception as ex:
                messagebox.showerror('Lỗi mở Zalo', str(ex), parent=self)
        else:
            messagebox.showinfo('Hãy mở Zalo PC',
                'Chưa tìm được đường dẫn Zalo. Bạn hãy mở ứng dụng Zalo PC từ Desktop hoặc Start Menu, '
                'sau đó Zalo Call Companion sẽ tự kết nối.', parent=self)

    def _initial_zalo_check(self):
        if not self.last_processes:
            if messagebox.askyesno('Zalo PC chưa mở',
                    'Không thấy Zalo PC đang chạy. Bạn có muốn mở Zalo bây giờ?', parent=self):
                self.open_zalo()

    def _set_connected(self, running):
        if self.last_status_running == running:
            return
        self.last_status_running = running
        if running:
            self.zalo_sidebar_state.configure(text='● Zalo đang chạy', text_color=GREEN)
            self.connection_text.configure(text='Đã nhận diện Zalo PC')
            self.connection_chip.configure(text='ĐÃ KẾT NỐI', text_color=GREEN)
            self.connection_hint.configure(text='Đang quan sát cửa sổ cuộc gọi đến / đi.')
            self.log('Đã kết nối với tiến trình Zalo PC.')
        else:
            self.zalo_sidebar_state.configure(text='● Zalo chưa mở', text_color=GOLD)
            self.connection_text.configure(text='Chưa tìm thấy Zalo PC')
            self.connection_chip.configure(text='CHƯA KẾT NỐI', text_color=GOLD)
            self.connection_hint.configure(text='Mở Zalo để kích hoạt phát hiện cuộc gọi.')
            self.log('Chưa tìm thấy Zalo PC đang chạy.')

    def diagnostics(self):
        """Save snapshot to user's chosen location; no messages/audio collected."""
        path = filedialog.asksaveasfilename(parent=self, title='Lưu chẩn đoán Zalo',
                    defaultextension='.txt', filetypes=[('Văn bản', '*.txt')],
                    initialfile='kiem-tra-cua-so-zalo.txt')
        if not path:
            return
        try:
            processes = zalo_processes()
            windows = windows_for_pids(set(processes))
            Path(path).write_text(describe_windows(windows, processes), encoding='utf-8')
            self.log('Đã lưu chẩn đoán cửa sổ Zalo.')
            messagebox.showinfo('Đã lưu',
                'Đã lưu thông tin cửa sổ Zalo. Nếu bạn chia sẻ để nhờ hỗ trợ, hãy xem lại tên cửa sổ '
                'vì có thể chứa tên người liên hệ.', parent=self)
        except Exception as ex:
            messagebox.showerror('Lỗi', str(ex), parent=self)

    def manual_confirm(self):
        if self.recorder.state != 'idle':
            return
        key = None
        if len(self.active_call_keys) == 1:
            if messagebox.askyesno('Tự dừng khi kết thúc gọi?',
                    'Gắn bản ghi với cuộc gọi đang nhận diện?\nCó: tự dừng khi cuộc gọi kết thúc.\nKhông: ghi đến khi bạn bấm Dừng & lưu.', parent=self):
                key = next(iter(self.active_call_keys))
        self._show_decision(key, 'Tự dừng theo cuộc gọi.' if key is not None else 'Ghi thủ công: bấm Dừng & lưu khi xong.')

    def _show_decision(self, key, reason):
        if self.pending_popup or self.recorder.state != 'idle':
            return
        if self.state() == 'withdrawn':
            self.show_window()
        caller_name = next((caller_from_title(w.title) for w in self.last_windows if w.hwnd == key), '')
        def accept(name=''):
            self.pending_popup = None
            if key is not None and key not in self.active_call_keys:
                self.log('Cuộc gọi không còn được nhận diện; bỏ qua yêu cầu ghi âm cũ.')
                return
            self.current_call_key = key
            self.current_caller_name = name
            self.lost_call_since = None
            self._start_recording()
        def decline():
            self.pending_popup = None
            if key is not None:
                self.detector.dismiss(key)
            self.log('Bỏ qua ghi âm cuộc gọi (hoặc hết 30 giây).')
        self.pending_popup = ConfirmPopup(self, reason, accept, decline, caller_name=caller_name)
        self.log('Hiện thông báo hỏi có ghi âm cuộc gọi không.')

    def _selected_index(self, devices, combo):
        name = combo.get()
        for d in devices:
            if device_name(d) == name:
                return int(d['index'])
        raise RuntimeError('Thiết bị đã thay đổi. Hãy bấm “Làm mới” rồi chọn lại.')

    def _start_recording(self, automatic=False):
        try:
            # Device indexes may move when a headset is unplugged. Resolve the
            # selected endpoint by its full name, never silently switch devices.
            if self.library and self.library.winfo_exists():
                self.library.stop_playback()
            microphones, speakers, _, _ = scan_devices()
            mic = resolve_device(microphones, self.mic_combo.get())
            speaker = resolve_device(speakers, self.out_combo.get())
            testing = getattr(self, '_test_mode', False) is True
            self.recorder.session_details = {'devices': {
                'microphone': next(d['name'] for d in microphones if int(d['index']) == mic),
                'speaker': next(d['name'] for d in speakers if int(d['index']) == speaker)},
                'purpose': 'audio_check' if testing else 'call'}
            folder = app_root() / 'Data' / 'AudioChecks' if testing else Path(self.folder)
            channel_mode = 'mixed' if testing else getattr(self, 'channel_mode', 'mixed')
            normalize = getattr(self, 'normalize', False)
            if not self.recorder.start(mic, speaker, folder, self.format_menu.get(), self.current_caller_name,
                                      channel_mode=channel_mode, normalize=normalize):
                self.current_call_key = None
                return
            if getattr(self, 'floating_widget', True) and not testing:
                try:
                    if self.mini_overlay and self.mini_overlay.winfo_exists():
                        self.mini_overlay.destroy()
                    self.mini_overlay = MiniOverlay(self, on_stop=self.stop_recording, on_expand=self.show_window)
                except Exception:
                    pass
            self._tray_error = False
            self.test_btn.configure(state='disabled')
            self.record_btn.configure(state='disabled')
            self.stop_btn.configure(state='normal')
            self.mic_combo.configure(state='disabled')
            self.out_combo.configure(state='disabled')
            self.format_menu.configure(state='disabled')
            self.recording_state.configure(text='● ĐANG MỞ THIẾT BỊ', text_color=GOLD)
            self.current_file_label.configure(text='Đang ghi: ' + self.recorder.recording_file.name)
            self.log('Đang mở hai nguồn thu (' + ('tự động' if automatic else 'đã xác nhận') + ').')
            self._notify('Đang bắt đầu ghi cuộc gọi. Chọn Dừng & lưu trong menu khay để dừng.')
            self.quiet_since = {'speaker': time.monotonic(), 'microphone': time.monotonic()}
            self._sync_tray()
            return True
        except Exception as ex:
            self.current_call_key = None
            self._tray_error = True
            self._sync_tray()
            self.log('Không thể bắt đầu ghi âm: ' + str(ex))
            self.current_file_label.configure(text='Không thể ghi: ' + str(ex))
            if automatic:
                self._notify('Không thể ghi âm: ' + str(ex))
            else:
                messagebox.showerror('Không thể ghi âm', str(ex), parent=self)

    def stop_recording(self):
        if self.recorder.stop():
            self.current_call_key = None
            self.stop_btn.configure(state='disabled')
            self.recording_state.configure(text='● ĐANG LƯU', text_color=GOLD)
            self.log('Đang ghép và lưu bản ghi âm thanh...')

    def _restore_controls(self):
        if hasattr(self, 'mini_overlay') and self.mini_overlay and self.mini_overlay.winfo_exists():
            try:
                self.mini_overlay.destroy()
            except Exception:
                pass
            self.mini_overlay = None
        self.test_btn.configure(state='normal')
        self.record_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.mic_combo.configure(state='normal')
        self.out_combo.configure(state='normal')
        self.format_menu.configure(state='normal')
        self.recording_state.configure(text='● CHƯA GHI', text_color=MUTED)
        self.timer_label.configure(text='00:00:00')

    def _poll(self):
        # Poll GUI queue in main thread. Windows window enumeration is cheap;
        # no third-party Zalo process data or messages are read.
        self.recorder.retry_completion()
        self.recorder.refresh()
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == 'saved':
                    self._tray_error = bool(read_json(Path(message).with_suffix(Path(message).suffix + '.json')).get('warnings'))
                    self._restore_controls()
                    self.current_file_label.configure(text='Đã lưu: ' + Path(message).name)
                    self.log('Đã lưu thành công: ' + Path(message).name)
                    self._notify('Đã lưu: ' + Path(message).name)
                    backup = getattr(self, 'backup_folder', None)
                    if isinstance(backup, str) and backup.strip() and Path(backup).is_dir():
                        def do_backup(src_path):
                            try:
                                src = Path(src_path)
                                dest_dir = Path(backup)
                                shutil.copy2(src, dest_dir / src.name)
                                sidecar = src.with_suffix(src.suffix + '.json')
                                if sidecar.is_file():
                                    shutil.copy2(sidecar, dest_dir / sidecar.name)
                                self.events.put(('info', f'Đã sao lưu phụ sang: {dest_dir.name}'))
                            except Exception as e:
                                self.events.put(('info', f'Lỗi sao lưu phụ: {e}'))
                        threading.Thread(target=do_backup, args=(message,), daemon=True).start()
                    if self.library and self.library.winfo_exists():
                        self.library.refresh()
                    if getattr(self, '_test_mode', False) is True:
                        self._test_mode = False
                        self._test_deadline = None
                        if not self.close_requested and not self.pending_signals:
                            if self.library and self.library.winfo_exists():
                                self.library.destroy()
                            self.library = LibraryWindow(self, Path(message).parent, self.recover_recording)
                            self.library.select_path(message, autoplay=True)
                    if self.close_requested:
                        self.persist()
                        self.destroy()
                        return
                elif kind == 'error':
                    self._test_mode = False
                    self._test_deadline = None
                    self._tray_error = True
                    self.close_requested = False
                    self._restore_controls()
                    self.log('Lỗi lưu bản ghi âm.')
                    self.recording_state.configure(text='● LƯU BỊ LỖI', text_color=RED)
                    self.current_file_label.configure(text='Lưu lỗi — mở Nhật ký / Khôi phục để kiểm tra.')
                    self.log(message)
                    self._notify('Lưu bản ghi gặp lỗi. Mở ứng dụng để kiểm tra và khôi phục.')
                    if self.state() != 'withdrawn':
                        messagebox.showerror('Ghi âm gặp lỗi', message, parent=self)
                elif kind == 'blocked':
                    self.close_requested = False
                    self.record_btn.configure(state='disabled')
                    self.stop_btn.configure(state='disabled')
                    self.recording_state.configure(text='● CHỜ THIẾT BỊ', text_color=GOLD)
                    self.log(message)
                elif kind == 'info':
                    self.log(message)
                elif kind == 'ready':
                    if self.recorder.state == 'recording':
                        self.recording_state.configure(text='● ĐANG THU THỬ' if getattr(self, '_test_mode', False) is True else '● ĐANG GHI', text_color=RED)
                        self.log(message)
                        if getattr(self, '_test_mode', False) is True:
                            self._test_deadline = time.monotonic() + 8
                elif kind == 'show':
                    self.show_window()
                elif kind == 'stop':
                    self.stop_recording()
                elif kind == 'hotkey':
                    if self.recorder.state in ('starting', 'recording'):
                        self.log('Phím tắt: Dừng & lưu cuộc gọi.')
                        self.stop_recording()
                    elif self.recorder.state == 'idle':
                        self.log('Phím tắt: Bắt đầu ghi âm.')
                        self.manual_confirm()
                elif kind == 'quit':
                    self.show_window()
                    self.on_close()
                    if getattr(self, "_destroyed", False) is True:
                        return
        except queue.Empty:
            pass
        try:
            self.last_processes = zalo_processes()
            running = bool(self.last_processes)
            self._set_connected(running)
            self.last_windows = windows_for_pids(set(self.last_processes)) if running else []
            signals, active = self.detector.update(self.last_windows, running)
            self.active_call_keys = active
            if signals and getattr(self, '_test_mode', False) is True and self.recorder.state in ('starting', 'recording'):
                self.log('Có cuộc gọi: dừng bài kiểm tra âm thanh để ưu tiên cuộc gọi.')
                self.stop_recording()
            if self.recorder.state in ('starting', 'recording') and self.current_call_key is not None:
                # A ringing window may be replaced by another HWND when answered.
                # Only a stable, positively identified call window can take over.
                ended = any(w.hwnd == self.current_call_key and any(t in plain(w.title)
                    for t in ('cuoc goi ket thuc', 'da ket thuc', 'ket thuc cuoc goi',
                              'call ended', 'call finished', 'missed call', 'khong bat may', 'khong tra loi'))
                    for w in self.last_windows)
                candidates = [w for w in self.last_windows if w.hwnd in active and
                    (looks_like_call_title(w.title) or is_call_process_window(w))]
                current = next((w for w in candidates if w.hwnd == self.current_call_key), None)
                if current is None and not ended and len(candidates) == 1:
                    candidate = candidates[0]
                    name = caller_from_title(candidate.title)
                    old_name = self.current_caller_name
                    if not old_name or not name or plain(old_name) == plain(name):
                        current = candidate
                        self.current_call_key = candidate.hwnd
                        self.log('Đã chuyển sang cửa sổ cuộc gọi mới; tiếp tục cùng bản ghi.')
                if current is not None:
                    self.lost_call_since = None
                    name = caller_from_title(current.title)
                    if name and not self.current_caller_name:
                        self.recorder.set_caller_name(name)
                        self.current_caller_name = name
                        self.current_file_label.configure(text='Đang ghi: ' + self.recorder.recording_file.name)
                    self.pending_signals.pop(current.hwnd, None)
                    signals = [s for s in signals if s.key != current.hwnd]
                elif self.current_call_key not in active or ended:
                    if self.lost_call_since is None:
                        self.lost_call_since = time.monotonic()
                    if ended or time.monotonic() - self.lost_call_since >= 5:
                        self.log('Cuộc gọi đã kết thúc hoặc cửa sổ đã đóng: tự dừng & lưu.')
                        self.stop_recording()
                else:
                    self.lost_call_since = None
            if signals:
                self.pending_signals[signals[0].key] = signals[0]
            self.pending_signals = {key: signal for key, signal in self.pending_signals.items() if key in active}
            if self.pending_signals and not self.pending_popup and self.recorder.state == 'idle':
                key = next(iter(self.pending_signals))
                signal = self.pending_signals.pop(key)
                self._handle_signal(signal)
            for additional in signals[1:]:
                # Ignore extra call windows from the same incoming/outgoing session.
                self.detector.dismiss(additional.key)
            if self.recorder.state in ('starting', 'recording') and self.recorder.error_if_any():
                self.log('Thiết bị gặp lỗi; lưu phần đã thu: ' + self.recorder.error_if_any())
                self.stop_recording()
        except Exception as ex:
            self.log('Lỗi nhận diện tạm thời: ' + str(ex)[:95])
        self._sync_tray()
        self.after(750, self._poll)

    def _clock(self):
        self.recorder.refresh()
        if getattr(self, '_test_mode', False) is True and self.recorder.state == 'recording':
            if self._test_deadline is not None and time.monotonic() >= self._test_deadline:
                self._test_deadline = None
                self.stop_recording()
        if hasattr(self, 'mini_overlay') and self.mini_overlay and self.mini_overlay.winfo_exists():
            try:
                self.mini_overlay.update_time(self.timer_label.cget('text'))
            except Exception:
                pass
        if self.recorder.state == 'recording' and self.recorder.recorded_from:
            seconds = int(time.monotonic() - self.recorder.recorded_from)
            self.timer_label.configure(text=f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}')
        elif self.recorder.state in ('saving', 'blocked'):
            seconds = int(self.recorder.elapsed)
            self.timer_label.configure(text=f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}')
        quiet = []
        for role, meter in self.audio_meters.items():
            level = self.recorder.levels.get(role, 0) if self.recorder.state == 'recording' else 0
            meter.set(min(1, level ** 0.5))
            if self.recorder.state == 'recording':
                if level > 0.005:
                    self.quiet_since[role] = time.monotonic()
                elif time.monotonic() - self.quiet_since.get(role, time.monotonic()) >= 10:
                    quiet.append('micro' if role == 'microphone' else 'loa/tai nghe')
        self.audio_hint.configure(text=('Chưa thấy tín hiệu từ ' + ', '.join(quiet) + ' — kiểm tra thiết bị nếu đang nói.')
                                  if quiet else 'Mức âm hiển thị khi ghi; im lặng không tự dừng phiên.',
                                  text_color=GOLD if quiet else MUTED)
        if getattr(self, '_test_mode', False) is True and self.recorder.state == 'recording' and self._test_deadline is not None:
            remaining = max(0, int(self._test_deadline - time.monotonic() + 0.999))
            self.audio_hint.configure(text=f'Thu thử còn {remaining} giây • Hãy nói vào micro và phát âm thanh trên loa.', text_color=BLUE)
        self.after(500, self._clock)

    def on_close(self):
        if self.recorder.state in ('starting', 'recording'):
            if messagebox.askyesno('Dừng ghi âm?', 'Dừng, lưu bản ghi rồi đóng phần mềm?', parent=self):
                self.close_requested = True
                self.stop_recording()
        elif self.recorder.state in ('saving', 'blocked'):
            messagebox.showinfo('Đang lưu', 'Ứng dụng đang lưu bản ghi. Hãy đóng sau khi lưu xong.', parent=self)
        else:
            if self.pending_popup:
                self.pending_popup.decline()
            self.persist()
            self.destroy()

if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit('Chương trình chỉ chạy trên Windows 10/11.')
    instance = SingleInstance()
    try:
        if instance.primary:
            Companion(instance).mainloop()
    finally:
        instance.close()
