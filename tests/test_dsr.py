"""The dsr skill's scripts: collecting a day's commits, checking and rendering the table."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "dsr", "scripts")
sys.path.insert(0, SCRIPTS)

import dsr_commits  # noqa: E402
import dsr_render  # noqa: E402

T = dsr_render.clock


def rows(*spec):
    return [(T(a), T(b), t) for a, b, t in spec]


class Check(unittest.TestCase):
    DAY = rows(("11:30 AM", "01:00 PM", "a"), ("01:00 PM", "02:00 PM", "Lunch Break"), ("02:00 PM", "09:00 PM", "b"))

    def test_a_good_day_passes(self):
        self.assertEqual(dsr_render.check(self.DAY, "11:30 AM", "9 PM", "01:00 PM to 02:00 PM", "Lunch Break"), [])

    def test_gaps_overlaps_and_bounds(self):
        bad = rows(("11:30 AM", "01:00 PM", "a"), ("01:30 PM", "03:00 PM", "b"), ("02:30 PM", "08:00 PM", "c"))
        problems = dsr_render.check(bad, "11:00 AM", "09:00 PM", "01:00 PM to 02:00 PM", "Lunch Break")
        text = " | ".join(problems)
        for want in ("a gap", "an overlap", "starts at 11:30 AM", "ends at 08:00 PM", "Lunch Break"):
            self.assertIn(want, text)

    def test_lunch_only_when_the_day_spans_it(self):
        morning = rows(("09:00 AM", "12:00 PM", "a"))
        self.assertEqual(dsr_render.check(morning, None, None, "01:00 PM to 02:00 PM", "Lunch Break"), [])

    def test_render_is_a_real_table(self):
        plain, page = dsr_render.render("26/10/2026", self.DAY, "Hello,")
        self.assertIn("Date : 26/10/2026", plain)
        self.assertIn("11:30 AM to 01:00 PM\ta", plain)
        self.assertEqual(page.count("<tr>"), 4)
        self.assertIn("<th", page)

    def test_tasks_are_escaped(self):
        _, page = dsr_render.render("26/10/2026", rows(("09:00 AM", "10:00 AM", "<b>&")), "Hello,")
        self.assertIn("&lt;b&gt;&amp;", page)

    def test_command_writes_both_files(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "rows.json"), "w") as f:
            json.dump({"date": "2026-10-26", "rows": [["11:30 AM", "01:00 PM", "a"], ["01:00 PM", "02:00 PM", "Lunch Break"],
                                                       ["02:00 PM", "09:00 PM", "b"]]}, f)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dsr_render.py"), os.path.join(d, "rows.json"),
                            "--start", "11:30 AM", "--end", "09:00 PM"],
                           capture_output=True, text=True, env={**os.environ, "XDG_CONFIG_HOME": d})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(d, "dsr.html")))


class Structure(unittest.TestCase):
    DAY = Check.DAY
    COMMITS = {"repos": {"/w/app": [
        {"time": "16:00", "subject": "Fix login", "project": "App", "merge": False, "pushed": True,
         "url": "https://github.com/o/App/commit/b"},
        {"time": "11:00", "subject": "Add page", "project": "App", "merge": False, "pushed": True,
         "url": "https://github.com/o/App/commit/a"},
        {"time": "17:00", "subject": "Merge branch", "project": "App", "merge": True, "pushed": True, "url": "x"}]}}

    def test_commit_links_at_the_bottom_oldest_first(self):
        links, problems, _ = dsr_render.links(self.COMMITS, False)
        self.assertEqual(problems, [])
        self.assertEqual([s for _, s, _ in links], ["Add page", "Fix login"])
        plain, page = dsr_render.render("02/11/2026", self.DAY, "Hello,", links, ["Regards,", "Me"])
        self.assertLess(plain.index("Lunch Break"), plain.index("Commits:"))
        self.assertLess(plain.index("Commits:"), plain.index("Regards,\nMe"))
        self.assertIn('<a href="https://github.com/o/App/commit/a">Add page</a>', page)
        self.assertNotIn("Merge branch", page)

    def test_unpushed_commits_are_refused_or_left_out(self):
        data = {"repos": {"/w/app": [{"subject": "Local", "project": "App", "pushed": False, "url": "u"}]}}
        self.assertIn("not pushed", dsr_render.links(data, False)[1][0])
        links, problems, left = dsr_render.links(data, True)
        self.assertEqual((links, problems, len(left)), ([], [], 1))

    def test_monday_is_new_the_rest_reply_in_the_weeks_thread(self):
        cfg = {"to": ["Boss <b@x.com>"], "cc": ["HR"]}
        mon = dsr_render.plan(dt.date(2026, 11, 2), cfg)
        sat = dsr_render.plan(dt.date(2026, 11, 7), cfg)
        self.assertEqual((mon["mode"], sat["mode"]), ("new", "reply"))
        self.assertEqual(mon["subject"], "Daily Status Report: 02/11/2026 to 07/11/2026")
        self.assertEqual(mon["subject"], sat["subject"])
        self.assertEqual(mon["unresolved"], ["HR"])

    def test_sunday_is_refused(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "rows.json"), "w") as f:
            json.dump({"date": "01/11/2026", "rows": [["09:00 AM", "10:00 AM", "a"]]}, f)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dsr_render.py"), os.path.join(d, "rows.json")],
                           capture_output=True, text=True, env={**os.environ, "XDG_CONFIG_HOME": d})
        self.assertEqual(r.returncode, 2)
        self.assertIn("Sunday", r.stderr)


class Commits(unittest.TestCase):
    def test_web_links_from_remotes(self):
        for remote, want in (("git@github.com:o/r.git", "https://github.com/o/r"),
                             ("git@github-work:o/r.git", "https://github.com/o/r"),
                             ("https://github.com/o/r", "https://github.com/o/r"),
                             ("ssh://git@gitlab.com/g/r.git", "https://gitlab.com/g/r"),
                             ("git@example.org:o/r.git", "")):
            self.assertEqual(dsr_commits.web_url(remote), want, remote)
        self.assertEqual(dsr_commits.commit_link("https://gitlab.com/g/r", "a1"), "https://gitlab.com/g/r/-/commit/a1")

    def test_finds_the_days_commits_by_author_date(self):
        root = tempfile.mkdtemp()
        repo = os.path.join(root, "work", "app")
        os.makedirs(repo)
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "XDG_CONFIG_HOME": root}

        def git(*a, when=None):
            e = dict(env)
            if when:
                e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = when
            subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True, env=e)

        git("init", "-q")
        git("config", "user.email", "me@example.com")
        git("config", "user.name", "Me")
        day = dt.date(2026, 10, 26)
        git("commit", "-q", "--allow-empty", "-m", "built the thing", "-m", "the details", when=f"{day}T15:00:00")
        git("commit", "-q", "--allow-empty", "-m", "the day after", when=f"{day + dt.timedelta(days=1)}T10:00:00")
        git("-c", "user.email=someone@example.com", "commit", "-q", "--allow-empty", "-m", "not mine", when=f"{day}T16:00:00")
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dsr_commits.py"), "26/10/2026", "--repos", root, "--json"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        found = json.loads(r.stdout)["repos"]
        subjects = [c["subject"] for c in found[repo]]
        self.assertEqual(subjects, ["built the thing"])
        self.assertEqual(found[repo][0]["body"], "the details")
        self.assertFalse(found[repo][0]["pushed"])


if __name__ == "__main__":
    unittest.main()
