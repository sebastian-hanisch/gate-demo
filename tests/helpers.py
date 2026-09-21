"""Testhilfen: zufällige Szenarien und unabhängige, bewusst einfache Nachrechnungen (teilen keinen Code mit gate_queue und gate_scenario)."""

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import gate_constants as C  # noqa: E402
import gate_scenario as S  # noqa: E402


def random_setup(seed):
    """(day, lanes, sigma, cap, share_pct) aus zufälligen, aber gültigen Einstellungen."""
    rng = random.Random(seed)
    n = rng.choice([20, 40, 80, 150])
    lanes = rng.randint(1, 5)
    service = rng.choice([2, 3, 5])
    day = S.make_day(seed, n, rng.choice([0, 25, 50, 75]), float(service))
    return day, lanes, rng.choice([0, 10, 40]), max(1, rng.choice([1, 2, 5, 10, 40])), rng.choice([20, 60, 100])


def reference_waits(arrive, service, lanes, booked=None, priority=False):
    """Unabhängige Ereignisliste: je Spur die Freigabezeit in einer Liste (kein Heap); jede Entscheidung durchsucht alle noch nicht bedienten Lkw."""
    n = len(arrive)
    free = [0.0] * lanes
    left = set(range(n))
    waits = [0.0] * n
    while left:
        lane = min(range(lanes), key=lambda l: free[l])
        t = free[lane]
        waiting = [i for i in left if arrive[i] <= t]
        if not waiting:
            t = min(arrive[i] for i in left)
            waiting = [i for i in left if arrive[i] <= t]
        if priority:
            pool = [i for i in waiting if booked[i]] or waiting
        else:
            pool = waiting
        i = min(pool, key=lambda k: (arrive[k], k))
        waits[i] = t - arrive[i]
        free[lane] = t + service[i]
        left.remove(i)
    return waits


def reference_slots(day, cap, share_pct):
    """Naive Fensterbuchung: je Buchendem alle Fenster nach (Abstand, Index) sortiert durchsuchen."""
    k = S.n_slots()
    used = [0] * k
    out = [None] * day.n
    for i in day.order:
        if not day.booker[i] < share_pct / 100:
            continue
        w = min(int(day.pref[i] // C.SLOT_LEN), k - 1)
        for j in sorted(range(k), key=lambda j: (abs(j - w), j)):
            if used[j] < cap:
                used[j] += 1
                out[i] = j
                break
    return out
