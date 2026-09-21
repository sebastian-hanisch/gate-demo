"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute und "×" sind erlaubt, aber "–" (Gedankenstrich), "−" (Minuszeichen), "€", "σ", "Σ", "≥", "≤", Emoji usw. lassen fpdf2 abstürzen. Deshalb läuft jeder Text
durch pdf_text(); Regeln erscheinen mit ihren Kurznamen ohne Emoji."""

import time

import gate_constants as C
import gate_evaluation as E

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "Σ": "Summe", "δ": "Delta", "σ": "sigma", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR", "·": "-",
    "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "±": "+-", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "",
}
FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO


def pdf_text(text):
    """Text für die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def short_name(key):
    return C.RULE_SHORT[key]


def verdict_text(rows, label, key, reference, field, unit):
    """Ein Satz je Vergleich, wie im Kernabschnitt der App (ohne Emoji)."""
    v = E.verdict(rows, key, reference, field)
    d = E.distribution(rows, key, reference, field)
    if v.kind == "better":
        amount = f"{abs(v.pct):.0f} % weniger" if v.pct is not None else f"{abs(v.diff):.2f} min weniger"
        return f"{label}: im Mittel {amount} {unit} ({v.diff:+.2f} min je Tag, Standardfehler {v.se:.2f}); an {d.worse * 100:.0f} % der Tage ist es umgekehrt."
    if v.kind == "worse":
        amount = f"{v.pct:.0f} % mehr" if v.pct is not None else f"{v.diff:.2f} min mehr"
        return f"{label}: im Mittel {amount} {unit} ({v.diff:+.2f} min je Tag, Standardfehler {v.se:.2f}); an {d.better * 100:.0f} % der Tage ist es besser."
    return (f"{label}: kein klarer Unterschied, die Differenz ({v.diff:+.2f} min {unit}, gemittelt über die Tage) liegt innerhalb des Rauschens (Standardfehler {v.se:.2f}); "
            f"besser an {d.better * 100:.0f} %, schlechter an {d.worse * 100:.0f} % der Tage.")


def generate_gate_pdf(p, seed, outcomes, diag, sample=None, curve=None, compress=True):
    """Ergebnis der aktuellen Einstellung als PDF: Szenario, Zusammenfassung, Regelvergleich, optional Stichprobe/Urteil und Kapazitätskurve, Hinweise.

    `p`: E.Params; `outcomes`: die drei Outcomes (eines Tages); `diag`: E.Diagnosis; `sample`: Tupel von DayRow oder None; `curve`: E.Curve (Kapazitätskurve) oder None."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    by_key = {o.key: o for o in outcomes}
    gate_cap = p.lanes * C.SLOT_LEN / p.service

    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(70, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        """Beginnt einen Abschnitt auf einer neuen Seite, wenn er sonst über den Seitenumbruch liefe (keine halb abgeschnittenen Listen)."""
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    def note(text, size=8):
        pdf.set_font("Helvetica", "I", size)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    def cell(v, fmt):
        return "-" if v is None else format(v, fmt)

    pdf.set_font("Helvetica", "B", 16)
    line("Lkw-Gate: Was bringt ein Terminsystem?", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    heading("Szenario")
    pairs([("Gate", f"{p.lanes} Spuren, Bearbeitung im Mittel {p.service} min (Gate-Kapazität {gate_cap:.0f} Lkw je {C.SLOT_LEN} min)"),
           ("Lkw pro Tag", f"{p.trucks} (mittlere Auslastung {E.utilisation_of(p) * 100:.0f} %), davon {p.peak_pct} % in zwei Stoßzeiten"),
           ("Terminsystem", f"Fenster {C.SLOT_LEN} min, {E.cap_of(p)} Lkw je Fenster ({p.cap_pct} % der Gate-Kapazität), Buchungsquote {p.share_pct} %"),
           ("Verspätung", f"sigma {p.sigma} min"), ("Seed", str(seed))])
    pdf.ln(3)

    heading("Zusammenfassung")
    note(E.diagnosis_text(diag, p), 9)
    pairs([(short_name(o.key), f"{o.m.mean:.1f} min im Mittel, 95 %: {o.m.p95:.0f} min, {o.m.over_limit * 100:.0f} % über {C.WAIT_LIMIT:.0f} min") for o in outcomes])
    pdf.ln(3)

    heading("Regelvergleich (dieser Tag)")
    rows = []
    for o in outcomes:
        m = o.m
        rows.append([short_name(o.key), f"{m.mean:.1f}", f"{m.p95:.0f}", f"{m.over_limit * 100:.0f}", "-" if o.key == FR else f"{m.shift:.1f}", f"{m.booked_share * 100:.0f}",
                     cell(m.mean_booked, ".1f"), cell(m.mean_unbooked, ".1f")])
    table(["Regel", "Mittel (min)", "95 % (min)", "> 15 min (%)", "Verschiebung", "mit Termin (%)", "Wartezeit mit T.", "ohne T."], [24, 24, 22, 24, 26, 26, 28, 20], rows)
    note("Verschiebung: mittlerer Abstand zwischen gebuchtem und Wunschfenster in Minuten (nur Lkw mit Termin). Wartezeit mit T. / ohne T.: mittlere Wartezeit der Lkw mit beziehungsweise ohne Termin.")
    pdf.ln(3)

    if sample is not None:
        keep_together(100)
        heading("Stichprobe und Urteil")
        table(["Regel", "Mittel (min)", "95 % (min)", "Verschiebung (min)"], [44, 40, 40, 46],
              [[short_name(k), f"{E.mean_of(sample, k):.1f}", f"{E.mean_of(sample, k, 'p95'):.1f}", "-" if k == FR else f"{E.mean_of(sample, k, 'shift'):.1f}"] for k in C.RULE_KEYS])
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        for label, key, ref, field, unit in (("Terminsystem gegen Freie Anfahrt, mittlere Wartezeit", SH, FR, "mean", "Wartezeit"),
                                             ("Vorrang gegen Terminsystem, mittlere Wartezeit aller Lkw", PR, SH, "mean", "Wartezeit"),
                                             ("Vorrang gegen Terminsystem, Wartezeit der Termininhaber", PR, SH, "mean_booked", "Wartezeit")):
            if E.values(sample, key, field) and E.values(sample, ref, field):
                pdf.multi_cell(0, 5, pdf_text("- " + verdict_text(sample, label, key, ref, field, unit)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        note(f"Basis: {len(sample)} Tage (Seeds 0-{len(sample) - 1}, nicht der eingestellte Seed) mit den eingestellten Werten. Klar heißt: Unterschied größer als zwei Standardfehler der gepaarten Differenz.")
        pdf.ln(3)

    if curve is not None:
        keep_together(85)
        heading("Fensterkapazität: Wartezeit und Verschiebung")
        s = curve.series["termin"]
        table(["Fensterkapazität (%)", "Mittel (min)", "95 % (min)", "Verschiebung (min)", "ohne Fenster (%)"], [42, 32, 32, 42, 38],
              [[x, f"{s['mean'][j]:.1f}", f"{s['p95'][j]:.1f}", f"{s['shift'][j]:.1f}", f"{s['nofit_share'][j] * 100:.1f}"] for j, x in enumerate(curve.xs)])
        note(f"Terminsystem mit Ihren Einstellungen, Mittel über {curve.n_days} Tage (Seeds 0-{curve.n_days - 1}); freie Anfahrt zum Vergleich im Mittel {curve.series['frei']['mean'][0]:.1f} min.")
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Ein Betriebstag von 12 Stunden; Wunschzeiten teils in zwei Stoßzeiten; Bearbeitung am Gate lognormal (Streuung 0,6); Gate mit gleichen Spuren und einer gemeinsamen Schlange.",
        "Alle Lkw sind gleich; keine No-Shows, keine Ablehnung zu früher Lkw, keine Platzgrenze der Schlange, keine Spurtypen. Die Lkw buchen ohne Absprache in zufälliger Reihenfolge das nächste freie Fenster.",
        "Die Verschiebung ist kein Geldbetrag; Wartezeit und Verschiebung werden bewusst nicht zu einer Zahl vermischt.",
        "Alle Zahlen sind Größenordnungen aus einer Simulation mit zufälligen Tagen, keine Messung an echten Terminals; die Rechnung ist gegen die Theorie (Erlang C) geprüft.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
