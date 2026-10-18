"""Date-based Plant Battle day labels: never derive duration from plant metadata."""
from datetime import date
from cloud.app.battle_calendar import battle_progress


def test_competition_days():
    a, b = date(2026, 10, 12), date(2026, 10, 18)
    assert battle_progress(a, b, today=a) == (1, 7)
    assert battle_progress(a, b, today=date(2026, 10, 17)) == (6, 7)
    assert battle_progress(a, b, today=b) == (7, 7)
    assert battle_progress(a, b, today=date(2026, 10, 19)) == (7, 7)
    assert battle_progress(a, b, today=date(2026, 10, 11)) == (None, 7)
    assert battle_progress(date(2026, 10, 19), date(2026, 10, 25), today=b) == (None, 7)
    assert battle_progress(a, a, today=a) == (1, 1)
    assert battle_progress(a, None, today=b) == (None, None)
    assert battle_progress(None, b, today=b) == (None, None)
    assert battle_progress(b, a, today=b) == (None, None)


if __name__ == "__main__":
    test_competition_days()
    print("PASS: calendar duration inclusive, before/during/after, missing dates")
