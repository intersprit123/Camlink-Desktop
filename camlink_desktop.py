import io
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import urlopen, Request
from urllib.parse import urlencode

try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("Pillow is required. Install it with: python -m pip install -r requirements.txt")


BG = "#0a0f1a"
PANEL = "#111927"
PANEL_ALT = "#192438"
BORDER = "#28364c"
TEXT = "#f4f7fb"
MUTED = "#9aa9bd"
ACCENT = "#4f7cff"
GREEN = "#42d6ad"


class CamLinkDesktop:
    def __init__(self, root):
        self.root = root
        self.root.title("CamLink | Desktop Camera")
        self.root.geometry("1360x860")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)
        self.running = False
        self.host = ""
        self.worker = None
        self.frame_photo = None
        self.last_image = None
        self.sidebar_visible = True
        self.frame_count = 0
        self.last_fps_time = time.monotonic()
        self.fps = 0
        self.control_status = tk.StringVar(value="Connect to a camera to unlock controls.")
        self.status = tk.StringVar(value="Ready to connect")
        self.zoom_value = tk.DoubleVar(value=1.0)
        self.jpeg_value = tk.IntVar(value=85)
        self.resolution = tk.StringVar(value="1080p · Full HD")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Heading.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 21, "bold"))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 8), background=PANEL_ALT, foreground=TEXT, borderwidth=0)
        style.map("TButton", background=[("active", "#263858"), ("disabled", "#182033")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#829cff")])
        style.configure("TEntry", fieldbackground=PANEL_ALT, foreground=TEXT, insertcolor=TEXT, padding=8)
        style.configure("TCombobox", fieldbackground=PANEL_ALT, background=PANEL_ALT, foreground=TEXT, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_ALT)], foreground=[("readonly", TEXT)])
        style.configure("Horizontal.TScale", background=PANEL)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 14))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", fill="x", expand=True)
        tk.Label(brand, text="CamLink", bg=BG, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(brand, text="LIVE CAMERA  /  DESKTOP STUDIO", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(1, 0))
        self.live_badge = tk.Label(header, text="●  DISCONNECTED", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 9, "bold"), padx=14, pady=9)
        self.live_badge.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        self.body = body
        self.sidebar = tk.Frame(body, bg=PANEL, width=320, highlightbackground=BORDER, highlightthickness=1)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)
        self.build_sidebar()

        self.divider = tk.Frame(body, bg=BG, width=34)
        self.divider.pack(side="right", fill="y")
        self.toggle_button = tk.Button(self.divider, text="‹", command=self.toggle_sidebar, bg=PANEL_ALT, fg=TEXT,
                                       activebackground=ACCENT, activeforeground="#ffffff", relief="flat",
                                       bd=0, font=("Segoe UI", 17, "bold"), cursor="hand2", width=2)
        self.toggle_button.place(relx=0.5, rely=0.5, anchor="center")

        viewer = tk.Frame(body, bg=BG)
        viewer.pack(side="left", fill="both", expand=True)
        self.viewer = viewer
        self.preview_border = tk.Frame(viewer, bg=BORDER, padx=2, pady=2)
        self.preview_border.pack(fill="both", expand=True)
        self.preview = tk.Label(self.preview_border, bg="#050912", fg=MUTED,
                                text="Your camera feed will appear here\n\nConnect to your phone to start viewing",
                                font=("Segoe UI", 14), justify="center")
        self.preview.pack(fill="both", expand=True)
        info = tk.Frame(viewer, bg=BG)
        info.pack(fill="x", pady=(12, 0))
        self.status_label = tk.Label(info, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.status_label.pack(side="left")
        self.fps_label = tk.Label(info, text="— FPS", bg=BG, fg=GREEN, font=("Segoe UI", 10, "bold"))
        self.fps_label.pack(side="right")

        tk.Label(root, text="CAMLINK  •  PRIVATE LOCAL NETWORK  •  USE ON A TRUSTED WI-FI NETWORK",
                 bg=BG, fg="#71819b", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=24, pady=(0, 12))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.preview.bind("<Configure>", self.redraw_last_image)

    def section(self, parent, title):
        tk.Label(parent, text=title.upper(), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(17, 8))

    def build_sidebar(self):
        self.section(self.sidebar, "Connection")
        tk.Label(self.sidebar, text="CAMERA PHONE ADDRESS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16)
        self.ip = tk.StringVar(value="")
        self.ip_entry = ttk.Entry(self.sidebar, textvariable=self.ip)
        self.ip_entry.pack(fill="x", padx=16, pady=(6, 10))
        buttons = tk.Frame(self.sidebar, bg=PANEL)
        buttons.pack(fill="x", padx=16)
        self.connect_button = ttk.Button(buttons, text="Connect", style="Accent.TButton", command=self.connect)
        self.connect_button.pack(side="left", fill="x", expand=True)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.disconnect, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))

        self.section(self.sidebar, "Camera")
        row = tk.Frame(self.sidebar, bg=PANEL)
        row.pack(fill="x", padx=16)
        ttk.Button(row, text="↻  Flip camera", command=lambda: self.send_control("switch")).pack(fill="x", expand=True, side="left")
        ttk.Button(row, text="☼  Flash", command=lambda: self.send_control("torch")).pack(fill="x", expand=True, side="left", padx=(7, 0))

        self.make_slider("Zoom", self.zoom_value, 1, 4, lambda v: f"{float(v):.1f}×", self.apply_zoom)
        self.section(self.sidebar, "Image quality")
        tk.Label(self.sidebar, text="Capture resolution", bg=PANEL, fg=TEXT, font=("Segoe UI", 10)).pack(anchor="w", padx=16)
        self.resolution_box = ttk.Combobox(self.sidebar, textvariable=self.resolution, state="readonly",
                                           values=("480p · Low", "720p · HD", "1080p · Full HD", "1440p · 2K", "2160p · 4K"))
        self.resolution_box.pack(fill="x", padx=16, pady=(6, 8))
        ttk.Button(self.sidebar, text="Apply resolution", command=self.apply_resolution).pack(fill="x", padx=16)

        self.make_slider("JPEG quality", self.jpeg_value, 50, 95, lambda v: f"{int(float(v))}%", self.apply_jpeg, integer=True)
        tk.Label(self.sidebar, text="Higher quality uses more Wi-Fi bandwidth.\n4K depends on phone support.",
                 bg=PANEL, fg=MUTED, justify="left", font=("Segoe UI", 9), wraplength=255).pack(anchor="w", padx=16, pady=(5, 12))
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(5, 10))
        tk.Label(self.sidebar, textvariable=self.control_status, bg=PANEL, fg=GREEN,
                 wraplength=255, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 14))

    def make_slider(self, title, variable, start, end, formatter, apply, integer=False):
        row = tk.Frame(self.sidebar, bg=PANEL)
        row.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(row, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 10)).pack(side="left")
        value_label = tk.Label(row, text=formatter(variable.get()), bg=PANEL, fg=GREEN,
                               font=("Segoe UI", 10, "bold"))
        value_label.pack(side="right")
        scale = ttk.Scale(self.sidebar, from_=start, to=end, variable=variable)
        scale.pack(fill="x", padx=16, pady=(0, 3))
        scale.configure(command=lambda value: value_label.configure(text=formatter(value)))
        ttk.Button(self.sidebar, text=f"Apply {title.lower()}", command=apply).pack(fill="x", padx=16, pady=(3, 0))

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.pack_forget()
            self.toggle_button.configure(text="›")
            self.sidebar_visible = False
        else:
            self.sidebar.pack(side="right", fill="y", before=self.divider)
            self.toggle_button.configure(text="‹")
            self.sidebar_visible = True

    def connect(self):
        host = self.ip.get().strip()
        if not host or any(c in host for c in "/ :"):
            messagebox.showerror("CamLink", "Enter the camera phone's IP address, for example 192.168.1.12.")
            return
        self.disconnect(clear_status=False)
        self.host = host
        self.running = True
        self.connect_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Connecting to {host}:8080…")
        self.live_badge.configure(text="●  CONNECTING", fg="#ffd479")
        self.worker = threading.Thread(target=self.fetch_loop, daemon=True)
        self.worker.start()

    @staticmethod
    def read_exact(stream, size):
        data = bytearray()
        while len(data) < size:
            part = stream.read(size - len(data))
            if not part:
                raise ConnectionError('Stream ended')
            data.extend(part)
        return bytes(data)

    def fetch_loop(self):
        while self.running:
            try:
                req = Request(f'http://{self.host}:8080/stream', headers={'Accept': 'multipart/x-mixed-replace'})
                with urlopen(req, timeout=10) as response:
                    while self.running:
                        boundary = response.readline()
                        if not boundary:
                            raise ConnectionError('Stream ended')
                        if not boundary.startswith(b'--frame'):
                            continue
                        headers = {}
                        while True:
                            line = response.readline()
                            if not line:
                                raise ConnectionError('Stream ended')
                            if line in (b'\r\n', b'\n'):
                                break
                            if b':' in line:
                                key, value = line.decode('latin-1').split(':', 1)
                                headers[key.strip().lower()] = value.strip()
                        size = int(headers.get('content-length', '0'))
                        if size <= 0 or size > 50000000:
                            raise ConnectionError('Invalid JPEG size')
                        jpeg = self.read_exact(response, size)
                        response.read(2)
                        with Image.open(io.BytesIO(jpeg)) as source:
                            image = source.convert('RGB')
                        self.root.after(0, self.show_frame, image)
            except Exception as exc:
                if self.running:
                    self.root.after(0, self.set_error, str(exc))
                    time.sleep(0.01)

    def show_frame(self, image):
        if not self.running:
            return
        self.last_image = image
        self.frame_count += 1
        now = time.monotonic()
        elapsed = now - self.last_fps_time
        if elapsed >= 1:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_fps_time = now
            self.fps_label.configure(text=f"{self.fps:.0f} FPS")
        self.redraw_last_image()
        self.status.set(f"Connected to {self.host}:8080")
        self.live_badge.configure(text="●  LIVE", fg=GREEN)

    def redraw_last_image(self, _event=None):
        if self.last_image is None or not self.running:
            return
        width = max(self.preview.winfo_width(), 80)
        height = max(self.preview.winfo_height(), 80)
        image = self.last_image.copy()
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.frame_photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.frame_photo, text="")

    def set_error(self, error):
        if self.running:
            self.status.set(f"Waiting for phone… {error}")
            self.live_badge.configure(text="●  RETRYING", fg="#ffd479")

    def send_control(self, command, value=None):
        if not self.running:
            self.control_status.set("Connect to the camera phone first.")
            return
        params = {"cmd": command}
        if value is not None:
            params["value"] = str(value)
        url = f"http://{self.host}:8080/control?{urlencode(params)}"

        def worker():
            try:
                req = Request(url, headers={"Cache-Control": "no-cache"})
                with urlopen(req, timeout=4) as response:
                    result = response.read().decode("utf-8", errors="replace")
                self.root.after(0, self.control_status.set, result)
            except Exception as exc:
                self.root.after(0, self.control_status.set, f"Control failed: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def apply_zoom(self):
        self.send_control("zoom", round(self.zoom_value.get(), 1))

    def apply_resolution(self):
        choices = ("480p · Low", "720p · HD", "1080p · Full HD", "1440p · 2K", "2160p · 4K")
        try:
            self.send_control("quality", choices.index(self.resolution.get()))
        except ValueError:
            self.send_control("quality", 2)

    def apply_jpeg(self):
        self.send_control("jpeg", int(self.jpeg_value.get()))

    def disconnect(self, clear_status=True):
        self.running = False
        if hasattr(self, "connect_button"):
            self.connect_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
        if hasattr(self, "preview"):
            self.preview.configure(image="", text="Your camera feed will appear here\n\nConnect to your phone to start viewing")
            self.frame_photo = None
            self.last_image = None
        if clear_status and hasattr(self, "status"):
            self.status.set("Disconnected")
            self.live_badge.configure(text="●  DISCONNECTED", fg=MUTED)
            self.fps_label.configure(text="— FPS")

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    app = CamLinkDesktop(window)
    window.mainloop()
