"""A 9:16 Short with a stacked chain: four cards top to bottom joined by labeled arrows.
Writes portrait_stack.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("How a vaccine trains your body", aspect="9:16", voice="shimmer")
s = p.scene("Vaccine")
head_r, body = p.area().cut_top(260)
names = ["Vaccine", "Immune cells", "Antibodies", "Protection"]
links = ["shows a harmless piece", "learn the shape", "remember it"]
# stack() sizes the vertical gaps so each arrow label fits between the cards.
cells = body.stack(4, labels=links, w=760)
title = s.text("How a vaccine\ntrains your body", at=head_r, fontWeight=800)
colors = ["#f472b6", "#38bdf8", "#a78bfa", "#34d399"]
cards = [s.box(n, at=c, stroke=col) for n, c, col in zip(names, cells, colors)]
arrows = [s.arrow(a, b, lab) for a, b, lab in zip(cards, cards[1:], links)]

s.step("How does a vaccine train your body?").reveal(title, style="slideInDown")
s.step("A vaccine shows your body a harmless piece of a germ.").reveal(cards[0], style="slideInLeft")
for i, line in enumerate(["Immune cells study its shape.",
                          "They make antibodies that fit that shape.",
                          "Your body remembers it, so the real germ is stopped fast."]):
    s.step(line).reveal(cards[i + 1], style="slideInLeft").draw(arrows[i])
s.step("That memory is your protection.").set(cards[-1], fill="#065f46")

p.save(sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "portrait_stack.json"))
