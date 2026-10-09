"""A 9:16 Short: a headline, three stacked cards and a progress bar, in the single-scene (flat) form.
Writes short.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("3 habits of fast teams", aspect="9:16", theme="light", background="#fffbeb")
s = p.scene("3 habits of fast teams")
# area() already leaves the bottom 30% clear for captions.
head_r, body = p.area().inset(20, 0).cut_top(320)
cards_r, bar_r = body.cut_bottom(28, gap=60)

ink = "#1c1917"
headline = s.text("3 habits of\nfast teams", at=head_r, fontWeight=800, lineHeight=1.1, color=ink)
cards = []
for r, label, color in zip(cards_r.stack(3, gap=48), ["Ship small", "Review fast", "Automate tests"],
                           ["#fde68a", "#bbf7d0", "#bfdbfe"]):
    cards.append(s.box(label, at=r, fill=color, stroke=ink, strokeWidth=4, cornerRadius=28,
                       labelColor=ink, labelFontWeight="bold"))
bar = s.progress(0, at=bar_r, fill="#e7e5e4")

s.step("Three habits of fast teams.").reveal(headline, style="slideInUp")
lines = ["One: ship small changes.", "Two: review them the same day.", "Three: let tests catch the mistakes."]
for i, (card, line) in enumerate(zip(cards, lines)):
    s.step(line).reveal(card, style="slideInLeft").set(bar, value=round((i + 1) / 3.0, 3))

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "short.json"),
       flat=True)
