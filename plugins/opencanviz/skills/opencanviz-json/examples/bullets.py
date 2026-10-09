"""A list of points, each with a check that draws itself in. Writes bullets.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Good passwords", aspect="16:9")
s = p.scene("Tips")
title_area, body = p.area().cut_top(110)
title = s.text("Three rules for a good password", at=title_area, fontWeight=700)
points = s.bullets(["Make it long: 14 characters or more", "Never reuse it on another site",
                    "Keep it in a password manager"], at=body.inset(160, 40))

s.step("Three rules make a password hard to crack.").reveal(title)
for pt, line in zip(points, ["Length matters most.", "Reuse turns one leak into many.", "A manager remembers them for you."]):
    s.step(line).reveal(pt)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "bullets.json"))
