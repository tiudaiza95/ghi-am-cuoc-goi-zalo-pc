from pathlib import Path
import os
from audio_player import AudioPlayer
from tkinter import ttk, messagebox
import customtkinter as ctk
from recording_library import list_recordings, recovery_candidates, rename_recording


class LibraryWindow(ctk.CTkToplevel):
    def __init__(self, parent, folder, on_recover):
        super().__init__(parent)
        self.owner = parent
        self.player = AudioPlayer()
        self._tick_id = None
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.title('Ghi Âm Zalo PC — Bản ghi')
        self.configure(fg_color=('#F2F2F7', '#111114'))
        self.geometry('900x530')
        self.minsize(720, 420)
        self.folder = Path(folder)
        self.on_recover = on_recover
        self.search = ctk.CTkEntry(self, placeholder_text='Tìm theo tên bản ghi…', height=40,
            corner_radius=12, fg_color=('#FFFFFF', '#1C1C1E'), border_color=('#E5E5EA', '#38383A'), text_color=('#1C1C1E', '#F5F5F7'))
        self.search.pack(fill='x', padx=18, pady=(18, 8))
        self.search.bind('<KeyRelease>', lambda _: self.refresh())
        self.tabs = ctk.CTkTabview(self, fg_color=('#FFFFFF', '#1C1C1E'), corner_radius=16)
        self.tabs.pack(fill='both', expand=True, padx=18, pady=8)
        saved = self.tabs.add('Bản ghi')
        recovery = self.tabs.add('Khôi phục')
        self.apply_tree_theme()
        self.tree = ttk.Treeview(saved, columns=('name', 'date', 'duration', 'status'),
                                style='Recordings.Treeview', show='headings', selectmode='browse')
        for key, label, width in [('name', 'Tên bản ghi', 390), ('date', 'Ngày lưu', 140),
                                   ('duration', 'Thời lượng', 85), ('status', 'Trạng thái', 130)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        saved.grid_rowconfigure(0, weight=1)
        saved.grid_columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(saved, orient='vertical', command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<<TreeviewSelect>>', self._select_recording)
        player = ctk.CTkFrame(saved, fg_color=('#F2F2F7', '#111114'), corner_radius=12)
        player.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        player.grid_columnconfigure(1, weight=1)
        self.play_button = ctk.CTkButton(player, text='Phát', width=95, command=self.play)
        self.play_button.grid(row=0, column=0, padx=8, pady=8)
        self.seek_bar = ctk.CTkSlider(player, from_=0, to=1, command=self._seek)
        self.seek_bar.set(0)
        self.seek_bar.grid(row=0, column=1, sticky='ew', padx=8)
        self.play_time = ctk.CTkLabel(player, text='00:00 / 00:00', width=115)
        self.play_time.grid(row=0, column=2, padx=8)
        self.play_hint = ctk.CTkLabel(player, text='Chọn một bản ghi để nghe ngay', anchor='w')
        self.play_hint.grid(row=1, column=0, columnspan=3, sticky='ew', padx=12)

        buttons = ctk.CTkFrame(saved, fg_color='transparent')
        buttons.grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        for label, command in [('Dừng nghe', self.stop_playback), ('Đổi tên', self.rename),
                               ('Mở thư mục', self.open_folder), ('Làm mới', self.refresh)]:
            ctk.CTkButton(buttons, text=label, width=130, height=36, corner_radius=12,
                          fg_color=('#007AFF', '#0A84FF'), hover_color='#0064D4', command=command).pack(side='left', padx=4)
        self.recovery_tree = ttk.Treeview(recovery, columns=('name',), style='Recordings.Treeview', show='headings', selectmode='browse')
        self.recovery_tree.heading('name', text='Phiên chưa lưu — WAV gốc được giữ lại sau khôi phục')
        recovery.grid_rowconfigure(0, weight=1)
        recovery.grid_columnconfigure(0, weight=1)
        self.recovery_tree.grid(row=0, column=0, sticky='nsew')
        ctk.CTkButton(recovery, text='Khôi phục phiên đã chọn', command=self.recover).grid(row=1, column=0, pady=10)
        self.summary = ctk.CTkLabel(self, text='')
        self.summary.pack(pady=(0, 10))
        self.refresh()
        self.after(100, self.lift)
        self._tick()

    def apply_tree_theme(self):
        dark = ctk.get_appearance_mode() == 'Dark'
        bg, fg, header = ('#1C1C1E', '#F5F5F7', '#38383A') if dark else ('#FFFFFF', '#1C1C1E', '#E5E5EA')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Recordings.Treeview', rowheight=34, font=('Segoe UI', 11),
                        background=bg, fieldbackground=bg, foreground=fg, bordercolor=header)
        style.configure('Recordings.Treeview.Heading', background=header, foreground=fg,
                        font=('Segoe UI', 11, 'bold'))
        style.map('Recordings.Treeview', background=[('selected', '#007AFF')],
                  foreground=[('selected', '#FFFFFF')])
        style.map('Recordings.Treeview.Heading', background=[('active', header)])

    def _set_appearance_mode(self, mode):
        super()._set_appearance_mode(mode)
        if hasattr(self, 'tree'):
            self.apply_tree_theme()

    def refresh(self):
        try:
            records = list_recordings(self.folder)
            query = self.search.get().casefold()
            self.records = [r for r in records if query in r['name'].casefold()]
            self.tree.delete(*self.tree.get_children())
            for index, record in enumerate(self.records):
                duration = record['duration']
                seconds = int(duration) if duration is not None else None
                label = f'{seconds // 60:02d}:{seconds % 60:02d}' if seconds is not None else '—'
                self.tree.insert('', 'end', iid=str(index), values=(record['name'], record['date'], label, record['status']))
            self.recoveries = recovery_candidates(self.folder)
            self.recovery_tree.delete(*self.recovery_tree.get_children())
            for index, path in enumerate(self.recoveries):
                self.recovery_tree.insert('', 'end', iid=str(index), values=(path.name,))
            self.summary.configure(text=f'{len(self.records)} bản ghi • {len(self.recoveries)} phiên có thể khôi phục')
        except Exception as ex:
            messagebox.showerror('Không đọc được thư viện', str(ex), parent=self)

    def selected(self):
        selection = self.tree.selection()
        return self.records[int(selection[0])]['path'] if selection else None

    def _select_recording(self, _event=None):
        path = self.selected()
        if path and path != self.player.path:
            self.play()

    def play(self):
        path = self.selected()
        if not path:
            return
        if self.owner.recorder.state != 'idle':
            self.play_hint.configure(text='Đợi thu âm và lưu xong để nghe lại, tránh lọt tiếng phát vào bản ghi.')
            return
        try:
            if self.player.path != path:
                self.player.load(path)
                self.seek_bar.configure(to=max(1, self.player.length))
            self.player.toggle()
            self.play_hint.configure(text=path.name)
        except Exception as ex:
            self.stop_playback()
            self.play_hint.configure(text='Không phát được: ' + str(ex))

    def stop_playback(self):
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
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
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
                rename_recording(path, name)
                self.refresh()
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
