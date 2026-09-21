import math
import random
import statistics

import pytest

import gate_constants as C
import gate_evaluation as E
import gate_queue as Q
import gate_scenario as S
from helpers import random_setup, reference_waits


def erlang_c_wait(lam, mean_service, c):
    a = lam * mean_service
    rho = a / c
    s = sum(a ** k / math.factorial(k) for k in range(c))
    top = a ** c / (math.factorial(c) * (1 - rho))
    return top / (s + top) * mean_service / (c * (1 - rho))


def simulate_mmc(lam, mean_service, c, n, seed):
    rng = random.Random(seed)
    t, arrive, service = 0.0, [], []
    for _ in range(n):
        t += rng.expovariate(lam)
        arrive.append(t)
        service.append(rng.expovariate(1 / mean_service))
    w = Q.waits_fifo(arrive, service, c)
    return statistics.fmean(w[n // 10:])


# ---------------------------------------------------------------------------------------------------
# Theorie
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lam,c", [(0.9, 4), (1.1, 4), (1.5, 6)])
def test_fifo_queue_matches_erlang_c_for_poisson_arrivals_and_exponential_service(lam, c):
    theory = erlang_c_wait(lam, 3.0, c)
    sim = statistics.fmean(simulate_mmc(lam, 3.0, c, 60000, s) for s in range(4))
    assert sim == pytest.approx(theory, rel=0.04)


def test_single_lane_matches_the_mm1_formula():
    lam, s = 0.25, 3.0                                                            # rho = 0,75
    rho = lam * s
    theory = rho * s / (1 - rho)
    sim = statistics.fmean(simulate_mmc(lam, s, 1, 80000, k) for k in range(4))
    assert sim == pytest.approx(theory, rel=0.06)


def test_priority_with_equal_service_times_keeps_the_overall_mean_wait():
    """Erhaltungssatz: bei klassenunabhängiger Bearbeitungszeit ändert ein nicht unterbrechender Vorrang das Mittel über alle Lkw nicht (Mehrspur: näherungsweise)."""
    rng = random.Random(5)
    n, c = 40000, 3
    t, arrive, service, booked = 0.0, [], [], []
    for _ in range(n):
        t += rng.expovariate(0.8)
        arrive.append(t)
        service.append(rng.expovariate(1 / 3.0))
        booked.append(rng.random() < 0.6)
    fifo = statistics.fmean(Q.waits_fifo(arrive, service, c))
    prio = Q.waits_priority(arrive, service, booked, c)
    assert statistics.fmean(prio) == pytest.approx(fifo, rel=0.05)
    wb = statistics.fmean(w for w, b in zip(prio, booked) if b)
    wu = statistics.fmean(w for w, b in zip(prio, booked) if not b)
    assert wb < 0.5 * fifo < wu / 1.5                                              # die Wartezeit wandert zu den Lkw ohne Termin


# ---------------------------------------------------------------------------------------------------
# Unabhängige Nachrechnung und Invarianten
# ---------------------------------------------------------------------------------------------------
def test_fifo_and_priority_match_the_independent_reference_on_random_days():
    for seed in range(50):
        day, lanes, sigma, cap, share = random_setup(seed)
        slot, _ = S.book_slots(day, cap, share)
        arrive = S.appointment_arrivals(day, sigma, slot)
        booked = [j is not None for j in slot]
        assert Q.waits_fifo(arrive, day.service, lanes) == pytest.approx(reference_waits(arrive, day.service, lanes), abs=1e-9), seed
        assert Q.waits_priority(arrive, day.service, booked, lanes) == pytest.approx(reference_waits(arrive, day.service, lanes, booked, True), abs=1e-9), seed


def test_priority_equals_fifo_bit_for_bit_when_everyone_or_nobody_has_an_appointment():
    for seed in range(30):
        day, lanes, sigma, cap, share = random_setup(seed)
        arrive = S.free_arrivals(day, sigma)
        fifo = Q.waits_fifo(arrive, day.service, lanes)
        assert Q.waits_priority(arrive, day.service, [False] * day.n, lanes) == fifo
        assert Q.waits_priority(arrive, day.service, [True] * day.n, lanes) == fifo


def test_priority_never_serves_an_unbooked_truck_while_a_booked_one_is_waiting():
    for seed in range(30):
        day, lanes, sigma, cap, share = random_setup(seed)
        slot, _ = S.book_slots(day, cap, share)
        arrive = S.appointment_arrivals(day, sigma, slot)
        booked = [j is not None for j in slot]
        waits = Q.waits_priority(arrive, day.service, booked, lanes)
        start = [a + w for a, w in zip(arrive, waits)]
        for i in range(day.n):
            if not booked[i]:
                for j in range(day.n):
                    if booked[j]:
                        assert not (arrive[j] <= start[i] < start[j] - 1e-9), (seed, i, j)


def test_waits_are_non_negative_lanes_never_overlap_and_a_lone_truck_never_waits():
    for seed in range(30):
        day, lanes, sigma, cap, share = random_setup(seed)
        arrive = S.free_arrivals(day, sigma)
        waits = Q.waits_fifo(arrive, day.service, lanes)
        assert all(w >= 0 for w in waits)
        starts = sorted((a + w, s) for a, w, s in zip(arrive, waits, day.service))
        busy = [0.0] * lanes                                                        # gierig auf Spuren verteilt: nie mehr als `lanes` gleichzeitig
        for st, sv in starts:
            k = min(range(lanes), key=lambda l: busy[l])
            assert busy[k] <= st + 1e-9
            busy[k] = st + sv
    assert Q.waits_fifo([5.0], [3.0], 2) == [0.0] and Q.waits_priority([5.0], [3.0], [True], 2) == [0.0]


def test_more_lanes_never_increase_any_wait_in_fifo():
    day = S.make_day(4, 200, 50, 3.0)
    arrive = S.free_arrivals(day, 10)
    one, two, four = (Q.waits_fifo(arrive, day.service, c) for c in (1, 2, 4))
    assert all(a >= b - 1e-9 for a, b in zip(one, two)) and all(a >= b - 1e-9 for a, b in zip(two, four))


def test_two_trucks_one_lane_hand_computed():
    assert Q.waits_fifo([0.0, 1.0], [5.0, 5.0], 1) == [0.0, 4.0]
    assert Q.waits_fifo([0.0, 1.0, 1.0], [5.0, 2.0, 2.0], 1) == [0.0, 4.0, 6.0]           # gleiche Ankunft: kleinerer Index zuerst
    assert Q.waits_priority([0.0, 1.0, 2.0], [5.0, 2.0, 2.0], [False, False, True], 1) == [0.0, 6.0, 3.0]   # der Lkw mit Termin überholt den früher angekommenen ohne


# ---------------------------------------------------------------------------------------------------
# Kennzahlen
# ---------------------------------------------------------------------------------------------------
def test_percentile95_follows_the_measured_definition():
    assert Q.percentile95([]) is None and Q.percentile95([7.0]) == 7.0
    assert Q.percentile95(list(range(100))) == 95 and Q.percentile95(list(range(20))) == 19 and Q.percentile95(list(range(10))) == 9
    assert Q.percentile95([5, 1, 3]) == 5


def test_metrics_fields():
    waits = [0.0, 2.0, 16.0, 30.0]
    m = Q.metrics(waits, [3.0, 3.0, 3.0, 3.0], [True, True, False, False], 2, shift=4.5, nofit=1)
    assert m.n == 4 and m.mean == 12.0 and m.p95 == 30.0 and m.over_limit == 0.5 and m.max_wait == 30.0 and m.util == pytest.approx(12.0 / (2 * C.DAY_MINUTES))
    assert m.shift == 4.5 and m.booked_share == 0.5 and m.nofit_share == 0.25
    assert m.mean_booked == 1.0 and m.mean_unbooked == 23.0 and m.p95_booked == 2.0 and m.p95_unbooked == 30.0
    m2 = Q.metrics([1.0, 2.0], [1.0, 1.0], [False, False], 1)
    assert m2.mean_booked is None and m2.p95_booked is None and m2.mean_unbooked == 1.5 and m2.booked_share == 0
    m3 = Q.metrics([1.0], [1.0], [True], 1)
    assert m3.mean_unbooked is None and m3.p95_unbooked is None and m3.over_limit == 0.0
    assert Q.metrics([C.WAIT_LIMIT], [1.0], [False], 1).over_limit == 0.0 and Q.metrics([C.WAIT_LIMIT + 0.01], [1.0], [False], 1).over_limit == 1.0


def test_windows_and_trace():
    tr = Q.Trace((5.0, 31.0, 40.0, 719.9), (1.0, 3.0, 5.0, 7.0), (True, True, False, False), 2, 3.0)
    nb, nu, mw = Q.windows(tr)
    assert len(nb) == len(nu) == len(mw) == 24
    assert nb[0] == 1 and nb[1] == 1 and nu[1] == 1 and nu[23] == 1 and sum(nb) + sum(nu) == 4
    assert mw[0] == 1.0 and mw[1] == 4.0 and mw[23] == 7.0 and mw[5] is None


def test_metrics_of_a_real_day_are_consistent():
    p = E.Params(4, 650, 3, 50, 90, 100, 10)
    day = E.make_day(p, 3)
    out = E.run_rules(p, day, record=True)
    for o in out:
        assert len(o.trace.arrive) == len(o.trace.wait) == 650 and o.m.mean == pytest.approx(statistics.fmean(o.trace.wait))
        assert o.m.util == pytest.approx(sum(day.service) / (4 * C.DAY_MINUTES))
        nb, nu, _ = Q.windows(o.trace)
        assert sum(nb) + sum(nu) == 650
