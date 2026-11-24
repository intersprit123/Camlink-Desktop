#!/usr/bin/env python3
"""Measure CamLink Android capture FPS at each built-in resolution preset.

Start camera sharing on Android first. For USB, establish the ADB forward tunnel
from CamLink Desktop (USB · ADB -> Connect), then run this script with host
127.0.0.1. The script changes resolution through /control and samples /stats.
"""
import argparse
import csv
import json
import statistics
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PRESETS = [
    (0, "480p"),
    (1, "720p"),
    (2, "1080p"),
    (3, "1440p"),
    (4, "2160p / 4K"),
]


def get_text(url, timeout):
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def get_stats(base, timeout):
    return json.loads(get_text(f"{base}/stats?t={time.time_ns()}", timeout))


def main():
    parser = argparse.ArgumentParser(description="Benchmark CamLink capture FPS across resolution presets.")
    parser.add_argument("--host", default="127.0.0.1", help="Phone IP for Wi-Fi, or 127.0.0.1 for an active ADB USB forward")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--warmup", type=float, default=5.0, help="Seconds to wait after changing resolution")
    parser.add_argument("--sample", type=float, default=10.0, help="Seconds to sample each resolution")
    parser.add_argument("--output", default="camlink-resolution-benchmark.csv")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"
    rows = []
    print(f"CamLink resolution benchmark: {base}")
    print("Keep the phone still, use the same camera/lens, and avoid other camera apps.\n")

    initial = get_stats(base, 3)
    print(f"Connected. Current capture: {initial.get('width')}x{initial.get('height')} "
          f"at {initial.get('fps')} FPS\n")

    for index, label in PRESETS:
        command = f"{base}/control?{urlencode({'cmd': 'quality', 'value': index})}"
        try:
            result = get_text(command, 5)
            print(f"[{label}] {result.strip()}")
        except URLError as exc:
            print(f"[{label}] Could not request resolution: {exc}")
            continue

        time.sleep(max(0.0, args.warmup))
        samples = []
        deadline = time.monotonic() + max(1.0, args.sample)
        while time.monotonic() < deadline:
            try:
                samples.append(get_stats(base, 3))
            except Exception as exc:
                print(f"  Stats sample failed: {exc}")
            time.sleep(1.0)

        if not samples:
            print("  No stats received; skipping this preset.\n")
            continue

        fps = [float(s.get("fps") or 0) for s in samples]
        encode = [float(s.get("encodeMs") or 0) for s in samples]
        bitrate = [float(s.get("bitrateMbps") or 0) for s in samples]
        actual_sizes = [f"{s.get('width', 0)}x{s.get('height', 0)}" for s in samples]
        most_common_size = max(set(actual_sizes), key=actual_sizes.count)
        row = {
            "preset": label,
            "actual_resolution": most_common_size,
            "avg_capture_fps": round(statistics.mean(fps), 2),
            "min_capture_fps": round(min(fps), 2),
            "max_capture_fps": round(max(fps), 2),
            "avg_jpeg_encode_ms": round(statistics.mean(encode), 2),
            "avg_bitrate_mbps": round(statistics.mean(bitrate), 2),
            "samples": len(samples),
        }
        rows.append(row)
        print(f"  Actual {most_common_size} | avg {row['avg_capture_fps']} FPS "
              f"(min {row['min_capture_fps']}, max {row['max_capture_fps']}) | "
              f"JPEG encode {row['avg_jpeg_encode_ms']} ms | "
              f"{row['avg_bitrate_mbps']} Mbps\n")

    if rows:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(rows)} resolution results to {args.output}")
    else:
        print("No benchmark results were collected.")


if __name__ == "__main__":
    main()
