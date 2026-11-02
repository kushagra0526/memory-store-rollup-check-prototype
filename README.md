# Rollup check for team memory (MemStore-style)

**Unofficial prototype by Kushagra Pratap Singh. Not affiliated with Memory Store.**

## The problem
MemStore's homepage shows a real morning rollup ([mem.store](https://mem.store)). Its lines are claims people act on before standup: "Overdue since 25 August", "three days out", "unresolved since 10 August", "for you". The same rollup shows two stores disagreeing ("Diwank's store still holds the 26 August waitlist launch as set … where your notes hold the announcement"), and the site says teammates' agents can search "personal material you've recorded". The footer counts grounding ("16 memories from your store and 42 from teammates") but nothing checks each line.

## What I built
A pre-send check for one person's rollup. Each line cites memory ids; the check returns **SEND / FIX / HOLD** with line-level findings and a fix:

| Code | Catches |
|---|---|
| `SUPERSEDED` | line rests on a memory a newer one replaced (due date moved, item done) — names the newer memory |
| `DATE` | "overdue since X", "N days overdue/late/to go", "due on X", "N days on", "unresolved since X" recomputed from the newest memory and the rollup time |
| `STATUS` | says still open when the store says done, or the reverse |
| `OWNER` | "for you" item owned by someone else, or the wrong person named |
| `CONFLICT_HIDDEN` | stores disagree and the line states one side as fact (must cite both and say so) |
| `PERSONAL_LEAK` (HOLD) | another person's memory marked personal, or with personal content (health, pay, job search, family…) |
| `DELETED` (HOLD) | cites a memory its owner deleted |
| `CITE_MISSING / CITE_UNKNOWN / FUTURE_CITE` | no source, a source that does not exist, a source recorded after the rollup |

Your own personal memories in your own rollup are allowed.

## Demo (`python demo.py`)
```
line 0  DATE            says overdue since 24 August; due date is 25 August
line 1  SUPERSEDED      m02 (18 Aug) was replaced by m03 (25 Aug): scoring criteria moved to 29 August
line 2  SUPERSEDED      m04 (21 Aug) was replaced by m05 (26 Aug): WorkOS plan merged
line 3  CONFLICT_HIDDEN stores disagree on 'waitlist launch' (Bruno: 26 August launch as set vs Asha: hold until real users exist)
line 4  PERSONAL_LEAK   m08 from Chen's store is personal content ('interviewing with')
line 5  CITE_MISSING    line cites no memory
Verdict: HOLD
```
A "cites a memory that exists" check flags only line 5.

## Results (synthetic teams, known truth)
Generator: 4–7 people, 8–12 commitments (some moved, some done, teammates' notes), 2 decisions where two stores disagree, one personal memory per person (some marked, most not), deleted drafts. Correct rollup per person, then 0–3 planted mistakes of 14 kinds. Held-out uses different names, different phrasings ("slipped past its Aug 25 date", "late by three days", "past due since 2026-08-25", "two days to go") and new personal topics; it was committed to git before its first run.

| | dev (60 teams) | held-out (100 teams, first run) |
|---|---|---|
| planted mistakes caught | 379 / 379 | **609 / 610** |
| false flags on clean lines | 0 / 3,846 | **0 / 6,556** |
| bad rollups that would be sent | 0 / 221 | **0 / 363** |
| … by "every cite exists" check | 123 / 221 | 180 / 363 |
| clean rollups held | 0 / 101 | 0 / 187 |

Per-kind numbers are in `results/`. The held-out miss: "chemo appointments for my aunt" (personal, not marked, a word not in my list).

## Honest limits
- **Near-circular.** I wrote the generator, both phrase banks and the checker; held-out phrasings were written knowing how the parser reads dates. It shows the logic holds together, not accuracy on real rollups.
- Dev had one fix before the numbers above: a generator bug put a decision memory after the rollup time (28 false `FUTURE_CITE` flags, 3 hidden conflicts missed). The checker was not changed.
- Memories here are structured (topic, owner, due, status, value). Real memories are free text; topic grouping and value extraction would come from your pipeline.
- Personal content without the user's flag is a word list. It misses unseen words (the held-out miss). An owner-confirmed "personal" flag at `record` time is the real fix.
- "Owner's store wins" decides supersession; two non-owners disagreeing counts as a conflict.

## Run it (Python 3.10+, stdlib only)
```
python demo.py
python -m unittest discover -s tests -t .
python -m rollupcheck.evaluate heldout
```
