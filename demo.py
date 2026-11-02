"""One morning rollup, checked before it is sent. Usage: python demo.py"""
from datetime import date, datetime

from rollupcheck.memcheck import Line, Memory, check

NOW = datetime(2026, 8, 27, 7, 0)
TEAM = ["Asha", "Bruno", "Chen"]


def m(id, store, when, topic, **kw):
    kw.setdefault("kind", "note")
    kw.setdefault("text", topic)
    return Memory(id=id, store=store, at=datetime(2026, 8, *when), topic=topic, **kw)


MEMS = {x.id: x for x in [
    m("m01", "Asha", (20, 10), "round details to the investor", kind="commitment", owner="Asha",
      due=date(2026, 8, 25), status="open", text="Asha sends round details by 25 August"),
    m("m02", "Bruno", (18, 9), "scoring criteria", kind="commitment", owner="Bruno",
      due=date(2026, 8, 24), status="open", text="Bruno writes scoring criteria by 24 August"),
    m("m03", "Bruno", (25, 16), "scoring criteria", kind="commitment", owner="Bruno",
      due=date(2026, 8, 29), status="open", supersedes="m02", text="scoring criteria moved to 29 August"),
    m("m04", "Chen", (21, 11), "WorkOS org-support plan", kind="commitment", owner="Chen",
      due=date(2026, 8, 26), status="open", text="Chen ships WorkOS plan by 26 August"),
    m("m05", "Chen", (26, 18), "WorkOS org-support plan", kind="status", owner="Chen",
      due=date(2026, 8, 26), status="done", supersedes="m04", text="WorkOS plan merged"),
    m("m06", "Bruno", (24, 9), "waitlist launch", kind="decision", value="26 August launch as set",
      text="waitlist launch stays 26 August"),
    m("m07", "Asha", (25, 20), "waitlist launch", kind="decision", value="hold until real users exist",
      text="hold the announcement until real users exist"),
    m("m08", "Chen", (25, 8), "personal:Chen", text="interviewing with another startup next week"),
]}

ROLLUP = [
    Line("for_you", "**Round details to the investor.** Overdue since 24 August; still unsent.", ["m01"]),
    Line("for_others", "Bruno, on scoring criteria: overdue since 24 August.", ["m02"]),
    Line("for_others", "Chen still owes the WorkOS org-support plan, 1 day overdue.", ["m04"]),
    Line("other_updates", "The waitlist launch is set for 26 August.", ["m06"]),
    Line("other_updates", "Chen noted: interviewing with another startup next week.", ["m08"]),
    Line("for_you", "Fathom integration ownership is unowned.", []),
]

if __name__ == "__main__":
    print(f"Rollup for Asha, {NOW:%d %b %Y %H:%M}\n")
    for i, ln in enumerate(ROLLUP):
        print(f"  [{i}] ({ln.section}) {ln.text}   cites {ln.cites or '-'}")
    rep = check("Asha", NOW, ROLLUP, MEMS, TEAM)
    print(f"\nVerdict: {rep.verdict}\n")
    for f in rep.findings:
        print(f"  line {f.line}  {f.code:<15} {f.detail}" + (f"\n{'':24}fix: {f.fix}" if f.fix else ""))
    print("\nA 'cites a memory that exists' check would flag only line 5.")
