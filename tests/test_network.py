"""The network skill's ledger: one key per person, no second contact, the limits, notes, the report."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "network", "scripts", "net.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import net  # noqa: E402


class Keys(unittest.TestCase):
    def test_linkedin_forms_are_one_person(self):
        forms = ["https://www.linkedin.com/in/Jane-Doe-123/", "https://in.linkedin.com/in/jane-doe-123?trk=x",
                 "linkedin.com/in/jane-doe-123/recent-activity/all/", "jane-doe-123"]
        self.assertEqual({net.key("linkedin", f) for f in forms}, {"linkedin:jane-doe-123"})
        self.assertEqual(net.key("linkedin", "https://www.linkedin.com/company/acme/"), "")

    def test_x_forms_are_one_person(self):
        forms = ["https://x.com/JaneDev", "https://twitter.com/janedev/status/123", "@janedev", "x.com/janedev?s=20"]
        self.assertEqual({net.key("x", f) for f in forms}, {"x:janedev"})
        self.assertEqual(net.key("x", "https://x.com/home"), "")
        self.assertEqual(net.key("mastodon", "@a"), "")


class Ledger(unittest.TestCase):
    def test_failed_may_be_retried_everything_else_blocks(self):
        rows = [{"key": "x:a", "status": "failed"}]
        self.assertIsNone(net.blocking(rows, "x:a"))
        for status in ("followed", "skipped", "already", "withdrawn"):
            self.assertIsNotNone(net.blocking([{"key": "x:a", "status": status}], "x:a"))

    def test_split(self):
        cfg = dict(net.DEFAULTS, exclude_companies=["Acme Infotech"], min_score=55)
        people = [
            {"platform": "linkedin", "profile": "https://www.linkedin.com/in/a/", "score": 70},
            {"platform": "linkedin", "profile": "https://www.linkedin.com/in/a?x=1", "score": 70},
            {"platform": "linkedin", "profile": "https://www.linkedin.com/in/b/", "score": 90},
            {"platform": "linkedin", "profile": "https://www.linkedin.com/in/c/", "score": 90,
             "headline": "HR at Acme Infotech"},
            {"platform": "x", "profile": "@d", "score": 40},
            {"platform": "x", "profile": "@e", "score": 80},
        ]
        rows = [{"key": "x:e", "status": "followed", "action": "follow", "ts": "2026-11-01T10:00:00"}]
        g = net.split(people, rows, cfg)
        self.assertEqual([p["key"] for p in g["new"]], ["linkedin:b", "linkedin:a"])
        self.assertEqual(g["done"][0]["last"], "follow followed 2026-11-01")
        self.assertEqual({p["key"]: p["reason"] for p in g["excluded"]},
                         {"linkedin:c": "works at Acme Infotech", "x:d": "score under 55"})

    def test_usage(self):
        now = dt.datetime(2026, 11, 12, 18, 0)
        cfg = dict(net.DEFAULTS, linkedin_per_day=20, linkedin_per_week=22, notes_per_month=5)
        row = lambda ts, **kw: dict({"platform": "linkedin", "action": "connect", "status": "sent",
                                      "note": "", "ts": ts}, **kw)
        rows = [row("2026-11-12T09:00:00", note="hi")] * 3 + [row("2026-11-08T09:00:00")] * 10 \
            + [row("2026-10-30T09:00:00", note="hi")] * 4 + [row("2026-11-12T09:00:00", status="already")]
        used, left = net.usage(rows, cfg, now)
        self.assertEqual(used, {"linkedin_today": 3, "linkedin_week": 13, "notes_month": 3, "x_today": 0})
        self.assertEqual(left, {"linkedin": 9, "notes": 2, "x": 15})

    def test_note_check(self):
        self.assertEqual(net.note_problem("Hi, saw your post.", 200), "")
        self.assertIn("cut 1", net.note_problem("x" * 201, 200))
        self.assertIn("placeholder", net.note_problem("Hi [name], hello", 200))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self.tmp.name, "data")
        self.cfg = os.path.join(self.tmp.name, "network.toml")
        with open(self.cfg, "w") as f:
            f.write(f'data_dir = "{self.data}"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def net(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "--config", self.cfg, *args], capture_output=True, text=True)

    def test_log_once_then_check_blocks_and_report(self):
        self.assertEqual(self.net("init").returncode, 0)
        since = json.loads(self.net("status").stdout)["now"]
        url = "https://www.linkedin.com/in/jane-doe/"
        self.assertEqual(self.net("check", "--platform", "linkedin", "--profile", url).returncode, 0)
        r = self.net("log", "--platform", "linkedin", "--profile", url + "?trk=a", "--action", "connect",
                     "--name", "Jane Doe", "--category", "founder", "--score", "88",
                     "--note", "Saw your hiring post for Node devs.")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = self.net("check", "--platform", "linkedin", "--profile", "jane-doe")
        self.assertEqual(c.returncode, 1)
        self.assertIn("connect sent", c.stdout)
        self.assertEqual(self.net("log", "--platform", "linkedin", "--profile", url, "--action", "connect").returncode, 1)
        self.assertNotEqual(self.net("log", "--platform", "x", "--profile", "@bob", "--action", "follow",
                                     "--note", "x" * 300).returncode, 0)
        self.assertEqual(self.net("log", "--platform", "x", "--profile", "@bob", "--action", "follow",
                                  "--name", "Bob").returncode, 0)

        st = json.loads(self.net("status").stdout)
        self.assertEqual(st["used"]["linkedin_today"], 1)
        self.assertEqual(st["used"]["notes_month"], 1)
        self.assertEqual(st["left_this_run"]["notes"], 4)

        self.assertEqual(self.net("mark", "--platform", "linkedin", "--profile", url, "--status", "accepted").returncode, 0)
        self.assertIn("accepted", self.net("list").stdout)

        engage = os.path.join(self.tmp.name, "engage.json")
        with open(engage, "w") as f:
            json.dump([{"name": "Bob", "url": "https://x.com/bob/status/1", "text": "Shipping v2", "reply_idea": "ask"}], f)
        rp = self.net("report", "--since", since, "--engage", engage)
        self.assertEqual(rp.returncode, 0, rp.stderr)
        with open(rp.stdout.strip()) as f:
            text = f.read()
        self.assertIn("1 followed on X", text)
        self.assertIn("Worth a reply on X", text)
        self.assertIn("https://x.com/bob/status/1", text)


if __name__ == "__main__":
    unittest.main()
