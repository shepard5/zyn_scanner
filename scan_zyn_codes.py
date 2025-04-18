#!/usr/bin/env python3
# Auto-detect ZBar library via ctypes.util.find_library on macOS or Linux
import os
import sys
import ctypes.util
if 'ZBAR_LIBRARY_PATH' not in os.environ:
    _lib = ctypes.util.find_library('zbar') or ctypes.util.find_library('zbar.0')
    if _lib:
        os.environ['ZBAR_LIBRARY_PATH'] = _lib
        print(f'Set ZBAR_LIBRARY_PATH to {_lib}', file=sys.stderr)
"""
scan_zyn_codes.py

Extract unique reward codes from QR codes on Zyn container backs via video.
"""
import os
import sys
import cv2
import re
import argparse
# Debug: print ZBar library lookup
import ctypes.util
# Common brew/homebrew and local paths for libzbar
brew_libs = [
    # User-local ~/lib workaround: symlink your zbar dylib here
    os.path.expanduser('~/lib/libzbar.dylib'),
    os.path.expanduser('~/lib/libzbar.0.dylib'),
    # Homebrew (ARM)
    '/opt/homebrew/lib/libzbar.dylib',
    '/opt/homebrew/lib/libzbar.0.dylib',
    # Homebrew (Intel) and standard locations
    '/usr/local/lib/libzbar.dylib',
    '/usr/local/lib/libzbar.0.dylib',
    '/usr/local/opt/zbar/lib/libzbar.dylib',
    '/usr/local/opt/zbar/lib/libzbar.0.dylib'
]
print('PYZBAR DEBUG:')
print('  ctypes.util.find_library("zbar") ->', ctypes.util.find_library('zbar'))
for lib in brew_libs:
    print(f'  exists {lib}?', os.path.isfile(lib))
print('  ZBAR_LIBRARY_PATH=', os.environ.get('ZBAR_LIBRARY_PATH'))
# After debug lookup, if ZBAR_LIBRARY_PATH not set, try our brew paths
if 'ZBAR_LIBRARY_PATH' not in os.environ:
    for lib in brew_libs:
        if os.path.isfile(lib):
            os.environ['ZBAR_LIBRARY_PATH'] = lib
            print(f"Setting ZBAR_LIBRARY_PATH to {lib}", file=sys.stderr)
            break
# Try to import pyzbar (ZBar). If unavailable or fails to load, fall back to OpenCV QRCodeDetector.
try:
    from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol
    have_pyzbar = True
except ImportError as ie:
    have_pyzbar = False
    print(f"Warning: pyzbar Python module not found ({ie}); install with 'pip install pyzbar'. Falling back to OpenCV QRCodeDetector", file=sys.stderr)
    detector_cv = cv2.QRCodeDetector()
except OSError as oe:
    have_pyzbar = False
    zbar_path = os.environ.get('ZBAR_LIBRARY_PATH', '<not set>')
    print(f"Warning: could not load ZBar library at '{zbar_path}' ({oe}); ensure ZBAR_LIBRARY_PATH is correct. Falling back to OpenCV QRCodeDetector", file=sys.stderr)
    detector_cv = cv2.QRCodeDetector()

def extract_codes_from_frame(frame, code_regex, full_url=False, upsample=1):
    """
    Detect QR codes in frame and return set of code strings.
    If full_url is True, returns full decoded URLs; otherwise, returns only tail code segment matching regex.
    """
    # Upsample to improve QR detection for small codes
    if upsample and upsample > 1:
        frame = cv2.resize(frame, None,
                           fx=upsample, fy=upsample,
                           interpolation=cv2.INTER_LINEAR)
    codes = set()
    if have_pyzbar:
        # Decode via ZBar (only QR codes)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded_objs = pyzbar_decode(gray, symbols=[ZBarSymbol.QRCODE])
        for obj in decoded_objs:
            try:
                url = obj.data.decode('utf-8', errors='ignore')
            except Exception:
                continue
            if full_url:
                codes.add(url)
            else:
                # Extract substring after last slash via regex
                match = re.search(r'[^/]+$', url.strip())
                if not match:
                    continue
                code = match.group(0)
                if code_regex.fullmatch(code):
                    codes.add(code)
    else:
        # Fallback: OpenCV QRCodeDetector
        try:
            ok, decoded_info, _, _ = detector_cv.detectAndDecodeMulti(frame)
        except Exception:
            data, _pts = detector_cv.detectAndDecode(frame)
            decoded_info = [data] if data else []
            ok = bool(data)
        if ok:
            for url in decoded_info:
                if not url:
                    continue
                if full_url:
                    codes.add(url)
                else:
                    # Extract substring after last slash via regex
                    match = re.search(r'[^/]+$', url.strip())
                    if not match:
                        continue
                    code = match.group(0)
                    if code_regex.fullmatch(code):
                        codes.add(code)
    return codes

def main():
    parser = argparse.ArgumentParser(description='Scan Zyn container codes from video')
    parser.add_argument('--video', required=True, help='Path to input video file')
    parser.add_argument('--interval', type=int, default=10,
                        help='Process every Nth frame (default: 10)')
    parser.add_argument('--pattern', default=r'[A-Z0-9]{6,}',
                        help='Regex pattern for codes (default: [A-Z0-9]{6,}), applied case-insensitively')
    parser.add_argument('--output', help='Write unique codes to this file')
    parser.add_argument('--full-url', action='store_true',
                        help='Store the full decoded URL instead of just the code segment')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug output: bounding boxes and decoded data for each frame')
    parser.add_argument('--upsample', type=int, default=1,
                        help='Upsample factor for frames before QR decode (default: 1)')
    args = parser.parse_args()

    # Compile code regex (for the tail of URL)
    try:
        # Compile regex for code matching, case-insensitive by default
        code_regex = re.compile(args.pattern, re.IGNORECASE)
    except re.error as e:
        print(f'Invalid regex pattern: {e}', file=sys.stderr)
        sys.exit(1)

    # Open video
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f'Error: unable to open video "{args.video}"', file=sys.stderr)
        sys.exit(1)

    unique_codes = set()
    frame_idx = 0
    print('Scanning video for codes...')
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % args.interval != 0:
            continue
        # Debug visualization: show detected QR boxes and data
        if args.debug:
            dbg = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if have_pyzbar:
                # Only decode QR codes in debug mode
                objs = pyzbar_decode(gray, symbols=[ZBarSymbol.QRCODE])
                print(f"[Debug] Frame {frame_idx}: {len(objs)} QR codes decoded")
                for obj in objs:
                    x, y, w, h = obj.rect
                    cv2.rectangle(dbg, (x, y), (x+w, y+h), (0,255,0), 2)
                    txt = obj.data.decode('utf-8', errors='ignore')
                    cv2.putText(dbg, txt, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
            else:
                ok, pts = detector_cv.detect(frame)
                print(f"[Debug] Frame {frame_idx}: OpenCV detect {'ok' if ok else 'fail'}")
                if ok and pts is not None:
                    for quad in pts:
                        pts_int = quad.astype(int)
                        cv2.polylines(dbg, [pts_int], True, (255,0,0), 2)
            cv2.imshow('Debug', dbg)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                args.debug = False
                cv2.destroyWindow('Debug')
        # Detect QR codes and extract reward code after last slash
        codes = extract_codes_from_frame(frame, code_regex, args.full_url, args.upsample)
        new_codes = codes - unique_codes
        if new_codes:
            for code in sorted(new_codes):
                print('Found code:', code)
            unique_codes.update(new_codes)
    cap.release()
    # Output results
    print(f'Total unique codes: {len(unique_codes)}')
    if args.output:
        try:
            with open(args.output, 'w') as f:
                for code in sorted(unique_codes):
                    f.write(code + '\n')
            print(f'Codes written to {args.output}')
        except IOError as e:
            print(f'Error writing to output file: {e}', file=sys.stderr)
    else:
        for code in sorted(unique_codes):
            print(code)

if __name__ == '__main__':
    main()