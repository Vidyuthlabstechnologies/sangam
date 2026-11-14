import httpx
import openpyxl

from fieldos_sales.llm import OfflineLLM
from fieldos_sales.pitch import write_pitch
from fieldos_sales.prospects import import_xlsx
from fieldos_sales.research import fetch_site, html_to_text, research_prospect
from fieldos_sales.store import Store

HOME = """<html><head><title>Demo Builders</title><meta name="description" content="Villas in Kokapet">
<script>var x = 1;</script></head><body><h1>Premium villas</h1>
<a href="/about-us">About</a><a href="/projects/ongoing">Projects</a><a href="https://other.example/x">x</a>
<a href="/careers">Careers</a></body></html>"""


def site_transport(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /projects/")
    pages = {"/": HOME, "/about-us": "<p>Since 2009, 14 projects delivered in Hyderabad.</p>"}
    if path in pages:
        return httpx.Response(200, text=pages[path], headers={"content-type": "text/html"})
    return httpx.Response(404)


def test_html_to_text_drops_scripts():
    title, text, links = html_to_text(HOME)
    assert title == "Demo Builders"
    assert "var x" not in text and "Villas in Kokapet" in text
    assert "/about-us" in links


def test_fetch_site_follows_relevant_pages_and_respects_robots():
    client = httpx.Client(transport=httpx.MockTransport(site_transport))
    pages = fetch_site("https://demo.example", client)
    urls = [p["url"] for p in pages]
    assert urls[0].startswith("https://demo.example")
    assert "https://demo.example/about-us" in urls
    assert not any("projects" in u for u in urls)  # disallowed by robots.txt
    assert not any("other.example" in u or "careers" in u for u in urls)


def test_research_without_website_is_low_confidence():
    llm = OfflineLLM(lambda *a: {"summary": "x", "confidence": "high"})
    profile = research_prospect({"firm": "No Site Co", "segment": "Contractor"}, llm, pages=[])
    assert profile["confidence"] == "low" and profile["sources"] == []
    assert "untrusted data" in llm.calls[0]["system"][0]["text"]


def test_pitch_retries_then_falls_back_when_model_leaks_price():
    bad = {"call_brief": "Tell them it's ₹999.", "whatsapp_opener": "Free trial!"}
    llm = OfflineLLM(lambda *a: bad)
    out = write_pitch({"firm": "Demo Builders"}, {"summary": "x"}, llm)
    assert len(llm.calls) == 2
    assert "Demo Builders" in out["whatsapp_opener"] and "₹" not in out["whatsapp_opener"]


def test_import_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Firms"
    ws.append(["#", "Firm", "Segment", "Size (rough)", "Priority for FieldOS", "Suggested plan", "Website",
               "Public phone (from website)", "Public email (from website)"])
    ws.append([7, "Demo Builders", "Developer", "Mid", "A - best fit", "Business", "https://demo.example",
               "+91 91000 50801, 040 2341 8080", "info@demo.example"])
    ws.append([8, None, None])
    path = tmp_path / "firms.xlsx"
    wb.save(path)
    st = Store(":memory:")
    assert import_xlsx(st, path) == 1
    p = st.prospect(7)
    assert p["phones"] == ["+919100050801", "+914023418080"]
    assert st.prospect_by_phone("+914023418080")["firm"] == "Demo Builders"
