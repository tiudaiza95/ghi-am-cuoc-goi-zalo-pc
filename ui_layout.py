"""Compact light interface inspired by iOS grouped settings."""
import customtkinter as ctk
from desktop_support import autostart_enabled

BG = ('#F2F2F7', '#111114')
WHITE = ('#FFFFFF', '#1C1C1E')
TEXT = ('#1C1C1E', '#F5F5F7')
MUTED = ('#636366', '#AEAEB2')
BLUE = ('#007AFF', '#0A84FF')
SOFT = ('#E8F2FF', '#172C46')
LINE = ('#E5E5EA', '#38383A')


def build_ui(app):
    def label(parent, text, size=13, color=TEXT, bold=False, **kw):
        return ctk.CTkLabel(parent, text=text, text_color=color,
                           font=('Segoe UI', size, 'bold' if bold else 'normal'), **kw)

    def button(parent, text, command, primary=False, **kw):
        return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=12,
            fg_color=BLUE if primary else SOFT, hover_color='#0064D4' if primary else ('#D7E8FC', '#203C5C'),
            text_color='#FFFFFF' if primary else BLUE, font=('Segoe UI', 12, 'bold'), **kw)

    def card(parent):
        frame = ctk.CTkFrame(parent, fg_color=WHITE, corner_radius=20, border_width=1, border_color=LINE)
        frame.pack(fill='x', pady=(0, 14))
        return frame

    header = ctk.CTkFrame(app, fg_color='transparent')
    header.pack(fill='x', padx=28, pady=(24, 10))
    branding = ctk.CTkFrame(header, fg_color='transparent')
    branding.pack(side='left')
    label(branding, 'Ghi Âm Zalo PC', 27, bold=True).pack(anchor='w')
    label(branding, 'Cuộc gọi được lưu. Mọi thứ ở ngay trên máy bạn.', 12, MUTED).pack(anchor='w')
    button(header, 'Chạy nền ↗', app.hide_to_tray, width=108).pack(side='right', padx=(8, 0))
    button(header, 'Bản ghi', app.open_library, primary=True, width=100).pack(side='right')

    tabs = ctk.CTkTabview(app, fg_color=BG, corner_radius=18, text_color=TEXT,
        segmented_button_fg_color=LINE, segmented_button_unselected_color=LINE,
        segmented_button_unselected_hover_color=('#DADAE0', '#48484A'), segmented_button_selected_color=WHITE,
        segmented_button_selected_hover_color=WHITE)
    tabs.pack(fill='both', expand=True, padx=18, pady=(0, 12))
    record = ctk.CTkScrollableFrame(tabs.add('Ghi âm'), fg_color=BG)
    settings = ctk.CTkScrollableFrame(tabs.add('Cài đặt'), fg_color=BG)
    activity = ctk.CTkFrame(tabs.add('Nhật ký'), fg_color=BG)
    for frame in (record, settings, activity):
        frame.pack(fill='both', expand=True)

    connection = card(record)
    status = ctk.CTkFrame(connection, fg_color='transparent')
    status.pack(side='left', padx=20, pady=14)
    app.connection_text = label(status, 'Đang kiểm tra Zalo…', 15, bold=True)
    app.connection_text.pack(anchor='w')
    app.connection_hint = label(status, 'Theo dõi cuộc gọi kể cả khi chạy nền.', 11, MUTED)
    app.connection_hint.pack(anchor='w')
    app.connection_chip = label(connection, 'ĐANG CHỜ', 11, BLUE, bold=True)
    app.connection_chip.pack(side='right', padx=20)
    # Existing connection updates also address this compact label.
    app.zalo_sidebar_state = label(status, '', 10, MUTED)
    app.zalo_sidebar_state.pack(anchor='w')

    capture = card(record)
    app.recording_state = label(capture, '● SẴN SÀNG', 12, MUTED, bold=True)
    app.recording_state.pack(pady=(20, 2))
    app.timer_label = label(capture, '00:00:00', 48, bold=True)
    app.timer_label.pack()
    app.current_file_label = label(capture, 'Chưa có phiên ghi âm', 12, MUTED, wraplength=650)
    app.current_file_label.pack(padx=18, pady=(0, 16))
    meters = ctk.CTkFrame(capture, fg_color='transparent')
    meters.pack(fill='x', padx=22)
    meters.grid_columnconfigure((0, 1), weight=1)
    app.audio_meters = {}
    for column, (role, title) in enumerate((('microphone', 'MICRO CỦA BẠN'), ('speaker', 'LOA / TAI NGHE'))):
        group = ctk.CTkFrame(meters, fg_color=BG, corner_radius=12)
        group.grid(row=0, column=column, sticky='ew', padx=5)
        label(group, title, 10, MUTED, bold=True).pack(anchor='w', padx=14, pady=(10, 4))
        meter = ctk.CTkProgressBar(group, height=7, fg_color=LINE, progress_color='#34C759')
        meter.pack(fill='x', padx=14, pady=(0, 12))
        meter.set(0)
        app.audio_meters[role] = meter
    app.audio_hint = label(capture, 'Im lặng không tự dừng bản ghi.', 11, MUTED, wraplength=650)
    app.audio_hint.pack(padx=14, pady=(8, 12))
    controls = ctk.CTkFrame(capture, fg_color='transparent')
    controls.pack(pady=(0, 20))
    app.record_btn = button(controls, '●  Ghi thủ công', app.manual_confirm, primary=True, width=178)
    app.record_btn.pack(side='left', padx=5)
    app.stop_btn = ctk.CTkButton(controls, text='■  Dừng & lưu', command=app.stop_recording,
        width=178, height=36, corner_radius=12, fg_color=('#FFF0EF', '#3A2023'), hover_color=('#FFE1DE', '#542A30'),
        text_color=('#D93025', '#FF6961'), text_color_disabled='#AEAEB2', state='disabled')
    app.stop_btn.pack(side='left', padx=5)

    automation = card(record)
    app.auto_switch = ctk.CTkSwitch(automation, text='Tự ghi khi có cuộc gọi', command=app.toggle_auto_record,
        progress_color=BLUE, text_color=TEXT, font=('Segoe UI', 14, 'bold'))
    app.auto_switch.pack(anchor='w', padx=20, pady=(16, 5))
    if app.auto_record:
        app.auto_switch.select()
    app.auto_hint = label(automation, '', 11, MUTED, wraplength=650, justify='left')
    app.auto_hint.pack(anchor='w', padx=20, pady=(0, 14))
    app.update_auto_hint()

    appearance = card(settings)
    label(appearance, 'Giao diện', 18, bold=True).pack(anchor='w', padx=20, pady=(16, 8))
    app.theme_switch = ctk.CTkSegmentedButton(appearance, values=['Sáng', 'Tối'],
        command=app.change_theme, height=36)
    app.theme_switch.pack(fill='x', padx=20, pady=(0, 16))
    app.theme_switch.set('Tối' if app.appearance == 'Dark' else 'Sáng')

    devices = card(settings)
    label(devices, 'Âm thanh', 18, bold=True).pack(anchor='w', padx=20, pady=(16, 4))
    label(devices, 'Chọn đúng thiết bị đang dùng trong Zalo.', 12, MUTED).pack(anchor='w', padx=20, pady=(0, 8))
    for key, title in (('mic_combo', 'Micro'), ('out_combo', 'Loa / tai nghe')):
        label(devices, title, 12, MUTED).pack(anchor='w', padx=20, pady=(6, 4))
        combo = ctk.CTkOptionMenu(devices, values=['Đang dò thiết bị…'], height=38,
            fg_color=BG, button_color=LINE, button_hover_color=('#D1D1D6', '#48484A'), text_color=TEXT,
            dropdown_fg_color=WHITE, dropdown_text_color=TEXT, dropdown_hover_color=SOFT,
            command=lambda _: app.persist())
        combo.pack(fill='x', padx=20, pady=(0, 8))
        setattr(app, key, combo)
    button(devices, 'Làm mới thiết bị', app.reload_devices).pack(anchor='e', padx=20, pady=(4, 16))

    files = card(settings)
    label(files, 'Lưu trữ', 18, bold=True).pack(anchor='w', padx=20, pady=(16, 8))
    app.format_menu = ctk.CTkSegmentedButton(files, values=['MP3', 'WAV'], command=app.change_format,
        selected_color=BLUE, selected_hover_color='#0064D4', unselected_color=LINE,
        unselected_hover_color=('#D1D1D6', '#48484A'), text_color=TEXT, height=34)
    app.format_menu.pack(fill='x', padx=20, pady=(0, 10))
    app.format_menu.set(app.chosen_format if app.chosen_format in ('MP3', 'WAV') else 'MP3')
    app.folder_label = label(files, 'Lưu tại: ' + app.folder, 11, MUTED, wraplength=640, justify='left')
    app.folder_label.pack(anchor='w', padx=20, pady=4)
    row = ctk.CTkFrame(files, fg_color='transparent')
    row.pack(fill='x', padx=16, pady=(8, 16))
    button(row, 'Chọn thư mục', app.choose_folder).pack(side='left', padx=4)
    button(row, 'Mở thư mục', app.open_folder).pack(side='left', padx=4)

    background = card(settings)
    label(background, 'Theo dõi & chạy nền', 18, bold=True).pack(anchor='w', padx=20, pady=(16, 10))
    app.detector_switch = ctk.CTkSwitch(background, text='Nhận diện cửa sổ gọi chuyên biệt',
        command=app.toggle_new_windows, progress_color=BLUE, text_color=TEXT)
    app.detector_switch.pack(anchor='w', padx=20, pady=8)
    if app.detector.allow_new_windows:
        app.detector_switch.select()
    label(background, 'Không dùng cửa sổ hồ sơ, ảnh hoặc chat để suy đoán cuộc gọi.', 11, MUTED,
          wraplength=650).pack(anchor='w', padx=20)
    app.autostart_switch = ctk.CTkSwitch(background, text='Mở cùng Windows', command=app.toggle_autostart,
        progress_color=BLUE, text_color=TEXT)
    app.autostart_switch.pack(anchor='w', padx=20, pady=12)
    if autostart_enabled():
        app.autostart_switch.select()
    label(background, 'Nút X thu xuống khay. Chọn Thoát ứng dụng để dừng chạy nền.', 11, MUTED,
          wraplength=650).pack(anchor='w', padx=20, pady=(0, 14))
    support = card(settings)
    row = ctk.CTkFrame(support, fg_color='transparent')
    row.pack(padx=16, pady=16, fill='x')
    button(row, 'Mở Zalo PC', app.open_zalo, width=120).pack(side='left', padx=4)
    button(row, 'Chẩn đoán', app.diagnostics, width=120).pack(side='left', padx=4)
    button(row, 'Thoát ứng dụng', app.on_close, width=140).pack(side='right', padx=4)

    label(activity, 'Hoạt động gần đây', 20, bold=True).pack(anchor='w', padx=16, pady=12)
    app.log_view = ctk.CTkTextbox(activity, fg_color=WHITE, text_color=TEXT, corner_radius=16,
                                 font=('Segoe UI', 12), state='disabled', wrap='word')
    app.log_view.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    button(activity, 'Xuất nhật ký hỗ trợ', app.export_logs).pack(anchor='e', padx=12, pady=(0, 12))
    label(app, 'Ghi Âm Zalo PC  •  2.4.0  •  Lưu trên máy của bạn', 10, MUTED).pack(pady=(0, 10))
    app.log('Đã mở Ghi Âm Zalo PC. Chế độ: ' + ('TỰ GHI' if app.auto_record else 'HỎI TRƯỚC KHI GHI'))
