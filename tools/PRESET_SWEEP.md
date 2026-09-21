# Preset-Abstimmung (AP 5)

Werkzeug: `tools/tune_presets.py` (Modi `population`, `seeds`); Kriterien in `gate_stories.py`, Abnahme in `tests/test_preset_stories.py` (echte Daten) und `tests/test_stories.py` (künstliche Werte an den
Schwellen). Deterministisch, kein Löser: die Ergebnisse hängen nicht vom Rechner ab.

Messbasis: 4 Spuren, Bearbeitung 3 min, halb der Lkw in zwei Stoßzeiten, Verspätung σ 10 min, Fenster 30 min; Tage mit den Seeds 0 bis 199 (Grundgesamtheit) und 200 bis 699 (Suche nach dem Preset-Seed). Die Zahlen
reproduzieren die Vorab-Messreihe (`hafen-planung/messreihe_gate/sweep6.json`) auf zwei Stellen (Test `test_the_population_reproduces_the_messreihe`).

## Grundgesamtheit (200 Tage je Preset, mittlere Wartezeit in min, in Klammern 95. Perzentil und Anteil über 15 min)

| Preset | Spuren, Lkw (Auslastung), Fenster, Quote | Freie Anfahrt | Terminsystem | Verschiebung | Vorrang (alle; 95. Perzentil) | Vorrang: mit Termin / ohne Termin |
|---|---|---|---|---|---|---|
| Ruhiger Tag | 4, 350 (36 %), 90 %, 100 % | 0,31 (2,2; 0 %) | 0,26 (1,9; 0 %) | 0,1 | 0,26 (1,9) | 0,26 / – |
| Stoßzeit | 4, 650 (68 %), 90 %, 100 % | 9,91 (30,5; 30 %) | 1,46 (5,9; 0 %) | 9,6 | 1,46 (5,9) | 1,46 / – |
| Halbe Quote | 4, 650 (68 %), 90 %, 60 % | 9,91 (30,5; 30 %) | 9,27 (28,7; 28 %) | 0,3 | 9,26 (**54,3**) | 1,08 / 21,69 |
| Fenster zu weit | 4, 650 (68 %), 120 %, 100 % | 9,91 (30,5; 30 %) | 7,26 (22,1; 19 %) | 1,7 | 7,26 (22,1) | 7,26 / – |
| Voller Tag | 4, 850 (89 %), 100 %, 100 % | 30,15 (69,7; 63 %) | 5,01 (12,8; 4 %) | 18,1 | 5,01 (12,8) | 5,01 / – |

Urteil (gepaarte Differenz je Tag, klar ab zwei Standardfehlern), Terminsystem gegen Freie Anfahrt bei der mittleren Wartezeit: Stoßzeit −8,46 ± 0,16, Voller Tag −25,15 ± 0,22, Fenster zu weit −2,65 ± 0,10, Halbe Quote
−0,64 ± 0,06, Ruhiger Tag −0,05 ± 0,01 (statistisch klar, praktisch ohne Bedeutung). Vorrang gegen Terminsystem: das Mittel über alle Lkw ist in allen fünf Presets **nicht klar verschieden** (Halbe Quote −0,008 min); das
**95. Perzentil** steigt bei Halbe Quote **klar** um 25,6 min (54,3 gegen 28,7).

## Befunde und Abweichungen vom Plan

- **Der Vorrang verdoppelt das 95. Perzentil (Halbe Quote), das der Plan nicht genannt hatte.** Er senkt die Wartezeit der Termininhaber auf 1,1 min, aber die Lkw ohne Termin (40 % der Lkw) tragen jetzt den langen Schwanz: 21,7 min im Mittel.
  Der Anteil über 15 min sinkt dabei (an Seed 289 von 38 auf 20 %), weil weniger Lkw lange warten, die übrigen aber viel länger. Der Erhaltungssatz gilt für das Mittel, nicht für Perzentile. Die App zeigt beides (Kennzahl 95. Perzentil bei der Regel Vorrang).
- **Ruhiger Tag:** Das Terminsystem senkt die Wartezeit statistisch klar (−0,05 min), aber bedeutungslos klein; die Verschiebung ist 0,1 min. Das Kriterium lautet deshalb „nicht mehr als 1 min anders“, nicht „nicht klar besser“.
- **Fenster zu weit (120 %):** Die Fenster lassen die Spitze durch: 7,26 gegen 9,91 min, kaum Verschiebung (1,7 min). Bei 90 % sind es 1,46 min.
- **Voller Tag:** Ohne Termine wartet im Mittel jeder Lkw 30 min (63 % länger als 15 min); mit Terminen bleibt es bei 5,0 min, aber die mittlere Verschiebung steigt auf 18 min.
- **Halbe Quote (60 %):** Nur 0,64 min Ersparnis in der gemeinsamen Schlange; die Nichtbucher halten die Spitze.

## Gewählt

- Eine gemeinsame Tages-Nummer für alle Presets: **Seed 289** (jede Kennzahl aus `TYPICAL` zwischen dem 10. und 90. Perzentil der 200 Grundgesamtheits-Tage; Test `test_the_shown_day_is_typical_for_every_key_measure`).
  Alle fünf Geschichten tragen an diesem Tag, und der Seed liegt außerhalb der Stichprobe (Seeds ab 200). Von 500 Seeds (200 bis 699) tragen 215 alle fünf; Seed 289 liegt mit 0,28 (Summe der Logarithmen) am nächsten am Median der
  Kennzahlen, danach 307 (0,33) und 509 (0,43).
- An Seed 289 (mittlere Wartezeit frei / Terminsystem, Verschiebung): Ruhiger Tag 0,3 / 0,2; Stoßzeit 9,8 / 1,6 (8,4 min); Halbe Quote 9,8 / 9,3 (Vorrang: 0,9 mit Termin, 20,8 ohne); Fenster zu weit 9,8 / 7,2 (0,8 min);
  Voller Tag 29,9 / 4,7 (17,4 min). Ein Tag hat 350 bis 850 Lkw, die Mittel sind stabil: die Kriterien gelten am gezeigten Tag mit denselben Schwellen wie im Mittel.
