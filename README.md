# Lkw-Gate: Was bringt ein Terminsystem? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-gate-demo.streamlit.app/)**

Interaktive Fall-Demo zur **Warteschlange am Lkw-Gate eines Containerterminals**: In den Stoßzeiten kommen mehr Lkw, als die Gate-Spuren schaffen, und die Schlange wächst. Ein **Terminsystem** vergibt Zeitfenster mit
begrenzter Kapazität und glättet die Spitzen. Die Demo beantwortet: **Was spart das an Wartezeit, was kostet es die Spediteure an Verschiebung, wie viele Spuren spart es, und wer trägt die Wartezeit, wenn nicht
alle buchen?**

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning", Zusatz zur Hafen-Linie (Lkw-Terminvergabe; setzt auf der `truck-appointment-demo` auf, die die Termine an
Hallentoren deterministisch plant, hier die stochastische Warteschlange davor).

## Warum dieses Problem

Naheliegend wäre „Terminsystem senkt die Wartezeit“. Gemessen stimmt das **nur unter Bedingungen**, und der erste Versuch lag im falschen Bereich: bei 25 bis 40 % Auslastung wartet praktisch kein Lkw, ein Terminsystem sieht dort
nutzlos aus. Im belasteten Bereich (die Stoßzeiten liegen über der Gate-Kapazität) sinkt die mittlere Wartezeit von 9,9 auf 1,5 min, **aber** das Terminsystem **verlagert** die Wartezeit auf die Verschiebung der Buchenden
(9,6 min im Mittel), es wirkt nur, wenn (fast) alle buchen, und ein **Vorrang für Termininhaber** senkt deren Wartezeit, **ohne das Mittel zu senken**: die Lkw ohne Termin warten dann länger.

## Modell

Ein Betriebstag von 12 Stunden; *N* Lkw mit **Wunschzeit** (ein Anteil in zwei Stoßzeiten bei 25 % und 70 % des Tages, Streuung 45 min, der Rest gleichverteilt); Bearbeitung am Gate lognormal (Mittel *s*, Streuung 0,6);
*c* gleiche Spuren, **eine gemeinsame Schlange**. **Freie Anfahrt:** Ankunft = Wunschzeit + Verspätung (σ). **Terminsystem:** Fenster von 30 min mit höchstens *K* Lkw (*K* = Fensterkapazität in % dessen, was das Gate in 30 min
schafft); ein Anteil der Lkw (Buchungsquote) bucht in zufälliger Reihenfolge das dem Wunsch nächste Fenster mit Platz **innerhalb des Betriebstags**; wer keins findet oder nicht bucht, kommt wie ohne Termin.
**Vorrang:** wird eine Spur frei, bedient sie zuerst den am längsten wartenden Lkw mit Termin. Kennzahlen: mittlere Wartezeit, 95. Perzentil, Anteil über 15 min und die **Verschiebung** (mittlerer Abstand zwischen gebuchtem und
Wunschfenster, nur Buchende). Wartezeit und Verschiebung werden **nicht** zu einer Zahl vermischt. Alle Regeln laufen auf denselben Zufallszahlen je Tag. Formal im Expander „📐 Mathematische Formulierung“.

## Methodik – drei Regeln

Alle Regeln arbeiten denselben Tag ab; Referenz aller Vergleiche ist **Freie Anfahrt**.

- **🚚 Freie Anfahrt:** jeder kommt zur Wunschzeit plus Verspätung.
- **📅 Terminsystem:** Fenster mit Kapazität, gemeinsame Schlange für alle.
- **⭐ Terminsystem mit Vorrang:** wie 📅, aber Termininhaber werden vor den Lkw ohne Termin bedient (nicht unterbrechend).

Die **Stichprobe** (100 Tage mit den Seeds 0 bis 99, nicht der eingestellte Seed) und die **drei Kurven** (Fensterkapazität, Buchungsquote, Spurenzahl; je 50 Tage) rechnen in wenigen Sekunden und brauchen keinen Knopf (ein
Tag mit drei Regeln kostet 1,5 bis 3 ms; der größte Fall komplett unter 2 s).

## Befunde (gemessen, keine Behauptungen)

4 Spuren, 650 Lkw (68 % mittlere Auslastung), 3 min Bearbeitung, halb der Lkw in Stoßzeiten, σ 10 min; Zahlen aus `tools/PRESET_SWEEP.md` und der Vorab-Messreihe (`hafen-planung/messreihe_gate/ERGEBNIS.md`).

| Frage | Befund |
|---|---|
| **Stimmt die Rechnung?** | Die Warteschlange stimmt mit **Erlang C** überein (Poisson-Ankünfte, exponentielle Bearbeitung, 4 bis 6 Spuren): −0,4 bis −0,7 % (Test gegen die Theorie, dazu gegen eine unabhängige Ereignisliste). |
| **Was bringt das Terminsystem?** | Mittlere Wartezeit **9,91 → 1,46 min** (95. Perzentil 30,5 → 5,9), bei **9,6 min Verschiebung**. Bei 89 % Auslastung 30,2 → 5,0 min (Verschiebung 18,1 min). |
| **Wie eng müssen die Fenster sein?** | Knie bei **90 bis 100 % der Gate-Kapazität**: dort sinkt die Wartezeit am stärksten; darunter gewinnt man nur noch eine halbe Minute, die Verschiebung wächst um mehr als die Hälfte. Bei 120 % lassen die Fenster die Spitze durch (7,3 min). |
| **Was, wenn nicht alle buchen?** | Der Nutzen verschwindet mit sinkender Quote: mittlere Wartezeit bei Quote 100 / 80 / 60 % **1,5 / 6,5 / 9,3 min**. Die Lkw ohne Termin halten die Spitze. |
| **Was macht der Vorrang?** | Bei 60 % Quote warten Termininhaber **1,1 min**, Lkw ohne Termin **21,7 min**; das Mittel bleibt (9,26 gegen 9,27), das **95. Perzentil verdoppelt sich** (28,7 → 54,3 min): der Vorrang verlagert, er spart nicht. |
| **Wie viele Spuren spart das Terminsystem?** | Für „95 % warten höchstens 15 min“: 500 / 700 / 900 Lkw brauchen ohne Terminsystem 4 / 6 / 7 Spuren, mit Terminsystem 3 / 4 / 4 (bei 900 Lkw 36,8 min Verschiebung, 4 % ohne Fenster). |
| **Was, wenn die Lkw unpünktlich sind?** | Das Terminsystem hält bis σ ≈ 90 min (drei Fensterlängen); erst dort ist der Unterschied weg, weil die Verspätung die Spitzen auch ohne Termine verschmiert. |
| **Was ändert nichts?** | Fensterlänge 10 bis 120 min bei gleicher relativer Kapazität: Wartezeit 1,3 bis 1,4 min. Größere Streuung der Bearbeitung erhöht die Wartezeit mit Terminsystem (cv 1,5: 2,9 statt 1,4 min). Ohne Spitzen bringt das Terminsystem nichts. |
| **Presets** | Eine gemeinsame Tages-Nummer (Seed 289) für alle fünf; jede Kennzahl zwischen dem 10. und 90. Perzentil der Grundgesamtheit. Von 500 Seeds tragen 215 alle fünf Geschichten. |

## Ehrliche Grenzen

- Alle Lkw sind gleich: keine Spurtypen (Import, Export), keine Ausreißer bei der Dokumentenprüfung; **keine No-Shows** und keine Ablehnung zu früher Lkw.
- Die Schlange hat **keine Platzgrenze** (kein Rückstau auf die Straße); ein Tag startet und endet leer.
- Wunschzeiten, Stoßzeiten und Bearbeitungszeit sind **Annahmen** (Größenordnung, nicht an Echtdaten gemessen); die Lkw buchen ohne Absprache in zufälliger Reihenfolge.
- Die **Verschiebung ist kein Geldbetrag**; ihr Preis gegen eine Wartezeit ist Sache des Betreibers.
- Fensterlänge (30 min) und Streuung der Bearbeitungszeit (0,6) sind fest.
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an echten Terminals**.

## Design-Entscheidungen und Funde

**Erst den richtigen Messbereich finden.** Der erste Messlauf lag bei 25 bis 42 % Auslastung und zeigte „kein Effekt“. Erst im belasteten Bereich (Spitzen über der Gate-Kapazität) wird das Terminsystem sichtbar; der Regler „Lkw pro Tag“
nennt deshalb im Hilfetext die mittlere Auslastung, und das Preset „Ruhiger Tag“ zeigt den Gegenfall ausdrücklich.

**Zwei Modellfehler der ersten Fassung, in der Messreihe gefunden.** (1) Die Buchung erlaubte Fenster hinter Betriebsschluss; das ergab Verschiebungen von 500 min und scheinbar gesparte Spuren. Jetzt gibt es keine Fenster jenseits des
Tages, wer keins findet, kommt wie ohne Termin. (2) Die Verschiebung wurde gegen die Fenstermitte gemessen und enthielt so rund 7 min Rundungsanteil auch ohne jede Verschiebung; jetzt gegen das Wunschfenster.

**Der Vorrang verlagert, er spart nicht.** Der Erhaltungssatz (bei gleichen Bearbeitungszeiten bleibt das Mittel über alle Lkw gleich) ist als Test eingebaut. Dass das 95. Perzentil dabei **steigt**, hatte der Plan nicht genannt; die App
zeigt es bei der Regel Vorrang, und die Bedingte Meldung nennt beide Klassen.

**Gemeinsame Zufallszahlen und Buchungsreihenfolge.** Alle Regeln laufen auf denselben Zufallszahlen je Tag, die Buchungsreihenfolge ist zufällig und für alle Regeln gleich; sonst entstünde ein Scheinvorteil (Lehre aus der Reefer-Demo).

**Alles deterministisch.** Kein Löser, keine Zeitgrenze: Preset-Kriterien und Tests hängen nicht vom Rechner ab; jedes Kriterium hat einen Test mit künstlichen Werten, der einzeln an seiner Schwelle kippt, und die Schwellen im Test stehen fest
im Test (sie werden nicht aus dem Code gelesen).

## Tests

`python -m pytest tests/ -v` – 182 Tests, rund 3 Minuten. Zusammensetzung:

- **Theorie und Rechnung:** die Warteschlange gegen Erlang C (M/M/c) und die M/M/1-Formel, gegen eine **unabhängige Ereignisliste** auf 50 Zufallstagen, Vorrang = FIFO bitgleich bei nur einer Klasse, Vorrang bedient nie einen Lkw ohne Termin, solange einer mit Termin wartet,
  Erhaltungssatz, von Hand gerechnete Fälle.
- **Szenario:** der Tag bitgleich zur Messreihe, Fensterbuchung gegen eine naive Suche (nächstes freies Fenster, früher bei Gleichstand, nie über die Kapazität oder den Tag hinaus), Randwerte, Fehlermeldungen.
- **Auswertung:** Stichprobe, Kurven gegen Direktrechnungen, Urteil in drei Zuständen und genau an der Schwelle, Verteilung, Diagnose in allen fünf Arten samt Vorrang der Bedingungen, Sätze der Meldung.
- **Figuren:** Tag am Gate (Ankünfte gestapelt gegen Kapazität, Wartezeit, gemeinsame Achsen), Kurven, Verteilung, Vergleich; alle Achsen fest.
- **Presets:** Geschichte am gezeigten Tag, im Mittel von 200 Tagen, typisch je Kennzahl; alle Kriterien einzeln an ihren Schwellen mit künstlichen Werten; Reproduktion der Messreihe.
- **PDF:** Inhalt Zelle für Zelle, genaue Sonderzeichen (fpdf2 stürzt bei „–“, „€“, „σ“ und Emoji ab), Randfälle.
- **End-to-End (AppTest):** Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, die bedingte Meldung in allen Zuständen, Urteil in allen Zuständen, gesparte Spuren, Vergleichstabelle, PDF, Texte.

Zusätzlich wurde jedes Modul mit **eingebauten Fehlern** geprüft (`tools/mutation_check.py`, 93 Mutanten, mit Zeitgrenze je Mutant). Der erste Lauf fand 84; von den neun Überlebenden waren sechs echte Lücken der Tests (Randwerte 0 und 100 % Stoßzeiten, ein einzelner Lkw,
die Fehlermeldung bei nicht positiver Bearbeitungszeit, der Satz der Quotenmeldung, die Grenze von genau einer Minute im Preset „Ruhiger Tag“, die Beschriftung kleiner Anteile in der Verteilung); sie sind geschlossen und
erneut geprüft. Drei Überlebende sind **gleichwertig**: die Klarheitsschwelle und die Fünf-Prozent-Grenze des Vorrang-Kriteriums genau auf einer Gleitkommagrenze, und eine Schutzbedingung im PDF, die bei Buchungsquoten ab 20 %
nie auslöst (es gibt dann immer Lkw mit Termin).

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar, Hauptansicht, Blick in den Tag, Kernabschnitt, Regelvergleich, Texte |
| `gate_constants.py` | Regler-Grenzen, `PRESETS`, Regeln, Schwellen der Meldung, Farben, Festwerte |
| `gate_presets.py` | `SETTING_SPECS`, Permalink (Begrenzen und Einrasten), Presets, Seed-Knopf |
| `gate_scenario.py` | Tag (Wunschzeiten, Bearbeitung, Buchungsreihenfolge, Rauschen), Fensterbuchung, Ankünfte, Verschiebung |
| `gate_queue.py` | Warteschlange (FIFO und Vorrang), Kennzahlen, Verlauf über den Tag |
| `gate_evaluation.py` | Regeln auf einem Tag, Stichprobe, drei Kurven, gepaarte Differenz, Verteilung, Urteil, Diagnose |
| `gate_visualization.py` | Tag am Gate, Kurven, Verteilung, Vergleich (alle Achsen fest) |
| `gate_ui_panel.py` | Panel je Regel (Kennzahlen 2 × 2, Tag am Gate) |
| `gate_pdf_export.py` | PDF-Ergebnis (`fpdf2`, Kernschrift, Sonderzeichen-Bereinigung) |
| `gate_stories.py` | Abnahmekriterien der Presets (Quelle für Werkzeug und Tests) |
| `tools/tune_presets.py`, `tools/PRESET_SWEEP.md` | Preset-Abstimmung und ihr Bericht |
| `tools/mutation_check.py` | Fehler-Einbau-Test |
| `tests/` | siehe oben |

## Bewusst nicht umgesetzt (mögliche Erweiterungen)

- **No-Shows und Umbuchung**, Ablehnung zu früher Lkw (Torschluss vor dem Fenster).
- **Mehrere Spurtypen** (Import/Export, Leer/Voll) und **Rückstau auf die Straße** (Platzgrenze der Schlange).
- **Gestaffelte Preise für Fenster** (Anreiz statt Zwang).
- **Zeitverlauf mit Schrittregler**, **zwei Gates hintereinander** (Gate und Kran), Kopplung an die Kaiplatz- oder Stapelplanung.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py population|seeds`. Fehler-Einbau: `python tools/mutation_check.py`.

---
