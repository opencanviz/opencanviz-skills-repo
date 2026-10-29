"""The launch-reel scene library. Each scene is one beat of a product launch reel:

  logo        the mark pops in on paper
  mascot      the brand's face reacts on a colour field (only with a mascot)
  headline    one or two lines rise through a mask, optionally underlining a word
  pill_cycle  "One tool to [pill]" with the pill cycling through jobs, then "do it all"
  app_wall    a row of integration logos pops, shrinks under a headline
  chat        an assistant panel: suggestions, a typed question, status steps, an answer
  doc_edit    a document page: highlight, prompt, generated copy, Accept menu with a cursor
  file_chat   a file dropped into the assistant over a dashboard, read, answered
  chips       a headline with two or three option chips under it
  phone_chat  the same assistant on a phone: suggestions, keyboard typing, answer
  end         call to action, tagline, logo, logo plus wordmark

Every scene owns its own nodes (ids prefixed with its slot, `s3_`), opens with a hard cut and
leaves the builder to switch off whatever it left on screen. Copy is fitted, never trusted: a
line that is too long for its slot is set smaller down to a floor, then ellipsised, so a long
answer from the agent shrinks a little rather than running off the panel.

Timing comes from the copy too. A hold is reading time for its words, a typed line takes time
in proportion to its characters, so the same scene paces a terse spec and a wordy one sensibly.
"""
from __future__ import annotations

from ._metrics import text_width as tw
from .builder import C0, FONT, Reel

FACES = ("smiley-bold", "smiley-wink-bold", "smiley-meh-bold", "smiley-nervous-bold")


# ---------------- copy fitting and pacing ----------------
def fit(text: str, size: float, maxw: float, weight: int = 600, floor: float = 0.8) -> tuple[str, float]:
    """Shrink `text` until it fits `maxw`, down to `floor` x size, then ellipsise."""
    text = " ".join(str(text or "").split())
    s = size
    while tw(text, s, weight) > maxw and s > size * floor:
        s -= 1
    if tw(text, s, weight) <= maxw:
        return text, s
    while text and tw(text + "…", s, weight) > maxw:
        text = text[:-1]
    return text.rstrip(" ,.;:") + "…", s


def wrap(text: str, size: float, maxw: float, weight: int = 500, max_lines: int = 3) -> list[str]:
    """Greedy word wrap; the last line is ellipsised if the text runs past `max_lines`."""
    words, lines, cur = " ".join(str(text or "").split()).split(" "), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if cur and tw(nxt, size, weight) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(lines[-1] + " …", size, maxw, weight, floor=1)[0]
    return lines


def read_ms(*texts: str, base: int = 500, per_word: int = 230, lo: int = 800, hi: int = 1900) -> int:
    words = sum(len(str(t or "").split()) for t in texts)
    return max(lo, min(hi, base + per_word * words))


def type_ms(text: str, per_char: int = 26, lo: int = 420, hi: int = 1300) -> int:
    return max(lo, min(hi, per_char * len(text or "")))


def line_ms(text: str) -> int:
    return max(340, min(620, 14 * len(text or "")))


class Ctx:
    """What a scene needs besides its own params."""

    def __init__(self, r: Reel, brand: dict, slot: int):
        self.r, self.pal, self.brand = r, r.pal, brand
        self.k = f"s{slot}_"
        self.mascot = bool(brand.get("mascot"))


class Mascot:
    """A round face that swaps expressions with hard cuts. Every swap is a 1ms step."""

    def __init__(self, c: Ctx, name: str, cx: float, cy: float, d: float):
        r, k = c.r, c.k + name
        self.r, self.k = r, k
        r.node(k, "circle", cx - d / 2, cy - d / 2, d, d, 30, fill=c.pal.panel, stroke=c.pal.ink,
               strokeWidth=d * 0.034, scaleX=0.7, scaleY=0.7)
        f = d * 0.62
        for face in FACES:
            r.icon(f"{k}_{face}", "ph:" + face, cx - f / 2, cy - f / 2, f, 31, color=c.pal.ink)
        self.face = FACES[0]

    def ids(self):
        return [self.k, f"{self.k}_{self.face}"]

    def all_ids(self):
        return [self.k] + [f"{self.k}_{f}" for f in FACES]

    def pop(self, ms=400):
        self.r.step(ms, "back", [dict(id=self.k, scaleX=1, scaleY=1)], note="mascot pop")

    def swap(self, face: str, hold: int = 0, note="face", extra=None):
        old, self.face = self.face, face
        self.r.step(1, "linear", self.r.off(f"{self.k}_{old}") + self.r.on(f"{self.k}_{face}") + (extra or []),
                    note=note)
        self.r.hold(hold)


def _drift(zoom=1.04, ms=2000, at=C0):
    return {"c": at, "e": {**at, "zoom": at.get("zoom", 1) * zoom}, "d": ms}


def _icon_color(ref: str, default: str):
    """Brand marks keep their own colours, interface glyphs take the UI grey."""
    return None if ref.startswith("logos:") else default


# ---------------- scenes ----------------
def logo(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    letter = (c.brand.get("logo_letter") or c.brand["name"][:1]).upper()[:2]
    r.node(k + "logo", "rect", -48, -48, 96, 96, 30, fill=pal.panel, stroke=pal.ink, strokeWidth=6,
           cornerRadius=22, scaleX=0.6, scaleY=0.6, label=letter, labelColor=pal.ink, labelFontSize=58,
           labelFontWeight=800, fontSize=58, fontWeight=800, fontFamily=r.style.display, labelFontFamily=r.style.display)
    r.cut([k + "logo"], bg=pal.field(p.get("bg")), note="cut logo")
    r.step(520, "back", [dict(id=k + "logo", scaleX=1, scaleY=1)], note="logo pop",
           camera=_drift(1.03, 1200))
    r.hold(700)


def mascot(c: Ctx, p: dict):
    if not c.mascot:
        return
    r = c.r
    m = Mascot(c, "masc", 0, 0, 200)
    r.cut(m.ids(), bg=c.pal.field(p.get("bg") or "accent1"), note="cut mascot")
    m.pop(420)
    r.hold(200)
    for face, ms in (("smiley-wink-bold", 420), ("smiley-meh-bold", 340), ("smiley-nervous-bold", 340),
                     ("smiley-bold", 420)):
        m.swap(face, ms)


def headline(c: Ctx, p: dict):
    r, k = c.r, c.k
    lines = [l for l in (p.get("lines") or [])[:2] if l] or [c.brand["name"]]
    size = 64
    fitted = [fit(l, size, 1080) for l in lines]
    size = min(s for _, s in fitted)
    lines = [t for t, _ in fitted]
    ys = [0] if len(lines) == 1 else [-38, 40]
    masks, kids = [], []
    for i, (txt, y) in enumerate(zip(lines, ys)):
        masks.append(r.rise_line(f"{k}h{i}", 0, y, txt, size))
        kids.append(f"{k}h{i}")
    ul = (p.get("underline") or "").strip()
    has_ul = bool(ul) and ul in lines[0]
    if has_ul:
        pre = lines[0][:lines[0].index(ul)]
        x = -tw(lines[0], size) / 2 + tw(pre, size)
        r.node(k + "ul", "rect", x, ys[0] + size * 0.5, 0, 5, 22, fill=c.pal.ink, cornerRadius=3)
    r.cut(masks, bg=c.pal.field(p.get("bg")), note="cut headline")
    r.step(600, "ease-out", r.rise_in(*kids), delays={kids[-1]: 110} if len(kids) > 1 else None,
           note="headline rise", camera=_drift(1.04, 2400))
    if has_ul:
        r.appear(k + "ul", note="underline on")
        r.step(380, "ease-out", [dict(id=k + "ul", w=tw(ul, size))], note="underline")
    r.hold(read_ms(*lines))
    r.step(320, "ease-in", r.rise_out(*kids), delays={kids[-1]: 60} if len(kids) > 1 else None,
           note="headline out")


def pill_cycle(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    HS, PAD, PS, PH = 56, 40, 24, 58
    head, HS = fit(p.get("lead") or "One tool to", HS, 560)
    end = fit(p.get("end") or "do it all.", HS, 560)[0]
    pills = [(fit(x.get("label", ""), PS, 400, 500)[0], x.get("icon") or "ph:sparkle-bold")
             for x in (p.get("pills") or [])[:4] if x.get("label")]
    if not pills:
        pills = [("Get it done", "ph:sparkle-bold")]
    wh = tw(head, HS) + 4
    wd = tw(end, HS) + 4

    def pill_w(lbl):
        return 22 + 28 + 12 + tw(lbl, PS, 500) + 26

    r.mask(k + "h_m", -wh / 2 - PAD, -HS * 0.65, wh + 2 * PAD, HS * 1.3, 20)
    r.text(k + "h", 0, HS * 1.3, wh + 2 * PAD, HS * 1.3, head, HS, z=21, parentId=k + "h_m", opacity=1,
           letterSpacing=-0.5, align="center")
    pw0 = pill_w(pills[0][0])
    r.node(k + "pill", "rect", 0, -PH / 2, pw0, PH, 22, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
           cornerRadius=PH / 2, dropShadow=dict(dx=0, dy=4, color="rgba(0,0,0,0.06)", radius=14))
    r.mask(k + "pill_m", 0, -PH / 2, max(pill_w(l) for l, _ in pills), PH, 23)
    for i, (lbl, ic) in enumerate(pills):
        y0 = 0 if i == 0 else PH
        r.icon(f"{k}pi{i}", ic, 22, y0 + 15, 28, 24, color=_icon_color(ic, pal.grey), parentId=k + "pill_m",
               opacity=1)
        r.text(f"{k}pt{i}", 62, y0, tw(lbl, PS, 500) + 20, PH, lbl, PS, color=pal.body, weight=500, z=24,
               parentId=k + "pill_m", opacity=1)
    r.mask(k + "d_m", 0, -HS * 0.65, wd + 2 * PAD, HS * 1.3, 20)
    r.text(k + "d", 0, HS * 1.3, wd + 2 * PAD, HS * 1.3, end, HS, z=21, parentId=k + "d_m", opacity=1,
           letterSpacing=-0.5, align="center")

    def layout(pw):
        x0 = -(wh + 16 + pw) / 2
        return [dict(id=k + "h_m", x=x0 - PAD), dict(id=k + "pill", x=x0 + wh + 16, w=pw),
                dict(id=k + "pill_m", x=x0 + wh + 16)]

    r.cut([k + "h_m"], bg=pal.field(p.get("bg")), note="cut pill")
    r.step(520, "ease-out", r.rise_in(k + "h"), note="lead rise")
    r.hold(300)
    # The pill and its window land at their first position in the same 1ms step they appear.
    r.appear(k + "pill", k + "pill_m", extra=layout(pw0) + [dict(id=k + "pill", scaleX=0.85, scaleY=0.85)],
             note="pill on")
    r.step(380, "back", [dict(id=k + "pill", scaleX=1, scaleY=1)], note="pill pop")
    r.hold(read_ms(pills[0][0], base=500, lo=800, hi=1100))
    for i in range(1, len(pills)):
        pw = pill_w(pills[i][0])
        r.step(360, "ease", layout(pw) + [dict(id=f"{k}pi{i-1}", y=-PH + 15), dict(id=f"{k}pt{i-1}", y=-PH),
                                          dict(id=f"{k}pi{i}", y=15), dict(id=f"{k}pt{i}", y=0)],
               note=f"pill {i}")
        r.hold(read_ms(pills[i][0], base=500, lo=750, hi=1000))
    last = len(pills) - 1
    x0 = -(wh + 4 + wd) / 2
    r.appear(k + "d_m", extra=[dict(id=k + "d_m", x=x0 + wh + 4 - PAD)], note="end on")
    r.step(420, "ease-out", [dict(id=k + "h_m", x=x0 - PAD), dict(id=k + "pill", opacity=0, x=x0 + wh + 4, w=wd), dict(id=k + "pill_m", x=x0 + wh + 4),
                             dict(id=f"{k}pt{last}", y=-PH), dict(id=f"{k}pi{last}", y=-PH + 15),
                             dict(id=k + "d", y=0)], delays={k + "d": 80}, note="do it all")
    r.hold(1100)
    r.step(300, "ease-in", r.rise_out(k + "h", k + "d"), note="pill out")


def app_wall(c: Ctx, p: dict):
    r, k = c.r, c.k
    apps = [a for a in (p.get("apps") or []) if a][:8] or ["ph:sparkle-fill"]
    n = len(apps)
    lines = [l for l in (p.get("lines") or [])[:2] if l]
    sizes = [fit(l, 58, 1080) for l in lines]
    size = min([s for _, s in sizes] or [58])
    lines = [t for t, _ in sizes]
    gap, big = 112, 76
    ax0 = -(n - 1) * gap / 2
    ids = []
    for i, a in enumerate(apps):
        nd = r.icon(f"{k}app{i}", a, 0, 0, big, 30, color=_icon_color(a, c.pal.ink), scaleX=0.3, scaleY=0.3)
        r.place(nd["id"], ax0 + i * gap - big / 2, -nd["h"] / 2)
        ids.append(nd["id"])
    ys = {0: [], 1: [-84], 2: [-120, -48]}[len(lines)]
    kids, masks = [], []
    for i, (txt, y) in enumerate(zip(lines, ys)):
        masks.append(r.rise_line(f"{k}f{i}", 0, y, txt, size))
        kids.append(f"{k}f{i}")
    r.cut(ids, bg=c.pal.field(p.get("bg")), note="cut apps", camera=_drift(1.03, 3600))
    r.step(700 + 60 * n, "back", [dict(id=i, scaleX=1, scaleY=1) for i in ids],
           delays={i: j * 90 for j, i in enumerate(ids)}, note="apps pop")
    r.hold(700)
    if kids:
        sg, s = 58, 36 / big
        sx0 = -(n - 1) * sg / 2
        small = [dict(id=f"{k}app{i}", x=sx0 + i * sg - 18, y=40, w=36, h=r.byid[f"{k}app{i}"]["h"] * s)
                 for i in range(n)]
        r.appear(*masks, note="lines on")
        r.step(560, "ease-out", small + r.rise_in(*kids), delays={kd: 120 + 80 * j for j, kd in enumerate(kids)},
               note="find answers")
        r.hold(read_ms(*lines))
    else:
        r.hold(600)


def _chat_panel(c: Ctx, k: str, x: float, y: float, w: float, h: float, z: float = 26):
    """White assistant panel with a shadow and the two header glyphs. Returns its ids."""
    r, pal = c.r, c.pal
    r.node(k + "sh", "rect", x + 10, y + 16, w, h, z - 1, fill="rgba(0,0,0,0.10)", cornerRadius=20)
    r.node(k + "pn", "rect", x, y, w, h, z, fill=pal.panel, cornerRadius=20)
    for j, ic in enumerate(["ph:dots-three-bold", "ph:x-bold"]):
        r.icon(f"{k}hd{j}", ic, x + w - 80 + j * 34, y + 22, 22, z + 1, color=pal.faint)
    return [k + "sh", k + "pn", k + "hd0", k + "hd1"]


def _bullets(c: Ctx, k: str, items: list[str], x: float, y: float, gap: float, size: float, maxw: float,
             z: float = 28, dot: float = 7):
    r, pal = c.r, c.pal
    out = []
    for i, a in enumerate(items):
        txt, s = fit(a, size, maxw - 24, 500)
        r.node(f"{k}b{i}", "circle", x + 4, y + i * gap + 17 - dot / 2 - 4, dot, dot, z, fill=pal.ink)
        r.text(f"{k}t{i}", x + 24, y + i * gap, maxw, 34, txt, s, color=pal.body, weight=500, z=z,
               typeProgress=0)
        out.append((f"{k}b{i}", f"{k}t{i}", txt))
    return out


def _actions(c: Ctx, k: str, x: float, y: float, z: float = 28, n: int = 3, size: float = 22):
    for j, ic in enumerate(["ph:copy-bold", "ph:thumbs-up-bold", "ph:arrow-clockwise-bold"][:n]):
        c.r.icon(f"{k}{j}", ic, x + j * (size + 18), y, size, z, color=c.pal.grey)
    return [f"{k}{j}" for j in range(n)]


def chat(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    PW, PH = 960, 540
    PX = -800 if c.mascot else -PW / 2
    PY = -270
    CX = PX + 220 if c.mascot else PX + 60
    CW = PX + PW - 60 - CX                                  # content width
    panel = _chat_panel(c, k + "p_", PX, PY, PW, PH)
    q = fit(p.get("question") or "What changed this week?", 22, min(CW - 60, 620), 500)[0]
    qw = tw(q, 22, 500) + 40
    r.node(k + "bub", "rect", PX + PW - 50 - qw, PY + 90, qw, 52, 27, fill=pal.soft, cornerRadius=16,
           scaleX=0.9, scaleY=0.9)
    r.text(k + "bubt", PX + PW - 50 - qw + 20, PY + 90, qw - 20, 52, q, 22, weight=500, z=28)
    status = [(x.get("icon") or "ph:magnifying-glass-bold", fit(x.get("label", ""), 20, CW - 60, 500)[0])
              for x in (p.get("status") or [])[:3] if x.get("label")] or [("ph:sparkle-fill", "Thinking...")]
    for i, (ic, lbl) in enumerate(status):
        r.icon(f"{k}st_i{i}", ic, CX, PY + 176, 24, 28, color=_icon_color(ic, pal.grey))
        r.text(f"{k}st_t{i}", CX + 36, PY + 170, CW - 40, 36, lbl, 20, color=pal.grey, weight=500, z=28)
    title = fit(p.get("answer_title") or "Here's what I found:", 21, CW, 600)[0]
    r.text(k + "ah", CX, PY + 160, CW, 34, title, 21, weight=600, z=28)
    ans = _bullets(c, k + "a", (p.get("answer") or [])[:4], CX, PY + 214, 42, 20, CW)
    acts = _actions(c, k + "act", CX, PY + 214 + len(ans) * 42 + 18)
    r.node(k + "inp", "rect", CX - 20, PY + PH - 86, PX + PW - 30 - (CX - 20), 58, 27, fill=pal.panel,
           stroke=pal.line, strokeWidth=1.5, cornerRadius=14)
    r.text(k + "ph", CX, PY + PH - 86, 400, 58, p.get("placeholder") or "Ask AI anything...", 20,
           color=pal.faint, weight=500, z=28)
    r.text(k + "it", CX, PY + PH - 86, CW - 80, 58, q, fit(q, 20, CW - 90, 500)[1], weight=500, z=29,
           typeProgress=0)
    r.node(k + "send", "circle", PX + PW - 104, PY + PH - 73, 32, 32, 28, fill=pal.disabled)
    r.icon(k + "send_i", "ph:arrow-up-bold", PX + PW - 97, PY + PH - 66, 18, 29, color=pal.on_ink)
    menu = []
    greet = p.get("greeting")
    sugg = [(x.get("icon") or "ph:sparkle-bold", fit(x.get("label", ""), 19, CW - 60, 500)[0])
            for x in (p.get("suggestions") or [])[:4] if x.get("label")]
    if greet or sugg:
        r.icon(k + "hi_i", "ph:sparkle-fill", CX, PY + 104, 30, 28, color=pal.ink)
        r.text(k + "hi_t", CX, PY + 142, CW, 40, fit(greet or "How can I help?", 24, CW, 700)[0], 24, weight=700,
               z=28)
        menu = [k + "hi_i", k + "hi_t"]
        if sugg:
            r.text(k + "sg_h", CX, PY + 192, 300, 30, "Suggested", 17, color=pal.faint, weight=500, z=28)
            menu.append(k + "sg_h")
        for i, (ic, lbl) in enumerate(sugg):
            r.icon(f"{k}sg_i{i}", ic, CX, PY + 234 + i * 44 + 3, 22, 28, color=pal.grey)
            r.text(f"{k}sg_t{i}", CX + 36, PY + 234 + i * 44 - 2, CW - 40, 32, lbl, 19, color=pal.body,
                   weight=500, z=28)
            menu += [f"{k}sg_i{i}", f"{k}sg_t{i}"]
    m = Mascot(c, "m", 420, 0, 220) if c.mascot else None

    opening = panel + [k + "inp", k + "ph", k + "send", k + "send_i"] + (m.ids() if m else [])
    r.cut(opening, bg=pal.field(p.get("bg") or "accent1"), note="cut chat",
          camera={"c": C0, "e": {"x": -30 if m else 0, "y": 0, "zoom": 1.05}, "d": 9000})
    if m:
        m.pop(380)
    if menu:
        r.appear(*menu, note="menu on")
        r.hold(read_ms(greet, *[s for _, s in sugg], base=300, per_word=90, lo=900, hi=1600))
    if m:
        m.swap("smiley-wink-bold", 0, "wink")
    r.step(1, "linear", r.off(k + "ph") + r.on(k + "it"), note="input on")
    ms = type_ms(q)
    r.step(ms, "linear", actions=[r.tween(k + "it", "typeProgress", 0, 1, ms - 80)], note="type q")
    r.step(140, "ease", [dict(id=k + "send", fill=pal.ink)], note="send ready")
    r.hold(160)
    r.step(1, "linear", r.off(k + "it", *menu) + r.on(k + "ph", k + "bubt", k + "bub"), note="sent")
    r.step(340, "back", [dict(id=k + "bub", scaleX=1, scaleY=1), dict(id=k + "send", fill=pal.disabled)],
           note="bubble")
    faces = ["smiley-meh-bold", "smiley-nervous-bold", "smiley-meh-bold"]
    for i in range(len(status)):
        prev = r.off(f"{k}st_i{i-1}", f"{k}st_t{i-1}") if i else []
        r.step(1, "linear", prev + r.on(f"{k}st_i{i}", f"{k}st_t{i}"), note=f"status {i}")
        if m:
            m.swap(faces[i], 0)
        r.hold(700)
    r.step(1, "linear", r.off(f"{k}st_i{len(status)-1}", f"{k}st_t{len(status)-1}") + r.on(k + "ah"),
           note="answer on")
    if m:
        m.swap("smiley-bold", 0)
    for b, t, txt in ans:
        r.appear(b, note="bullet")
        r.type_in(t, line_ms(txt))
    r.appear(*acts, note="actions")
    r.hold(300)
    if m:
        m.swap("smiley-wink-bold", 900, "wink")
    else:
        r.hold(900)


def doc_edit(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    PG_X, TW = -470, 1000
    bg = pal.field(p.get("bg") or "accent2")
    icon = p.get("icon") or "ph:file-text-fill"
    r.node(k + "pg", "rect", -560, -330, 1120, 710, 26, fill=pal.panel, cornerRadius=14)
    r.icon(k + "pg_ic", icon, PG_X, -280, 56, 27, color=_icon_color(icon, bg))
    title, ts = fit(p.get("title") or "Untitled", 44, TW, 700)
    r.text(k + "pg_t", PG_X, -210, TW, 60, title, ts, weight=700, z=27, letterSpacing=-0.5)
    r.text(k + "pg_s", PG_X, -140, TW, 40, fit(p.get("subtitle") or "", 26, TW)[0], 26, weight=600, z=27)
    bul = [fit(b, 20, TW - 40, 500)[0] for b in (p.get("bullets") or [])[:3]]
    for i, b in enumerate(bul):
        bw = tw(b, 20, 500)
        r.node(f"{k}hl{i}", "rect", PG_X + 18, -96 + i * 34, 0, 30, 26, fill=pal.highlight, cornerRadius=4)
        r.node(f"{k}pb{i}", "circle", PG_X + 4, -96 + i * 34 + 12, 6, 6, 27, fill=pal.ink)
        r.text(f"{k}pbt{i}", PG_X + 24, -96 + i * 34, bw + 10, 30, b, 20, color=pal.body, weight=500, z=28)
    r.node(k + "pin", "rect", PG_X - 10, 20, TW, 56, 27, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
           cornerRadius=12, dropShadow=dict(dx=0, dy=6, color="rgba(0,0,0,0.08)", radius=18))
    r.icon(k + "pin_i", "ph:sparkle-fill", PG_X + 8, 36, 24, 28, color=pal.link)
    chip = fit(p.get("chip") or "", 18, 300, 600)[0]
    cw = tw(chip, 18, 600) + 40 if chip else 0
    pq, pqs = fit(p.get("prompt") or "Write a draft", 20, TW - 160 - cw, 500)
    pqw = tw(pq, pqs, 500)
    r.text(k + "pin_t", PG_X + 44, 20, pqw + 20, 56, pq, pqs, weight=500, z=28, typeProgress=0)
    if chip:
        r.node(k + "chip", "rect", PG_X + 44 + pqw + 12, 33, cw, 30, 28, fill=pal.soft, cornerRadius=8,
               scaleX=0.8, scaleY=0.8)
        r.text(k + "chip_t", PG_X + 44 + pqw + 24, 33, cw, 30, chip, 18, weight=600, z=29)
    r.node(k + "psend", "circle", PG_X + 946, 32, 32, 32, 28, fill=pal.link)
    r.icon(k + "psend_i", "ph:arrow-up-bold", PG_X + 953, 39, 18, 29, color=pal.on_ink)
    gen = wrap(p.get("output") or "", 20, TW, 500, 3) or ["Here is a first draft."]
    for i, g in enumerate(gen):
        r.text(f"{k}gen{i}", PG_X, 100 + i * 34, TW, 32, g, 20, color=pal.link, weight=500, z=28, typeProgress=0)
    AY = 100 + len(gen) * 34 + 12
    r.node(k + "am", "rect", PG_X, AY, 250, 138, 28, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
           cornerRadius=10, dropShadow=dict(dx=0, dy=8, color="rgba(0,0,0,0.10)", radius=20))
    r.node(k + "am_hl", "rect", PG_X + 6, AY + 6, 238, 40, 28.5, fill=pal.soft, cornerRadius=7)
    am = [k + "am", k + "am_hl"]
    for i, (ic, lbl) in enumerate([("ph:check-bold", "Accept"), ("ph:x-bold", "Discard"),
                                   ("ph:arrow-down-bold", "Insert below")]):
        r.icon(f"{k}am_i{i}", ic, PG_X + 18, AY + 14 + i * 40 + 3, 20, 29, color=pal.grey)
        r.text(f"{k}am_t{i}", PG_X + 50, AY + 8 + i * 40, 180, 36, lbl, 18, color=pal.body, weight=500, z=29)
        am += [f"{k}am_i{i}", f"{k}am_t{i}"]
    r.icon(k + "cur", "ph:cursor-fill", 360, 330, 30, 45, color=pal.ink)
    r.node(k + "bar", "rect", -700, 400, 1400, 14, 40, fill=bg)

    page = [k + x for x in ("pg", "pg_ic", "pg_t", "pg_s", "pin", "pin_i", "psend", "psend_i", "bar", "cur")]
    page += [f"{k}{p_}{i}" for i in range(len(bul)) for p_ in ("pb", "pbt", "hl")]
    r.cut(page, bg=bg, note="cut page", camera={"c": {"x": 0, "y": 0, "zoom": 0.55}})
    r.step(700, "ease-out", [dict(id="bg", fill=pal.paper)], note="page grows",
           camera={"c": {"x": 0, "y": 0, "zoom": 0.55}, "e": {"x": -60, "y": -70, "zoom": 1.08}, "d": 700})
    if bul:
        r.step(520, "ease-out", [dict(id=f"{k}hl{i}", w=tw(b, 20, 500) + 12) for i, b in enumerate(bul)],
               delays={f"{k}hl{i}": i * 90 for i in range(len(bul))}, note="highlight")
    r.appear(k + "pin_t", note="prompt on")
    ms = type_ms(pq, lo=600)
    r.step(ms, "linear", actions=[r.tween(k + "pin_t", "typeProgress", 0, 1, ms - 80)], note="type prompt",
           camera={"c": {"x": -60, "y": -70, "zoom": 1.08}, "e": {"x": 40, "y": 20, "zoom": 1.22}, "d": ms + 300})
    if chip:
        r.appear(k + "chip", k + "chip_t", note="chip on")
        r.step(320, "back", [dict(id=k + "chip", scaleX=1, scaleY=1)], note="chip")
    r.step(520, "ease", [dict(id=k + "cur", x=PG_X + 958, y=46)], note="cursor to send")
    r.step(120, "ease-out", [dict(id=k + "psend", scaleX=0.85, scaleY=0.85),
                             dict(id=k + "cur", scaleX=0.85, scaleY=0.85)], note="press")
    r.step(240, "back", [dict(id=k + "psend", scaleX=1, scaleY=1), dict(id=k + "cur", scaleX=1, scaleY=1)],
           note="release")
    for i, g in enumerate(gen):
        r.type_in(f"{k}gen{i}", max(450, min(650, 8 * len(g))), note="generate")
    r.step(600, "ease", note="frame menu",
           camera={"c": {"x": 40, "y": 20, "zoom": 1.22}, "e": {"x": 0, "y": 90, "zoom": 1.08}, "d": 600})
    r.appear(*am, note="accept menu")
    r.hold(300)
    r.step(600, "ease", [dict(id=k + "cur", x=PG_X + 130, y=AY + 24)], note="cursor to accept")
    r.step(120, "ease-out", [dict(id=k + "cur", scaleX=0.85, scaleY=0.85)], note="press")
    r.step(160, "back", [dict(id=k + "cur", scaleX=1, scaleY=1)], note="release")
    r.step(1, "linear", r.off(*am), note="menu off")
    r.step(400, "ease", [dict(id=f"{k}gen{i}", color=pal.body) for i in range(len(gen))], note="accept")
    r.hold(900)


_FILE_ICONS = {"pdf": ("ph:file-pdf-fill", "#e5484d"), "png": ("ph:file-image-fill", "#8e4ec6"),
               "jpg": ("ph:file-image-fill", "#8e4ec6"), "jpeg": ("ph:file-image-fill", "#8e4ec6"),
               "csv": ("ph:file-csv-fill", "#30a46c"), "xlsx": ("ph:file-xls-fill", "#30a46c"),
               "docx": ("ph:file-doc-fill", "#3e63dd"), "doc": ("ph:file-doc-fill", "#3e63dd")}


def file_chat(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    sx = 0 if c.mascot else 150
    DX, DY, DW, DH = -720 + sx, -330, 560, 660
    fname = fit(p.get("file") or "Report.pdf", 17, 360, 600)[0]
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    ficon, fcol = _FILE_ICONS.get(ext, ("ph:file-text-fill", pal.grey))
    r.node(k + "db", "rect", DX, DY, DW, DH, 24, fill=pal.panel, cornerRadius=18)
    r.text(k + "db_t", DX + 120, DY + 18, 300, 30, fit(p.get("dashboard_title") or "Overview", 17, 220)[0], 17,
           color=pal.grey, weight=600, z=25)
    acc = pal.accents + pal.accents
    bars = [0.55, 0.8, 0.4, 0.9, 0.65, 0.5, 0.75, 0.35]
    dash = [k + "db", k + "db_t", k + "ring"]
    for i, hh in enumerate(bars):
        r.node(f"{k}bar{i}", "rect", DX + 120 + i * 22, DY + 70 + (1 - hh) * 120, 12, hh * 120, 25,
               fill=acc[i % 3], cornerRadius=3)
        r.node(f"{k}bbr{i}", "rect", DX + 120 + i * 22, DY + 420 + (1 - bars[-1 - i]) * 160, 12,
               bars[-1 - i] * 160, 25, fill=acc[(i + 1) % 3], cornerRadius=3)
        dash += [f"{k}bar{i}", f"{k}bbr{i}"]
    r.node(k + "ring", "circle", DX + 150, DY + 240, 110, 110, 25, stroke=pal.accents[0], strokeWidth=12)
    PX, PY, PW, PH = -370 + sx, -300, 650, 600
    CX, CW = PX + 40, PW - 90
    panel = _chat_panel(c, k + "p_", PX, PY, PW, PH, 26.5)
    fcw = tw(fname, 17, 600) + 92
    r.node(k + "fc", "rect", PX + PW - 40 - fcw, PY + 66, fcw, 58, 27, fill=pal.panel, stroke=pal.line,
           strokeWidth=1.5, cornerRadius=12, scaleX=0.9, scaleY=0.9)
    r.icon(k + "fc_i", ficon, PX + PW - 40 - fcw + 14, PY + 79, 32, 28, color=fcol)
    r.text(k + "fc_t", PX + PW - 40 - fcw + 56, PY + 66, fcw - 60, 58, fname, 17, weight=600, z=28)
    q = fit(p.get("question") or "Summarize this file", 18, CW - 40, 500)[0]
    qw = tw(q, 18, 500) + 40
    r.node(k + "b2", "rect", PX + PW - 40 - qw, PY + 136, qw, 48, 27, fill=pal.soft, cornerRadius=14, scaleX=0.9,
           scaleY=0.9)
    r.text(k + "b2t", PX + PW - 40 - qw + 20, PY + 136, qw - 20, 48, q, 18, weight=500, z=28)
    r.icon(k + "th_i", "ph:sparkle-fill", CX, PY + 214, 22, 28, color=pal.link)
    r.text(k + "th_t", CX + 32, PY + 206, CW - 40, 36, fit(p.get("thinking") or "Reading the file...", 18,
                                                             CW - 40, 500)[0], 18, color=pal.grey, weight=500, z=28)
    r.text(k + "ah", CX, PY + 204, CW, 34, fit(p.get("answer_title") or "Here's what stands out:", 19, CW)[0], 19,
           weight=600, z=28)
    ans = _bullets(c, k + "n", (p.get("answer") or [])[:4], CX, PY + 252, 40, 18, CW)
    acts = _actions(c, k + "act", CX, PY + 252 + len(ans) * 40 + 16)
    r.node(k + "i2", "rect", CX - 16, PY + PH - 120, PW - 48, 100, 27, fill=pal.panel, stroke=pal.line,
           strokeWidth=1.5, cornerRadius=14)
    cw2 = tw(fname, 15, 600) + 56
    r.node(k + "i2c", "rect", CX, PY + PH - 110, cw2, 36, 28, fill=pal.soft, cornerRadius=8, scaleX=0.8,
           scaleY=0.8)
    r.icon(k + "i2c_i", ficon, CX + 8, PY + PH - 104, 22, 29, color=fcol)
    r.text(k + "i2c_t", CX + 36, PY + PH - 110, cw2 - 20, 36, fname, 15, weight=600, z=29)
    r.text(k + "i2ph", CX, PY + PH - 70, 400, 44, "Ask AI anything...", 18, color=pal.faint, weight=500, z=28)
    r.text(k + "i2t", CX, PY + PH - 70, CW - 60, 44, q, fit(q, 18, CW - 60, 500)[1], weight=500, z=29,
           typeProgress=0)
    r.node(k + "s2", "circle", PX + PW - 74, PY + PH - 62, 32, 32, 28, fill=pal.disabled)
    r.icon(k + "s2_i", "ph:arrow-up-bold", PX + PW - 67, PY + PH - 55, 18, 29, color=pal.on_ink)
    m = Mascot(c, "m", 420, -10, 220) if c.mascot else None

    opening = dash + panel + [k + "i2", k + "i2ph", k + "s2", k + "s2_i"] + (m.ids() if m else [])
    r.cut(opening, bg=pal.field(p.get("bg") or "accent1"), note="cut file",
          camera={"c": {"x": -20, "y": 0, "zoom": 1.0}, "e": {"x": 10, "y": 0, "zoom": 1.05}, "d": 9000})
    r.hold(400)
    r.appear(k + "i2c", k + "i2c_i", k + "i2c_t", note="attach on")
    r.step(340, "back", [dict(id=k + "i2c", scaleX=1, scaleY=1)], note="attach")
    r.hold(400)
    r.step(1, "linear", r.off(k + "i2ph") + r.on(k + "i2t"), note="input on")
    ms = type_ms(q)
    r.step(ms, "linear", actions=[r.tween(k + "i2t", "typeProgress", 0, 1, ms - 80)], note="type q")
    r.step(140, "ease", [dict(id=k + "s2", fill=pal.ink)], note="send ready")
    r.hold(160)
    r.step(1, "linear", r.off(k + "i2t", k + "i2c", k + "i2c_i", k + "i2c_t")
           + r.on(k + "i2ph", k + "fc", k + "fc_i", k + "fc_t", k + "b2", k + "b2t"), note="sent")
    r.step(360, "back", [dict(id=k + "fc", scaleX=1, scaleY=1), dict(id=k + "b2", scaleX=1, scaleY=1),
                         dict(id=k + "s2", fill=pal.disabled)], delays={k + "b2": 90}, note="bubble")
    r.appear(k + "th_i", k + "th_t", note="thinking")
    if m:
        m.swap("smiley-meh-bold", 600)
        m.swap("smiley-nervous-bold", 600)
    else:
        r.hold(1100)
    r.step(1, "linear", r.off(k + "th_i", k + "th_t") + r.on(k + "ah"), note="answer on")
    if m:
        m.swap("smiley-bold", 0)
    for b, t, txt in ans:
        r.appear(b, note="bullet")
        r.type_in(t, line_ms(txt))
    r.appear(*acts, note="actions")
    r.hold(300)
    if m:
        m.swap("smiley-wink-bold", 1000, "wink")
    else:
        r.hold(1000)


def chips(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    line, size = fit(p.get("line") or "", 62, 1080)
    mask = r.rise_line(k + "ch", 0, -30, line, size)
    items = [(x.get("icon") or "ph:sparkle-fill", fit(x.get("label", ""), 22, 300)[0])
             for x in (p.get("chips") or [])[:3] if x.get("label")]
    widths = [tw(l, 22) + 70 for _, l in items]
    mx = -(sum(widths) + 24 * (len(items) - 1)) / 2
    ids = []
    for i, ((ic, lbl), w) in enumerate(zip(items, widths)):
        r.node(f"{k}md{i}", "rect", mx, 48, w, 46, 22, fill=pal.panel, stroke=pal.line, strokeWidth=1.5,
               cornerRadius=23, scaleX=0.7, scaleY=0.7)
        r.icon(f"{k}mi{i}", ic, mx + 16, 59, 24, 23, color=_icon_color(ic, pal.accents[i % len(pal.accents)]))
        r.text(f"{k}mt{i}", mx + 48, 48, w - 48, 46, lbl, 22, z=23)
        ids += [f"{k}md{i}", f"{k}mi{i}", f"{k}mt{i}"]
        mx += w + 24
    r.cut([mask], bg=pal.field(p.get("bg")), note="cut chips", camera=_drift(1.04, 2800))
    r.step(600, "ease-out", r.rise_in(k + "ch"), note="chips line rise")
    if ids:
        r.appear(*ids, note="chips on")
        r.step(420, "back", [dict(id=f"{k}md{i}", scaleX=1, scaleY=1) for i in range(len(items))],
               delays={f"{k}md{i}": i * 120 for i in range(len(items))}, note="chips pop")
    r.hold(read_ms(line, *[l for _, l in items], lo=1200))


def phone_chat(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    PHX, PHY, PHW, PHH = -200, -300, 400, 820
    r.node(k + "ph", "rect", PHX, PHY, PHW, PHH, 26, fill=pal.bezel, cornerRadius=62)
    r.node(k + "scr", "rect", PHX + 12, PHY + 12, PHW - 24, PHH - 24, 27, fill=pal.panel, cornerRadius=52)
    r.node(k + "nt", "rect", -60, PHY + 26, 120, 34, 28, fill=pal.bezel, cornerRadius=17)
    r.text(k + "tm", PHX + 44, PHY + 24, 80, 36, "9:41", 17, weight=700, z=28)
    prompt = " ".join(str(p.get("prompt") or "Help me plan my week").split())
    pl = wrap(prompt, 17, PHW - 190, 500, 2)
    bw = max(tw(l, 17, 500) for l in pl) + 34
    r.node(k + "qb", "rect", PHX + PHW - 30 - bw, PHY + 150, bw, 28 + 24 * len(pl), 28, fill=pal.soft,
           cornerRadius=16, scaleX=0.9, scaleY=0.9)
    r.text(k + "q", PHX + PHW - 30 - bw + 16, PHY + 150, bw - 20, 28 + 24 * len(pl), "\n".join(pl), 17,
           weight=500, z=29)
    r.text(k + "ah", PHX + 34, PHY + 150 + 50 + 24 * len(pl), PHW - 60, 30,
           fit(p.get("answer_title") or "Here you go:", 18, PHW - 70)[0], 18, weight=600, z=29)
    ay = PHY + 150 + 96 + 24 * len(pl)
    ans = _bullets(c, k + "a", (p.get("answer") or [])[:5], PHX + 34, ay, 36, 17, PHW - 80, z=29, dot=6)
    acts = _actions(c, k + "act", PHX + 34, ay + len(ans) * 36 + 14, z=29, n=2, size=20)
    r.node(k + "in", "rect", PHX + 26, PHY + 480, PHW - 52, 52, 29, fill=pal.panel, stroke=pal.line,
           strokeWidth=1.5, cornerRadius=14)
    it, its = fit(prompt, 16, PHW - 90, 500, floor=0.75)
    r.text(k + "it", PHX + 42, PHY + 480, PHW - 80, 52, it, its, weight=500, z=30, typeProgress=0)
    r.node(k + "kb", "rect", PHX + 12, PHY + 548, PHW - 24, 260, 29, fill=pal.keyboard)
    keys = [k + "kb"]
    kw = (PHW - 24 - 20) / 10
    for row_i, row in enumerate(["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]):
        off = (10 - len(row)) * kw / 2
        for col, ch in enumerate(row):
            x = PHX + 22 + off + col * kw
            r.node(f"{k}k{row_i}{col}", "rect", x + 3, PHY + 564 + row_i * 58, kw - 6, 46, 30, fill=pal.panel,
                   cornerRadius=6, label=ch, labelColor=pal.ink, labelFontSize=18, fontSize=18, fontWeight=500,
                   fontFamily=r.style.display, labelFontFamily=r.style.display)
            keys.append(f"{k}k{row_i}{col}")
    r.node(k + "sp", "rect", PHX + 90, PHY + 564 + 3 * 58, PHW - 180, 46, 30, fill=pal.panel, cornerRadius=6)
    keys.append(k + "sp")
    sugg = []
    for i, x in enumerate([x for x in (p.get("suggestions") or []) if x.get("label")][:3]):
        ic = x.get("icon") or "ph:sparkle-bold"
        r.icon(f"{k}sg_i{i}", ic, PHX + 34, PHY + 352 + i * 40 + 4, 22, 30, color=_icon_color(ic, pal.grey))
        r.text(f"{k}sg_t{i}", PHX + 66, PHY + 352 + i * 40, PHW - 100, 30, fit(x["label"], 17, PHW - 110, 500)[0],
               17, color=pal.body, weight=500, z=30)
        sugg += [f"{k}sg_i{i}", f"{k}sg_t{i}"]

    shell = [k + x for x in ("ph", "scr", "nt", "tm", "in")]
    r.cut(shell + keys + sugg, bg=pal.field(p.get("bg") or "accent3"), note="cut phone",
          camera={"c": {"x": 0, "y": 160, "zoom": 1.45}})
    r.hold(900)
    r.appear(k + "it", note="phone input on")
    ms = type_ms(it, lo=700)
    r.step(ms, "linear", actions=[r.tween(k + "it", "typeProgress", 0, 1, ms - 80)], note="phone type",
           camera={"c": {"x": 0, "y": 160, "zoom": 1.45}, "e": {"x": 0, "y": 150, "zoom": 1.5}, "d": ms})
    r.hold(200)
    r.step(1, "linear", r.off(k + "it", *keys, *sugg) + r.on(k + "q", k + "qb")
           + [dict(id=k + "in", y=PHY + PHH - 110)], note="phone send")
    r.step(700, "ease", [dict(id=k + "qb", scaleX=1, scaleY=1)], note="phone zoom out",
           camera={"c": {"x": 0, "y": 150, "zoom": 1.5}, "e": {"x": 0, "y": 40, "zoom": 1.0}, "d": 700})
    r.appear(k + "ah", note="answer on")
    for b, t, txt in ans:
        r.appear(b, note="bullet")
        r.type_in(t, max(300, min(480, 12 * len(txt))))
    r.appear(*acts, note="actions")
    r.hold(1100)


def end(c: Ctx, p: dict):
    r, pal, k = c.r, c.pal, c.k
    name = c.brand["name"]
    cta, cs = fit(p.get("cta") or f"Try {name} today", 62, 1080)
    tag, ts = fit(p.get("tagline") or "", 62, 1080)
    m1 = r.rise_line(k + "e1", 0, 0, cta, cs)
    m2 = r.rise_line(k + "e2", 0, 0, tag, ts) if tag else None
    letter = (c.brand.get("logo_letter") or name[:1]).upper()[:2]
    r.node(k + "logo", "rect", -48, -48, 96, 96, 30, fill=pal.panel, stroke=pal.ink, strokeWidth=6,
           cornerRadius=22, scaleX=0.6, scaleY=0.6, label=letter, labelColor=pal.ink, labelFontSize=58,
           labelFontWeight=800, fontSize=58, fontWeight=800, fontFamily=r.style.display, labelFontFamily=r.style.display)
    word, wsz = fit(name, 56, 760, 700)
    total = 72 + 22 + tw(word, wsz, 700, -1)
    x0 = -total / 2
    r.node(k + "el", "rect", x0, -36, 72, 72, 30, fill=pal.panel, stroke=pal.ink, strokeWidth=5, cornerRadius=17,
           label=letter, labelColor=pal.ink, labelFontSize=44, labelFontWeight=800, fontSize=44, fontWeight=800,
           fontFamily=r.style.display, labelFontFamily=r.style.display, scaleX=0.7, scaleY=0.7)
    r.text(k + "ew", x0 + 94, -40, tw(word, wsz, 700) + 40, 80, word, wsz, weight=700, z=30, letterSpacing=-1)
    m = Mascot(c, "m", 0, 0, 200) if c.mascot else None

    r.cut([m1], bg=pal.field(p.get("bg")), note="cut end", camera=_drift(1.04, 2000))
    r.step(600, "ease-out", r.rise_in(k + "e1"), note="cta rise")
    r.hold(read_ms(cta, lo=1200))
    r.step(300, "ease-in", r.rise_out(k + "e1"), note="cta out")
    if m:
        r.cut(m.ids(), note="end mascot")
        m.pop(420)
        r.hold(300)
        m.swap("smiley-wink-bold", 700, "end wink")
    if m2:
        r.cut([m2], note="tagline", camera=_drift(1.04, 1800))
        r.step(600, "ease-out", r.rise_in(k + "e2"), note="tagline rise")
        r.hold(read_ms(tag, lo=1000))
        r.step(300, "ease-in", r.rise_out(k + "e2"), note="tagline out")
    r.cut([k + "logo"], note="end logo")
    r.step(480, "back", [dict(id=k + "logo", scaleX=1, scaleY=1)], note="end logo pop")
    r.hold(700)
    r.cut([k + "el", k + "ew"], note="lockup")
    r.step(500, "back", [dict(id=k + "el", scaleX=1, scaleY=1)], note="lockup pop")


SCENES = {f.__name__: f for f in (logo, mascot, headline, pill_cycle, app_wall, chat, doc_edit, file_chat,
                                  chips, phone_chat, end)}
