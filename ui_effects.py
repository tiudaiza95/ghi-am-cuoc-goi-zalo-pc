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


def cancel_root_callbacks(root):
    for job in root.tk.call('after', 'info'):
        root.tk.call('after', 'cancel', job)
