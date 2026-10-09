"""A number that counts up and a progress bar that fills. Writes counter_progress.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Upload progress", aspect="16:9")
s = p.scene("Upload")
title_area, body = p.area().cut_top(110)
title = s.text("Uploading a video", at=title_area, fontWeight=700)
num_area, bar_area = body.inset(200, 60).column(2, gap=60)
count = s.counter(2048, at=num_area, suffix=" MB", duration=2500)
bar = s.progress(0, at=bar_area.inset(0, (bar_area.h - 40) / 2))

s.step("A two gigabyte video starts uploading.").reveal(title).reveal(bar, offset=300)
s.step("The bytes stream up while the bar fills.", duration=3500).reveal(count).set(bar, value=1)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "counter_progress.json"))
