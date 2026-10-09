"""A line that draws itself across a labeled chart, with notes at key points. Writes line_chart.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("World population", aspect="16:9")
s = p.scene("Growth")
title_area, body = p.area().cut_top(110)
title = s.text("World population since 1800", at=title_area, fontWeight=700)
data = [(1800, 1.0), (1850, 1.26), (1900, 1.65), (1927, 2.0), (1950, 2.5), (1960, 3.0), (1974, 4.0), (1987, 5.0),
        (1999, 6.0), (2011, 7.0), (2022, 8.0)]
chart = s.line_chart(data, at=body.inset(40, 10), x_range=(1800, 2025), y_range=(0, 9),
                     x_ticks=[1800, 1850, 1900, 1950, 2000], y_ticks=[0, 2, 4, 6, 8],
                     y_title="billions of people", notes={3: "2 billion", 10: "8 billion"})

s.step("In 1800 there were about one billion people.").reveal(title).reveal(chart, offset=300)
s.step("It took until 1927 to reach two billion.").extend(chart, 3)
s.step("Then growth sped up: eight billion by 2022.", duration=5000).extend(chart)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "line_chart.json"))
