import unittest
from datetime import date, datetime

from rollupcheck.memcheck import Line, Memory, check, claims

NOW = datetime(2026, 8, 27, 7, 0)
TEAM = ["Ana", "Ben", "Cy"]


def mem(id, store, day, topic, **kw):
    kw.setdefault("kind", "note")
    kw.setdefault("text", topic)
    return Memory(id=id, store=store, at=datetime(2026, 8, day, 12), topic=topic, **kw)


def store(*ms):
    return {m.id: m for m in ms}


class Claims(unittest.TestCase):
    def test_spoken_dates_and_numbers(self):
        self.assertEqual(claims("Round details overdue since 25 August.", 2026)["overdue_since"], date(2026, 8, 25))
        self.assertEqual(claims("Pricing copy slipped past its Aug 25 date.", 2026)["overdue_since"], date(2026, 8, 25))
        self.assertEqual(claims("EC2 review is late by three days.", 2026)["days_overdue"], 3)
        self.assertEqual(claims("Tracker: two days to go.", 2026)["days_left"], 2)
        self.assertEqual(claims("Billing landed (Ben).", 2026)["state"], "done")
        self.assertEqual(claims("Instructions still unsent.", 2026)["state"], "open")


class Check(unittest.TestCase):
    def test_moved_due_date_is_superseded(self):
        ms = store(mem("m1", "Ana", 20, "deck", kind="commitment", owner="Ana", due=date(2026, 8, 25), status="open"),
                   mem("m2", "Ana", 24, "deck", kind="commitment", owner="Ana", due=date(2026, 8, 30), status="open",
                       supersedes="m1"))
        bad = check("Ana", NOW, [Line("for_you", "Deck overdue since 25 August.", ["m1"])], ms, TEAM)
        self.assertEqual([f.code for f in bad.findings], ["SUPERSEDED"])
        good = check("Ana", NOW, [Line("for_you", "Deck is due in 3 days.", ["m2"])], ms, TEAM)
        self.assertEqual(good.verdict, "SEND")

    def test_date_math_and_owner(self):
        ms = store(mem("m1", "Ben", 20, "deck", kind="commitment", owner="Ben", due=date(2026, 8, 25), status="open"))
        rep = check("Ana", NOW, [Line("for_you", "Deck: 3 days overdue.", ["m1"])], ms, TEAM)
        self.assertEqual(sorted(f.code for f in rep.findings), ["DATE", "OWNER"])

    def test_other_persons_personal_memory_holds_but_own_is_fine(self):
        ms = store(mem("p1", "Ben", 25, "p:Ben", text="dentist appointment Thursday"),
                   mem("p2", "Ana", 25, "p:Ana", text="dentist appointment Thursday"))
        self.assertEqual(check("Ana", NOW, [Line("other_updates", "Ben: dentist.", ["p1"])], ms, TEAM).verdict, "HOLD")
        self.assertEqual(check("Ana", NOW, [Line("your_updates", "You: dentist.", ["p2"])], ms, TEAM).verdict, "SEND")

    def test_conflict_must_cite_both_sides_and_say_so(self):
        ms = store(mem("d1", "Ana", 24, "launch", kind="decision", value="launch 26 Aug"),
                   mem("d2", "Ben", 25, "launch", kind="decision", value="hold until users"))
        hidden = check("Cy", NOW, [Line("other_updates", "Launch is on hold.", ["d2"])], ms, TEAM)
        self.assertEqual([f.code for f in hidden.findings], ["CONFLICT_HIDDEN"])
        shown = check("Cy", NOW, [Line("other_updates", "Ana has launch 26 Aug, where Ben holds it.", ["d1", "d2"])], ms, TEAM)
        self.assertEqual(shown.verdict, "SEND")

    def test_deleted_and_unknown_citations(self):
        m = mem("x1", "Ben", 20, "idea")
        m.deleted_at = datetime(2026, 8, 21)
        rep = check("Ana", NOW, [Line("other_updates", "Ben idea.", ["x1"]), Line("other_updates", "Ghost.", ["m999"])],
                    store(m), TEAM)
        self.assertEqual([f.code for f in rep.findings], ["DELETED", "CITE_UNKNOWN"])
        self.assertEqual(rep.verdict, "HOLD")


if __name__ == "__main__":
    unittest.main()
