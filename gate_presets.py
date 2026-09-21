"""Regler-Spezifikation, Permalink, Presets und Seed-Knopf (Standardmuster aus dem OR-Demo-Portfolio, siehe rfr_presets.py)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import gate_constants as C


def _view(raw):
    if raw not in C.RIGHT_VIEW_KEYS:
        raise ValueError(raw)
    return raw


def _int_text(value):
    return str(int(value))


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    step: Optional[int] = None
    encoder: Callable = _int_text


SETTING_SPECS = {
    "lanes_slider": SettingSpec("ln", int, C.LANES_DEFAULT, *C.LANES_RANGE, 1),
    "trucks_slider": SettingSpec("tr", int, C.TRUCKS_DEFAULT, *C.TRUCKS_RANGE, C.TRUCKS_STEP),
    "service_slider": SettingSpec("sv", int, C.SERVICE_DEFAULT, *C.SERVICE_RANGE, 1),
    "peak_slider": SettingSpec("pk", int, C.PEAK_PCT_DEFAULT, *C.PEAK_PCT_RANGE, C.PEAK_PCT_STEP),
    "cap_slider": SettingSpec("cp", int, C.CAP_PCT_DEFAULT, *C.CAP_PCT_RANGE, C.CAP_PCT_STEP),
    "share_slider": SettingSpec("sh", int, C.SHARE_PCT_DEFAULT, *C.SHARE_PCT_RANGE, C.SHARE_PCT_STEP),
    "sigma_slider": SettingSpec("sg", int, C.SIGMA_DEFAULT, *C.SIGMA_RANGE, C.SIGMA_STEP),
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE, 1),
    "view_radio": SettingSpec("vw", _view, C.VIEW_DEFAULT, encoder=str),
}

PRESET_STATE_KEYS = {
    "lanes": "lanes_slider", "trucks": "trucks_slider", "service": "service_slider", "peak_pct": "peak_slider", "cap_pct": "cap_slider", "share_pct": "share_slider",
    "sigma": "sigma_slider", "seed": "seed_input",
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def parse_setting(spec, raw):
    """Wert aus der Adresszeile: umwandeln, auf den Bereich begrenzen, auf die Schrittweite runden. None, wenn er sich nicht auswerten lässt."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.step > 1 and spec.lo is not None:
        value = spec.lo + round((value - spec.lo) / spec.step) * spec.step
        value = min(spec.hi, value)
    return value


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = parse_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """values: dict state_key -> aktueller Wert (aus den Widgets, damit dieselbe Änderung, die gerade gerendert wurde, sofort in der Adresszeile landet)."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = SETTING_SPECS[state_key].encoder(value)
    except Exception:
        pass


def apply_preset(name):
    for field, state_key in PRESET_STATE_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][field]


def randomize_seed():
    """Würfelt einen neuen Seed für den Tag."""
    st.session_state["seed_input"] = random.randint(*C.SEED_RANGE)
