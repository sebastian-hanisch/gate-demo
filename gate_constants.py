"""Konstanten der Gate-Demo.

Die Erzeugung des Tages (Wunschzeiten, Bearbeitungszeiten, Buchungsreihenfolge, Rauschen) und die Fensterbuchung sind die der Messreihe (hafen-planung/messreihe_gate), damit deren Zahlen
mit diesem Code reproduzierbar sind."""

# --- Fachliche Festwerte (keine Regler; im Text genannt) ---------------------------------------------
DAY_MINUTES = 720.0                  # Betriebstag: 12 Stunden
SLOT_LEN = 30                        # Fensterlänge in Minuten (10 bis 120 min sind bei gleicher relativer Kapazität kaum verschieden)
SERVICE_CV = 0.6                     # Streuung der Bearbeitungszeit (lognormal)
PEAK_POSITIONS = (0.25, 0.70)        # Stoßzeiten als Anteil des Tages
PEAK_SD = 45.0                       # Streuung um eine Stoßzeit in Minuten
WAIT_LIMIT = 15.0                    # Wartezeit, ab der ein Lkw als "lange wartend" zählt, und Grenze für die Spurenzahl (95. Perzentil)

# --- Regler ------------------------------------------------------------------------------------------
LANES_RANGE, LANES_DEFAULT = (2, 10), 4
TRUCKS_RANGE, TRUCKS_DEFAULT, TRUCKS_STEP = (200, 1200), 650, 50
SERVICE_RANGE, SERVICE_DEFAULT = (2, 5), 3
PEAK_PCT_RANGE, PEAK_PCT_DEFAULT, PEAK_PCT_STEP = (0, 75), 50, 25
CAP_PCT_RANGE, CAP_PCT_DEFAULT, CAP_PCT_STEP = (60, 150), 90, 10
SHARE_PCT_RANGE, SHARE_PCT_DEFAULT, SHARE_PCT_STEP = (20, 100), 100, 10
SIGMA_RANGE, SIGMA_DEFAULT, SIGMA_STEP = (0, 90), 10, 10
SEED_RANGE, SEED_DEFAULT = (0, 9999), 289

# --- Regeln ------------------------------------------------------------------------------------------
RULE_FREE, RULE_SHARED, RULE_PRIO = "frei", "termin", "vorrang"
RULE_KEYS = (RULE_FREE, RULE_SHARED, RULE_PRIO)
RULE_LABELS = {RULE_FREE: "🚚 Freie Anfahrt", RULE_SHARED: "📅 Terminsystem", RULE_PRIO: "⭐ Terminsystem mit Vorrang"}
RULE_SHORT = {RULE_FREE: "Frei", RULE_SHARED: "Termin", RULE_PRIO: "Vorrang"}
BASELINE = RULE_FREE
RIGHT_VIEW_KEYS = (RULE_SHARED, RULE_PRIO)
VIEW_DEFAULT = RULE_SHARED

RULE_DESCRIPTIONS = {
    RULE_FREE: "Jeder Lkw kommt, wann er will: zur Wunschzeit plus Verspätung. Das ist der Ist-Zustand ohne Terminsystem und die Referenz für alle Vergleiche.",
    RULE_SHARED: "Zeitfenster mit begrenzter Kapazität: die Lkw buchen in zufälliger Reihenfolge das dem Wunsch nächste Fenster mit Platz. Wer kein Fenster findet oder nicht bucht, kommt wie ohne Termin. "
                 "Alle stehen in derselben Schlange.",
    RULE_PRIO: "Wie das Terminsystem, aber wird eine Spur frei, bedient sie zuerst den am längsten wartenden Lkw mit Termin, sonst den ohne (nicht unterbrechend). Der Vorrang verlagert die Wartezeit "
               "auf die Lkw ohne Termin; das Mittel über alle bleibt gleich.",
}

# --- Auswertung ---------------------------------------------------------------------------------------
SAMPLE_DAYS = 100                    # Tage (Seeds 0 .. n-1, bewusst NICHT der eingestellte Seed) für Urteil und Verteilung
CURVE_DAYS = 50                      # Tage je Punkt der Kurven
VERDICT_Z = 2.0                      # klar ab mehr als VERDICT_Z Standardfehlern der gepaarten Differenz
CAP_CURVE_POINTS = tuple(range(60, 151, 10))
SHARE_CURVE_POINTS = tuple(range(20, 101, 10))

# --- Diagnose (Schwellen der bedingten Meldung) -------------------------------------------------------
CALM_FREE_MEAN = 1.0                 # freie Anfahrt wartet im Mittel unter einer Minute: nichts zu glätten
OVERLOAD_NOFIT = 0.02                # mehr als 2 % der Buchenden finden kein Fenster: die Fenster reichen nicht
LITTLE_EFFECT = 0.7                  # Terminsystem senkt die Wartezeit nicht unter 70 % der freien: kaum Nutzen
FULL_SHARE = 90                      # Buchungsquote ab der die Nichtbucher die Spitze nicht mehr halten

# --- Darstellung --------------------------------------------------------------------------------------
RULE_COLORS = {RULE_FREE: "#8a94a3", RULE_SHARED: "#2a6fb0", RULE_PRIO: "#2e7d4f"}
BOOKED_COLOR, UNBOOKED_COLOR = "#2a6fb0", "#c77700"
CAPACITY_COLOR = "#c0392b"
MARKER_LINE_COLOR = "#808895"
OUTCOME_COLORS = {"better": "#2e7d4f", "equal": "#8a94a3", "worse": "#c0392b"}
CHART_HEIGHT = 380
DAY_FIGURE_HEIGHT = 400

# --- Presets ------------------------------------------------------------------------------------------
PRESETS = {
    "Ruhiger Tag": dict(lanes=4, trucks=350, service=3, peak_pct=50, cap_pct=90, share_pct=100, sigma=10, seed=289),
    "Stoßzeit": dict(lanes=4, trucks=650, service=3, peak_pct=50, cap_pct=90, share_pct=100, sigma=10, seed=289),
    "Halbe Quote": dict(lanes=4, trucks=650, service=3, peak_pct=50, cap_pct=90, share_pct=60, sigma=10, seed=289),
    "Fenster zu weit": dict(lanes=4, trucks=650, service=3, peak_pct=50, cap_pct=120, share_pct=100, sigma=10, seed=289),
    "Voller Tag": dict(lanes=4, trucks=850, service=3, peak_pct=50, cap_pct=100, share_pct=100, sigma=10, seed=289),
}
