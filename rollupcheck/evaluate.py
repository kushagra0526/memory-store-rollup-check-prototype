"""Score the rollup check against planted mistakes. Usage: python -m rollupcheck.evaluate dev|heldout"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter

from .gen import EXPECT, mutate, rollup, world
from .memcheck import check, cite_exists_baseline

SEEDS = {"dev": range(0, 60), "heldout": range(5000, 5100)}


def run(split: str) -> dict:
    caught, missed, by_kind, false_flags = Counter(), Counter(), Counter(), Counter()
    clean_lines = bad_lines = 0
    rollups = {"clean": 0, "clean_flagged": 0, "bad": 0, "bad_sent": 0, "bad_sent_baseline": 0, "clean_flagged_baseline": 0}
    examples = []
    for seed in SEEDS[split]:
        w = world(seed, split)
        rng = random.Random(seed * 7 + 1)
        for person in w["team"]:
            lines, hooks = rollup(w, person, rng)
            truth = mutate(w, person, lines, hooks, rng, rng.choice([0, 0, 1, 1, 2, 3]))
            rep = check(person, w["now"], lines, w["mems"], w["team"])
            base_ok = cite_exists_baseline(lines, w["mems"])
            if truth:
                rollups["bad"] += 1
                rollups["bad_sent"] += rep.verdict == "SEND"
                rollups["bad_sent_baseline"] += base_ok
            else:
                rollups["clean"] += 1
                rollups["clean_flagged"] += rep.verdict != "SEND"
                rollups["clean_flagged_baseline"] += not base_ok
            codes = {}
            for f in rep.findings:
                codes.setdefault(f.line, set()).add(f.code)
            for i, ln in enumerate(lines):
                if i in truth:
                    bad_lines += 1
                    kind = truth[i]
                    by_kind[kind] += 1
                    if EXPECT[kind] in codes.get(i, set()):
                        caught[kind] += 1
                    else:
                        missed[kind] += 1
                        if len(examples) < 12:
                            examples.append({"kind": kind, "line": ln.text, "got": sorted(codes.get(i, []))})
                else:
                    clean_lines += 1
                    for c in codes.get(i, []):
                        false_flags[c] += 1
                        if len(examples) < 12:
                            examples.append({"false": c, "line": ln.text})
    return {"split": split, "bad_lines": bad_lines, "caught": sum(caught.values()),
            "by_kind": {k: f"{caught[k]}/{by_kind[k]}" for k in sorted(by_kind)},
            "clean_lines": clean_lines, "false_flags": dict(false_flags), "rollups": rollups, "examples": examples}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "dev"), indent=1, default=str))
