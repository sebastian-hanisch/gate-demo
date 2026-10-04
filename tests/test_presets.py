"""Tests der Regler-Spezifikation: Permalink-Auswertung (begrenzen, einrasten, Müll ignorieren), Presets innerhalb der Reglergrenzen, Konsistenz mit den Konstanten."""

import gate_constants as C
import gate_presets as P

S = P.SETTING_SPECS


def test_parse_clamps_to_range():
    assert P.parse_setting(S["lanes_slider"], "99") == 10 and P.parse_setting(S["lanes_slider"], "-5") == 2 and P.parse_setting(S["lanes_slider"], "6") == 6
    assert P.parse_setting(S["service_slider"], "1") == 2 and P.parse_setting(S["service_slider"], "9") == 5
    assert P.parse_setting(S["seed_input"], "12345") == 9999 and P.parse_setting(S["sigma_slider"], "500") == 90


def test_parse_snaps_to_step_from_lower_bound():
    trucks, peak, cap, share, sigma = S["trucks_slider"], S["peak_slider"], S["cap_slider"], S["share_slider"], S["sigma_slider"]
    assert P.parse_setting(trucks, "620") == 600 and P.parse_setting(trucks, "640") == 650 and P.parse_setting(trucks, "1") == 200 and P.parse_setting(trucks, "5000") == 1200
    assert P.parse_setting(peak, "40") == 50 and P.parse_setting(peak, "60") == 50 and P.parse_setting(peak, "70") == 75 and P.parse_setting(peak, "100") == 75
    assert P.parse_setting(cap, "94") == 90 and P.parse_setting(cap, "96") == 100 and P.parse_setting(cap, "10") == 60 and P.parse_setting(cap, "200") == 150
    assert P.parse_setting(share, "64") == 60 and P.parse_setting(share, "66") == 70 and P.parse_setting(share, "5") == 20 and P.parse_setting(share, "100") == 100
    assert P.parse_setting(sigma, "14") == 10 and P.parse_setting(sigma, "16") == 20
    assert P.parse_setting(share, "65") == 60 and P.parse_setting(share, "75") == 80                      # Python rundet halbe Werte zur geraden Zahl (Bankers Rounding): 4,5 Schritte -> 4, 5,5 -> 6


def test_step_grid_starts_at_the_lower_bound_not_at_zero():
    spec = P.SettingSpec("x", int, 1, 1, 21, 5)
    assert [P.parse_setting(spec, str(v)) for v in (1, 3, 4, 7, 9, 14, 19, 21)] == [1, 1, 6, 6, 11, 16, 21, 21]


def test_parse_ignores_garbage():
    for key in ("lanes_slider", "seed_input", "trucks_slider", "cap_slider", "share_slider"):
        assert P.parse_setting(S[key], "abc") is None and P.parse_setting(S[key], None) is None and P.parse_setting(S[key], "") is None
    assert P.parse_setting(S["lanes_slider"], "4.5") is None                       # nur ganze Zahlen
    assert P.parse_setting(S["view_radio"], "junk") is None
    assert P.parse_setting(S["view_radio"], "frei") is None                        # die Referenz steht immer links, ist keine Wahl rechts
    assert P.parse_setting(S["view_radio"], "vorrang") == "vorrang" and P.parse_setting(S["view_radio"], "termin") == "termin"


def test_specs_match_constants_and_defaults_inside_bounds():
    assert S["lanes_slider"].default == C.LANES_DEFAULT == 4 and S["seed_input"].default == C.SEED_DEFAULT == 289 and S["trucks_slider"].default == 650 and S["cap_slider"].default == 90
    for key, spec in S.items():
        assert P.bounds(key) == (spec.lo, spec.hi)
        if spec.lo is not None:
            assert spec.lo <= spec.default <= spec.hi
            if spec.step and spec.step > 1:
                assert (spec.default - spec.lo) % spec.step == 0
    assert len({spec.url_param for spec in S.values()}) == len(S) and {spec.url_param for spec in S.values()} == {"ln", "tr", "sv", "pk", "cp", "sh", "sg", "seed", "vw"}
    assert S["view_radio"].default in C.RIGHT_VIEW_KEYS and C.BASELINE not in C.RIGHT_VIEW_KEYS


def test_every_preset_is_inside_bounds_on_the_step():
    assert list(C.PRESETS) == ["Ruhiger Tag", "Stoßzeit", "Niedrige Quote", "Fenster zu weit", "Voller Tag"] and all(len(n) <= 16 for n in C.PRESETS)
    for name, p in C.PRESETS.items():
        assert set(p) == set(P.PRESET_STATE_KEYS)
        for field, state_key in P.PRESET_STATE_KEYS.items():
            spec = S[state_key]
            assert spec.lo <= p[field] <= spec.hi, (name, field)
            if spec.step and spec.step > 1:
                assert (p[field] - spec.lo) % spec.step == 0, (name, field)
    assert len({p["seed"] for p in C.PRESETS.values()}) == 1                                   # eine gemeinsame Tages-Nummer


def test_presets_differ_from_the_stossszeit_baseline_in_exactly_the_intended_setting():
    base = C.PRESETS["Stoßzeit"]
    diffs = {name: {k for k in base if base[k] != p[k]} for name, p in C.PRESETS.items() if name != "Stoßzeit"}
    assert diffs == {"Ruhiger Tag": {"trucks"}, "Niedrige Quote": {"share_pct"}, "Fenster zu weit": {"cap_pct"}, "Voller Tag": {"trucks", "cap_pct"}}
    assert base == dict(lanes=4, trucks=650, service=3, peak_pct=50, cap_pct=90, share_pct=100, sigma=10, seed=289)


def test_encoders_roundtrip_through_parse():
    for key, spec in S.items():
        assert P.parse_setting(spec, spec.encoder(spec.default)) == spec.default


def test_preset_state_keys_map_the_right_sliders():
    assert P.PRESET_STATE_KEYS == {"lanes": "lanes_slider", "trucks": "trucks_slider", "service": "service_slider", "peak_pct": "peak_slider", "cap_pct": "cap_slider", "share_pct": "share_slider",
                                   "sigma": "sigma_slider", "seed": "seed_input"}
