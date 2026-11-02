"""Synthetic team memory stores + rollups with planted mistakes (known truth)."""
from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from .memcheck import Line, Memory, fmt

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]

BANKS = {
    "dev": {
        "names": ["Asha", "Bruno", "Chen", "Dara", "Emeka", "Farah", "Goran", "Hana"],
        "overdue": ["**{title}.** Overdue since {due}; still open in {owner}'s store.",
                    "{title}: {n} days overdue, owner {owner}."],
        "others": ["{owner}, on {title}: overdue since {due}.",
                   "{owner} owes {title}, {n} days overdue."],
        "due": ["{title} is due in {n} days.", "{title}: {n} days out.", "{title} is due {due}."],
        "done": ["{owner} finished {title}.", "{title} is done ({owner})."],
        "quiet": ["{title} has been quiet: {n} days on with no new memory."],
        "conflict": ["{a}'s store has {title} as {va}, where {b}'s notes hold {vb}."],
        "personal_own": ["You noted: {text}"],
        "personal_other": ["{store} noted: {text}"],
        "personal": [("dentist appointment Thursday morning", False), ("salary review with the CEO next week", False),
                     ("my partner's visa renewal is stuck", False), ("taking Friday off, family stuff", True),
                     ("interviewing with another startup", False), ("therapy moved to Tuesdays", False)],
    },
    "heldout": {
        "names": ["Ines", "Jonas", "Kofi", "Lena", "Mateo", "Noor", "Oskar", "Priya", "Quinn"],
        "overdue": ["{title} slipped past its {due_us} date and is still open.",
                    "{title} is late by {nw} days ({owner}).",
                    "{title} has been past due since {due_iso}."],
        "others": ["{owner} still hasn't closed {title}; it's {nw} days late.",
                   "Waiting on {owner} for {title}, overdue since {due_us}."],
        "due": ["{title}: {nw} days to go.", "{title} is due on {due_us}.", "{title} — {n} days away."],
        "done": ["{owner} wrapped up {title}.", "{title} landed ({owner})."],
        "quiet": ["{title} stalled: {nw} days without a new memory."],
        "conflict": ["{title} differs by store: {a} says {va}, while {b} says {vb}."],
        "personal_own": ["Your own note: {text}"],
        "personal_other": ["From {store}: {text}"],
        "personal": [("doctor said to rest my back", False), ("my mom is in hospital this week", False),
                     ("negotiating a raise before the round", False), ("off Monday for a wedding", False),
                     ("landlord dispute eating my evenings", False), ("chemo appointments for my aunt", False),
                     ("note to self, keep private", True)],
    },
}

TITLES = ["scoring criteria for the eval window", "login instructions to the beta user", "round details to the investor",
          "WorkOS org-support plan", "Fathom integration owner", "EC2 cost review", "launch tracker canvas",
          "pricing page copy", "SOC 2 vendor questionnaire", "rollup latency fix", "Slack importer spec",
          "onboarding email sequence", "MCP auth refresh", "customer research notes", "GitHub PR integration",
          "retention dashboard", "deletion API design", "Claude importer dedupe", "on-call rota", "Q4 roadmap draft"]
VALUES = [("26 August launch as set", "hold until real users exist"), ("ship Tuesday", "ship after the audit"),
          ("Postgres for rollups", "keep rollups in S3"), ("public beta", "invite-only beta"),
          ("weekly digest", "daily digest")]

EXPECT = {"stale_due": "SUPERSEDED", "stale_done": "SUPERSEDED", "wrong_date": "DATE", "wrong_days": "DATE",
          "early_overdue": "DATE", "owner_for_you": "OWNER", "owner_named": "OWNER", "personal_leak": "PERSONAL_LEAK",
          "deleted": "DELETED", "hidden_conflict": "CONFLICT_HIDDEN", "no_cite": "CITE_MISSING",
          "ghost_cite": "CITE_UNKNOWN", "future_cite": "FUTURE_CITE", "wrong_quiet": "DATE"}


def _phr(rng, bank, key, must=None, **kw):
    n = kw.get("n")
    if n is not None:
        kw.setdefault("nw", WORDS[n] if 0 <= n < len(WORDS) else str(n))
    d = kw.get("due_d")
    if d is not None:
        kw.setdefault("due", fmt(d))
        kw.setdefault("due_us", f"{d.strftime('%b')} {d.day}")
        kw.setdefault("due_iso", d.isoformat())
    pool = [x for x in bank[key] if must is None or any(m in x for m in must)]
    return rng.choice(pool).format(**kw)


def _auth(t):
    return [m for m in t["mems"] if m.kind != "note"][-1]


def world(seed: int, bank_name: str = "dev"):
    rng = random.Random(seed)
    bank = BANKS[bank_name]
    team = rng.sample(bank["names"], rng.randint(4, min(7, len(bank["names"]))))
    now = datetime.combine(datetime(2026, 9, 1).date() + timedelta(days=rng.randint(0, 50)), time(7, 0))
    today = now.date()
    mems: dict[str, Memory] = {}
    ids = iter(range(1, 10_000))

    def add(**kw) -> Memory:
        m = Memory(id=f"m{next(ids):04d}", **kw)
        mems[m.id] = m
        return m

    topics = []
    for title in rng.sample(TITLES, rng.randint(8, 12)):
        owner = rng.choice(team)
        t0 = now - timedelta(days=rng.randint(3, 20), hours=rng.randint(1, 10))
        due = t0.date() + timedelta(days=rng.randint(1, 14))
        if due == today:
            due += timedelta(days=1)
        c = add(store=owner, at=t0, topic=title, kind="commitment", text=f"{owner} commits to {title} by {fmt(due)}",
                owner=owner, due=due, status="open")
        info = {"title": title, "owner": owner, "mems": [c], "kind": "commitment"}
        r = rng.random()
        if r < 0.25:
            t1 = t0 + (now - t0) * rng.uniform(0.3, 0.9)
            new_due = due + timedelta(days=rng.randint(2, 7))
            info["mems"].append(add(store=owner, at=t1, topic=title, kind="commitment", text=f"{title} moved to {fmt(new_due)}",
                                    owner=owner, due=new_due, status="open", supersedes=c.id))
            info["moved"] = c
        elif r < 0.5:
            t1 = now - timedelta(hours=rng.randint(2, 60))
            info["mems"].append(add(store=owner, at=t1, topic=title, kind="status", text=f"{title} done",
                                    owner=owner, due=due, status="done", supersedes=c.id))
        if rng.random() < 0.3:
            other = rng.choice([p for p in team if p != owner])
            info["mems"].append(add(store=other, at=t0 + timedelta(hours=rng.randint(1, 30)), topic=title, kind="note",
                                    text=f"{other} asked {owner} about {title}"))
        topics.append(info)
    for va, vb in rng.sample(VALUES, 2):
        a, b = rng.sample(team, 2)
        title = f"{va.split()[0]} decision"
        t0 = now - timedelta(days=rng.randint(1, 6))
        ma = add(store=a, at=t0, topic=title, kind="decision", text=f"{a}: {va}", value=va)
        mb = add(store=b, at=min(t0 + timedelta(hours=rng.randint(2, 30)), now - timedelta(hours=1)), topic=title, kind="decision", text=f"{b}: {vb}", value=vb)
        topics.append({"title": title, "kind": "conflict", "a": ma, "b": mb})
    personal = []
    for p in team:
        text, flag = rng.choice(bank["personal"])
        personal.append(add(store=p, at=now - timedelta(days=rng.randint(1, 5)), topic=f"personal:{p}", kind="note",
                            text=text, personal=flag))
    gone = []
    for p in rng.sample(team, 2):
        t = now - timedelta(days=rng.randint(2, 8))
        gone.append(add(store=p, at=t, topic=f"draft:{p}", kind="note", text=f"{p} draft idea for the roadmap",
                        deleted_at=t + timedelta(hours=rng.randint(1, 20))))
    return {"team": team, "now": now, "mems": mems, "topics": topics, "personal": personal, "gone": gone, "bank": bank}


def rollup(w, person: str, rng: random.Random):
    """Correct lines for one person, plus how each line can be broken."""
    bank, now, today = w["bank"], w["now"], w["now"].date()
    lines, hooks = [], []
    for t in w["topics"]:
        if t["kind"] == "conflict":
            a, b = t["a"], t["b"]
            lines.append(Line("other_updates", _phr(rng, bank, "conflict", a=a.store, b=b.store, title=t["title"],
                                                      va=a.value, vb=b.value), [a.id, b.id]))
            hooks.append(("conflict", t))
            continue
        auth = _auth(t)
        o = t["owner"]
        if auth.status == "done":
            if (now - auth.at).days <= 3:
                lines.append(Line("your_updates" if o == person else "other_updates",
                                  _phr(rng, bank, "done", owner=o, title=t["title"]), [auth.id]))
                hooks.append(("done", t))
            continue
        due = auth.due
        if o == person:
            key, sec = ("overdue" if due < today else "due"), "for_you"
        elif due < today:
            key, sec = "others", "for_others"
        else:
            last = max(m.at for m in t["mems"]).date()
            lines.append(Line("other_updates", _phr(rng, bank, "quiet", title=t["title"], n=(today - last).days), [auth.id]))
            hooks.append(("quiet", t))
            continue
        n = (today - due).days if due < today else (due - today).days
        lines.append(Line(sec, _phr(rng, bank, key, title=t["title"], owner=o, n=n, due_d=due), [auth.id]))
        hooks.append(("open", t))
    own = next(m for m in w["personal"] if m.store == person)
    lines.append(Line("your_updates", _phr(rng, bank, "personal_own", text=own.text), [own.id]))
    hooks.append(("own_personal", own))
    return lines, hooks


def mutate(w, person, lines, hooks, rng, k):
    """Plant up to k mistakes on distinct lines. Returns truth {line_index: kind}."""
    bank, now, today = w["bank"], w["now"], w["now"].date()
    truth = {}
    order = list(range(len(lines)))
    rng.shuffle(order)
    for i in order:
        if len(truth) >= k:
            break
        hook, t = hooks[i]
        opts = ["no_cite", "ghost_cite", "future_cite"]
        if hook == "open":
            opts += ["wrong_date", "wrong_days"]
            if lines[i].section == "for_others":
                opts += ["owner_named", "owner_for_you"]
            if "moved" in t:
                opts += ["stale_due"] * 3
            if lines[i].section == "for_you" and _auth(t).due >= today:
                opts += ["early_overdue"]
        if hook == "done":
            opts += ["stale_done"] * 2
        if hook == "conflict":
            opts += ["hidden_conflict"] * 3
        if hook == "quiet":
            opts += ["wrong_quiet"] * 2
        if hook == "own_personal":
            opts += ["personal_leak"] * 3 + ["deleted"] * 2
        kind = rng.choice(opts)
        ln = lines[i]
        if kind == "no_cite":
            lines[i] = Line(ln.section, ln.text, [])
        elif kind == "ghost_cite":
            lines[i] = Line(ln.section, ln.text, ["m9" + str(rng.randint(100, 999))])
        elif kind == "future_cite":
            fut = Memory(id=f"m8{rng.randint(100, 999)}", store=person, at=now + timedelta(hours=rng.randint(1, 30)),
                         topic=f"future:{i}", kind="note", text="recorded later")
            w["mems"][fut.id] = fut
            lines[i] = Line(ln.section, ln.text, ln.cites + [fut.id])
        elif kind == "stale_due":
            old = t["moved"]
            n = (today - old.due).days if old.due < today else (old.due - today).days
            key = "overdue" if (ln.section == "for_you" and old.due < today) else ("due" if ln.section == "for_you" else "others")
            lines[i] = Line(ln.section, _phr(rng, bank, key, title=t["title"], owner=t["owner"], n=n, due_d=old.due), [old.id])
        elif kind == "stale_done":
            c = t["mems"][0]
            n = max(1, (today - c.due).days)
            lines[i] = Line("for_others" if t["owner"] != person else "for_you",
                            _phr(rng, bank, "others", title=t["title"], owner=t["owner"], n=n, due_d=c.due), [c.id])
        elif kind in ("wrong_date", "wrong_days", "early_overdue"):
            due = _auth(t).due
            if kind == "early_overdue":
                lines[i] = Line(ln.section, _phr(rng, bank, "overdue", title=t["title"], owner=t["owner"], n=1, due_d=due), ln.cites)
            else:
                shift = rng.choice([-3, -2, -1, 1, 2, 3])
                key = "overdue" if ln.section == "for_you" and due < today else ("due" if ln.section == "for_you" else "others")
                n = abs((today - due).days)
                if kind == "wrong_date":
                    txt = _phr(rng, bank, key, must=["{due"], title=t["title"], owner=t["owner"], n=n,
                               due_d=due + timedelta(days=shift))
                else:
                    if n + shift < 1:
                        shift = -shift
                    txt = _phr(rng, bank, key, must=["{n"], title=t["title"], owner=t["owner"], n=n + shift, due_d=due)
                lines[i] = Line(ln.section, txt, ln.cites)
        elif kind == "owner_for_you":
            lines[i] = Line("for_you", ln.text, ln.cites)
        elif kind == "owner_named":
            other = rng.choice([p for p in w["team"] if p != t["owner"]])
            lines[i] = Line(ln.section, ln.text.replace(t["owner"], other), ln.cites)
        elif kind == "hidden_conflict":
            side = rng.choice([t["a"], t["b"]])
            lines[i] = Line(ln.section, f"{t['title']}: {side.value} ({side.store}).", [side.id])
        elif kind == "wrong_quiet":
            last = max(m.at for m in t["mems"]).date()
            lines[i] = Line(ln.section, _phr(rng, bank, "quiet", title=t["title"], n=(today - last).days + rng.choice([-2, -1, 1, 2, 3])), ln.cites)
        elif kind == "personal_leak":
            other = rng.choice([m for m in w["personal"] if m.store != person])
            lines[i] = Line("other_updates", _phr(rng, bank, "personal_other", store=other.store, text=other.text), [other.id])
        elif kind == "deleted":
            g = rng.choice(w["gone"])
            lines[i] = Line("other_updates", f"{g.store} is drafting a roadmap idea.", [g.id])
        if (lines[i].text, lines[i].cites, lines[i].section) != (ln.text, ln.cites, ln.section):
            truth[i] = kind
    return truth
