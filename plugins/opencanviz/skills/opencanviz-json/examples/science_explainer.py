"""A 3-scene narrated science explainer (why the sky is blue): title card, a labeled chain, and a
noon-versus-sunset comparison. Writes science_explainer.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Why the sky is blue", aspect="16:9", voice="nova")
area = p.area()

# Scene 1: title card with a sun.
s1 = p.scene("Title")
icon_r, rest = area.cut_top(area.h * 0.45)
title_r, sub_r = rest.cut_top(130, gap=20)
sun = s1.node("circle", id="sun", at=icon_r.centered(icon_r.h * 0.8, icon_r.h * 0.8), fill="#fbbf24", stroke="#f59e0b")
title = s1.text("Why the sky is blue", at=title_r, fontWeight=800)
sub = s1.text("Sunlight, air, and a little physics", at=sub_r.cut_top(70)[0], fontSize=40, color="#94a3b8")
s1.step("Why is the sky blue?", narration="Look up on a clear day. Why is the sky blue?").reveal(sun).reveal(title, offset=300)
s1.step("Sunlight, air, and a little physics.").reveal(sub, style="slideInUp")

# Scene 2: a chain with edge labels; flow() sizes the gaps so each label fits.
s2 = p.scene("Scattering", transition="slideLeft")
labels = ["all colors", "blue scatters most"]
r = area.flow(3, labels=labels)
light = s2.box("Sunlight", at=r[0], stroke="#fbbf24")
air = s2.node("circle", "Air molecules", at=r[1].centered(min(r[1].w, r[1].h)), stroke="#38bdf8")
eye = s2.box("Your eye", at=r[2], stroke="#a78bfa")
a1 = s2.arrow(light, air, labels[0])
a2 = s2.arrow(air, eye, labels[1], stroke="#38bdf8")
s2.step("Sunlight holds every color.", narration="Sunlight looks white, but it holds every color of the rainbow.").reveal(light)
s2.step("Air molecules scatter short blue waves the most.").reveal(air).draw(a1)
(s2.step("That scattered blue reaches your eye from all over the sky.")
 .reveal(eye).draw(a2).set(air, fill="#0c4a6e"))

# Scene 3: noon versus sunset, two rows of the same chain.
s3 = p.scene("Sunsets", transition="crossfade")
top, bottom = area.column(2, gap=80)
rows = []
for band, (when, path, sky, color) in zip((top, bottom), [("Noon", "short path", "Blue sky", "#38bdf8"),
                                                           ("Sunset", "long path", "Red sky", "#f97316")]):
    a, b = band.row(2, labels=[path], w=520)
    start = s3.box(when, at=a, stroke=color)
    end = s3.box(sky, at=b, stroke=color, fill="#1e293b")
    rows.append((start, end, s3.arrow(start, end, path, stroke=color)))
(noon, blue, n_link), (dusk, red, d_link) = rows
s3.step("At noon, light crosses a thin layer of air.").reveal(noon).reveal(blue).draw(n_link)
(s3.step("At sunset it crosses much more, so the blue scatters away.",
         narration="At sunset, light crosses much more air. The blue scatters away before it reaches you, "
                   "and reds and oranges are left.")
 .reveal(dusk).reveal(red).draw(d_link).set(red, fill="#7c2d12"))

p.save(sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "science_explainer.json"))
