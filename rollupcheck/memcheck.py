"""Pre-send check for a person's daily rollup built from team memory stores.

Each rollup line cites memory ids. A line passes only if it rests on the
newest live memory for its topic, its date math is right, its owner is
right, disagreements between stores are disclosed, and nothing personal
from another person's store appears.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9
NUMWORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUMWORDS.update({"a": 1, "an": 1, "a couple of": 2, "a couple": 2})

MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
DATE = rf"(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{MON}|{MON}\s+\d{{1,2}}(?:st|nd|rd|th)?)"
NUM = r"(?:\d+|a couple of|a couple|an?|" + "|".join(sorted((w for w in NUMWORDS if " " not in w and len(w) > 1), key=len, reverse=True)) + ")"

PERSONAL_WORDS = re.compile(
    r"\b(doctor|dentist|therapist|therapy|diagnos\w*|medication|surgery|pregnan\w*|"
    r"salary|raise|compensation|interview(?:ing)? (?:at|with)|job offer|recruiter|"
    r"divorce|wedding|funeral|my (?:wife|husband|partner|kid|son|daughter|mom|dad|mother|father)|"
    r"visa|immigration|landlord|rent|loan|debt|sick leave|burn(?:ed|t)? out|"
    r"hospital|biopsy|ivf|custody)\b", re.I)
CONFLICT_WORDS = re.compile(
    r"\b(where|whereas|while|but|conflict\w*|disagree\w*|contradict\w*|"
    r"differs?|other(?:wise)?|yet)\b", re.I)
OPEN_WORDS = re.compile(r"\b(overdue|late|past due|still (?:unsent|open|pending|waiting)|"
                        r"not (?:yet )?(?:sent|done|merged|shipped)|blocked|waiting on|due)\b", re.I)
DONE_WORDS = re.compile(r"\b(finished|done|completed|merged|shipped|sent|closed|wrapped up|landed)\b", re.I)


@dataclass
class Memory:
    id: str
    store: str
    at: datetime
    topic: str
    kind: str                 # commitment | status | decision | note
    text: str
    owner: str | None = None
    due: date | None = None
    status: str | None = None  # open | done
    value: str | None = None   # decision value, compared across stores
    supersedes: str | None = None
    personal: bool = False
    deleted_at: datetime | None = None


@dataclass
class Line:
    section: str              # for_you | for_others | your_updates | other_updates | unowned
    text: str
    cites: list[str]


@dataclass
class Finding:
    line: int
    code: str
    detail: str
    fix: str = ""


@dataclass
class Report:
    person: str
    verdict: str
    findings: list[Finding] = field(default_factory=list)


HOLD_CODES = {"PERSONAL_LEAK", "DELETED"}


def num(tok: str) -> int:
    tok = tok.lower().strip()
    return int(tok) if tok.isdigit() else NUMWORDS[tok]


def parse_date(tok: str, year: int) -> date:
    tok = tok.lower().replace(".", "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tok):
        return date.fromisoformat(tok)
    tok = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", tok)
    a, b = tok.split()
    day, mon = (a, b) if a.isdigit() else (b, a)
    return date(year, MONTHS[mon], int(day))


def fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%B')}"


def claims(text: str, year: int) -> dict:
    """Date/number claims a reader would act on. Keys absent = not stated."""
    t = text.lower()
    out: dict = {}
    m = re.search(rf"(?:overdue|late|past due|slipped past)\b[^.;]*?(?:since|from|was due|its|the)\s+({DATE})", t) \
        or re.search(rf"(?:due|deadline)\s+(?:was\s+|on\s+)?({DATE})[^.;]*?(?:overdue|late|missed|passed)", t)
    if m:
        out["overdue_since"] = parse_date(m.group(1), year)
    m = re.search(rf"({NUM})\s+days?\s+(?:overdue|late|past due|behind)", t) \
        or re.search(rf"(?:overdue|late|past due)\s+by\s+({NUM})\s+days?", t)
    if m:
        out["days_overdue"] = num(m.group(1))
    m = re.search(rf"(?:due in|in)\s+({NUM})\s+days?", t) or re.search(rf"({NUM})\s+days?\s+(?:out|away|left|to go)", t)
    if m:
        out["days_left"] = num(m.group(1))
    m = re.search(rf"\bdue(?: on| by)?\s+({DATE})", t)
    if m and "overdue_since" not in out:
        out["due_on"] = parse_date(m.group(1), year)
    m = re.search(rf"({NUM})\s+days?\s+(?:on|later|since|without)", t) \
        or re.search(rf"(?:for|in)\s+({NUM})\s+days?\s+(?:now|running)", t)
    if m:
        out["days_since"] = num(m.group(1))
    m = re.search(rf"(?:unresolved|untouched|quiet|stalled|open|unsettled|deferred)\s+since\s+({DATE})", t)
    if m:
        out["since"] = parse_date(m.group(1), year)
    if DONE_WORDS.search(t) and not re.search(r"\b(not|un|n't|still)\s*(?:yet\s+)?(sent|done|merged|shipped|finished)", t):
        out["state"] = "done"
    elif OPEN_WORDS.search(t):
        out["state"] = "open"
    return out


def live(mem: Memory, when: datetime) -> bool:
    return mem.at <= when and (mem.deleted_at is None or mem.deleted_at > when)


def newest_per_topic(mems: dict[str, Memory], when: datetime) -> dict[str, dict[str, Memory]]:
    """topic -> store -> that store's newest live memory on the topic."""
    out: dict[str, dict[str, Memory]] = {}
    for m in mems.values():
        if not live(m, when):
            continue
        cur = out.setdefault(m.topic, {}).get(m.store)
        if cur is None or m.at > cur.at:
            out[m.topic][m.store] = m
    return out


def authority(topic_mems: dict[str, Memory], owner: str | None) -> Memory:
    """The memory that states the topic now: owner's store wins, else newest."""
    if owner and owner in topic_mems:
        return topic_mems[owner]
    return max(topic_mems.values(), key=lambda m: m.at)


def conflict(topic_mems: dict[str, Memory]) -> list[Memory] | None:
    vals = {}
    for m in topic_mems.values():
        if m.value is not None:
            vals.setdefault(m.value, m)
    return list(vals.values()) if len(vals) > 1 else None


def topic_owner(mems: dict[str, Memory], topic: str) -> str | None:
    owners = [m.owner for m in mems.values() if m.topic == topic and m.owner]
    return owners[-1] if owners else None


def check(person: str, when: datetime, lines: list[Line], mems: dict[str, Memory],
          team: list[str]) -> Report:
    today = when.date()
    newest = newest_per_topic(mems, when)
    f: list[Finding] = []
    for i, ln in enumerate(lines):
        if not ln.cites:
            f.append(Finding(i, "CITE_MISSING", "line cites no memory"))
            continue
        cited = []
        for cid in ln.cites:
            m = mems.get(cid)
            if m is None:
                f.append(Finding(i, "CITE_UNKNOWN", f"{cid} is not in any store"))
            elif m.at > when:
                f.append(Finding(i, "FUTURE_CITE", f"{cid} was recorded after this rollup ({m.at:%d %b %H:%M})"))
            elif m.deleted_at and m.deleted_at <= when:
                f.append(Finding(i, "DELETED", f"{cid} was deleted by {m.store} on {m.deleted_at:%d %b}",
                                 "drop the line or rebuild it without this memory"))
            else:
                cited.append(m)
        for m in cited:
            if m.store != person and (m.personal or PERSONAL_WORDS.search(m.text)):
                why = "marked personal" if m.personal else f"personal content ('{PERSONAL_WORDS.search(m.text).group(0)}')"
                f.append(Finding(i, "PERSONAL_LEAK", f"{m.id} from {m.store}'s store is {why}",
                                 "remove; personal memories stay in their owner's rollup"))
        if not cited:
            continue
        topics = {m.topic for m in cited}
        for topic in topics:
            tm = newest.get(topic)
            if not tm:
                continue
            owner = topic_owner(mems, topic)
            auth = authority(tm, owner)
            cited_ids = {m.id for m in cited if m.topic == topic}
            clash = conflict(tm)
            if clash:
                sides = {m.id for m in clash}
                if not sides <= cited_ids or not CONFLICT_WORDS.search(ln.text):
                    who = " vs ".join(f"{m.store}: {m.value}" for m in clash)
                    f.append(Finding(i, "CONFLICT_HIDDEN", f"stores disagree on '{topic}' ({who})",
                                     "cite both sides and say they disagree"))
                continue
            if auth.id not in cited_ids:
                old = max((m for m in cited if m.topic == topic), key=lambda m: m.at)
                if auth.at > old.at:
                    f.append(Finding(i, "SUPERSEDED", f"{old.id} ({old.at:%d %b}) was replaced by {auth.id} ({auth.at:%d %b}): {auth.text}",
                                     f"rebuild from {auth.id}"))
                    continue
            c = claims(ln.text, today.year)
            com = auth if auth.kind == "commitment" or auth.due else None
            if c.get("state") == "open" and auth.status == "done":
                f.append(Finding(i, "STATUS", f"line says still open; {auth.id} records it done", "move to updates as done"))
            if c.get("state") == "done" and auth.status == "open" and "overdue_since" not in c and "days_overdue" not in c:
                f.append(Finding(i, "STATUS", f"line says done; {auth.id} records it open"))
            if com and com.due:
                due = com.due
                if "overdue_since" in c and c["overdue_since"] != due:
                    f.append(Finding(i, "DATE", f"says overdue since {fmt(c['overdue_since'])}; due date is {fmt(due)}",
                                     f"overdue since {fmt(due)}"))
                if ("overdue_since" in c or "days_overdue" in c) and due >= today:
                    f.append(Finding(i, "DATE", f"says overdue; due {fmt(due)} is not past"))
                if "days_overdue" in c and c["days_overdue"] != (today - due).days:
                    f.append(Finding(i, "DATE", f"says {c['days_overdue']} days overdue; it is {(today - due).days}",
                                     f"{(today - due).days} days overdue"))
                if "days_left" in c and c["days_left"] != (due - today).days:
                    f.append(Finding(i, "DATE", f"says {c['days_left']} days left; it is {(due - today).days}",
                                     f"due in {(due - today).days} days"))
                if "due_on" in c and c["due_on"] != due:
                    f.append(Finding(i, "DATE", f"says due {fmt(c['due_on'])}; due date is {fmt(due)}", f"due {fmt(due)}"))
            if "days_since" in c:
                last = max(m.at for m in tm.values()).date()
                if c["days_since"] != (today - last).days:
                    f.append(Finding(i, "DATE", f"says {c['days_since']} days since; last memory {fmt(last)} is {(today - last).days} days ago"))
            if "since" in c:
                first = min(m.at for m in mems.values() if m.topic == topic and live(m, when)).date()
                if c["since"] != first:
                    f.append(Finding(i, "DATE", f"says since {fmt(c['since'])}; topic first recorded {fmt(first)}"))
            if owner and ln.section == "for_you" and owner != person:
                f.append(Finding(i, "OWNER", f"'for you' but {topic} is owned by {owner}", "move to 'for other people'"))
            if owner and ln.section == "for_others":
                named = [p for p in team if re.search(rf"\b{re.escape(p)}\b", ln.text)]
                if named and owner not in named:
                    f.append(Finding(i, "OWNER", f"names {', '.join(named)}; {topic} is owned by {owner}"))
    codes = {x.code for x in f}
    verdict = "HOLD" if codes & HOLD_CODES else ("FIX" if f else "SEND")
    return Report(person, verdict, f)


def cite_exists_baseline(lines: list[Line], mems: dict[str, Memory]) -> bool:
    """What 'grounded in N memories' checks: every line cites ids that exist."""
    return all(ln.cites and all(c in mems for c in ln.cites) for ln in lines)
