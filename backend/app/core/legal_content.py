"""HTML for the public legal pages Google Play and the DPDP Act 2023 require.

Every value that comes from settings is HTML-escaped before it is placed in a
page. The text describes what the Android app and backend really do; if a data
flow changes (a new processor, a new retention period), change it here and in
docs/PLAY_CONSOLE.md in the same commit.
"""
from __future__ import annotations

from html import escape

from app.config import settings

DELETION_REQUEST_DAYS = 30
GST_RETENTION_YEARS = 6

# Shared by the backend pages (inlined) and the static site (written to assets/legal.css
# by scripts/build_site.py, which prepends the @font-face rules). Fonts fall back to
# system faces, so the inlined copy needs no font files.
STYLE = (
    ":root{--bg:#F4F8F9;--ink:#0D2633;--muted:#4B6470;--rule:#C9D8DD;--link:#9A5B00;"
    "--stream-a:#D97706;--stream-b:#0D2633}"
    "@media(prefers-color-scheme:dark){:root{--bg:#0D2633;--ink:#E6EEF0;--muted:#9DB2BA;"
    "--rule:#27414D;--link:#F59E0B;--stream-a:#F59E0B;--stream-b:#E6EEF0}}"
    "*{box-sizing:border-box}"
    "body{margin:0;background:var(--bg);color:var(--ink);"
    "font:400 1.0625rem/1.72 'Source Serif 4',Charter,'Iowan Old Style',Georgia,serif}"
    ".top,main,footer{max-width:41rem;margin:0 auto;padding:0 1.25rem}"
    ".top{padding-top:1.75rem;padding-bottom:.5rem}"
    ".brand{display:inline-flex;align-items:center;gap:.55rem;color:var(--ink);"
    "text-decoration:none;font:700 1.15rem/1 'Bricolage Grotesque',system-ui,sans-serif;"
    "letter-spacing:-.01em}"
    ".brand svg{width:2rem;height:2rem}"
    "h1,h2,th{font-family:'Bricolage Grotesque',system-ui,sans-serif}"
    "h1{font-size:clamp(1.9rem,5vw,2.6rem);line-height:1.08;letter-spacing:-.025em;"
    "margin:2.5rem 0 1.25rem}"
    "h2{font-size:1.25rem;font-weight:600;letter-spacing:-.01em;margin:2.5rem 0 .4rem}"
    "p,ul,ol{margin:.75rem 0}li{margin:.35rem 0}"
    "a{color:var(--link);text-underline-offset:.18em}"
    "a:focus-visible{outline:2px solid var(--link);outline-offset:3px;border-radius:2px}"
    "table{border-collapse:collapse;width:100%;margin:1rem 0}"
    "th,td{padding:.7rem 1rem .7rem 0;text-align:left;vertical-align:top;"
    "border-bottom:1px solid var(--rule)}"
    "th{font-size:.95rem;font-weight:600;color:var(--muted)}"
    "footer{margin-top:4rem;padding-top:1.25rem;padding-bottom:3rem;"
    "border-top:1px solid var(--rule);color:var(--muted);"
    "font:400 .92rem/1.6 'Bricolage Grotesque',system-ui,sans-serif}"
    "footer a{color:var(--muted)}footer nav{display:flex;flex-wrap:wrap;gap:.4rem 1.25rem}"
)

# Two streams that meet, with a dotted third between them (the Triveni Sangam).
# Colours come from CSS variables so the mark reads on light and dark pages.
MARK_SVG = (
    '<svg viewBox="0 0 108 108" aria-hidden="true" fill="none" stroke-linecap="round">'
    '<path d="M29 24C29 50 50 47 50 70V84" stroke="var(--stream-a)" stroke-width="8"/>'
    '<path d="M79 24C79 50 58 47 58 70V84" stroke="var(--stream-b)" stroke-width="8"/>'
    '<path d="M54 24V52" stroke="var(--stream-b)" stroke-opacity=".6" stroke-width="6" '
    'stroke-dasharray="0 13"/></svg>'
)

_FOOTER_LINKS = (
    ("/legal/privacy", "Privacy policy"),
    ("/legal/terms", "Terms of use"),
    ("/legal/delete-account", "Delete your account"),
)


def _operator() -> str:
    return escape(settings.legal_operator_name)


def _email() -> str:
    return escape(settings.legal_contact_email)


def _contact_block() -> str:
    address = "<br>".join(
        escape(line.strip()) for line in settings.legal_postal_address.splitlines() if line.strip()
    )
    lines = [f'<p><strong>{_operator()}</strong><br>Email: <a href="mailto:{_email()}">{_email()}</a>']
    if address:
        lines.append(f"<br>{address}")
    lines.append("</p>")
    return "".join(lines)


def footer_html() -> str:
    links = "".join(f'<a href="{href}">{label}</a>' for href, label in _FOOTER_LINKS)
    return f"<footer><nav>{links}</nav><p>{_operator()}</p></footer>"


def _page(title: str, body: str, *, static_site: bool = False) -> str:
    """Wrap a body fragment in the shared shell.

    The backend inlines STYLE. The static site links /assets/legal.css (STYLE plus
    font files) and makes the brand mark a link to the site home page.
    """
    css = (
        '<link rel="stylesheet" href="/assets/legal.css">'
        '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">'
        if static_site
        else f"<style>{STYLE}</style>"
    )
    brand_inner = f"{MARK_SVG}<span>Sangamitra</span>"
    brand = (
        f'<a class="brand" href="/">{brand_inner}</a>'
        if static_site
        else f'<span class="brand">{brand_inner}</span>'
    )
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{escape(title)}</title>{css}</head>"
        f'<body><header class="top">{brand}</header>'
        f"<main><h1>{escape(title)}</h1>{body}</main>{footer_html()}</body></html>"
    )


def privacy_policy_html(*, static_site: bool = False) -> str:
    body = f"""
<p>This policy explains what the Sangamitra AI Android app and its servers collect, why, who
processes it, and the choices you have. {_operator()} follows the Digital Personal Data
Protection (DPDP) Act 2023 (India) and the Google Play User Data policy.</p>

<h2>What we collect</h2>
<table>
<tr><th>Data</th><th>Why</th></tr>
<tr><td>Name, email address and sign-in identifiers (Google account id, Firebase user id)</td>
<td>To create your account and sign you in with Google or email and password.</td></tr>
<tr><td>Business profile, workflows and settings you enter</td>
<td>To set up and run your AI calling assistant.</td></tr>
<tr><td>Call summaries, caller callback requests and call duration</td>
<td>To show the business owner what the assistant handled and to bill call usage.</td></tr>
<tr><td>Audio from your microphone, only while you record a voice instruction in the app</td>
<td>To turn your spoken instruction into text and a workflow. The app asks for microphone permission first.</td></tr>
<tr><td>Notification token (Firebase Cloud Messaging)</td>
<td>To send you call, payment and service alerts on this device.</td></tr>
<tr><td>Purchase records (plan, amount, Google Play order id)</td>
<td>To credit your wallet and keep invoices.</td></tr>
</table>
<p>We do not collect your location, contacts, photos or advertising ID, and the app shows no ads.
We do not sell your personal data.</p>

<h2>Who processes it for us</h2>
<ul>
<li><strong>Google Firebase</strong> (Authentication, Cloud Firestore, Cloud Messaging): sign-in, a small user profile record and push notifications.</li>
<li><strong>Google Play</strong> and <strong>RevenueCat</strong>: purchases and subscriptions are handled by Google Play Billing; RevenueCat validates each purchase and tells our servers it happened.</li>
<li><strong>Sarvam AI</strong>: speech-to-text, text-to-speech and language models that run the voice assistant and transcribe your recorded instructions.</li>
<li><strong>Razorpay</strong>: card and UPI payments in builds not distributed through Google Play.</li>
</ul>
<p>Data is encrypted in transit with HTTPS. On your device, sign-in tokens are kept in
Android encrypted storage.</p>

<h2>Sensitive identifiers</h2>
<p>Twelve-digit Aadhaar numbers and ten-character PAN numbers are redacted before anything is stored.</p>

<h2>Callers</h2>
<p>Callers are told that an AI assistant is answering. Call summaries are stored for the business
owner who deployed the assistant.</p>

<h2>How long we keep data</h2>
<p>We keep your data while your account is active. When you delete your account (see below) we
erase your business profile, phone-number binding, tool connections, workflows, vendor documents,
callback requests and notification tokens. Payment and invoice ledger entries are kept for at least
{GST_RETENTION_YEARS} years because Indian GST law requires it; they are detached from your business name and GSTIN.</p>

<h2>Your rights</h2>
<p>Under the DPDP Act you may ask to access, correct or erase your personal data, withdraw
consent, and complain about how it is handled. Write to the contact below. You can delete your
account yourself, as described at <a href="/legal/delete-account">/legal/delete-account</a>.</p>

<h2>Children</h2>
<p>The app is for people aged 18 and over and is not directed at children.</p>

<h2>Contact and grievance officer</h2>
{_contact_block()}
<p>Changes to this policy are published on this page.</p>
"""
    return _page("Privacy policy", body, static_site=static_site)


def terms_html(*, static_site: bool = False) -> str:
    body = f"""
<p>These Terms of use apply to the Sangamitra AI app and service run by {_operator()}.
By creating an account you agree to them.</p>

<h2>The service</h2>
<p>Sangamitra AI lets a business set up an AI assistant that answers phone calls and runs
workflows. You are responsible for the instructions you give it and for having the right to
record, store and process the calls your business receives.</p>

<h2>Your account</h2>
<p>You must be 18 or over. Keep your sign-in details safe and tell us if you think someone else
has used your account.</p>

<h2>Plans, wallet and payments</h2>
<p>Plans are sold through Google Play subscriptions and one-time products, and GST is shown in the
app before you pay. Call usage is deducted from your wallet at the rate shown in the app. Google
Play handles subscription renewal, cancellation and refunds under its own rules. Wallet credit has
no cash value and is not transferable.</p>

<h2>Acceptable use</h2>
<p>Do not use the service for unlawful calls, spam, harassment, impersonation or collecting
data you are not allowed to collect. We may pause an account that does.</p>

<h2>AI output</h2>
<p>The assistant can make mistakes. Review call summaries before you rely on them for legal,
medical or financial decisions.</p>

<h2>Ending the service</h2>
<p>You may stop at any time and delete your account at
<a href="/legal/delete-account">/legal/delete-account</a>. We may suspend or end the service for a
breach of these terms.</p>

<h2>Liability</h2>
<p>To the extent the law allows, the service is provided as is and {_operator()} is not liable
for indirect or consequential loss.</p>

<h2>Governing law</h2>
<p>These terms are governed by the laws of India.</p>

<h2>Contact</h2>
{_contact_block()}
<p>Purchases are processed by Google Play. Read how we handle your data in our
<a href="/legal/privacy">Privacy Policy</a>.</p>
"""
    return _page("Terms of use", body, static_site=static_site)


def delete_account_html(*, static_site: bool = False) -> str:
    body = f"""
<p>You can delete your Sangamitra AI account and its data in either of two ways.</p>

<h2>Option 1: inside the app</h2>
<ol>
<li>Open Sangamitra AI and sign in.</li>
<li>Tap <strong>Voice Agent</strong> in the bottom bar.</li>
<li>Scroll to the bottom of the screen and tap <strong>Delete Account</strong>.</li>
<li>Tap <strong>Delete Permanently</strong>. Your data is erased and you are signed out.</li>
</ol>

<h2>Option 2: by email</h2>
<p>If you can no longer open the app, email
<a href="mailto:{_email()}">{_email()}</a> from the address you signed up with, with the subject
"Delete account". We will confirm your identity and complete the deletion within
{DELETION_REQUEST_DAYS} days.</p>

<h2>What is deleted</h2>
<ul>
<li>Your profile record (name, email address and sign-in provider) held in Firebase</li>
<li>Your sign-in login. If Firebase asks you to sign in again before it will remove the login,
email us and we will remove it for you</li>
<li>Your business profile and assigned phone number binding</li>
<li>Connected tools, workflows, vendor documents and callback requests</li>
<li>Notification tokens</li>
</ul>

<h2>What is kept</h2>
<p>Payment and invoice ledger entries are kept for at least {GST_RETENTION_YEARS} years because Indian GST law
requires it. They are detached from your business name and GSTIN. Purchase records held by
Google Play follow Google's own retention.</p>

<h2>Contact</h2>
{_contact_block()}
<p>See also our <a href="/legal/privacy">Privacy Policy</a>.</p>
"""
    return _page("Delete your account", body, static_site=static_site)
