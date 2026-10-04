"""Abnahmekriterien der Presets (Plan, Abschnitt 7): Welche Geschichte erzählt jedes Beispielszenario, und woran erkennt man, dass sie trägt?

Einzige Quelle für `tools/tune_presets.py` (Abstimmung) und `tests/test_preset_stories.py` (Abnahme). Jedes Kriterium ist eine Aussage über ein Tupel von `DayRow`s (gate_evaluation): über viele Tage
die Aussage im MITTEL (`criteria`), über den EINEN Tag des Presets dieselbe Aussage an diesem Tag (`holds`; ein Tag hat 350 bis 850 Lkw, die Mittel sind stabil). So wird dieselbe Geschichte an der
Grundgesamtheit UND am gewählten Tag geprüft: das Preset soll typisch sein, nicht der schönste Einzelfall. Deterministisch, ohne Löser und Zeitgrenze: die Kriterien sind CI-robust."""

import gate_constants as C
import gate_evaluation as E

FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO

# Kennzahlen, an denen 'typisch' gemessen wird: (Preset, Regel, Feld)
TYPICAL = (("Ruhiger Tag", FR, "mean"), ("Stoßzeit", FR, "mean"), ("Stoßzeit", SH, "mean"), ("Niedrige Quote", SH, "mean"), ("Niedrige Quote", PR, "mean_unbooked"),
           ("Fenster zu weit", SH, "mean"), ("Voller Tag", FR, "mean"), ("Voller Tag", SH, "mean"))


def criteria(name, rows):
    """Kriterien über ein Tupel von Tagen (Mittel). Rückgabe: Liste (erfüllt, Text)."""
    fr, sh, pr = E.mean_of(rows, FR), E.mean_of(rows, SH), E.mean_of(rows, PR)
    shift = E.mean_of(rows, SH, "shift")
    if name == "Ruhiger Tag":
        return [(fr <= 1.0, f"frei: mittlere Wartezeit <= 1 min: {fr:.2f}"),
                (abs(sh - fr) <= 1.0, f"Terminsystem nicht mehr als 1 min anders: {sh:.2f} gegen {fr:.2f}"),
                (shift <= 1.0, f"Verschiebung <= 1 min: {shift:.1f}")]
    if name == "Stoßzeit":
        return [(fr >= 8.0, f"frei >= 8 min: {fr:.1f}"),
                (sh <= 0.25 * fr, f"Terminsystem <= 25 % davon: {sh:.1f}"),
                (shift <= 15.0, f"Verschiebung <= 15 min: {shift:.1f}")]
    if name == "Niedrige Quote":
        booked, unbooked = E.mean_of(rows, PR, "mean_booked"), E.mean_of(rows, PR, "mean_unbooked")
        fmt = lambda v: "keine Lkw" if v is None else f"{v:.1f}"          # noqa: E731  (gibt es keine Lkw dieser Gruppe, ist das Kriterium nicht erfüllt)
        return [(sh >= 0.8 * fr, f"Terminsystem >= 80 % der freien Wartezeit: {sh:.1f} gegen {fr:.1f}"),
                (booked is not None and booked <= 2.0, f"Vorrang: Termininhaber <= 2 min: {fmt(booked)}"),
                (unbooked is not None and unbooked >= 15.0, f"Vorrang: ohne Termin >= 15 min: {fmt(unbooked)}"),
                (abs(pr - sh) <= 0.05 * sh, f"Vorrang-Mittel = Termin-Mittel +-5 %: {pr:.2f} gegen {sh:.2f}")]
    if name == "Fenster zu weit":
        return [(sh >= 0.6 * fr, f"Terminsystem >= 60 % der freien Wartezeit: {sh:.1f} gegen {fr:.1f}"),
                (shift <= 3.0, f"Verschiebung <= 3 min: {shift:.1f}")]
    if name == "Voller Tag":
        return [(fr >= 20.0, f"frei >= 20 min: {fr:.1f}"),
                (sh <= 0.25 * fr, f"Terminsystem <= 25 % davon: {sh:.1f}"),
                (shift >= 12.0, f"Verschiebung >= 12 min: {shift:.1f}")]
    raise KeyError(name)


def holds(name, row):
    """Gilt die Geschichte an dem EINEN Tag (`DayRow`), den das Preset zeigt?"""
    return all(ok for ok, _ in criteria(name, (row,)))


def key_values(name, rows):
    """Die Kennzahlen dieses Presets aus TYPICAL als {(Regel, Feld): Mittel}."""
    return {(k, f): E.mean_of(rows, k, f) for n, k, f in TYPICAL if n == name}
