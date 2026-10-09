"""A scatter chart whose dots move into two groups, and a grid filled cell by cell (dynamic programming).
Writes scatter_grid.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Scatter and grid", aspect="16:9")
th = p.colors

s = p.scene("Clusters")
title_area, body = p.area().cut_top(110)
title = s.text("Grouping customers by spend and visits", at=title_area, fontWeight=700)
start = [(2, 3), (3, 7), (4, 2), (6, 8), (7, 3), (8, 7), (5, 5), (2, 8)]
chart = s.scatter(start, at=body.inset(160, 0), x_range=(0, 10), y_range=(0, 10),
                  x_ticks=[0, 5, 10], y_ticks=[0, 5, 10], x_title="visits per month", y_title="spend")
s.step("Each dot is one customer.").reveal(title).reveal(chart, offset=300)
low, high = th["accent"], th["ok"]
s.step("They settle into two groups: casual and loyal.").scatter_to(
    chart, [(2, 2), (3, 3), (2, 3), (8, 8), (3, 2), (8, 7), (7, 8), (7, 7)],
    colors=[low, low, low, high, low, high, high, high])

s2 = p.scene("Grid")
title_area, body = p.area().cut_top(110)
t2 = s2.text("Counting paths across a grid", at=title_area, fontWeight=700)
grid = s2.grid([[1, 1, 1], [1, "", ""], [1, "", ""]], at=body.inset(500, 20))
s2.step("The top row and the left column each have one path.").reveal(t2).reveal(grid, offset=300)
s2.step("Each cell adds the cell above and the cell to its left.").set_cell(grid, 1, 1, 2) \
    .color(grid, {(1, 1): th["hi"]})
s2.step("Keep filling, one cell at a time.").set_cell(grid, 1, 2, 3).color(grid, {(1, 1): None, (1, 2): th["hi"]})
s2.step("The corner holds the answer: six paths.").set_cell(grid, 2, 1, 3).set_cell(grid, 2, 2, 6).color(grid, {(1, 2): None, (2, 2): th["ok"]})

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "scatter_grid.json"))
