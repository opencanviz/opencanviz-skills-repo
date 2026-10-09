"""A four-step 16:9 flow diagram with a title, captions and narration. Writes flow.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("How a web request travels", aspect="16:9")
s = p.scene("Request")
title_area, body = p.area().cut_top(110)
cells = body.flow(3)

title = s.text("How a web request travels", at=title_area, fontWeight=700)
client = s.box("Browser", at=cells[0])
server = s.box("API server", at=cells[1], stroke="#a78bfa")
db = s.node("cylinder", "Database", at=cells[2], stroke="#34d399")
to_server = s.arrow(client, server)
to_db = s.arrow(server, db)

s.step("A request starts in the browser.").reveal(title).reveal(client, offset=400)
s.step("It travels to the API server.").reveal(server, duration=400).draw(to_server, duration=600)
s.step("The server asks the database for the data.").reveal(db, duration=400).draw(to_db, duration=600)
(s.step("The database answers, and the page loads.", easing="ease-out")
 .set(db, fill="#065f46").set(client, fill="#0c4a6e")
 .set(to_server, animationStyle="ball").set(to_db, animationStyle="ball"))

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "flow.json"))
