"""Unabhängiges Orakel für Gate-Warteschlange und Auswertung: (1) FIFO und Vorrang gegen eine Ereignisliste mit gebündelten Zeitpunkten (auch gleichzeitige Ankünfte und
Bearbeitungszeit 0), (2) geschlossene Formeln für das, was die Demo simuliert: Pollaczek-Khinchine (M/G/1 mit der lognormalen Bearbeitung der Demo) und Cobham (nicht
unterbrechender Vorrang, eine Spur), (3) Kennzahlen eines Tages, Urteil und Verteilung gegen eine eigene Rechnung mit numpy."""

import math
import random
import statistics

import numpy as np
import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
import gate_scenario as S


def _event_waits(arrive, service, lanes, booked=None, priority=False):
    """Ereignisliste: je Zeitpunkt zuerst alle Ankünfte und freien Spuren aufnehmen, dann verteilen (Vorrang: Termin zuerst, sonst früheste Ankunft, dann Index)."""
    n = len(arrive)
    by_time = {}
    for i, a in enumerate(arrive):
        by_time.setdefault(a, []).append(i)
    times, ai = sorted(by_time), 0
    free_at, idle = [], list(range(lanes))
    qb, qu, waits, served = [], [], [None] * n, 0
    while served < n:
        now = min(([times[ai]] if ai < len(times) else []) + ([free_at[0][0]] if free_at else []))
        while ai < len(times) and times[ai] == now:
            for i in by_time[now]:
                (qb if priority and booked[i] else qu).append((arrive[i], i))
            ai += 1
        while free_at and free_at[0][0] == now:
            idle.append(free_at.pop(0)[1])
        qb.sort()
        qu.sort()
        while idle and (qb or qu):
            a, i = (qb if qb else qu).pop(0)
            waits[i] = now - a
            free_at.append((now + service[i], idle.pop()))
            free_at.sort()
            served += 1
    return waits


def test_fifo_and_priority_match_the_event_list_including_simultaneous_arrivals():
    rnd = random.Random(99)
    for _ in range(300):
        n, lanes = rnd.randint(1, 50), rnd.randint(1, 8)
        if rnd.random() < 0.5:                                                    # ganzzahlig: viele gleichzeitige Ankünfte, Bearbeitungszeit 0 möglich
            arrive = [float(rnd.randint(0, 30)) for _ in range(n)]
            service = [float(rnd.choice([0, 1, 2, 3, 5])) for _ in range(n)]
        else:
            arrive = [rnd.uniform(0, 60) for _ in range(n)]
            service = [rnd.uniform(0.1, 6) for _ in range(n)]
        booked = [rnd.random() < rnd.choice([0, 0.3, 0.6, 1]) for _ in range(n)]
        assert Q.waits_fifo(arrive, service, lanes) == pytest.approx(_event_waits(arrive, service, lanes), abs=1e-9)
        got = Q.waits_priority(arrive, service, booked, lanes)
        assert min(got) >= 0.0
        assert got == pytest.approx(_event_waits(arrive, service, lanes, booked, True), abs=1e-9)


def test_priority_with_simultaneous_arrivals_on_idle_lanes_never_waits_negative():
    """Zwei Spuren, zwei Lkw kommen gleichzeitig bei t = 20 an: beide fahren sofort an (Wartezeit 0). Früher bediente die zweite Spur den zweiten Lkw schon bei t = 0
    (Wartezeit -20), weil der Sprung der ersten Spur ihn schon in die Warteschlange gelegt hatte."""
    assert Q.waits_priority([20.0, 20.0], [5.0, 5.0], [True, False], 2) == [0.0, 0.0]
    assert Q.waits_priority([20.0, 20.0, 20.0], [5.0, 5.0, 5.0], [False, True, False], 2) == [0.0, 0.0, 5.0]


def _lognormal_service(rng, mean, n):
    s2 = math.log(1 + C.SERVICE_CV ** 2)
    mu = math.log(mean) - s2 / 2
    return [rng.lognormvariate(mu, math.sqrt(s2)) for _ in range(n)]


def _poisson_day(seed, lam, n, mean_s, p_booked=None):
    rng = random.Random(seed)
    t, arrive, booked = 0.0, [], []
    for _ in range(n):
        t += rng.expovariate(lam)
        arrive.append(t)
        booked.append(rng.random() < p_booked if p_booked is not None else False)
    return arrive, _lognormal_service(rng, mean_s, n), booked


def test_single_lane_with_the_demo_service_distribution_matches_pollaczek_khinchine():
    """M/G/1: Wq = lambda E[S^2] / (2 (1 - rho)), E[S^2] = s^2 (1 + cv^2) für die lognormale Bearbeitung der Demo. Mittel über 8 Läufe, Band 3 Standardfehler plus 3 % Einschwingen."""
    lam, s = 0.25, 3.0
    theory = lam * s * s * (1 + C.SERVICE_CV ** 2) / (2 * (1 - lam * s))
    reps = []
    for r in range(8):
        arrive, service, _ = _poisson_day(1000 + r, lam, 40000, s)
        reps.append(statistics.fmean(Q.waits_fifo(arrive, service, 1)[4000:]))
    mean, se = statistics.fmean(reps), statistics.stdev(reps) / math.sqrt(len(reps))
    assert abs(mean - theory) <= 3 * se + 0.03 * theory, (mean, theory, se)


def test_single_lane_non_preemptive_priority_matches_cobham():
    """Cobham: W_hoch = W0 / (1 - rho_hoch), W_niedrig = W0 / ((1 - rho_hoch)(1 - rho)), W0 = lambda E[S^2] / 2."""
    lam, s, p_b = 0.28, 3.0, 0.5
    rho, rho_b = lam * s, lam * p_b * s
    w0 = lam * s * s * (1 + C.SERVICE_CV ** 2) / 2
    theory = {True: w0 / (1 - rho_b), False: w0 / ((1 - rho_b) * (1 - rho))}
    res = {True: [], False: []}
    for r in range(8):
        arrive, service, booked = _poisson_day(5000 + r, lam, 40000, s, p_b)
        w = Q.waits_priority(arrive, service, booked, 1)
        for flag in (True, False):
            res[flag].append(statistics.fmean(x for x, b in zip(w[4000:], booked[4000:]) if b == flag))
    for flag in (True, False):
        mean, se = statistics.fmean(res[flag]), statistics.stdev(res[flag]) / math.sqrt(8)
        assert abs(mean - theory[flag]) <= 3 * se + 0.03 * theory[flag], (flag, mean, theory[flag], se)


def _naive_slots(day, cap, share_pct):
    k = S.n_slots()
    used, out, nofit = [0] * k, [None] * day.n, 0
    for i in day.order:
        if not day.booker[i] < share_pct / 100:
            continue
        wish = min(int(day.pref[i] // C.SLOT_LEN), k - 1)
        for j in sorted(range(k), key=lambda j: (abs(j - wish), j)):
            if used[j] < cap:
                used[j] += 1
                out[i] = j
                break
        else:
            nofit += 1
    return out, nofit


@pytest.mark.parametrize("params,seed", [(E.Params(4, 650, 3, 50, 90, 100, 10), 3), (E.Params(4, 650, 3, 50, 90, 60, 10), 7), (E.Params(3, 850, 4, 75, 60, 80, 40), 11),
                                         (E.Params(6, 300, 2, 0, 150, 100, 0), 5), (E.Params(2, 1200, 5, 75, 100, 20, 90), 2)])
def test_day_metrics_match_an_independent_calculation(params, seed):
    p = params
    day = E.make_day(p, seed)
    outs = {o.key: o.m for o in E.run_rules(p, day)}
    wish = [max(0.0, day.pref[i] + p.sigma * day.noise[i]) for i in range(day.n)]
    slot, nofit = _naive_slots(day, S.window_capacity(p.lanes, p.service, p.cap_pct), p.share_pct)
    booked = [j is not None for j in slot]
    arr_a = [wish[i] if slot[i] is None else max(0.0, slot[i] * 30 + day.within[i] * 30 + p.sigma * day.noise[i]) for i in range(day.n)]
    shift = [abs(slot[i] - min(int(day.pref[i] // 30), 23)) * 30 for i in range(day.n) if slot[i] is not None]
    cases = {C.RULE_FREE: (_event_waits(wish, day.service, p.lanes), [False] * day.n, 0.0, 0),
             C.RULE_SHARED: (_event_waits(arr_a, day.service, p.lanes), booked, statistics.fmean(shift) if shift else 0.0, nofit),
             C.RULE_PRIO: (_event_waits(arr_a, day.service, p.lanes, booked, True), booked, statistics.fmean(shift) if shift else 0.0, nofit)}
    for key, (waits, bk, sh, nf) in cases.items():
        m, srt = outs[key], sorted(waits)
        assert m.mean == pytest.approx(np.mean(waits), abs=1e-9) and m.p95 == pytest.approx(srt[min(day.n - 1, int(0.95 * day.n))], abs=1e-9)
        assert m.over_limit == pytest.approx(np.mean(np.array(waits) > 15.0)) and m.max_wait == pytest.approx(max(waits), abs=1e-9)
        assert m.util == pytest.approx(sum(day.service) / (p.lanes * 720.0)) and m.shift == pytest.approx(sh, abs=1e-9)
        assert m.booked_share == pytest.approx(sum(bk) / day.n) and m.nofit_share == pytest.approx(nf / day.n)
        wb = [w for w, b in zip(waits, bk) if b]
        wu = [w for w, b in zip(waits, bk) if not b]
        assert (m.mean_booked is None) == (not wb) and (m.mean_unbooked is None) == (not wu)
        if wb:
            assert m.mean_booked == pytest.approx(np.mean(wb), abs=1e-9)
        if wu:
            assert m.mean_unbooked == pytest.approx(np.mean(wu), abs=1e-9)


def test_verdict_and_distribution_match_numpy():
    p = E.Params(4, 650, 3, 50, 90, 60, 10)
    rows = E.sample(p, 40)
    for key in (C.RULE_SHARED, C.RULE_PRIO):
        d = np.array([r.m[key].mean - r.m[C.RULE_FREE].mean for r in rows])
        v = E.verdict(rows, key, C.RULE_FREE)
        se = d.std(ddof=1) / math.sqrt(len(d))
        assert v.diff == pytest.approx(d.mean(), abs=1e-9) and v.se == pytest.approx(se, abs=1e-9) and v.n == 40
        assert v.kind == ("unclear" if abs(d.mean()) <= C.VERDICT_Z * se else ("better" if d.mean() < 0 else "worse"))
        assert v.pct == pytest.approx(100 * d.mean() / np.mean([r.m[C.RULE_FREE].mean for r in rows]), abs=1e-9)
        dist = E.distribution(rows, key, C.RULE_FREE)
        assert dist.better == pytest.approx(np.mean(d < -1e-9)) and dist.worse == pytest.approx(np.mean(d > 1e-9))
        assert dist.mean_gain == pytest.approx(-d.mean(), abs=1e-9) and dist.median_gain == pytest.approx(-np.median(d), abs=1e-9)
