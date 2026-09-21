import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
import gate_visualization as V

FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO
P = E.Params(4, 650, 3, 50, 90, 100, 10)
OUTS = E.run_rules(P, E.make_day(P, 289), record=True)


def axes_locked(fig):
    return bool(fig.layout.xaxis.fixedrange) and bool(fig.layout.yaxis.fixedrange)


def trace_named(fig, name):
    return next(t for t in fig.data if t.name == name)


# ---------------------------------------------------------------------------------------------------
# Tag am Gate
# ---------------------------------------------------------------------------------------------------
def test_clock_and_titles():
    assert V.clock(0) == "6:00" and V.clock(30) == "6:30" and V.clock(90) == "7:30" and V.clock(720) == "18:00" and V.clock(59.6) == "7:00"
    assert V.day_title("Regel", OUTS[0].m).startswith("<b>Regel</b><br><sub>Wartezeit im Mittel ") and f"{OUTS[0].m.mean:.1f}" in V.day_title("Regel", OUTS[0].m)


def test_day_figure_stacks_arrivals_with_and_without_appointment_and_shows_the_wait_line():
    tr = Q.Trace((5.0, 31.0, 40.0, 719.9), (1.0, 3.0, 5.0, 7.0), (True, True, False, False), 4, 3.0)
    fig = V.day_figure(tr, 40.0, "t")
    with_t, without_t = trace_named(fig, "Ankünfte mit Termin"), trace_named(fig, "Ankünfte ohne Termin")
    assert len(with_t.x) == 24 and with_t.y[0] == 1 and with_t.y[1] == 1 and sum(with_t.y) == 2 and without_t.y[1] == 1 and without_t.y[23] == 1 and sum(without_t.y) == 2
    assert fig.layout.barmode == "stack" and with_t.marker.color == C.BOOKED_COLOR and without_t.marker.color == C.UNBOOKED_COLOR
    wait = next(t for t in fig.data if getattr(t, "mode", None) == "lines+markers")
    assert wait.y[0] == 1.0 and wait.y[1] == 4.0 and wait.y[23] == 7.0 and wait.y[5] is None and wait.connectgaps is False
    assert abs(with_t.x[0] - 6.25) < 1e-9 and abs(with_t.x[23] - 17.75) < 1e-9
    assert with_t.customdata[0] == "6:00-6:30" and with_t.customdata[23] == "17:30-18:00"


def test_day_figure_draws_the_gate_capacity_and_the_wait_limit_and_labels_the_capacity_in_the_legend():
    fig = V.day_figure(OUTS[0].trace, 40.0, "t")
    lines = [s for s in fig.layout.shapes if s.type == "line"]
    assert sorted(s.y0 for s in lines) == [C.WAIT_LIMIT, 40.0] and {s.line.dash for s in lines} == {"dash", "dot"}
    assert any(t.name == "Gate-Kapazität 40 Lkw je 30 min" for t in fig.data) and axes_locked(fig)
    assert list(fig.layout.xaxis2.tickvals)[:3] == [6, 8, 10] and fig.layout.xaxis2.ticktext[0] == "6:00" and fig.layout.height == C.DAY_FIGURE_HEIGHT


def test_shared_day_ranges_cover_both_days_with_headroom_and_make_the_axes_equal():
    a, b = OUTS[0].trace, OUTS[1].trace
    arr, wait = V.shared_day_ranges([a, b], 40.0)
    peak = max(max(bb + uu for bb, uu in zip(*Q.windows(t)[:2])) for t in (a, b))
    worst = max(w for t in (a, b) for w in Q.windows(t)[2] if w is not None)
    assert arr == pytest.approx(max(peak, 40.0) * 1.1) and wait == pytest.approx(max(worst, C.WAIT_LIMIT) * 1.1)
    assert peak > 40.0 and worst > C.WAIT_LIMIT                                        # freie Anfahrt liegt über Kapazität und Grenze: sie bestimmt die Achsen
    fa, fb = (V.day_figure(t, 40.0, "x", (arr, wait)) for t in (a, b))
    assert tuple(fa.layout.yaxis.range) == tuple(fb.layout.yaxis.range) == (0, arr) and tuple(fa.layout.yaxis2.range) == tuple(fb.layout.yaxis2.range) == (0, wait)
    quiet = Q.Trace((10.0,), (0.0,), (False,), 4, 3.0)
    assert V.shared_day_ranges([quiet], 40.0) == pytest.approx((44.0, C.WAIT_LIMIT * 1.1))            # Kapazität und 15-Minuten-Grenze setzen die Mindesthöhe
    assert V.day_figure(quiet, 40.0, "x").layout.yaxis.range is None                                   # ohne Vorgabe skaliert das Diagramm selbst


def test_day_figure_from_a_real_day_counts_every_truck():
    for o in OUTS:
        fig = V.day_figure(o.trace, 40.0, "x")
        assert sum(trace_named(fig, "Ankünfte mit Termin").y) + sum(trace_named(fig, "Ankünfte ohne Termin").y) == 650
    assert sum(trace_named(V.day_figure(OUTS[0].trace, 40.0, "x"), "Ankünfte mit Termin").y) == 0          # freie Anfahrt: niemand hat einen Termin


# ---------------------------------------------------------------------------------------------------
# Kurven
# ---------------------------------------------------------------------------------------------------
def test_cap_curve_figures():
    cv = E.cap_curve(P, 3)
    wait, shift = V.cap_curve_figures(cv, 90)
    assert [t.name for t in wait.data] == ["Freie Anfahrt (Mittel)", "Terminsystem (Mittel)", "Terminsystem (95 %)"] and axes_locked(wait) and axes_locked(shift)
    assert list(wait.data[1].x) == list(cv.xs) and list(wait.data[1].y) == list(cv.series["termin"]["mean"]) and list(wait.data[2].y) == list(cv.series["termin"]["p95"])
    assert list(wait.data[0].y) == list(cv.series["frei"]["mean"]) and wait.data[0].line.dash == "dash"
    assert list(shift.data[0].y) == list(cv.series["termin"]["shift"]) and "ohne Fenster" in shift.data[0].text[0]
    assert len(wait.layout.shapes) == 1 and len(shift.layout.shapes) == 1 and len(V.cap_curve_figures(cv, 95)[0].layout.shapes) == 0        # nur ein Punkt der Kurve wird markiert


def test_share_curve_figure_has_a_line_per_class_and_gaps_where_a_class_is_empty():
    cv = E.share_curve(P, 3)
    fig = V.share_curve_figure(cv, 60)
    assert [t.name for t in fig.data] == ["Freie Anfahrt", "Terminsystem (alle)", "Vorrang: mit Termin", "Vorrang: ohne Termin"] and axes_locked(fig)
    assert list(fig.data[3].y)[-1] is None and fig.data[3].connectgaps is False and list(fig.data[2].y) == list(cv.series["vorrang"]["mean_booked"])
    assert [t.line.color for t in fig.data] == [C.RULE_COLORS[FR], C.RULE_COLORS[SH], C.RULE_COLORS[PR], C.UNBOOKED_COLOR]
    assert len(fig.layout.shapes) == 1 and len(V.share_curve_figure(cv, 65).layout.shapes) == 0


def test_lanes_curve_figure_has_the_limit_line_and_a_fixed_axis():
    cv = E.lanes_curve(P, 3)
    fig = V.lanes_curve_figure(cv, 4)
    assert [t.name for t in fig.data] == ["Freie Anfahrt", "Terminsystem"] and list(fig.data[0].x) == list(cv.xs) and list(fig.data[1].y) == list(cv.series["termin"]["p95"])
    assert tuple(fig.layout.yaxis.range) == (0, V.LANES_Y_MAX) and axes_locked(fig)
    lines = [s for s in fig.layout.shapes if s.type == "line" and s.y0 == C.WAIT_LIMIT]
    assert len(lines) == 1 and len([s for s in fig.layout.shapes if s.type == "line"]) == 2                              # Grenze und eingestellte Spurenzahl
    assert "95 % warten höchstens" in fig.data[0].hovertemplate and "%%" not in fig.data[0].hovertemplate


def test_hover_templates_have_no_doubled_percent_signs():
    cv = E.cap_curve(P, 2)
    for fig in V.cap_curve_figures(cv, 90):
        assert all("%%" not in (t.hovertemplate or "") for t in fig.data)
    assert all("%%" not in (t.hovertemplate or "") for t in V.share_curve_figure(E.share_curve(P, 2), 60).data)


# ---------------------------------------------------------------------------------------------------
# Verteilung und Vergleich
# ---------------------------------------------------------------------------------------------------
def test_distribution_figure_stacks_three_shares_per_row_and_names_the_reference():
    rows = E.sample(P, 6)
    dists = [E.distribution(rows, k, FR) for k in (SH, PR)]
    fig = V.distribution_figure(dists, ["Termin", "Vorrang"], "frei", "Wartezeit")
    assert [t.name for t in fig.data] == ["weniger Wartezeit als frei", "gleich", "mehr Wartezeit als frei"] and list(fig.data[0].y) == ["Termin", "Vorrang"]
    assert [t.marker.color for t in fig.data] == [C.OUTCOME_COLORS[k] for k in ("better", "equal", "worse")]
    for i in range(2):
        assert sum(t.x[i] for t in fig.data) == pytest.approx(100)
    assert fig.layout.barmode == "stack" and axes_locked(fig)
    for t in fig.data:
        assert all((lab == "") == (v < 6) for lab, v in zip(t.text, t.x))                      # kleine Anteile bleiben unbeschriftet, alle drei Balkenarten
    assert any(v < 6 for t in fig.data for v in t.x) and any(v >= 6 for t in fig.data for v in t.x)
    edge = V.distribution_figure([E.Distribution("k", "mean", 10, 0.05, 0.9, 0.05, 1.0, 1.0)], ["x"], "frei", "Wartezeit")
    assert [t.text[0] for t in edge.data] == ["", "90 %", ""]


def test_wait_bar_figure_shows_all_booked_and_unbooked_and_leaves_undefined_bars_empty():
    fig = V.wait_bar_figure(OUTS)
    assert [t.name for t in fig.data] == ["alle Lkw", "mit Termin", "ohne Termin"] and list(fig.data[0].x) == ["Frei", "Termin", "Vorrang"]
    assert list(fig.data[0].y) == [o.m.mean for o in OUTS] and list(fig.data[1].y) == [None, OUTS[1].m.mean_booked, OUTS[2].m.mean_booked] and list(fig.data[2].y)[1:] == [None, None]
    assert list(fig.data[2].y)[0] == OUTS[0].m.mean and fig.layout.yaxis.range[0] == 0 and fig.layout.yaxis.range[1] > max(o.m.mean for o in OUTS) and axes_locked(fig)
    assert list(fig.data[0].marker.color) == [C.RULE_COLORS[k] for k in C.RULE_KEYS]


def test_wait_bar_figure_with_a_partial_booking_share():
    p = P._replace(share_pct=60)
    outs = E.run_rules(p, E.make_day(p, 289))
    fig = V.wait_bar_figure(outs)
    assert all(v is not None for v in fig.data[1].y[1:]) and all(v is not None for v in fig.data[2].y) and fig.layout.yaxis.range[1] > outs[2].m.mean_unbooked
