import re

import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
from gate_pdf_export import generate_gate_pdf, pdf_text, short_name, verdict_text

FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO
P = E.Params(4, 650, 3, 50, 90, 100, 10)


def _make(p=P, seed=289, sample=None, curve=None, compress=False):
    outs = E.run_rules(p, E.make_day(p, seed))
    diag = E.diagnose(outs, p)
    return generate_gate_pdf(p, seed, outs, diag, sample=sample, curve=curve, compress=compress), outs, diag


def _texts(data):
    """Alle Textstücke des (unkomprimierten) PDFs als Liste, Latin-1 gelesen, PDF-Escapes aufgelöst."""
    raw = re.findall(rb"\((.*?)\)\s*Tj", data)
    return [t.decode("latin-1").replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\") for t in raw]


def mk(mean, mean_b=None, mean_u=None):
    return Q.Metrics(n=100, mean=mean, p95=mean * 3, over_limit=0.0, max_wait=mean * 4, util=0.5, shift=0.0, booked_share=1.0, nofit_share=0.0, mean_booked=mean_b, mean_unbooked=mean_u,
                     p95_booked=None, p95_unbooked=None)


def rows(fr, sh, n=20, spread=1):
    return tuple(E.DayRow(i, {FR: mk(fr + (i % 2) * spread), SH: mk(sh), PR: mk(sh)}) for i in range(n))


# ---------- Sonderzeichen: mit den GENAUEN Zeichen testen (fpdf2 stürzt bei "–" und "€" ab) ----------
EXPECTED = {"–": "-", "—": "-", "−": "-", "€": "EUR", "Σ": "Summe", "δ": "Delta", "σ": "sigma", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "„": '"', "“": '"', "’": "'", "·": "-",
            "±": "+-", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": ""}


@pytest.mark.parametrize("char,replacement", list(EXPECTED.items()))
def test_pdf_text_replaces_every_known_troublemaker_with_a_readable_equivalent(char, replacement):
    out = pdf_text(f"a{char}b")
    out.encode("latin-1")
    assert out == f"a{replacement}b"


def test_pdf_text_keeps_umlauts_and_times_sign_and_replaces_unknown():
    assert pdf_text("Füllgrad äöüß ÄÖÜ × 3") == "Füllgrad äöüß ÄÖÜ × 3" and pdf_text("日本語").encode("latin-1") == b"???" and "?" in pdf_text("🚛 Gate")


def test_short_names_have_no_emoji_and_survive_latin_1():
    assert [short_name(k) for k in C.RULE_KEYS] == ["Frei", "Termin", "Vorrang"]
    assert all(pdf_text(short_name(k)) == short_name(k) for k in C.RULE_KEYS)


# ---------- Sätze ----------
def test_verdict_text_covers_all_states_and_survives_latin_1():
    better, worse = rows(10, 2), rows(2, 10)
    unclear = tuple(E.DayRow(i, {FR: mk(5), SH: mk(5 + (1 if i % 2 else -1)), PR: mk(5)}) for i in range(20))
    for sample, expected in ((better, "im Mittel"), (worse, "im Mittel"), (unclear, "kein klarer Unterschied")):
        text = verdict_text(sample, "L", SH, FR, "mean", "Wartezeit")
        assert text.startswith("L:") and expected in text
        text.encode("latin-1")
    t = verdict_text(better, "L", SH, FR, "mean", "Wartezeit")
    assert "im Mittel 81 % weniger Wartezeit" in t and "(-8.50 min je Tag" in t and "an 0 % der Tage ist es umgekehrt" in t                      # (2 - 10,5) / 10,5 = -81 %: ohne Vorzeichen
    assert "im Mittel 300 % mehr Wartezeit (+7.50 min je Tag" in verdict_text(worse, "L", SH, FR, "mean", "Wartezeit") and "an 0 % der Tage ist es besser" in verdict_text(worse, "L", SH, FR, "mean", "Wartezeit")
    assert "gemittelt über die Tage" in verdict_text(unclear, "L", SH, FR, "mean", "Wartezeit")


def test_verdict_text_without_a_percentage_when_the_reference_needs_nothing(monkeypatch):
    monkeypatch.setattr(E, "verdict", lambda r, k, ref, field="mean": E.Verdict("better", -2.0, 0.5, None, 20, field))
    t = verdict_text(rows(1, 1), "L", SH, FR, "mean", "Wartezeit")
    assert "im Mittel 2.00 min weniger Wartezeit (-2.00 min je Tag" in t and "%" not in t.split("(")[0]
    monkeypatch.setattr(E, "verdict", lambda r, k, ref, field="mean": E.Verdict("worse", 2.0, 0.5, None, 20, field))
    assert "im Mittel 2.00 min mehr Wartezeit (+2.00 min je Tag" in verdict_text(rows(1, 1), "L", SH, FR, "mean", "Wartezeit")


# ---------- Inhalt ----------
def test_pdf_is_a_valid_document_with_all_sections_without_sample():
    data, outs, diag = _make()
    assert data.startswith(b"%PDF") and data.endswith(b"%%EOF\n") and len(data) > 2000
    text = _texts(data)
    for label in ("Lkw-Gate: Was bringt ein Terminsystem?", "Szenario", "Zusammenfassung", "Regelvergleich (dieser Tag)", "Hinweise zum Modell"):
        assert label in text, label
    assert "Stichprobe und Urteil" not in text and "Fensterkapazität: Wartezeit und Verschiebung" not in text


def test_pdf_scenario_block_pairs_every_label_with_its_own_value():
    data, outs, diag = _make()
    text = _texts(data)

    def value(label):
        return text[text.index(label) + 1]
    assert value("Gate") == "4 Spuren, Bearbeitung im Mittel 3 min (Gate-Kapazität 40 Lkw je 30 min)"
    assert value("Lkw pro Tag") == "650 (mittlere Auslastung 68 %), davon 50 % in zwei Stoßzeiten"
    assert value("Terminsystem") == "Fenster 30 min, 36 Lkw je Fenster (90 % der Gate-Kapazität), Buchungsquote 100 %"
    assert value("Verspätung") == "sigma 10 min" and value("Seed") == "289"


def test_pdf_summary_quotes_the_diagnosis_and_each_rule_with_its_own_numbers():
    data, outs, diag = _make()
    text = _texts(data)
    start = text.index("Zusammenfassung")
    for o in outs:
        line = text[text.index(short_name(o.key), start) + 1]
        assert line == f"{o.m.mean:.1f} min im Mittel, 95 %: {o.m.p95:.0f} min, {o.m.over_limit * 100:.0f} % über 15 min"
    assert any(E.diagnosis_text(diag, P)[:50] in t for t in text)


def test_pdf_rule_table_has_one_row_per_rule_with_the_right_cells():
    data, outs, diag = _make(P._replace(share_pct=60))
    text = _texts(data)
    start = text.index("Regelvergleich (dieser Tag)") + 9                      # acht Kopfzellen
    assert text[start - 8: start] == ["Regel", "Mittel (min)", "95 % (min)", "> 15 min (%)", "Verschiebung", "mit Termin (%)", "Wartezeit mit T.", "ohne T."]
    for i, o in enumerate(outs):
        m = o.m
        row = text[start + 8 * i: start + 8 * i + 8]
        assert row == [short_name(o.key), f"{m.mean:.1f}", f"{m.p95:.0f}", f"{m.over_limit * 100:.0f}", "-" if o.key == FR else f"{m.shift:.1f}", f"{m.booked_share * 100:.0f}",
                       "-" if m.mean_booked is None else f"{m.mean_booked:.1f}", "-" if m.mean_unbooked is None else f"{m.mean_unbooked:.1f}"]
    assert row[7] != "-" and text[start + 4] == "-" and text[start + 7] != "-"                # Vorrang-Zeile hat beide Klassen, die freie keine Verschiebung


def test_pdf_with_sample_and_curve_adds_the_sections_and_quotes_the_verdicts():
    sample = E.sample(P, 8)
    curve = E.cap_curve(P, 3)
    data, *_ = _make(sample=sample, curve=curve)
    text = _texts(data)
    assert "Stichprobe und Urteil" in text and "Fensterkapazität: Wartezeit und Verschiebung" in text
    joined = " ".join(text)
    assert verdict_text(sample, "Terminsystem gegen Freie Anfahrt, mittlere Wartezeit", SH, FR, "mean", "Wartezeit")[:60] in joined
    assert "Vorrang gegen Terminsystem, mittlere Wartezeit aller Lkw" in joined and "Vorrang gegen Terminsystem, Wartezeit der Termininhaber" in joined
    start = text.index("Stichprobe und Urteil") + 5                                # vier Kopfzellen
    for i, k in enumerate(C.RULE_KEYS):
        assert text[start + 4 * i: start + 4 * i + 4] == [short_name(k), f"{E.mean_of(sample, k):.1f}", f"{E.mean_of(sample, k, 'p95'):.1f}", "-" if k == FR else f"{E.mean_of(sample, k, 'shift'):.1f}"]
    s = curve.series["termin"]
    cstart = text.index("Fensterkapazität: Wartezeit und Verschiebung") + 6
    assert text[cstart: cstart + 5] == [str(curve.xs[0]), f"{s['mean'][0]:.1f}", f"{s['p95'][0]:.1f}", f"{s['shift'][0]:.1f}", f"{s['nofit_share'][0] * 100:.1f}"]
    assert f"Mittel über {curve.n_days} Tage" in joined


def test_pdf_skips_the_booked_verdict_when_nobody_or_everybody_is_in_a_class():
    sample = E.sample(P, 3)                                                       # Quote 100 %: Termininhaber haben Werte, Nichtbucher nicht
    data, *_ = _make(sample=sample)
    assert "Wartezeit der Termininhaber" in " ".join(_texts(data))
    p = P._replace(share_pct=20)
    data, *_ = _make(p, sample=E.sample(p, 3))
    assert data.startswith(b"%PDF")


# ---------- Ränder ----------
@pytest.mark.parametrize("lanes,trucks,share", [(2, 200, 20), (10, 1200, 100), (4, 350, 60), (2, 1200, 100)])
def test_pdf_is_generated_for_the_edge_cases_compressed_and_uncompressed(lanes, trucks, share):
    p = P._replace(lanes=lanes, trucks=trucks, share_pct=share)
    for compress in (True, False):
        data, *_ = _make(p, sample=E.sample(p, 2), curve=E.cap_curve(p, 2), compress=compress)
        assert data.startswith(b"%PDF") and len(data) > 1500
