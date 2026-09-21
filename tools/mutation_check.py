"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prüft, ob die Tests (ohne AppTests) sie finden.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/mutation_check.py [Teilstring des Dateinamens]
Jeder Mutant ersetzt genau eine Stelle; Überlebende sind entweder gleichwertig (kein sichtbarer Unterschied) oder eine Lücke der Tests. Die Kopie liegt in einem temporären Ordner;
PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Überlebenden vortäuscht; Quelltexte als LF (Windows-Python schreibt sonst CRLF und die Zeichenketten unten finden nichts).
Ein Mutant kann in eine Endlosschleife laufen; nach TIMEOUT Sekunden gilt er als gefunden."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
TIMEOUT = 240                      # Sekunden je Mutant; Endlosschleifen zählen als gefunden

MUTANTS = [
    # gate_scenario.py
    ("gate_scenario.py", "if not 0 <= peak_pct <= 100:", "if not 0 <= peak_pct < 100:"),
    ("gate_scenario.py", "if n_trucks < 1:", "if n_trucks < 0:"),
    ("gate_scenario.py", "if service_mean <= 0:", "if service_mean < 0:"),
    ("gate_scenario.py", "share = peak_pct / 100", "share = peak_pct / 10"),
    ("gate_scenario.py", "mu = math.log(service_mean) - s2 / 2", "mu = math.log(service_mean) + s2 / 2"),
    ("gate_scenario.py", "return max(1, int(cap_pct / 100 * lanes * C.SLOT_LEN / service))", "return max(0, int(cap_pct / 100 * lanes * C.SLOT_LEN / service))"),
    ("gate_scenario.py", "return lanes * C.SLOT_LEN / service", "return lanes * C.SLOT_LEN * service"),
    ("gate_scenario.py", "return min(int(pref // C.SLOT_LEN), n_slots() - 1)", "return int(pref // C.SLOT_LEN)"),
    ("gate_scenario.py", "if not day.booker[i] < share:", "if day.booker[i] < share:"),
    ("gate_scenario.py", "for j in ((j0 - d, j0 + d) if d else (j0,)):", "for j in ((j0 + d, j0 - d) if d else (j0,)):"),
    ("gate_scenario.py", "if 0 <= j < k and used[j] < cap:", "if 0 <= j < k and used[j] <= cap:"),
    ("gate_scenario.py", "        if not placed:\n            nofit += 1", "        if not placed:\n            nofit += 2"),
    ("gate_scenario.py", "return [max(0.0, day.pref[i] + sigma * day.noise[i]) for i in range(day.n)]", "return [max(0.0, day.pref[i] - sigma * day.noise[i]) for i in range(day.n)]"),
    ("gate_scenario.py", "slot[i] * C.SLOT_LEN + day.within[i] * C.SLOT_LEN + sigma", "slot[i] * C.SLOT_LEN + sigma"),
    ("gate_scenario.py", "moved = [abs(slot[i] - wish_slot(day.pref[i])) * C.SLOT_LEN", "moved = [(slot[i] - wish_slot(day.pref[i])) * C.SLOT_LEN"),
    ("gate_scenario.py", "return sum(moved) / len(moved) if moved else 0.0", "return sum(moved) / len(moved) if moved else 1.0"),
    ("gate_scenario.py", "return int(math.ceil(C.DAY_MINUTES / C.SLOT_LEN))", "return int(math.ceil(C.DAY_MINUTES / C.SLOT_LEN)) + 1"),
    ("gate_scenario.py", "    if n_trucks < 1:\n        raise ValueError(\"Mindestens", "    if n_trucks < 2:\n        raise ValueError(\"Mindestens"),
    # gate_queue.py
    ("gate_queue.py", "return s[min(len(s) - 1, int(0.95 * len(s)))]", "return s[min(len(s) - 1, int(0.9 * len(s)))]"),
    ("gate_queue.py", "        start = max(t, arrive[i])\n        waits[i] = start - arrive[i]", "        start = t\n        waits[i] = start - arrive[i]"),
    ("gate_queue.py", "a, i = heapq.heappop(heap_b) if heap_b else heapq.heappop(heap_w)", "a, i = heapq.heappop(heap_w) if heap_w else heapq.heappop(heap_b)"),
    ("gate_queue.py", "if not heap_b and not heap_w:", "if not heap_b:"),
    ("gate_queue.py", "over_limit=sum(1 for w in waits if w > C.WAIT_LIMIT) / n", "over_limit=sum(1 for w in waits if w >= C.WAIT_LIMIT) / n"),
    ("gate_queue.py", "util=sum(service) / (lanes * C.DAY_MINUTES)", "util=sum(service) / lanes"),
    ("gate_queue.py", "booked_share=len(wb) / n", "booked_share=len(wu) / n"),
    ("gate_queue.py", "nofit_share=nofit / n", "nofit_share=nofit"),
    ("gate_queue.py", "(nb if b else nu)[j] += 1", "(nu if b else nb)[j] += 1"),
    ("gate_queue.py", "if nb[j] + nu[j] else None for j in range(k)]", "if nb[j] + nu[j] else 0.0 for j in range(k)]"),
    ("gate_queue.py", "mean=sum(waits) / n, p95=percentile95(waits)", "mean=sum(waits) / n, p95=max(waits)"),
    ("gate_queue.py", "heapq.heappush(free, start + service[i])", "heapq.heappush(free, arrive[i] + service[i])"),
    ("gate_queue.py", "heapq.heappush(free, t + service[i])", "heapq.heappush(free, a + service[i])"),
    # gate_evaluation.py
    ("gate_evaluation.py", "return p.trucks * p.service / (p.lanes * C.DAY_MINUTES)", "return p.trucks * p.service / C.DAY_MINUTES"),
    ("gate_evaluation.py", "S.book_slots(day, cap_of(p), p.share_pct)\n    arrive = S.appointment_arrivals(day, p.sigma, slot)\n    booked", "S.book_slots(day, p.cap_pct, p.share_pct)\n    arrive = S.appointment_arrivals(day, p.sigma, slot)\n    booked"),
    ("gate_evaluation.py", "(C.RULE_PRIO, Q.waits_priority(arrive, day.service, booked, p.lanes))", "(C.RULE_PRIO, Q.waits_fifo(arrive, day.service, p.lanes))"),
    ("gate_evaluation.py", "    shift = S.shift_minutes(day, slot)\n    for key, waits in", "    shift = 0.0\n    for key, waits in"),
    ("gate_evaluation.py", "out.append(a - b)", "out.append(b - a)"),
    ("gate_evaluation.py", "sum(1 for x in d if x < -1e-9)", "sum(1 for x in d if x < 1e-9)"),
    ("gate_evaluation.py", "-statistics.median(d)", "statistics.median(d)"),
    ("gate_evaluation.py", "abs(diff) <= C.VERDICT_Z * se", "abs(diff) < C.VERDICT_Z * se"),
    ("gate_evaluation.py", "        kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else (\"better\" if diff < 0 else \"worse\")", "        kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else (\"better\" if diff > 0 else \"worse\")"),
    ("gate_evaluation.py", "kind = \"unclear\" if diff == 0 else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if diff == 1 else (\"better\" if diff < 0 else \"worse\")"),
    ("gate_evaluation.py", "100.0 * diff / ref if ref else None", "10.0 * diff / ref if ref else None"),
    ("gate_evaluation.py", "S.book_slots(day, S.window_capacity(p.lanes, p.service, c), p.share_pct)", "S.book_slots(day, S.window_capacity(p.lanes, p.service, p.cap_pct), p.share_pct)"),
    ("gate_evaluation.py", "slot, nofit = S.book_slots(day, cap, q)", "slot, nofit = S.book_slots(day, cap, p.share_pct)"),
    ("gate_evaluation.py", "S.book_slots(day, cap_of(q), q.share_pct)", "S.book_slots(day, cap_of(p), q.share_pct)"),
    ("gate_evaluation.py", "if v is not None and v <= limit:", "if v is not None and v < limit:"),
    ("gate_evaluation.py", "if fr.mean < C.CALM_FREE_MEAN:", "if fr.mean <= C.CALM_FREE_MEAN:"),
    ("gate_evaluation.py", "elif sh.nofit_share > C.OVERLOAD_NOFIT:", "elif sh.nofit_share >= C.OVERLOAD_NOFIT:"),
    ("gate_evaluation.py", "ratio > C.LITTLE_EFFECT and p.share_pct < C.FULL_SHARE:", "ratio > C.LITTLE_EFFECT and p.share_pct <= C.FULL_SHARE:"),
    ("gate_evaluation.py", "    elif ratio is not None and ratio > C.LITTLE_EFFECT:\n        kind = \"wide\"", "    elif ratio is not None and ratio >= C.LITTLE_EFFECT:\n        kind = \"wide\""),
    ("gate_evaluation.py", "s = f\"Nur {p.share_pct} % buchen", "s = f\"Nur {p.cap_pct} % buchen"),
    ("gate_evaluation.py", "ratio = sh.mean / fr.mean if fr.mean else None", "ratio = fr.mean / sh.mean if sh.mean else None"),
    ("gate_evaluation.py", "return DayRow(seed, {o.key: o.m for o in run_rules(p, make_day(p, seed))})", "return DayRow(seed, {o.key: o.m for o in run_rules(p, make_day(p, seed + 1))})"),
    # gate_stories.py
    ("gate_stories.py", "(fr <= 1.0,", "(fr < 1.0,"),
    ("gate_stories.py", "(abs(sh - fr) <= 1.0,", "(abs(sh - fr) < 1.0,"),
    ("gate_stories.py", "(shift <= 1.0,", "(shift < 1.0,"),
    ("gate_stories.py", "(fr >= 8.0,", "(fr > 8.0,"),
    ("gate_stories.py", "(sh <= 0.25 * fr, f\"Terminsystem <= 25 % davon: {sh:.1f}\"),\n                (shift <= 15.0", "(sh < 0.25 * fr, f\"Terminsystem <= 25 % davon: {sh:.1f}\"),\n                (shift <= 15.0"),
    ("gate_stories.py", "(shift <= 15.0,", "(shift < 15.0,"),
    ("gate_stories.py", "(sh >= 0.8 * fr,", "(sh > 0.8 * fr,"),
    ("gate_stories.py", "booked is not None and booked <= 2.0", "booked is not None and booked < 2.0"),
    ("gate_stories.py", "unbooked is not None and unbooked >= 15.0", "unbooked is not None and unbooked > 15.0"),
    ("gate_stories.py", "(abs(pr - sh) <= 0.05 * sh,", "(abs(pr - sh) < 0.05 * sh,"),
    ("gate_stories.py", "(sh >= 0.6 * fr,", "(sh > 0.6 * fr,"),
    ("gate_stories.py", "(shift <= 3.0,", "(shift < 3.0,"),
    ("gate_stories.py", "(fr >= 20.0,", "(fr > 20.0,"),
    ("gate_stories.py", "(shift >= 12.0,", "(shift > 12.0,"),
    ("gate_stories.py", "return all(ok for ok, _ in criteria(name, (row,)))", "return any(ok for ok, _ in criteria(name, (row,)))"),
    # gate_visualization.py
    ("gate_visualization.py", "xs = [DAY_START_HOUR + (j + 0.5) * C.SLOT_LEN / 60 for j in range(k)]", "xs = [DAY_START_HOUR + j * C.SLOT_LEN / 60 for j in range(k)]"),
    ("gate_visualization.py", "template=\"plotly_white\", barmode=\"stack\"", "template=\"plotly_white\", barmode=\"group\""),
    ("gate_visualization.py", "fig.add_hline(y=gate_capacity,", "fig.add_hline(y=gate_capacity + 1,"),
    ("gate_visualization.py", "total = int(round(minutes)) + DAY_START_HOUR * 60", "total = int(round(minutes))"),
    ("gate_visualization.py", "fig.update_yaxes(range=[0, LANES_Y_MAX])", "fig.update_yaxes(range=[0, LANES_Y_MAX + 10])"),
    ("gate_visualization.py", "top = max([o.m.mean for o in outcomes]", "top = min([o.m.mean for o in outcomes]"),
    ("gate_visualization.py", "for attr, name in ((\"better\", f\"weniger {unit} als {reference_label}\")", "for attr, name in ((\"worse\", f\"weniger {unit} als {reference_label}\")"),
    ("gate_visualization.py", "text=[f\"{v:.0f} %\" if v >= 6 else \"\" for v in shares]", "text=[f\"{v:.0f} %\" if v >= 0 else \"\" for v in shares]"),
    ("gate_visualization.py", "marker_color=[C.RULE_COLORS[o.key] for o in outcomes] if attr == \"mean\" else color", "marker_color=color"),
    # gate_pdf_export.py
    ("gate_pdf_export.py", "amount = f\"{abs(v.pct):.0f} % weniger\"", "amount = f\"{v.pct:.0f} % weniger\""),
    ("gate_pdf_export.py", "\"-\" if o.key == FR else f\"{m.shift:.1f}\", f\"{m.booked_share * 100:.0f}\"", "f\"{m.shift:.1f}\", f\"{m.booked_share * 100:.0f}\""),
    ("gate_pdf_export.py", "gate_cap = p.lanes * C.SLOT_LEN / p.service", "gate_cap = p.lanes * C.SLOT_LEN * p.service"),
    ("gate_pdf_export.py", "if E.values(sample, key, field) and E.values(sample, ref, field):", "if E.values(sample, key, field) or E.values(sample, ref, field):"),
    ("gate_pdf_export.py", "\"σ\": \"sigma\", ", ""),
    # gate_presets.py
    ("gate_presets.py", "value = spec.lo + round((value - spec.lo) / spec.step) * spec.step", "value = spec.lo + int((value - spec.lo) / spec.step) * spec.step"),
    ("gate_presets.py", "        value = min(spec.hi, value)\n    if spec.step", "        value = min(spec.hi, value + 1)\n    if spec.step"),
    # gate_constants.py
    ("gate_constants.py", "VERDICT_Z = 2.0", "VERDICT_Z = 1.0"),
    ("gate_constants.py", "VERDICT_Z = 2.0", "VERDICT_Z = 3.0"),
    ("gate_constants.py", "CALM_FREE_MEAN = 1.0", "CALM_FREE_MEAN = 2.0"),
    ("gate_constants.py", "OVERLOAD_NOFIT = 0.02", "OVERLOAD_NOFIT = 0.05"),
    ("gate_constants.py", "LITTLE_EFFECT = 0.7", "LITTLE_EFFECT = 0.8"),
    ("gate_constants.py", "FULL_SHARE = 90", "FULL_SHARE = 80"),
    ("gate_constants.py", "PEAK_POSITIONS = (0.25, 0.70)", "PEAK_POSITIONS = (0.25, 0.75)"),
    ("gate_constants.py", "SERVICE_CV = 0.6", "SERVICE_CV = 0.5"),
    ("gate_constants.py", "WAIT_LIMIT = 15.0", "WAIT_LIMIT = 20.0"),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gate_mut_"))
    for f in ROOT.glob("*.py"):
        shutil.copy(f, tmp / f.name)
    shutil.copytree(ROOT / "tests", tmp / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    for f in tmp.glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    survivors, errors, killed = [], [], 0
    for n, (name, old, new) in enumerate(MUTANTS, 1):
        if only and only not in name:
            continue
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        if original.count(old) != 1:
            errors.append((n, name, old[:60], original.count(old)))
            continue
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_app.py"], cwd=tmp, env=env, capture_output=True, text=True, timeout=TIMEOUT)
            survived = r.returncode == 0
        except subprocess.TimeoutExpired:
            survived = False                    # Endlosschleife: das gilt als gefunden
            print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
        path.write_bytes(original.encode("utf-8"))
        if survived:
            survivors.append((n, name, old[:70], new[:70]))
            print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:60]!r} -> {new[:60]!r}", flush=True)
        else:
            killed += 1
            print(f"[{n:3d}] gefunden  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} überlebt, {len(errors)} Fehler in der Mutantenliste")
    for e in errors:
        print("  FEHLER (Stelle nicht eindeutig gefunden):", e)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
