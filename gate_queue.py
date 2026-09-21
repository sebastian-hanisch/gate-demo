"""Warteschlange am Gate: c gleiche Spuren, eine gemeinsame Schlange. Zwei Disziplinen: FIFO (nach Ankunft) und nicht unterbrechender Vorrang für Lkw mit Termin.

Die Rechnung ist gegen die Theorie geprüft (tests/test_queue.py: Erlang C für Poisson-Ankünfte und exponentielle Bearbeitung) und gegen eine unabhängige Ereignisliste."""

import heapq
from dataclasses import dataclass

import gate_constants as C


def percentile95(values):
    """95. Perzentil: Element mit Rang int(0.95 n) der sortierten Werte (wie in der Messreihe); None bei leerer Liste."""
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(0.95 * len(s)))]


def waits_fifo(arrive, service, lanes):
    """Wartezeit je Lkw bei FIFO: die Spur mit der frühesten Freigabe übernimmt den Lkw, der als nächster ankommt (gleiche Ankunft: kleinerer Index)."""
    n = len(arrive)
    free = [0.0] * lanes
    heapq.heapify(free)
    waits = [0.0] * n
    for i in sorted(range(n), key=lambda k: arrive[k]):
        t = heapq.heappop(free)
        start = max(t, arrive[i])
        waits[i] = start - arrive[i]
        heapq.heappush(free, start + service[i])
    return waits


def waits_priority(arrive, service, booked, lanes):
    """Wartezeit je Lkw mit Vorrang: wird eine Spur frei, bedient sie den am längsten wartenden Lkw MIT Termin, sonst den am längsten wartenden ohne (nicht unterbrechend)."""
    n = len(arrive)
    idx = sorted(range(n), key=lambda k: arrive[k])
    free = [0.0] * lanes
    heapq.heapify(free)
    waits = [0.0] * n
    heap_b, heap_w = [], []
    k = 0
    for _ in range(n):
        t = heapq.heappop(free)
        while k < n and arrive[idx[k]] <= t:
            i = idx[k]
            heapq.heappush(heap_b if booked[i] else heap_w, (arrive[i], i))
            k += 1
        if not heap_b and not heap_w:                       # niemand wartet: die Spur wartet auf den nächsten Lkw
            t = arrive[idx[k]]
            while k < n and arrive[idx[k]] <= t:
                i = idx[k]
                heapq.heappush(heap_b if booked[i] else heap_w, (arrive[i], i))
                k += 1
        a, i = heapq.heappop(heap_b) if heap_b else heapq.heappop(heap_w)
        waits[i] = t - a
        heapq.heappush(free, t + service[i])
    return waits


@dataclass(frozen=True)
class Metrics:
    """Kennzahlen eines Tages für eine Regel."""
    n: int
    mean: float
    p95: float
    over_limit: float        # Anteil der Lkw mit mehr als C.WAIT_LIMIT min Wartezeit
    max_wait: float
    util: float              # Bearbeitungszeit / (Spuren * Tag)
    shift: float             # mittlere Verschiebung der Buchenden in Minuten
    booked_share: float      # Anteil der Lkw mit Termin
    nofit_share: float       # Anteil der Lkw, die buchen wollten und kein Fenster fanden
    mean_booked: object      # mittlere Wartezeit der Lkw mit Termin; None, wenn niemand einen hat
    mean_unbooked: object    # mittlere Wartezeit der Lkw ohne Termin; None, wenn alle einen haben
    p95_booked: object
    p95_unbooked: object


def metrics(waits, service, booked, lanes, shift=0.0, nofit=0):
    n = len(waits)
    wb = [w for w, b in zip(waits, booked) if b]
    wu = [w for w, b in zip(waits, booked) if not b]
    return Metrics(
        n=n, mean=sum(waits) / n, p95=percentile95(waits), over_limit=sum(1 for w in waits if w > C.WAIT_LIMIT) / n, max_wait=max(waits), util=sum(service) / (lanes * C.DAY_MINUTES),
        shift=shift, booked_share=len(wb) / n, nofit_share=nofit / n, mean_booked=sum(wb) / len(wb) if wb else None, mean_unbooked=sum(wu) / len(wu) if wu else None,
        p95_booked=percentile95(wb), p95_unbooked=percentile95(wu))


@dataclass(frozen=True)
class Trace:
    """Ein Tag Lkw für Lkw (für die Darstellung): Ankunft, Wartezeit, ob mit Termin."""
    arrive: tuple
    wait: tuple
    booked: tuple
    lanes: int
    service_mean: float


def windows(trace):
    """Je 30-min-Fenster: (Ankünfte mit Termin, Ankünfte ohne Termin, mittlere Wartezeit der in diesem Fenster Angekommenen; None, wenn keiner kam)."""
    k = int(-(-C.DAY_MINUTES // C.SLOT_LEN))
    nb, nu, sw = [0] * k, [0] * k, [0.0] * k
    for a, w, b in zip(trace.arrive, trace.wait, trace.booked):
        j = min(k - 1, int(a // C.SLOT_LEN))
        (nb if b else nu)[j] += 1
        sw[j] += w
    return nb, nu, [sw[j] / (nb[j] + nu[j]) if nb[j] + nu[j] else None for j in range(k)]
