---
name: arithmetic-answers
description: Answers a short arithmetic question with just the number. Use when the user asks to compute a sum, difference, or product and wants only the result back.
---

# Arithmetic answers

Read the expression, compute it, and reply with the number alone — no units, no
working, no trailing punctuation.

Inputs are not always tidy: people write number words ("plus", "minus", "times")
and thousands separators ("1,200"). Normalize the expression to plain digits and
operators before computing.
