"""Step through a function line by line with a highlight and a variable box. Writes code_walkthrough.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from opencanviz import Project  # noqa: E402


p = Project("Factorial, line by line", aspect="16:9")
s = p.scene("factorial(4)")
title_area, body = p.area().cut_top(110)
left, right = body.split(0.68)                        # code gets the width; the variables are narrow
title = s.text("How factorial(4) runs", at=title_area, fontWeight=700)
code = s.code("def factorial(n):\n    result = 1\n    for i in range(2, n + 1):\n        result = result * i\n    return result",
              at=left)
r_box, i_box = right.column(2, gap=40, h=120)         # stacked next to the code, centered
result = s.variable("result", "-", at=r_box)
i_var = s.variable("i", "-", at=i_box)

s.step("Here is a function that multiplies the numbers from 1 to n.").reveal(title).reveal(code, offset=300)
s.step("result starts at 1.").highlight(code, 2).reveal(result).assign(result, 1)
s.step("The loop runs i from 2 up to n.").highlight(code, 3).reveal(i_var).assign(i_var, 2)
s.step("result becomes 1 times 2, which is 2.").highlight(code, 4).assign(result, 2)
s.step("Next i is 3, and result becomes 6.").highlight(code, 3, 4).assign(i_var, 3).assign(result, 6)
s.step("Then i is 4, and result becomes 24.").highlight(code, 3, 4).assign(i_var, 4).assign(result, 24)
s.step("The loop ends, and the function returns 24.").highlight(code, 5)

p.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "code_walkthrough.json"))
