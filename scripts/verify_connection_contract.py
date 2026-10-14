#!/usr/bin/env python3
"""Static integration-contract checks for the Windows CamLink desktop client.

These checks match the Build #10 /frame-polling baseline plus the Focus control.
They verify the UI-to-network control path without importing Tkinter or starting a GUI.
They complement (but do not replace) a real phone/PC connection test.
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


# UI actions available in the Build #10 baseline.
check("Connect button is wired to connect()", 'text="Connect"' in SOURCE and "command=self.connect" in SOURCE)
check("Stop button is wired to disconnect()", 'text="Stop"' in SOURCE and "command=self.disconnect" in SOURCE)
for label, callback in (
    ("Flip", 'self.send_control("switch")'),
    ("Flash", 'self.send_control("torch")'),
    ("Focus", 'self.send_control("focus")'),
    ("Zoom", "self.apply_zoom"),
    ("Apply resolution", "self.apply_resolution"),
    ("JPEG quality", "self.apply_jpeg"),
):
    check(f"{label} action is wired", callback in SOURCE)

# Connect -> /frame polling -> JPEG decode -> Tk display.
check("Connect starts the frame worker", "threading.Thread(target=self.fetch_loop" in SOURCE)
check("desktop requests Android /frame", '"/frame?t=' in SOURCE or 'f"http://{self.host}:8080/frame?t=' in SOURCE)
check("frame requests use a finite timeout", "urlopen(req, timeout=3)" in SOURCE)
check("frame responses are decoded as images", "Image.open(io.BytesIO(data))" in SOURCE)
check("decoded frames are displayed in the preview", "self.root.after(0, self.show_frame, image)" in SOURCE and
      "self.preview.configure(image=self.frame_photo, text=\"\")" in SOURCE)
check("desktop does not call the /stream endpoint", "/stream" not in SOURCE)

# Controls must use the Android /control contract.
check("control requests encode cmd/value and call port 8080 /control",
      'params = {"cmd": command}' in SOURCE and 'params["value"] = str(value)' in SOURCE and
      'f"http://{self.host}:8080/control?{urlencode(params)}"' in SOURCE and
      "urlopen(req, timeout=4)" in SOURCE)
for command in ("switch", "torch", "focus", "zoom", "quality", "jpeg"):
    check(f"desktop emits {command} control command", f'"{command}"' in SOURCE)

check("Stop clears the active state and restores connection buttons",
      "self.running = False" in SOURCE and
      'self.connect_button.configure(state="normal")' in SOURCE and
      'self.stop_button.configure(state="disabled")' in SOURCE)
check("close stops polling and closes the window",
      "self.disconnect()" in SOURCE and "self.root.destroy()" in SOURCE)

print(f"Windows connection contract: PASS ({len(checks)} checks)")
for item in checks:
    print(f"  PASS  {item}")
