from pathlib import Path
import os
import threading
from audio_player import AudioPlayer
from ui_effects import fade_in, ManagedToplevel
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from recording_library import (
    list_recordings, recovery_candidates, rename_recording, matches_date,
    session_description, filter_records, read_json, atomic_json,
    update_record_metadata, filter_date_range, export_recordings_csv,
    add_timestamp_mark, remove_timestamp_mark, transcribe_with_gemini
)


class LibraryWindow(ManagedToplevel):
    def __init__(self, parent, folder, on_recover):
        super().__init__(parent)
        self.owner = parent
        self.player = AudioPlayer()
        self._tick_id = None
        self._search_job = None
        self._dragging_seek = False
        self._cached_records = []
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.title('Ghi Âm Zalo PC — Bản ghi')
        self.configure(fg_color=('#F2F2F7', '#111114'))
        self.geometry('1080x780')
        self.minsize(880, 660)
        self.folder = Path(folder)
        self.on_recover = on_recover
        preferences = read_json(self.folder / '.library-preferences.json')
        try:
            self.player.set_volume(float(preferences.get('volume', 80)))
        except (ValueError, TypeError, OverflowError):
            self.player.set_volume(80)
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=22, pady=(18, 0))
        ctk.CTkLabel(header, text='Thư viện cuộc gọi', font=('Segoe UI', 25, 'bold')).pack(side='left')
        self.overview = ctk.CTkLabel(header, text='', font=('Segoe UI', 12), text_color=('#636366', '#AEAEB2'))
        ctk.CTkButton(header, text='Mở thư mục', width=110, height=32, command=self.open_folder).pack(side='right', padx=(12, 0))
        self.overview.pack(side='right')
        self.search = ctk.CTkEntry(self, placeholder_text='Tìm tên hoặc ghi chú · không cần gõ dấu…', height=40,
            corner_radius=12, fg_color=('#FFFFFF', '#1C1C1E'), border_color=('#E5E5EA', '#38383A'), text_color=('#1C1C1E', '#F5F5F7'))
        self.search.pack(fill='x', padx=18, pady=(18, 8))
        self.search.bind('<KeyRelease>', self._schedule_search)
        self.bind('<Control-f>', lambda _: self.search.focus_set())
        self.date_filter = ctk.CTkSegmentedButton(self,
            values=['Tất cả ngày', 'Hôm nay', '7 ngày qua', '30 ngày qua'], command=lambda _: self.refresh(False), height=34)
        self.date_filter.set('Tất cả ngày')
        self.date_filter.pack(fill='x', padx=18, pady=(0, 8))
        filters = ctk.CTkFrame(self, fg_color='transparent')
        filters.pack(fill='x', padx=20, pady=(0, 4))
        self.favorite_filter = ctk.CTkSwitch(filters, text='Chỉ bản quan trọng', command=lambda: self.refresh(False))
        self.favorite_filter.pack(side='left')
        self.sort_menu = ctk.CTkOptionMenu(filters, values=['Mới nhất', 'Cũ nhất', 'Tên A–Z', 'Dài nhất'],
            command=lambda _: self.refresh(False), width=150)
        self.sort_menu.pack(side='right')
        date_range = ctk.CTkFrame(self, fg_color='transparent')
        date_range.pack(fill='x', padx=20, pady=4)
        self.range_start = ctk.CTkEntry(date_range, placeholder_text='Từ DD/MM/YYYY', width=150)
        self.range_start.pack(side='left', padx=(0, 6))
        self.range_end = ctk.CTkEntry(date_range, placeholder_text='Đến DD/MM/YYYY', width=150)
        self.range_end.pack(side='left', padx=6)
        ctk.CTkButton(date_range, text='Áp dụng', width=85, command=lambda: self.refresh(False)).pack(side='left', padx=6)
        ctk.CTkButton(date_range, text='Bỏ khoảng ngày', width=115, command=self.clear_date_range).pack(side='left', padx=6)
        ctk.CTkButton(date_range, text='Xuất CSV', width=100, command=self.export_csv).pack(side='right')
        self.tabs = ctk.CTkTabview(self, fg_color=('#FFFFFF', '#1C1C1E'), corner_radius=16)
        self.tabs.pack(fill='both', expand=True, padx=18, pady=8)
        saved = self.tabs.add('Bản ghi')
        recovery = self.tabs.add('Khôi phục')
        self.apply_tree_theme()
        self.tree = ttk.Treeview(saved, height=6, columns=('name', 'date', 'duration', 'status'),
                                style='Recordings.Treeview', show='headings', selectmode='browse')
        for key, label, width in [('name', 'Tên bản ghi', 390), ('date', 'Ngày ghi', 140),
                                   ('duration', 'Thời lượng', 85), ('status', 'Trạng thái', 130)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        saved.grid_rowconfigure(0, weight=1)
        saved.grid_columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(saved, orient='vertical', command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<ButtonRelease-1>', self._select_recording)
        self.tree.bind('<KeyRelease-Up>', self._select_recording)
        self.tree.bind('<KeyRelease-Down>', self._select_recording)
        self.tree.bind('<Return>', lambda _: self.play())
        self.tree.bind('<space>', lambda _: self._key_action(self.play))
        self.tree.bind('<Left>', lambda _: self._key_action(lambda: self._skip(-10)))
        self.tree.bind('<Right>', lambda _: self._key_action(lambda: self._skip(10)))
        player = ctk.CTkFrame(saved, fg_color=('#F2F2F7', '#111114'), corner_radius=12)
        player.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        player.grid_columnconfigure(1, weight=1)
        self.play_button = ctk.CTkButton(player, text='Phát', width=95, command=self.play)
        self.play_button.grid(row=0, column=0, padx=8, pady=8)
        self.seek_bar = ctk.CTkSlider(player, from_=0, to=1, command=self._seek)
        self.seek_bar.bind('<ButtonPress-1>', lambda _: setattr(self, '_dragging_seek', True), add=True)
        self.seek_bar.bind('<ButtonRelease-1>', lambda _: setattr(self, '_dragging_seek', False), add=True)
        self.seek_bar.set(0)
        self.seek_bar.grid(row=0, column=1, sticky='ew', padx=8)
        self.play_time = ctk.CTkLabel(player, text='00:00 / 00:00', width=115)
        self.play_time.grid(row=0, column=2, padx=8)
        self.play_hint = ctk.CTkLabel(player, text='Chọn một bản ghi để nghe ngay', anchor='w')
        self.play_hint.configure(wraplength=720, font=('Segoe UI', 12))
        self.play_hint.grid(row=1, column=0, columnspan=3, sticky='ew', padx=12, pady=(0, 6))

        transport = ctk.CTkFrame(player, fg_color='transparent')
        transport.grid(row=2, column=0, columnspan=3, sticky='ew', padx=8, pady=(0, 10))
        for title, seconds in [('−10 giây', -10), ('+10 giây', 10)]:
            ctk.CTkButton(transport, text=title, width=88, height=30,
                command=lambda n=seconds: self._skip(n)).pack(side='left', padx=3)
        self.volume_label = ctk.CTkLabel(transport, text=f'Âm lượng {self.player.volume}%', width=105)
        self.volume_label.pack(side='left', padx=(10, 2))
        self.volume_slider = ctk.CTkSlider(transport, from_=0, to=100, width=130, command=self._volume)
        self.volume_slider.set(self.player.volume)
        self.volume_slider.pack(side='left', padx=2)

        ctk.CTkLabel(transport, text='Tốc độ:', width=45).pack(side='left', padx=(12, 2))
        self.speed_menu = ctk.CTkSegmentedButton(transport, values=['0.75x', '1.0x', '1.25x', '1.5x', '2.0x'],
            command=self._change_speed, height=28)
        self.speed_menu.set('1.0x')
        self.speed_menu.pack(side='left', padx=2)

        buttons = ctk.CTkFrame(saved, fg_color='transparent')
        buttons.grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        for label, command in [('Dừng nghe', self.stop_playback), ('Đổi tên', self.rename),
                               ('Chi tiết / Ghi chú', self.show_details), ('★ Quan trọng', self.toggle_favorite),
                               ('+ Đánh dấu mốc', self.add_bookmark), ('Bóc băng AI', self.ai_transcribe),
                               ('Làm mới', self.refresh)]:
            ctk.CTkButton(buttons, text=label, width=110, height=36, corner_radius=12,
                          fg_color=('#E8F2FF', '#172C46'), hover_color=('#D7E8FC', '#203C5C'),
                          text_color=('#0066CC', '#64ADFF'), command=command).pack(side='left', padx=3)

        self.recovery_tree = ttk.Treeview(recovery, columns=('name',), style='Recordings.Treeview', show='headings', selectmode='browse')
        self.recovery_tree.heading('name', text='Phiên chưa lưu — WAV gốc được giữ lại sau khôi phục')
        recovery.grid_rowconfigure(0, weight=1)
        recovery.grid_columnconfigure(0, weight=1)
        self.recovery_tree.grid(row=0, column=0, sticky='nsew')
        ctk.CTkButton(recovery, text='Khôi phục phiên đã chọn', command=self.recover).grid(row=1, column=0, pady=10)
        self.summary = ctk.CTkLabel(self, text='')
        self.summary.pack(pady=(0, 10))
        self.records = []
        self.refresh()
        self.after(100, self.lift)
        self._tick()
        fade_in(self, getattr(parent, 'reduce_motion', False) is not True)

    def _change_speed(self, value):
        try:
            factor = float(value.replace('x', ''))
            self.player.set_speed(factor)
        except Exception:
            pass

    def add_bookmark(self):
        path = self.selected()
        if not path:
            messagebox.showinfo('Đánh dấu mốc', 'Hãy chọn một bản ghi trước.', parent=self)
            return
        _, pos_ms = self.player.status()
        pos_sec = round(pos_ms / 1000.0, 1)
        dialog = ctk.CTkInputDialog(text=f'Ghi chú cho mốc {int(pos_sec//60):02d}:{int(pos_sec%60):02d}:', title='Thêm mốc thời gian')
        label = dialog.get_input()
        if label is not None:
            try:
                add_timestamp_mark(path, pos_sec, label)
                self.refresh(False)
                messagebox.showinfo('Đã thêm mốc', f'Đã thêm mốc {int(pos_sec//60):02d}:{int(pos_sec%60):02d} - {label}', parent=self)
            except Exception as ex:
                messagebox.showerror('Lỗi', str(ex), parent=self)

    def ai_transcribe(self):
        path = self.selected()
        if not path:
            messagebox.showinfo('Bóc băng AI', 'Hãy chọn một bản ghi trước.', parent=self)
            return
        key = getattr(self.owner, 'settings', {}).get('gemini_api_key', '').strip()
        if not key:
            key_dialog = ctk.CTkInputDialog(text='Nhập Google Gemini API Key của bạn (miễn phí tại aistudio.google.com):', title='Nhập Gemini API Key')
            input_key = key_dialog.get_input()
            if not input_key:
                return
            key = input_key.strip()
            self.owner.settings['gemini_api_key'] = key
            self.owner.persist()
        self.play_hint.configure(text='Đang gửi audio đến Gemini AI để bóc băng và tóm tắt... Vui lòng đợi trong giây lát.')
        def run_ai():
            try:
                res = transcribe_with_gemini(key, path)
                self.after(0, lambda: self._on_transcribe_done(path, res))
            except Exception as ex:
                self.after(0, lambda: (self.play_hint.configure(text='Bóc băng gặp lỗi.'), messagebox.showerror('Lỗi bóc băng AI', str(ex), parent=self)))
        threading.Thread(target=run_ai, daemon=True).start()

    def _on_transcribe_done(self, path, result):
        self.refresh(False)
        self.play_hint.configure(text='Đã bóc băng AI thành công!')
        self.show_details()

    def apply_tree_theme(self):
        dark = ctk.get_appearance_mode() == 'Dark'
        bg, fg, header = ('#1C1C1E', '#F5F5F7', '#38383A') if dark else ('#FFFFFF', '#1C1C1E', '#E5E5EA')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Recordings.Treeview', rowheight=38, font=('Segoe UI', -13),
                        background=bg, fieldbackground=bg, foreground=fg, bordercolor=header)
        style.configure('Recordings.Treeview.Heading', background=header, foreground=fg,
                        font=('Segoe UI', -13, 'bold'))
        style.map('Recordings.Treeview', background=[('selected', '#007AFF')],
                  foreground=[('selected', '#FFFFFF')])
        style.map('Recordings.Treeview.Heading', background=[('active', header)])

    def _set_appearance_mode(self, mode):
        super()._set_appearance_mode(mode)
        if hasattr(self, 'tree'):
            self.apply_tree_theme()

    def clear_date_range(self):
        self.range_start.delete(0, 'end')
        self.range_end.delete(0, 'end')
        self.refresh(False)

    def export_csv(self):
        try:
            records = self.current_filtered_records()
            if not records:
                messagebox.showinfo('Xuất CSV', 'Không có bản ghi nào để xuất.', parent=self)
                return
            destination = filedialog.asksaveasfilename(parent=self, title='Xuất danh sách ra CSV',
                defaultextension='.csv', filetypes=[('Bảng CSV Excel', '*.csv')],
                initialfile=f'danh-sach-ban-ghi-{len(records)}.csv')
            if destination:
                export_recordings_csv(records, destination)
                messagebox.showinfo('Xuất CSV', f'Đã xuất {len(records)} bản ghi ra file CSV thành công.', parent=self)
        except Exception as ex:
            messagebox.showerror('Xuất CSV gặp lỗi', str(ex), parent=self)

    def current_filtered_records(self):
        query = self.search.get()
        period = self.date_filter.get()
        starred = bool(self.favorite_filter.get())
        order = self.sort_menu.get()
        records = filter_records(self._cached_records, query, period, starred, order)
        start = self.range_start.get().strip()
        end = self.range_end.get().strip()
        if start or end:
            records = filter_date_range(records, start, end)
        return records

    def _schedule_search(self, _):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(200, lambda: self.refresh(False))

    def _key_action(self, func):
        func()
        return 'break'

    def _select_recording(self, _=None):
        path = self.selected()
        if path:
            self.play_hint.configure(text=path.name)

    def selected(self):
        selection = self.tree.selection()
        return Path(selection[0]) if selection else None

    def refresh(self, reload_files=True):
        selected_id = self.selected()
        if reload_files or not self._cached_records:
            try:
                self._cached_records = list_recordings(self.folder)
            except OSError:
                self._cached_records = []
        try:
            records = self.current_filtered_records()
        except ValueError as ex:
            messagebox.showwarning('Khoảng ngày không hợp lệ', str(ex), parent=self)
            return
        self.records = records
        self.tree.delete(*self.tree.get_children())
        for r in records:
            dur = r['duration']
            dtext = f'{int(dur//60):02d}:{int(dur%60):02d}' if dur is not None else '--:--'
            star = '★ ' if r.get('metadata', {}).get('favorite') else ''
            self.tree.insert('', 'end', iid=str(r['path']),
                             values=(star + r['name'], r['date'], dtext, r['status']))
        if selected_id and self.tree.exists(str(selected_id)):
            self.tree.selection_set(str(selected_id))
        total_time = sum((r['duration'] or 0) for r in self._cached_records)
        hours = total_time // 3600
        mins = (total_time % 3600) // 60
        self.overview.configure(text=f'{len(self._cached_records)} bản ghi · {int(hours)} giờ {int(mins)} phút')
        self.summary.configure(text=f'Đang hiển thị {len(records)} / {len(self._cached_records)} bản ghi')
        self.recoveries = recovery_candidates(self.folder)
        self.recovery_tree.delete(*self.recovery_tree.get_children())
        for index, item in enumerate(self.recoveries):
            self.recovery_tree.insert('', 'end', iid=str(index), values=(item.name,))
        self.tabs.set('Bản ghi' if self.records or not self.recoveries else 'Khôi phục')

    def play(self):
        path = self.selected() or self.player.path
        if not path:
            return
        if self.owner and getattr(self.owner.recorder, 'state', 'idle') != 'idle':
            self.play_hint.configure(text='Đợi thu âm và lưu xong để nghe lại, tránh lọt tiếng phát vào bản ghi.')
            return
        try:
            if self.player.path != path:
                self._remember_playback()
                self.player.load(path)
                data = read_json(path.with_suffix(path.suffix + '.json'))
                try:
                    position = max(0, int(data.get('playback_position_ms', 0)))
                except (TypeError, ValueError, OverflowError):
                    position = 0
                if 0 < position < self.player.length - 1500:
                    self.player.seek(position)
                self.seek_bar.configure(to=max(1, self.player.length))
            self.player.toggle()
            self._remember_playback()
            self.play_hint.configure(text=path.name)
        except Exception as ex:
            self.stop_playback()
            self.play_hint.configure(text='Không phát được: ' + str(ex))

    def show_details(self):
        path = self.selected()
        if path:
            dialog = ManagedToplevel(self)
            dialog.title('Thông tin phiên ghi âm')
            dialog.geometry('740x700')
            dialog.minsize(580, 540)
            dialog.transient(self)
            ctk.CTkLabel(dialog, text=path.stem, font=('Segoe UI', 18, 'bold'),
                         wraplength=520).pack(padx=24, pady=(18, 10))

            metadata = read_json(path.with_suffix(path.suffix + '.json'))

            timestamps = metadata.get('timestamps', [])
            if timestamps:
                ctk.CTkLabel(dialog, text='Mốc thời gian (bấm để nghe từ mốc):', font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=24, pady=(4, 2))
                ts_frame = ctk.CTkScrollableFrame(dialog, height=52, orientation='horizontal', fg_color='transparent')
                ts_frame.pack(fill='x', padx=24, pady=(0, 6))
                for ts in timestamps:
                    sec = ts.get('time', 0)
                    lbl = ts.get('label', '')
                    time_str = f"{int(sec//60):02d}:{int(sec%60):02d}"
                    ctk.CTkButton(ts_frame, text=f"⏱ {time_str} - {lbl}", height=30, corner_radius=8,
                                  fg_color=('#E8F2FF', '#172C46'), text_color=('#0066CC', '#64ADFF'),
                                  command=lambda s=sec: (self.player.seek(int(s * 1000)), self.play() if self.player.status()[0] != 'playing' else None)).pack(side='left', padx=3)

            text = ctk.CTkTextbox(dialog, height=140, font=('Segoe UI', 13), wrap='word', corner_radius=14)
            text.pack(fill='x', padx=24, pady=(0, 8))
            text.insert('1.0', session_description(path))
            text.configure(state='disabled')

            transcription = metadata.get('transcription')
            if transcription:
                ctk.CTkLabel(dialog, text='Bản bóc băng & Tóm tắt AI (Gemini):', font=('Segoe UI', 13, 'bold'), text_color='#007AFF').pack(anchor='w', padx=24, pady=(4, 2))
                ai_box = ctk.CTkTextbox(dialog, height=160, wrap='word', font=('Segoe UI', 12))
                ai_box.pack(fill='both', expand=True, padx=24, pady=(0, 8))
                ai_box.insert('1.0', transcription)
                ai_box.configure(state='disabled')

            ctk.CTkLabel(dialog, text='Ghi chú riêng', font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=24)
            note = ctk.CTkTextbox(dialog, height=75, wrap='word', font=('Segoe UI', 13))
            note.pack(fill='x', padx=24, pady=(4, 6))
            note.insert('1.0', str(metadata.get('note', '')))
            feedback = ctk.CTkLabel(dialog, text='Ghi chú và mốc thời gian lưu trên máy của bạn.', font=('Segoe UI', 11), text_color=('#636366', '#AEAEB2'))
            feedback.pack(padx=24)
            def save_note():
                try:
                    value = note.get('1.0', 'end-1c').strip()
                    if len(value) > 5000:
                        raise ValueError('Ghi chú tối đa 5.000 ký tự.')
                    update_record_metadata(path, note=value)
                    self.refresh(False)
                    feedback.configure(text='Đã lưu ghi chú.')
                except Exception as ex:
                    feedback.configure(text='Không lưu được: ' + str(ex))
            ctk.CTkButton(dialog, text='Lưu ghi chú', command=save_note, height=36).pack(pady=(6, 14))
            dialog.after(100, dialog.lift)

    def toggle_favorite(self):
        path = self.selected()
        if not path:
            return
        try:
            data = read_json(path.with_suffix(path.suffix + '.json'))
            update_record_metadata(path, favorite=not bool(data.get('favorite')))
            self.refresh(False)
        except Exception as ex:
            self.play_hint.configure(text='Không đánh dấu được: ' + str(ex))

    def _remember_playback(self):
        if not self.player.path:
            return
        try:
            _, position = self.player.status()
            if self.player.length - position < 1500:
                position = 0
            update_record_metadata(self.player.path, playback_position_ms=position)
        except Exception as ex:
            self.play_hint.configure(text='Không lưu được vị trí nghe: ' + str(ex))

    def select_path(self, path, autoplay=False):
        key = str(Path(path))
        if self.tree.exists(key):
            self.tree.selection_set(key)
            self.tree.see(key)
            if autoplay:
                self.play()

    def _skip(self, seconds):
        try:
            self.player.skip(seconds)
        except Exception as ex:
            self.play_hint.configure(text='Không tua được: ' + str(ex))

    def _volume(self, value):
        try:
            self.player.set_volume(value)
            self.volume_label.configure(text=f'Âm lượng {self.player.volume}%')
        except Exception as ex:
            self.play_hint.configure(text='Không đổi được âm lượng: ' + str(ex))

    def stop_playback(self):
        self._remember_playback()
        self.player.close()
        self.play_button.configure(text='Phát')
        self.seek_bar.set(0)
        self.play_time.configure(text='00:00 / 00:00')
        self.play_hint.configure(text='Đã dừng nghe. Chọn bản ghi hoặc bấm Phát để nghe lại.')

    def _seek(self, value):
        try:
            self.player.seek(value)
        except Exception as ex:
            self.play_hint.configure(text='Không tua được: ' + str(ex))

    def _tick(self):
        try:
            mode, position = self.player.status()
            self.play_button.configure(text='Tạm dừng' if mode == 'playing' else 'Phát')
            if not self._dragging_seek:
                self.seek_bar.set(position)
            def stamp(ms):
                seconds = ms // 1000
                return f'{seconds // 60:02d}:{seconds % 60:02d}'
            self.play_time.configure(text=f'{stamp(position)} / {stamp(self.player.length)}')
        except Exception as ex:
            self.play_hint.configure(text='Lỗi phát âm thanh: ' + str(ex))
            self.player.close()
        self._tick_id = self.after(250, self._tick)

    def destroy(self):
        if getattr(self, '_fade_job', None):
            self.after_cancel(self._fade_job)
            self._fade_job = None
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        self._remember_playback()
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            atomic_json(self.folder / '.library-preferences.json', {'volume': self.player.volume})
        except OSError:
            pass
        self.player.close()
        super().destroy()

    def rename(self):
        path = self.selected()
        if not path:
            return
        name = ctk.CTkInputDialog(title='Đổi tên bản ghi', text='Tên mới (không cần .mp3 hoặc .wav):').get_input()
        if name is not None:
            try:
                if self.player.path == path:
                    self.stop_playback()
                destination = rename_recording(path, name)
                self.refresh()
                self.select_path(destination)
            except Exception as ex:
                messagebox.showerror('Không đổi được tên', str(ex), parent=self)

    def open_folder(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.folder))
        except OSError as ex:
            messagebox.showerror('Không mở được thư mục', str(ex), parent=self)

    def recover(self):
        selection = self.recovery_tree.selection()
        if selection:
            self.on_recover(self.recoveries[int(selection[0])])
