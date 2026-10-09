"""Bubble sort on an array: pointers compare neighbours, swaps slide, a bracket marks the sorted tail.
Writes bubble_sort.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402

p = Project("Bubble sort", aspect="16:9")
s = p.scene("One pass")
title_area, body = p.area().cut_top(110)
th = p.colors

title = s.text("Bubble sort: swap neighbours that are out of order", at=title_area, fontWeight=700)
arr = s.array([5, 2, 8, 1, 9], at=body.inset(140, 40))
i_ptr = s.pointer(arr, 0, label="j", color=th["hi"])
j_ptr = s.pointer(arr, 1, label="j+1", color=th["accent"])

s.step("Bubble sort walks the list and compares each pair of neighbours.").reveal(title).reveal(arr, offset=300)
s.step("5 is bigger than 2, so they swap.").color(arr, {0: th["hi"], 1: th["hi"]}).swap(arr, 0, 1)
s.step("5 and 8 are in order. Move on.").color(arr, {0: None, 1: None}).point(i_ptr, 1).point(j_ptr, 2)
s.step("8 is bigger than 1, so they swap.").color(arr, {2: th["hi"], 3: th["hi"]}).point(i_ptr, 2) \
    .point(j_ptr, 3).swap(arr, 2, 3)
s.step("8 and 9 are in order.").color(arr, {2: None, 3: None}).point(i_ptr, 3).point(j_ptr, 4)
s.step("After one pass the biggest value has bubbled to the end.").color(arr, {4: th["ok"]}) \
    .bracket(arr, 4, 4, label="sorted", color=th["ok"])

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "bubble_sort.json"))
