"""The job-hunt skill's ledger: matching jobs, skipping the applied ones, the report."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "job-hunt", "scripts", "jobs.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import jobs  # noqa: E402


class Match(unittest.TestCase):
    def test_job_ids_from_urls(self):
        self.assertEqual(jobs.job_id("https://www.linkedin.com/jobs/view/4012345678/?refId=x"), "4012345678")
        self.assertEqual(jobs.job_id("https://www.linkedin.com/jobs/view/backend-engineer-at-acme-4012345678"), "4012345678")
        self.assertEqual(jobs.job_id("https://www.linkedin.com/jobs/search/?currentJobId=4012345678&k=x"), "4012345678")
        self.assertEqual(jobs.job_id("https://acme.com/careers/12"), "")

    def test_same_by_id_or_company_and_title(self):
        row = {"company": "Acme Pvt. Ltd.", "title": "Backend Engineer (Node.js)",
               "url": "https://www.linkedin.com/jobs/view/111111111/"}
        self.assertTrue(jobs.same({"url": "https://www.linkedin.com/jobs/view/111111111"}, row))
        repost = {"company": "ACME", "title": "backend engineer - node.js", "url": "https://www.linkedin.com/jobs/view/222222222/"}
        self.assertTrue(jobs.same(repost, row))
        self.assertFalse(jobs.same({"company": "Acme", "title": "Frontend Engineer"}, row))
        self.assertFalse(jobs.same({"company": "", "title": ""}, {"company": "", "title": ""}))

    def test_split(self):
        found = [
            {"url": "https://www.linkedin.com/jobs/view/111111111/", "company": "A", "title": "X", "score": 70},
            {"url": "https://www.linkedin.com/jobs/view/222222222/", "company": "B", "title": "Y", "score": 90},
            {"url": "https://www.linkedin.com/jobs/view/222222222/", "company": "B", "title": "Y", "score": 90},
            {"url": "https://www.linkedin.com/jobs/view/333333333/", "company": "C", "title": "Z", "score": 80},
            {"url": "https://www.linkedin.com/jobs/view/444444444/", "company": "D", "title": "W", "score": 95},
        ]
        applied = [{"company": "C", "title": "Z", "date": "2026-11-01", "url": ""}]
        seen = [{"job_id": "444444444", "date": "2026-11-05"}]
        g = jobs.split(found, applied, seen)
        self.assertEqual([j["company"] for j in g["new"]], ["B", "A"])
        self.assertEqual([j["company"] for j in g["applied"]], ["C"])
        self.assertEqual(g["seen"][0]["seen_on"], "2026-11-05")


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self.tmp.name, "data")
        self.cfg = os.path.join(self.tmp.name, "job-hunt.toml")
        with open(self.cfg, "w") as f:
            f.write(f'data_dir = "{self.data}"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def run_jobs(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "--config", self.cfg, *args],
                              capture_output=True, text=True)

    def test_applied_then_report_skips_it_and_remembers_the_rest(self):
        self.assertEqual(self.run_jobs("init").returncode, 0)
        r = self.run_jobs("applied", "add", "--url", "https://www.linkedin.com/jobs/view/111111111/",
                          "--company", "Acme", "--title", "Backend Engineer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.run_jobs("applied", "add", "--company", "acme", "--title", "backend engineer").returncode, 1)

        cand = os.path.join(self.tmp.name, "candidates.json")
        with open(cand, "w") as f:
            json.dump([
                {"url": "https://www.linkedin.com/jobs/view/111111111/", "company": "Acme", "title": "Backend Engineer"},
                {"url": "https://www.linkedin.com/jobs/view/555555555/", "company": "Globex", "title": "API Developer",
                 "score": 82, "why": ["5 years of Node.js"], "gaps": ["Kafka"],
                 "contacts": [{"name": "Sam R", "role": "Recruiter", "profile": "https://www.linkedin.com/in/x",
                               "source": "job post"}]},
            ], f)
        r = self.run_jobs("report", cand)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(r.stdout.strip()) as f:
            text = f.read()
        self.assertIn("API Developer - Globex  (82/100)", text)
        self.assertIn("Sam R - Recruiter", text)
        self.assertIn("Skipped: already applied", text)
        with open(os.path.join(self.data, "seen.csv")) as f:
            self.assertEqual([row["company"] for row in csv.DictReader(f)], ["Globex"])

        self.assertTrue(os.path.exists(r.stdout.strip()[:-3] + ".json"))
        m = self.run_jobs("message", "--tip", "Apply to 1 first.")
        self.assertEqual(m.returncode, 0, m.stderr)
        self.assertIn("*1. API Developer - Globex*", m.stdout)
        self.assertIn("https://www.linkedin.com/jobs/view/555555555/", m.stdout)
        self.assertIn("👤 Sam R - Recruiter", m.stdout)
        self.assertIn("⚠️ Kafka", m.stdout)
        self.assertNotIn("Acme", m.stdout)
        self.assertIn("*👉 Tip:* Apply to 1 first.", m.stdout)

        again = json.loads(self.run_jobs("filter", cand).stdout)
        self.assertEqual((len(again["new"]), len(again["seen"]), len(again["applied"])), (0, 1, 1))
        self.assertNotEqual(self.run_jobs("report", cand).stdout.strip(), r.stdout.strip())

    def test_message_without_a_report(self):
        self.run_jobs("init")
        r = self.run_jobs("message")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no report yet", r.stderr)


if __name__ == "__main__":
    unittest.main()
