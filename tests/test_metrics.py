import math

from toolcut.metrics import bootstrap_mean, paired_diff, wilson


def test_wilson_known_values():
    lo, hi = wilson(40, 40)
    assert hi == 1.0 and math.isclose(lo, 0.9124, abs_tol=1e-3)
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and math.isclose(hi, 0.2775, abs_tol=1e-3)
    lo, hi = wilson(20, 40)
    assert math.isclose(lo, 0.352, abs_tol=1e-3) and math.isclose(hi, 0.648, abs_tol=1e-3)


def test_wilson_empty():
    assert wilson(0, 0) == (0.0, 1.0)


def test_bootstrap_is_seeded_and_brackets_the_mean():
    vals = [1, 2, 3, 4, 10, 2, 3]
    a = bootstrap_mean(vals)
    assert a == bootstrap_mean(vals)
    m, lo, hi = a
    assert lo <= m <= hi
    assert bootstrap_mean([5, 5, 5]) == (5, 5, 5)


def test_paired_diff():
    assert paired_diff([1, 2, 3], [1, 2, 3]) == (0, 0, 0)
    m, lo, hi = paired_diff([1, 2, 3, 4], [2, 4, 6, 8])
    assert m == 2.5 and lo <= m <= hi
