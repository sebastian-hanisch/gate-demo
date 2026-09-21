"""Die Preset-Kriterien einzeln an ihren Schwellen: künstliche Werte, bei denen genau ein Kriterium kippt (Muster aus den Hafen-Demos)."""

import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
import gate_stories as ST

FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO


def mk(mean, shift=0.0, mean_b=None, mean_u=None):
    return Q.Metrics(n=100, mean=mean, p95=mean * 3, over_limit=0.0, max_wait=mean * 4, util=0.5, shift=shift, booked_share=1.0, nofit_share=0.0, mean_booked=mean_b, mean_unbooked=mean_u,
                     p95_booked=None, p95_unbooked=None)


def rows(fr, sh, pr=None, shift=0.0, mean_b=None, mean_u=None, n=3):
    return tuple(E.DayRow(i, {FR: mk(fr), SH: mk(sh, shift), PR: mk(sh if pr is None else pr, shift, mean_b, mean_u)}) for i in range(n))


def flags(name, r):
    return [ok for ok, _ in ST.criteria(name, r)]


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        ST.criteria("unbekannt", rows(1, 1))
    with pytest.raises(KeyError):
        ST.holds("unbekannt", rows(1, 1)[0])


def test_ruhiger_tag_thresholds():
    assert flags("Ruhiger Tag", rows(0.5, 0.4, shift=0.5)) == [True, True, True]
    assert flags("Ruhiger Tag", rows(1.0, 0.9))[0] is True and flags("Ruhiger Tag", rows(1.01, 1.0))[0] is False
    assert flags("Ruhiger Tag", rows(0.9, 0.0))[1] is True and flags("Ruhiger Tag", rows(0.9, 1.0))[1] is True and flags("Ruhiger Tag", rows(0.9, 2.0))[1] is False
    assert flags("Ruhiger Tag", rows(0.5, 0.4, shift=1.0))[2] is True and flags("Ruhiger Tag", rows(0.5, 0.4, shift=1.01))[2] is False
    assert flags("Ruhiger Tag", rows(0.9, 1.91))[1] is False                                     # der Unterschied gilt in beide Richtungen
    assert flags("Ruhiger Tag", rows(0.5, 1.5))[1] is True and flags("Ruhiger Tag", rows(0.5, 1.5001))[1] is False and flags("Ruhiger Tag", rows(0.5, 0.0))[1] is True   # genau 1 min gerade erfüllt


def test_stosszeit_thresholds():
    assert flags("Stoßzeit", rows(10, 1.5, shift=9.6)) == [True, True, True]
    assert flags("Stoßzeit", rows(8.0, 1.5))[0] is True and flags("Stoßzeit", rows(7.9, 1.5))[0] is False
    assert flags("Stoßzeit", rows(10, 2.5))[1] is True and flags("Stoßzeit", rows(10, 2.6))[1] is False                                  # 25 %
    assert flags("Stoßzeit", rows(10, 1, shift=15.0))[2] is True and flags("Stoßzeit", rows(10, 1, shift=15.1))[2] is False


def test_halbe_quote_thresholds():
    ok = rows(10, 9, pr=9, mean_b=1.0, mean_u=20.0)
    assert flags("Halbe Quote", ok) == [True, True, True, True]
    assert flags("Halbe Quote", rows(10, 8.0, pr=8.0, mean_b=1.0, mean_u=20.0))[0] is True and flags("Halbe Quote", rows(10, 7.9, pr=7.9, mean_b=1.0, mean_u=20.0))[0] is False
    assert flags("Halbe Quote", rows(10, 9, mean_b=2.0, mean_u=20.0))[1] is True and flags("Halbe Quote", rows(10, 9, mean_b=2.1, mean_u=20.0))[1] is False
    assert flags("Halbe Quote", rows(10, 9, mean_b=1.0, mean_u=15.0))[2] is True and flags("Halbe Quote", rows(10, 9, mean_b=1.0, mean_u=14.9))[2] is False
    assert flags("Halbe Quote", rows(10, 9, pr=9.45, mean_b=1.0, mean_u=20.0))[3] is True and flags("Halbe Quote", rows(10, 9, pr=9.5, mean_b=1.0, mean_u=20.0))[3] is False   # 5 %
    assert flags("Halbe Quote", rows(10, 9, pr=8.55, mean_b=1.0, mean_u=20.0))[3] is True and flags("Halbe Quote", rows(10, 9, pr=8.5, mean_b=1.0, mean_u=20.0))[3] is False


def test_halbe_quote_without_trucks_of_a_class_fails_the_criterion_instead_of_crashing():
    f = flags("Halbe Quote", rows(10, 9, pr=9))                                    # niemand ohne Termin, niemand mit: die Klassenwerte fehlen
    assert f == [True, False, False, True]
    text = " ".join(t for _, t in ST.criteria("Halbe Quote", rows(10, 9, pr=9)))
    assert "keine Lkw" in text
    assert flags("Halbe Quote", rows(10, 9, pr=9, mean_b=1.0))[2] is False and flags("Halbe Quote", rows(10, 9, pr=9, mean_u=20.0))[1] is False


def test_fenster_zu_weit_thresholds():
    assert flags("Fenster zu weit", rows(10, 7.3, shift=1.7)) == [True, True]
    assert flags("Fenster zu weit", rows(10, 6.0))[0] is True and flags("Fenster zu weit", rows(10, 5.9))[0] is False
    assert flags("Fenster zu weit", rows(10, 7, shift=3.0))[1] is True and flags("Fenster zu weit", rows(10, 7, shift=3.1))[1] is False


def test_voller_tag_thresholds():
    assert flags("Voller Tag", rows(30, 5, shift=18)) == [True, True, True]
    assert flags("Voller Tag", rows(20.0, 5))[0] is True and flags("Voller Tag", rows(19.9, 5))[0] is False
    assert flags("Voller Tag", rows(30, 7.5))[1] is True and flags("Voller Tag", rows(30, 7.6))[1] is False
    assert flags("Voller Tag", rows(30, 5, shift=12.0))[2] is True and flags("Voller Tag", rows(30, 5, shift=11.9))[2] is False


def test_holds_applies_the_same_criteria_to_a_single_day():
    day = rows(10, 1.5, shift=9.6, n=1)[0]
    assert ST.holds("Stoßzeit", day) and not ST.holds("Ruhiger Tag", day) and not ST.holds("Voller Tag", day)
    assert ST.holds("Halbe Quote", rows(10, 9, pr=9, mean_b=1.0, mean_u=20.0, n=1)[0]) and not ST.holds("Halbe Quote", rows(10, 9, pr=9, mean_b=3.0, mean_u=20.0, n=1)[0])


def test_key_values_lists_only_the_typical_measures_of_the_preset():
    r = rows(10, 1.5, mean_b=1.0, mean_u=20.0)
    kv = ST.key_values("Stoßzeit", r)
    assert set(kv) == {(FR, "mean"), (SH, "mean")} and kv[(FR, "mean")] == 10 and kv[(SH, "mean")] == 1.5
    assert set(ST.key_values("Halbe Quote", r)) == {(SH, "mean"), (PR, "mean_unbooked")} and ST.key_values("Halbe Quote", r)[(PR, "mean_unbooked")] == 20.0
    assert {n for n, _, _ in ST.TYPICAL} == set(C.PRESETS)
