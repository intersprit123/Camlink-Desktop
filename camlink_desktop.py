import io
import json
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
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
        self.settings_path = Path.home() / ".camlink_desktop.json"
        self.settings = self.load_settings()
        self.windowed_geometry = self.settings.get("geometry", "1360x860")
        self.root.geometry(self.windowed_geometry)
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)
        self.running = False
        self.connection_generation = 0  # Invalidates older pollers after a rapid Stop/Connect.
        self.host = ""
        self.worker = None
        self.frame_photo = None
        self.last_image = None
        self.preview_mode = self.settings.get("preview_mode", "fit")
        if self.preview_mode not in ("fit", "original"):
            self.preview_mode = "fit"
        self.fullscreen = False
        self.sidebar_visible = bool(self.settings.get("sidebar_visible", True))
        self.pending_jpeg_lock = threading.Lock()
        self.pending_jpeg = None
        self.pending_sequence = 0
        self.displayed_sequence = 0
        self.received_frames = 0
        self.received_bytes = 0
        self.received_fps = 0.0
        self.received_mbps = 0.0
        self.decode_ms = 0.0
        self.last_stats_time = time.monotonic()
        self.retry_delay = 0.10
        self.preview_tick_id = None
        self.control_status = tk.StringVar(value="Connect to a camera to unlock controls.")
        self.status = tk.StringVar(value="Ready to connect")
        self.zoom_value = tk.DoubleVar(value=self.safe_number("zoom", 1.0, 1.0, 10.0))
        self.exposure_value = tk.DoubleVar(value=self.safe_number("exposure", 0.0, -3.0, 3.0))
        self.white_balance = tk.StringVar(value=self.settings.get("white_balance", "auto"))
        if self.white_balance.get() not in ("auto", "daylight", "cloudy", "incandescent", "fluorescent"):
            self.white_balance.set("auto")
        self.jpeg_value = tk.IntVar(value=int(self.safe_number("jpeg_quality", 75, 50, 95)))
        self.resolution = tk.StringVar(value=self.settings.get("resolution", "720p · HD"))
        if self.resolution.get() not in ("480p · Low", "720p · HD", "1080p · Full HD", "1440p · 2K", "2160p · 4K"):
            self.resolution.set("1080p · Full HD")

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
        studio_tools = tk.Frame(viewer, bg=BG)
        studio_tools.pack(fill="x", pady=(10, 0))
        ttk.Button(studio_tools, text="Save snapshot", command=self.save_snapshot).pack(side="left")
        ttk.Button(studio_tools, text="Fit to window", command=lambda: self.set_preview_mode("fit")).pack(side="left", padx=(7, 0))
        ttk.Button(studio_tools, text="Original size", command=lambda: self.set_preview_mode("original")).pack(side="left", padx=(7, 0))
        ttk.Button(studio_tools, text="⚡ Max FPS preset", command=self.apply_performance_profile).pack(side="left", padx=(7, 0))
        self.fullscreen_button = ttk.Button(studio_tools, text="Fullscreen  (F11)", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side="right")

        info = tk.Frame(viewer, bg=BG)
        info.pack(fill="x", pady=(10, 0))
        self.status_label = tk.Label(info, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.status_label.pack(side="left")
        self.fps_label = tk.Label(info, text="— FPS", bg=BG, fg=GREEN, font=("Segoe UI", 10, "bold"))
        self.fps_label.pack(side="right")

        tk.Label(root, text="CAMLINK  •  PRIVATE LOCAL NETWORK  •  USE ON A TRUSTED WI-FI NETWORK",
                 bg=BG, fg="#71819b", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=24, pady=(0, 12))
        if not self.sidebar_visible:
            self.sidebar.pack_forget()
            self.toggle_button.configure(text="›")
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.preview.bind("<Configure>", self.redraw_last_image)
        self.ip.set(str(self.settings.get("host", "")))
        self.save_settings()
        self.preview_tick_id = self.root.after(16, self.consume_latest_frame)

    def section(self, parent, title):
        tk.Label(parent, text=title.upper(), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(17, 8))

    def build_sidebar(self):
        self.section(self.sidebar, "Connection")
        tk.Label(self.sidebar, text="CAMERA PHONE ADDRESS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16)
        self.ip = tk.StringVar(value=str(self.settings.get("host", "")))
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
        ttk.Button(row, text="↻  Flip", command=lambda: self.send_control("switch")).pack(fill="x", expand=True, side="left")
        ttk.Button(row, text="☼  Flash", command=lambda: self.send_control("torch")).pack(fill="x", expand=True, side="left", padx=(6, 0))
        ttk.Button(row, text="◎  Focus", command=lambda: self.send_control("focus")).pack(fill="x", expand=True, side="left", padx=(6, 0))

        self.make_slider("Zoom", self.zoom_value, 1, 10, lambda v: f"{float(v):.1f}×", self.apply_zoom)
        self.make_slider("Exposure compensation", self.exposure_value, -3, 3,
                         lambda v: f"{int(round(float(v))):+d} steps", self.apply_exposure, integer=True)
        tk.Label(self.sidebar, text="White balance", bg=PANEL, fg=TEXT, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(10, 4))
        wb_row = tk.Frame(self.sidebar, bg=PANEL)
        wb_row.pack(fill="x", padx=16, pady=(0, 8))
        self.white_balance_box = ttk.Combobox(wb_row, textvariable=self.white_balance, state="readonly",
                                               values=("auto", "daylight", "cloudy", "incandescent", "fluorescent"))
        self.white_balance_box.pack(side="left", fill="x", expand=True)
        ttk.Button(wb_row, text="Apply", command=self.apply_white_balance).pack(side="left", padx=(6, 0))
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
        self.save_settings()

    def connect(self):
        host = self.ip.get().strip()
        if not host or any(c in host for c in "/ :"):
            messagebox.showerror("CamLink", "Enter the camera phone's IP address, for example 192.168.1.12.")
            return
        self.disconnect(clear_status=False)
        self.connection_generation += 1
        generation = self.connection_generation
        self.host = host
        self.save_settings()
        self.running = True
        self.connect_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Connecting to {host}:8080…")
        self.live_badge.configure(text="●  CONNECTING", fg="#ffd479")
        self.worker = threading.Thread(target=self.fetch_loop, args=(generation,), daemon=True)
        self.worker.start()

    def fetch_loop(self, generation):
        # Each connection gets a generation token so an older worker cannot resume
        # polling if the user quickly presses Stop and then Connect again.
        retry_delay = 0.10
        while self.running and generation == self.connection_generation:
            try:
                url = f"http://{self.host}:8080/frame?t={time.time_ns()}"
                req = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
                with urlopen(req, timeout=3) as response:
                    jpeg = response.read()
                if not self.running or generation != self.connection_generation:
                    return
                if not jpeg:
                    raise ConnectionError("The phone returned an empty frame")

                # Keep only the newest compressed frame, using the existing low-latency
                # UI consumer so queued frames cannot build up.
                with self.pending_jpeg_lock:
                    self.pending_jpeg = jpeg
                    self.pending_sequence += 1
                    self.received_frames += 1
                    self.received_bytes += len(jpeg)
                retry_delay = 0.10
            except Exception as exc:
                if self.running and generation == self.connection_generation:
                    try:
                        self.root.after(0, self.set_error, str(exc))
                    except tk.TclError:
                        return
                    time.sleep(retry_delay)
                    retry_delay = min(0.75, retry_delay * 1.7)

            # Avoid hammering the phone's HTTP server while polling individual frames.
            if self.running and generation == self.connection_generation:
                time.sleep(0.01)

    def consume_latest_frame(self):
        if not self.root.winfo_exists():
            return

        jpeg = None
        sequence = 0
        stats_updated = False
        with self.pending_jpeg_lock:
            if self.pending_sequence != self.displayed_sequence and self.pending_jpeg is not None:
                jpeg = self.pending_jpeg
                sequence = self.pending_sequence
            now = time.monotonic()
            elapsed = now - self.last_stats_time
            if elapsed >= 1.0:
                frames = self.received_frames
                byte_count = self.received_bytes
                self.received_frames = 0
                self.received_bytes = 0
                self.last_stats_time = now
                self.received_fps = frames / elapsed
                self.received_mbps = (byte_count * 8 / elapsed) / 1_000_000
                stats_updated = True

        if jpeg is not None:
            self.displayed_sequence = sequence
            started = time.perf_counter()
            try:
                with Image.open(io.BytesIO(jpeg)) as source:
                    image = source.convert("RGB")
                self.decode_ms = (time.perf_counter() - started) * 1000.0
                self.show_frame(image)
            except Exception as exc:
                self.status.set(f"Received an invalid frame: {exc}")

        if self.running:
            # Update text widgets once per second, not once per preview tick.
            if stats_updated:
                self.fps_label.configure(
                    text=f"{self.received_fps:.0f} RX FPS · {self.decode_ms:.1f} ms decode"
                )
                if self.received_fps > 0:
                    self.status.set(
                        f"Connected to {self.host}:8080  ·  {self.received_mbps:.1f} Mbps"
                    )

        # Keep the consumer alive while disconnected; Connect may be pressed long
        # after startup, and the frame renderer must still be waiting for new frames.
        try:
            self.preview_tick_id = self.root.after(16, self.consume_latest_frame)
        except tk.TclError:
            self.preview_tick_id = None


    def show_frame(self, image):
        if not self.running:
            return
        self.last_image = image
        self.redraw_last_image()
        self.live_badge.configure(text="●  LIVE", fg=GREEN)

    def redraw_last_image(self, _event=None):
        if self.last_image is None or not self.running:
            return
        width = max(self.preview.winfo_width(), 80)
        height = max(self.preview.winfo_height(), 80)
        image = self.last_image.copy()
        if self.preview_mode == "fit":
            # Bilinear resampling is much cheaper than Lanczos for a continuously updating preview.
            image.thumbnail((width, height), Image.Resampling.BILINEAR)
        self.frame_photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.frame_photo, text="")

    def set_error(self, error):
        if self.running:
            self.status.set(f"Waiting for phone… {error}")
            self.live_badge.configure(text="●  RETRYING", fg="#ffd479")

    def send_control(self, command, value=None):
        self.save_settings()
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

    def apply_exposure(self):
        self.send_control("exposure", int(round(self.exposure_value.get())))

    def apply_white_balance(self):
        self.send_control("whitebalance", self.white_balance.get())

    def apply_resolution(self):
        choices = ("480p · Low", "720p · HD", "1080p · Full HD", "1440p · 2K", "2160p · 4K")
        try:
            self.send_control("quality", choices.index(self.resolution.get()))
        except ValueError:
            self.send_control("quality", 2)

    def apply_jpeg(self):
        self.send_control("jpeg", int(self.jpeg_value.get()))

    def apply_performance_profile(self):
        # Favor the camera/network/preview pipeline over maximum image detail.
        self.resolution.set("720p · HD")
        self.jpeg_value.set(75)
        self.save_settings()
        if not self.running:
            self.control_status.set("Performance preset saved. Connect to the camera to apply 720p / JPEG 75%.")
            return

        self.control_status.set("Applying performance preset: 720p · JPEG 75%…")

        def worker():
            results = []
            try:
                for command, value in (("quality", "1"), ("jpeg", "75")):
                    params = urlencode({"cmd": command, "value": value})
                    req = Request(
                        f"http://{self.host}:8080/control?{params}",
                        headers={"Cache-Control": "no-cache"}
                    )
                    with urlopen(req, timeout=4) as response:
                        results.append(response.read().decode("utf-8", errors="replace"))
                message = "Performance preset applied · 720p / JPEG 75%"
            except Exception as exc:
                message = f"Could not apply full performance preset: {exc}"
            try:
                self.root.after(0, self.control_status.set, message)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def disconnect(self, clear_status=True):
        self.running = False
        self.connection_generation += 1
        with self.pending_jpeg_lock:
            self.pending_jpeg = None
            self.pending_sequence += 1
            self.displayed_sequence = self.pending_sequence
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

    def safe_number(self, key, default, minimum, maximum):
        try:
            value = float(self.settings.get(key, default))
        except (TypeError, ValueError):
            value = float(default)
        return max(minimum, min(maximum, value))

    def load_settings(self):
        try:
            with self.settings_path.open("r", encoding="utf-8") as source:
                data = json.load(source)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_settings(self):
        if not hasattr(self, "settings_path"):
            return
        try:
            geometry = getattr(self, "windowed_geometry", "1360x860")
            if hasattr(self, "root") and not getattr(self, "fullscreen", False):
                geometry = self.root.geometry()
            settings = {
                "host": self.ip.get().strip() if hasattr(self, "ip") else self.settings.get("host", ""),
                "zoom": float(self.zoom_value.get()) if hasattr(self, "zoom_value") else 1.0,
                "exposure": float(self.exposure_value.get()) if hasattr(self, "exposure_value") else 0.0,
                "white_balance": self.white_balance.get() if hasattr(self, "white_balance") else "auto",
                "jpeg_quality": int(self.jpeg_value.get()) if hasattr(self, "jpeg_value") else 85,
                "resolution": self.resolution.get() if hasattr(self, "resolution") else "720p · HD",
                "preview_mode": getattr(self, "preview_mode", "fit"),
                "sidebar_visible": getattr(self, "sidebar_visible", True),
                "geometry": geometry
            }
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            self.settings = settings
        except (OSError, tk.TclError, ValueError):
            # Settings persistence is best-effort; it must never interrupt the live preview.
            pass

    def set_preview_mode(self, mode):
        if mode not in ("fit", "original"):
            return
        self.preview_mode = mode
        self.redraw_last_image()
        self.save_settings()
        if mode == "fit":
            self.status.set("Preview scaled to fit the window")
        else:
            self.status.set("Original pixel size · scroll/resize window to inspect")

    def toggle_fullscreen(self, _event=None):
        if not self.fullscreen:
            try:
                self.windowed_geometry = self.root.geometry()
            except tk.TclError:
                pass
            self.fullscreen = True
            self.root.attributes("-fullscreen", True)
            self.fullscreen_button.configure(text="Exit fullscreen  (Esc)")
        else:
            self.exit_fullscreen()

    def exit_fullscreen(self, _event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)
            self.root.geometry(self.windowed_geometry)
            self.fullscreen_button.configure(text="Fullscreen  (F11)")
            self.save_settings()

    def save_snapshot(self):
        if self.last_image is None:
            messagebox.showinfo("CamLink", "Connect to the camera and wait for a frame before saving a snapshot.")
            return
        pictures = Path.home() / "Pictures"
        initial_dir = pictures if pictures.is_dir() else Path.home()
        filename = f"CamLink_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save CamLink snapshot",
            initialdir=str(initial_dir),
            initialfile=filename,
            defaultextension=".jpg",
            filetypes=(("JPEG image", "*.jpg *.jpeg"), ("PNG image", "*.png"), ("All files", "*.*"))
        )
        if not path:
            return
        try:
            self.last_image.save(path)
            self.status.set(f"Snapshot saved: {path}")
        except (OSError, ValueError) as exc:
            messagebox.showerror("CamLink", f"Could not save snapshot:\\n{exc}")

    def close(self):
        self.save_settings()
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    app = CamLinkDesktop(window)
    window.mainloop()
