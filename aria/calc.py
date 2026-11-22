"""Spoken arithmetic.

The old version passed user text straight into eval(). This parses the
expression with the ast module and only allows numbers and a handful of
operators, so "what is __import__('os')..." just fails to parse.
"""

from __future__ import annotations

import ast
import math
import operator
import re

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt}

# order matters: longer phrases first
_WORD_OPS = [
    (r"\bmultiplied by\b", "*"),
    (r"\bdivided by\b", "/"),
    (r"\bto the power of\b", "**"),
    (r"\bsquare root of\b", "sqrt "),
    (r"\bsquared\b", "**2"),
    (r"\bcubed\b", "**3"),
    (r"\bpercent of\b", "/100*"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\btimes\b", "*"),
    (r"\bx\b", "*"),
    (r"\bover\b", "/"),
    (r"\bmod(ulo)?\b", "%"),
]

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

MAX_EXPONENT = 100


class CalcError(ValueError):
    pass


def normalise(text: str) -> str:
    """Turn 'what is five times 3.5' into '5 * 3.5'."""
    t = text.lower()
    t = re.sub(r"^(hey aria,?\s*)?(please\s+)?(calculate|compute|what is|what's|whats)\s+", "", t)
    t = t.replace("?", "").replace(",", "")
    for pattern, repl in _WORD_OPS:
        t = re.sub(pattern, f" {repl} ", t)
    t = re.sub(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b",
               lambda m: str(_NUMBER_WORDS[m.group(1)]), t)
    t = re.sub(r"sqrt\s+([\d.]+)", r"sqrt(\1)", t)
    return re.sub(r"\s+", " ", t).strip()


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError("exponent too large")
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS and len(node.args) == 1 and not node.keywords):
        return _FUNCS[node.func.id](_eval(node.args[0]))
    raise CalcError(f"unsupported expression: {ast.dump(node)[:40]}")


def evaluate(text: str) -> float:
    expr = normalise(text)
    if not expr:
        raise CalcError("empty expression")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"can't parse {expr!r}") from exc
    try:
        return _eval(tree)
    except ZeroDivisionError as exc:
        raise CalcError("division by zero") from exc


def format_number(x: float) -> str:
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)
