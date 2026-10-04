"""
Lkw-Gate – interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Zusatz zur Hafen-Linie (Lkw-Terminvergabe): Lkw warten vor den Spuren des Gates, vor allem in Stoßzeiten. Gezeigt wird, was ein Terminsystem an Wartezeit spart, was es die Spediteure an
Verschiebung kostet, wie viele Spuren es spart und wer die Wartezeit trägt, wenn nicht alle buchen (Vorrang für Termininhaber).

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import gate_constants as C
import gate_evaluation as E
import gate_scenario as S
import gate_visualization as V
from gate_pdf_export import generate_gate_pdf
from gate_presets import apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, SETTING_SPECS, sync_query_params
from gate_ui_panel import render_rule_panel

st.set_page_config(page_title="Lkw-Gate – Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)
FR, SH, PR = C.RULE_FREE, C.RULE_SHARED, C.RULE_PRIO
LABEL = C.RULE_LABELS


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_day(key):
    """Ein Tag (Seed) mit allen drei Regeln, mit Verlauf für die Darstellung."""
    p = E.Params(*key[:-1])
    return E.run_rules(p, E.make_day(p, key[-1]), record=True)


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_sample(key):
    """Stichprobe (Seeds 0-99), unabhängig vom eingestellten Seed."""
    return E.sample(E.Params(*key))


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_cap_curve(key):
    """Kapazitätskurve: läuft über die Fensterkapazität, hängt also nicht von ihr ab."""
    return E.cap_curve(E.Params(*key))


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_share_curve(key):
    """Quotenkurve: läuft über die Buchungsquote, hängt nicht von ihr ab."""
    return E.share_curve(E.Params(*key))


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_lanes_curve(key):
    """Spurenkurve: läuft über die Zahl der Spuren, hängt nicht von ihr ab."""
    return E.lanes_curve(E.Params(*key))


st.title("🚛 Lkw-Gate: Was bringt ein Terminsystem?")
st.markdown(
    """
An der Einfahrt eines Containerterminals warten Lkw vor den Spuren des **Gates**, vor allem in den Stoßzeiten. Ein **Terminsystem** vergibt Zeitfenster mit begrenzter **Fensterkapazität** und
glättet die Spitzen. Die Demo zeigt, was das an Wartezeit spart, was es die Spediteure an **Verschiebung** gegen ihren Wunschzeitpunkt kostet, wie viele Spuren es spart und was passiert, wenn nicht
alle buchen (**Buchungsquote**). Wie das Modell funktioniert, steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Beschreibung im Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Ruhiger Tag": "Kaum Schlange: das Terminsystem bringt nichts und kostet nur Verschiebung.",
    "Stoßzeit": "Die Spitzen überlasten das Gate: das Terminsystem glättet sie und senkt die Wartezeit stark, gegen eine Verschiebung von rund zehn Minuten.",
    "Niedrige Quote": "Nur 60 % buchen: in der gemeinsamen Schlange bleibt fast alles beim Alten, der Vorrang verteilt die Wartezeit nur um (Termininhaber kurz, die anderen lang).",
    "Fenster zu weit": "Die Fenster sind weiter als das Gate: sie lassen die Spitze durch und bringen kaum etwas.",
    "Voller Tag": "Volle Auslastung: ohne Termine bricht das Gate zusammen, mit Terminen bleibt es tragbar, aber die Verschiebung wird groß.",
}
# Je Zeile drei Schaltflächen: bei fünf in einer Zeile werden die Namen in schmalen Fenstern abgeschnitten.
preset_names = list(C.PRESETS.keys())
for row in (preset_names[:3], preset_names[3:]):
    cols = st.columns(3)
    for col, name in zip(cols, row):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

ss = st.session_state
util_now = ss["trucks_slider"] * ss["service_slider"] / (ss["lanes_slider"] * C.DAY_MINUTES)
cap_now = S.window_capacity(ss["lanes_slider"], ss["service_slider"], ss["cap_slider"])

with st.sidebar:
    st.header("⚙️ Einstellungen")
    lanes = st.slider("Gate-Spuren", *bounds("lanes_slider"), key="lanes_slider", help="Zahl paralleler Spuren mit einer gemeinsamen Schlange. Bestimmt, wie viele Lkw das Gate je Fenster schafft.")
    trucks = st.slider("Lkw pro Tag", *bounds("trucks_slider"), step=C.TRUCKS_STEP, key="trucks_slider",
                       help=f"Mittlere Auslastung der Spuren = Lkw mal Bearbeitungszeit durch Spuren mal Tag, jetzt {util_now * 100:.0f} %. Probleme entstehen, wenn die Stoßzeiten über der Kapazität liegen "
                            "(mittlere Auslastung ab etwa 60 %).")
    service = st.slider("Bearbeitung je Lkw (min)", *bounds("service_slider"), key="service_slider", help="Mittlere Zeit am Gate (lognormal verteilt, Streuung 0,6).")
    peak_pct = st.slider("Anteil in Stoßzeiten (%)", *bounds("peak_slider"), step=C.PEAK_PCT_STEP, format="%d%%", key="peak_slider",
                         help="Anteil der Lkw, die eine von zwei Stoßzeiten wünschen (Schichtwechsel); der Rest kommt gleichverteilt. Ohne Spitzen gibt es nichts zu glätten.")
    cap_pct = st.slider("Fensterkapazität (% der Gate-Kapazität)", *bounds("cap_slider"), step=C.CAP_PCT_STEP, format="%d%%", key="cap_slider",
                        help=f"Lkw je 30-min-Fenster in Prozent dessen, was das Gate in 30 min schafft; jetzt {cap_now} Lkw je Fenster. Um 90 bis 100 % wirkt das Terminsystem am besten.")
    share_pct = st.slider("Buchungsquote (%)", *bounds("share_slider"), step=C.SHARE_PCT_STEP, format="%d%%", key="share_slider",
                          help="Anteil der Lkw, die ein Fenster buchen. Die anderen kommen wie ohne Termin. Bei 100 % gibt es keine Lkw ohne Termin.")
    sigma = st.slider("Verspätung σ (min)", *bounds("sigma_slider"), step=C.SIGMA_STEP, key="sigma_slider", help="Streuung der Ankunft um den Wunschzeitpunkt beziehungsweise um das Fenster.")
    seed = st.number_input("Seed", *bounds("seed_input"), key="seed_input", step=1, help="Bestimmt Wunschzeiten, Bearbeitungszeiten, Buchungsreihenfolge und Verspätungen.")
    st.button("🎲 Neuer Tag", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed für den Tag.")

sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

p = E.Params(int(lanes), int(trucks), int(service), int(peak_pct), int(cap_pct), int(share_pct), int(sigma))
with st.spinner("Simuliere den Tag..."):
    outcomes = _compute_day(tuple(p) + (int(seed),))
by_key = {o.key: o for o in outcomes}
free = by_key[FR]
diag = E.diagnose(outcomes, p)
gate_cap = S.gate_capacity(p.lanes, p.service)
cap = E.cap_of(p)

# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🎯 Wie lange warten die Lkw am Gate?")
st.caption(f"{p.lanes} Spuren schaffen {gate_cap:.0f} Lkw je 30 min; Fensterkapazität {cap} Lkw je Fenster; {p.trucks} Lkw am Tag, mittlere Auslastung {E.utilisation_of(p) * 100:.0f} %, "
           f"Buchungsquote {p.share_pct} %. Angezeigt wird die gewählte Regel (siehe Blick in den Tag); Delta = Regel minus Freie Anfahrt.")

right_key = ss.get("view_radio", C.VIEW_DEFAULT)
chosen = by_key[right_key]
m, base = chosen.m, free.m
metric_rows = [st.columns(2), st.columns(2)]                  # 2 x 2: vier Spalten schneiden die Namen bei 800 px ab
mm = metric_rows[0] + metric_rows[1]
mm[0].metric("Mittlere Wartezeit", f"{m.mean:.1f} min", delta=f"{m.mean - base.mean:+.1f} min", delta_color="inverse" if abs(m.mean - base.mean) > 0.05 else "off",
             help=f"Mittel über alle Lkw des Tages, Regel: {LABEL[right_key]}. Delta gegen Freie Anfahrt; weniger ist besser.")
mm[1].metric("95. Perzentil", f"{m.p95:.0f} min", delta=f"{m.p95 - base.p95:+.0f} min", delta_color="inverse" if abs(m.p95 - base.p95) >= 0.5 else "off",
             help="So lange wartet der Lkw, der schlechter dran ist als 95 % der anderen.")
mm[2].metric(f"Anteil über {C.WAIT_LIMIT:.0f} min", f"{m.over_limit * 100:.0f} %", delta=f"{(m.over_limit - base.over_limit) * 100:+.0f} Punkte",
             delta_color="inverse" if abs(m.over_limit - base.over_limit) >= 0.005 else "off", help="Anteil der Lkw, die länger als 15 min warten.")
mm[3].metric("Verschiebung gegen Wunsch", f"{m.shift:.1f} min", help="Mittlerer Abstand zwischen gebuchtem und Wunschfenster (nur Lkw mit Termin). Der Preis des Terminsystems für die Spediteure.")

text = E.diagnosis_text(diag, p)
if diag.kind == "helps":
    st.success(f"✅ {text}")
elif diag.kind == "calm":
    st.info(f"ℹ️ {text}")
else:
    st.warning(f"⚠️ {text}")

st.markdown("#### 🔍 Blick in den Tag")
right_key = st.radio("Rechts vergleichen mit", list(C.RIGHT_VIEW_KEYS), format_func=LABEL.get, key="view_radio", horizontal=True, help="Links steht immer Freie Anfahrt.")
right = by_key[right_key]
left_col, right_col = st.columns(2)
day_ranges = V.shared_day_ranges([free.trace, right.trace], gate_cap)                       # beide Diagramme mit denselben Achsen: sie sollen sich vergleichen lassen
for col, outcome, side in ((left_col, free, "left"), (right_col, right, "right")):
    with col:
        st.plotly_chart(V.day_figure(outcome.trace, gate_cap, V.day_title(outcome.label, outcome.m), day_ranges), width="stretch", key=f"day_chart_{side}")
st.caption("Oben die Ankünfte je 30 min (blau mit Termin, orange ohne) gegen die Gate-Kapazität (rot gestrichelt): was darüber liegt, staut sich. Unten die mittlere Wartezeit der in diesem Fenster "
           f"Angekommenen, gepunktet die {C.WAIT_LIMIT:.0f}-Minuten-Grenze.")

pdf_slot = st.container()

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.subheader("📐 Was kostet das Terminsystem, und wie viele Spuren spart es?")
st.markdown(
    """
Kernfrage dieser Demo: Was spart das Terminsystem an Wartezeit, was kostet es an **Verschiebung**, wie viele **Spuren** spart es, und wer trägt die Wartezeit, wenn nicht alle buchen? Ein
**Vorrang für Termininhaber** senkt deren Wartezeit, aber nicht das Mittel über alle: er **verlagert** die Wartezeit auf die Lkw ohne Termin. Hier live für Ihre Einstellungen gerechnet,
**mit der Verteilung dazu**:
"""
)
with st.spinner("Rechne Stichprobe und Kurven..."):
    key = tuple(p)
    sample = _compute_sample(key)
    cap_curve = _compute_cap_curve(key[:4] + (0,) + key[5:])
    share_curve = _compute_share_curve(key[:5] + (0,) + key[6:])
    lanes_curve = _compute_lanes_curve((0,) + key[1:])
g1, g2, g3 = st.columns(3)
g1.metric("Gate-Kapazität je Fenster", f"{gate_cap:.0f} Lkw", help="So viele Lkw schafft das Gate in 30 min bei mittlerer Bearbeitungszeit: Spuren mal 30 durch Bearbeitungszeit.")
g2.metric("Fensterkapazität", f"{cap} Lkw", help="So viele Lkw dürfen je Fenster buchen (Fensterkapazität in Prozent der Gate-Kapazität, abgerundet).")
g3.metric("Mittlere Auslastung", f"{E.utilisation_of(p) * 100:.0f} %", help="Lkw mal Bearbeitungszeit durch Spuren mal Betriebstag. Die Stoßzeiten liegen weit darüber.")

st.markdown("**Wartezeit und Verschiebung über der Fensterkapazität**")
cap_wait, cap_shift = V.cap_curve_figures(cap_curve, p.cap_pct)
st.plotly_chart(cap_wait, width="stretch", key="cap_wait_chart")
st.plotly_chart(cap_shift, width="stretch", key="cap_shift_chart")
st.caption(f"Basis: {cap_curve.n_days} Tage (Seeds 0-{cap_curve.n_days - 1}, nicht Ihr Seed) mit Ihren Einstellungen (Buchungsquote {p.share_pct} %). Enge Fenster senken die Wartezeit, aber die Verschiebung wächst; "
           "ab etwa 90 bis 100 % der Gate-Kapazität kostet jede weitere Verengung mehr Verschiebung, als sie an Wartezeit bringt. Unter dem Bedarf des Tages finden Lkw kein Fenster und kommen wie ohne Termin.")


def _show_verdict(label, key, reference, field, unit):
    if not (E.values(sample, key, field) and E.values(sample, reference, field)):
        st.info(f"ℹ️ **{label}**: bei diesen Einstellungen gibt es keine Lkw dieser Gruppe (Buchungsquote {p.share_pct} %).")
        return
    v = E.verdict(sample, key, reference, field)
    d = E.distribution(sample, key, reference, field)
    if v.kind == "better":
        amount = f"**{abs(v.pct):.0f} % weniger**" if v.pct is not None else f"**{abs(v.diff):.2f} min weniger**"
        st.success(f"✅ **{label}**: im Mittel {amount} {unit} ({v.diff:+.2f} min je Tag, Standardfehler {v.se:.2f}). An **{d.worse * 100:.0f} %** der Tage ist es umgekehrt.")
    elif v.kind == "worse":
        amount = f"**{v.pct:.0f} % mehr**" if v.pct is not None else f"**{v.diff:.2f} min mehr**"
        st.warning(f"⚠️ **{label}**: im Mittel {amount} {unit} ({v.diff:+.2f} min je Tag, Standardfehler {v.se:.2f}). An **{d.better * 100:.0f} %** der Tage ist es besser.")
    else:
        st.info(f"ℹ️ Kein klarer Unterschied bei **{label}**: die Differenz ({v.diff:+.2f} min {unit}, gemittelt über die Tage) liegt innerhalb des Rauschens (Standardfehler {v.se:.2f}). "
                f"Besser an {d.better * 100:.0f} %, schlechter an {d.worse * 100:.0f} % der Tage.")


st.markdown("**Urteil über die Stichprobe** (gepaarte Differenz je Tag, klar ab mehr als zwei Standardfehlern)")
_show_verdict("Terminsystem gegen Freie Anfahrt, mittlere Wartezeit", SH, FR, "mean", "Wartezeit")
_show_verdict("Vorrang gegen Terminsystem, mittlere Wartezeit aller Lkw", PR, SH, "mean", "Wartezeit")
_show_verdict("Vorrang gegen Terminsystem, Wartezeit der Termininhaber", PR, SH, "mean_booked", "Wartezeit")
dcol1, dcol2 = st.columns(2)
with dcol1:
    st.markdown("**Mittlere Wartezeit gegen Freie Anfahrt** (Anteil der Tage)")
    st.plotly_chart(V.distribution_figure([E.distribution(sample, k, FR) for k in (SH, PR)], [C.RULE_SHORT[k] for k in (SH, PR)], "frei", "Wartezeit"), width="stretch", key="distribution_free_chart")
with dcol2:
    st.markdown("**Vorrang gegen Terminsystem** (Anteil der Tage)")
    rows_d = [("alle Lkw", E.distribution(sample, PR, SH, "mean"))]
    if E.values(sample, PR, "mean_booked") and E.values(sample, SH, "mean_booked"):
        rows_d.append(("Termininhaber", E.distribution(sample, PR, SH, "mean_booked")))
    st.plotly_chart(V.distribution_figure([d for _, d in rows_d], [n for n, _ in rows_d], "Terminsystem", "Wartezeit"), width="stretch", key="distribution_priority_chart")
st.caption(
    f"Basis: {len(sample)} Tage (Seeds 0-{len(sample) - 1}, nicht Ihr Seed). Im Mittel je Tag {E.mean_of(sample, FR):.1f} min Wartezeit bei freier Anfahrt, {E.mean_of(sample, SH):.1f} min mit Terminsystem "
    f"(Verschiebung {E.mean_of(sample, SH, 'shift'):.1f} min) und {E.mean_of(sample, PR):.1f} min mit Vorrang. Gleich heißt: dieselbe Zahl am selben Tag."
)

st.markdown("**Wartezeit über der Buchungsquote**")
st.plotly_chart(V.share_curve_figure(share_curve, p.share_pct), width="stretch", key="share_curve_chart")
st.caption(f"Basis: {share_curve.n_days} Tage (Seeds 0-{share_curve.n_days - 1}); Fensterkapazität {p.cap_pct} % wie eingestellt. Bei sinkender Quote halten die Lkw ohne Termin die Spitze: die gemeinsame Schlange "
           "wartet fast wieder so lange wie ohne Terminsystem. Der Vorrang senkt die Wartezeit der Termininhaber, die der anderen steigt (bei Quote 100 % gibt es keine).")

st.markdown("**Wie viele Spuren spart das Terminsystem?**")
need_free, need_appt = E.lanes_needed(lanes_curve, "frei"), E.lanes_needed(lanes_curve, "termin")
sp1, sp2, sp3 = st.columns(3)
sp1.metric("Spuren frei", f"{need_free}" if need_free else f"> {C.LANES_RANGE[1]}", help=f"Kleinste Spurenzahl, bei der 95 % der Lkw höchstens {C.WAIT_LIMIT:.0f} min warten, bei freier Anfahrt.")
sp2.metric("Spuren mit Termin", f"{need_appt}" if need_appt else f"> {C.LANES_RANGE[1]}", help="Dasselbe mit Terminsystem (Fensterkapazität und Buchungsquote wie eingestellt).")
sp3.metric("Gesparte Spuren", f"{need_free - need_appt}" if need_free and need_appt else "–", help="Unterschied der beiden; fehlt, wenn eine der Zahlen außerhalb von 2 bis 10 Spuren liegt.")
st.plotly_chart(V.lanes_curve_figure(lanes_curve, p.lanes), width="stretch", key="lanes_curve_chart")
st.caption(f"Basis: {lanes_curve.n_days} Tage (Seeds 0-{lanes_curve.n_days - 1}); die Fensterkapazität folgt der jeweiligen Spurenzahl. Die Achse endet bei {V.LANES_Y_MAX:.0f} min: höhere Werte laufen aus dem Bild. "
           "Weniger Spuren sparen Kosten, aber nur, wenn die Verschiebung der Spediteure akzeptabel ist (Kapazitätskurve oben).")

with pdf_slot:
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_gate_pdf(p, int(seed), outcomes, diag, sample=sample, curve=cap_curve),
        file_name="gate_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Szenario, Regelvergleich, Diagnose, Stichprobe mit Urteil und die Kapazitätskurve.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Regelvergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – Regeln im Vergleich"):
    tabs = st.tabs([o.label for o in outcomes] + ["📊 Vergleich"])
    for tab, outcome in zip(tabs, outcomes):
        with tab:
            render_rule_panel(f"rule_{outcome.key}", outcome, outcomes, p.lanes, p.service)
    with tabs[3]:
        table = []
        for o in outcomes:
            r = o.m
            table.append({"Regel": o.label, "Mittlere Wartezeit (min)": round(r.mean, 1), "95. Perzentil (min)": round(r.p95), f"Anteil über {C.WAIT_LIMIT:.0f} min (%)": round(r.over_limit * 100),
                          "Verschiebung (min)": round(r.shift, 1) if o.key != FR else None, "mit Termin (%)": round(r.booked_share * 100),
                          "Wartezeit mit Termin (min)": None if r.mean_booked is None else round(r.mean_booked, 1),
                          "Wartezeit ohne Termin (min)": None if r.mean_unbooked is None else round(r.mean_unbooked, 1), "Delta Wartezeit (min)": round(r.mean - base.mean, 1)})
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)
        st.plotly_chart(V.wait_bar_figure(outcomes), width="stretch", key="comparison_wait_chart")
        st.caption("Ein Tag, drei Regeln. Bei einer Buchungsquote von 100 % sind Terminsystem und Vorrang gleich: es gibt keine Lkw ohne Termin, die der Vorrang zurücksetzen könnte.")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Der Tag.** Ein Betriebstag hat 12 Stunden. Jeder Lkw hat einen **Wunschzeitpunkt**: ein Teil wünscht eine von zwei **Stoßzeiten** (etwa Schichtwechsel), der Rest kommt gleichverteilt. Am Gate
bedienen **Spuren** die Lkw aus einer gemeinsamen Schlange; die Bearbeitung dauert im Mittel so viele Minuten, wie eingestellt (lognormal, Streuung 0,6). Die Lkw kommen nicht auf die Minute:
die **Verspätung** streut mit σ um den Wunschzeitpunkt.

**Drei Regeln**, alle auf demselben Tag (gleichen Zufallszahlen):

- **🚚 Freie Anfahrt** (Referenz): jeder kommt zur Wunschzeit plus Verspätung.
- **📅 Terminsystem:** Zeitfenster von 30 min mit höchstens so vielen Lkw, wie die **Fensterkapazität** sagt (in Prozent dessen, was das Gate in 30 min schafft). Die Lkw buchen in zufälliger
  Reihenfolge das dem Wunsch nächste Fenster mit freiem Platz, **innerhalb des Betriebstags**; die **Verschiebung** ist der Abstand zwischen gebuchtem und Wunschfenster. Wer nicht bucht oder kein
  Fenster findet, kommt wie ohne Termin. Alle stehen in derselben Schlange.
- **⭐ Terminsystem mit Vorrang:** wie das Terminsystem, aber wird eine Spur frei, bedient sie zuerst den am längsten wartenden Lkw mit Termin, sonst den ohne (nicht unterbrechend).

**Warum das Terminsystem wirkt.** Ohne Termine kommen in den Stoßzeiten mehr Lkw, als das Gate schafft: die Schlange wächst. Das Terminsystem begrenzt die Ankünfte je Fenster auf etwa die
Kapazität des Gates und schiebt den Überschuss in ruhigere Fenster: die Wartezeit wandert vom Gate zur Wunschzeit der Buchenden. Das kostet Verschiebung.

**Warum die Buchungsquote zählt.** Buchen nur einige, bleibt die Spitze der Lkw ohne Termin, und alle stehen in derselben Schlange: die Wartezeit sinkt kaum. Ein **Vorrang** für Termininhaber senkt
deren Wartezeit stark, aber nicht das Mittel über alle (bei gleichen Bearbeitungszeiten gilt ein Erhaltungssatz, bei mehreren Spuren nur näherungsweise: in den Presets weicht das Mittel um weniger als 0,3 % ab): die Lkw ohne Termin warten entsprechend länger. Das ist ein Anreiz zu buchen, keine
Einsparung.

**Warum die Auslastung zählt.** Bei ruhigem Tag (niedrige mittlere Auslastung) gibt es keine Schlange, die ein Terminsystem glätten könnte: es kostet dann nur Verschiebung.

**Stichprobe, Verteilung und Urteil.** Die Stichprobe stellt Ihre Einstellungen auf 100 Tage (Seeds 0 bis 99, nicht Ihr Seed) nach. Ein Unterschied gilt als klar, wenn er mehr als zwei
Standardfehler der gepaarten Differenz beträgt. Die Verteilung zeigt, an wie vielen Tagen eine Regel weniger, gleich viel oder mehr Wartezeit hat.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- Alle Lkw sind gleich: keine Spurtypen (Import, Export), keine Ausreißer bei der Dokumentenprüfung; **keine No-Shows** und keine Ablehnung zu früher Lkw.
- Die Schlange vor dem Gate hat keine Platzgrenze (kein Rückstau auf die Straße); ein Tag startet und endet leer.
- Wunschzeiten, Stoßzeiten und Bearbeitungszeit sind **Annahmen** (Größenordnung, nicht an Echtdaten gemessen); die Lkw buchen ohne Absprache.
- Die **Verschiebung ist kein Geldbetrag**; ihr Preis gegen eine Wartezeit ist Sache des Betreibers, deshalb werden beide nicht zu einer Zahl vermischt.
- Die Fensterlänge (30 min) und die Streuung der Bearbeitungszeit sind fest: 10 bis 120 min Fensterlänge sind bei gleicher relativer Kapazität kaum verschieden, eine größere Streuung erhöht die
  Wartezeit mit Terminsystem.
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an echten Terminals**; die Rechnung selbst ist gegen die Theorie (Erlang C) geprüft.
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Gate.** $c$ gleiche Spuren, eine gemeinsame Schlange. Lkw $j$ kommt zur Zeit $a_j$ und braucht $s_j$ Minuten (lognormal mit Mittel $\bar s$ und Variationskoeffizient $0{,}6$). Sei $f_l$ die Zeit, zu der Spur
$l$ frei wird. Bei FIFO nimmt die Spur mit dem kleinsten $f_l$ den nächsten Lkw (nach Ankunft): $W_j = \max(0,\ \min_l f_l - a_j)$, danach $f_l \leftarrow \max(f_l, a_j) + s_j$. Im Grenzfall Poisson-Ankünfte
und exponentielle Bearbeitung ist das die M/M/c-Schlange, deren mittlere Wartezeit die Erlang-C-Formel liefert (Test).

**Ankunft.** Freie Anfahrt: $a_j = \max(0,\ w_j + \sigma \varepsilon_j)$ mit Wunschzeit $w_j$ und $\varepsilon_j \sim \mathcal N(0,1)$. Mit Terminsystem und Fenster $k_j$: $a_j = \max(0,\ 30\,(k_j + U_j) + \sigma \varepsilon_j)$
mit $U_j \sim \mathcal U(0,1)$; ohne Fenster wie frei.

**Buchung.** Fenster $k = 0, \dots, 23$ mit Kapazität $K = \lfloor q \cdot c \cdot 30 / \bar s \rfloor$ ($q$ = Fensterkapazität in Prozent der Gate-Kapazität, mindestens 1). Die buchenden Lkw ($u_j < b$ mit
Buchungsquote $b$) kommen in zufälliger Reihenfolge; Lkw $j$ mit Wunschfenster $w(j) = \min(\lfloor w_j / 30 \rfloor, 23)$ erhält das Fenster $k$ mit freiem Platz und kleinstem $|k - w(j)|$ (bei Gleichstand das frühere).
Findet er keins, bleibt er ohne Fenster. **Verschiebung** $V = \frac{30}{|B|} \sum_{j \in B} |k_j - w(j)|$ über die Buchenden $B$.

**Vorrang.** Wird eine Spur zur Zeit $t$ frei, wählt sie unter den bereits angekommenen Lkw den mit Termin und kleinster Ankunftszeit, sonst den ohne (nicht unterbrechend). Für klassenunabhängige
Bearbeitungszeiten gilt der Erhaltungssatz: das Mittel der Wartezeit über alle Lkw ist gleich dem bei FIFO (exakt für eine Spur, bei mehreren Spuren und lognormaler Bearbeitung nur näherungsweise).

**Kennzahlen.** Mittlere Wartezeit $\bar W$, 95. Perzentil $W_{(\lfloor 0{,}95 n \rfloor)}$, Anteil mit $W_j > 15$ min, Verschiebung $V$; Auslastung $\rho = \sum_j s_j / (c \cdot 720)$. Gate-Kapazität je Fenster $30 c / \bar s$.

**Vergleich über Tage.** Für Regel $A$ gegen die Referenz $B$ auf denselben Tagen $d = 1, \dots, D$ ist $\Delta_d = X_A^{(d)} - X_B^{(d)}$ die Differenz einer Kennzahl $X$ (negativ = besser); berichtet werden
Mittel, Median und die Anteile der Tage mit $\Delta_d < 0$, $= 0$, $> 0$. Ein Unterschied gilt als klar, wenn $|\bar\Delta| > 2\,\mathrm{SE}(\Delta)$ mit dem Standardfehler der gepaarten Differenz.

Implementiert in `gate_scenario.py` (Tag, Buchung), `gate_queue.py` (Schlange), `gate_evaluation.py` (Regeln, Stichprobe, Kurven, Urteil).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Hof- und Yard-Management optimieren](https://sebastianhanisch.net/yard-management-optimierung.html)."
)
