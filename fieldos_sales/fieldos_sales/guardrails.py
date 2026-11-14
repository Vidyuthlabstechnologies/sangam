"""Hard rules checked in code on every line the AI is about to say or send.

Prompts ask the model to behave; these checks make sure it did. Any text that
fails is regenerated once and otherwise replaced with a safe line.

1. Never reveal pricing in any form (amounts, rates, discounts, "free",
   "cheaper than", trial-to-paid terms).
2. Never claim to be a human.
3. Detect a prospect's opt-out ("stop", "don't call", "band karo", "vaddu"...).
"""
from __future__ import annotations

import re
import unicodedata

_FLAGS = re.IGNORECASE | re.UNICODE

# --- 1. pricing -----------------------------------------------------------
_PRICE_PATTERNS = [
    r"₹", r"\brs\.?\s*\d", r"\binr\b", r"\brupees?\b", r"\brupay", r"रुपय", r"रुपए", r"రూపాయ",
    r"\d[\d,.]*\s*(?:k|cr|lakhs?|lacs?|crores?|thousand|hundred)\b",
    r"\blakhs?\b", r"\blacs?\b", r"\bcrores?\b", r"लाख", r"करोड़", r"హజార్|లక్ష|కోటి",
    r"\bprice[sd]?\b", r"\bpricing\b", r"\bcosts?\b", r"\bcosting\b", r"\bcostly\b",
    r"\bcheap(?:er|est|ly)?\b", r"\bafford", r"\bdiscount", r"\boff(?:er)?\s+of\s+\d", r"\d+\s*%\s*off\b",
    r"\bper\s+(?:month|year|annum|user|person|seat|site|head|day)\b", r"\b(?:monthly|yearly|annual)\s+(?:fee|plan|charge|subscription|payment)",
    r"\bsubscription\b", r"\bfees?\b", r"\bcharges?\b(?!\s+(?:of|against)\s+the\s+(?:po|site))", r"\btariff",
    r"\bfree\b", r"\bno[- ]cost\b", r"\bcosts? nothing\b", r"\bpaid\s+(?:pilot|plan|version|seat|tier)\b",
    r"\bplans? (?:start|begin)s?\b", r"\bbudget[- ]friendly\b", r"\binexpensive\b", r"\bvalue for money\b",
    r"\bgst\s+(?:extra|included|inclusive)\b", r"\binvoice\s+(?:amount|value)\b",
    r"\bmuft\b", r"\bsasta\b", r"\bkeemat\b", r"\bkimat\b", r"\bdaam\b",
    r"मुफ्त|मुफ़्त|फ्री|सस्ता|कीमत|दाम|शुल्क|मूल्य",
    r"ఉచితం|ఉచిత|ధర|చౌక|రుసుము|ఫ్రీ",
    r"\bdhara\b|\buchitham\b",
]
_PRICE_RE = re.compile("|".join(_PRICE_PATTERNS), _FLAGS)
# Plain money amounts like "49,000" or "2.49" next to a money-ish word are caught above;
# a bare large number with commas in Indian grouping is also blocked.
_INDIAN_AMOUNT_RE = re.compile(r"\b\d{1,2}(?:,\d{2})+,\d{3}\b|\b\d{1,3}(?:,\d{3})+\b")

# Questions about price coming FROM the prospect (wider net; used to deflect).
_PRICE_QUESTION_RE = re.compile(
    r"\b(?:price|pricing|cost|costs|charges?|rate|rates|fees?|how much|kitna|kitne|kitni|"
    r"paisa|paise|quotation|subscription|pricing\s+plan|free\s+trial|free\s+version|trial\s+period|discount|"
    r"enta|entha|yentha|dhara|kharcha|kharch)\b|कितना|कितने|कीमत|दाम|खर्च|पैसे|ఎంత|ధర|ఖర్చు|రేటు",
    _FLAGS,
)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def pricing_violation(text: str) -> str | None:
    """Return the offending fragment if the text reveals or hints at pricing."""
    t = _norm(text)
    m = _PRICE_RE.search(t) or _INDIAN_AMOUNT_RE.search(t)
    return m.group(0) if m else None


def asks_about_price(text: str) -> bool:
    return bool(_PRICE_QUESTION_RE.search(_norm(text)))


# --- 2. never claim to be human -------------------------------------------
_HUMAN_CLAIM_RE = re.compile(
    r"\bi(?:'m| am)\s+(?:a\s+)?(?:real\s+)?(?:human|person|man|woman|lady|guy)\b"
    r"|\bi(?:'m| am)\s+not\s+(?:an?\s+)?(?:ai|bot|robot|machine|computer|recording)\b"
    r"|\bnot\s+a\s+(?:bot|robot)\b|\breal\s+person\s+here\b"
    r"|main\s+(?:insaan|insan|asli)\b|मैं\s+इंसान|मैं\s+रोबोट\s+नहीं|nenu\s+manishi|నేను\s+మనిషి",
    _FLAGS,
)


def claims_human(text: str) -> bool:
    return bool(_HUMAN_CLAIM_RE.search(_norm(text)))


_ASKS_IF_AI_RE = re.compile(
    r"\b(?:are you|is this|r u|you are)\s+(?:an?\s+)?(?:ai|bot|robot|machine|computer|recorded|recording|real|human|person)\b"
    r"|\brobot\s+(?:hai|ho)\b|\b(?:ai|bot)\s+(?:hai|ho|aa|na)\b|kya\s+aap\s+(?:robot|insaan|ai)|రోబో|మనిషా|रोबोट|इंसान",
    _FLAGS,
)


def asks_if_ai(text: str) -> bool:
    return bool(_ASKS_IF_AI_RE.search(_norm(text)))


# --- 3. opt-out -------------------------------------------------------------
_OPT_OUT_RE = re.compile(
    r"^\s*(?:stop|unsubscribe|stop all|end|quit|cancel|remove)\s*[.!]*\s*$"
    r"|\b(?:don'?t|do not|never|stop)\s+(?:call|message|msg|text|contact|whatsapp|disturb|bother)(?:ing)?\b"
    r"|\bnot\s+interested\b|\bno\s+interest\b|\bremove\s+(?:my|this)\s+(?:number|no)\b|\bopt[- ]?out\b"
    r"|\bleave\s+me\s+alone\b|\bno\s+more\s+(?:calls|messages|msgs)\b|\bblock(?:ing)?\s+(?:you|this|your)\b|\bspam\b|\bdnd\b"
    r"|\b(?:call|phone|message|msg)\s+(?:mat|matt)\s+(?:karo|karna|kijiye|kariye|karein)\b"
    r"|\bband\s+(?:karo|kijiye|kariye|karein)\b|\bnahi\s+chahiye\b|\bnahin\s+chahiye\b|\binterest\s+nahi\b|\bmat\s+karo\b"
    r"|बंद\s*कर|मत\s*कर|नहीं\s*चाहिए|कॉल\s*मत|मैसेज\s*मत|रुचि\s*नहीं"
    r"|\bvaddu\b|\bvaddhu\b|\bcheyakandi\b|\bcheyyakandi\b|\bapandi\b|\bpampakandi\b|\binterest\s+ledu\b"
    r"|వద్దు|ఆపండి|చేయకండి|చేయొద్దు|పంపకండి|ఆసక్తి\s*లేదు",
    _FLAGS,
)


def is_opt_out(text: str) -> bool:
    return bool(_OPT_OUT_RE.search(_norm(text)))


# --- combined check ------------------------------------------------------------
def check_outbound(text: str) -> list[str]:
    """Problems with a line we are about to say or send. Empty list = safe."""
    problems = []
    frag = pricing_violation(text)
    if frag:
        problems.append(f"mentions pricing ({frag!r})")
    if claims_human(text):
        problems.append("claims to be human")
    return problems
