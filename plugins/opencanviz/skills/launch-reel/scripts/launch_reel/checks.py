"""Checks between a spec and the build.

`ground()` holds the spec's claims to the sources the agent gathered: a price, a figure, a
competitor's name, a date, a star count or a quote has to appear in them. Mock UI (dashboard
numbers, inbox mail, kanban cards) is sample data and is not checked. AI scenes need AI in the
product. `check_icons()` swaps icons that will not draw for a sparkle, and drops app-wall logos
that will not draw or are wordmarks too wide for an icon slot. `clean()` takes em dashes out of
copy.
"""
from __future__ import annotations

import re

from ._icons import icon_paths, resolves


def clean(v):
    if isinstance(v, str):
        return re.sub(r"\s*[—–]\s*", ", ", v).strip()
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


def _square(ref: str) -> str | None:
    """The ref, or its `-icon` variant, if it draws as a roughly square mark. Wordmarks such as
    logos:stripe are 2-4x wider than tall and shrink to a sliver in an icon-sized slot."""
    for r in (ref + "-icon", ref) if not ref.endswith("-icon") else (ref,):
        if resolves(r):
            vb = icon_paths(r)[1]
            if vb["w"] <= 1.5 * vb["h"]:
                return r
    return None


def check_icons(spec: dict) -> dict:
    """Swap icons that do not resolve (or are wordmarks) for a sparkle; drop them from app walls."""
    for sc in spec["scenes"]:
        if "apps" in sc:
            sc["apps"] = [r for r in map(_square, sc["apps"]) if r]
        if sc.get("icon") and not _square(sc["icon"]):
            sc["icon"] = "ph:file-text-fill"
        for key in ("pills", "suggestions", "status", "chips", "items", "features", "products"):
            for item in sc.get(key) or []:
                if isinstance(item, dict) and item.get("icon") and not (sq := _square(item["icon"])):
                    item["icon"] = "ph:sparkle-bold"
                elif isinstance(item, dict) and item.get("icon"):
                    item["icon"] = sq
    return spec


# AI scenes need the product to have AI in it; the planner likes to give every product a chat.
_AI_GATES = {
    "chat": r"\b(assistant|chat|ask|copilot|agent)", "phone_chat": r"\b(assistant|chat|ask|copilot|agent)",
    "file_chat": r"\b(assistant|chat|ask|copilot|agent)",
    "doc_edit": r"\b(write|writes|writing|written|draft|generat|assistant|copilot)",
    "pill_cycle": r"\b(write|writes|writing|written|draft|generat|assistant|copilot)",
}
_NUMS = re.compile(r"\d[\d,]*(?:\.\d+)?")


_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
_WORDS.update(thirty="30", forty="40", fifty="50", hundred="100", thousand="1000", half="0.5")


def _nums(text, words: bool = False) -> set[str]:
    """The numbers in a text. With `words`, spelled-out numbers count too ("two minutes" states
    a 2), which is how a description is read; a claim has to use digits to be checked."""
    text = str(text or "")
    out = {n.replace(",", "").rstrip(".") for n in _NUMS.findall(text)}
    if words:
        out |= {_WORDS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in _WORDS}
    return out


def _norm(text) -> str:
    return " ".join(re.sub(r"[“”‘’\"']", "", str(text or "")).lower().split())


def ground(spec: dict, description: str) -> list[str]:
    """Hold the spec's claims to the sources (`description`: every fact file the agent gathered,
    joined), in place. Mock UI may be invented; claims may not. Scenes whose claim is not in the
    sources are dropped or repaired: AI scenes for a product with no AI, tool names and prices
    that were never given, a stat or star count that does not appear, a date that was not
    stated, a quote that is not word for word. Returns a note per change; `build.py` refuses to
    build while there are any, so the agent fixes the spec or the sources instead."""
    desc, low, nums = description or "", _norm(description), _nums(description, words=True)
    named = lambda v: bool(_norm(v)) and _norm(v) in low
    stated = lambda v: _nums(v) <= nums
    notes, keep = [], []
    for sc in spec.get("scenes") or []:
        t = sc.get("type")
        gate = _AI_GATES.get(t)
        if gate and not re.search(gate, desc, re.I):
            notes.append(f"dropped {t}: the sources have no AI that fits it")
            continue
        if t == "receipt":
            items = [x for x in sc.get("items") or [] if named(x.get("name")) and stated(x.get("price"))
                     and _nums(x.get("price"))]
            if len(items) < len(sc.get("items") or []):
                notes.append(f"receipt: dropped {len(sc['items']) - len(items)} tool(s) or price(s) not in the sources")
            sc["items"] = items
            for key in ("total", "new_price"):
                if sc.get(key) and not stated(sc[key]):
                    notes.append(f"receipt: dropped {key} {sc[key]!r}")
                    sc.pop(key)
            if len(items) < 2:
                notes.append("dropped receipt: fewer than two named tools with prices")
                continue
        if t == "compare":
            cols = list(sc.get("columns") or [])
            if cols and _norm(cols[0]) not in ("typical tools", "the old way") and not named(cols[0]):
                notes.append(f"compare: {cols[0]!r} is not named in the sources")
                cols[0] = "Typical tools"
                sc["columns"] = cols
        if t == "lineup":
            prods = [x for x in sc.get("products") or [] if named(x.get("name"))]
            if len(prods) < len(sc.get("products") or []):
                notes.append("lineup: dropped products not named in the sources")
            sc["products"] = prods
            if len(prods) < 2:
                notes.append("dropped lineup: fewer than two named products")
                continue
        if t in ("stat", "pricing"):
            v = sc.get("value") if t == "stat" else sc.get("price")
            if not _nums(v) or not stated(v):
                notes.append(f"dropped {t}: {v!r} is not stated in the sources")
                continue
        if t == "repo":
            if not re.search(r"open[ -]?source", desc, re.I):
                notes.append("dropped repo: the sources do not say it is open source")
                continue
            if sc.get("stars") and not stated(sc["stars"]):
                notes.append(f"repo: dropped stars {sc['stars']!r}")
                sc.pop("stars")
            if sc.get("license") and not named(sc["license"]):
                notes.append(f"repo: dropped license {sc['license']!r}")
                sc.pop("license")
        if t == "timeline":
            items = [x for x in sc.get("items") or [] if stated(x.get("date")) and stated(x.get("label"))]
            if len(items) < len(sc.get("items") or []):
                notes.append("timeline: dropped milestones whose dates are not in the sources")
            sc["items"] = items
            if len(items) < 2:
                notes.append("dropped timeline: fewer than two stated milestones")
                continue
        if t == "quote" and not (len(_norm(sc.get("quote"))) > 12 and named(sc.get("quote"))):
            notes.append("dropped quote: not word for word from the sources")
            continue
        if t == "screenshot" and not sc.get("image"):
            notes.append("dropped screenshot: no image supplied")
            continue
        keep.append(sc)
    spec["scenes"] = keep
    return notes
