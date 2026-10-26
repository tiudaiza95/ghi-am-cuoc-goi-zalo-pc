"""Small, bounded animations; capture work never runs on this UI timer."""
import customtkinter as ctk


class SmoothProgress(ctk.CTkProgressBar):
    def __init__(self, master, motion_enabled=lambda: True, **kwargs):
        self._motion_enabled = motion_enabled
        self._motion_job = None
        self._shown = 0.0
        super().__init__(master, **kwargs)

    def set(self, value, **kwargs):
        value = max(0.0, min(1.0, float(value)))
        if self._motion_job:
            self.after_cancel(self._motion_job)
            self._motion_job = None
        if not self._motion_enabled() or self.winfo_toplevel().state() == 'withdrawn':
            self._shown = value
            return super().set(value, **kwargs)
        start = self._shown
        def frame(step=1):
            self._motion_job = None
            t = step / 5
            self._shown = start + (value - start) * (1 - (1 - t) ** 3)
            super(SmoothProgress, self).set(self._shown)
            if step < 5:
                self._motion_job = self.after(35, lambda: frame(step + 1))
        frame()

    def destroy(self):
        if self._motion_job:
            self.after_cancel(self._motion_job)
            self._motion_job = None
        super().destroy()


def fade_in(window, enabled=True):
    """Short entrance fade, with no repeating background animation."""
    if not enabled:
        return
    try:
        window.attributes('-alpha', 0.0)
        def frame(step=1):
            window._fade_job = None
            if not window.winfo_exists():
                return
            window.attributes('-alpha', min(1, step / 6))
            if step < 6:
                window._fade_job = window.after(25, lambda: frame(step + 1))
        window._fade_job = window.after(0, frame)
    except Exception:
        window.attributes('-alpha', 1.0)


class ManagedToplevel(ctk.CTkToplevel):
    """Cancel callbacks owned by a window before Tk removes its commands."""
    def __init__(self, *args, **kwargs):
        self._owned_after = set()
        super().__init__(*args, **kwargs)

    def after(self, ms, func=None, *args):
        if func is None:
            return super().after(ms)
        token = []
        def invoke():
            if token:
                self._owned_after.discard(token[0])
            return func(*args)
        job = super().after(ms, invoke)
        token.append(job)
        self._owned_after.add(job)
        return job

    def after_cancel(self, job):
        self._owned_after.discard(job)
        return super().after_cancel(job)

    def destroy(self):
        for job in tuple(self._owned_after):
            self.after_cancel(job)
        super().destroy()


class MiniOverlay(ManagedToplevel):
    """Floating draggable mini pill with timer, stop button and expand button."""
    def __init__(self, parent, on_stop, on_expand):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(fg_color=('#1C1C1E', '#1C1C1E'))
        self.geometry('260x52+120+120')
        self._drag_data = {'x': 0, 'y': 0}

        container = ctk.CTkFrame(self, fg_color=('#2C2C2E', '#2C2C2E'), corner_radius=16, border_width=1, border_color=('#3A3A3C', '#3A3A3C'))
        container.pack(fill='both', expand=True, padx=2, pady=2)

        container.bind('<Button-1>', self._start_drag)
        container.bind('<B1-Motion>', self._on_drag)

        self.dot = ctk.CTkLabel(container, text='●', text_color='#FF453A', font=('Segoe UI', 16, 'bold'), width=24)
        self.dot.pack(side='left', padx=(10, 2))
        self.dot.bind('<Button-1>', self._start_drag)
        self.dot.bind('<B1-Motion>', self._on_drag)

        self.timer = ctk.CTkLabel(container, text='00:00:00', text_color='#FFFFFF', font=('Consolas', 15, 'bold'))
        self.timer.pack(side='left', padx=4)
        self.timer.bind('<Button-1>', self._start_drag)
        self.timer.bind('<B1-Motion>', self._on_drag)

        ctk.CTkButton(container, text='■', width=30, height=30, corner_radius=8,
                      fg_color='#FF3B30', hover_color='#D32F2F', text_color='#FFFFFF',
                      font=('Segoe UI', 12, 'bold'), command=on_stop).pack(side='right', padx=(4, 8))

        ctk.CTkButton(container, text='⤢', width=30, height=30, corner_radius=8,
                      fg_color=('#3A3A3C', '#3A3A3C'), hover_color=('#48484A', '#48484A'), text_color='#FFFFFF',
                      font=('Segoe UI', 13, 'bold'), command=on_expand).pack(side='right', padx=2)

    def _start_drag(self, event):
        self._drag_data['x'] = event.x_root - self.winfo_x()
        self._drag_data['y'] = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_data['x']
        y = event.y_root - self._drag_data['y']
        self.geometry(f"+{x}+{y}")

    def update_time(self, time_str):
        if self.winfo_exists():
            self.timer.configure(text=time_str)


def cancel_root_callbacks(root):
    for job in root.tk.call('after', 'info'):
        root.tk.call('after', 'cancel', job)
