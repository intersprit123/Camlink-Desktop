# CamLink Desktop

Modern Windows desktop viewer for the CamLink Android camera-sharing app, with a large live preview and a collapsible settings panel.

## Download the EXE

1. Open the repository's **Actions** tab.
2. Open the latest successful **Build CamLink Desktop EXE** run.
3. Under **Artifacts**, download `CamLink-Desktop-Windows`.
4. Extract the ZIP and run `CamLink-Desktop.exe`.

GitHub Actions builds the Windows executable automatically when changes are pushed to `main`. You can also run the workflow manually from Actions.

## How to use

1. Connect the camera phone and Windows PC to the same trusted Wi-Fi network.
2. On the Android phone, open CamLink, choose **Share this phone's camera**, grant camera permission, and start sharing.
3. Note the IP address shown by the phone.
4. Open CamLink Desktop, enter that IP address, and click **Connect**.
5. Use **Flip**, **Flash**, **Focus**, the zoom and exposure sliders, the white-balance picker, and image-quality controls where the camera supports them.

## Desktop studio shortcuts and tools

- **Save snapshot** saves the latest received full-resolution frame as JPEG or PNG to a location you choose.
- **Fit to window** scales the preview to the available panel; **Original size** displays the received pixels without resizing.
- **Fullscreen** or **F11** toggles fullscreen; **Esc** exits fullscreen.
- The last camera IP, zoom, exposure, white balance, JPEG quality, resolution selection, preview mode, sidebar visibility, and window size are saved to `~/.camlink_desktop.json` (your Windows home folder). Settings are restored on the next launch.

## Performance-first streaming

The desktop reader keeps a single newest-frame slot instead of decoding every JPEG and queuing one UI callback per frame. It decodes at the preview refresh rate (about 60 Hz), drops stale frames instead of accumulating delay, uses faster bilinear scaling, and updates telemetry once per second. The preview reports received FPS, decode time, and estimated stream payload bitrate. Received FPS is not the same as displayed FPS, and decode time is not end-to-end network latency.

The Android service defaults to 720p and JPEG quality 75 to favor smoothness, lower CPU load, and reduced Wi-Fi bandwidth. Use **⚡ Max FPS preset** in the desktop or web controls to request 720p / JPEG 75 from the camera phone. Higher resolution and quality remain selectable when image detail matters more than smoothness. Capture rate depends on the phone camera, device load, network and PC.

CamLink uses continuous multipart MJPEG (`/stream`) and the control endpoint on port 8080. It is simpler to use but is still CPU-heavy compared with a hardware-encoded H.264 pipeline; hardware video encoding remains a potential next major upgrade. The preview preserves incoming aspect ratio, and the Android service rotates frames according to CameraX orientation metadata. This is an early prototype, not encrypted and without pairing authentication. Use only on a trusted local network; do not port-forward the camera server to the internet.

## Build locally

Install Python 3.10+ and run:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name CamLink-Desktop camlink_desktop.py
```

The EXE will be in `dist/CamLink-Desktop.exe`.
