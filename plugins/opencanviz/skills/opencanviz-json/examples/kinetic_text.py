"""Kinetic type: a written-on title, a typed subtitle, staggered lines, a number that pops, then a
colour wipe into the next scene and a morph that carries one box across. Writes kinetic_text.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Why queues help", aspect="16:9", background="#0f172a")
area = p.area()

# Scene 1: a title written on by a marker, a typed subtitle under it.
s1 = p.scene("Title")
title_r, rest = area.inset(100, 0).cut_top(area.h * 0.55, gap=20)
title = s1.text("Why queues help", at=title_r.cut_bottom(170)[1], fontWeight=800)
sub = s1.text("Three reasons, in one minute", at=rest.cut_top(90)[0], fontSize=44, color="#94a3b8")
s1.step("Why do queues help?").reveal(title, style="write")
s1.step("Three reasons, in one minute.").reveal(sub, style="type_quiet")

# Scene 2: three reasons that come in one after another, then a number that pops.
s2 = p.scene("Reasons", transition="colorWipe", color="#f59e0b", background="#1e1b4b")
head_r, body = area.cut_top(110)
head = s2.text("A queue lets you", at=head_r, fontWeight=700)
list_r, num_r = body.inset(60, 20).split(0.62)
reasons = s2.lines(["Absorb a traffic spike", "Retry what failed", "Scale workers on their own"], at=list_r)
num_box, job_box = num_r.inset(40, 20).cut_bottom(160)
num = s2.text("10x", at=num_box, fontWeight=800, color="#f59e0b")
job = s2.box("Job", at=job_box.inset(40, 0), morph_key="job", fill="#3b0764", stroke="#c084fc")
s2.step("A queue does three things for you.").reveal(head).reveal_lines(reasons, offset=300)
s2.step("It can soak up ten times the normal load.").reveal(num, style="pop").reveal(job)

# Scene 3: the same job box morphs into its place in the pipeline.
s3 = p.scene("Pipeline", transition="morph", transition_ms=800)
a, q, w = area.row(3, w=440, h=420, gap=180)
api = s3.box("API", at=a, stroke="#38bdf8")
job3 = s3.box("Job", at=q, morph_key="job", fill="#3b0764", stroke="#c084fc")
worker = s3.box("Worker", at=w, stroke="#22c55e")
s3.step("Each job waits in the queue until a worker is free.").reveal(api).reveal(worker, offset=200)
s3.step("The worker pulls it when it is ready.").draw(s3.arrow(api, job3)).draw(s3.arrow(job3, worker), offset=400)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "kinetic_text.json"))
