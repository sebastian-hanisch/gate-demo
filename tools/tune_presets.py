"""Preset-Abstimmung per Sweep: trägt die Geschichte jedes Presets im MITTEL über viele Tage, und an dem einen Tag, den das Preset zeigt?

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py <modus>
  population   Grundgesamtheit (Seeds 0-199): Mittelwert-Kriterien aller Presets
  seeds        je Seed 200..699: welche Presets tragen an diesem Tag, Abstand zum Median der Kennzahlen; nennt die besten gemeinsamen Seeds

Grundsätze (aus den Hafen-Demos): den Seed nicht nach dem schönsten Einzelfall wählen, sondern nahe am MEDIAN; der Preset-Seed liegt außerhalb der Grundgesamtheit (Seeds ab 200);
alle Presets teilen sich EINE Tages-Nummer. Deterministisch, kein Löser: die Ergebnisse hängen nicht vom Rechner ab."""
import math
import statistics
import sys

sys.path.insert(0, ".")
import gate_constants as C
import gate_evaluation as E
import gate_stories as ST

NAMES = list(C.PRESETS)
POPULATION = 200
SEEDS = range(POPULATION, POPULATION + 500)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["lanes"], p["trucks"], p["service"], p["peak_pct"], p["cap_pct"], p["share_pct"], p["sigma"])


def cmd_population():
    for name in NAMES:
        rows = E.sample(params(name), POPULATION)
        print(f"\n### {name}")
        for ok, text in ST.criteria(name, rows):
            print(("  OK   " if ok else "  FAIL ") + text)
        print("  Kennzahlen:", {f"{k}/{f}": round(v, 2) for (k, f), v in ST.key_values(name, rows).items()})


def _value(row, key, field):
    return getattr(row.m[key], field)


def _median(table):
    return {(n, k, f): statistics.median(_value(table[n][s], k, f) for s in table[n]) for n, k, f in ST.TYPICAL}


def _score(table, med, seed):
    return sum(abs(math.log(_value(table[n][seed], k, f) + 0.5) - math.log(med[(n, k, f)] + 0.5)) for n, k, f in ST.TYPICAL)


def cmd_seeds():
    table = {n: {s: E.day_row(params(n), s) for s in SEEDS} for n in NAMES}
    med = _median(table)
    for name in NAMES:
        print(f"{name}: trägt an {sum(ST.holds(name, table[name][s]) for s in SEEDS)} von {len(SEEDS)} Tagen")
    allgood = sorted((s for s in SEEDS if all(ST.holds(n, table[n][s]) for n in NAMES)), key=lambda s: _score(table, med, s))
    print("\nalle fünf tragen an:", allgood[:12], f"({len(allgood)} von {len(SEEDS)})")
    for s in allgood[:6]:
        print(f"  seed {s:3d} | Abstand zum Median {_score(table, med, s):.2f} | " + ", ".join(
            f"{n}: {table[n][s].m[C.RULE_FREE].mean:.1f}/{table[n][s].m[C.RULE_SHARED].mean:.1f}" for n in NAMES))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "population"
    {"population": cmd_population, "seeds": cmd_seeds}.get(mode, lambda: sys.exit(__doc__))()
