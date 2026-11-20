#!/usr/bin/env python3
"""Manual baseline for the business case: time a person preparing the same handler brief.

Protocol (docs/business-case.md, "A benchmark the jury can repeat"):
  - Preparer: a teammate who has NOT seen the agent's brief. Handler: a second teammate.
  - Same input text and the same finish line as the agent: the handler can open a brief with
    the reported fact, timeline, evidence and a pending human decision, with no invented person
    or conclusion.
  - The timer starts when the text is shown and stops when the handler confirms the brief.

Run in a terminal (standard library only):
  python3 tests/manual_benchmark.py

Writes evidence/manual_benchmark_<timestamp>.json and prints the comparison with the agent's
live traces (evidence/live_trace_*.json). Synthetic text only.
"""
import json
import time
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
REPORT = "Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries."
CHECKS = [
    ("fact", "Does the brief state the reported discrepancy between the invoice totals?"),
    ("timeline", "Does it give Monday as the timeline?"),
    ("evidence", "Does it name the ledger entries as evidence?"),
    ("decision", "Is the human decision marked as pending (nothing decided, no person or conclusion invented)?"),
]


def ask(prompt):
    return input(prompt).strip()


print(__doc__.split("Run in a terminal")[0])
preparer = ask("Preparer's first name or initials: ")
handler = ask("Handler's first name or initials: ")
ask("\nHandler: press Enter to release the report to the preparer and START the timer. ")
start = time.perf_counter()
print(f"\n--- REPORT (synthetic) ---\n{REPORT}\n")
print("Preparer: fill in the restricted case form. Press Enter after each field.\n")
brief = {
    "facts": ask("Reported fact(s): "),
    "timeline": ask("Timeline: "),
    "evidence": ask("Evidence: "),
    "decision": ask("Human decision status: "),
}
prepared = time.perf_counter() - start
print("\n--- BRIEF AS THE HANDLER SEES IT ---")
for k, v in brief.items():
    print(f"{k:9}: {v}")
print("\nHandler: check the brief. Answer y or n.")
checks, corrections = {}, []
for key, question in CHECKS:
    while True:
        answer = ask(f"  {question} ").lower()
        if answer in ("y", "n"):
            break
    checks[key] = answer == "y"
    while not checks[key]:
        fix = ask(f"  Preparer: correct the {key} field now (the clock keeps running): ")
        brief["facts" if key == "fact" else key] = fix
        corrections.append(key)
        checks[key] = ask("  Handler: correct now? (y/n) ").lower() == "y"
ask("\nHandler: press Enter when you can open and act on the brief. This STOPS the timer. ")
elapsed = time.perf_counter() - start

agent = []
for f in sorted((ROOT / "evidence").glob("live_trace_*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("four_fields_present"):
        agent.append({"file": f.name, "seconds": d["seconds_until_handler_can_open_brief"]})

result = {
    "protocol": "docs/business-case.md: same text, same four checks, timer from release to handler access",
    "input": REPORT,
    "preparer": preparer, "handler": handler,
    "seconds_to_first_draft": round(prepared, 1),
    "seconds_until_handler_can_open_brief": round(elapsed, 1),
    "brief": brief, "checks": checks, "corrections": corrections,
    "all_four_fields_correct": all(checks.values()),
    "agent_live_runs": agent,
}
out = ROOT / "evidence" / f"manual_benchmark_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\nManual: {elapsed:.1f} s until the handler could open the brief "
      f"({'all four fields correct' if result['all_four_fields_correct'] else 'NOT all fields correct'}, "
      f"{len(corrections)} correction(s)).")
if agent:
    secs = [a["seconds"] for a in agent]
    print(f"Agent (live BRANE, n={len(secs)}): {min(secs):.1f}–{max(secs):.1f} s, same finish line.")
    agent_median = median(secs)
    print(f"Measured difference: manual {elapsed:.1f} s vs agent median {agent_median:.1f} s "
          f"= {elapsed / agent_median:.1f}× the agent's time (one manual run, synthetic report).")
print(f"Saved {out.relative_to(ROOT)}. Run it once per preparer to increase n.")
