"""Scenes for products the first two sets did not cover: suites, stacks, plain SaaS with no AI in
it, open source, and real screenshots. Same contract as `scenes.py`.

  lineup        a suite: one tile per product, each in its own colour, icon and one-liner
  receipt       the stack it replaces: named tools and prices tick in, the total counts up,
                every line is struck through and the new price is stamped on top
  snippet       one line of install code types out, copy is pressed, the status goes live
  inbox         a mail client: emails slide in, one opens in the reading pane
  funnel        stage bars grow with their counts
  toggle        a settings panel; the switches flip on one by one
  form_builder  form fields drop in, the submit button is pressed
  repo          a GitHub repo card: open source badge, licence, stars only when given
  timeline      dated milestones along a line that draws itself
  quote         one quote, word for word from the description
  phone_app     a mobile app home screen with no AI in it: hero number, rows, an alert drops in
  screenshot    a real screenshot in a browser or phone frame; the camera visits focus points

Copy that names other companies, prices, numbers or quotes is checked against the product
description by `plan.ground()`, so nothing here invents a fact.
"""
from __future__ import annotations

import math
import re

from ._metrics import text_width as tw
from .builder import C0, _lum, _mix
from .scenes import SCENES, Ctx, _drift, _icon_color, fit, read_ms, type_ms, wrap
from .scenes2 import _NUM, _cursor, _group, _lines, _mono_fit, _press, count_frames


def _on(color: str) -> str:
    """Glyph colour that reads on a filled `color` tile."""
    return "#111111" if _lum(color) > 0.6 else "#ffffff"


def _hex(v, default: str) -> str:
    v = str(v or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.lower()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        return "#" + "".join(ch * 2 for ch in v[1:]).lower()
    return default


def product_chip(r, k: str, name: str, color: str) -> list[str]:
    """A suite product's name in a pill at the top right of its stage, part of the backdrop so
    it stays up for the whole scene."""
    pal = r.pal
    name, s = fit(name, 17, 260, 700)
    w = tw(name, s, 700) + 52
    x, y = 560 - w, -306
    r.node(k + "pc", "rect", x, y, w, 34, 80, fill=pal.panel, stroke=pal.line, strokeWidth=1, cornerRadius=17)
    r.node(k + "pcd", "circle", x + 14, y + 11, 12, 12, 81, fill=color)
    r.text(k + "pct", x + 34, y, w - 40, 34, name, s, weight=700, z=81)
    return [k + "pc", k + "pcd", k + "pct"]


def _money(v) -> float | None:
    m = _NUM.match(str(v or "").strip())
    return float(m.group(2).replace(",", "")) if m else None


def _headline(c: Ctx, line: str, cy: float, size=46, maxw=1100, bg=None):
    """An optional one-line headline above a scene, set light when the scene's field `bg` is
    dark (a suite product's own colour). Returns (masks, kids)."""
    if not line:
        return [], []
    t, s = fit(line, size, maxw)
    field = c.pal.field(bg)
    color = _on(field) if _lum(field) < 0.4 else None
    return [c.r.rise_line(c.k + "hd", 0, cy, t, s, color=color)], [c.k + "hd"]


def _rise(c: Ctx, kids: list[str]):
    if kids:
        c.r.step(560, "ease-out", c.r.rise_in(*kids), delays={kd: 90 * j for j, kd in enumerate(kids)},
                 note="line rise")


# ---------------- lineup ----------------
def lineup(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    prods = [x for x in (p.get("products") or []) if x.get("name")][:6] or [{"name": c.brand["name"]}]
    n = len(prods)
    cols = n if n <= 4 else 3
    rows = math.ceil(n / cols)
    G = 24
    TW = min(340, (1120 - G * (cols - 1)) / cols)
    TH = 236 if rows == 1 else 196
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -300 if rows > 1 else -250, bg=p.get("bg"))
    top = -(rows * TH + (rows - 1) * G) / 2 + (30 if line else 0)
    groups = []
    for i, pr in enumerate(prods):
        row, col = divmod(i, cols)
        in_row = min(cols, n - row * cols)
        x0 = -(in_row * TW + (in_row - 1) * G) / 2
        x, y = x0 + col * (TW + G), top + row * (TH + G)
        g = f"{k}t{i}"
        col_hex = _hex(pr.get("color"), pal.accents[i % len(pal.accents)])
        _group(c, g, x, y + 60, TW, TH, 30 + i)
        r.node(g + "_b", "rect", 0, 0, TW, TH, 31, fill=pal.panel, stroke=pal.line, strokeWidth=1.2,
               cornerRadius=20, parentId=g, opacity=1)
        r.node(g + "_bar", "rect", 0, 0, TW, 8, 32, fill=col_hex, parentId=g, opacity=1)
        r.node(g + "_s", "rect", 24, 30, 60, 60, 32, fill=col_hex, cornerRadius=16, parentId=g, opacity=1)
        ic = pr.get("icon") or "ph:cube-fill"
        r.icon(g + "_i", ic, 38, 44, 32, 33, color=_icon_color(ic, _on(col_hex)), parentId=g, opacity=1)
        r.text(g + "_n", 24, 104, TW - 48, 40, fit(pr["name"], 27, TW - 48, 700)[0], 27, weight=700, z=33,
               parentId=g, opacity=1)
        for j, l in enumerate(wrap(pr.get("desc") or "", 17, TW - 48, 500, 2 if rows > 1 else 3)):
            r.text(f"{g}_d{j}", 24, 146 + j * 24, TW - 48, 24, l, 17, color=pal.grey, weight=500, z=33,
                   parentId=g, opacity=1)
        groups.append((g, y))
    r.cut(masks, bg=pal.field(p.get("bg")), note="cut lineup", camera=_drift(1.04, 6000))
    _rise(c, kids)
    for i, (g, y) in enumerate(groups):
        r.appear(g, note="tile on")
        r.step(460, "back", [dict(id=g, y=y)], note="tile in")
        r.cue("pop", n=i)
        r.hold(120)
    r.hold(read_ms(*[x.get("desc") for x in prods], base=300, per_word=60, lo=1300, hi=2400))


# ---------------- receipt ----------------
def receipt(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("name") and x.get("price")][:6]
    if not items:
        items = [{"name": "Your current tools", "price": p.get("total") or "$99/mo"}]
    total = str(p.get("total") or "")
    if not total:
        vals = [_money(x["price"]) for x in items]
        if all(v is not None for v in vals):
            m = _NUM.match(str(items[0]["price"]).strip())
            total = f"{m.group(1)}{sum(vals):,.0f}{m.group(3)}"
    new = str(p.get("new_price") or "")
    W, RH = 600, 56
    n = len(items)
    H = 96 + n * RH + 30 + (RH + 10 if total else 0) + 30
    X0, Y0 = -W / 2, -H / 2 + 20
    line = p.get("line") or ""
    masks, kids = _headline(c, line, Y0 - 52, 40, bg=p.get("bg"))
    r.node(k + "pp", "rect", X0, Y0, W, H, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=6,
           dropShadow=dict(dx=0, dy=14, color="rgba(0,0,0,0.12)", radius=36))
    title = fit(p.get("title") or "Your stack today", 22, W - 80, 700)[0]
    r.text(k + "ti", X0 + 40, Y0 + 26, W - 80, 36, title, 22, weight=700, z=23)
    r.node(k + "dv0", "rect", X0 + 40, Y0 + 80, W - 80, 1.5, 23, fill=pal.line)
    rows, strikes = [], []
    for i, it in enumerate(items):
        y = Y0 + 96 + i * RH
        price = _mono_fit(str(it["price"]), 22, 170)
        r.text(f"{k}nm{i}", X0 + 40, y, W - 260, RH, fit(it["name"], 22, W - 260, 500)[0], 22, color=pal.body,
               weight=500, z=23)
        r.text(f"{k}pr{i}", X0 + W - 210, y, 170, RH, price, 22, weight=600, align="right", z=23, role="mono")
        r.node(f"{k}st{i}", "rect", X0 + 30, y + RH / 2 - 1.5, 0, 3, 25, fill=pal.bad, cornerRadius=2)
        rows.append([f"{k}nm{i}", f"{k}pr{i}"])
        strikes.append(f"{k}st{i}")
    ty = Y0 + 96 + n * RH + 14
    r.node(k + "dv1", "rect", X0 + 40, ty, W - 80, 1.5, 23, fill=pal.line)
    frames = []
    if total:
        r.text(k + "tl", X0 + 40, ty + 14, 200, RH, "Total", 24, weight=700, z=23)
        frames = count_frames(c, k + "tt", _mono_fit(total, 28, 260), X0 + W - 300, ty + 14, 260, RH, 28, n=14,
                              weight=700, align="right", z=23, role="mono")
        r.node(k + "stt", "rect", X0 + 30, ty + 14 + RH / 2 - 1.5, 0, 3, 25, fill=pal.bad, cornerRadius=2)
        strikes.append(k + "stt")
    # the stamp
    stamp = []
    if new:
        nv, ns = fit(new, 64, 420, 800)
        sw = tw(nv, ns, 800) + 90
        lab = fit(p.get("new_label") or c.brand["name"], 20, sw - 40, 700)[0]
        sx, sy = -sw / 2 + 60, Y0 + H / 2 - 30
        acc = pal.accents[0]
        r.node(k + "sp", "rect", sx, sy, sw, 150, 40, fill=_mix(acc, pal.panel, 0.85), stroke=acc, strokeWidth=5,
               cornerRadius=14, rotationZ=-7, scaleX=1.7, scaleY=1.7)
        r.text(k + "sv", sx, sy + 12, sw, 86, nv, ns, color=acc, weight=800, align="center", z=41, rotationZ=-7,
               scaleX=1.7, scaleY=1.7, role="display")
        r.text(k + "sl", sx, sy + 96, sw, 36, lab, 20, color=acc, weight=700, align="center", z=41, rotationZ=-7,
               scaleX=1.7, scaleY=1.7, letterSpacing=1)
        stamp = [k + "sp", k + "sv", k + "sl"]
    r.cut(masks + [k + "pp", k + "ti", k + "dv0"], bg=pal.field(p.get("bg")), note="cut receipt",
          camera=_drift(1.04, 7000))
    _rise(c, kids)
    for i, rw in enumerate(rows):
        r.appear(*rw, note="line item")
        r.cue("tick", n=i)
        r.hold(read_ms(items[i]["name"], base=150, per_word=60, lo=320, hi=520))
    r.appear(k + "dv1", *([k + "tl", frames[0]] if frames else []), note="total on")
    r.count(frames, 900)
    r.hold(500)
    r.appear(*strikes, note="strikes on")
    r.step(520, "ease-out", [dict(id=s, w=W - 60) for s in strikes], delays={s: j * 70 for j, s in enumerate(strikes)},
           note="strike through")
    r.cue("whoosh")
    r.hold(350)
    if stamp:
        r.appear(*stamp, note="stamp on")
        r.step(260, "ease-in", [dict(id=s, scaleX=1, scaleY=1) for s in stamp], note="stamp")
        r.cue("thud")
        r.step(160, "ease-out", [dict(id=s, scaleX=1.04, scaleY=1.04) for s in stamp], note="stamp settle")
        r.step(160, "ease", [dict(id=s, scaleX=1, scaleY=1) for s in stamp], note="stamp settle")
    r.hold(1500)


# ---------------- snippet ----------------
def snippet(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -230, bg=p.get("bg"))
    W, H = 1020, 150
    X0, Y0 = -W / 2, -90
    dark = "#16181d"
    r.node(k + "cd", "rect", X0, Y0, W, H, 21, fill=dark, cornerRadius=18,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.16)", radius=40))
    fname = fit(p.get("label") or "index.html", 15, 400, 500)[0]
    r.text(k + "fn", X0 + 28, Y0 + 14, 400, 30, fname, 15, color="#8b93a1", weight=500, z=23, role="mono")
    code = _mono_fit(p.get("code") or f'<script src="https://cdn.{c.brand["name"].lower()}.com/v1.js"></script>',
                     21, W - 190)
    r.text(k + "cx", X0 + 28, Y0 + 60, W - 190, 60, code, 21, color="#e6e9ef", weight=500, z=23, role="mono",
           typeProgress=0)
    BW = 120
    bx, by = X0 + W - BW - 24, Y0 + 66
    r.node(k + "cb", "rect", bx, by, BW, 46, 23, fill="#2a2e37", cornerRadius=12, label="Copy", labelColor="#e6e9ef",
           labelFontSize=17, labelFontWeight=600, fontSize=17, fontFamily=r.style.body, labelFontFamily=r.style.body)
    r.node(k + "cb2", "rect", bx, by, BW, 46, 24, fill=pal.good, cornerRadius=12, label="Copied", labelColor="#ffffff",
           labelFontSize=17, labelFontWeight=600, fontSize=17, fontFamily=r.style.body, labelFontFamily=r.style.body)
    cur = _cursor(c, k + "cur", bx + 260, by + 160)
    status = fit(p.get("status") or "Live", 22, 360, 700)[0]
    sw = tw(status, 22, 700) + 90
    sx, sy = -sw / 2, Y0 + H + 60
    r.node(k + "ring", "circle", sx + 20, sy + 12, 24, 24, 22, fill=_mix(pal.good, pal.panel, 0.5))
    r.node(k + "sp", "rect", sx, sy, sw, 50, 23, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=25,
           scaleX=0.6, scaleY=0.6)
    r.node(k + "dot", "circle", sx + 24, sy + 16, 16, 16, 24, fill=pal.good, scaleX=0.6, scaleY=0.6)
    r.text(k + "stx", sx + 52, sy, sw - 64, 50, status, 22, weight=700, z=24, scaleX=0.6, scaleY=0.6)
    pill = [k + "sp", k + "dot", k + "stx"]
    r.cut(masks + [k + "cd", k + "fn", k + "cb"], bg=pal.field(p.get("bg") or "accent2"), note="cut snippet",
          camera={"c": {"x": 0, "y": 0, "zoom": 1.08}, "e": {"x": 0, "y": 20, "zoom": 1.02}, "d": 6000})
    _rise(c, kids)
    ms = type_ms(code, per_char=20, lo=700, hi=1500)
    r.cue("type")
    r.type_in(k + "cx", ms, note="code types")
    r.appear(cur, note="cursor on")
    r.step(520, "ease", [dict(id=cur, x=bx + 70, y=by + 22)], note="cursor to copy")
    _press(c, [k + "cb"], note="copy press")
    r.cue("click")
    r.appear(k + "cb2", note="copied")
    r.hold(350)
    r.step(380, "ease", [dict(id=cur, x=bx + 200, y=by + 230)], note="cursor away")
    r.appear(*pill, k + "ring", note="live on")
    r.step(420, "back", [dict(id=i, scaleX=1, scaleY=1) for i in pill], note="live pop")
    r.cue("ding")
    r.step(900, "ease-out", [dict(id=k + "ring", scaleX=3, scaleY=3, opacity=0)], note="pulse")
    r.hold(read_ms(line, status, lo=900, hi=1400))


# ---------------- inbox ----------------
def inbox(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("subject")][:4] or [{"from": c.brand["name"],
                                                                            "subject": "Welcome"}]
    opn = max(0, min(len(items) - 1, int(p.get("open") or 0)))
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -300, 40, bg=p.get("bg"))
    W, H = 1120, 520
    X0, Y0 = -W / 2, -H / 2 + (30 if line else 0)
    LW, RH = 440, 96
    r.node(k + "fr", "rect", X0, Y0, W, H, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=18,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.12)", radius=40))
    r.node(k + "sep", "rect", X0 + LW, Y0, 1.2, H, 22, fill=pal.line)
    r.text(k + "ib", X0 + 28, Y0 + 14, 300, 40, "Inbox", 22, weight=700, z=23)
    r.icon(k + "ibi", "ph:tray-fill", X0 + LW - 52, Y0 + 22, 24, 23, color=pal.grey)
    LY = Y0 + 62
    rows = []
    for i, it in enumerate(items):
        g = f"{k}m{i}"
        _group(c, g, X0 + 1, LY, LW - 2, RH, 30 + i)
        kid = [(r.node(g + "_b", "rect", 0, 0, LW - 2, RH, 31, fill=pal.panel, parentId=g, opacity=1), 0)]
        kid.append((r.node(g + "_d", "circle", 18, 22, 10, 10, 32, fill=pal.accents[0], parentId=g, opacity=1), 22))
        kid.append((r.text(g + "_f", 40, 8, LW - 130, 30, fit(it.get("from") or "", 17, LW - 130, 700)[0], 17,
                           weight=700, z=32, parentId=g, opacity=1), 8))
        kid.append((r.text(g + "_w", LW - 90, 8, 70, 30, "now", 14, color=pal.faint, weight=500, align="right", z=32,
                           parentId=g, opacity=1), 8))
        kid.append((r.text(g + "_s", 40, 36, LW - 60, 28, fit(it["subject"], 17, LW - 60, 600)[0], 17, color=pal.body,
                           weight=600, z=32, parentId=g, opacity=1), 36))
        kid.append((r.text(g + "_p", 40, 62, LW - 60, 26, fit(it.get("preview") or "", 15, LW - 60, 500)[0], 15,
                           color=pal.grey, weight=500, z=32, parentId=g, opacity=1), 62))
        kid.append((r.node(g + "_l", "rect", 0, RH - 1, LW, 1, 32, fill=pal.line, parentId=g, opacity=1), RH - 1))
        for nd, y in kid:
            nd["y"] = y - RH
        rows.append((g, [(nd["id"], y) for nd, y in kid]))
    # reading pane
    it = items[opn]
    PX, PW = X0 + LW + 40, W - LW - 80
    sub = wrap(it["subject"], 28, PW, 700, 2)
    pane = []
    for j, s in enumerate(sub):
        r.text(f"{k}ps{j}", PX, Y0 + 40 + j * 38, PW, 38, s, 28, weight=700, z=23)
        pane.append(f"{k}ps{j}")
    fy = Y0 + 50 + len(sub) * 38
    frm = it.get("from") or ""
    r.node(k + "av", "circle", PX, fy, 40, 40, 23, fill=pal.accents[1 % len(pal.accents)], label=(frm[:1] or "?").upper(),
           labelColor=_on(pal.accents[1 % len(pal.accents)]), labelFontSize=18, labelFontWeight=700, fontSize=18,
           fontFamily=r.style.body, labelFontFamily=r.style.body)
    r.text(k + "pf", PX + 54, fy, PW - 54, 40, fit(frm, 17, PW - 54, 600)[0], 17, weight=600, z=23)
    pane += [k + "av", k + "pf"]
    body = wrap(it.get("preview") or "", 19, PW, 500, 3)
    for j, s in enumerate(body):
        r.text(f"{k}pb{j}", PX, fy + 70 + j * 30, PW, 30, s, 19, color=pal.body, weight=500, z=23)
        pane.append(f"{k}pb{j}")
    for j in range(3):
        r.node(f"{k}pl{j}", "rect", PX, fy + 90 + len(body) * 30 + j * 24, PW * (0.95 - 0.2 * j), 10, 23,
               fill=pal.line, cornerRadius=5)
        pane.append(f"{k}pl{j}")
    r.cut(masks + [k + "fr", k + "sep", k + "ib", k + "ibi"], bg=pal.field(p.get("bg")), note="cut inbox",
          camera={"c": {"x": -140, "y": 0, "zoom": 1.12}, "e": {"x": -120, "y": 0, "zoom": 1.1}, "d": 4000})
    _rise(c, kids)
    shown = []
    for i, (g, kd) in enumerate(rows):
        # the new mail rolls down into the top slot, the ones already there move down a row
        moves = [dict(id=i_, y=y) for i_, y in kd] + [dict(id=s_, y=LY + RH * (len(shown) - j))
                                                   for j, s_ in enumerate(shown)]
        r.appear(g, note="mail on")
        r.step(420, "back", moves, note="mail in")
        r.cue("ding" if i == 0 else "pop", n=i)
        shown.append(g)
        r.hold(read_ms(items[i]["subject"], base=150, per_word=70, lo=420, hi=800))
    og = rows[opn][0]
    r.step(520, "ease", note="to pane", camera={"e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 520, "ease": "ease"})
    r.step(200, "ease", [dict(id=og + "_b", fill=pal.highlight), dict(id=og + "_d", opacity=0)], note="open mail")
    r.cue("click")
    r.appear(*pane, note="pane on")
    r.hold(read_ms(it["subject"], it.get("preview"), lo=1400, hi=2200))


# ---------------- funnel ----------------
def funnel(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    stages = [x for x in (p.get("stages") or []) if x.get("label")][:5] or [{"label": "Visitors", "value": "100"}]
    vals = [_money(x.get("value")) for x in stages]
    top_v = max([v for v in vals if v] or [1])
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -280, 42, bg=p.get("bg"))
    LW, BW, VW = 260, 640, 180
    X0 = -(LW + BW + VW) / 2
    RH = 74 if len(stages) <= 4 else 64
    top = -(len(stages) * RH) / 2 + (40 if line else 0)
    r.node(k + "pn", "rect", X0 - 30, top - 26, LW + BW + VW + 60, len(stages) * RH + 38, 21, fill=pal.panel,
           stroke=pal.line, strokeWidth=1.2, cornerRadius=18,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.10)", radius=40))
    bars, frames, labels = [], [], [k + "pn"]
    for i, st in enumerate(stages):
        y = top + i * RH
        r.text(f"{k}l{i}", X0, y, LW - 20, RH - 14, fit(st["label"], 22, LW - 20, 600)[0], 22, color=pal.body,
               weight=600, align="right", z=24)
        frac = (vals[i] / top_v) if vals[i] else 0.5
        acc = pal.accents[i % len(pal.accents)]
        r.node(f"{k}b{i}", "rect", X0 + LW, y + 6, 0, RH - 26, 23, fill=acc, cornerRadius=10)
        bars.append((f"{k}b{i}", max(14, BW * frac)))
        fr = count_frames(c, f"{k}v{i}", _mono_fit(str(st.get("value") or ""), 24, VW - 20), X0 + LW + BW + 20, y,
                          VW - 20, RH - 14, 24, n=12, weight=700, z=24, role="mono")
        frames.append(fr)
        labels.append(f"{k}l{i}")
    r.cut(masks + labels, bg=pal.field(p.get("bg")), note="cut funnel", camera=_drift(1.04, 6000))
    _rise(c, kids)
    r.appear(*[b for b, _ in bars], *[f[0] for f in frames], note="bars on")
    r.step(900, "ease-out", [dict(id=b, w=w) for b, w in bars], delays={b: j * 110 for j, (b, _) in enumerate(bars)},
           note="bars grow")
    longest = max(len(f) for f in frames)
    r.count([f + [f[-1]] * (longest - len(f)) for f in frames], 900)
    r.hold(read_ms(*[s["label"] for s in stages], lo=1300, hi=2000))


# ---------------- toggle ----------------
def toggle(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("label")][:5] or [{"label": "Enabled"}]
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -290, 42, bg=p.get("bg"))
    W, RH = 760, 88
    H = 70 + len(items) * RH + 10
    X0, Y0 = -W / 2, -H / 2 + (34 if line else 0)
    r.node(k + "pn", "rect", X0, Y0, W, H, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=18,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.10)", radius=40))
    r.icon(k + "gi", "ph:gear-six-fill", X0 + 28, Y0 + 22, 26, 23, color=pal.grey)
    r.text(k + "pt", X0 + 66, Y0 + 14, W - 100, 42, fit(p.get("title") or "Settings", 21, W - 100, 700)[0], 21,
           weight=700, z=23)
    static = [k + "pn", k + "gi", k + "pt"]
    flips = []
    TWD, THT = 64, 36
    for i, it in enumerate(items):
        y = Y0 + 70 + i * RH
        r.node(f"{k}rl{i}", "rect", X0 + 28, y, W - 56, 1.2, 22, fill=pal.line)
        sub = it.get("sub") or ""
        r.text(f"{k}lb{i}", X0 + 28, y + (12 if sub else 22), W - 180, 34, fit(it["label"], 21, W - 180, 600)[0], 21,
               weight=600, z=23)
        static += [f"{k}rl{i}", f"{k}lb{i}"]
        if sub:
            r.text(f"{k}sb{i}", X0 + 28, y + 46, W - 180, 28, fit(sub, 16, W - 180, 500)[0], 16, color=pal.grey,
                   weight=500, z=23)
            static.append(f"{k}sb{i}")
        tx, ty = X0 + W - 28 - TWD, y + (RH - THT) / 2
        r.node(f"{k}tr{i}", "rect", tx, ty, TWD, THT, 23, fill=pal.disabled, cornerRadius=THT / 2)
        r.node(f"{k}to{i}", "rect", tx, ty, TWD, THT, 24, fill=pal.good, cornerRadius=THT / 2)
        r.node(f"{k}kn{i}", "circle", tx + 4, ty + 4, THT - 8, THT - 8, 25, fill="#ffffff",
               dropShadow=dict(dx=0, dy=2, color="rgba(0,0,0,0.2)", radius=4))
        static += [f"{k}tr{i}", f"{k}kn{i}"]
        flips.append((f"{k}to{i}", f"{k}kn{i}", tx + TWD - THT + 4))
    r.cut(masks + static, bg=pal.field(p.get("bg")), note="cut toggle",
          camera={"c": {"x": 0, "y": 0, "zoom": 1.0}, "e": {"x": 0, "y": 10, "zoom": 1.06}, "d": 6000})
    _rise(c, kids)
    r.hold(300)
    for i, (on, kn, kx) in enumerate(flips):
        r.appear(on, note="switch on")
        r.step(240, "ease-out", [dict(id=kn, x=kx)], note="knob")
        r.cue("click", n=i)
        r.hold(read_ms(items[i]["label"], base=120, per_word=60, lo=320, hi=560))
    r.hold(1100)


# ---------------- form builder ----------------
_FIELD_ICONS = {"email": "ph:at-bold", "select": "ph:caret-down-bold", "date": "ph:calendar-blank-bold",
                "number": "ph:hash-bold", "checkbox": "ph:check-square-bold", "file": "ph:paperclip-bold",
                "phone": "ph:phone-bold", "rating": "ph:star-bold", "text": "ph:text-aa-bold"}


def form_builder(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    fields = [x for x in (p.get("fields") or []) if x.get("label")][:4] or [{"label": "Email", "type": "email"}]
    line = p.get("line") or ""
    W, FH = 600, 92
    H = 96 + len(fields) * FH + 90
    X0 = (-W / 2 + 180) if line else -W / 2
    Y0 = -H / 2
    masks, kids, _ = _lines(c, k + "l", line, -390, 0, 50, 420, 3) if line else ([], [], [])
    r.node(k + "cd", "rect", X0, Y0, W, H, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=18,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.10)", radius=40))
    r.text(k + "ft", X0 + 36, Y0 + 26, W - 72, 44, fit(p.get("title") or "Get in touch", 26, W - 72, 700)[0], 26,
           weight=700, z=23)
    groups = []
    for i, f in enumerate(fields):
        g = f"{k}f{i}"
        y = Y0 + 96 + i * FH
        _group(c, g, X0 + 36, y - 120, W - 72, FH - 10, 30 + i)
        r.text(g + "_l", 0, 0, W - 72, 26, fit(f["label"], 16, W - 72, 600)[0], 16, color=pal.body, weight=600, z=31,
               parentId=g, opacity=1)
        r.node(g + "_in", "rect", 0, 30, W - 72, 48, 31, fill=pal.soft, stroke=pal.line, strokeWidth=1.2,
               cornerRadius=10, parentId=g, opacity=1)
        ic = _FIELD_ICONS.get(str(f.get("type") or "text").lower(), "ph:text-aa-bold")
        r.icon(g + "_i", ic, W - 72 - 40, 42, 22, 32, color=pal.faint, parentId=g, opacity=1)
        groups.append((g, y))
    by = Y0 + 96 + len(fields) * FH + 10
    btn = fit(p.get("button") or "Submit", 19, W - 120, 600)[0]
    r.node(k + "bt", "rect", X0 + 36, by, W - 72, 54, 23, fill=pal.accents[0], cornerRadius=12, label=btn,
           labelColor=_on(pal.accents[0]), labelFontSize=19, labelFontWeight=600, fontSize=19,
           fontFamily=r.style.body, labelFontFamily=r.style.body)
    r.node(k + "ok", "rect", X0 + 36, by, W - 72, 54, 24, fill=pal.good, cornerRadius=12,
           label=fit(p.get("done") or "Sent", 19, W - 120, 600)[0], labelColor="#ffffff", labelFontSize=19,
           labelFontWeight=600, fontSize=19, fontFamily=r.style.body, labelFontFamily=r.style.body)
    cur = _cursor(c, k + "cur", X0 + W + 60, by + 160)
    r.cut(masks + [k + "cd", k + "ft"], bg=pal.field(p.get("bg") or "accent1"), note="cut form",
          camera={"c": C0, "e": {"x": 0, "y": 10, "zoom": 1.05}, "d": 6000})
    _rise(c, kids)
    for i, (g, y) in enumerate(groups):
        r.appear(g, note="field on")
        r.step(420, "back", [dict(id=g, y=y)], note="field drops")
        r.cue("pop", n=i)
        r.hold(150)
    r.appear(k + "bt", cur, note="button on")
    r.step(560, "ease", [dict(id=cur, x=X0 + W / 2 + 40, y=by + 22)], note="cursor to submit")
    _press(c, [k + "bt"], note="submit")
    r.cue("click")
    r.appear(k + "ok", note="sent")
    r.cue("ding")
    r.hold(1300)


# ---------------- repo ----------------
def repo(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    name = p.get("name") or c.brand["name"].lower()
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -260, 46, bg=p.get("bg"))
    W, H = 860, 290
    X0, Y0 = -W / 2, -H / 2 + (40 if line else 0)
    r.node(k + "cd", "rect", X0, Y0, W, H, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.2, cornerRadius=16,
           dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.12)", radius=40))
    r.icon(k + "gh", "logos:github-icon", X0 + 36, Y0 + 34, 44, 23)
    owner, _, rn = name.rpartition("/")
    r.text(k + "nm", X0 + 96, Y0 + 30, W - 330, 52,
           fit((owner + " / " if owner else "") + rn, 28, W - 330, 600)[0], 28, color=pal.link, weight=600, z=23)
    static = [k + "cd", k + "gh", k + "nm"]
    pills = []
    px = X0 + 36
    for j, (ic, lab) in enumerate((("ph:lock-open-bold", "Open source"),) +
                                  ((("ph:scales-bold", p["license"] + " license"),) if p.get("license") else ()) +
                                  ((("ph:code-bold", p["language"]),) if p.get("language") else ())):
        lab = fit(lab, 16, 260, 600)[0]
        w = tw(lab, 16, 600) + 64
        g = f"{k}pl{j}"
        r.node(g, "rect", px, Y0 + 200, w, 40, 23, fill=_mix(pal.accents[0], pal.panel, 0.82), cornerRadius=20,
               scaleX=0.5, scaleY=0.5)
        r.icon(g + "i", ic, px + 14, Y0 + 210, 20, 24, color=pal.accents[0], scaleX=0.5, scaleY=0.5)
        r.text(g + "t", px + 40, Y0 + 200, w - 48, 40, lab, 16, color=pal.body, weight=600, z=24, scaleX=0.5,
               scaleY=0.5)
        pills.append([g, g + "i", g + "t"])
        px += w + 12
    desc = wrap(p.get("desc") or "", 20, W - 72, 500, 2)
    dsc = []
    for j, d in enumerate(desc):
        r.text(f"{k}ds{j}", X0 + 36, Y0 + 100 + j * 32, W - 72, 32, d, 20, color=pal.body, weight=500, z=23)
        dsc.append(f"{k}ds{j}")
    stars = str(p.get("stars") or "").strip()
    star_btn = []
    frames = []
    if stars:
        bx = X0 + W - 210
        r.node(k + "sb", "rect", bx, Y0 + 32, 174, 46, 23, fill=pal.soft, stroke=pal.line, strokeWidth=1.2,
               cornerRadius=10)
        r.icon(k + "si", "ph:star-fill", bx + 16, Y0 + 44, 22, 24, color="#e3b341")
        frames = count_frames(c, k + "sc", _mono_fit(stars, 18, 110), bx + 48, Y0 + 32, 110, 46, 18, n=14, weight=700,
                              z=24, role="mono")
        star_btn = [k + "sb", k + "si"]
    r.cut(masks + static, bg=pal.field(p.get("bg") or "accent3"), note="cut repo",
          camera={"c": {"x": 0, "y": 0, "zoom": 1.06}, "e": {"x": 0, "y": 10, "zoom": 1.0}, "d": 5000})
    _rise(c, kids)
    for d in dsc:
        r.appear(d, note="desc")
        r.hold(160)
    for i, pl in enumerate(pills):
        r.appear(*pl, note="badge on")
        r.step(360, "back", [dict(id=x, scaleX=1, scaleY=1) for x in pl], note="badge pop")
        r.cue("pop", n=i)
    if star_btn:
        r.appear(*star_btn, frames[0], note="stars on")
        r.count(frames, 1000)
    r.hold(read_ms(line, *desc, lo=1200, hi=2000))


# ---------------- timeline ----------------
def timeline(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    items = [x for x in (p.get("items") or []) if x.get("label")][:5] or [{"date": "Today", "label": "Launch"}]
    n = len(items)
    line = p.get("line") or ""
    masks, kids = _headline(c, line, -230, 48, bg=p.get("bg"))
    W = 1080
    X0, LY = -W / 2, 20
    gap = W / max(1, n - 1) if n > 1 else 0
    xs = [X0 + gap * i for i in range(n)] if n > 1 else [0]
    r.node(k + "tr", "rect", X0, LY - 3, W, 6, 21, fill=pal.line, cornerRadius=3)
    r.node(k + "pr", "rect", X0, LY - 3, 0, 6, 22, fill=pal.accents[0], cornerRadius=3)
    marks = []
    for i, (x, it) in enumerate(zip(xs, items)):
        last = i == n - 1
        acc = pal.accents[0]
        d = 34 if last else 24
        r.node(f"{k}d{i}", "circle", x - d / 2, LY - d / 2, d, d, 23, fill=pal.good if last else acc,
               stroke=pal.panel, strokeWidth=4, scaleX=0.3, scaleY=0.3)
        cw = min(280, gap - 16) if n > 1 else 400
        ax = max(X0 - 40, min(X0 + W + 40 - cw, x - cw / 2))
        r.text(f"{k}dt{i}", ax, LY - 92, cw, 36, fit(it.get("date") or "", 17, cw, 600)[0], 17, color=pal.grey,
               weight=600, align="center", z=23, role="mono")
        ls = wrap(it["label"], 21, cw, 700, 2)
        ids = [f"{k}d{i}", f"{k}dt{i}"]
        for j, l in enumerate(ls):
            r.text(f"{k}lb{i}_{j}", ax, LY + 34 + j * 28, cw, 28, l, 21, weight=700, align="center", z=23)
            ids.append(f"{k}lb{i}_{j}")
        marks.append((x, ids))
    r.cut(masks + [k + "tr"], bg=pal.field(p.get("bg")), note="cut timeline",
          camera={"c": {"x": X0 + 200, "y": 0, "zoom": 1.25}, "e": {"x": 0, "y": 0, "zoom": 1.0}, "d": 600})
    _rise(c, kids)
    r.appear(k + "pr", note="progress on")
    for i, (x, ids) in enumerate(marks):
        if i:
            r.step(480, "ease", [dict(id=k + "pr", w=x - X0)], note="progress")
        r.appear(*ids, note="milestone")
        r.step(320, "back", [dict(id=ids[0], scaleX=1, scaleY=1)], note="dot pop")
        r.cue("pop" if i < len(marks) - 1 else "ding", n=i)
        r.hold(read_ms(items[i]["label"], base=150, per_word=90, lo=420, hi=800))
    r.hold(1300)


# ---------------- quote ----------------
def quote(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    q = " ".join(str(p.get("quote") or "").split()).strip(' "“”')
    ls = wrap(q, 44, 960, 600, 4)
    size = 44 if len(ls) <= 3 else 38
    ls = wrap(q, size, 960, 600, 4)
    lh = size * 1.3
    y0 = -(len(ls) * lh) / 2 - 30
    r.icon(k + "qm", "ph:quotes-fill", -520, y0 - 60, 80, 22, color=pal.accents[0], scaleX=0.4, scaleY=0.4)
    masks, kids = [], []
    for i, l in enumerate(ls):
        masks.append(r.rise_line(f"{k}q{i}", 0, y0 + i * lh + lh / 2, l, size))
        kids.append(f"{k}q{i}")
    who = [x for x in (p.get("author"), p.get("role")) if x]
    att = []
    if who:
        r.node(k + "ar", "rect", -30, y0 + len(ls) * lh + 30, 60, 3, 22, fill=pal.accents[0])
        r.text(k + "at", -500, y0 + len(ls) * lh + 46, 1000, 34, fit(" · ".join(who), 20, 1000, 600)[0], 20,
               color=pal.grey, weight=600, align="center", z=22)
        att = [k + "ar", k + "at"]
    r.cut(masks, bg=pal.field(p.get("bg") or "paper"), note="cut quote", camera=_drift(1.04, 7000))
    r.appear(k + "qm", note="quote mark")
    r.step(380, "back", [dict(id=k + "qm", scaleX=1, scaleY=1)], note="mark pop")
    r.step(620, "ease-out", r.rise_in(*kids), delays={kd: 120 * j for j, kd in enumerate(kids)}, note="quote rise")
    if att:
        r.hold(300)
        r.appear(*att, note="attribution")
    r.hold(read_ms(q, base=600, per_word=200, lo=1800, hi=3600))


# ---------------- phone app ----------------
def phone_app(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    line = p.get("line") or ""
    PHW, PHH = 360, 720
    PHX = (-PHW / 2 + 230) if line else -PHW / 2
    PHY = -PHH / 2
    masks, kids, _ = _lines(c, k + "l", line, -300, 0, 52, 460, 3) if line else ([], [], [])
    r.node(k + "ph", "rect", PHX, PHY, PHW, PHH, 26, fill=pal.bezel, cornerRadius=56,
           dropShadow=dict(dx=0, dy=18, color="rgba(0,0,0,0.2)", radius=40))
    r.node(k + "scr", "rect", PHX + 11, PHY + 11, PHW - 22, PHH - 22, 27, fill=pal.panel, cornerRadius=46)
    r.node(k + "nt", "rect", PHX + PHW / 2 - 54, PHY + 24, 108, 30, 28, fill=pal.bezel, cornerRadius=15)
    r.text(k + "tm", PHX + 40, PHY + 22, 80, 34, "9:41", 15, weight=700, z=28)
    IX, IW = PHX + 30, PHW - 60
    r.text(k + "ti", IX, PHY + 74, IW, 40, fit(p.get("title") or c.brand["name"], 24, IW, 700)[0], 24, weight=700,
           z=28)
    frame = [k + "ph", k + "scr", k + "nt", k + "tm", k + "ti"]
    acc = pal.accents[0]
    r.node(k + "hc", "rect", IX, PHY + 128, IW, 150, 28, fill=acc, cornerRadius=22, scaleX=0.9, scaleY=0.9)
    r.text(k + "hl", IX + 22, PHY + 142, IW - 44, 28, fit(p.get("value_label") or "", 15, IW - 44, 600)[0], 15,
           color=_on(acc), weight=600, z=29)
    frames = count_frames(c, k + "hv", _mono_fit(str(p.get("value") or ""), 52, IW - 44) or " ", IX + 22, PHY + 176,
                          IW - 44, 80, 52, n=14, color=_on(acc), weight=800, z=29, role="display")
    rows = []
    for i, it in enumerate([x for x in (p.get("rows") or []) if x.get("label")][:4]):
        g = f"{k}r{i}"
        y = PHY + 300 + i * 74
        _group(c, g, IX + 40, y, IW, 64, 30 + i)
        r.node(g + "_b", "rect", 0, 0, IW, 64, 31, fill=pal.soft, cornerRadius=16, parentId=g, opacity=1)
        ic = it.get("icon") or "ph:circle-fill"
        r.icon(g + "_i", ic, 16, 20, 24, 32, color=_icon_color(ic, pal.accents[i % len(pal.accents)]), parentId=g,
               opacity=1)
        val = fit(str(it.get("value") or ""), 16, 110, 700)[0]
        vw = tw(val, 16, 700) if val else 0
        r.text(g + "_t", 52, 0, IW - 72 - vw, 64, fit(it["label"], 16, IW - 72 - vw, 600)[0], 16, weight=600, z=32,
               parentId=g, opacity=1)
        if val:
            r.text(g + "_v", IW - 16 - vw, 0, vw, 64, val, 16, color=pal.grey, weight=700, align="right", z=32,
                   parentId=g, opacity=1)
        rows.append((g, IX))
    r.node(k + "tab", "rect", PHX + 11, PHY + PHH - 92, PHW - 22, 70, 29, fill=pal.panel, stroke=pal.line,
           strokeWidth=1)
    for j, ic in enumerate(("ph:house-fill", "ph:chart-bar-bold", "ph:bell-bold", "ph:user-bold")):
        r.icon(f"{k}tb{j}", ic, PHX + 40 + j * (PHW - 80 - 26) / 3, PHY + PHH - 72, 26, 30,
               color=acc if j == 0 else pal.faint)
        frame.append(f"{k}tb{j}")
    frame.append(k + "tab")
    alert = p.get("alert") or {}
    al = []
    if alert.get("title"):
        g = k + "al"
        _group(c, g, PHX + 16, PHY - 120, PHW - 32, 84, 50)
        r.node(g + "_b", "rect", 0, 0, PHW - 32, 84, 51, fill=pal.panel, stroke=pal.line, strokeWidth=1,
               cornerRadius=20, parentId=g, opacity=1)
        r.node(g + "_s", "rect", 14, 18, 48, 48, 52, fill=acc, cornerRadius=12, parentId=g, opacity=1)
        r.icon(g + "_i", "ph:bell-simple-fill", 26, 30, 24, 53, color=_on(acc), parentId=g, opacity=1)
        r.text(g + "_t", 76, 12, PHW - 130, 30, fit(alert["title"], 16, PHW - 130, 700)[0], 16, weight=700, z=53,
               parentId=g, opacity=1)
        r.text(g + "_d", 76, 42, PHW - 130, 28, fit(alert.get("body") or "", 14, PHW - 130, 500)[0], 14,
               color=pal.grey, weight=500, z=53, parentId=g, opacity=1)
        al = [g]
    r.cut(masks + frame, bg=pal.field(p.get("bg") or "accent2"), note="cut phone app",
          camera={"c": {"x": PHX + PHW / 2 if not line else 0, "y": 0, "zoom": 1.0},
                  "e": {"x": PHX + PHW / 2 if not line else 0, "y": 10, "zoom": 1.05}, "d": 7000})
    if kids:
        r.step(600, "ease-out", r.rise_in(*kids), delays={kd: 90 * j for j, kd in enumerate(kids)}, note="line rise")
    r.appear(k + "hc", k + "hl", frames[0], note="hero on")
    r.step(380, "back", [dict(id=k + "hc", scaleX=1, scaleY=1)], note="hero pop")
    r.count(frames, 1000)
    for i, (g, x) in enumerate(rows):
        r.appear(g, note="row on")
        r.step(340, "ease-out", [dict(id=g, x=x)], note="row in")
        r.cue("tick", n=i)
        r.hold(120)
    r.hold(500)
    if al:
        r.appear(*al, note="alert on")
        r.step(460, "back", [dict(id=al[0], y=PHY + 60)], note="alert drops")
        r.cue("ding")
        r.hold(read_ms(alert["title"], alert.get("body"), lo=1200, hi=1800))
    r.hold(read_ms(line, lo=700, hi=1200))


# ---------------- screenshot ----------------
def screenshot(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    src = p.get("image") or ""
    frame = p.get("frame") if p.get("frame") in ("browser", "phone", "none") else "browser"
    iw, ih = float(p.get("image_w") or 1600), float(p.get("image_h") or 1000)
    caption = p.get("caption") or ""
    static = []
    if frame == "phone":
        SW, SHmax = 340, 700
        ih_d = SW * ih / iw
        SH = min(SHmax, ih_d)
        PX, PY = -SW / 2 - 14, -SH / 2 - 14 - (24 if caption else 0)
        r.node(k + "bz", "rect", PX, PY, SW + 28, SH + 28, 21, fill=pal.bezel, cornerRadius=46,
               dropShadow=dict(dx=0, dy=18, color="rgba(0,0,0,0.2)", radius=40))
        VX, VY, VW, VH = PX + 14, PY + 14, SW, SH
        rad = 34
        static.append(k + "bz")
    elif frame == "browser":
        VW = 1080
        ih_d = VW * ih / iw
        VH = min(560, ih_d)
        BX, BY = -VW / 2, -(VH + 46) / 2 - (24 if caption else 0)
        r.node(k + "fr", "rect", BX, BY, VW, VH + 46, 21, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
               cornerRadius=14, dropShadow=dict(dx=0, dy=16, color="rgba(0,0,0,0.14)", radius=40))
        r.node(k + "tb", "rect", BX, BY, VW, 46, 22, fill=pal.soft, cornerRadius=14)
        static += [k + "fr", k + "tb"]
        for j, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            r.node(f"{k}dot{j}", "circle", BX + 18 + j * 20, BY + 17, 12, 12, 23, fill=col)
            static.append(f"{k}dot{j}")
        url = p.get("url") or ""
        if url:
            UW = 520
            r.node(k + "url", "rect", -UW / 2, BY + 9, UW, 28, 23, fill=pal.panel, stroke=pal.line, strokeWidth=1,
                   cornerRadius=14)
            r.text(k + "urlt", -UW / 2 + 16, BY + 9, UW - 32, 28, fit(url, 14, UW - 32, 500)[0], 14, color=pal.body,
                   weight=500, align="center", z=24)
            static += [k + "url", k + "urlt"]
        VX, VY = BX, BY + 46
        rad = 0
    else:
        VW = 1080
        ih_d = VW * ih / iw
        if ih_d > 600:
            VW, ih_d = 600 * iw / ih, 600
        VH = ih_d
        VX, VY = -VW / 2, -VH / 2 - (24 if caption else 0)
        rad = 16
    vp = k + "vp"
    r.mask(vp, VX, VY, VW, VH, 24, cornerRadius=rad)
    r.node(k + "img", "rect", 0, 0, VW, ih_d, 25, imageData=src, imageCropShape="rectangle", parentId=vp, opacity=1)
    static.append(vp)
    cap = []
    if caption:
        t, s = fit(caption, 30, 1000, 700)
        r.text(k + "cap", -600, VY + VH + 30, 1200, 50, t, s, weight=700, align="center", z=26)
        cap = [k + "cap"]
    wide = {"x": 0, "y": 0, "zoom": 1.0}
    r.cut(static, bg=pal.field(p.get("bg") or "accent2"), note="cut screenshot",
          camera={"c": {"x": 0, "y": 30, "zoom": 0.94}, "e": wide, "d": 900})
    r.hold(900)
    if cap:
        r.appear(*cap, note="caption")
        r.hold(read_ms(caption, lo=900, hi=1500))
    for i, f in enumerate((p.get("focus") or [])[:3]):
        try:
            fx, fy = min(1.0, max(0.0, float(f.get("x", 0.5)))), min(1.0, max(0.0, float(f.get("y", 0.5))))
            z = min(2.6, max(1.2, float(f.get("zoom") or 1.8)))
        except (TypeError, ValueError):
            continue
        wx = VX + fx * VW
        wy = VY + min(VH, fy * ih_d)
        r.step(800, "ease", note="to focus", camera={"e": {"x": wx, "y": wy, "zoom": z}, "d": 800, "ease": "ease"})
        r.cue("whoosh", n=i)
        lab = fit(f.get("label") or "", 22 / z * 1.4, 420 / z, 700)
        if lab[0]:
            lw = tw(lab[0], lab[1], 700) + 36 / z
            lh = lab[1] * 2
            lx = min(wx + 30 / z, VX + VW - lw)
            ly = wy + 30 / z
            r.node(f"{k}fl{i}", "rect", lx, ly, lw, lh, 40, fill=pal.ink, cornerRadius=lh / 2,
                   label=lab[0], labelColor=pal.on_ink, labelFontSize=lab[1], labelFontWeight=700, fontSize=lab[1],
                   fontFamily=r.style.body, labelFontFamily=r.style.body, scaleX=0.5, scaleY=0.5)
            r.appear(f"{k}fl{i}", note="focus label")
            r.step(320, "back", [dict(id=f"{k}fl{i}", scaleX=1, scaleY=1)], note="label pop")
            r.cue("pop", n=i)
        r.hold(read_ms(f.get("label") or "", lo=1100, hi=1700))
        if lab[0]:
            r.step(1, "linear", r.off(f"{k}fl{i}"), note="label off")
    r.step(700, "ease", note="pull back", camera={"e": wide, "d": 700, "ease": "ease"})
    r.hold(900)


SCENES3 = {
    "lineup": lineup, "receipt": receipt, "snippet": snippet, "inbox": inbox, "funnel": funnel, "toggle": toggle,
    "form_builder": form_builder, "repo": repo, "timeline": timeline, "quote": quote, "phone_app": phone_app,
    "screenshot": screenshot,
}
SCENES.update(SCENES3)
