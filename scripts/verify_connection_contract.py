#!/usr/bin/env python3
"""Static integration-contract checks for the Windows CamLink desktop client.

These checks verify the UI-to-network-to-frame-display chain and paired control names.
They complement (but do not replace) a real phone/PC connection test.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "camlink_desktop.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")
# Parse/compile without importing Tkinter or starting a GUI.
ast.parse(SOURCE, filename=str(APP_PATH))
compile(SOURCE, str(APP_PATH), "exec")

checks = []

def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAIL: {label}")
    checks.append(label)


# UI button -> callback.
check("Connect button is wired to connect()", 'text="Connect"' in SOURCE and "command=self.connect" in SOURCE)
check("Stop button is wired to disconnect()", 'text="Stop"' in SOURCE and "command=self.disconnect" in SOURCE)
for label, callback in (
    ("Flip", 'self.send_control("switch")'),
    ("Flash", 'self.send_control("torch")'),
    ("Focus", 'self.send_control("focus")'),
    ("Zoom", "self.apply_zoom"),
    ("Exposure", "self.apply_exposure"),
    ("White balance", "self.apply_white_balance"),
    ("Apply resolution", "self.apply_resolution"),
    ("JPEG quality", "self.apply_jpeg"),
    ("Max FPS preset", "self.apply_performance_profile"),
    ("Save snapshot", "self.save_snapshot"),
    ("Fit preview", 'self.set_preview_mode("fit")'),
    ("Original-size preview", 'self.set_preview_mode("original")'),
):
    check(f"{label} action is wired", callback in SOURCE)

# Connect -> single active /frame poller -> JPEG decode -> Tk display.
check("Connect starts a generation-scoped frame worker",
      "threading.Thread(target=self.fetch_loop, args=(generation,), daemon=True)" in SOURCE)
check("worker invalidates stale Stop/Connect pollers",
      "while self.running and generation == self.connection_generation" in SOURCE and
      "self.connection_generation += 1" in SOURCE)
check("desktop requests Android /frame with cache-busting and no-cache headers",
      'f"/frame?t={time.time_ns()}"' in SOURCE and
      '"Cache-Control": "no-cache"' in SOURCE and '"Pragma": "no-cache"' in SOURCE and
      "connection.request(" in SOURCE and "connection.getresponse()" in SOURCE)

check("camera address accepts a bare host or copied HTTP URL on port 8080",
      "def normalize_camera_address(value):" in SOURCE and
      "parsed = urlsplit(candidate)" in SOURCE and
      "port not in (None, 8080)" in SOURCE)
check("local LAN requests use direct HTTP without urllib or system proxies",
      "http.client.HTTPConnection(host, 8080, timeout=timeout)" in SOURCE and
      "self.http_opener" not in SOURCE and "urlopen(" not in SOURCE and
      "urllib.request" not in SOURCE)
check("frame poller rejects non-JPEG responses with a useful diagnostic",
      'if not jpeg.startswith(b"\\xff\\xd8"):' in SOURCE and
      "/frame did not return a JPEG image" in SOURCE)
check("received JPEG bytes enter the latest-frame buffer",
      "self.pending_jpeg = jpeg" in SOURCE and "self.pending_sequence += 1" in SOURCE)
check("UI consumer decodes JPEG then draws it in the preview",
      "Image.open(io.BytesIO(jpeg))" in SOURCE and "self.show_frame(image)" in SOURCE and
      "ImageTk.PhotoImage(image)" in SOURCE and "self.preview.configure(image=self.frame_photo" in SOURCE)
check("poller backs off on request errors and has a finite request timeout",
      'self.http_get(\n                    f"/frame?t={time.time_ns()}", timeout=3' in SOURCE and
      "retry_delay = min(0.75, retry_delay * 1.7)" in SOURCE)
consumer = SOURCE.split("    def consume_latest_frame(self):", 1)[1].split("    def show_frame(self, image):", 1)[0]
check("preview timer keeps rearming while disconnected, so Connect can display later frames",
      "\n        try:\n            self.preview_tick_id = self.root.after(16, self.consume_latest_frame)" in consumer)
check("desktop does not call the /stream endpoint", "/stream" not in SOURCE)

# Desktop control requests must match Android service command names.
check("control requests encode cmd/value and call port 8080 /control",
      'params = {"cmd": command}' in SOURCE and 'params["value"] = str(value)' in SOURCE and
      'path = f"/control?{urlencode(params)}"' in SOURCE and
      'self.http_get(path, timeout=4)' in SOURCE)
for command in ("switch", "torch", "focus", "zoom", "exposure", "whitebalance", "quality", "jpeg"):
    check(f"desktop emits Android-supported {command} command", f'"{command}"' in SOURCE)
check("performance preset sends both resolution and JPEG settings",
      '("quality", "1"), ("jpeg", "75")' in SOURCE)
check("Stop invalidates poller, clears pending frame and restores buttons",
      "self.connection_generation += 1" in SOURCE and "self.pending_jpeg = None" in SOURCE and
      'self.connect_button.configure(state="normal")' in SOURCE and
      'self.stop_button.configure(state="disabled")' in SOURCE)
check("close saves settings, stops polling and closes the window",
      "self.save_settings()" in SOURCE and "self.disconnect()" in SOURCE and "self.root.destroy()" in SOURCE)

print(f"Windows connection contract: PASS ({len(checks)} checks)")
for item in checks:
    print(f"  PASS  {item}")
