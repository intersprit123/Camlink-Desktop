# CamLink Desktop

Windows desktop viewer for the CamLink Android camera-sharing app.

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
5. Use **Switch front / rear**, **Flashlight on / off**, and **Apply zoom** to control the phone camera where supported.

The desktop viewer uses the CamLink HTTP JPEG frame endpoint and control endpoint on port 8080. This is an early prototype, not encrypted and without pairing authentication. Use only on a trusted local network; do not port-forward the camera server to the internet.

## Build locally

Install Python 3.10+ and run:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name CamLink-Desktop camlink_desktop.py
```

The EXE will be in `dist/CamLink-Desktop.exe`.
