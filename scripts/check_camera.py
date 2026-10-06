"""Check a camera source: prints resolution and measured fps, saves a snapshot.
Usage:
  python scripts/check_camera.py 0                              # laptop webcam
  python scripts/check_camera.py http://192.168.x.x:8080/video  # phone (IP Webcam)
"""
import os
import sys
import time

import cv2


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src_arg = sys.argv[1]
    src = int(src_arg) if src_arg.isdigit() else src_arg
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

    backend = cv2.CAP_DSHOW if isinstance(src, int) and os.name == "nt" else cv2.CAP_ANY
    cap = cv2.VideoCapture(src, backend)
    if not cap.isOpened():
        print(f"FAIL: could not open source {src_arg!r}")
        sys.exit(2)

    frames, last, t0 = 0, None, time.time()
    while time.time() - t0 < seconds:
        ok, frame = cap.read()
        if not ok:
            print("FAIL: source opened but returned no frame")
            sys.exit(3)
        frames += 1
        last = frame
    elapsed = time.time() - t0
    cap.release()

    h, w = last.shape[:2]
    out = os.path.join(os.path.dirname(__file__), "..", "instance", "camera_check.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, last)
    print(f"OK: {w}x{h}, {frames} frames in {elapsed:.1f}s = {frames / elapsed:.1f} fps")
    print(f"Snapshot saved to {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
