"""The launch-reel spec: everything that changes from one product to the next.

    {"brand": {"name", "logo_letter", "ink", "paper", "accents": [3 hex], "mascot": bool},
     "style": <a STYLES key>, "story": <a STORIES key>,
     "scenes": [{"type": <scene name>, ...that scene's copy...}, ...]}

`normalize()` is the only gate between a spec (hand written or written by an agent) and the
builder. It fills defaults, drops scenes it does not know, and refuses colours it cannot parse.
It does not trim copy: the scenes fit their own text to their own slots, which is the only place
that knows how wide a slot is.

EXAMPLE is the Margin AI reel the template was cut from. It is also the reference the tests and
the SKILL.md examples are written against, so it stays a real, complete reel.
"""
from __future__ import annotations

import copy
import re

from .scenes import SCENES
from .scenes2 import SCENES2  # noqa: F401  (registers the newer scenes)
from .scenes3 import SCENES3  # noqa: F401
from .styles import STYLES

DEFAULT_BRAND = {"ink": "#191919", "paper": "#f7f6f3", "accents": ["#2383e2", "#e5484d", "#f5b82e"],
                 "mascot": False}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_SCENES = 16

# Story structures: the arc the agent writes to, and how fast the builder plays it. `arc` is
# the agent's brief; the builder only reads `pace` (a multiplier on reading holds).
STORIES = {
    "showcase": dict(pace=1.0, arc="logo, a headline, then one product scene per capability with a short "
                     "headline between them, ending on the end card. The original launch reel."),
    "problem_solution": dict(pace=1.0, arc="open on the pain (problem), turn with a headline that names the "
                             "product as the answer, show two or three product scenes solving that pain, land "
                             "a stat, end card."),
    "before_after": dict(pace=1.0, arc="logo, a headline, a split scene contrasting the old way with the new "
                         "way, then the product scenes that make the after true, a compare table, end card."),
    "deep_dive": dict(pace=1.1, arc="one feature only, shown in depth: logo, a headline naming the feature, "
                      "three or four scenes that each show a different moment of that one feature (setup, use, "
                      "result), a stat for the outcome, end card."),
    "rapid_fire": dict(pace=0.75, arc="fast: logo, feature_flash with five or six one-word features, two quick "
                       "product scenes, logo_grid, end card. Few words everywhere."),
    "countdown": dict(pace=0.95, arc="logo, a countdown of three reasons to use the product, then one product "
                      "scene proving the top reason, end card."),
}


def _hex(v, default):
    v = str(v or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        v = "#" + "".join(ch * 2 for ch in v[1:])
    return v.lower() if _HEX.match(v) else default


def normalize(spec: dict) -> dict:
    spec = copy.deepcopy(spec or {})
    b = {**DEFAULT_BRAND, **(spec.get("brand") or {})}
    b["name"] = " ".join(str(b.get("name") or "Product").split())[:40]
    b["ink"] = _hex(b.get("ink"), DEFAULT_BRAND["ink"])
    b["paper"] = _hex(b.get("paper"), DEFAULT_BRAND["paper"])
    acc = [_hex(a, None) for a in (b.get("accents") or [])]
    acc = [a for a in acc if a][:3]
    b["accents"] = (acc + DEFAULT_BRAND["accents"])[:3] if acc else list(DEFAULT_BRAND["accents"])
    b["mascot"] = bool(b.get("mascot"))
    scenes = [s for s in (spec.get("scenes") or []) if isinstance(s, dict) and s.get("type") in SCENES]
    if not scenes:
        scenes = [{"type": "logo"}, {"type": "headline", "lines": [f"Meet {b['name']}"]}, {"type": "end"}]
    style = spec.get("style") if spec.get("style") in STYLES else "classic"
    story = spec.get("story") if spec.get("story") in STORIES else "showcase"
    return {"brand": b, "style": style, "story": story, "scenes": scenes[:MAX_SCENES]}


EXAMPLE = {
    "brand": {"name": "Margin AI", "logo_letter": "M", "ink": "#191919", "paper": "#f7f6f3",
              "accents": ["#2383e2", "#e5484d", "#f5b82e"], "mascot": True},
    "scenes": [
        {"type": "logo"},
        {"type": "mascot", "bg": "accent1"},
        {"type": "headline", "lines": ["Meet the new", "Margin AI"], "underline": "new"},
        {"type": "pill_cycle", "lead": "One AI tool to", "end": "do it all.",
         "pills": [{"label": "Find in Google Drive", "icon": "logos:google-drive"},
                   {"label": "Summarize", "icon": "ph:list-bullets-bold"},
                   {"label": "Draft a meeting agenda", "icon": "ph:pencil-simple-line-bold"}]},
        {"type": "app_wall", "lines": ["Find answers", "from all your apps"],
         "apps": ["logos:slack-icon", "logos:google-drive", "logos:figma", "logos:github-icon",
                  "logos:dropbox", "logos:asana-icon", "logos:linear-icon"]},
        {"type": "chat", "bg": "accent1", "greeting": "Hi Sam! How can I help?",
         "suggestions": [{"icon": "ph:list-bullets-bold", "label": "Summarize this page"},
                         {"icon": "ph:question-bold", "label": "Ask a question about this page"},
                         {"icon": "ph:list-checks-bold", "label": "Find action items"},
                         {"icon": "ph:pencil-simple-line-bold", "label": "Draft anything"}],
         "question": "Any updates on the launch plan?",
         "status": [{"icon": "logos:slack-icon", "label": "Scanning Slack..."},
                    {"icon": "logos:google-drive", "label": "Scanning Google Drive..."}],
         "answer_title": "Here's where the launch stands:",
         "answer": ["Beta testing wraps Friday, owned by Priya", "Landing page copy is approved by Marcus",
                    "Pricing page is still in review with Dana", "Launch email is scheduled for Tuesday, 9am"]},
        {"type": "headline", "lines": ["Write smarter, with AI", "that knows your style"]},
        {"type": "doc_edit", "bg": "accent2", "icon": "ph:microphone-stage-fill", "title": "Podcast Release",
         "subtitle": "English Copy",
         "bullets": ["Hype post!", "Announce the new podcast (TechTalks) launching on Wednesday",
                     "Keep it light and fun."],
         "prompt": "Write a post according to", "chip": "Brand Voice Guidelines",
         "output": "Tech enthusiasts, get ready! Our new podcast, TechTalks, launches this Wednesday. "
                   "Join us for easy, honest conversations about the tools changing how we build, "
                   "delivered with our signature style. Your new go-to for tech talk starts now."},
        {"type": "headline", "lines": ["Analyze PDFs", "and images"]},
        {"type": "file_chat", "bg": "accent1", "dashboard_title": "Q3 metrics", "file": "Q3 Proposal.pdf",
         "question": "Recommend next steps for this proposal", "thinking": "Reading the proposal...",
         "answer_title": "Based on this proposal, here are next steps:",
         "answer": ["Review the vendor shortlist with Finance", "Confirm the timeline with the design team",
                    "Book a scoping call with stakeholders", "Draft a budget and pricing outline"]},
        {"type": "chips", "line": "Chat about anything",
         "chips": [{"icon": "ph:lightning-fill", "label": "Fast model"},
                   {"icon": "ph:brain-fill", "label": "Deep thinking"}]},
        {"type": "phone_chat", "bg": "accent3",
         "suggestions": [{"icon": "ph:magnifying-glass-bold", "label": "Look up updates on the launch"},
                         {"icon": "ph:microphone-bold", "label": "New voice memo"},
                         {"icon": "ph:list-bullets-bold", "label": "Summarize a page"}],
         "prompt": "Give me 5 ice breakers for a team event", "answer_title": "Here are five quick ones:",
         "answer": ["Two truths and a lie", "Emoji mood check", "Desert island picks", "Hidden talent round",
                    "Childhood photo guess"]},
        {"type": "end", "cta": "Try Margin AI for free", "tagline": "Think it. Write it."},
    ],
}
