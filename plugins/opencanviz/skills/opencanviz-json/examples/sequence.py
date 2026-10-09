"""A sequence diagram: lifelines, messages sent one by one, an activation bar. Writes sequence.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Logging in", aspect="16:9")
s = p.scene("Login")
title_area, body = p.area().cut_top(110)
title = s.text("What happens when you log in", at=title_area, fontWeight=700)
browser, server, db = s.sequence(["Browser", "Server", "Database"], at=body)
m1 = s.message(browser, server, "POST /login")
m2 = s.message(server, db, "find user")
m3 = s.message(db, server, "user row", reply=True)
m4 = s.message(server, browser, "session cookie", reply=True)

s.step("Three parts take part in a login.").reveal(title).reveal([browser, server, db], offset=300)
s.step("The browser sends the username and password.").draw(m1)
s.step("The server looks the user up.").draw(m2)
s.step("The database sends the row back.").draw(m3).activate(server, m1, m4)
s.step("The server answers with a session cookie.").draw(m4)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "sequence.json"))
