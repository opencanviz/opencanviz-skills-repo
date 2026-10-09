"""A node that travels along a curved path, and a dot sent along an arrow. Writes path_follow.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("A parcel on its way", aspect="16:9")
s = p.scene("Route")
title_area, body = p.area().cut_top(110)
title = s.text("A parcel on its way", at=title_area, fontWeight=700)
a, b, c = body.inset(0, 200).row(3, gap=300)
shop = s.box("Shop", at=a)
hub = s.box("Hub", at=b)
home = s.box("Home", at=c)
road = s.arrow(hub, home)
parcel = s.node("circle", None, x=a.cx - 25, y=a.y - 90, w=50, h=50, id="parcel", fill=p.colors["hi"], stroke="none",
                noGlow=True)
route = s.path([(a.cx, a.y - 65), ((a.cx + b.cx) / 2, a.y - 220), (b.cx, b.y - 65)])

s.step("A parcel leaves the shop.").reveal(title).reveal([shop, hub], offset=300).reveal(parcel, offset=600)
s.step("A truck carries it to the hub.").follow(parcel, route, duration=2000)
s.step("From the hub it goes out for delivery.").reveal(home).draw(road).packet(road)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "path_follow.json"))
