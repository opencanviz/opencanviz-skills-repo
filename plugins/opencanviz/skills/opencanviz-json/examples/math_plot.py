"""Math and graphs: a derivation whose changed term flashes, a plot with a curve drawn on, a shaded
area and a tangent that rides the curve, then a triangle, a matrix, a number line and a Venn diagram.
Needs node and mathjax-full (npm i mathjax-full, or set MATHJAX_PATH). Writes math_plot.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Math and graphs", aspect="16:9", background="#0f172a", stage="steady")
area = p.area()


def sq(x):
    return x * x


# Scene 1: a derivation, one line per step; the term that changes flashes.
s1 = p.scene("Derivation")
title, body = s1.title("The derivative of x squared")
lines = s1.derivation([[r"f(x) =", r"x^2"],
                       [r"f'(x) =", r"\lim_{h \to 0} \frac{(x+h)^2 - x^2}{h}"],
                       [r"=", r"\lim_{h \to 0} (2x + h)"],
                       [r"=", r"2x"]], at=body.inset(100, 0), size=60, align="eq")
s1.step("Start with f of x equals x squared.").reveal(title).stagger(lines[0], style="wipe", gap=400)
s1.step("The derivative is a limit.").stagger(lines[1], style="fade", gap=300)
s1.step("Expand and cancel the h.").stagger(lines[2], style="fade", gap=300)
s1.step("As h goes to zero, two x is left.").stagger(lines[3], style="fade", gap=300)
s1.step("That is the answer.").emphasize(lines[3][1], style="flash", color="#f59e0b")

# Scene 2: the curve, the area under it and a tangent that rides it.
s2 = p.scene("Plot")
plot_r, side = area.inset(40, 20).split(0.68)
pl = s2.plot(plot_r, (-3, 3), (-1, 9), x_ticks=[-3, -2, -1, 0, 1, 2, 3], y_ticks=[0, 2, 4, 6, 8], grid=True,
             x_label="x", y_label="y")
curve = pl.curve(sq, color="#38bdf8")
shade = pl.area(sq, 0, 2, color="#22c55e")
dot = pl.point(-2, 4, size=30, color="#f59e0b")
tan = pl.tangent(sq, -2, length=320, color="#f59e0b")
key = pl.legend([("y = x squared", "#38bdf8"), ("tangent", "#f59e0b")])
eq = s2.math(r"\text{slope} = 2x", at=side.inset(20, 0).cut_top(160)[0], size=60)
s2.step("Here is x squared.").reveal(pl.node).reveal(curve, style="draw").reveal(key)
s2.step("The area from zero to two.").reveal(shade)
s2.step("A tangent touches the curve at one point.").pop([dot]).reveal(tan, style="zoom")
s2.step("As the point slides, the slope changes: two x.").reveal(eq, style="wipe") \
    .ride(dot, pl, sq, -2, 2, duration=2600, tangent=tan)

# Scene 3: geometry, a matrix, a number line and a Venn diagram.
s3 = p.scene("Shapes")
top, bottom = area.inset(40, 20).cut_top(area.h * 0.52)
tri_r, mat_r = top.split(0.5)
A, B, C = (tri_r.x + 40, tri_r.y + tri_r.h - 30), (tri_r.x + tri_r.w - 60, tri_r.y + tri_r.h - 30), (tri_r.x + 40, tri_r.y + 40)
tri = s3.poly([A, B, C], color="#38bdf8", width=5)
ang = s3.angle_mark(B, A, C, r=70, color="#f59e0b", label="θ")
side_a = s3.side_label(A, B, "4", offset=-40)
side_b = s3.side_label(C, A, "3", offset=-40)
mat = s3.matrix([["1", "0"], ["0", "1"]], at=mat_r.inset(120, 30))
nl_r, venn_r = bottom.split(0.5)
nl = s3.number_line(nl_r.inset(20, 60), 0, 5, 1)
mark = nl.point(3, color="#f472b6")
venn = s3.venn(["A", "B"], at=venn_r.inset(20, 0))
s3.step("A right triangle.").reveal(tri, style="draw").reveal(side_a).reveal(side_b)
s3.step("And the angle at B.").reveal(ang, style="draw")
s3.step("The identity matrix, row by row.").reveal(mat.node).tint(mat.row(0), "#f59e0b")
s3.step("Three on the number line.").reveal(nl.node).pop([mark])
s3.step("Two sets that overlap.").pop(venn, stagger=200)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "math_plot.json"))
