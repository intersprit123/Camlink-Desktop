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
5. Use **Switch front / rear**, **Flashlight on / off**, **Apply zoom**, **Apply resolution**, and **Apply quality** to control the phone camera where supported.

The desktop viewer uses the CamLink HTTP JPEG frame endpoint and control endpoint on port 8080. The preview preserves the incoming frame's aspect ratio, and the Android service rotates frames using CameraX orientation metadata so portrait phone video can appear portrait on the desktop. The settings sidebar collapses with the small arrow beside the preview to give the camera more screen space. Resolution choices (480p, 720p, 1080p, 2K, 4K) are requests; actual capture resolution depends on the phone and CameraX support. JPEG quality is adjustable from 50–95%. Higher settings may increase lag, heat, battery use, and Wi-Fi bandwidth. This is an early prototype, not encrypted and without pairing authentication. Use only on a trusted local network; do not port-forward the camera server to the internet.

## Build locally

Install Python 3.10+ and run:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name CamLink-Desktop camlink_desktop.py
```

The EXE will be in `dist/CamLink-Desktop.exe`.
