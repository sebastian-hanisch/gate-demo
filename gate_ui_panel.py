"""Wiederverwendbares Panel zur Darstellung einer Regel im Regelvergleich (je Regel ein Tab)."""

import streamlit as st

import gate_constants as C
import gate_scenario as S
from gate_visualization import day_figure, day_title


def render_rule_panel(prefix, outcome, outcomes, lanes, service):
    """Beschreibung, Kennzahlen (2 x 2) und der Tag am Gate für eine Regel. Deltas lesen sich immer als "diese Regel minus Freie Anfahrt" (weniger ist besser).
    `outcomes` müssen mit record=True gerechnet sein."""
    base = next(o for o in outcomes if o.key == C.BASELINE).m
    m = outcome.m
    is_base = outcome.key == C.BASELINE

    st.markdown(C.RULE_DESCRIPTIONS[outcome.key])
    row1, row2 = st.columns(2), st.columns(2)
    row1[0].metric("Mittlere Wartezeit", f"{m.mean:.1f} min", delta=None if is_base else f"{m.mean - base.mean:+.1f} min", delta_color="inverse",
                   help="Mittel über alle Lkw des Tages.")
    row1[1].metric("95. Perzentil", f"{m.p95:.0f} min", delta=None if is_base else f"{m.p95 - base.p95:+.0f} min", delta_color="inverse",
                   help="So lange wartet der Lkw, der schlechter dran ist als 95 % der anderen.")
    row2[0].metric(f"Anteil über {C.WAIT_LIMIT:.0f} min", f"{m.over_limit * 100:.0f} %", delta=None if is_base else f"{(m.over_limit - base.over_limit) * 100:+.0f} Punkte", delta_color="inverse",
                   help="Anteil der Lkw, die länger als die Grenze warten.")
    row2[1].metric("Verschiebung gegen Wunsch", f"{m.shift:.1f} min" if not is_base else "–", help="Mittlerer Abstand zwischen gebuchtem und Wunschfenster (nur Lkw mit Termin). Bei freier Anfahrt gibt es keine.")
    if m.mean_booked is not None and m.mean_unbooked is not None:
        st.caption(f"Lkw mit Termin ({m.booked_share * 100:.0f} %): {m.mean_booked:.1f} min im Mittel (95 %: {m.p95_booked:.0f}); Lkw ohne Termin: {m.mean_unbooked:.1f} min (95 %: {m.p95_unbooked:.0f}).")
    st.plotly_chart(day_figure(outcome.trace, S.gate_capacity(lanes, service), day_title(outcome.label, m)), width="stretch", key=f"{prefix}_day_chart")
