"""The insights dashboard: one self-contained HTML page (no CDN, no build step).

Served live by `serve` at /dashboard?token=DASHBOARD_TOKEN (refreshes every minute), or written
as a snapshot file by `python -m fieldos_sales dashboard --out insights.html`.
All prospect text is inserted with textContent, never as HTML.
"""
from __future__ import annotations

import json
from typing import Any


def render(data: dict[str, Any], live_url: str = "") -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (PAGE.replace("__DATA__", payload)
            .replace("__LIVE__", json.dumps(live_url).replace("</", "<\\/")))


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>FieldOS sales insights</title>
<style>
:root{
  color-scheme:light;
  --bg:#f6f5f2;--surface:#fcfcfb;--surface-2:#f0efec;--line:#e3e1db;
  --text:#0b0b0b;--text-2:#52514e;--muted:#7a7972;
  --accent:#2a78d6;--accent-soft:#cde2fb;
  --seq-1:#cde2fb;--seq-2:#9ec5f4;--seq-3:#5598e7;--seq-4:#2a78d6;--seq-5:#1c5cab;--seq-6:#0d366b;
  --good:#0ca30c;--warn:#fab219;--bad:#d03b3b;--amber:#c27c00;
  --shadow:0 1px 2px rgba(0,0,0,.05);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --bg:#121211;--surface:#1a1a19;--surface-2:#242422;--line:#33332f;
  --text:#f0efec;--text-2:#c3c2b7;--muted:#8f8e86;
  --accent:#3987e5;--accent-soft:#184f95;
  --seq-1:#1c2f47;--seq-2:#184f95;--seq-3:#256abf;--seq-4:#3987e5;--seq-5:#6da7ec;--seq-6:#b7d3f6;
  --shadow:none;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#121211;--surface:#1a1a19;--surface-2:#242422;--line:#33332f;
  --text:#f0efec;--text-2:#c3c2b7;--muted:#8f8e86;
  --accent:#3987e5;--accent-soft:#184f95;
  --seq-1:#1c2f47;--seq-2:#184f95;--seq-3:#256abf;--seq-4:#3987e5;--seq-5:#6da7ec;--seq-6:#b7d3f6;
  --shadow:none;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.wrap{max-width:1240px;margin:0 auto;padding:0 16px}
.bar{display:flex;align-items:center;gap:12px;min-height:56px;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:650;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:12.5px}
.spacer{flex:1}
nav a{color:var(--text-2);text-decoration:none;font-size:13px;margin-left:14px;white-space:nowrap}
nav a:hover{color:var(--text)}
button,select,input{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
button{cursor:pointer}
.banner{background:#fff4d6;color:#5c4200;border:1px solid #f0d58a;border-radius:10px;padding:10px 14px;margin:16px 0 0}
:root[data-theme="dark"] .banner{background:#3a2f12;color:#f5dc9a;border-color:#6b5520}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .banner{background:#3a2f12;color:#f5dc9a;border-color:#6b5520}}
section{margin:22px 0}
h2{font-size:15px;margin:0 0 4px;font-weight:650}
.lede{color:var(--text-2);margin:0 0 12px;font-size:13px}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);min-width:0}
.card h3{font-size:13px;margin:0 0 10px;font-weight:600;color:var(--text-2)}
.tile .v{font-size:26px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.tile .l{color:var(--text-2);font-size:12.5px}
.tile .h{color:var(--muted);font-size:11.5px;margin-top:2px}
.rows{display:flex;flex-direction:column;gap:7px}
.row{display:grid;grid-template-columns:minmax(90px,46%) 1fr 44px;align-items:center;gap:10px;font-size:13px}
.row .name{color:var(--text-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .num{text-align:right;font-variant-numeric:tabular-nums;color:var(--text)}
.track{height:14px;position:relative}
.fill{height:100%;background:var(--accent);border-radius:0 4px 4px 0;min-width:2px}
.empty{color:var(--muted);font-size:13px;padding:6px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:var(--text-2);border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}
td{border-bottom:1px solid var(--line);padding:7px 8px;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr.click{cursor:pointer}
tr.click:hover td{background:var(--surface-2)}
.scroll{overflow-x:auto}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line);background:var(--surface-2);white-space:nowrap}
.pill.good::before,.pill.bad::before,.pill.warn::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:1px}
.pill.good::before{background:var(--good)}.pill.bad::before{background:var(--bad)}.pill.warn::before{background:var(--warn)}
.heat{display:grid;gap:2px;font-size:11.5px}
.heat .c{height:28px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-variant-numeric:tabular-nums}
.heat .lbl{color:var(--muted);display:flex;align-items:center;justify-content:center}
.legend{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11.5px;margin-top:8px}
.legend i{display:inline-block;width:18px;height:10px;border-radius:2px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.filters input{flex:1;min-width:160px}
ul.plain{margin:0;padding-left:18px}ul.plain li{margin:4px 0}
.change{border-left:3px solid var(--accent);padding:6px 10px;margin:8px 0;background:var(--surface-2);border-radius:0 8px 8px 0}
.change .why{color:var(--text-2);font-size:12.5px}
#tip{position:fixed;pointer-events:none;z-index:20;background:var(--text);color:var(--bg);font-size:12px;padding:5px 8px;border-radius:6px;opacity:0;transition:opacity .08s;max-width:260px}
dialog{border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--text);padding:0;width:min(860px,calc(100vw - 32px));max-height:calc(100vh - 48px)}
dialog::backdrop{background:rgba(0,0,0,.45)}
.dlg-h{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface)}
.dlg-b{padding:14px 16px;display:grid;gap:14px;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}
@media (max-width:720px){.dlg-b{grid-template-columns:1fr}nav{display:none}}
.msg{padding:7px 10px;border-radius:10px;margin:6px 0;max-width:92%;white-space:pre-wrap;word-wrap:break-word}
.msg.ai{background:var(--surface-2)}
.msg.p{background:var(--accent-soft);margin-left:auto}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:13px}
.kv dt{color:var(--muted)}.kv dd{margin:0}
footer{color:var(--muted);font-size:12px;padding:24px 0 40px}
</style>
</head>
<body>
<header><div class="wrap bar">
  <h1>FieldOS sales insights</h1><span class="sub" id="gen"></span>
  <span class="spacer"></span>
  <nav><a href="#next">Next actions</a><a href="#funnel">Funnel</a><a href="#calls">Calls</a><a href="#voice">What they say</a><a href="#learn">What to change</a><a href="#convos">Conversations</a><a href="#spend">AI spend</a></nav>
  <button id="theme" title="Switch light and dark">Theme</button>
</div></header>
<main class="wrap">
  <div id="sample" class="banner" hidden><b>Sample data.</b> These firms and conversations are made up so you can see how the dashboard works. Run <code>python -m fieldos_sales dashboard</code> without <code>--sample</code> for your real numbers.</div>

  <section><div class="grid g4" id="tiles"></div></section>

  <section id="next">
    <h2>What to do next</h2>
    <p class="lede">Walkthroughs to confirm, callbacks, details to send and chats waiting for a person. Newest first.</p>
    <div class="card scroll"><table id="actions"></table></div>
  </section>

  <section id="funnel" class="grid g2">
    <div class="card"><h3>Funnel: from the target list to a booked walkthrough</h3><div class="rows" id="funnelRows"></div></div>
    <div class="card"><h3>Where interest comes from (by segment)</h3><div class="scroll"><table id="seg"></table></div>
      <h3 style="margin-top:16px">By priority</h3><div class="scroll"><table id="prio"></table></div></div>
  </section>

  <section id="calls">
    <h2>Phone calls</h2>
    <p class="lede">How long people stay, where they hang up, and how fast the agent answers. A reply delay under 1.5 s feels natural; over 2.5 s people say "hello?" and hang up.</p>
    <div class="grid g4" id="callTiles"></div>
    <div class="grid g3" style="margin-top:12px">
      <div class="card"><h3>When callers hung up (after how many of their own turns)</h3><div class="rows" id="hangup"></div></div>
      <div class="card"><h3>How calls ended</h3><div class="rows" id="callOut"></div></div>
      <div class="card"><h3>Language spoken</h3><div class="scroll"><table id="langs"></table></div></div>
    </div>
    <div class="card" style="margin-top:12px"><h3>Best time to call: share of dialled calls answered (IST)</h3><div class="scroll"><div class="heat" id="heat"></div></div>
      <div class="legend" id="heatLegend"></div></div>
  </section>

  <section id="wa">
    <h2>WhatsApp</h2>
    <div class="grid g4" id="waTiles"></div>
  </section>

  <section id="voice">
    <h2>What prospects say</h2>
    <p class="lede">From the AI summary of each conversation (<span id="nsum">0</span> summarised). Use these to sharpen the pitch and the knowledge base.</p>
    <div class="grid g3">
      <div class="card"><h3>Objections</h3><div class="rows" id="obj"></div></div>
      <div class="card"><h3>Problems they mentioned</h3><div class="rows" id="pains"></div></div>
      <div class="card"><h3>How they track site work today</h3><div class="rows" id="method"></div></div>
      <div class="card"><h3>Why conversations ended</h3><div class="rows" id="ended"></div></div>
      <div class="card"><h3>Interest</h3><div class="rows" id="interest"></div><h3 style="margin-top:14px">Other apps they named</h3><div class="rows" id="comp"></div></div>
      <div class="card"><h3>Agent mistakes spotted</h3><div class="rows" id="mist"></div></div>
    </div>
  </section>

  <section id="learn">
    <h2>What to change</h2>
    <div class="grid g2">
      <div class="card" id="learnCard"></div>
      <div class="card"><h3>Latest coaching tips (one per conversation)</h3><ul class="plain" id="tips"></ul></div>
    </div>
  </section>

  <section id="convos">
    <h2>Conversations</h2>
    <p class="lede">Click one to read the transcript and its summary.</p>
    <div class="filters">
      <select id="fCh"><option value="">Calls and WhatsApp</option><option value="call">Calls</option><option value="whatsapp">WhatsApp</option></select>
      <select id="fOut"><option value="">Any outcome</option></select>
      <select id="fInt"><option value="">Any interest</option><option>hot</option><option>warm</option><option>cold</option><option>none</option></select>
      <input id="fQ" type="search" placeholder="Search firm, words in the transcript">
    </div>
    <div class="card scroll"><table id="convTable"></table></div>
  </section>

  <section id="spend" class="grid g2">
    <div class="card"><h3>AI spend by task (US$)</h3><div class="rows" id="spendRows"></div></div>
    <div class="card"><h3>AI spend per day, last 14 days (US$)</h3><div class="rows" id="spendDays"></div></div>
  </section>
  <footer>Data stays on this machine (data/sales.db). Prospect phone numbers and transcripts are personal data: don't share this page.</footer>
</main>
<div id="tip" role="tooltip"></div>
<dialog id="dlg"><div class="dlg-h"><b id="dTitle"></b><span class="sub" id="dSub"></span><span class="spacer"></span><button id="dClose">Close</button></div>
<div class="dlg-b"><div id="dTx"></div><div id="dIn"></div></div></dialog>

<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
const LIVE = __LIVE__;
let D = JSON.parse(document.getElementById("data").textContent);
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k === "style") n.style.cssText = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid instanceof Node ? kid : String(kid));
  return n;
};
const fmt = (v, unit = "") => v === null || v === undefined ? "–" : `${v}${unit}`;
const LABEL = {demo_booked:"Walkthrough booked", callback_later:"Call back later", send_info:"Send details", handover:"Wants a person",
  not_now:"Not now", opted_out:"Opted out", ended:"Hung up", chatting:"Chatting",
  no_time:"No time", not_decision_maker:"Not the decision maker", already_using_app:"Already uses an app", price_concern:"Worried about cost",
  no_need:"No need", send_details_first:"Send details first", bad_timing:"Bad timing", trust_or_data_worry:"Trust or data worry", language:"Language", other:"Other",
  booked_demo:"Booked walkthrough", callback:"Callback", wants_info:"Wants info", not_interested:"Not interested", hung_up_early:"Hung up early",
  gatekeeper:"Gatekeeper", wrong_number:"Wrong number", technical_problem:"Technical problem", hot:"Hot", warm:"Warm", cold:"Cold", none:"None",
  call:"Call", whatsapp:"WhatsApp"};
const L = k => LABEL[k] || (k ? String(k).replace(/_/g, " ") : "–");
const GOOD = new Set(["demo_booked","callback_later","send_info","handover","hot"]);
const BAD = new Set(["opted_out","ended","not_now","cold","none"]);
const pill = k => el("span", {class: "pill " + (GOOD.has(k) ? "good" : BAD.has(k) ? "bad" : "")}, L(k));
const when = iso => { if (!iso) return "–"; const d = new Date(iso);
  return d.toLocaleString("en-IN", {timeZone:"Asia/Kolkata", day:"numeric", month:"short", hour:"numeric", minute:"2-digit"}); };

const tip = $("tip");
function hover(node, text) {
  node.addEventListener("mousemove", e => { tip.textContent = text; tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 12, innerWidth - 270) + "px"; tip.style.top = (e.clientY + 14) + "px"; });
  node.addEventListener("mouseleave", () => tip.style.opacity = 0);
}

function bars(id, items, {label = x => L(x.name), value = x => x.n, unit = "", detail} = {}) {
  const box = $(id); box.replaceChildren();
  if (!items || !items.length) { box.append(el("div", {class: "empty"}, "No data yet")); return; }
  const max = Math.max(...items.map(value), 0) || 1;
  for (const it of items) {
    const v = value(it), f = el("div", {class: "fill", style: `width:${Math.max(0, v) / max * 100}%`});
    const row = el("div", {class: "row"}, el("div", {class: "name", title: label(it)}, label(it)), el("div", {class: "track"}, f), el("div", {class: "num"}, fmt(v, unit)));
    hover(row, detail ? detail(it) : `${label(it)}: ${fmt(v, unit)}`);
    box.append(row);
  }
}

function tiles(id, list) {
  $(id).replaceChildren(...list.map(([v, l, h]) => el("div", {class: "card tile"}, el("div", {class: "v"}, v), el("div", {class: "l"}, l), h ? el("div", {class: "h"}, h) : null)));
}

function table(id, cols, rows, onclick) {
  const t = $(id); t.replaceChildren();
  t.append(el("thead", {}, el("tr", {}, cols.map(c => el("th", {class: c.n ? "n" : ""}, c.h)))));
  const body = el("tbody");
  if (!rows.length) body.append(el("tr", {}, el("td", {colspan: cols.length, class: "empty"}, "Nothing yet")));
  for (const r of rows) {
    const tr = el("tr", onclick ? {class: "click", onclick: () => onclick(r)} : {}, cols.map(c => { const v = c.v(r); return el("td", {class: c.n ? "n" : ""}, v instanceof Node ? v : fmt(v)); }));
    body.append(tr);
  }
  t.append(body);
}

function heat() {
  const box = $("heat"); box.replaceChildren();
  const days = ["Mon","Tue","Wed","Thu","Fri","Sat"], hours = [];
  for (let h = 9; h <= 19; h++) hours.push(h);
  box.style.gridTemplateColumns = `44px repeat(${hours.length}, minmax(34px,1fr))`;
  const cell = {}; for (const b of D.best_times) cell[b.day + b.hour] = b;
  const used = hours.filter(h => days.some(d => cell[d + h]));
  const show = used.length ? hours.filter(h => h >= Math.min(...used) && h <= Math.max(...used)) : hours.slice(1, 10);
  box.style.gridTemplateColumns = `44px repeat(${show.length}, minmax(34px,1fr))`;
  box.append(el("div"));
  for (const h of show) box.append(el("div", {class: "lbl"}, `${h % 12 || 12}${h < 12 ? "am" : "pm"}`));
  const steps = ["--seq-1","--seq-2","--seq-3","--seq-4","--seq-5","--seq-6"];
  for (const d of days) {
    box.append(el("div", {class: "lbl"}, d));
    for (const h of show) {
      const b = cell[d + h];
      if (!b) { box.append(el("div", {class: "c", style: "background:var(--surface-2)"})); continue; }
      const i = b.rate === null ? 0 : Math.min(5, Math.floor(b.rate / 20));
      const c = el("div", {class: "c", style: `background:var(${steps[i]});color:${i >= 3 ? "#fff" : "var(--text)"};opacity:${b.dialled >= 3 ? 1 : .35}`}, b.dialled >= 3 ? `${Math.round(b.rate)}%` : "");
      hover(c, `${d} ${h}:00–${h + 1}:00 · ${b.answered} of ${b.dialled} answered${b.dialled < 3 ? " (too few calls to judge)" : ""}`);
      box.append(c);
    }
  }
  $("heatLegend").replaceChildren("0%", ...steps.map(s => el("i", {style: `background:var(${s})`})), "100% answered · grey = no calls · faded = fewer than 3 calls");
}

function learnings() {
  const box = $("learnCard"); box.replaceChildren();
  const r = D.learnings;
  if (!r) { box.append(el("h3", {}, "AI review of the campaign"), el("p", {class: "empty"}, "Not run yet. After a few conversations run: python -m fieldos_sales insights --learn")); return; }
  box.append(el("h3", {}, `AI review of the campaign · ${when(r.at)}`), el("p", {style: "margin:0 0 8px;font-weight:600"}, r.headline));
  for (const c of r.changes || []) box.append(el("div", {class: "change"}, el("div", {}, el("span", {class: "pill"}, L(c.area)), " ", c.change), el("div", {class: "why"}, c.why)));
  const two = el("div", {class: "grid g2", style: "margin-top:10px"});
  two.append(el("div", {}, el("h3", {}, "Working"), el("ul", {class: "plain"}, (r.what_works || []).map(x => el("li", {}, x)))),
             el("div", {}, el("h3", {}, "Hurting"), el("ul", {class: "plain"}, (r.what_hurts || []).map(x => el("li", {}, x)))));
  box.append(two);
}

function openConvo(c) {
  $("dTitle").textContent = c.firm; $("dSub").textContent = `${L(c.channel)} · ${when(c.at)}${c.seconds ? ` · ${Math.round(c.seconds)} s` : ""}`;
  const tx = $("dTx"); tx.replaceChildren(el("h3", {}, "Transcript"));
  for (const line of (c.transcript || "").split("\n")) {
    if (!line.trim()) continue;
    const ai = line.startsWith("AI:");
    tx.append(el("div", {class: "msg " + (ai ? "ai" : "p")}, line.replace(/^(AI|Prospect):\s*/, "")));
  }
  const s = c.insight || {}, box = $("dIn"); box.replaceChildren(el("h3", {}, "Summary"));
  if (!s.summary) { box.append(el("p", {class: "empty"}, "Not summarised yet: run python -m fieldos_sales insights --summarise")); }
  else {
    box.append(el("p", {style: "margin-top:0"}, s.summary));
    const kv = el("dl", {class: "kv"});
    const add = (k, v) => { if (v && (!Array.isArray(v) || v.length)) kv.append(el("dt", {}, k), el("dd", {}, Array.isArray(v) ? v.map(L).join(", ") : v instanceof Node ? v : L(v))); };
    add("Outcome", pill(c.outcome)); add("Interest", pill(s.interest)); add("Sentiment", s.sentiment); add("Decision maker", s.decision_maker);
    add("Today they use", s.current_method); add("Problems", s.pains); add("Objections", s.objections); add("Other apps", s.competitors);
    add("Why it ended", s.why_ended); add("Next step", s.next_step); add("Agent mistakes", s.agent_mistakes); add("Coaching tip", s.coaching_tip);
    if (c.latency_ms) add("Reply delay", `${c.latency_ms} ms average`);
    box.append(kv);
  }
  $("dlg").showModal();
}
$("dClose").onclick = () => $("dlg").close();

function convos() {
  const ch = $("fCh").value, out = $("fOut").value, it = $("fInt").value, q = $("fQ").value.trim().toLowerCase();
  const rows = D.conversations.filter(c => (!ch || c.channel === ch) && (!out || c.outcome === out) && (!it || (c.insight || {}).interest === it)
    && (!q || (c.firm + " " + (c.transcript || "") + " " + ((c.insight || {}).summary || "")).toLowerCase().includes(q)));
  table("convTable", [
    {h: "When", v: c => when(c.at)}, {h: "Firm", v: c => c.firm}, {h: "Channel", v: c => L(c.channel)},
    {h: "Outcome", v: c => pill(c.outcome)}, {h: "Interest", v: c => (c.insight || {}).interest ? pill(c.insight.interest) : "–"},
    {h: "Length", n: 1, v: c => c.seconds ? `${Math.round(c.seconds)} s` : c.channel === "whatsapp" ? `${c.turns} msgs` : "–"},
    {h: "Summary", v: c => ((c.insight || {}).summary || "").slice(0, 120)},
  ], rows, openConvo);
}
["fCh","fOut","fInt"].forEach(id => $(id).onchange = convos); $("fQ").oninput = convos;

function draw() {
  const h = D.headline, c = D.calls, w = D.whatsapp, v = D.voice;
  $("gen").textContent = `Updated ${when(D.generated_at)}${LIVE ? " · refreshes every minute" : " · snapshot"}`;
  $("sample").hidden = !D.sample;
  tiles("tiles", [
    [h.contacted, "Firms contacted"], [h.conversations, "Real conversations", "3+ replies from them"],
    [h.positive, "Positive next steps", "walkthrough, callback, details, person"], [h.demos, "Walkthroughs booked"],
    [fmt(h.answer_rate, "%"), "Calls answered"], [fmt(h.reply_rate, "%"), "WhatsApp reply rate"], [h.opted_out, "Opted out", "never contacted again"],
  ]);
  const acts = D.actions.map(a => ({...a, src: "action"})).concat(D.hot.filter(x => !D.actions.some(a => a.prospect_id === x.prospect_id)).map(x => ({...x, kind: "hot", src: "hot", note: x.next_step})));
  table("actions", [
    {h: "What", v: a => pill(a.kind)}, {h: "Firm", v: a => a.firm}, {h: "Channel", v: a => L(a.channel)},
    {h: "When they asked for", v: a => a.when || "–"}, {h: "Note", v: a => a.note || "–"}, {h: "Logged", v: a => a.at ? when(a.at) : "–"},
  ], acts, a => { const cv = D.conversations.find(x => x.prospect_id === a.prospect_id && x.channel === a.channel); if (cv) openConvo(cv); });
  const top = D.funnel[0].n || 1;
  bars("funnelRows", D.funnel, {label: x => x.stage, detail: x => `${x.stage}: ${x.n} (${Math.round(x.n / top * 100)}% of imported)`});
  const segCols = [{h: "", v: r => r.name}, {h: "Contacted", n: 1, v: r => r.contacted}, {h: "Answered", n: 1, v: r => r.answered},
    {h: "Positive", n: 1, v: r => r.positive}, {h: "Rate", n: 1, v: r => fmt(r.positive_rate, "%")}, {h: "Walkthroughs", n: 1, v: r => r.demos}];
  table("seg", segCols, D.by_segment); table("prio", segCols, D.by_priority);
  tiles("callTiles", [
    [c.dialled, "Calls dialled"], [fmt(c.avg_seconds, " s"), "Average call length"],
    [fmt(c.avg_latency_ms, " ms"), "Average reply delay", c.avg_latency_ms > 2500 ? "too slow: see CALL_PLAYBOOK.md" : "target under 1,500 ms"],
    [fmt(c.avg_prospect_turns), "Prospect turns per call"], [fmt(c.price_question_rate, "%"), "Calls with a price question", "answered with the proposal line"],
    [fmt(c.barge_ins_per_call), "Interruptions per call"],
  ]);
  bars("hangup", c.hangup_after_turns, {label: x => x.turns === "0" ? "0 (said nothing)" : `${x.turns} turn${x.turns === "1" ? "" : "s"}`, detail: x => `${x.n} callers hung up after ${x.turns} of their turns`});
  bars("callOut", Object.entries(c.outcomes).map(([name, n]) => ({name, n})).sort((a, b) => b.n - a.n));
  table("langs", [{h: "", v: r => r.name}, {h: "Calls", n: 1, v: r => r.calls}, {h: "Positive", n: 1, v: r => r.positive}, {h: "Rate", n: 1, v: r => fmt(r.positive_rate, "%")}], D.languages);
  heat();
  tiles("waTiles", [[w.openers_sent, "Openers sent"], [fmt(w.reply_rate, "%"), "Replied"], [w.followups_sent, "Follow-ups sent"],
    [w.with_a_person, "Chats handed to you"], [w.followups_due, "Follow-ups due", "run wa-followups"], [w.queued, "Waiting to send"], [w.blocked, "Blocked by the checks"]]);
  $("nsum").textContent = v.summarised;
  bars("obj", v.objections); bars("pains", v.pains, {label: x => x.name}); bars("method", v.current_method, {label: x => x.name});
  bars("ended", v.why_ended); bars("interest", v.interest); bars("comp", v.competitors, {label: x => x.name}); bars("mist", v.agent_mistakes, {label: x => x.name});
  $("tips").replaceChildren(...(v.coaching_tips.length ? v.coaching_tips.slice().reverse().map(t => el("li", {}, t)) : [el("li", {class: "empty"}, "None yet")]));
  learnings();
  const outs = [...new Set(D.conversations.map(x => x.outcome))].sort(), sel = $("fOut"), keep = sel.value;
  sel.replaceChildren(el("option", {value: ""}, "Any outcome"), ...outs.map(o => el("option", {value: o}, L(o)))); sel.value = keep;
  convos();
  bars("spendRows", D.spend.by_purpose, {label: x => L(x.name), value: x => x.usd, detail: x => `${L(x.name)}: $${x.usd} over ${x.calls} AI calls`});
  bars("spendDays", D.spend.by_day, {label: x => x.day, value: x => x.usd});
}

const root = document.documentElement;
try { const t = localStorage.getItem("fos-theme"); if (t) root.dataset.theme = t; } catch (e) {}
$("theme").onclick = () => { const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark"; try { localStorage.setItem("fos-theme", root.dataset.theme); } catch (e) {} };

draw();
if (LIVE) setInterval(async () => {
  if ($("dlg").open) return;
  try { const r = await fetch(LIVE, {cache: "no-store"}); if (r.ok) { D = await r.json(); draw(); } } catch (e) {}
}, 60000);
</script>
</body>
</html>
"""
