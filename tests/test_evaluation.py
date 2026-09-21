import statistics

import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
import gate_scenario as S

FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO
P = E.Params(4, 650, 3, 50, 90, 100, 10)


def mk(mean, p95=None, shift=0.0, nofit=0.0, mean_b=None, mean_u=None, over=0.0):
    return Q.Metrics(n=100, mean=mean, p95=p95 if p95 is not None else mean * 3, over_limit=over, max_wait=mean * 4, util=0.5, shift=shift, booked_share=1.0, nofit_share=nofit,
                     mean_booked=mean_b, mean_unbooked=mean_u, p95_booked=None, p95_unbooked=None)


def row(seed, fr=10.0, sh=2.0, pr=2.0, **kw):
    return E.DayRow(seed, {FR: mk(fr), SH: mk(sh, **kw), PR: mk(pr)})


# ---------------------------------------------------------------------------------------------------
# Ein Tag
# ---------------------------------------------------------------------------------------------------
def test_params_derive_capacity_and_utilisation():
    assert E.cap_of(P) == 36 and E.cap_of(P._replace(cap_pct=100)) == 40 and E.cap_of(P._replace(lanes=2, service=5, cap_pct=60)) == 7
    assert E.utilisation_of(P) == pytest.approx(650 * 3 / (4 * 720)) and E.utilisation_of(P._replace(lanes=2, trucks=200, service=5)) == pytest.approx(200 * 5 / (2 * 720))


def test_run_rules_returns_three_rules_on_the_same_day():
    day = E.make_day(P, 3)
    outs = E.run_rules(P, day)
    assert [o.key for o in outs] == list(C.RULE_KEYS) and [o.label for o in outs] == [C.RULE_LABELS[k] for k in C.RULE_KEYS] and all(o.trace is None for o in outs)
    fr, sh, pr = (o.m for o in outs)
    assert fr.booked_share == 0 and fr.shift == 0 and fr.nofit_share == 0 and fr.mean_booked is None and fr.mean_unbooked == fr.mean
    assert sh.booked_share == 1.0 and sh.shift == pytest.approx(8.954, abs=1e-3) and sh.mean_unbooked is None
    assert pr.mean == sh.mean and pr.p95 == sh.p95                                    # bei Quote 100 % sind Termin und Vorrang gleich
    assert E.outcome_of(outs, SH) is outs[1]
    assert all(o.trace is not None for o in E.run_rules(P, day, record=True))


def test_run_rules_with_a_partial_booking_share_separates_the_classes():
    p = P._replace(share_pct=60)
    outs = E.run_rules(p, E.make_day(p, 3))
    sh, pr = outs[1].m, outs[2].m
    assert 0.5 < sh.booked_share < 0.7 and abs(sh.mean_unbooked - sh.mean_booked) < 0.2 * sh.mean            # gemeinsame Schlange: beide Klassen warten gleich
    assert pr.mean_booked < 0.5 * sh.mean_booked and pr.mean_unbooked > 1.3 * sh.mean_unbooked                # Vorrang: die Wartezeit wandert
    assert pr.mean == pytest.approx(sh.mean, rel=0.05) and pr.shift == sh.shift


def test_free_rule_ignores_booking_and_capacity_settings():
    day = E.make_day(P, 3)
    a = E.run_rules(P, day)[0].m
    b = E.run_rules(P._replace(cap_pct=60, share_pct=20), day)[0].m
    assert a == b


def test_make_day_uses_trucks_service_and_peak_share():
    d = E.make_day(P._replace(trucks=100, service=5, peak_pct=0), 4)
    assert d.n == 100 and d == S.make_day(4, 100, 0, 5.0)


# ---------------------------------------------------------------------------------------------------
# Stichprobe und Statistik
# ---------------------------------------------------------------------------------------------------
def test_sample_has_one_row_per_seed_and_matches_direct_runs():
    rows = E.sample(P, 4)
    assert [r.seed for r in rows] == [0, 1, 2, 3]
    direct = {o.key: o.m for o in E.run_rules(P, E.make_day(P, 2))}
    assert rows[2].m == direct and E.day_row(P, 2) == rows[2]


def test_values_and_means_skip_undefined_fields():
    rows = (row(0, mean_u=10.0), row(1), row(2, mean_u=20.0))
    assert E.values(rows, SH, "mean_unbooked") == [10.0, 20.0] and E.mean_of(rows, SH, "mean_unbooked") == 15.0 and E.mean_of(rows, SH) == 2.0
    assert E.mean_of(rows, SH, "mean_booked") is None and E.mean_of(rows, FR, "mean_unbooked") is None


def test_paired_differences_are_rule_minus_reference_and_skip_undefined():
    rows = (row(0, fr=10.0, sh=4.0), row(1, fr=8.0, sh=5.0))
    assert E.paired(rows, SH, FR) == [-6.0, -3.0]
    rows = (row(0, mean_u=10.0), row(1))
    assert E.paired(rows, SH, PR, "mean_unbooked") == []                                # Referenz undefiniert: keine Paare


def test_distribution_counts_better_equal_worse_and_gains():
    rows = (row(0, fr=10, sh=4), row(1, fr=10, sh=10), row(2, fr=10, sh=12), row(3, fr=10, sh=5))
    d = E.distribution(rows, SH, FR)
    assert (d.n, d.better, d.equal, d.worse) == (4, 0.5, 0.25, 0.25) and d.mean_gain == pytest.approx((6 + 0 - 2 + 5) / 4) and d.median_gain == pytest.approx(2.5)
    assert d.field == "mean" and d.key == SH


def test_verdict_three_states_and_the_threshold():
    clear = tuple(row(i, fr=10 + i % 2, sh=2) for i in range(20))
    v = E.verdict(clear, SH, FR)
    assert v.kind == "better" and v.diff < 0 and v.n == 20 and v.pct < 0 and v.field == "mean"
    assert E.verdict(tuple(row(i, fr=2, sh=10 + i % 2) for i in range(20)), SH, FR).kind == "worse"
    assert E.verdict(tuple(row(i, fr=5, sh=5 + (1 if i % 2 else -1)) for i in range(20)), SH, FR).kind == "unclear"
    diffs = [-1, -1, -1, -1, 0, 0, 0, 0, 0, 0]                                            # Mittel -0,4, Standardfehler 0,163: z = 2,45
    assert E.verdict(tuple(row(i, fr=5, sh=5 + d) for i, d in enumerate(diffs)), SH, FR).kind == "better"
    assert E.verdict(tuple(row(i, fr=5, sh=5 + d) for i, d in enumerate([-1, -1, 0, 0, 0, 0, 0, 0, 0, 0])), SH, FR).kind == "unclear"      # z = 1,5


def test_verdict_without_variance_and_with_a_zero_reference():
    same = tuple(row(i, fr=10, sh=4) for i in range(5))
    v = E.verdict(same, SH, FR)
    assert v.kind == "better" and v.se == 0 and v.diff == -6
    assert E.verdict(tuple(row(i, fr=5, sh=5) for i in range(5)), SH, FR).kind == "unclear"
    assert E.verdict(tuple(row(i, fr=5, sh=6) for i in range(5)), SH, FR).kind == "worse"
    zero = tuple(row(i, fr=0.0, sh=1.0) for i in range(5))
    assert E.verdict(zero, SH, FR).pct is None and E.verdict((row(0),), SH, FR).se == 0


def test_verdict_pct_is_relative_to_the_reference_mean():
    v = E.verdict(tuple(row(i, fr=10.0, sh=4.0) for i in range(5)), SH, FR)
    assert v.pct == pytest.approx(-60.0)


# ---------------------------------------------------------------------------------------------------
# Kurven
# ---------------------------------------------------------------------------------------------------
def test_cap_curve_equals_direct_means():
    cv = E.cap_curve(P, 3)
    assert cv.xs == C.CAP_CURVE_POINTS and cv.n_days == 3 and list(cv.series) == ["frei", "termin"]
    for j, c in enumerate(cv.xs):
        q = P._replace(cap_pct=c)
        rows = E.sample(q, 3)
        for f in ("mean", "p95", "shift", "nofit_share", "over_limit"):
            assert cv.series["termin"][f][j] == pytest.approx(E.mean_of(rows, SH, f)), (c, f)
        assert cv.series["frei"]["mean"][j] == pytest.approx(E.mean_of(rows, FR))
    assert cv.series["termin"]["mean"][0] < cv.series["termin"]["mean"][-1]                # engere Fenster: weniger Wartezeit
    assert cv.series["termin"]["shift"][0] > cv.series["termin"]["shift"][-1]              # ... aber mehr Verschiebung


def test_share_curve_equals_direct_means_and_shows_the_priority_effect():
    cv = E.share_curve(P, 3)
    assert cv.xs == C.SHARE_CURVE_POINTS and list(cv.series) == ["frei", "termin", "vorrang"]
    for j, q in enumerate(cv.xs):
        rows = E.sample(P._replace(share_pct=q), 3)
        assert cv.series["termin"]["mean"][j] == pytest.approx(E.mean_of(rows, SH)) and cv.series["vorrang"]["mean"][j] == pytest.approx(E.mean_of(rows, PR))
        assert cv.series["vorrang"]["mean_booked"][j] == pytest.approx(E.mean_of(rows, PR, "mean_booked"))
    u = cv.series["vorrang"]["mean_unbooked"]
    assert u[-1] is None and all(v is not None for v in u[:-1])                            # bei Quote 100 % gibt es keine Lkw ohne Termin
    assert cv.series["termin"]["mean"][0] > cv.series["termin"]["mean"][-1]                # mehr Buchende: weniger Wartezeit
    assert cv.series["vorrang"]["mean_booked"][2] < cv.series["termin"]["mean"][2] < u[2]


def test_lanes_curve_and_lanes_needed():
    cv = E.lanes_curve(P, 3)
    assert cv.xs == tuple(range(2, 11)) and list(cv.series) == ["frei", "termin"]
    for lanes in (3, 6):
        rows = E.sample(P._replace(lanes=lanes), 3)
        j = cv.xs.index(lanes)
        assert cv.series["frei"]["p95"][j] == pytest.approx(E.mean_of(rows, FR, "p95")) and cv.series["termin"]["p95"][j] == pytest.approx(E.mean_of(rows, SH, "p95"))
    assert E.lanes_needed(cv, "termin") < E.lanes_needed(cv, "frei")
    j = cv.xs.index(E.lanes_needed(cv, "frei"))
    assert cv.series["frei"]["p95"][j] <= C.WAIT_LIMIT and (j == 0 or cv.series["frei"]["p95"][j - 1] > C.WAIT_LIMIT)


def test_lanes_needed_edge_cases():
    curve = E.Curve((2, 3, 4), {"a": {"p95": (50.0, 15.0, 3.0)}, "b": {"p95": (50.0, 40.0, 30.0)}, "c": {"p95": (None, 20.0, 1.0)}}, 1)
    assert E.lanes_needed(curve, "a") == 3 and E.lanes_needed(curve, "a", 60) == 2 and E.lanes_needed(curve, "b") is None and E.lanes_needed(curve, "c") == 4


# ---------------------------------------------------------------------------------------------------
# Diagnose
# ---------------------------------------------------------------------------------------------------
def outs(fr, sh, nofit=0.0, mean_u=None):
    return [E.Outcome(FR, "f", mk(fr), None), E.Outcome(SH, "s", mk(sh, nofit=nofit, mean_u=mean_u), None), E.Outcome(PR, "p", mk(sh), None)]


def test_diagnose_kinds_and_their_order_of_precedence():
    assert E.diagnose(outs(0.5, 0.4), P).kind == "calm" and E.diagnose(outs(0.99, 0.9, nofit=0.5), P).kind == "calm"          # ruhig zuerst
    assert E.diagnose(outs(10, 2, nofit=0.03), P).kind == "overload" and E.diagnose(outs(10, 9, nofit=0.03), P._replace(share_pct=60)).kind == "overload"
    assert E.diagnose(outs(10, 9), P._replace(share_pct=60)).kind == "quota" and E.diagnose(outs(10, 9), P._replace(share_pct=80)).kind == "quota"
    assert E.diagnose(outs(10, 9), P._replace(share_pct=90)).kind == "wide" and E.diagnose(outs(10, 9), P).kind == "wide"
    assert E.diagnose(outs(10, 2), P._replace(share_pct=60)).kind == "helps" and E.diagnose(outs(10, 2), P).kind == "helps"
    assert E.diagnose(outs(10, 7.0), P).kind == "helps" and E.diagnose(outs(10, 7.1), P).kind == "wide"                         # Schwelle 70 %
    assert E.diagnose(outs(1.0, 0.5), P).kind == "helps" and E.diagnose(outs(10, 2, nofit=0.02), P).kind == "helps"             # ruhig erst unter 1 min, Überlast erst über 2 %


def test_diagnosis_text_for_every_kind_names_the_right_numbers():
    d = E.Diagnosis("quota", 10.0, 9.0, 0.9, 0.3, 0.0, 1.0, 20.0)
    q = E.diagnosis_text(d, P._replace(share_pct=60, cap_pct=110))
    assert q.startswith("Nur 60 % buchen") and "bleiben 9.0 von 10.0 min" in q and "Termininhaber 1.0 min, die Lkw ohne Termin 20.0 min" in q and "110" not in q
    assert "Mit Vorrang" not in E.diagnosis_text(E.Diagnosis("quota", 10.0, 9.0, 0.9, 0.3, 0.0, None, None), P._replace(share_pct=60))
    c = E.diagnosis_text(E.Diagnosis("calm", 0.4, 0.3, 0.75, 0.1, 0.0, None, None), P)
    assert c.startswith("Kaum Schlange") and "nur 0.4 min" in c and "Auslastung 68 %" in c and "0.1 min Verschiebung" in c
    o = E.diagnosis_text(E.Diagnosis("overload", 9.8, 0.5, 0.05, 35.0, 0.114, 0.4, 1.0), P)
    assert o.startswith("Die Fenster reichen nicht für alle: 11 % der Buchenden") and "im Mittel 0.5 min (frei: 9.8 min)" in o
    w = E.diagnosis_text(E.Diagnosis("wide", 9.8, 7.2, 0.73, 0.8, 0.0, 7.2, None), P)
    assert w.startswith("Die Fenster lassen die Spitze durch") and "noch 7.2 min im Mittel statt 9.8 min (0.8 min Verschiebung)" in w
    h = E.diagnosis_text(E.Diagnosis("helps", 9.8, 1.6, 0.16, 8.4, 0.0, 1.6, None), P)
    assert h.startswith("Das Terminsystem senkt die mittlere Wartezeit von 9.8 auf 1.6 min") and "8.4 min mittlerer Verschiebung" in h
    assert all("⚠" not in t and "✅" not in t for t in (q, c, o, w, h))


def test_diagnose_carries_the_numbers():
    d = E.diagnose(outs(10, 4, mean_u=25.0), P)
    assert (d.free_mean, d.shared_mean, d.ratio, d.shift, d.nofit_share, d.prio_booked, d.prio_unbooked) == (10.0, 4.0, 0.4, 0.0, 0.0, None, None)
    assert E.diagnose(outs(0.0, 0.0), P).ratio is None


def test_diagnose_on_real_days_matches_the_stories():
    for share, cap, fr, expected in ((100, 90, 650, "helps"), (60, 90, 650, "quota"), (100, 120, 650, "wide"), (100, 90, 350, "calm"), (100, 60, 650, "overload")):
        p = P._replace(share_pct=share, cap_pct=cap, trucks=fr)
        assert E.diagnose(E.run_rules(p, E.make_day(p, 3)), p).kind == expected, (share, cap, fr)


def test_statistics_helpers():
    assert E._mean_none([1.0, None, 3.0]) == 2.0 and E._mean_none([None]) is None and E._se([1.0]) == 0.0 and E._se([1.0, 3.0]) == pytest.approx(statistics.stdev([1.0, 3.0]) / 2 ** 0.5)
