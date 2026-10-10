"""Motion presets: every entrance, emphasis and exit style that renders, plus a kinetic title, a ring
with a walking key, a stream of packets, a table and comparison bars. Writes motion_presets.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Motion presets", aspect="16:9", background="#0f172a", sfx="soft", stage="steady")
area = p.area()

# Scene 1: a letter-by-letter title that pops in, pulses, then scatters out.
s1 = p.scene("Title")
title = s1.letters("HASHING", cx=area.cx, cy=area.cy, size=150, color="#f8fafc")
s1.step("Letters pop in one by one.").pop(title, stagger=40, from_="below")
s1.step("Then they scatter away.").hide(title, style="scatter")

# Scene 2: entrances, side by side.
s2 = p.scene("Entrances")
cells = area.inset(60, 120).row(5, h=200, gap=50, labels=["drop", "rise", "zoom", "wipe", "slide"])
boxes = [s2.box(lbl, at=c, stroke="#38bdf8") for lbl, c in zip(["drop", "rise", "zoom", "wipe", "slide"], cells)]
st = s2.step("Five ways in.")
for b, style in zip(boxes, ["drop", "rise", "zoom", "wipe", "slide"]):
    st.reveal(b, style=style)
s2.step("One emphasis per beat: a pulse.").pulse(boxes[0])
s2.step("A shake for a mistake.").emphasize(boxes[1], style="shake")
s2.step("A flash to point.").emphasize(boxes[3], style="flash", color="#f59e0b")
s2.step("Shrink, absorb and slide away.").hide(boxes[4], style="shrink").hide(boxes[2], style="absorb", into=boxes[3]) \
    .hide(boxes[0], style="slide")

# Scene 3: a hash ring, servers placed on it, a key that walks clockwise and is absorbed.
s3 = p.scene("Ring")
ring = s3.ring(center=(area.cx, area.cy), r=330, color="#334155")
servers = [ring.dot(a, size=56, color=c, label=n) for a, c, n in ((30, "#38bdf8", "A"), (150, "#22c55e", "B"), (260, "#f59e0b", "C"))]
key = ring.dot(80, size=30, color="#f472b6", label="k")
wedge = ring.arc(30, 150, color="#22c55e")
s3.step("Three servers sit on the ring.").reveal(ring.node).pop([sv for sv in servers])
s3.step("A key lands at eighty degrees.").pop([key])
s3.step("It walks clockwise to the next server.").reveal(wedge, style="draw").walk(key, ring, 150, absorb_into=servers[1])

# Scene 4: a pipe with a packet stream, a table and comparison bars.
s4 = p.scene("Data")
top, bottom = area.inset(60, 60).cut_top(300)
a, b = top.row(2, w=300, h=150, gap=500)
ca, cb = s4.box("Client", at=a), s4.box("Cache", at=b)
pipe = s4.arrow(ca, cb)
left, right = bottom.split(0.55)
tbl = s4.table([["node", "dist"], ["A", "0"], ["B", "4"], ["C", "7"]], at=left, colors={(2, 1): "#14532d"})
bars = s4.compare_bars([("Modulo", 75), ("Ring", 25)], at=right, unit="%")
s4.step("Requests stream from the client to the cache.").reveal(ca).reveal(cb).draw(pipe).stream(pipe, n=3)
s4.step("The table fills column by column.").stagger(tbl.column(0), style="fade").stagger(tbl.column(1), style="pop", offset=600)
s4.step("Seventy five percent of keys move, against twenty five.")\
    .reveal(bars.labels).stagger(bars.bars, style="wipe").pop(bars.numbers, offset=700)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "motion_presets.json"))
