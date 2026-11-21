"""Estimate how long tests/manual_benchmark.py takes two people. A SIMULATION, not a measurement.

Run: python3 scripts/estimate_manual_baseline.py  (writes evidence/manual_baseline_estimate.json)
A timed run with two teammates (tests/manual_benchmark.py) replaces this estimate.

Sources for the parameters:
- Typing (transcription): Dhakal et al., CHI 2018, 136M keystrokes from 168,000 people:
  mean 51.6 wpm, SD 20.2 wpm (1 word = 5 characters).
- Composing your own text is slower than copying: Karat et al., CHI 1999 measured about
  0.55-0.6x transcription speed for composition.
- Reading: Brysbaert, J. Memory & Language 2019: silent reading of English non-fiction
  238 wpm on average (range about 175-300); reading to act on it is slower, modelled at 0.7x.
- Mental preparation before each action: Keystroke-Level Model, Card, Moran & Newell 1983,
  M = 1.35 s; a key press K about 0.28 s for an average typist.
"""
import random
import statistics

REPORT_WORDS = 15            # "Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries."
INSTRUCTION_WORDS = 14       # "Preparer: fill in the restricted case form. Press Enter after each field."
FIELDS = {                   # plausible answers, in characters (min, max)
    "facts": (25, 60),       # "Two invoice totals differ (same supplier invoice)"
    "timeline": (6, 25),     # "Monday" / "Discrepancy appeared on Monday"
    "evidence": (12, 35),    # "Ledger (both entries)"
    "decision": (7, 35),     # "Pending" / "Pending: awaiting handler decision"
}
FIELD_PROMPT_WORDS = 3
BRIEF_WORDS = 30             # the brief as printed for the handler
CHECK_WORDS = [12, 7, 9, 15] # the four y/n questions
M, K = 1.35, 0.28


def run(rng):
    wpm_type = max(15, rng.gauss(51.6, 20.2))
    compose_cps = wpm_type * 5 / 60 * rng.uniform(0.5, 0.65)
    read_wps = max(150, min(320, rng.gauss(238, 35))) / 60 * 0.7
    handover = rng.uniform(2, 5)                      # keyboard passes from handler to preparer
    t = handover + (REPORT_WORDS + INSTRUCTION_WORDS) / read_wps
    for lo, hi in FIELDS.values():
        chars = rng.randint(lo, hi)
        t += FIELD_PROMPT_WORDS / read_wps + M + rng.uniform(1, 4)   # read prompt, decide what to write
        t += chars / compose_cps + K                                  # type it, press Enter
    draft = t
    t += rng.uniform(2, 5)                                            # keyboard back to the handler
    t += BRIEF_WORDS / read_wps
    for words in CHECK_WORDS:
        t += words / read_wps + M + 2 * K                             # read question, decide, "y" + Enter
    # About 1 in 4 runs has one field the handler rejects (usually the decision field gets a
    # conclusion, or the timeline is missing): explain, preparer retypes, handler re-checks.
    if rng.random() < 0.25:
        t += rng.uniform(5, 12) + rng.randint(10, 35) / compose_cps + M + 2 * K + rng.uniform(2, 5)
    t += M + K                                                        # final Enter stops the timer
    return draft, t


rng = random.Random(21)
runs = [run(rng) for _ in range(10_000)]
totals = sorted(t for _, t in runs)
drafts = sorted(d for d, _ in runs)
q = lambda xs, p: xs[int(p * (len(xs) - 1))]
agent = [7.62, 6.33, 7.16, 6.22]   # evidence/live_trace_20261120-*.json, seconds until the handler can open the brief
result = {
    "type": "SIMULATION, not a measurement: no person was timed",
    "method": "Monte Carlo, 10,000 runs, seed 21; parameters and sources in scripts/estimate_manual_baseline.py",
    "input": "Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries.",
    "finish_line": "same as tests/manual_benchmark.py: handler can open a brief with fact, timeline, evidence, pending decision",
    "first_draft_seconds": {"median": round(statistics.median(drafts)), "p05": round(q(drafts, .05)), "p95": round(q(drafts, .95))},
    "handler_can_open_brief_seconds": {"median": round(statistics.median(totals)), "p05": round(q(totals, .05)), "p95": round(q(totals, .95))},
    "agent_live_seconds": {"n": len(agent), "min": min(agent), "max": max(agent), "median": round(statistics.median(agent), 2)},
    "ratio_at_median": round(statistics.median(totals) / statistics.median(agent), 1),
}
from pathlib import Path
import json
out = Path(__file__).resolve().parent.parent / "evidence" / "manual_baseline_estimate.json"
out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
h = result["handler_can_open_brief_seconds"]
print(f"Estimated by hand: median {h['median']} s ({h['median']/60:.1f} min), 90% of runs {h['p05']}-{h['p95']} s "
      f"({h['p05']/60:.1f}-{h['p95']/60:.1f} min). Agent: {min(agent)}-{max(agent)} s. "
      f"About {result['ratio_at_median']}x at the median. Wrote {out.name}.")
