"""Two boxes, one arrow, two steps. Writes minimal.json (or the path given as the first argument)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Idea to video", aspect="16:9")
s = p.scene("Idea to video")
left, right = p.area().row(2, w=420, h=240, gap=400)
idea = s.box("Idea", at=left)
video = s.box("Video", at=right, stroke="#a78bfa")
link = s.arrow(idea, video)

s.step("Every video starts with an idea.").reveal(idea)
s.step("openCanviz turns it into a video.").reveal(video, duration=400).draw(link)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimal.json"))
