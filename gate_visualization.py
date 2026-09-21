"""Plotly-Figuren der Gate-Demo: Tag am Gate, Kapazitäts-, Quoten- und Spurenkurve, Verteilung, Vergleich.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Marker-Linien in mittlerem Grau, Überschriften stehen als Markdown ÜBER dem Diagramm. Plotly wird erst
in den Funktionen importiert, damit die reine Rechnung ohne Plotly testbar bleibt."""

import gate_constants as C
import gate_queue as Q

LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)
LANES_Y_MAX = 60.0                       # die Spurenkurve zeigt Wartezeiten bis hierher; was darüber liegt, läuft aus dem Bild (im Text gesagt)
DAY_START_HOUR = 6                       # Betriebsbeginn als Uhrzeit für die Achse (wie in der Terminvergabe-Demo)


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _vline(fig, x, text, **kw):
    fig.add_vline(x=x, line=dict(color=C.MARKER_LINE_COLOR, width=2, dash="dot"), annotation_text=text, annotation_position="top", annotation_font=dict(size=11), **kw)


def clock(minutes):
    """Minuten ab Betriebsbeginn als Uhrzeit."""
    total = int(round(minutes)) + DAY_START_HOUR * 60
    return f"{total // 60}:{total % 60:02d}"


# ---------------------------------------------------------------------------------------------------
# Der Tag am Gate
# ---------------------------------------------------------------------------------------------------
def day_title(label, m):
    """Zweizeiliger Titel: in halbbreiten Spalten ist eine Zeile zu lang und wird abgeschnitten."""
    return f"<b>{label}</b><br><sub>Wartezeit im Mittel {m.mean:.1f} min · 95 %: {m.p95:.0f} min</sub>"


def shared_day_ranges(traces, gate_capacity):
    """Gemeinsame obere Achsengrenzen für mehrere Tages-Diagramme, damit sie sich vergleichen lassen: (Ankünfte je Fenster, Wartezeit in min), mit etwas Luft."""
    arrivals = [gate_capacity]
    waits = [C.WAIT_LIMIT]
    for tr in traces:
        nb, nu, mw = Q.windows(tr)
        arrivals.append(max(b + u for b, u in zip(nb, nu)))
        waits.extend(w for w in mw if w is not None)
    return max(arrivals) * 1.1, max(waits) * 1.1


def day_figure(trace, gate_capacity, title, y_ranges=None):
    """Oben die Ankünfte je 30-min-Fenster (gestapelt: mit und ohne Termin) gegen die Gate-Kapazität, unten die mittlere Wartezeit der in diesem Fenster Angekommenen.
    `y_ranges` = (Ankünfte, Wartezeit) legt die oberen Achsengrenzen fest (siehe shared_day_ranges); ohne Angabe skaliert das Diagramm selbst."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    nb, nu, mw = Q.windows(trace)
    k = len(nb)
    xs = [DAY_START_HOUR + (j + 0.5) * C.SLOT_LEN / 60 for j in range(k)]
    labels = [f"{clock(j * C.SLOT_LEN)}-{clock((j + 1) * C.SLOT_LEN)}" for j in range(k)]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.56, 0.44], vertical_spacing=0.09)
    fig.add_trace(go.Bar(x=xs, y=nb, name="Ankünfte mit Termin", marker_color=C.BOOKED_COLOR, customdata=labels, hovertemplate="%{customdata}<br>%{y} mit Termin<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=xs, y=nu, name="Ankünfte ohne Termin", marker_color=C.UNBOOKED_COLOR, customdata=labels, hovertemplate="%{customdata}<br>%{y} ohne Termin<extra></extra>"), row=1, col=1)
    fig.add_hline(y=gate_capacity, line=dict(color=C.CAPACITY_COLOR, width=2, dash="dash"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[DAY_START_HOUR - 1], y=[None], mode="lines", name=f"Gate-Kapazität {gate_capacity:.0f} Lkw je 30 min", line=dict(color=C.CAPACITY_COLOR, width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=xs, y=mw, mode="lines+markers", name="mittlere Wartezeit", line=dict(color=C.RULE_COLORS[C.RULE_FREE], width=2), marker=dict(size=5), connectgaps=False,
                             customdata=labels, hovertemplate="%{customdata}<br>%{y:.1f} min Wartezeit<extra></extra>", showlegend=False), row=2, col=1)
    fig.add_hline(y=C.WAIT_LIMIT, line=dict(color=C.MARKER_LINE_COLOR, width=1.5, dash="dot"), row=2, col=1)
    fig.update_layout(title=dict(text=title, font=dict(size=14), x=0.02), template="plotly_white", barmode="stack", height=C.DAY_FIGURE_HEIGHT, hovermode="closest",
                      legend=dict(orientation="h", yanchor="top", y=-0.08, x=0, font=dict(size=10)), margin=dict(t=64, b=64, l=48, r=8))
    ticks = list(range(DAY_START_HOUR, DAY_START_HOUR + 13, 2))
    fig.update_xaxes(tickmode="array", tickvals=ticks, ticktext=[f"{h}:00" for h in ticks], range=[DAY_START_HOUR - 0.1, DAY_START_HOUR + 12.1], row=2, col=1)
    fig.update_yaxes(title_text="Lkw je 30 min", row=1, col=1)
    fig.update_yaxes(title_text="Wartezeit (min)", rangemode="tozero", row=2, col=1)
    if y_ranges is not None:
        fig.update_yaxes(range=[0, y_ranges[0]], row=1, col=1)
        fig.update_yaxes(range=[0, y_ranges[1]], row=2, col=1)
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Kurven
# ---------------------------------------------------------------------------------------------------
def cap_curve_figures(curve, current):
    """(Wartezeit, Verschiebung) über der Fensterkapazität: Wartezeit mit Terminsystem (Mittel und 95. Perzentil) gegen die freie Anfahrt; Verschiebung der Buchenden."""
    import plotly.graph_objects as go

    xs = list(curve.xs)
    fr, tm = curve.series["frei"], curve.series["termin"]
    wait = go.Figure()
    wait.add_trace(go.Scatter(x=xs, y=list(fr["mean"]), mode="lines", name="Freie Anfahrt (Mittel)", line=dict(color=C.RULE_COLORS[C.RULE_FREE], width=2, dash="dash"),
                              hovertemplate="Freie Anfahrt: %{y:.1f} min<extra></extra>"))
    wait.add_trace(go.Scatter(x=xs, y=list(tm["mean"]), mode="lines+markers", name="Terminsystem (Mittel)", line=dict(color=C.RULE_COLORS[C.RULE_SHARED], width=2.5), marker=dict(size=6),
                              hovertemplate="Fensterkapazität %{x} %<br>Mittel %{y:.1f} min<extra></extra>"))
    wait.add_trace(go.Scatter(x=xs, y=list(tm["p95"]), mode="lines+markers", name="Terminsystem (95 %)", line=dict(color=C.RULE_COLORS[C.RULE_SHARED], width=1.5, dash="dot"), marker=dict(size=5),
                              hovertemplate="Fensterkapazität %{x} %<br>95 %: %{y:.1f} min<extra></extra>"))
    wait.update_layout(template="plotly_white", height=C.CHART_HEIGHT, legend=LEGEND_BOTTOM, margin=dict(t=25, b=110), hovermode="closest", xaxis_title="Fensterkapazität (% der Gate-Kapazität)",
                       yaxis_title="Wartezeit (min)")
    wait.update_yaxes(rangemode="tozero")
    shift = go.Figure(go.Scatter(x=xs, y=list(tm["shift"]), mode="lines+markers", name="Verschiebung", line=dict(color=C.UNBOOKED_COLOR, width=2.5), marker=dict(size=6),
                                 text=[f"Fensterkapazität {x} %<br>{v:.1f} min Verschiebung<br>{n * 100:.1f} % der Buchenden ohne Fenster" for x, v, n in zip(xs, tm["shift"], tm["nofit_share"])],
                                 hovertemplate="%{text}<extra></extra>"))
    shift.update_layout(template="plotly_white", height=C.CHART_HEIGHT - 120, margin=dict(t=25, b=45), showlegend=False, hovermode="closest", xaxis_title="Fensterkapazität (% der Gate-Kapazität)",
                        yaxis_title="Verschiebung (min)")
    shift.update_yaxes(rangemode="tozero")
    for fig in (wait, shift):
        if current in xs:
            _vline(fig, current, "eingestellt")
    return _lock_axes(wait), _lock_axes(shift)


def share_curve_figure(curve, current):
    """Mittlere Wartezeit über der Buchungsquote: freie Anfahrt, Terminsystem (alle in einer Schlange) und beim Vorrang getrennt Termininhaber und Lkw ohne Termin."""
    import plotly.graph_objects as go

    xs = list(curve.xs)
    fr, tm, pr = curve.series["frei"], curve.series["termin"], curve.series["vorrang"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=list(fr["mean"]), mode="lines", name="Freie Anfahrt", line=dict(color=C.RULE_COLORS[C.RULE_FREE], width=2, dash="dash"), hovertemplate="Freie Anfahrt: %{y:.1f} min<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=list(tm["mean"]), mode="lines+markers", name="Terminsystem (alle)", line=dict(color=C.RULE_COLORS[C.RULE_SHARED], width=2.5), marker=dict(size=6),
                             hovertemplate="Quote %{x} %<br>alle in einer Schlange: %{y:.1f} min<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=list(pr["mean_booked"]), mode="lines+markers", name="Vorrang: mit Termin", line=dict(color=C.RULE_COLORS[C.RULE_PRIO], width=2.5), marker=dict(size=6),
                             connectgaps=False, hovertemplate="Quote %{x} %<br>Termininhaber: %{y:.1f} min<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=list(pr["mean_unbooked"]), mode="lines+markers", name="Vorrang: ohne Termin", line=dict(color=C.UNBOOKED_COLOR, width=2.5), marker=dict(size=6),
                             connectgaps=False, hovertemplate="Quote %{x} %<br>ohne Termin: %{y:.1f} min<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, legend=LEGEND_BOTTOM, margin=dict(t=25, b=130), hovermode="closest", xaxis_title="Buchungsquote (% der Lkw mit Termin)",
                      yaxis_title="mittlere Wartezeit (min)")
    fig.update_yaxes(rangemode="tozero")
    if current in xs:
        _vline(fig, current, "eingestellt")
    return _lock_axes(fig)


def lanes_curve_figure(curve, current):
    """95. Perzentil der Wartezeit über der Zahl der Spuren, freie Anfahrt gegen Terminsystem, mit der 15-Minuten-Grenze. Werte über LANES_Y_MAX laufen aus dem Bild."""
    import plotly.graph_objects as go

    xs = list(curve.xs)
    fig = go.Figure()
    for key, name in (("frei", "Freie Anfahrt"), ("termin", "Terminsystem")):
        color = C.RULE_COLORS[C.RULE_FREE if key == "frei" else C.RULE_SHARED]
        fig.add_trace(go.Scatter(x=xs, y=list(curve.series[key]["p95"]), mode="lines+markers", name=name, line=dict(color=color, width=2.5), marker=dict(size=6),
                                 hovertemplate=f"{name}<br>%{{x}} Spuren: 95 % warten höchstens %{{y:.1f}} min<extra></extra>"))
    fig.add_hline(y=C.WAIT_LIMIT, line=dict(color=C.CAPACITY_COLOR, width=1.5, dash="dash"), annotation_text=f"{C.WAIT_LIMIT:.0f} min", annotation_position="top right", annotation_font=dict(color=C.CAPACITY_COLOR))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT - 60, legend=LEGEND_BOTTOM, margin=dict(t=25, b=100), hovermode="closest", xaxis_title="Gate-Spuren",
                      yaxis_title="Wartezeit, die 95 % der Lkw nicht überschreiten (min)")
    fig.update_xaxes(tickmode="array", tickvals=xs)
    fig.update_yaxes(range=[0, LANES_Y_MAX])
    if current in xs:
        _vline(fig, current, "eingestellt")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Verteilung und Vergleich
# ---------------------------------------------------------------------------------------------------
def distribution_figure(dists, labels, reference_label, unit):
    """Je Zeile ein gestapelter Balken: Anteil der Tage mit weniger / gleicher / mehr (unit) als die Referenz."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for attr, name in (("better", f"weniger {unit} als {reference_label}"), ("equal", "gleich"), ("worse", f"mehr {unit} als {reference_label}")):
        shares = [getattr(d, attr) * 100 for d in dists]
        fig.add_trace(go.Bar(y=labels, x=shares, orientation="h", name=name, marker_color=C.OUTCOME_COLORS[attr], text=[f"{v:.0f} %" if v >= 6 else "" for v in shares], textposition="inside",
                             insidetextanchor="middle", hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.0f}} % der Tage<extra></extra>"))
    fig.update_layout(barmode="stack", template="plotly_white", height=150 + 70 * len(dists), legend=dict(LEGEND_BOTTOM, y=-0.45, traceorder="normal"), margin=dict(t=20, b=110, l=10),
                      xaxis_title="Anteil der Tage (%)")
    fig.update_xaxes(range=[0, 100])
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


def wait_bar_figure(outcomes):
    """Mittlere Wartezeit je Regel (ein Tag): alle Lkw, Lkw mit Termin und Lkw ohne Termin; wo es keine solche Lkw gibt, fehlt der Balken."""
    import plotly.graph_objects as go

    labels = [C.RULE_SHORT[o.key] for o in outcomes]
    fig = go.Figure()
    for name, attr, color in (("alle Lkw", "mean", "#2a6fb0"), ("mit Termin", "mean_booked", C.BOOKED_COLOR), ("ohne Termin", "mean_unbooked", C.UNBOOKED_COLOR)):
        ys = [getattr(o.m, attr) for o in outcomes]
        fig.add_trace(go.Bar(x=labels, y=ys, name=name, marker_color=[C.RULE_COLORS[o.key] for o in outcomes] if attr == "mean" else color,
                             text=[f"{v:.1f}" if v is not None else "" for v in ys], textposition="outside", hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y:.1f}} min<extra></extra>"))
    top = max([o.m.mean for o in outcomes] + [o.m.mean_unbooked or 0 for o in outcomes] + [o.m.mean_booked or 0 for o in outcomes] + [1])
    fig.update_layout(template="plotly_white", barmode="group", height=C.CHART_HEIGHT - 40, legend=LEGEND_BOTTOM, margin=dict(t=25, b=90), yaxis_title="mittlere Wartezeit (min)")
    fig.update_yaxes(range=[0, top * 1.2])
    return _lock_axes(fig)
