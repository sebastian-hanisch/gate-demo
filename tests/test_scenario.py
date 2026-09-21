import pytest

import gate_constants as C
import gate_scenario as S
from helpers import random_setup, reference_slots


def test_day_is_bit_identical_to_the_messreihe_generator():
    """Referenzwerte aus hafen-planung/messreihe_gate/gate.py (dort geprüft: bitgleich in drei Fällen)."""
    d = S.make_day(3, 650, 50, 3.0)
    assert d.n == 650 and d.seed == 3
    assert [round(x, 4) for x in d.pref[:3]] == [138.088, 47.1808, 548.657]
    assert [round(x, 4) for x in d.service[:3]] == [9.9047, 2.7048, 1.3862]
    assert list(d.order[:5]) == [22, 365, 402, 521, 407]
    assert [round(x, 4) for x in d.noise[:2]] == [-1.0096, 0.1851] and [round(x, 4) for x in d.within[:2]] == [0.6729, 0.0602] and [round(x, 4) for x in d.booker[:2]] == [0.7379, 0.5795]
    slot, nofit = S.book_slots(d, S.window_capacity(4, 3, 90), 100)
    assert slot[:8] == [4, 1, 18, 6, 13, 8, 7, 15] and nofit == 0 and S.shift_minutes(d, slot) == pytest.approx(8.954, abs=1e-3)


def test_day_is_deterministic_and_all_fields_have_one_entry_per_truck():
    a, b = S.make_day(5, 100, 50, 3.0), S.make_day(5, 100, 50, 3.0)
    assert a == b and S.make_day(6, 100, 50, 3.0) != a
    for field in (a.pref, a.service, a.order, a.noise, a.within, a.booker):
        assert len(field) == 100
    assert sorted(a.order) == list(range(100))
    assert all(0.0 <= x <= C.DAY_MINUTES for x in a.pref) and all(x > 0 for x in a.service) and all(0 <= x < 1 for x in a.within + a.booker)


@pytest.mark.parametrize("args,message", [((1, 0, 50, 3.0), "Mindestens ein Lkw"), ((1, 10, -1, 3.0), "zwischen 0 und 100"), ((1, 10, 101, 3.0), "zwischen 0 und 100"),
                                          ((1, 10, 50, 0.0), "Bearbeitungszeit muss positiv"), ((1, 10, 50, -1.0), "Bearbeitungszeit muss positiv")])
def test_invalid_days_are_rejected(args, message):
    with pytest.raises(ValueError, match=message):
        S.make_day(*args)


def test_boundary_values_of_a_day_are_valid():
    assert S.make_day(1, 1, 50, 3.0).n == 1                                          # ein einziger Lkw
    assert S.make_day(1, 10, 0, 3.0).n == 10 and S.make_day(1, 10, 100, 3.0).n == 10  # 0 % und 100 % in Stoßzeiten
    assert S.make_day(1, 10, 50, 0.1).n == 10


def test_service_time_mean_and_spread_match_the_settings():
    d = S.make_day(1, 20000, 50, 3.0)
    mean = sum(d.service) / d.n
    sd = (sum((x - mean) ** 2 for x in d.service) / d.n) ** 0.5
    assert mean == pytest.approx(3.0, rel=0.03) and sd / mean == pytest.approx(C.SERVICE_CV, rel=0.05)
    assert sum(S.make_day(1, 5000, 50, 5.0).service) / 5000 == pytest.approx(5.0, rel=0.05)


def test_peak_share_moves_wishes_into_the_two_peaks():
    def in_peaks(d):
        near = [any(abs(x - p * C.DAY_MINUTES) < 2 * C.PEAK_SD for p in C.PEAK_POSITIONS) for x in d.pref]
        return sum(near) / d.n
    calm, busy = in_peaks(S.make_day(2, 5000, 0, 3.0)), in_peaks(S.make_day(2, 5000, 75, 3.0))
    assert calm == pytest.approx(len(C.PEAK_POSITIONS) * 4 * C.PEAK_SD / C.DAY_MINUTES, abs=0.03) and busy > 0.7      # zwei Bereiche von je +-2 Streuungen = die Hälfte des Tages


def test_window_capacity_and_gate_capacity():
    assert S.window_capacity(4, 3, 90) == 36 and S.window_capacity(4, 3, 100) == 40 and S.window_capacity(4, 3, 120) == 48 and S.window_capacity(4, 3, 60) == 24
    assert S.window_capacity(2, 5, 60) == 7 and S.window_capacity(2, 5, 90) == 10 and S.window_capacity(2, 5, 150) == 18
    assert S.window_capacity(1, 5, 1) == 1                                     # mindestens 1
    assert S.gate_capacity(4, 3) == 40.0 and S.gate_capacity(3, 4) == 22.5 and S.n_slots() == 24 and S.wish_slot(0.0) == 0 and S.wish_slot(719.9) == 23 and S.wish_slot(720.0) == 23


def test_booking_matches_the_naive_reference_on_random_days():
    for seed in range(60):
        day, lanes, sigma, cap, share = random_setup(seed)
        slot, nofit = S.book_slots(day, cap, share)
        assert slot == reference_slots(day, cap, share), seed
        assert nofit == sum(1 for i in range(day.n) if day.booker[i] < share / 100 and slot[i] is None)


def test_booking_never_exceeds_the_capacity_or_the_day_and_leaves_non_bookers_without_a_window():
    for seed in range(40):
        day, lanes, sigma, cap, share = random_setup(seed)
        slot, nofit = S.book_slots(day, cap, share)
        counts = {}
        for i, j in enumerate(slot):
            if j is not None:
                assert 0 <= j < S.n_slots() and day.booker[i] < share / 100
                counts[j] = counts.get(j, 0) + 1
        assert all(v <= cap for v in counts.values())
        assert all(slot[i] is None for i in range(day.n) if not day.booker[i] < share / 100)


def test_booking_takes_the_nearest_free_window_and_the_earlier_one_on_a_tie():
    day = S.make_day(0, 4, 0, 3.0)
    day = day.__class__(day.seed, (100.0, 100.0, 100.0, 100.0), day.service, (0, 1, 2, 3), day.noise, day.within, (0.0, 0.0, 0.0, 0.0))
    slot, nofit = S.book_slots(day, 1, 100)
    assert slot == [3, 2, 4, 1] and nofit == 0                                    # Wunschfenster 3, dann 2 (früher bei Gleichstand), dann 4, dann 1
    slot, _ = S.book_slots(day, 2, 100)
    assert slot == [3, 3, 2, 2]


def test_booking_with_too_little_capacity_leaves_trucks_without_a_window():
    day = S.make_day(1, 100, 50, 3.0)
    slot, nofit = S.book_slots(day, 3, 100)                                        # 24 Fenster mal 3 = 72 Plätze für 100 Lkw
    assert nofit == 28 and sum(1 for j in slot if j is not None) == 72
    slot, nofit = S.book_slots(day, 1000, 100)
    assert nofit == 0 and all(j == S.wish_slot(day.pref[i]) for i, j in enumerate(slot))


def test_arrivals_free_and_with_appointments():
    day = S.make_day(2, 50, 50, 3.0)
    free = S.free_arrivals(day, 10)
    assert free == [max(0.0, day.pref[i] + 10 * day.noise[i]) for i in range(50)] and S.free_arrivals(day, 0) == list(day.pref)
    slot, _ = S.book_slots(day, 40, 60)
    arr = S.appointment_arrivals(day, 0, slot)
    for i in range(50):
        if slot[i] is None:
            assert arr[i] == day.pref[i]
        else:
            assert arr[i] == pytest.approx(slot[i] * C.SLOT_LEN + day.within[i] * C.SLOT_LEN) and slot[i] * C.SLOT_LEN <= arr[i] < (slot[i] + 1) * C.SLOT_LEN
    assert all(a >= 0 for a in S.appointment_arrivals(day, 90, slot)) and all(a >= 0 for a in S.free_arrivals(day, 90))


def test_shift_is_zero_without_bookers_and_without_a_move():
    day = S.make_day(1, 30, 50, 3.0)
    assert S.shift_minutes(day, [None] * 30) == 0.0
    slot, _ = S.book_slots(day, 1000, 100)
    assert S.shift_minutes(day, slot) == 0.0
    slot, nofit = S.book_slots(day, 2, 100)                                       # 48 Plätze für 30 Lkw: alle bekommen ein Fenster
    expected = sum(abs(slot[i] - S.wish_slot(day.pref[i])) for i in range(30)) / 30 * C.SLOT_LEN
    assert nofit == 0 and expected > 0 and S.shift_minutes(day, slot) == pytest.approx(expected)
