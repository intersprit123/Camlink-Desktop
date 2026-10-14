#!/usr/bin/env python3
"""Static integration-contract checks for CamLink Desktop Build #10.

The source and expected controls are intentionally pinned to the Build #10
contract. This is a static source test, not a live phone/PC connection test.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "camlink_desktop.py"
SOURCE = APP_PATH.read_text(encoding="utf-8")
ast.parse(SOURCE, filename=str(APP_PATH))
compile(SOURCE, str(APP_PATH), "exec")

checks = []


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAIL: {label}")
    checks.append(label)


# Build #10 source identity: verify the original feature set and architecture,
# rather than silently validating a different/remade desktop application.
check("Build #10 uses urllib Request/urlopen",
      "from urllib.request import urlopen, Request" in SOURCE and "urlopen(req, timeout=3)" in SOURCE)
check("Build #10 preserves /frame polling",
      'f"http://{self.host}:8080/frame?t={time.time_ns()}"' in SOURCE)
check("Build #10 does not use /stream", '"/stream' not in SOURCE and "'/stream" not in SOURCE)

# UI button -> callback. Do not assert controls that Build #10 does not have.
check("Connect button is wired to connect()",
      'text="Connect"' in SOURCE and "command=self.connect" in SOURCE)
check("Stop button is wired to disconnect()",
      'text="Stop"' in SOURCE and "command=self.disconnect" in SOURCE)
for label, callback in (
    ("Flip camera", 'self.send_control("switch")'),
    ("Flash", 'self.send_control("torch")'),
    ("Zoom", "self.apply_zoom"),
    ("Apply resolution", "self.apply_resolution"),
    ("JPEG quality", "self.apply_jpeg"),
):
    check(f"{label} action is wired", callback in SOURCE)

# Connect -> frame worker -> decode -> preview.
check("Connect starts the frame worker",
      "threading.Thread(target=self.fetch_loop" in SOURCE and "self.worker.start()" in SOURCE)
check("frame fetch uses a finite timeout", "urlopen(req, timeout=3)" in SOURCE)
check("frame bytes are decoded as an image", "Image.open(io.BytesIO(data))" in SOURCE)
check("decoded frame is handed to the Tk UI",
      "self.root.after(0, self.show_frame, image)" in SOURCE)
check("preview renders the decoded image",
      "ImageTk.PhotoImage(image)" in SOURCE and
      'self.preview.configure(image=self.frame_photo, text="")' in SOURCE)

# Control URL contract shared with Android.
check("control URL carries cmd/value to port 8080 /control",
      'params = {"cmd": command}' in SOURCE and
      'params["value"] = str(value)' in SOURCE and
      'f"http://{self.host}:8080/control?{urlencode(params)}"' in SOURCE and
      "urlopen(req, timeout=4)" in SOURCE)
for command in ("switch", "torch", "zoom", "quality", "jpeg"):
    check(f"Build #10 emits {command} control command", f'"{command}"' in SOURCE)

check("resolution maps to the quality command",
      'self.send_control("quality", choices.index(self.resolution.get()))' in SOURCE)
check("JPEG slider maps to the jpeg command",
      'self.send_control("jpeg", int(self.jpeg_value.get()))' in SOURCE)
check("zoom slider maps to the zoom command",
      'self.send_control("zoom", round(self.zoom_value.get(), 1))' in SOURCE)

check("Stop restores connection controls",
      "self.running = False" in SOURCE and
      'self.connect_button.configure(state="normal")' in SOURCE and
      'self.stop_button.configure(state="disabled")' in SOURCE)
check("close stops the worker and closes the window",
      "self.disconnect()" in SOURCE and "self.root.destroy()" in SOURCE)

print(f"Windows Build #10 connection contract: PASS ({len(checks)} checks)")
for item in checks:
    print(f"  PASS  {item}")
