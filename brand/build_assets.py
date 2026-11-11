"""Render the store graphics from brand/mark.svg with headless Chrome.

    python brand/build_assets.py

Writes brand/play-icon-512.png and brand/play-feature-1024x500.png. Chrome is the
renderer so the fonts in site/assets/fonts are used exactly as the website uses them.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
FONTS = ROOT / "site" / "assets" / "fonts"

INK = "#0D2633"
MIST = "#E6EEF0"
AMBER = "#F59E0B"

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome",
    "chromium",
)

FONT_FACE = f"""
@font-face {{
  font-family: 'Bricolage Grotesque';
  src: url('{(FONTS / "bricolage-grotesque-latin-wght-normal.woff2").as_uri()}') format('woff2');
  font-weight: 200 800;
}}
"""

ICON_HTML = f"""<!doctype html><meta charset=utf-8>
<style>html,body{{margin:0;width:512px;height:512px;background:{INK};overflow:hidden}}
img{{position:absolute;left:-24px;top:-24px;width:560px;height:560px}}</style>
<img src="{(BRAND / "mark.svg").as_uri()}" alt="">"""

FEATURE_HTML = f"""<!doctype html><meta charset=utf-8>
<style>{FONT_FACE}
html,body{{margin:0;width:1024px;height:500px;background:{INK};overflow:hidden}}
body{{position:relative;font-family:'Bricolage Grotesque',system-ui,sans-serif;color:{MIST}}}
img{{position:absolute;left:78px;top:50px;width:400px;height:400px}}
.words{{position:absolute;left:470px;top:0;height:500px;display:flex;flex-direction:column;justify-content:center;width:480px}}
h1{{margin:0;font-size:92px;line-height:1;font-weight:700;letter-spacing:-.025em}}
p{{margin:22px 0 0;font-size:31px;line-height:1.28;font-weight:400;color:{MIST};opacity:.82;max-width:420px}}
.rule{{width:56px;height:6px;border-radius:3px;background:{AMBER};margin-top:28px}}
</style>
<img src="{(BRAND / "mark.svg").as_uri()}" alt="">
<div class=words><h1>Sangamitra</h1><div class=rule></div><p>An assistant that picks up your business calls.</p></div>"""


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    sys.exit("No Chrome or Edge found; install one to render the graphics.")


def render(chrome: str, html: str, width: int, height: int, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={width},{height}", f"--screenshot={out}", page.as_uri(),
            ],
            check=True, capture_output=True,
        )
    print(f"wrote {out.relative_to(ROOT)}")


def main() -> None:
    chrome = find_chrome()
    render(chrome, ICON_HTML, 512, 512, BRAND / "play-icon-512.png")
    render(chrome, FEATURE_HTML, 1024, 500, BRAND / "play-feature-1024x500.png")


if __name__ == "__main__":
    main()
