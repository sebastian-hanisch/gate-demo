"""Szenario: ein Betriebstag am Gate. Wunschzeiten, Bearbeitungszeiten, Buchungsreihenfolge, Verspätungsrauschen und die Fensterbuchung.

Alles Zufällige eines Tages steht in `Day` (aus dem Seed), unabhängig von Spuren, Regel und Fensterkapazität: so laufen alle Regeln auf denselben Zufallszahlen (gemeinsame Zufallszahlen)."""

import math
import random
from dataclasses import dataclass

import gate_constants as C


@dataclass(frozen=True)
class Day:
    seed: int
    pref: tuple            # Wunschzeit je Lkw in Minuten ab Betriebsbeginn
    service: tuple         # Bearbeitungszeit am Gate in Minuten
    order: tuple           # Buchungsreihenfolge (Permutation der Lkw)
    noise: tuple           # Standardnormale, mit sigma zur Verspätung skaliert
    within: tuple          # Gleichverteilung im Fenster
    booker: tuple          # Gleichverteilung: der Lkw bucht, wenn booker < Buchungsquote

    @property
    def n(self):
        return len(self.pref)


def make_day(seed, n_trucks, peak_pct=50, service_mean=3.0):
    """Ein Tag aus dem Seed. Ein Anteil peak_pct der Lkw wünscht eine von zwei Stoßzeiten (Normalverteilung um 25 % und 70 % des Tages), der Rest gleichverteilt; die Bearbeitung ist lognormal
    mit Mittel service_mean und Streuung C.SERVICE_CV."""
    if n_trucks < 1:
        raise ValueError("Mindestens ein Lkw nötig.")
    if not 0 <= peak_pct <= 100:
        raise ValueError("Der Anteil in Stoßzeiten muss zwischen 0 und 100 % liegen.")
    if service_mean <= 0:
        raise ValueError("Die Bearbeitungszeit muss positiv sein.")
    rng = random.Random(seed)
    T = C.DAY_MINUTES
    peaks = tuple(p * T for p in C.PEAK_POSITIONS)
    share = peak_pct / 100
    pref = []
    for _ in range(n_trucks):
        if rng.random() < share:
            pref.append(min(max(rng.gauss(peaks[rng.randrange(2)], C.PEAK_SD), 0.0), T))
        else:
            pref.append(rng.uniform(0.0, T))
    s2 = math.log(1 + C.SERVICE_CV ** 2)
    mu = math.log(service_mean) - s2 / 2
    service = [rng.lognormvariate(mu, math.sqrt(s2)) for _ in range(n_trucks)]
    order = list(range(n_trucks))
    rng.shuffle(order)
    noise = [rng.gauss(0.0, 1.0) for _ in range(n_trucks)]
    within = [rng.random() for _ in range(n_trucks)]
    booker = [rng.random() for _ in range(n_trucks)]
    return Day(seed, tuple(pref), tuple(service), tuple(order), tuple(noise), tuple(within), tuple(booker))


def n_slots():
    return int(math.ceil(C.DAY_MINUTES / C.SLOT_LEN))


def window_capacity(lanes, service, cap_pct):
    """Lkw je Fenster: Fensterkapazität in % der Gate-Kapazität je Fenster (Spuren mal Fensterlänge durch Bearbeitungszeit), abgerundet, mindestens 1."""
    return max(1, int(cap_pct / 100 * lanes * C.SLOT_LEN / service))


def gate_capacity(lanes, service):
    """Lkw, die das Gate in einem Fenster höchstens schafft (nicht abgerundet)."""
    return lanes * C.SLOT_LEN / service


def wish_slot(pref):
    return min(int(pref // C.SLOT_LEN), n_slots() - 1)


def book_slots(day, cap, share_pct):
    """Fensterindex je Lkw oder None. Es buchen die Lkw mit booker < share_pct / 100 in zufälliger Buchungsreihenfolge; jeder nimmt das dem Wunschfenster nächste Fenster mit freiem Platz
    INNERHALB des Betriebstags (bei gleichem Abstand das frühere). Findet er keins, bleibt er None. Rückgabe: (slots, nofit) mit nofit = Buchende ohne Fenster."""
    k = n_slots()
    used = [0] * k
    slot = [None] * day.n
    nofit = 0
    share = share_pct / 100
    for i in day.order:
        if not day.booker[i] < share:
            continue
        j0 = wish_slot(day.pref[i])
        placed = False
        for d in range(k):
            for j in ((j0 - d, j0 + d) if d else (j0,)):
                if 0 <= j < k and used[j] < cap:
                    used[j] += 1
                    slot[i] = j
                    placed = True
                    break
            if placed:
                break
        if not placed:
            nofit += 1
    return slot, nofit


def free_arrivals(day, sigma):
    """Freie Anfahrt: Wunschzeit plus Verspätung, nicht vor Betriebsbeginn."""
    return [max(0.0, day.pref[i] + sigma * day.noise[i]) for i in range(day.n)]


def appointment_arrivals(day, sigma, slot):
    """Mit Terminsystem: gebuchte Lkw kommen im Fenster (Gleichverteilung) plus Verspätung, alle anderen wie bei freier Anfahrt."""
    out = []
    for i in range(day.n):
        if slot[i] is None:
            out.append(max(0.0, day.pref[i] + sigma * day.noise[i]))
        else:
            out.append(max(0.0, slot[i] * C.SLOT_LEN + day.within[i] * C.SLOT_LEN + sigma * day.noise[i]))
    return out


def shift_minutes(day, slot):
    """Mittlere Verschiebung der Buchenden: Abstand zwischen gebuchtem und Wunschfenster in Minuten (0, wenn niemand bucht)."""
    moved = [abs(slot[i] - wish_slot(day.pref[i])) * C.SLOT_LEN for i in range(day.n) if slot[i] is not None]
    return sum(moved) / len(moved) if moved else 0.0
