import pytest

from aria.calc import CalcError, evaluate, format_number, normalise


@pytest.mark.parametrize("text,expected", [
    ("what is 25 times 4", 100),
    ("calculate 7 plus 8 minus 5", 10),
    ("what's 2 to the power of 10", 1024),
    ("what is twelve divided by four", 3),
    ("15 percent of 240", 36),
    ("square root of 81", 9),
    ("(2 + 3) * 4", 20),
    ("what is 3 squared", 9),
    ("minus 4 plus 10", 6),
])
def test_evaluate(text, expected):
    assert evaluate(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [
    "__import__('os').system('ls')",
    "what is open('x')",
    "calculate a.b",
    "2 ** 1000000",
    "",
    "what is love",
])
def test_rejects_anything_that_isnt_maths(text):
    with pytest.raises(CalcError):
        evaluate(text)


def test_division_by_zero():
    with pytest.raises(CalcError):
        evaluate("5 divided by 0")


def test_normalise():
    assert normalise("What is five times three?") == "5 * 3"


def test_format_number():
    assert format_number(4.0) == "4"
    assert format_number(1 / 3) == "0.333333"
