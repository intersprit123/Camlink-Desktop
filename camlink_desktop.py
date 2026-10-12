import io
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import urlencode

try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("Pillow is required. Install it with: python -m pip install -r requirements.txt")


class CamLinkDesktop:
    def __init__(self, root):
        self.root = root
        self.root.title("CamLink Desktop")
        self.root.geometry("960x680")
        self.root.minsize(640, 480)
        self.root.configure(bg="#101525")
        self.running = False
        self.worker = None
        self.frame_photo = None
        self.control_status = tk.StringVar(value="Controls require a connected CamLink camera phone.")
        self.zoom_value = tk.DoubleVar(value=1.0)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101525")
        style.configure("TLabel", background="#101525", foreground="#f4f6ff", font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)

        top = ttk.Frame(root, padding=16)
        top.pack(fill="x")
        ttk.Label(top, text="CamLink Desktop", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="View a CamLink camera phone on the same trusted Wi-Fi network.").pack(anchor="w", pady=(4, 12))

        controls = ttk.Frame(root, padding=(16, 0, 16, 12))
        controls.pack(fill="x")
        ttk.Label(controls, text="Camera phone IP:").pack(side="left")
        self.ip = tk.StringVar(value="192.168.1.10")
        self.ip_entry = ttk.Entry(controls, textvariable=self.ip, width=22)
        self.ip_entry.pack(side="left", padx=(8, 12))
        self.connect_button = ttk.Button(controls, text="Connect", command=self.connect)
        self.connect_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="Disconnect", command=self.disconnect, state="disabled")
        self.stop_button.pack(side="left", padx=8)

        remote = ttk.LabelFrame(root, text="Remote camera controls", padding=12)
        remote.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Button(remote, text="Switch front / rear", command=lambda: self.send_control("switch")).pack(side="left", padx=(0, 8))
        ttk.Button(remote, text="Flashlight on / off", command=lambda: self.send_control("torch")).pack(side="left", padx=(0, 8))
        ttk.Label(remote, text="Zoom").pack(side="left", padx=(8, 4))
        self.zoom_scale = ttk.Scale(remote, from_=1.0, to=4.0, variable=self.zoom_value, command=self.on_zoom_change)
        self.zoom_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.zoom_label = ttk.Label(remote, text="1.0×")
        self.zoom_label.pack(side="left", padx=4)
        ttk.Button(remote, text="Apply zoom", command=lambda: self.send_control("zoom", self.zoom_value.get())).pack(side="left", padx=(8, 0))
        ttk.Label(root, textvariable=self.control_status).pack(anchor="w", padx=18, pady=(0, 8))

        self.status = tk.StringVar(value="Not connected")
        ttk.Label(root, textvariable=self.status).pack(anchor="w", padx=18, pady=(0, 8))

        self.screen = tk.Label(root, bg="#05070d", fg="#c4cbe0", text="Camera preview will appear here", font=("Segoe UI", 14))
        self.screen.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        root.protocol("WM_DELETE_WINDOW", self.close)

    def connect(self):
        host = self.ip.get().strip()
        if not host or any(c in host for c in "/ :"):
            messagebox.showerror("CamLink", "Enter only the camera phone's IP address, such as 192.168.1.12.")
            return
        self.host = host
        self.running = True
        self.connect_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Connecting to {host}:8080…")
        self.worker = threading.Thread(target=self.fetch_loop, daemon=True)
        self.worker.start()

    def on_zoom_change(self, value):
        self.zoom_label.configure(text=f"{float(value):.1f}×")

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

    def fetch_loop(self):
        while self.running:
            try:
                url = f"http://{self.host}:8080/frame?t={time.time_ns()}"
                req = Request(url, headers={"Cache-Control": "no-cache"})
                with urlopen(req, timeout=3) as response:
                    data = response.read()
                image = Image.open(io.BytesIO(data)).convert("RGB")
                self.root.after(0, self.show_frame, image)
                time.sleep(0.12)
            except Exception as exc:
                self.root.after(0, self.set_status, f"Waiting for camera… ({exc})")
                time.sleep(1)

    def show_frame(self, image):
        if not self.running:
            return
        width = max(self.screen.winfo_width(), 320)
        height = max(self.screen.winfo_height(), 240)
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.frame_photo = ImageTk.PhotoImage(image)
        self.screen.configure(image=self.frame_photo, text="")
        self.status.set(f"Connected to {self.host}:8080")

    def set_status(self, text):
        if self.running:
            self.status.set(text)

    def disconnect(self):
        self.running = False
        self.connect_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.set("Disconnected")
        self.screen.configure(image="", text="Camera preview will appear here")
        self.frame_photo = None

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    app = CamLinkDesktop(window)
    window.mainloop()
