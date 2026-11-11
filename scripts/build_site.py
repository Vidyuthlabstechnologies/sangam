"""Build the static public site (home page and legal pages) into site/.

    python scripts/build_site.py

The legal text, stylesheet and page shell come from backend/app/core/legal_content.py,
the same module the backend serves at /legal/*, so the two copies cannot drift apart.
Operator name, contact email and postal address come from the LEGAL_* environment
variables (see backend/app/config.py). Run from any directory.
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.core import legal_content as legal  # noqa: E402

SITE = ROOT / "site"
FONT_DIR = "/assets/fonts"

FONT_FACE_CSS = (
    "@font-face{font-family:'Bricolage Grotesque';font-weight:200 800;font-display:swap;"
    f"src:url({FONT_DIR}/bricolage-grotesque-latin-wght-normal.woff2) format('woff2')}}"
    "@font-face{font-family:'Source Serif 4';font-weight:400;font-style:normal;font-display:swap;"
    f"src:url({FONT_DIR}/source-serif-4-latin-400-normal.woff2) format('woff2')}}"
    "@font-face{font-family:'Source Serif 4';font-weight:400;font-style:italic;font-display:swap;"
    f"src:url({FONT_DIR}/source-serif-4-latin-400-italic.woff2) format('woff2')}}"
    "@font-face{font-family:'Source Serif 4';font-weight:600;font-style:normal;font-display:swap;"
    f"src:url({FONT_DIR}/source-serif-4-latin-600-normal.woff2) format('woff2')}}"
)

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">
<rect width="108" height="108" rx="24" fill="#0D2633"/>
<g fill="none" stroke-linecap="round">
<path d="M29 24C29 50 50 47 50 70V84" stroke="#F59E0B" stroke-width="9"/>
<path d="M79 24C79 50 58 47 58 70V84" stroke="#E6EEF0" stroke-width="9"/>
</g></svg>
"""

HEADERS = """/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests

/assets/*
  Cache-Control: public, max-age=86400

/legal/*
  Cache-Control: public, max-age=3600
"""

ROBOTS = "User-agent: *\nAllow: /\n"

# Hero mark: same geometry as brand/mark.svg, with classes so the two streams can draw in.
HERO_MARK = (
    '<svg class="hero-mark" viewBox="0 0 108 108" role="img" aria-label="Two streams joining into one"'
    ' fill="none" stroke-linecap="round">'
    '<path class="s s1" pathLength="1" d="M29 24C29 50 50 47 50 70V84" stroke="var(--stream-a)" stroke-width="8"/>'
    '<path class="s s2" pathLength="1" d="M79 24C79 50 58 47 58 70V84" stroke="var(--stream-b)" stroke-width="8"/>'
    '<path class="dots" d="M54 24V52" stroke="var(--stream-b)" stroke-opacity=".7" stroke-width="6"'
    ' stroke-dasharray="0 13"/></svg>'
)

HOME_TITLE = "Sangamitra: an assistant that picks up when you can't"
HOME_DESCRIPTION = (
    "Sangamitra answers your business phone, takes callback requests "
    "and sends you a summary of each call."
)

FACTS = (
    ("Calls", "Answers your business number and tells callers an assistant is on the line."),
    ("Callbacks", "Takes a name, a number and a reason, so you can ring back the people who matter."),
    ("Summaries", "Sends you what each caller wanted. You read a few lines instead of a voicemail."),
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")


def home_html() -> str:
    email = escape(settings.legal_contact_email)
    facts = "".join(f"<div><dt>{escape(term)}</dt><dd>{escape(text)}</dd></div>" for term, text in FACTS)
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="dark">'
        f"<title>{escape(HOME_TITLE)}</title>"
        f'<meta name="description" content="{escape(HOME_DESCRIPTION)}">'
        '<link rel="stylesheet" href="/assets/legal.css"><link rel="stylesheet" href="/assets/site.css">'
        '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"></head>'
        '<body class="home"><header class="top">'
        f'<span class="brand">{legal.MARK_SVG}<span>Sangamitra</span></span></header>'
        '<main><section class="hero"><div class="hero-copy">'
        "<h1>An assistant that picks up when you can&rsquo;t.</h1>"
        f'<p class="lede">{escape(HOME_DESCRIPTION)}</p>'
        f'<p><a href="mailto:{email}">Write to us at {email}</a></p></div>'
        f'<div class="hero-art">{HERO_MARK}</div></section>'
        '<section class="about"><h2>What it handles</h2>'
        f'<dl class="facts">{facts}</dl>'
        "<h2>Why the name</h2>"
        "<p>Sangam means confluence, the place where rivers meet. The mark is two streams "
        "that keep their own colour as they join into one line, with a third, fainter one "
        "running between them.</p></section></main>"
        f"{legal.footer_html()}</body></html>"
    )


def build() -> None:
    write(SITE / "assets" / "legal.css", FONT_FACE_CSS + legal.STYLE + "\n")
    write(SITE / "assets" / "favicon.svg", FAVICON_SVG)
    write(SITE / "_headers", HEADERS)
    write(SITE / "robots.txt", ROBOTS)
    write(SITE / "index.html", home_html())
    write(SITE / "legal" / "privacy.html", legal.privacy_policy_html(static_site=True))
    write(SITE / "legal" / "terms.html", legal.terms_html(static_site=True))
    write(SITE / "legal" / "delete-account.html", legal.delete_account_html(static_site=True))


if __name__ == "__main__":
    build()
