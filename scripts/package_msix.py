#!/usr/bin/env python3
"""Build an unsigned MSIX for Microsoft Store submission from the CamLink EXE.

The Store re-signs MSIX packages submitted for Store distribution. The package
identity and publisher must match the values displayed in Partner Center.
"""
from __future__ import annotations

import argparse
import glob
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

FOUNDATION = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
DESKTOP = "http://schemas.microsoft.com/appx/manifest/desktop/windows10"

ET.register_namespace("", FOUNDATION)
ET.register_namespace("uap", UAP)
ET.register_namespace("desktop", DESKTOP)


def valid_version(value: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value):
        raise argparse.ArgumentTypeError("Version must have four numeric parts, e.g. 1.0.0.0")
    parts = [int(part) for part in value.split(".")]
    if any(part > 65535 for part in parts):
        raise argparse.ArgumentTypeError("Each version part must be between 0 and 65535")
    return ".".join(map(str, parts))


def make_logo(path: Path, size: int) -> None:
    """Create a crisp, original CamLink-themed logo without extra asset files."""
    image = Image.new("RGB", (size, size), "#0a0f1a")
    draw = ImageDraw.Draw(image)
    pad = max(3, size // 8)
    # Rounded camera body and lens.
    draw.rounded_rectangle(
        (pad, int(size * 0.28), size - pad, int(size * 0.76)),
        radius=max(3, size // 10),
        fill="#192438",
        outline="#4f7cff",
        width=max(1, size // 35),
    )
    lens_r = int(size * 0.14)
    cx, cy = size // 2, int(size * 0.52)
    draw.ellipse(
        (cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r),
        fill="#0a0f1a",
        outline="#42d6ad",
        width=max(1, size // 32),
    )
    draw.ellipse(
        (cx - max(1, lens_r // 3), cy - max(1, lens_r // 3),
         cx + max(1, lens_r // 3), cy + max(1, lens_r // 3)),
        fill="#42d6ad",
    )
    # Small viewfinder bump.
    draw.rounded_rectangle(
        (int(size * 0.27), int(size * 0.18), int(size * 0.48), int(size * 0.31)),
        radius=max(2, size // 30),
        fill="#4f7cff",
    )
    image.save(path, format="PNG")


def make_manifest(stage: Path, identity_name: str, publisher: str,
                  publisher_display_name: str, version: str) -> None:
    package = ET.Element(
        f"{{{FOUNDATION}}}Package",
        {"IgnorableNamespaces": "uap desktop"},
    )
    ET.SubElement(
        package, f"{{{FOUNDATION}}}Identity",
        {
            "Name": identity_name,
            "Publisher": publisher,
            "Version": version,
            "ProcessorArchitecture": "x64",
        },
    )
    properties = ET.SubElement(package, f"{{{FOUNDATION}}}Properties")
    ET.SubElement(properties, f"{{{FOUNDATION}}}DisplayName").text = "CamLink Desktop"
    ET.SubElement(properties, f"{{{FOUNDATION}}}PublisherDisplayName").text = publisher_display_name
    ET.SubElement(properties, f"{{{FOUNDATION}}}Logo").text = "Assets\\StoreLogo.png"

    dependencies = ET.SubElement(package, f"{{{FOUNDATION}}}Dependencies")
    ET.SubElement(
        dependencies, f"{{{FOUNDATION}}}TargetDeviceFamily",
        {
            "Name": "Windows.Desktop",
            "MinVersion": "10.0.17763.0",
            "MaxVersionTested": "10.0.26100.0",
        },
    )
    resources = ET.SubElement(package, f"{{{FOUNDATION}}}Resources")
    ET.SubElement(resources, f"{{{FOUNDATION}}}Resource", {"Language": "en-us"})

    applications = ET.SubElement(package, f"{{{FOUNDATION}}}Applications")
    application = ET.SubElement(
        applications, f"{{{FOUNDATION}}}Application",
        {
            "Id": "CamLinkDesktop",
            "Executable": "CamLink-Desktop.exe",
            "EntryPoint": "Windows.FullTrustApplication",
        },
    )
    ET.SubElement(
        application, f"{{{UAP}}}VisualElements",
        {
            "DisplayName": "CamLink Desktop",
            "Description": "View and control the CamLink Android camera stream over Wi-Fi.",
            "BackgroundColor": "#0a0f1a",
            "Square150x150Logo": "Assets\\Square150x150Logo.png",
            "Square44x44Logo": "Assets\\Square44x44Logo.png",
        },
    )
    extensions = ET.SubElement(application, f"{{{FOUNDATION}}}Extensions")
    extension = ET.SubElement(
        extensions, f"{{{DESKTOP}}}Extension",
        {
            "Category": "windows.fullTrustProcess",
            "Executable": "CamLink-Desktop.exe",
        },
    )
    ET.SubElement(extension, f"{{{DESKTOP}}}FullTrustProcess")
    ET.indent(package, space="  ")
    ET.ElementTree(package).write(
        stage / "AppxManifest.xml", encoding="utf-8", xml_declaration=True
    )


def find_makeappx() -> Path:
    candidates = glob.glob(
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\MakeAppx.exe"
    )
    if not candidates:
        raise FileNotFoundError(
            "MakeAppx.exe was not found. Use a Windows GitHub Actions runner with Windows SDK installed."
        )
    return Path(sorted(candidates, reverse=True)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identity-name", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--publisher-display-name", required=True)
    parser.add_argument("--version", type=valid_version, default="1.0.0.0")
    args = parser.parse_args()

    if not args.exe.is_file():
        parser.error(f"EXE not found: {args.exe}")
    for label, value in (
        ("identity name", args.identity_name),
        ("publisher", args.publisher),
        ("publisher display name", args.publisher_display_name),
    ):
        if not value.strip():
            parser.error(f"{label} must not be blank")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    makeappx = find_makeappx()

    with tempfile.TemporaryDirectory(prefix="camlink-msix-") as temporary:
        stage = Path(temporary)
        shutil.copy2(args.exe, stage / "CamLink-Desktop.exe")
        assets = stage / "Assets"
        assets.mkdir()
        make_logo(assets / "StoreLogo.png", 50)
        make_logo(assets / "Square44x44Logo.png", 44)
        make_logo(assets / "Square150x150Logo.png", 150)
        make_manifest(
            stage,
            args.identity_name.strip(),
            args.publisher.strip(),
            args.publisher_display_name.strip(),
            args.version,
        )
        if args.output.exists():
            args.output.unlink()
        subprocess.run(
            [str(makeappx), "pack", "/d", str(stage), "/p", str(args.output), "/o"],
            check=True,
        )

    print(f"Created unsigned Store-submission package: {args.output}")
    print("Upload this .msix file directly on the Partner Center Packages page.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"MSIX packaging failed: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
