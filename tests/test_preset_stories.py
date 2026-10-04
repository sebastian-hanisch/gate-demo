"""Abnahme der Presets an ECHTEN Daten: jede Geschichte trägt im Mittel über 200 Tage (Seeds 0-199) UND an dem einen Tag, den das Preset zeigt; der gezeigte Tag ist typisch, nicht der schönste
Einzelfall. Deterministisch (kein Löser, keine Zeitgrenze)."""

import pytest

import gate_constants as C
import gate_evaluation as E
import gate_stories as ST

POPULATION = 200
NAMES = list(C.PRESETS)
_POP = {}


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["lanes"], p["trucks"], p["service"], p["peak_pct"], p["cap_pct"], p["share_pct"], p["sigma"])


def population(name):
    if name not in _POP:
        _POP[name] = E.sample(params(name), POPULATION)
    return _POP[name]


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_on_average_over_the_population(name):
    for ok, text in ST.criteria(name, population(name)):
        assert ok, f"{name}: {text}"


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_at_the_day_the_preset_shows(name):
    assert ST.holds(name, E.day_row(params(name), C.PRESETS[name]["seed"])), name


def test_the_preset_seed_lies_outside_the_population():
    assert all(p["seed"] >= POPULATION for p in C.PRESETS.values())


@pytest.mark.parametrize("name", NAMES)
def test_the_shown_day_is_typical_for_every_key_measure(name):
    """Jede Kennzahl des gezeigten Tages liegt zwischen dem 10. und 90. Perzentil der Grundgesamtheit."""
    shown = E.day_row(params(name), C.PRESETS[name]["seed"])
    for n, key, field in ST.TYPICAL:
        if n != name:
            continue
        vals = sorted(E.values(population(name), key, field))
        lo, hi = vals[int(0.1 * len(vals))], vals[int(0.9 * len(vals)) - 1]
        assert lo <= getattr(shown.m[key], field) <= hi, (name, key, field, getattr(shown.m[key], field), (lo, hi))


def test_the_stories_differ_between_presets():
    assert not all(ok for ok, _ in ST.criteria("Stoßzeit", population("Ruhiger Tag")))
    assert not all(ok for ok, _ in ST.criteria("Stoßzeit", population("Niedrige Quote")))
    assert not all(ok for ok, _ in ST.criteria("Fenster zu weit", population("Stoßzeit")))
    assert not all(ok for ok, _ in ST.criteria("Niedrige Quote", population("Stoßzeit")))


def test_the_population_reproduces_the_messreihe():
    """sweep6.json (hafen-planung/messreihe_gate): Stoßzeit frei 9,91 / Terminsystem 1,46 / Verschiebung 9,6; Niedrige Quote Termininhaber 1,08, ohne Termin 21,69."""
    pop = population("Stoßzeit")
    assert E.mean_of(pop, C.RULE_FREE) == pytest.approx(9.91, abs=0.01) and E.mean_of(pop, C.RULE_SHARED) == pytest.approx(1.46, abs=0.01)
    assert E.mean_of(pop, C.RULE_FREE, "p95") == pytest.approx(30.5, abs=0.05) and E.mean_of(pop, C.RULE_SHARED, "shift") == pytest.approx(9.6, abs=0.05)
    half = population("Niedrige Quote")
    assert E.mean_of(half, C.RULE_SHARED) == pytest.approx(9.27, abs=0.01) and E.mean_of(half, C.RULE_PRIO, "mean_booked") == pytest.approx(1.08, abs=0.01)
    assert E.mean_of(half, C.RULE_PRIO, "mean_unbooked") == pytest.approx(21.69, abs=0.02)
    full = population("Voller Tag")
    assert E.mean_of(full, C.RULE_FREE) == pytest.approx(30.15, abs=0.02) and E.mean_of(full, C.RULE_SHARED) == pytest.approx(5.01, abs=0.01)
