#!/usr/bin/env python3
"""Measure CamLink frame delivery on the same LAN as the camera phone.

Example:
  python scripts/benchmark_stream.py 192.168.1.12 --duration 30

This measures client-observed HTTP/JPEG performance. The /stats endpoint, when
available, adds camera-side capture FPS and JPEG encode timing. It does not
change the camera configuration or use the optional stream endpoint.
"""
from __future__ import annotations

import argparse
import io
import json
import statistics
import time
from urllib.request import Request, urlopen

from PIL import Image


def read_url(url: str, timeout: float) -> tuple[bytes, float]:
    started = time.perf_counter()
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
    return payload, (time.perf_counter() - started) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Camera phone IP address")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--duration", type=float, default=20.0, help="Measurement duration in seconds")
    parser.add_argument("--poll-fps", type=float, default=60.0, help="Maximum frame poll rate")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.duration <= 0:
        parser.error("--duration must be positive")
    if not 1 <= args.poll_fps <= 120:
        parser.error("--poll-fps must be between 1 and 120")

    base = f"http://{args.host}:{args.port}"
    interval = 1.0 / args.poll_fps
    deadline = time.monotonic() + args.duration
    previous_payload = None
    requests = unique_frames = failures = total_bytes = 0
    request_ms: list[float] = []
    decode_ms: list[float] = []
    last_stats_at = 0.0
    camera_stats = None
    last_dimensions = None
    started = time.monotonic()

    print(f"CamLink benchmark: {base}/frame for {args.duration:.1f}s (max {args.poll_fps:.0f} polls/s)")
    while time.monotonic() < deadline:
        cycle_started = time.monotonic()
        try:
            payload, elapsed_ms = read_url(f"{base}/frame?t={time.time_ns()}", args.timeout)
            requests += 1
            request_ms.append(elapsed_ms)
            total_bytes += len(payload)

            if payload and payload != previous_payload:
                decode_started = time.perf_counter()
                with Image.open(io.BytesIO(payload)) as image:
                    image.load()
                    last_dimensions = image.size
                decode_ms.append((time.perf_counter() - decode_started) * 1000.0)
                unique_frames += 1
                previous_payload = payload
        except Exception as exc:
            failures += 1
            print(f"  request failed: {exc}")

        now = time.monotonic()
        if now - last_stats_at >= 1.0:
            try:
                raw, _ = read_url(f"{base}/stats?t={time.time_ns()}", args.timeout)
                camera_stats = json.loads(raw.decode("utf-8"))
            except Exception:
                camera_stats = None
            last_stats_at = now

        remaining = interval - (time.monotonic() - cycle_started)
        if remaining > 0:
            time.sleep(remaining)

    elapsed = max(time.monotonic() - started, 0.001)
    avg_request = statistics.fmean(request_ms) if request_ms else 0.0
    p95_request = sorted(request_ms)[min(len(request_ms) - 1, int(len(request_ms) * 0.95))] if request_ms else 0.0
    avg_decode = statistics.fmean(decode_ms) if decode_ms else 0.0

    print("\nResults")
    print(f"  Duration:             {elapsed:.1f}s")
    print(f"  HTTP requests:        {requests} ({requests / elapsed:.1f}/s)")
    print(f"  New JPEG frames:      {unique_frames} ({unique_frames / elapsed:.1f}/s)")
    print(f"  Failed requests:      {failures}")
    print(f"  Received data:        {total_bytes / 1024 / 1024:.2f} MiB ({total_bytes * 8 / elapsed / 1_000_000:.2f} Mbps)")
    print(f"  HTTP latency average: {avg_request:.1f} ms (p95 {p95_request:.1f} ms)")
    print(f"  JPEG decode average:  {avg_decode:.1f} ms")
    if last_dimensions:
        print(f"  Last image size:      {last_dimensions[0]}×{last_dimensions[1]}")
    if camera_stats:
        print(f"  Camera FPS:           {float(camera_stats.get('fps') or 0):.1f}")
        print(f"  Camera JPEG encode:   {float(camera_stats.get('encodeMs') or 0):.1f} ms")
        print(f"  Camera resolution:    {int(camera_stats.get('width') or 0)}×{int(camera_stats.get('height') or 0)}")
        print(f"  Camera JPEG quality:  {int(camera_stats.get('jpegQuality') or 0)}%")
    else:
        print("  Camera-side stats:    unavailable (older camera build?)")
    return 0 if requests and failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
