 # Zyn Container Code Scanner

 This utility extracts unique reward codes embedded in QR codes printed on the backs of empty Zyn containers from a video.
 Lay out multiple container backs, record a short video, and this script will detect and decode each QR code URL, then pull out the code after the last slash.

 ## Features
- Process an input video and sample frames at a configurable interval
- Detect and decode QR codes using pyzbar (ZBar)
- Extract the substring after the last slash from each decoded URL (or capture full URL with `--full-url`)
- Upsample frames prior to QR decode for small-code detection (`--upsample`)

 ## Requirements
- Python 3.7+
- OpenCV (installed via `opencv-python`)
- ZBar library (system package for QR code decoding):
  - macOS (Homebrew): `brew install zbar`
  - Linux (Debian/Ubuntu): `sudo apt install libzbar0`
  - Local symlink workaround: if the library isn’t autodetected, symlink it into `~/lib`:
      mkdir -p ~/lib && ln -s "$(brew --prefix zbar)/lib/libzbar.dylib" ~/lib/libzbar.dylib
  - If installed in a non-standard location, set the `ZBAR_LIBRARY_PATH` environment variable to the full path of the shared library (e.g., `export ZBAR_LIBRARY_PATH=/opt/homebrew/lib/libzbar.dylib`).
  - If unavailable, the script will fall back to OpenCV's QRCodeDetector (which may miss small codes).

 ## Installation
 ```bash
 pip install -r requirements.txt
 ```

 ## Usage
```bash
python scan_zyn_codes.py \
  --video path/to/containers.mp4 \
  --interval 5     # process every 5th frame (default 10) \
  --pattern "[A-Z0-9]{6,}"  # regex to validate code segment (case-insensitive) \
  --output codes.txt \
  [--full-url]      # include this flag to capture the full decoded URL instead of just the last segment \
  [--upsample 2]    # upsample factor for frame resizing (default: 1)
```

 - `--video`: Path to input video file
 - `--interval`: Process every Nth frame (default: 10)
- `--pattern`: Regex pattern for code filtering (default: `[A-Z0-9]{6,}`), applied case-insensitively
 - `--output`: Optional path to write codes (one per line)

 ## Example
 ```bash
 python scan_zyn_codes.py --video containers.mp4 --interval 15 --output codes.txt
 ```
 ```text
 DEADBE
 FACE42
 123ABC
 ```

## Submitting Codes

After extracting codes, you can submit them automatically using `submit_zyn_codes.py`.

Usage (defaults provided):
```bash
python submit_zyn_codes.py \
  --codes-file codes.txt \
  [--login-url https://us.zyn.com/login/] \
  [--submit-url https://us.zyn.com/ZYNRewards/] \
  [--dry-run] \
  [--browser]     # use Selenium-based browser automation
  [--verbose]
```

`--login-url` defaults to `https://us.zyn.com/login/`, and `--submit-url` defaults to `https://us.zyn.com/ZYNRewards/`. Only override if needed.
  
## Running in Binder (no local install required)

You can launch this tool in a free online environment via [Binder](https://mybinder.org/) without installing anything locally.

1. Push this repository to a public GitHub repository (e.g., `github.com/yourusername/zyn_scanner`).
2. Ensure the files `requirements.txt` (Python deps) and `apt.txt` (system packages) are in the repo root.
3. Open the Binder link (replace `yourusername` and `zyn_scanner`):

   https://mybinder.org/v2/gh/yourusername/zyn_scanner/HEAD?urlpath=lab/tree

4. In the launched JupyterLab interface, open a new terminal window.
5. In the terminal, run:
   ```bash
   # Optionally set your credentials
   export ZYN_USERNAME="you@example.com"
   export ZYN_PASSWORD="YourSecretPassword"

   # Dry-run with browser automation
   python submit_zyn_codes.py --codes-file codes.txt --browser --dry-run

   # Full submission
   python submit_zyn_codes.py --codes-file codes.txt --browser
   ```

This uses the `apt.txt` to install Chrome and related drivers, plus `requirements.txt` for Python packages, all in a cloud container.

By default, the script submits codes via HTTP requests. If the rewards site requires JavaScript or dynamic interaction, include `--browser` to use Selenium. Ensure you have Chrome installed and dependencies (`selenium`, `webdriver-manager`) by running:
```bash
pip install -r requirements.txt
```

 Codes printed to `codes.txt` and console.
 Feel free to adjust the regex pattern or frame sampling interval if needed.