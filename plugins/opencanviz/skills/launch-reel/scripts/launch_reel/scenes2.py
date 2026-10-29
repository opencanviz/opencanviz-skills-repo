"""Scenes added with the style packs and story structures. Same contract as `scenes.py`: each
scene owns its nodes (ids prefixed with its slot), opens with `cut()`, fits its copy and paces
itself from it.

  dashboard      a product dashboard: KPI cards count up, a bar chart grows, a note pops
  terminal       a terminal window: commands type out, output scrolls in, a success line
  browser        a browser: the URL types, the landing page loads and scrolls
  split          before and after side by side: the old way struck out, the new way checked
  stat           one big number counting up, with its label
  kanban         a board with three columns; the cursor drags a card to done
  notifications  a headline and a stack of alerts sliding in one after another
  map            a dotted world map with pins dropping on cities
  pricing        a plan card: the price counts up, features tick in, the button is pressed
  logo_grid      a grid of integration marks popping in a wave under a headline
  compare        a feature table, the product's column lit up and checked down
  problem        the pain: cards pile up, shake and fall away
  countdown      "3 reasons": big numerals counting down, a reason with each
  feature_flash  rapid fire: one icon and one word per beat, hard cuts on alternating colour

Counting numbers are pre-set text frames flipped in 1ms steps (`Reel.count`), since a text
node cannot tween its digits.
"""
from __future__ import annotations

import math
import re

from ._metrics import text_width as tw
from .builder import C0, _mix
from .scenes import SCENES, Ctx, _drift, _icon_color, fit, read_ms, type_ms, wrap


# ---------------- helpers ----------------
_NUM = re.compile(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$")


def count_frames(c: Ctx, id: str, value: str, x, y, w, h, size, n=14, **kw) -> list[str]:
    """Text nodes for a number counting up to `value` ("$12,480", "98%", "3.2x"). A value with
    no number in it gets one frame."""
    r = c.r
    value = str(value or "").strip()
    m = _NUM.match(value)
    texts = [value]
    if m:
        pre, num, post = m.groups()
        dec = len(num.split(".")[1]) if "." in num else 0
        commas = "," in num
        target = float(num.replace(",", ""))
        texts = []
        for j in range(n):
            v = target * j / (n - 1)
            s = f"{v:,.{dec}f}" if commas else f"{v:.{dec}f}"
            texts.append(pre + s + post)
        texts[-1] = value
    ids = []
    for j, t in enumerate(texts):
        r.text(f"{id}_{j}", x, y, w, h, t, size, **kw)
        ids.append(f"{id}_{j}")
    return ids


def _group(c: Ctx, id, x, y, w, h, z):
    """A clipping group used as a movable card: children in local coordinates move with it."""
    return c.r.mask(id, x, y, w, h, z)


def _lines(c: Ctx, k: str, text: str, cx: float, cy: float, size: float, maxw: float, max_lines=2,
           gap=1.12):
    """A headline wrapped to `max_lines` and set as rising lines. Returns (masks, kids)."""
    r = c.r
    ls = wrap(text, size, maxw, 700, max_lines) or [""]
    lh = size * gap * max(1.0, r.style.display_scale ** 0.5)
    y0 = cy - (len(ls) - 1) * lh / 2
    masks, kids = [], []
    for i, l in enumerate(ls):
        masks.append(r.rise_line(f"{k}{i}", cx, y0 + i * lh, l, size))
        kids.append(f"{k}{i}")
    return masks, kids, ls


def _cursor(c: Ctx, k: str, x, y):
    c.r.icon(k, "ph:cursor-fill", x, y, 34, 60, color=c.pal.ink)
    return k


def _press(c: Ctx, ids: list[str], note="press"):
    r = c.r
    r.step(110, "ease-out", [dict(id=i, scaleX=0.9, scaleY=0.9) for i in ids], note=note)
    r.step(220, "back", [dict(id=i, scaleX=1, scaleY=1) for i in ids], note="release")


# ---------------- dashboard ----------------
def dashboard(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    PX, PY, PW, PH = -540, -310, 1080, 620
    r.node(k + "pn", "rect", PX, PY, PW, PH, 24, fill=pal.panel, cornerRadius=20,
           dropShadow=dict(dx=0, dy=14, color="rgba(0,0,0,0.10)", radius=36))
    r.node(k + "rail", "rect", PX, PY, 210, PH, 25, fill=pal.soft, cornerRadius=20)
    letter = (c.brand.get("logo_letter") or c.brand["name"][:1]).upper()[:2]
    r.node(k + "lg", "rect", PX + 24, PY + 26, 36, 36, 26, fill=pal.ink, cornerRadius=9, label=letter,
           labelColor=pal.on_ink, labelFontSize=18, labelFontWeight=800, fontSize=18,
           fontFamily=r.style.display, labelFontFamily=r.style.display)
    r.text(k + "lgt", PX + 70, PY + 26, 130, 36, fit(c.brand["name"], 17, 130, 700)[0], 17, weight=700, z=26)
    static = [k + "pn", k + "rail", k + "lg", k + "lgt"]
    nav = (p.get("nav") or ["Overview", "Reports", "Customers", "Settings"])[:5]
    icons = ["ph:squares-four-bold", "ph:chart-bar-bold", "ph:users-bold", "ph:gear-bold", "ph:bell-bold"]
    for i, lbl in enumerate(nav):
        y = PY + 96 + i * 46
        if i == 0:
            r.node(k + "navhl", "rect", PX + 14, y - 4, 182, 40, 25.5, fill=pal.panel, cornerRadius=10)
            static.append(k + "navhl")
        r.icon(f"{k}nvi{i}", icons[i], PX + 28, y + 6, 20, 26, color=pal.ink if i == 0 else pal.grey)
        r.text(f"{k}nvt{i}", PX + 58, y - 4, 140, 40, fit(lbl, 16, 130, 500)[0], 16,
               color=pal.ink if i == 0 else pal.grey, weight=600 if i == 0 else 500, z=26)
        static += [f"{k}nvi{i}", f"{k}nvt{i}"]
    CX = PX + 240
    CW = PW - 240 - 36
    r.text(k + "tt", CX, PY + 24, CW, 44, fit(p.get("title") or "Overview", 26, CW - 200, 700)[0], 26,
           weight=700, z=26)
    static.append(k + "tt")
    kpis = [x for x in (p.get("kpis") or []) if x.get("value")][:3] or [{"label": "Total", "value": "1,284"}]
    n = len(kpis)
    cw = (CW - 20 * (n - 1)) / n
    frames = []
    for i, kp in enumerate(kpis):
        x = CX + i * (cw + 20)
        r.node(f"{k}kc{i}", "rect", x, PY + 86, cw, 124, 25, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
               cornerRadius=14)
        r.text(f"{k}kl{i}", x + 20, PY + 98, cw - 40, 30, fit(kp.get("label", ""), 16, cw - 40, 500)[0], 16,
               color=pal.grey, weight=500, z=26)
        val, vs = fit(kp["value"], 40, cw - 40, 700)
        frames.append(count_frames(c, f"{k}kv{i}", val, x + 20, PY + 132, cw - 40, 56, vs, weight=700, z=26,
                                   role="display"))
        dl = kp.get("delta")
        if dl:
            dt = fit(str(dl), 14, 90, 600)[0]
            dw = tw(dt, 14, 600) + 20
            r.node(f"{k}kd{i}", "rect", x + cw - 20 - dw, PY + 100, dw, 26, 26, fill=_mix(pal.good, pal.panel, 0.85),
                   cornerRadius=13)
            r.text(f"{k}kdt{i}", x + cw - 20 - dw + 10, PY + 100, dw, 26, dt, 14, color=pal.good, weight=600, z=27)
            static += [f"{k}kd{i}", f"{k}kdt{i}"]
        static += [f"{k}kc{i}", f"{k}kl{i}", frames[-1][0]]
    # chart
    r.text(k + "ct", CX, PY + 232, CW, 30, fit(p.get("chart_title") or "Last 12 weeks", 18, CW, 600)[0], 18,
           weight=600, z=26)
    static.append(k + "ct")
    base, top = PY + PH - 44, PY + 290
    for j in range(4):
        y = top + j * (base - top) / 3
        r.node(f"{k}gl{j}", "rect", CX, y, CW, 1.2, 25, fill=pal.line)
        static.append(f"{k}gl{j}")
    hs = [0.32, 0.4, 0.36, 0.48, 0.52, 0.5, 0.61, 0.66, 0.72, 0.7, 0.84, 0.97]
    slot = CW / len(hs)
    bw = slot * 0.56
    bars = []
    for j, hh in enumerate(hs):
        x = CX + j * slot + (slot - bw) / 2
        last = j == len(hs) - 1
        r.node(f"{k}br{j}", "rect", x, base, bw, 0, 26, fill=pal.accents[0] if last else _mix(pal.accents[0], pal.panel, 0.6),
               cornerRadius=6)
        bars.append((f"{k}br{j}", hh * (base - top)))
    note = fit(p.get("chart_note") or "", 16, 260, 700)[0]
    if note:
        nw = tw(note, 16, 700) + 32
        bx = CX + (len(hs) - 1) * slot + slot / 2
        r.node(k + "nt", "rect", bx - nw + 20, base - bars[-1][1] - 54, nw, 38, 28, fill=pal.ink, cornerRadius=19,
               scaleX=0.6, scaleY=0.6, label=note, labelColor=pal.on_ink, labelFontSize=16, labelFontWeight=700,
               fontSize=16, fontWeight=700, fontFamily=r.style.body, labelFontFamily=r.style.body)

    r.cut(static, bg=pal.field(p.get("bg") or "accent1"), note="cut dashboard",
          camera={"c": {"x": 0, "y": 0, "zoom": 0.98}, "e": {"x": 60, "y": 40, "zoom": 1.07}, "d": 7000})
    r.hold(350)
    r.count(frames, 1100)
    r.appear(*[b for b, _ in bars], note="bars on")
    r.step(800, "ease-out", [dict(id=b, h=h, y=base - h) for b, h in bars],
           delays={b: j * 45 for j, (b, _) in enumerate(bars)}, note="bars grow")
    if note:
        r.appear(k + "nt", note="note on")
        r.step(380, "back", [dict(id=k + "nt", scaleX=1, scaleY=1)], note="note pop")
    r.hold(read_ms(note, *[x.get("label", "") for x in kpis], lo=1300))


# ---------------- terminal ----------------
TERM_BG, TERM_BAR, TERM_TXT, TERM_DIM = "#0f1218", "#1b2029", "#e6e9ef", "#8b95a5"


def _mono_fit(text: str, size: float, maxw: float) -> str:
    text = " ".join(str(text or "").split())
    while text and tw(text, size, face="mono") > maxw:
        text = text[:-2] + "…"
    return text


def terminal(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    WX, WY, WW, WH = -500, -290, 1000, 580
    r.node(k + "win", "rect", WX, WY, WW, WH, 24, fill=TERM_BG, cornerRadius=16,
           dropShadow=dict(dx=0, dy=20, color="rgba(0,0,0,0.25)", radius=40))
    r.node(k + "bar", "rect", WX, WY, WW, 46, 25, fill=TERM_BAR, cornerRadius=16)
    r.node(k + "bar2", "rect", WX, WY + 30, WW, 16, 25, fill=TERM_BAR)
    shell = [k + "win", k + "bar", k + "bar2"]
    for j, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        r.node(f"{k}dot{j}", "circle", WX + 20 + j * 22, WY + 17, 13, 13, 26, fill=col)
        shell.append(f"{k}dot{j}")
    title = fit(p.get("title") or "~/" + re.sub(r"[^a-z0-9]+", "-", c.brand["name"].lower()).strip("-"), 15, 400,
                500)[0]
    r.text(k + "ttl", WX, WY, WW, 46, title, 15, color=TERM_DIM, weight=500, align="center", z=26)
    shell.append(k + "ttl")
    S, LH = 21, 36
    X0, Y = WX + 32, WY + 70
    maxw = WW - 64 - 30
    beats = []
    cmds = [x for x in (p.get("commands") or []) if x.get("cmd")][:2] or [{"cmd": "npm install", "output": []}]
    row = 0
    for i, cm in enumerate(cmds):
        y = Y + row * LH
        r.text(f"{k}ps{i}", X0, y, 30, LH, "$", S, color=pal.accents[0], weight=700, z=27, role="mono")
        cmd = _mono_fit(cm["cmd"], S, maxw - 30)
        r.text(f"{k}cm{i}", X0 + 28, y, maxw, LH, cmd, S, color=TERM_TXT, weight=500, z=27, role="mono",
               typeProgress=0)
        beats.append(("cmd", f"{k}ps{i}", f"{k}cm{i}", cmd))
        row += 1
        for j, o in enumerate((cm.get("output") or [])[:4]):
            o = _mono_fit(o, S - 2, maxw)
            good = o.startswith(("✓", "✔", "+", "Done", "done", "Success"))
            r.text(f"{k}o{i}_{j}", X0, Y + row * LH, maxw, LH, o, S - 2, color=pal.good if good else TERM_DIM,
                   weight=500, z=27, role="mono")
            beats.append(("out", f"{k}o{i}_{j}"))
            row += 1
        row += 0.4
    done = p.get("done")
    if done:
        y = Y + row * LH + 6
        r.icon(k + "dn_i", "ph:check-circle-fill", X0, y + 6, 26, 27, color="#3ecf7a", scaleX=0.5, scaleY=0.5)
        r.text(k + "dn_t", X0 + 38, y, maxw - 40, LH + 4, _mono_fit(done, S, maxw - 40), S, color=TERM_TXT,
               weight=700, z=27, role="mono")
    zoom_y = min(120, max(0, (row * LH) - 300))
    r.cut(shell, bg=pal.field(p.get("bg") or "accent2"), note="cut terminal",
          camera={"c": {"x": 0, "y": 0, "zoom": 1.0}, "e": {"x": 0, "y": zoom_y * 0.5, "zoom": 1.08}, "d": 7000})
    r.hold(300)
    for b in beats:
        if b[0] == "cmd":
            r.appear(b[1], note="prompt")
            r.hold(120)
            r.type_in(b[2], type_ms(b[3], per_char=38, lo=500, hi=1400), note="command")
            r.hold(220)
        else:
            r.appear(b[1], note="output")
            r.cue("tick")
            r.hold(170)
    if done:
        r.hold(150)
        r.appear(k + "dn_i", k + "dn_t", note="done")
        r.step(340, "back", [dict(id=k + "dn_i", scaleX=1, scaleY=1)], note="done pop")
    r.hold(read_ms(done, lo=1100, hi=1500))


# ---------------- browser ----------------
def browser(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    BX, BY, BW, BH = -560, -320, 1120, 640
    r.node(k + "fr", "rect", BX, BY, BW, BH, 24, fill=pal.panel, stroke=pal.line, strokeWidth=1.5, cornerRadius=14,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.12)", radius=40))
    r.node(k + "tb", "rect", BX, BY, BW, 56, 25, fill=pal.soft, cornerRadius=14)
    r.node(k + "tb2", "rect", BX, BY + 40, BW, 16, 25, fill=pal.soft)
    chrome = [k + "fr", k + "tb", k + "tb2"]
    for j, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        r.node(f"{k}dot{j}", "circle", BX + 20 + j * 22, BY + 22, 13, 13, 26, fill=col)
        chrome.append(f"{k}dot{j}")
    UX, UW = BX + 120, BW - 240
    r.node(k + "url", "rect", UX, BY + 12, UW, 32, 26, fill=pal.panel, stroke=pal.line, strokeWidth=1, cornerRadius=16)
    r.icon(k + "lock", "ph:lock-simple-fill", UX + 14, BY + 20, 16, 27, color=pal.grey)
    url = fit(p.get("url") or re.sub(r"[^a-z0-9]+", "", c.brand["name"].lower()) + ".com", 16, UW - 60, 500)[0]
    r.text(k + "urlt", UX + 38, BY + 12, UW - 50, 32, url, 16, color=pal.body, weight=500, z=27, typeProgress=0)
    chrome += [k + "url", k + "lock"]
    # page, in local coordinates of the viewport mask
    vp = k + "vp"
    VW, VH = BW, BH - 56
    r.mask(vp, BX, BY + 56, VW, VH, 26)
    kids = []

    def kid(nd):
        kids.append(nd["id"])
        return nd

    letter = (c.brand.get("logo_letter") or c.brand["name"][:1]).upper()[:2]
    kid(r.node(k + "plg", "rect", 40, 22, 34, 34, 27, fill=pal.ink, cornerRadius=8, parentId=vp, opacity=1,
               label=letter, labelColor=pal.on_ink, labelFontSize=17, labelFontWeight=800, fontSize=17,
               fontFamily=r.style.display, labelFontFamily=r.style.display))
    kid(r.text(k + "pnm", 84, 22, 200, 34, fit(c.brand["name"], 18, 200, 700)[0], 18, weight=700, z=27,
               parentId=vp, opacity=1))
    for j, lbl in enumerate((p.get("nav") or ["Product", "Pricing", "Docs"])[:3]):
        kid(r.text(f"{k}pn{j}", VW - 470 + j * 110, 22, 110, 34, fit(lbl, 16, 100, 500)[0], 16, color=pal.grey,
                   weight=500, z=27, parentId=vp, opacity=1))
    kid(r.node(k + "pbt", "rect", VW - 150, 18, 110, 40, 27, fill=pal.ink, cornerRadius=20, parentId=vp, opacity=1,
               label="Sign up", labelColor=pal.on_ink, labelFontSize=15, labelFontWeight=600, fontSize=15,
               fontFamily=r.style.body, labelFontFamily=r.style.body))
    title, ts = fit(p.get("title") or c.brand["name"], 52, VW - 160, 700)
    kid(r.text(k + "h1", 0, 120, VW, 70, title, ts, weight=700, align="center", z=27, parentId=vp, opacity=1))
    sub = wrap(p.get("subtitle") or "", 21, VW - 300, 500, 2)
    for j, s in enumerate(sub):
        kid(r.text(f"{k}sb{j}", 0, 200 + j * 32, VW, 32, s, 21, color=pal.grey, weight=500, align="center", z=27,
                   parentId=vp, opacity=1))
    cta = fit(p.get("cta") or "Get started", 18, 260, 600)[0]
    cw = tw(cta, 18, 600) + 56
    kid(r.node(k + "cta", "rect", VW / 2 - cw / 2, 290, cw, 52, 27, fill=pal.accents[0], cornerRadius=26, parentId=vp,
               opacity=1, label=cta, labelColor=pal.ink if not pal.dark else "#ffffff", labelFontSize=18,
               labelFontWeight=600, fontSize=18, fontFamily=r.style.body, labelFontFamily=r.style.body))
    feats = [x for x in (p.get("features") or []) if x.get("label")][:3] or [{"icon": "ph:sparkle-fill", "label": "Fast"}]
    fw = (VW - 80 - 24 * (len(feats) - 1)) / len(feats)
    for j, f in enumerate(feats):
        x = 40 + j * (fw + 24)
        kid(r.node(f"{k}fc{j}", "rect", x, 400, fw, 190, 27, fill=pal.soft, cornerRadius=16, parentId=vp, opacity=1))
        ic = f.get("icon") or "ph:sparkle-fill"
        kid(r.icon(f"{k}fi{j}", ic, x + 24, 424, 40, 28, color=_icon_color(ic, pal.accents[j % len(pal.accents)]),
                   parentId=vp, opacity=1))
        kid(r.text(f"{k}ft{j}", x + 24, 478, fw - 48, 34, fit(f["label"], 21, fw - 48, 700)[0], 21, weight=700,
                   z=28, parentId=vp, opacity=1))
        for q in range(2):
            kid(r.node(f"{k}fl{j}{q}", "rect", x + 24, 526 + q * 22, (fw - 48) * (0.9 - 0.3 * q), 10, 28,
                       fill=pal.line, cornerRadius=5, parentId=vp, opacity=1))
    # a product shot further down
    kid(r.node(k + "shot", "rect", 40, 640, VW - 80, 290, 27, fill=pal.soft, cornerRadius=18, parentId=vp, opacity=1))
    for j in range(7):
        hh = 50 + 26 * ((j * 37) % 7)
        kid(r.node(f"{k}sb_{j}", "rect", 120 + j * 120, 900 - hh, 60, hh, 28,
                   fill=_mix(pal.accents[j % len(pal.accents)], pal.panel, 0.25), cornerRadius=8, parentId=vp,
                   opacity=1))

    r.cut(chrome, bg=pal.field(p.get("bg") or "accent3"), note="cut browser",
          camera={"c": {"x": 0, "y": -250, "zoom": 1.9}})
    r.hold(250)
    r.appear(k + "urlt", note="url on")
    ms = type_ms(url, per_char=45, lo=600, hi=1200)
    r.step(ms, "linear", actions=[r.tween(k + "urlt", "typeProgress", 0, 1, ms - 60)], note="type url")
    r.hold(150)
    r.cue("click")
    r.appear(vp, note="page loads")
    r.step(700, "ease", note="pull back", camera={"e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 700, "ease": "ease"})
    r.hold(read_ms(title, *sub, lo=1000, hi=1600))
    dy = 380
    # the clip hides fills but not outlines, so whatever scrolls out of the viewport also fades
    gone = {i for i in kids if r.byid[i]["y"] + r.byid[i]["h"] - dy < 0}
    r.step(1300, "ease", [dict(id=i, y=r.byid[i]["y"] - dy, **({"opacity": 0} if i in gone else {}))
                          for i in kids], note="scroll",
           camera={"e": {"x": 0, "y": 10, "zoom": 1.04}, "d": 1300, "ease": "ease"})
    r.hold(read_ms(*[f["label"] for f in feats], lo=1000, hi=1500))


# ---------------- split ----------------
def split(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    LX, RX, Y0, W, H = -610, 20, -270, 590, 540
    r.node(k + "lp", "rect", LX, Y0, W, H, 24, fill=pal.soft, stroke=pal.line, strokeWidth=1.5, cornerRadius=22)
    r.node(k + "rp", "rect", RX, Y0, W, H, 24, fill=pal.panel, stroke=pal.accents[0], strokeWidth=3, cornerRadius=22,
           dropShadow=dict(dx=0, dy=14, color="rgba(0,0,0,0.10)", radius=36))
    bt = fit(p.get("before_title") or "Before", 30, W - 80, 700)[0]
    at = fit(p.get("after_title") or f"With {c.brand['name']}", 30, W - 80, 700)[0]
    r.text(k + "lt", LX + 40, Y0 + 30, W - 80, 50, bt, 30, color=pal.grey, weight=700, z=25)
    r.text(k + "rt", RX + 40, Y0 + 30, W - 80, 50, at, 30, weight=700, z=25)
    before = [x for x in (p.get("before") or []) if x][:4] or ["Manual work"]
    after = [x for x in (p.get("after") or []) if x][:4] or ["Automatic"]
    gap = min(100, (H - 140) / max(len(before), len(after)))
    lb, ra = [], []
    for i, t in enumerate(before):
        y = Y0 + 120 + i * gap
        txt, s = fit(t, 23, W - 130, 500)
        r.icon(f"{k}bi{i}", "ph:x-circle-fill", LX + 40, y + 10, 32, 25, color=pal.bad, scaleX=0.5, scaleY=0.5)
        r.text(f"{k}bt{i}", LX + 88, y, W - 120, 52, txt, s, color=pal.grey, weight=500, z=25)
        r.node(f"{k}bs{i}", "rect", LX + 88, y + 25, 0, 2.5, 26, fill=pal.grey)
        lb.append((f"{k}bi{i}", f"{k}bt{i}", f"{k}bs{i}", tw(txt, s, 500)))
    for i, t in enumerate(after):
        y = Y0 + 120 + i * gap
        txt, s = fit(t, 23, W - 130, 600)
        r.icon(f"{k}ai{i}", "ph:check-circle-fill", RX + 40, y + 10, 32, 25, color=pal.good, scaleX=0.5, scaleY=0.5)
        r.text(f"{k}at{i}", RX + 88, y, W - 120, 52, txt, s, weight=600, z=25)
        ra.append((f"{k}ai{i}", f"{k}at{i}"))
    r.cut([k + "lp", k + "rp", k + "lt", k + "rt"], bg=pal.field(p.get("bg")), note="cut split",
          camera={"c": {"x": -315, "y": 0, "zoom": 1.18}})
    r.hold(300)
    for ic, t, _, _ in lb:
        r.appear(ic, t, note="before item")
        r.step(300, "back", [dict(id=ic, scaleX=1, scaleY=1)], note="x pop")
        r.hold(180)
    r.appear(*[s for _, _, s, _ in lb], note="strikes on")
    r.step(420, "ease-out", [dict(id=s, w=w) for _, _, s, w in lb], delays={s: j * 80 for j, (_, _, s, _) in enumerate(lb)},
           note="strike")
    r.hold(300)
    r.step(650, "ease", note="to after", camera={"e": {"x": 315, "y": 0, "zoom": 1.18}, "d": 650, "ease": "ease"})
    for ic, t in ra:
        r.appear(ic, t, note="after item")
        r.step(300, "back", [dict(id=ic, scaleX=1, scaleY=1)], note="check pop")
        r.hold(160)
    r.step(650, "ease", note="pull back", camera={"e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 650, "ease": "ease"})
    r.hold(read_ms(*after, lo=1000, hi=1600))


# ---------------- stat ----------------
def stat(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    val, vs = fit(p.get("value") or "10x", 200, 1100, 800)
    frames = count_frames(c, k + "v", val, -640, -200, 1280, 260, vs, n=18, weight=800, align="center", z=30,
                          role="display", letterSpacing=-4)
    label = p.get("label") or ""
    masks, kids, ls = _lines(c, k + "l", label, 0, 130, 44, 1000, 2) if label else ([], [], [])
    sub = fit(p.get("sub") or "", 20, 900, 500)[0]
    if sub:
        r.text(k + "sub", -500, 210 + 30 * (len(ls) - 1), 1000, 36, sub, 20, color=pal.body, weight=500,
               align="center", z=30)
    r.cut([frames[0]], bg=pal.field(p.get("bg") or "accent2"), note="cut stat",
          camera={"c": {"x": 0, "y": -20, "zoom": 1.12}, "e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 1600})
    r.count(frames, 1200)
    if kids:
        r.appear(*masks, note="label on")
        r.step(520, "ease-out", r.rise_in(*kids), delays={kd: 90 * j for j, kd in enumerate(kids)}, note="label rise")
    if sub:
        r.appear(k + "sub", note="sub on")
    r.hold(read_ms(label, sub, lo=1200))


# ---------------- kanban ----------------
def kanban(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    cols = [fit(x, 20, 220, 700)[0] for x in (p.get("columns") or ["To do", "In progress", "Done"])[:3]]
    while len(cols) < 3:
        cols.append(["To do", "In progress", "Done"][len(cols)])
    cards = [x for x in (p.get("cards") or []) if x.get("title")][:6] or [{"title": "Ship it", "col": 0}]
    CW, CH, G = 350, 540, 26
    X0 = -(3 * CW + 2 * G) / 2
    Y0 = -250
    board = []
    for j, name in enumerate(cols):
        x = X0 + j * (CW + G)
        r.node(f"{k}col{j}", "rect", x, Y0, CW, CH, 22, fill=pal.soft, cornerRadius=18)
        r.node(f"{k}cd{j}", "circle", x + 22, Y0 + 26, 12, 12, 23, fill=[pal.faint, pal.accents[0], pal.good][j])
        r.text(f"{k}cn{j}", x + 44, Y0 + 14, CW - 60, 36, name, 20, weight=700, z=23)
        board += [f"{k}col{j}", f"{k}cd{j}", f"{k}cn{j}"]
    per = {0: [], 1: [], 2: []}
    for i, cd in enumerate(cards):
        per[max(0, min(2, int(cd.get("col", 0) or 0)))].append(i)
    mv = p.get("move")
    mv = int(mv) if isinstance(mv, int) and 0 <= mv < len(cards) else (per[0] or per[1] or [0])[0]
    src = next(j for j in per if mv in per[j])
    if src == 2:
        per[2].remove(mv)
        per[0].insert(0, mv)
        src = 0
    KW, KH, KG = CW - 36, 84, 98
    pos = {}
    for j, ids in per.items():
        for q, i in enumerate(ids[:4]):
            pos[i] = (X0 + j * (CW + G) + 18, Y0 + 70 + q * KG)
    groups = []
    for i, (x, y) in pos.items():
        g = f"{k}k{i}"
        z = 40 if i == mv else 30
        _group(c, g, x, y, KW, KH, z)
        r.node(g + "_b", "rect", 0, 0, KW, KH, z + 1, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
               cornerRadius=12, parentId=g, opacity=1)
        r.node(g + "_t", "rect", 16, 16, 44, 8, z + 2, fill=pal.accents[i % len(pal.accents)], cornerRadius=4,
               parentId=g, opacity=1)
        r.text(g + "_x", 16, 32, KW - 70, 40, fit(cards[i]["title"], 18, KW - 80, 600)[0], 18, weight=600, z=z + 2,
               parentId=g, opacity=1)
        r.node(g + "_a", "circle", KW - 44, 42, 28, 28, z + 2, fill=_mix(pal.accents[(i + 1) % len(pal.accents)], pal.panel, 0.3),
               parentId=g, opacity=1)
        groups.append(g)
    tx, ty = X0 + 2 * (CW + G) + 18, Y0 + 70 + len([i for i in per[2] if i in pos]) * KG
    r.icon(k + "chk", "ph:check-circle-fill", tx + KW - 50, ty + 26, 32, 45, color=pal.good, scaleX=0.4, scaleY=0.4)
    sx, sy = pos[mv]
    cur = _cursor(c, k + "cur", sx + KW + 120, sy + 240)
    r.cut(board + groups, bg=pal.field(p.get("bg") or "accent1"), note="cut kanban",
          camera={"c": {"x": -60, "y": 0, "zoom": 1.06}, "e": {"x": 40, "y": 0, "zoom": 1.06}, "d": 5200})
    r.hold(500)
    r.appear(cur, note="cursor on")
    r.step(520, "ease", [dict(id=cur, x=sx + KW - 70, y=sy + 40)], note="to card")
    r.step(110, "ease-out", [dict(id=cur, scaleX=0.85, scaleY=0.85)], note="press")
    g = f"{k}k{mv}"
    r.step(900, "ease", [dict(id=g, x=tx, y=ty), dict(id=cur, x=tx + KW - 70, y=ty + 40, scaleX=1, scaleY=1)],
           note="drag")
    below = [i for i in per[src] if i in pos and pos[i][1] > sy]
    if below:
        r.step(300, "ease-out", [dict(id=f"{k}k{i}", y=pos[i][1] - KG) for i in below], note="close gap")
    r.appear(k + "chk", note="done check")
    r.step(340, "back", [dict(id=k + "chk", scaleX=1, scaleY=1)], note="check pop")
    r.hold(read_ms(cards[mv]["title"], lo=1000, hi=1400))


# ---------------- notifications ----------------
def notifications(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    line = p.get("line") or ""
    masks, kids, _ = _lines(c, k + "l", line, -330, 0, 52, 540, 3) if line else ([], [], [])
    items = [x for x in (p.get("items") or []) if x.get("title")][:4] or [{"title": "Done", "body": ""}]
    NX, NW, NH, NG = 40 if line else -260, 520, 92, 108
    top = -((len(items) - 1) * NG + NH) / 2
    groups = []
    for i, it in enumerate(items):
        g = f"{k}n{i}"
        _group(c, g, NX, top - 70, NW, NH, 30 + i)
        r.node(g + "_b", "rect", 0, 0, NW, NH, 31 + i, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=18,
               parentId=g, opacity=1)
        ic = it.get("icon") or "ph:bell-simple-fill"
        acc = pal.accents[i % len(pal.accents)]
        r.node(g + "_s", "rect", 18, 18, 56, 56, 32 + i, fill=_mix(acc, pal.panel, 0.55), cornerRadius=14, parentId=g,
               opacity=1)
        r.icon(g + "_i", ic, 32, 32, 28, 33 + i, color=_icon_color(ic, pal.ink), parentId=g, opacity=1)
        r.text(g + "_t", 92, 14, NW - 170, 34, fit(it["title"], 19, NW - 170, 700)[0], 19, weight=700, z=33 + i,
               parentId=g, opacity=1)
        r.text(g + "_d", 92, 46, NW - 120, 30, fit(it.get("body") or "", 16, NW - 120, 500)[0], 16, color=pal.grey,
               weight=500, z=33 + i, parentId=g, opacity=1)
        r.text(g + "_w", NW - 76, 14, 60, 34, "now", 14, color=pal.faint, weight=500, align="right", z=33 + i,
               parentId=g, opacity=1)
        groups.append(g)
    r.cut(masks, bg=pal.field(p.get("bg")), note="cut notifications",
          camera={"c": C0, "e": {"x": 30, "y": 0, "zoom": 1.05}, "d": 7000})
    if kids:
        r.step(600, "ease-out", r.rise_in(*kids), delays={kd: 90 * j for j, kd in enumerate(kids)}, note="line rise")
        r.hold(400)
    shown = []
    for i, g in enumerate(groups):
        r.appear(g, note="toast on")
        moves = [dict(id=g, y=top)] + [dict(id=s, y=top + NG * (len(shown) - j)) for j, s in enumerate(shown)]
        r.step(420, "back", moves, note="toast in")
        r.cue("ding", n=i)
        shown.append(g)
        r.hold(read_ms(items[i]["title"], items[i].get("body"), base=250, per_word=110, lo=650, hi=1000))
    r.hold(600)


# ---------------- map ----------------
_LAND = [
    [(-168, 66), (-162, 70), (-140, 70), (-125, 70), (-95, 72), (-80, 73), (-62, 66), (-56, 52), (-66, 45),
     (-70, 42), (-76, 35), (-81, 31), (-80, 25), (-84, 30), (-90, 29), (-97, 26), (-97, 21), (-92, 18), (-87, 21),
     (-88, 15), (-83, 9), (-78, 8), (-80, 8), (-86, 12), (-92, 15), (-105, 20), (-110, 24), (-112, 30), (-117, 32),
     (-122, 37), (-124, 42), (-124, 48), (-130, 54), (-140, 60), (-152, 58), (-165, 60)],
    [(-73, 78), (-60, 82), (-30, 83), (-20, 78), (-22, 70), (-42, 60), (-52, 64), (-58, 70), (-70, 76)],
    [(-80, 9), (-72, 12), (-62, 10), (-52, 5), (-50, 0), (-35, -5), (-39, -14), (-41, -22), (-48, -26), (-53, -33),
     (-58, -38), (-63, -41), (-66, -46), (-68, -52), (-73, -53), (-75, -46), (-73, -38), (-71, -30), (-70, -18),
     (-76, -14), (-81, -6), (-80, 1), (-78, 7)],
    [(-10, 36), (-9, 43), (-2, 44), (-5, 48), (2, 51), (8, 54), (10, 57), (5, 61), (10, 64), (15, 69), (22, 71),
     (30, 70), (40, 67), (42, 62), (40, 55), (35, 50), (30, 46), (28, 41), (24, 38), (20, 40), (15, 38), (12, 44),
     (8, 44), (3, 42), (-2, 37)],
    [(-6, 50), (1, 51), (2, 53), (-2, 56), (-3, 59), (-6, 58), (-5, 54)],
    [(-10, 52), (-6, 52), (-6, 55), (-9, 55)],
    [(-24, 64), (-14, 64), (-14, 66), (-22, 66)],
    [(-17, 21), (-16, 28), (-10, 32), (-6, 36), (10, 37), (11, 33), (20, 32), (25, 32), (32, 31), (34, 28), (38, 20),
     (43, 12), (51, 12), (51, 10), (45, 2), (40, -5), (40, -15), (35, -23), (32, -29), (27, -34), (20, -35), (17, -29),
     (12, -17), (13, -8), (9, -1), (9, 4), (5, 5), (-5, 5), (-8, 4), (-13, 8), (-17, 14)],
    [(44, -25), (47, -25), (50, -15), (49, -12), (44, -17)],
    [(28, 41), (36, 36), (35, 33), (34, 28), (39, 22), (43, 13), (45, 13), (52, 16), (56, 18), (59, 22), (57, 25),
     (52, 25), (50, 28), (48, 30), (56, 27), (62, 25), (67, 24), (70, 21), (73, 16), (77, 8), (80, 13), (80, 16),
     (87, 21), (91, 22), (94, 17), (98, 16), (98, 9), (100, 4), (104, 1), (103, 6), (105, 9), (109, 12), (108, 17),
     (106, 20), (110, 21), (117, 23), (121, 28), (122, 31), (119, 35), (122, 37), (121, 40), (125, 39), (129, 35),
     (129, 42), (135, 43), (141, 48), (141, 53), (137, 55), (143, 59), (155, 59), (160, 61), (163, 66), (178, 65),
     (180, 69), (170, 70), (160, 70), (150, 72), (140, 73), (130, 72), (115, 74), (105, 78), (95, 76), (80, 73),
     (70, 73), (66, 70), (60, 69), (50, 68), (44, 66), (40, 67), (42, 62), (40, 55), (35, 50), (30, 46)],
    [(130, 31), (132, 34), (135, 34), (140, 35), (141, 38), (142, 41), (140, 41), (137, 37), (133, 35)],
    [(140, 42), (145, 43), (145, 45), (141, 45)],
    [(95, 5), (98, 4), (104, -2), (106, -6), (102, -4), (97, 1)],
    [(109, 1), (112, -3), (116, -4), (119, 1), (117, 6), (113, 4)],
    [(105, -6), (114, -7), (114, -8), (106, -7)],
    [(131, -1), (138, -2), (147, -6), (150, -10), (142, -9), (137, -5), (132, -3)],
    [(120, 18), (122, 18), (126, 8), (125, 6), (122, 10), (120, 14)],
    [(114, -22), (114, -34), (118, -35), (124, -33), (131, -31), (137, -34), (140, -38), (146, -39), (150, -37),
     (153, -31), (153, -25), (146, -19), (142, -11), (141, -17), (136, -15), (136, -12), (131, -11), (126, -14),
     (122, -18)],
    [(172, -34), (175, -37), (178, -38), (175, -41), (171, -44), (167, -46), (170, -41)],
]

CITIES = {
    "new york": (-74, 40.7), "san francisco": (-122.4, 37.8), "los angeles": (-118.2, 34), "seattle": (-122.3, 47.6),
    "toronto": (-79.4, 43.7), "chicago": (-87.6, 41.9), "austin": (-97.7, 30.3), "miami": (-80.2, 25.8),
    "vancouver": (-123.1, 49.3), "mexico city": (-99.1, 19.4), "são paulo": (-46.6, -23.5), "sao paulo": (-46.6, -23.5),
    "buenos aires": (-58.4, -34.6), "bogotá": (-74.1, 4.7), "london": (-0.1, 51.5), "paris": (2.35, 48.9),
    "berlin": (13.4, 52.5), "amsterdam": (4.9, 52.4), "madrid": (-3.7, 40.4), "barcelona": (2.2, 41.4),
    "stockholm": (18.1, 59.3), "lisbon": (-9.1, 38.7), "dublin": (-6.3, 53.3), "zurich": (8.5, 47.4),
    "warsaw": (21, 52.2), "lagos": (3.4, 6.5), "nairobi": (36.8, -1.3), "cape town": (18.4, -33.9),
    "cairo": (31.2, 30), "dubai": (55.3, 25.2), "tel aviv": (34.8, 32.1), "istanbul": (29, 41),
    "mumbai": (72.9, 19), "bangalore": (77.6, 13), "bengaluru": (77.6, 13), "delhi": (77.2, 28.6),
    "singapore": (103.8, 1.35), "jakarta": (106.8, -6.2), "tokyo": (139.7, 35.7), "seoul": (127, 37.6),
    "shanghai": (121.5, 31.2), "hong kong": (114.2, 22.3), "sydney": (151.2, -33.9), "melbourne": (145, -37.8),
    "auckland": (174.8, -36.8), "manila": (121, 14.6), "bangkok": (100.5, 13.8),
}
MAP_W, LAT_N, LAT_S = 1120, 80, -56


def _inside(pt, poly):
    x, y = pt
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def _proj(lon, lat):
    s = MAP_W / 360
    return (lon + 180) * s - MAP_W / 2, (LAT_N - lat) * s


def world_dots(step=12.0, r=4.2) -> tuple[str, float]:
    """One path of dots covering the land, and the map's height."""
    s = MAP_W / 360
    h = (LAT_N - LAT_S) * s
    d = []
    y = step / 2
    while y < h:
        x = step / 2
        while x < MAP_W:
            lon, lat = x / s - 180, LAT_N - y / s
            if any(_inside((lon, lat), poly) for poly in _LAND):
                a, b, c, e = x - r, y - r, x + r, y + r
                d.append(f"M{a:.1f} {b:.1f}L{c:.1f} {b:.1f}L{c:.1f} {e:.1f}L{a:.1f} {e:.1f}Z")
            x += step
        y += step
    return "".join(d), h


def map_scene(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    dots, MH = world_dots()
    MY = -MH / 2 + 50
    r.node(k + "map", "svg", -MAP_W / 2, MY, MAP_W, MH, 20,
           svgPaths=[{"d": dots, "fill": _mix(pal.ink, pal.field(p.get("bg") or "paper"), 0.55)}],
           svgViewBox={"x": 0, "y": 0, "w": MAP_W, "h": MH}, svgStretch=True, fill=pal.ink)
    line = fit(p.get("line") or "", 46, 1100)[0]
    m = r.rise_line(k + "ln", 0, -290, line, fit(line, 46, 1100)[1]) if line else None
    pins = []
    for i, pn in enumerate([x for x in (p.get("pins") or []) if x.get("city")][:6]):
        ll = CITIES.get(str(pn["city"]).strip().lower())
        if not ll:
            continue
        x, y = _proj(*ll)
        x, y = x, y + MY
        acc = pal.accents[i % len(pal.accents)]
        r.node(f"{k}rg{i}", "circle", x - 30, y - 30, 60, 60, 30, stroke=acc, strokeWidth=3, scaleX=0.2, scaleY=0.2)
        r.icon(f"{k}pn{i}", "ph:map-pin-fill", x - 20, y - 40 - 60, 40, 32, color=acc)
        lbl = fit(pn.get("label") or pn["city"], 16, 220, 600)[0]
        lw = tw(lbl, 16, 600) + 28
        side = 1 if x < 380 else -1
        lx = x + 26 if side > 0 else x - 26 - lw
        r.node(f"{k}pl{i}", "rect", lx, y - 52, lw, 34, 33, fill=pal.panel, stroke=pal.line, strokeWidth=1,
               cornerRadius=17, scaleX=0.7, scaleY=0.7, label=lbl, labelColor=pal.ink, labelFontSize=16,
               labelFontWeight=600, fontSize=16, fontFamily=r.style.body, labelFontFamily=r.style.body)
        pins.append((i, y))
    r.cut([k + "map"] + ([m] if m else []), bg=pal.field(p.get("bg")), note="cut map",
          camera={"c": {"x": 0, "y": 0, "zoom": 0.94}, "e": {"x": 0, "y": 20, "zoom": 1.04}, "d": 7000})
    if m:
        r.step(600, "ease-out", r.rise_in(k + "ln"), note="line rise")
    r.hold(300)
    for i, y in pins:
        r.appear(f"{k}pn{i}", note="pin on")
        r.step(420, "back", [dict(id=f"{k}pn{i}", y=y - 40)], note="pin drop")
        r.cue("pop")
        r.appear(f"{k}rg{i}", f"{k}pl{i}", note="ring on")
        r.step(360, "back", [dict(id=f"{k}rg{i}", scaleX=1.4, scaleY=1.4, opacity=0), dict(id=f"{k}pl{i}", scaleX=1, scaleY=1)],
               note="ring")
        r.hold(150)
    r.hold(read_ms(line, lo=1100))


# ---------------- pricing ----------------
def pricing(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    CW, CH = 470, 580
    X, Y = -CW / 2, -CH / 2
    r.node(k + "card", "rect", X, Y, CW, CH, 24, fill=pal.panel, stroke=pal.line, strokeWidth=1.5, cornerRadius=26,
           dropShadow=dict(dx=0, dy=20, color="rgba(0,0,0,0.12)", radius=44))
    plan = fit(p.get("plan") or "Pro", 22, 240, 700)[0]
    r.text(k + "pl", X + 40, Y + 36, 300, 40, plan, 22, weight=700, z=25)
    shell = [k + "card", k + "pl"]
    badge = fit(p.get("badge") or "", 14, 160, 700)[0]
    if badge:
        bw = tw(badge, 14, 700) + 28
        r.node(k + "bd", "rect", X + CW - 40 - bw, Y + 40, bw, 30, 25, fill=_mix(pal.accents[0], pal.panel, 0.7),
               cornerRadius=15, label=badge, labelColor=pal.ink, labelFontSize=14, labelFontWeight=700, fontSize=14,
               fontFamily=r.style.body, labelFontFamily=r.style.body)
        shell.append(k + "bd")
    price, ps = fit(p.get("price") or "$19", 84, 260, 800)
    per = fit(p.get("period") or "/month", 22, 160, 500)[0]
    pw = tw(price, ps, 800)
    frames = count_frames(c, k + "pr", price, X + 40 - 200, Y + 92, pw + 200, 110, ps, n=12, weight=800,
                          align="right", z=26, role="display", letterSpacing=-2)
    r.text(k + "per", X + 40 + pw + 10, Y + 132, 200, 50, per, 22, color=pal.grey, weight=500, z=26)
    r.node(k + "hr", "rect", X + 40, Y + 226, CW - 80, 1.5, 25, fill=pal.line)
    shell += [frames[0], k + "per", k + "hr"]
    feats = [x for x in (p.get("features") or []) if x][:4]
    rows = []
    for i, f in enumerate(feats):
        y = Y + 252 + i * 50
        r.icon(f"{k}fi{i}", "ph:check-circle-fill", X + 40, y + 9, 26, 26, color=pal.good, scaleX=0.5, scaleY=0.5)
        r.text(f"{k}ft{i}", X + 80, y, CW - 120, 44, fit(f, 19, CW - 120, 500)[0], 19, color=pal.body, weight=500, z=26)
        rows.append((f"{k}fi{i}", f"{k}ft{i}"))
    cta = fit(p.get("cta") or "Start free trial", 19, CW - 120, 700)[0]
    r.node(k + "btn", "rect", X + 40, Y + CH - 96, CW - 80, 58, 26, fill=pal.ink, cornerRadius=16, label=cta,
           labelColor=pal.on_ink, labelFontSize=19, labelFontWeight=700, fontSize=19, fontFamily=r.style.body,
           labelFontFamily=r.style.body)
    shell.append(k + "btn")
    cur = _cursor(c, k + "cur", 300, 320)
    r.cut(shell, bg=pal.field(p.get("bg") or "accent3"), note="cut pricing",
          camera={"c": {"x": 0, "y": -110, "zoom": 1.35}, "e": {"x": 0, "y": -90, "zoom": 1.3}, "d": 1500})
    r.hold(250)
    r.count(frames, 900)
    r.hold(250)
    r.step(600, "ease", note="frame card", camera={"e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 600, "ease": "ease"})
    for ic, t in rows:
        r.appear(ic, t, note="feature")
        r.step(260, "back", [dict(id=ic, scaleX=1, scaleY=1)], note="tick pop")
        r.hold(140)
    r.appear(cur, note="cursor on")
    r.step(560, "ease", [dict(id=cur, x=40, y=Y + CH - 76)], note="to button")
    r.step(110, "ease-out", [dict(id=k + "btn", scaleX=0.96, scaleY=0.96), dict(id=cur, scaleX=0.85, scaleY=0.85)],
           note="press")
    r.step(240, "back", [dict(id=k + "btn", scaleX=1, scaleY=1, fill=pal.accents[0]), dict(id=cur, scaleX=1, scaleY=1)],
           note="release")
    r.hold(read_ms(plan, cta, lo=1000, hi=1300))


# ---------------- logo grid ----------------
def logo_grid(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    apps = [a for a in (p.get("apps") or []) if a][:12] or ["ph:sparkle-fill"]
    n = len(apps)
    cols = n if n <= 6 else math.ceil(n / 2)
    rows = math.ceil(n / cols)
    T, G = 124, 26
    gw = cols * T + (cols - 1) * G
    line = p.get("line") or ""
    masks, kids, ls = _lines(c, k + "l", line, 0, -220 if rows > 1 else -170, 52, 1100, 2) if line else ([], [], [])
    gy = -60 if rows > 1 else -30
    tiles = []
    for i, a in enumerate(apps):
        row, col = divmod(i, cols)
        x = -gw / 2 + col * (T + G)
        y = gy + row * (T + G)
        r.node(f"{k}t{i}", "rect", x, y, T, T, 24, fill=pal.panel, stroke=pal.line, strokeWidth=1.5, cornerRadius=26,
               scaleX=0.5, scaleY=0.5)
        nd = r.icon(f"{k}i{i}", a, 0, 0, 64, 25, color=_icon_color(a, pal.ink), scaleX=0.5, scaleY=0.5)
        r.place(nd["id"], x + (T - 64) / 2, y + (T - nd["h"]) / 2)
        tiles.append((f"{k}t{i}", f"{k}i{i}", row + col))
    r.cut(masks, bg=pal.field(p.get("bg")), note="cut logo grid", camera=_drift(1.04, 5000))
    if kids:
        r.step(600, "ease-out", r.rise_in(*kids), delays={kd: 90 * j for j, kd in enumerate(kids)}, note="line rise")
    ids = [x for t in tiles for x in t[:2]]
    r.appear(*ids, note="tiles on")
    r.step(700, "back", [dict(id=i, scaleX=1, scaleY=1) for i in ids],
           delays={i: t[2] * 70 for t in tiles for i in t[:2]}, note="tiles pop")
    r.hold(read_ms(*ls, lo=1300))


# ---------------- compare ----------------
def compare(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    rows = [x for x in (p.get("rows") or []) if x][:5] or ["Fast"]
    them = list(p.get("them") or [])
    cols = (p.get("columns") or [])[:2]
    them_l = fit(cols[0] if cols else "The old way", 20, 190, 700)[0]
    us_l = fit(cols[1] if len(cols) > 1 else c.brand["name"], 20, 190, 700)[0]
    W, FW, VW = 1060, 620, 200
    X0, RH = -W / 2, 76
    line = p.get("line") or ""
    m, ls = None, []
    if line:
        t, s = fit(line, 46, 1100)
        m, ls = r.rise_line(k + "ln", 0, -300, t, s), [t]
    top = -200 + (5 - len(rows)) * RH / 2
    ux = X0 + FW + VW
    r.node(k + "hl", "rect", ux + 10, top - 10, VW - 20, 0, 21, fill=_mix(pal.accents[0], pal.panel, 0.55), cornerRadius=18)
    r.text(k + "h0", X0 + FW, top, VW, 56, them_l, 20, color=pal.grey, weight=700, align="center", z=24)
    r.text(k + "h1", ux, top, VW, 56, us_l, 20, weight=700, align="center", z=24)
    head = [k + "h0", k + "h1"]
    beats, checks = [], []
    for i, row in enumerate(rows):
        y = top + 64 + i * RH
        r.node(f"{k}rl{i}", "rect", X0, y, W, 1.2, 22, fill=pal.line)
        r.text(f"{k}rt{i}", X0 + 10, y, FW - 20, RH, fit(row, 23, FW - 30, 500)[0], 23, color=pal.body, weight=500, z=24)
        has = bool(them[i]) if i < len(them) else False
        ic = "ph:check-bold" if has else "ph:x-bold"
        r.icon(f"{k}tm{i}", ic, X0 + FW + VW / 2 - 14, y + RH / 2 - 14, 28, 24, color=pal.faint)
        r.icon(f"{k}us{i}", "ph:check-circle-fill", ux + VW / 2 - 18, y + RH / 2 - 18, 36, 24, color=pal.good,
               scaleX=0.4, scaleY=0.4)
        beats.append([f"{k}rl{i}", f"{k}rt{i}", f"{k}tm{i}"])
        checks.append(f"{k}us{i}")
    full = 64 + len(rows) * RH + 20
    r.cut(head + ([m] if m else []), bg=pal.field(p.get("bg")), note="cut compare",
          camera={"c": {"x": 0, "y": 0, "zoom": 1.0}, "e": {"x": 0, "y": 20, "zoom": 1.05}, "d": 7000})
    if m:
        r.step(560, "ease-out", r.rise_in(k + "ln"), note="line rise")
    for b in beats:
        r.appear(*b, note="row")
        r.hold(260)
    r.appear(k + "hl", note="column on")
    r.step(520, "ease-out", [dict(id=k + "hl", h=full)], note="column grow")
    r.appear(*checks, note="checks on")
    r.step(560, "back", [dict(id=i, scaleX=1, scaleY=1) for i in checks],
           delays={i: j * 90 for j, i in enumerate(checks)}, note="checks pop")
    r.hold(read_ms(*rows, lo=1200, hi=1800))


# ---------------- problem ----------------
def problem(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    line = p.get("line") or "Sound familiar?"
    t, s = fit(line, 56, 1100)
    m = r.rise_line(k + "ln", 0, -220, t, s)
    pains = [x for x in (p.get("pains") or []) if x][:3] or ["Too much busywork"]
    CW, CH, G = 900, 104, 124
    groups = []
    for i, pn in enumerate(pains):
        g = f"{k}c{i}"
        x, y = -CW / 2 + (i - 1) * 14, -120 + i * G
        _group(c, g, x, y + 40, CW, CH, 30 + i)
        r.node(g + "_b", "rect", 0, 0, CW, CH, 31 + i, fill=pal.panel, stroke=pal.line, strokeWidth=1.5, cornerRadius=16,
               parentId=g, opacity=1)
        r.icon(g + "_i", "ph:warning-circle-fill", 30, 30, 44, 32 + i, color=pal.bad, parentId=g, opacity=1)
        r.text(g + "_t", 96, 0, CW - 130, CH, fit(pn, 32, CW - 130, 500)[0], 32, color=pal.body, weight=500, z=32 + i,
               parentId=g, opacity=1)
        groups.append((g, x, y))
    r.cut([m], bg=pal.field(p.get("bg")), note="cut problem", camera=_drift(1.03, 6000))
    r.step(600, "ease-out", r.rise_in(k + "ln"), note="line rise")
    r.hold(300)
    for (g, x, y), pn in zip(groups, pains):
        r.appear(g, note="pain on")
        r.step(380, "back", [dict(id=g, y=y)], note="pain in")
        r.cue("thud")
        r.hold(read_ms(pn, base=300, per_word=150, lo=600, hi=1100))
    for dx in (14, -14, 10, -6, 0):
        r.step(55, "linear", [dict(id=g, x=x + dx) for g, x, _ in groups], note="shake")
    r.hold(200)
    r.step(520, "ease-in", [dict(id=g, y=y + 900) for g, _, y in groups] + r.rise_out(k + "ln"),
           delays={g: 70 * j for j, (g, _, _) in enumerate(groups)}, note="fall away")


# ---------------- countdown ----------------
def countdown(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("label")][:5] or [{"label": "It just works"}]
    n = len(items)
    line = p.get("line") or ""
    if line:
        masks, kids, ls = _lines(c, k + "t", line, 0, 0, 64, 1100, 2)
        r.cut(masks, bg=pal.field(p.get("bg")), note="cut countdown", camera=_drift(1.04, 2400))
        r.step(600, "ease-out", r.rise_in(*kids), delays={kd: 100 * j for j, kd in enumerate(kids)}, note="title rise")
        r.hold(read_ms(*ls))
        r.step(300, "ease-in", r.rise_out(*kids), note="title out")
    fields = ["accent1", "accent2", "accent3", "paper", "accent1"]
    for j, it in enumerate(items):
        num = str(n - j)
        nid = f"{k}n{j}"
        r.text(nid, -620, -170, 460, 340, num, 280, weight=800, align="center", z=30, role="display",
               scaleX=0.6, scaleY=0.6)
        ic = it.get("icon") or "ph:sparkle-fill"
        r.icon(f"{k}i{j}", ic, -60, -150, 64, 30, color=_icon_color(ic, pal.ink))
        ls = wrap(it["label"], 50, 620, 700, 3)
        lh = 62
        ids = []
        for q, l in enumerate(ls):
            r.text(f"{k}l{j}_{q}", -60, -60 + q * lh, 680, lh, l, 50, weight=700, z=30, typeProgress=0)
            ids.append((f"{k}l{j}_{q}", l))
        show = [nid] if not line and j == 0 else [nid]
        r.cut(show, bg=pal.field(it.get("bg") or fields[j % len(fields)]), note=f"count {num}",
              camera={"c": {"x": 0, "y": 0, "zoom": 1.0}, "e": {"x": 20, "y": 0, "zoom": 1.04}, "d": 3000})
        r.step(380, "back", [dict(id=nid, scaleX=1, scaleY=1)], note="numeral pop")
        r.appear(f"{k}i{j}", note="icon on")
        for t, l in ids:
            r.type_in(t, max(260, min(520, 16 * len(l))), note="reason")
        r.hold(read_ms(it["label"], lo=900, hi=1500))


# ---------------- feature flash ----------------
def feature_flash(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("label")][:6] or [{"label": "Fast", "icon": "ph:lightning-fill"}]
    fields = ["accent1", "accent2", "accent3"]
    for j, it in enumerate(items):
        ic = it.get("icon") or "ph:sparkle-fill"
        nd = r.icon(f"{k}i{j}", ic, 0, 0, 150, 30, color=_icon_color(ic, pal.ink), scaleX=0.5, scaleY=0.5)
        r.place(nd["id"], -75, -170)
        t, s = fit(it["label"], 76, 1100)
        m = r.rise_line(f"{k}l{j}", 0, 90, t, s)
        r.cut([nd["id"], m], bg=pal.field(fields[j % 3]), note="flash",
              camera={"c": {"x": 0, "y": 0, "zoom": 1.0}, "e": {"x": 0, "y": 0, "zoom": 1.06}, "d": 1400})
        r.step(320, "back", [dict(id=nd["id"], scaleX=1, scaleY=1)] + r.rise_in(f"{k}l{j}"), note="flash pop")
        r.hold(read_ms(t, base=250, per_word=150, lo=520, hi=850))


SCENES2 = {"dashboard": dashboard, "terminal": terminal, "browser": browser, "split": split, "stat": stat,
           "kanban": kanban, "notifications": notifications, "map": map_scene, "pricing": pricing,
           "logo_grid": logo_grid, "compare": compare, "problem": problem, "countdown": countdown,
           "feature_flash": feature_flash}

SCENES.update(SCENES2)
