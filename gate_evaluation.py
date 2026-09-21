"""Auswertung: ein Tag mit den drei Regeln, Stichprobe über viele Tage, Kapazitäts-, Quoten- und Spurenkurve, gepaarte Differenz, Verteilung, Urteil und Diagnose.

Reine Rechnung ohne Streamlit. Kosten sind die Wartezeit am Gate und die Verschiebung der Buchenden (weniger ist besser, nicht zu einer Zahl vermischt); alle Vergleiche sind gepaart
(dieselben Tage, gemeinsame Zufallszahlen); Unterschied = Regel minus Referenz "Freie Anfahrt", negativ = besser."""

import math
import statistics
from dataclasses import dataclass
from typing import NamedTuple

import gate_constants as C
import gate_queue as Q
import gate_scenario as S


class Params(NamedTuple):
    """Alle Einstellungen, die einen Tag bestimmen (ohne Seed)."""
    lanes: int
    trucks: int
    service: int
    peak_pct: int
    cap_pct: int
    share_pct: int
    sigma: int


def make_day(p, seed):
    return S.make_day(seed, p.trucks, p.peak_pct, float(p.service))


def cap_of(p):
    return S.window_capacity(p.lanes, p.service, p.cap_pct)


def utilisation_of(p):
    """Mittlere Auslastung der Spuren über den Tag (erwartet): Lkw mal Bearbeitungszeit durch Spuren mal Tag."""
    return p.trucks * p.service / (p.lanes * C.DAY_MINUTES)


# ---------------------------------------------------------------------------------------------------
# Ein Tag, alle Regeln
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    key: str
    label: str
    m: Q.Metrics
    trace: object            # Q.Trace oder None (nur wenn aufgezeichnet)


def _rule_free(p, day, trace):
    arrive = S.free_arrivals(day, p.sigma)
    booked = [False] * day.n
    waits = Q.waits_fifo(arrive, day.service, p.lanes)
    m = Q.metrics(waits, day.service, booked, p.lanes)
    return m, Q.Trace(tuple(arrive), tuple(waits), tuple(booked), p.lanes, float(p.service)) if trace else None


def run_rules(p, day, record=False):
    """Die drei Regeln (Reihenfolge C.RULE_KEYS) auf demselben Tag."""
    out = []
    m, tr = _rule_free(p, day, record)
    out.append(Outcome(C.RULE_FREE, C.RULE_LABELS[C.RULE_FREE], m, tr))
    slot, nofit = S.book_slots(day, cap_of(p), p.share_pct)
    arrive = S.appointment_arrivals(day, p.sigma, slot)
    booked = [s is not None for s in slot]
    shift = S.shift_minutes(day, slot)
    for key, waits in ((C.RULE_SHARED, Q.waits_fifo(arrive, day.service, p.lanes)), (C.RULE_PRIO, Q.waits_priority(arrive, day.service, booked, p.lanes))):
        m = Q.metrics(waits, day.service, booked, p.lanes, shift, nofit)
        out.append(Outcome(key, C.RULE_LABELS[key], m, Q.Trace(tuple(arrive), tuple(waits), tuple(booked), p.lanes, float(p.service)) if record else None))
    return out


def outcome_of(outcomes, key):
    return next(o for o in outcomes if o.key == key)


# ---------------------------------------------------------------------------------------------------
# Stichprobe
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DayRow:
    seed: int
    m: dict                  # Regel -> Q.Metrics


def day_row(p, seed):
    return DayRow(seed, {o.key: o.m for o in run_rules(p, make_day(p, seed))})


def sample(p, n=C.SAMPLE_DAYS):
    """n Tage (Seeds 0 .. n-1, unabhängig vom eingestellten Seed) mit allen Regeln."""
    return tuple(day_row(p, seed) for seed in range(n))


def values(rows, key, field="mean"):
    """Werte eines Feldes je Tag; Tage, an denen es nicht definiert ist (None), fehlen."""
    return [v for v in (getattr(r.m[key], field) for r in rows) if v is not None]


def mean_of(rows, key, field="mean"):
    v = values(rows, key, field)
    return statistics.fmean(v) if v else None


def paired(rows, key, reference, field="mean"):
    """Gepaarte Differenz key - reference je Tag (nur Tage, an denen beide definiert sind; negativ = besser)."""
    out = []
    for r in rows:
        a, b = getattr(r.m[key], field), getattr(r.m[reference], field)
        if a is not None and b is not None:
            out.append(a - b)
    return out


def _se(d):
    return statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0


@dataclass(frozen=True)
class Distribution:
    key: str
    field: str
    n: int
    better: float
    equal: float
    worse: float
    mean_gain: float         # eingesparte Minuten je Tag (positiv = besser als die Referenz)
    median_gain: float


def distribution(rows, key, reference, field="mean"):
    d = paired(rows, key, reference, field)
    n = len(d)
    better, worse = sum(1 for x in d if x < -1e-9), sum(1 for x in d if x > 1e-9)
    return Distribution(key, field, n, better / n, (n - better - worse) / n, worse / n, -statistics.fmean(d), -statistics.median(d))


@dataclass(frozen=True)
class Verdict:
    kind: str                # "better" (weniger) | "worse" | "unclear"
    diff: float              # Regel minus Referenz je Tag (negativ = besser)
    se: float
    pct: object              # Unterschied in % der Referenz; None, wenn die Referenz im Mittel 0 ist
    n: int
    field: str


def verdict(rows, key, reference, field="mean"):
    """Bewertung gegen die Referenz. 'Klar' heißt: Unterschied > VERDICT_Z Standardfehler der gepaarten Differenz; sonst 'unclear'."""
    d = paired(rows, key, reference, field)
    diff, se = statistics.fmean(d), _se(d)
    ref = statistics.fmean([getattr(r.m[reference], field) for r in rows if getattr(r.m[reference], field) is not None and getattr(r.m[key], field) is not None])
    if se == 0:
        kind = "unclear" if diff == 0 else ("better" if diff < 0 else "worse")
    else:
        kind = "unclear" if abs(diff) <= C.VERDICT_Z * se else ("better" if diff < 0 else "worse")
    return Verdict(kind, diff, se, 100.0 * diff / ref if ref else None, len(d), field)


# ---------------------------------------------------------------------------------------------------
# Kurven
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Curve:
    xs: tuple
    series: dict             # Name -> {Feld: (Wert je x, None wo nicht definiert)}
    n_days: int


def _mean_none(vals):
    v = [x for x in vals if x is not None]
    return statistics.fmean(v) if v else None


def _fields(rows_m, names):
    return {f: _mean_none([getattr(m, f) for m in rows_m]) for f in names}


FIELDS = ("mean", "p95", "over_limit", "shift", "nofit_share", "mean_booked", "mean_unbooked")


def cap_curve(p, n=C.CURVE_DAYS):
    """Terminsystem über der Fensterkapazität (60 bis 150 %); dazu die freie Anfahrt als Referenzlinie."""
    days = [make_day(p, s) for s in range(n)]
    free = []
    per_cap = {c: [] for c in C.CAP_CURVE_POINTS}
    for day in days:
        free.append(_rule_free(p, day, False)[0])
        for c in C.CAP_CURVE_POINTS:
            slot, nofit = S.book_slots(day, S.window_capacity(p.lanes, p.service, c), p.share_pct)
            arrive = S.appointment_arrivals(day, p.sigma, slot)
            booked = [s is not None for s in slot]
            per_cap[c].append(Q.metrics(Q.waits_fifo(arrive, day.service, p.lanes), day.service, booked, p.lanes, S.shift_minutes(day, slot), nofit))
    series = {"frei": {f: (_mean_none([getattr(m, f) for m in free]),) * len(C.CAP_CURVE_POINTS) for f in FIELDS}}
    rows = [_fields(per_cap[c], FIELDS) for c in C.CAP_CURVE_POINTS]
    series["termin"] = {f: tuple(r[f] for r in rows) for f in FIELDS}
    return Curve(tuple(C.CAP_CURVE_POINTS), series, n)


def share_curve(p, n=C.CURVE_DAYS):
    """Alle drei Regeln über der Buchungsquote (20 bis 100 %)."""
    days = [make_day(p, s) for s in range(n)]
    cap = cap_of(p)
    free = [_rule_free(p, day, False)[0] for day in days]
    shared = {q: [] for q in C.SHARE_CURVE_POINTS}
    prio = {q: [] for q in C.SHARE_CURVE_POINTS}
    for day in days:
        for q in C.SHARE_CURVE_POINTS:
            slot, nofit = S.book_slots(day, cap, q)
            arrive = S.appointment_arrivals(day, p.sigma, slot)
            booked = [s is not None for s in slot]
            shift = S.shift_minutes(day, slot)
            shared[q].append(Q.metrics(Q.waits_fifo(arrive, day.service, p.lanes), day.service, booked, p.lanes, shift, nofit))
            prio[q].append(Q.metrics(Q.waits_priority(arrive, day.service, booked, p.lanes), day.service, booked, p.lanes, shift, nofit))
    pts = C.SHARE_CURVE_POINTS
    series = {"frei": {f: (_mean_none([getattr(m, f) for m in free]),) * len(pts) for f in FIELDS}}
    series["termin"] = {f: tuple(_mean_none([getattr(m, f) for m in shared[q]]) for q in pts) for f in FIELDS}
    series["vorrang"] = {f: tuple(_mean_none([getattr(m, f) for m in prio[q]]) for q in pts) for f in FIELDS}
    return Curve(tuple(pts), series, n)


def lanes_curve(p, n=C.CURVE_DAYS):
    """Freie Anfahrt und Terminsystem über der Zahl der Spuren (Fensterkapazität und Buchungsquote wie eingestellt, Kapazität je Fenster mit der jeweiligen Spurenzahl)."""
    days = [make_day(p, s) for s in range(n)]
    xs = tuple(range(C.LANES_RANGE[0], C.LANES_RANGE[1] + 1))
    free_m, appt_m = [], []
    for lanes in xs:
        q = p._replace(lanes=lanes)
        fr, ap = [], []
        for day in days:
            fr.append(_rule_free(q, day, False)[0])
            slot, nofit = S.book_slots(day, cap_of(q), q.share_pct)
            arrive = S.appointment_arrivals(day, q.sigma, slot)
            ap.append(Q.metrics(Q.waits_fifo(arrive, day.service, lanes), day.service, [s is not None for s in slot], lanes, S.shift_minutes(day, slot), nofit))
        free_m.append(_fields(fr, FIELDS))
        appt_m.append(_fields(ap, FIELDS))
    return Curve(xs, {"frei": {f: tuple(r[f] for r in free_m) for f in FIELDS}, "termin": {f: tuple(r[f] for r in appt_m) for f in FIELDS}}, n)


def lanes_needed(curve, key, limit=C.WAIT_LIMIT):
    """Kleinste Spurenzahl, bei der das 95. Perzentil der Wartezeit höchstens `limit` beträgt; None, wenn keine der gerechneten reicht."""
    for x, v in zip(curve.xs, curve.series[key]["p95"]):
        if v is not None and v <= limit:
            return x
    return None


# ---------------------------------------------------------------------------------------------------
# Diagnose (bedingte Meldung)
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Diagnosis:
    kind: str                # "calm" | "overload" | "quota" | "wide" | "helps"
    free_mean: float
    shared_mean: float
    ratio: object            # Wartezeit mit Terminsystem durch freie Wartezeit; None, wenn die freie 0 ist
    shift: float
    nofit_share: float
    prio_booked: object      # Wartezeit der Termininhaber mit Vorrang; None, wenn niemand einen Termin hat
    prio_unbooked: object    # Wartezeit der Lkw ohne Termin mit Vorrang; None, wenn alle einen haben


def diagnose(outcomes, p):
    """Was zeigt dieser Tag: nichts zu glätten (calm), Fenster reichen nicht für alle (overload), zu wenige buchen (quota), Fenster zu weit (wide) oder das Terminsystem hilft (helps)."""
    fr, sh, pr = (outcome_of(outcomes, k).m for k in C.RULE_KEYS)
    ratio = sh.mean / fr.mean if fr.mean else None
    if fr.mean < C.CALM_FREE_MEAN:
        kind = "calm"
    elif sh.nofit_share > C.OVERLOAD_NOFIT:
        kind = "overload"
    elif ratio is not None and ratio > C.LITTLE_EFFECT and p.share_pct < C.FULL_SHARE:
        kind = "quota"
    elif ratio is not None and ratio > C.LITTLE_EFFECT:
        kind = "wide"
    else:
        kind = "helps"
    return Diagnosis(kind, fr.mean, sh.mean, ratio, sh.shift, sh.nofit_share, pr.mean_booked, pr.mean_unbooked)


def diagnosis_text(d, p):
    """Die bedingte Meldung als Satz ohne Emoji (die App setzt je nach Art ein Zeichen davor, das PDF nicht)."""
    if d.kind == "calm":
        return (f"Kaum Schlange: bei freier Anfahrt warten die Lkw im Mittel nur {d.free_mean:.1f} min (Auslastung {utilisation_of(p) * 100:.0f} %). Ein Terminsystem bringt hier nichts und kostet "
                f"{d.shift:.1f} min Verschiebung. Mehr Lkw pro Tag oder weniger Spuren machen die Spitzen zum Problem.")
    if d.kind == "overload":
        return (f"Die Fenster reichen nicht für alle: {d.nofit_share * 100:.0f} % der Buchenden finden kein Fenster und kommen wie ohne Termin. Mit Terminsystem warten die Lkw im Mittel {d.shared_mean:.1f} min "
                f"(frei: {d.free_mean:.1f} min). Fensterkapazität oder Spuren erhöhen.")
    if d.kind == "quota":
        s = f"Nur {p.share_pct} % buchen: die Lkw ohne Termin halten die Spitze, mit Terminsystem bleiben {d.shared_mean:.1f} von {d.free_mean:.1f} min Wartezeit."
        if d.prio_booked is not None and d.prio_unbooked is not None:
            s += f" Mit Vorrang warten die Termininhaber {d.prio_booked:.1f} min, die Lkw ohne Termin {d.prio_unbooked:.1f} min: der Vorrang verlagert die Wartezeit, das Mittel über alle bleibt."
        return s
    if d.kind == "wide":
        return (f"Die Fenster lassen die Spitze durch: mit Terminsystem warten die Lkw noch {d.shared_mean:.1f} min im Mittel statt {d.free_mean:.1f} min ({d.shift:.1f} min Verschiebung). "
                f"Eine Fensterkapazität bei etwa 90 bis 100 % der Gate-Kapazität wirkt deutlich stärker.")
    return (f"Das Terminsystem senkt die mittlere Wartezeit von {d.free_mean:.1f} auf {d.shared_mean:.1f} min, bei {d.shift:.1f} min mittlerer Verschiebung gegen den Wunschzeitpunkt: "
            f"die Wartezeit wandert vom Gate zur Wunschzeit der Buchenden.")
