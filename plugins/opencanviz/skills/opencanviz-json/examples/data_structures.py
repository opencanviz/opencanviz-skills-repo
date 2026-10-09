"""A tree, a linked list and a graph with pointers and colors. Writes data_structures.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Three data structures", aspect="16:9")
th = p.colors
s = p.scene("Tree")
title_area, body = p.area().cut_top(110)
title = s.text("A binary search tree", at=title_area, fontWeight=700)
tree = s.tree({"8": ["4", "12"], "4": ["2", "6"], "12": ["10", "14"]}, at=body)
cur = s.pointer(tree, "8", label="cur")
s.step("Looking for 6 in a binary search tree.").reveal(title).reveal(tree, offset=300)
s.step("6 is less than 8, so go left.").color(tree, {"8": th["muted"]}).point(cur, "4")
s.step("6 is more than 4, so go right. Found it.").color(tree, {"4": th["muted"], "6": th["ok"]}).point(cur, "6")

s2 = p.scene("List")
title_area, body = p.area().cut_top(110)
t2 = s2.text("A linked list", at=title_area, fontWeight=700)
lst = s2.linked_list([3, 7, 1], at=body.inset(40, 200), capacity=4)
s2.step("Each node points to the next one.").reveal(t2).reveal(lst, offset=300)
s2.step("Adding at the tail links one more node.").append(lst, 9)

s3 = p.scene("Graph")
title_area, body = p.area().cut_top(110)
t3 = s3.text("A graph", at=title_area, fontWeight=700)
g = s3.graph({"A": (0, 0.5), "B": (0.4, 0), "C": (0.4, 1), "D": (1, 0.5)},
             [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], at=body.inset(200, 40))
s3.step("Four places joined by roads.").reveal(t3).reveal(g, offset=300)
s3.step("One route from A to D goes through B.").color(g, {"A": th["ok"], "B": th["ok"], "D": th["ok"]},
                                                     edges={("A", "B"): th["ok"], ("B", "D"): th["ok"]})

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_structures.json"))
