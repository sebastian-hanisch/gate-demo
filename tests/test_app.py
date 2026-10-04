"""AppTest: Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, Kennzahlen im 2 x 2-Raster, die bedingte Meldung in allen Zuständen, Stichprobe, Kurven und Urteil, gesparte
Spuren, Regelvergleich, PDF, Texte."""

import pathlib

import pytest
from streamlit.proto.Metric_pb2 import Metric as MetricProto
from streamlit.testing.v1 import AppTest

import gate_constants as C
import gate_evaluation as E
from gate_presets import SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = (
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Hof- und Yard-Management optimieren](https://sebastianhanisch.net/yard-management-optimierung.html)."
)
FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO

# Am Preset-Tag (Seed 289), Regel Terminsystem: (mittlere Wartezeit, Delta, 95. Perzentil, Delta) und Art der Meldung
EXPECTED = {"Ruhiger Tag": ("0.2 min", "-0.2 min", "1 min", "-1 min", "calm"), "Stoßzeit": ("1.6 min", "-8.3 min", "6 min", "-19 min", "helps"),
            "Niedrige Quote": ("9.3 min", "-0.6 min", "24 min", "-1 min", "quota"), "Fenster zu weit": ("7.2 min", "-2.6 min", "20 min", "-5 min", "wide"),
            "Voller Tag": ("4.7 min", "-25.2 min", "11 min", "-55 min", "helps")}


@pytest.fixture(autouse=True)
def clean_cache():
    """st.cache_data ist prozessweit: Tests, die Funktionen ersetzen, dürfen keine zwischengespeicherten Ergebnisse anderer Tests sehen."""
    import streamlit as st
    st.cache_data.clear()
    yield


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        (at.number_input if key.endswith("_input") else at.slider)(key=key).set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value, m.delta) for m in at.metric[:4]]


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception
    return at


def verdict_texts(at):
    """Die drei Urteilssätze des Kernabschnitts (in jeder der drei Meldungsarten)."""
    return [x.value for group in (at.success, at.warning, at.info) for x in group if "**Terminsystem gegen Freie Anfahrt" in x.value or "**Vorrang gegen Terminsystem" in x.value]


def message(at, needle):
    for group in (at.success, at.warning, at.info):
        for x in group:
            if needle in x.value:
                return x
    return None


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer():
    at = fresh()
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]                # genau EIN Header
    assert len(at.title) == 1 and "Gate" in at.title[0].value
    assert any(v.value.startswith("## 🎯") for v in at.markdown)
    assert [s.value for s in at.subheader] == ["📐 Was kostet das Terminsystem, und wie viele Spuren spart es?"]
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – Regeln im Vergleich", "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5 and all(len(n) <= 16 for n in presets)
    assert [s.label for s in at.sidebar.slider] == ["Gate-Spuren", "Lkw pro Tag", "Bearbeitung je Lkw (min)", "Anteil in Stoßzeiten (%)", "Fensterkapazität (% der Gate-Kapazität)", "Buchungsquote (%)",
                                                    "Verspätung σ (min)"]
    assert [n.label for n in at.sidebar.number_input] == ["Seed"] and any(b.label == "🎲 Neuer Tag" for b in at.sidebar.button)


def test_main_metrics_are_2x2_with_signed_deltas_against_free_arrival():
    at = fresh()
    assert [m[0] for m in main_metrics(at)] == ["Mittlere Wartezeit", "95. Perzentil", "Anteil über 15 min", "Verschiebung gegen Wunsch"]
    assert [m[1] for m in main_metrics(at)] == ["1.6 min", "6 min", "0 %", "8.4 min"]
    assert [m[2] for m in main_metrics(at)] == ["-8.3 min", "-19 min", "-38 Punkte", ""]
    assert [m.proto.color for m in at.metric[:3]] == [MetricProto.GREEN] * 3            # weniger Wartezeit = besser = grün ("inverse")
    assert all(len(m[0]) <= 26 for m in main_metrics(at))


def test_caption_states_gate_capacity_window_capacity_and_utilisation():
    at = fresh()
    cap = [c.value for c in at.caption if "Fensterkapazität" in c.value and "Auslastung" in c.value][0]
    assert "4 Spuren schaffen 40 Lkw je 30 min; Fensterkapazität 36 Lkw je Fenster; 650 Lkw am Tag, mittlere Auslastung 68 %, Buchungsquote 100 %" in cap


def test_core_section_metrics_and_the_saved_lanes():
    at = fresh()
    assert [(m.label, m.value) for m in at.metric[4:7]] == [("Gate-Kapazität je Fenster", "40 Lkw"), ("Fensterkapazität", "36 Lkw"), ("Mittlere Auslastung", "68 %")]
    assert [(m.label, m.value) for m in at.metric[7:10]] == [("Spuren frei", "5"), ("Spuren mit Termin", "3"), ("Gesparte Spuren", "2")]
    at = set_and_run(at, trucks_slider=200)
    assert [(m.label, m.value) for m in at.metric[7:10]] == [("Spuren frei", "2"), ("Spuren mit Termin", "2"), ("Gesparte Spuren", "0")]
    at = fresh(ln="10", tr="1200", sv="5")
    assert [(m.label, m.value) for m in at.metric[7:10]] == [("Spuren frei", "> 10"), ("Spuren mit Termin", "9"), ("Gesparte Spuren", "–")]


def test_the_caption_bases_name_the_sample_and_the_curves():
    at = fresh()
    caps = [c.value for c in at.caption]
    assert any("Basis: 100 Tage (Seeds 0-99, nicht Ihr Seed). Im Mittel je Tag 9.5 min Wartezeit bei freier Anfahrt, 1.4 min mit Terminsystem (Verschiebung 9.4 min) und 1.4 min mit Vorrang" in c for c in caps)
    assert any("Basis: 50 Tage (Seeds 0-49, nicht Ihr Seed) mit Ihren Einstellungen (Buchungsquote 100 %)" in c for c in caps)
    assert any("Basis: 50 Tage (Seeds 0-49); Fensterkapazität 90 % wie eingestellt" in c for c in caps)
    assert any("Basis: 50 Tage (Seeds 0-49); die Fensterkapazität folgt der jeweiligen Spurenzahl. Die Achse endet bei 60 min" in c for c in caps)


def test_charts_are_present_with_unique_keys():
    at = fresh()
    charts = at.get("plotly_chart")
    keys = [c.key for c in charts]
    assert len(charts) == 12                                                              # 2 Tage, 2 Kapazität, 2 Verteilungen, Quote, Spuren, 3 Regel-Tabs, Vergleich
    assert len(set(keys)) == 12 and all(keys)


# ---------------------------------------------------------------------------------------------------
# Presets, Permalink
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds_and_shows_its_story(name):
    at = fresh()
    click(at, name)
    p = C.PRESETS[name]
    assert at.slider(key="trucks_slider").value == p["trucks"] and at.slider(key="cap_slider").value == p["cap_pct"] and at.slider(key="share_slider").value == p["share_pct"]
    assert at.slider(key="lanes_slider").value == p["lanes"] and at.number_input(key="seed_input").value == p["seed"]
    for state_key, spec in SETTING_SPECS.items():
        if spec.lo is not None:
            value = at.session_state[state_key]
            assert spec.lo <= value <= spec.hi and (spec.step in (None, 1) or (value - spec.lo) % spec.step == 0)
    mean, dmean, p95, dp95, kind = EXPECTED[name]
    assert [main_metrics(at)[0][1:], main_metrics(at)[1][1:]] == [(mean, dmean), (p95, dp95)]
    needles = {"calm": "Kaum Schlange", "helps": "Das Terminsystem senkt die mittlere Wartezeit", "quota": "Nur 60 % buchen", "wide": "Die Fenster lassen die Spitze durch"}
    assert message(at, needles[kind]) is not None, name


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(tr="620", cp="94", sh="66", vw="junk", ln="abc", sg="14")
    assert at.slider(key="trucks_slider").value == 600 and at.slider(key="cap_slider").value == 90 and at.slider(key="share_slider").value == 70 and at.slider(key="sigma_slider").value == 10
    assert at.radio(key="view_radio").value == C.VIEW_DEFAULT and at.slider(key="lanes_slider").value == C.LANES_DEFAULT


def test_permalink_roundtrip_reflects_settings():
    at = fresh(ln="6", tr="400", sv="4", pk="25", cp="110", sh="80", sg="30", seed="11", vw="vorrang")
    values = {k: at.session_state[k] for k in SETTING_SPECS}
    assert values == {"lanes_slider": 6, "trucks_slider": 400, "service_slider": 4, "peak_slider": 25, "cap_slider": 110, "share_slider": 80, "sigma_slider": 30, "seed_input": 11, "view_radio": "vorrang"}
    for key, spec in SETTING_SPECS.items():
        got = at.query_params[spec.url_param]
        got = got[0] if isinstance(got, list) else got
        assert got == spec.encoder(values[key]), key


def test_new_day_button_changes_only_the_seed():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    click(at, "🎲 Neuer Tag")
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before and 0 <= at.session_state["seed_input"] <= 9999


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung
# ---------------------------------------------------------------------------------------------------
def test_message_overload_when_the_windows_do_not_suffice():
    at = set_and_run(fresh(), cap_slider=60)
    msg = message(at, "Die Fenster reichen nicht für alle")
    assert msg is not None and "11 % der Buchenden finden kein Fenster" in msg.value and "Mit Terminsystem warten die Lkw im Mittel 0.5 min (frei: 9.8 min)" in msg.value
    assert len([w for w in at.warning if "Die Fenster reichen nicht" in w.value]) == 1


def test_message_quota_names_both_classes_under_priority():
    at = set_and_run(fresh(), share_slider=60)
    msg = message(at, "Nur 60 % buchen")
    assert "mit Terminsystem bleiben 9.3 von 9.8 min Wartezeit" in msg.value and "Mit Vorrang warten die Termininhaber 0.9 min, die Lkw ohne Termin 20.8 min" in msg.value
    assert "der Vorrang verlagert die Wartezeit, das Mittel über alle bleibt" in msg.value and msg in list(at.warning)


def test_message_calm_says_nothing_to_smooth():
    at = set_and_run(fresh(), lanes_slider=10)
    msg = message(at, "Kaum Schlange")
    assert msg in list(at.info) and "Auslastung 27 %" in msg.value and "kostet 0.0 min Verschiebung" in msg.value


def test_message_wide_and_helps_are_warning_and_success():
    at = click(fresh(), "Fenster zu weit")
    assert message(at, "Die Fenster lassen die Spitze durch") in list(at.warning) and "noch 7.2 min im Mittel statt 9.8 min" in message(at, "Die Fenster lassen").value
    at = click(fresh(), "Stoßzeit")
    assert message(at, "Das Terminsystem senkt die mittlere Wartezeit") in list(at.success) and "von 9.8 auf 1.6 min, bei 8.4 min mittlerer Verschiebung" in message(at, "Das Terminsystem senkt").value


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [("lanes_slider", 2), ("lanes_slider", 10), ("trucks_slider", 200), ("trucks_slider", 1200), ("service_slider", 2), ("service_slider", 5), ("peak_slider", 0),
                                       ("peak_slider", 75), ("cap_slider", 60), ("cap_slider", 150), ("share_slider", 20), ("share_slider", 100), ("sigma_slider", 0), ("sigma_slider", 90)])
def test_every_slider_works_at_its_minimum_and_maximum(key, value):
    at = set_and_run(fresh(), **{key: value})
    assert at.session_state[key] == value and len(at.metric) >= 7


def test_extreme_combinations_run_without_exception():
    at = fresh(ln="2", tr="1200", sv="5", pk="75", cp="60", sh="20", sg="90")
    assert not at.exception and message(at, "Die Fenster reichen nicht für alle") is not None
    at = fresh(ln="10", tr="200", sv="2", pk="0", cp="150", sh="100", sg="0")
    assert not at.exception and message(at, "Kaum Schlange") is not None


# ---------------------------------------------------------------------------------------------------
# Stichprobe, Kurven, Urteil
# ---------------------------------------------------------------------------------------------------
def test_three_verdict_sentences_with_the_right_labels():
    at = fresh()
    texts = verdict_texts(at)
    assert len(texts) == 3
    assert any("Terminsystem gegen Freie Anfahrt, mittlere Wartezeit" in t and "85 % weniger" in t for t in texts)
    assert sum("Kein klarer Unterschied bei **Vorrang gegen Terminsystem" in t for t in texts) == 2               # Quote 100 %: Vorrang = Terminsystem (Erhaltungssatz und Gleichheit)


def test_verdict_hint_when_a_class_has_no_trucks():
    at = set_and_run(fresh(), share_slider=20)
    assert message(at, "Wartezeit der Termininhaber") is not None                                                   # bei Quote 20 % gibt es Termininhaber: kein Hinweis
    at = fresh()
    assert not any("gibt es keine Lkw dieser Gruppe" in x.value for x in at.info)


def _fake_verdict(monkeypatch, kind, pct):
    monkeypatch.setattr(E, "verdict", lambda rows, key, ref, field="mean": E.Verdict(kind, -2.0 if kind == "better" else 2.0, 0.5, pct, 20, field))


@pytest.mark.parametrize("kind,pct,expected", [
    ("better", -40.0, "im Mittel **40 % weniger** Wartezeit (-2.00 min je Tag, Standardfehler 0.50)."),
    ("better", None, "im Mittel **2.00 min weniger** Wartezeit (-2.00 min je Tag, Standardfehler 0.50)."),
    ("worse", 25.0, "im Mittel **25 % mehr** Wartezeit (+2.00 min je Tag, Standardfehler 0.50)."),
    ("worse", None, "im Mittel **2.00 min mehr** Wartezeit (+2.00 min je Tag, Standardfehler 0.50)."),
])
def test_verdict_sentences_in_the_four_variants(monkeypatch, kind, pct, expected):
    _fake_verdict(monkeypatch, kind, pct)
    at = fresh()
    texts = verdict_texts(at)
    assert len(texts) == 3 and all(expected in t for t in texts)
    assert all(t.count("(") == t.count(")") for t in texts)


def test_verdict_unclear(monkeypatch):
    _fake_verdict(monkeypatch, "unclear", 1.0)
    at = fresh()
    us = verdict_texts(at)
    assert len(us) == 3 and all(u.startswith("Kein klarer Unterschied") for u in us) and all("Rauschens" in u and "gemittelt über die Tage" in u for u in us)


def test_the_sample_does_not_depend_on_the_seed():
    at = fresh()
    before = [c.value for c in at.caption if "Im Mittel je Tag" in c.value]
    at = set_and_run(at, seed_input=5)
    assert [c.value for c in at.caption if "Im Mittel je Tag" in c.value] == before and len(before) == 1


# ---------------------------------------------------------------------------------------------------
# Blick in den Tag
# ---------------------------------------------------------------------------------------------------
def test_view_radio_switches_the_rule_shown_in_the_metrics_and_the_permalink():
    at = set_and_run(fresh(), share_slider=60)
    assert at.radio(key="view_radio").value == SH and list(at.radio(key="view_radio").options) == [C.RULE_LABELS[k] for k in C.RIGHT_VIEW_KEYS]
    assert main_metrics(at)[0][1:] == ("9.3 min", "-0.6 min")
    at = at.radio(key="view_radio").set_value(PR).run()
    assert not at.exception and main_metrics(at)[0][1:] == ("9.1 min", "-0.8 min")                                 # Vorrang senkt das Mittel nicht (9,3 gegen 9,1), nur die Klassenwerte
    assert main_metrics(at)[1][1:] == ("48 min", "+23 min")                                                          # aber das 95. Perzentil steigt: die Lkw ohne Termin tragen den langen Schwanz
    assert at.query_params["vw"] in ("vorrang", ["vorrang"])


def test_day_caption_explains_the_chart():
    at = fresh()
    assert any("Oben die Ankünfte je 30 min (blau mit Termin, orange ohne) gegen die Gate-Kapazität" in c.value and "gepunktet die 15-Minuten-Grenze" in c.value for c in at.caption)


# ---------------------------------------------------------------------------------------------------
# Regelvergleich, PDF, Texte
# ---------------------------------------------------------------------------------------------------
def test_comparison_table_has_a_row_per_rule_with_the_right_cells():
    at = set_and_run(fresh(), share_slider=60)
    df = at.dataframe[0].value
    assert list(df["Regel"]) == [C.RULE_LABELS[k] for k in C.RULE_KEYS]
    assert list(df["Mittlere Wartezeit (min)"]) == [9.8, 9.3, 9.1] and list(df["95. Perzentil (min)"]) == [25, 24, 48] and list(df["mit Termin (%)"]) == [0, 59, 59]
    assert list(df["Wartezeit mit Termin (min)"])[2] == 0.9 and list(df["Wartezeit ohne Termin (min)"])[2] == 20.8
    assert df["Verschiebung (min)"].isna().tolist() == [True, False, False] and list(df["Delta Wartezeit (min)"]) == [0.0, -0.6, -0.8]


def test_each_rule_tab_shows_its_metrics_with_deltas_against_free_arrival():
    at = fresh()
    tab = at.metric[10:]
    assert [m.label for m in tab] == ["Mittlere Wartezeit", "95. Perzentil", "Anteil über 15 min", "Verschiebung gegen Wunsch"] * 3
    assert [m.value for m in tab[:4]] == ["9.8 min", "25 min", "38 %", "–"] and [m.delta for m in tab[:4]] == ["", "", "", ""]              # Referenz ohne Delta
    assert [m.value for m in tab[4:8]] == ["1.6 min", "6 min", "0 %", "8.4 min"] and [m.delta for m in tab[4:7]] == ["-8.3 min", "-19 min", "-38 Punkte"]


def test_pdf_download_button_is_offered():
    at = fresh()
    buttons = at.get("download_button")
    assert len(buttons) == 1 and buttons[0].proto.label == "📄 Ergebnis als PDF herunterladen"


def test_texts_state_the_rules_the_assumptions_and_the_limits():
    at = fresh()
    text = "\n".join(m.value for m in at.expander[1].markdown)
    for needle in ("Freie Anfahrt", "Terminsystem", "Vorrang", "Verschiebung", "Fensterkapazität", "Buchungsquote", "Erhaltungssatz", "keine No-Shows", "Größenordnungen aus einer Simulation",
                   "Erlang C", "keine Platzgrenze"):
        assert needle in text, needle
    math = "\n".join(m.value for m in at.expander[2].markdown)
    for needle in ("Erlang-C-Formel", "\\lfloor q \\cdot c \\cdot 30 / \\bar s \\rfloor", "Erhaltungssatz", "2\\,\\mathrm{SE}", "Verschiebung"):
        assert needle in math, needle
