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
        self.assertEqual(jobs.job_id("https://in.indeed.com/viewjob?jk=4f2a9c1b7e3d5a60&from=serp"), "indeed:4f2a9c1b7e3d5a60")
        self.assertEqual(jobs.job_id("https://in.indeed.com/jobs?q=node&vjk=0a1b2c3d4e5f6789"), "indeed:0a1b2c3d4e5f6789")
        self.assertEqual(jobs.job_id("https://www.naukri.com/job-listings-node-js-developer-acme-mumbai-1-to-3-years-141125012345"),
                         "naukri:141125012345")
        self.assertEqual(jobs.job_id("https://www.naukri.com/job-listings-backend-dev-acme-pune-2-to-5-years-141125099999?src=jobsearchDesk"),
                         "naukri:141125099999")

    def test_more_boards_ids(self):
        cases = {
            "https://www.hirist.tech/j/nodejs-developer-1522246?jobPos=17": "hirist:1522246",
            "https://cutshort.io/job/Node-Js-Developer-Mumbai-Neon-Digital-ben30knW": "cutshort:ben30knW",
            "https://wellfound.com/jobs/3092804-nodejs-developer": "wellfound:3092804",
            "https://internshala.com/job/detail/backend-developer-job-in-mumbai-at-ink-in-caps1731473760": "internshala:1731473760",
            "https://www.foundit.in/job/nodejs-developer-acme-services-mumbai-35490342": "foundit:35490342",
            "https://www.instahyre.com/job-298765-nodejs-developer-at-acme-mumbai/": "instahyre:298765",
            "https://cutshort.io/jobs/nodejs-jobs-in-mumbai": "",
            "https://wellfound.com/role/r/node-js-developer": "",
        }
        for url, want in cases.items():
            self.assertEqual(jobs.job_id(url), want, url)
        self.assertEqual([jobs.site({"url": u}) for u in list(cases)[:5]],
                         ["hirist", "cutshort", "wellfound", "internshala", "foundit"])

    def test_site_and_grouping(self):
        self.assertEqual(jobs.site({"url": "https://www.linkedin.com/jobs/view/1234567/"}), "linkedin")
        self.assertEqual(jobs.site({"url": "https://in.indeed.com/viewjob?jk=abcdef12"}), "indeed")
        self.assertEqual(jobs.site({"url": "https://www.naukri.com/job-listings-x-123456789"}), "naukri")
        self.assertEqual(jobs.site({"url": "https://acme.com/careers/1"}), "other")
        self.assertEqual(jobs.site({"url": "https://acme.com/careers/1", "site": "Instahyre"}), "instahyre")
        found = [{"url": "https://acme.com/1", "company": "E"},
                 {"url": "https://www.naukri.com/job-listings-x-123456789", "company": "D"},
                 {"url": "https://in.indeed.com/viewjob?jk=abcdef12", "company": "C"},
                 {"url": "https://www.linkedin.com/jobs/view/1234567/", "company": "B"},
                 {"url": "https://www.naukri.com/job-listings-y-987654321", "company": "A"}]
        self.assertEqual([(k, [j["company"] for j in js]) for k, js in jobs.by_site(found)],
                         [("linkedin", ["B"]), ("indeed", ["C"]), ("naukri", ["D", "A"]), ("other", ["E"])])

    def test_same_job_on_two_boards_is_one_job(self):
        on_naukri = {"url": "https://www.naukri.com/job-listings-x-123456789", "company": "Acme Pvt Ltd", "title": "Node.js Developer"}
        seen = [{"job_id": "1234567", "company": "ACME", "title": "node.js developer", "date": "2026-11-15"}]
        g = jobs.split([on_naukri], [], seen)
        self.assertEqual((len(g["new"]), len(g["seen"])), (0, 1))
        self.assertEqual(g["seen"][0]["site"], "naukri")

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

    def test_report_and_message_group_jobs_by_site(self):
        self.run_jobs("init")
        cand = os.path.join(self.tmp.name, "candidates.json")
        with open(cand, "w") as f:
            json.dump([
                {"url": "https://www.naukri.com/job-listings-node-dev-acme-mumbai-1-to-3-years-141125012345",
                 "company": "Acme", "title": "Node Dev", "score": 90, "experience": "1-3 Yrs"},
                {"url": "https://www.linkedin.com/jobs/view/555555555/", "company": "Globex", "title": "API Dev", "score": 70},
                {"url": "https://in.indeed.com/viewjob?jk=4f2a9c1b7e3d5a60", "company": "Initech", "title": "Backend Dev", "score": 80},
                {"url": "https://www.linkedin.com/jobs/view/666666666/", "company": "Hooli", "title": "SDE 1", "score": 85},
            ], f)
        r = self.run_jobs("report", cand)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(r.stdout.strip()) as f:
            text = f.read()
        heads = [line for line in text.splitlines() if line.startswith("## ") or line.startswith("### ")]
        self.assertEqual(heads, ["## LinkedIn (2)", "### 1. SDE 1 - Hooli  (85/100)", "### 2. API Dev - Globex  (70/100)",
                                 "## Indeed (1)", "### 3. Backend Dev - Initech  (80/100)",
                                 "## Naukri (1)", "### 4. Node Dev - Acme  (90/100)"])
        self.assertIn("1-3 Yrs", text)

        m = self.run_jobs("message", "--top", "3")
        self.assertEqual(m.returncode, 0, m.stderr)
        out = m.stdout
        # The best 3 (Globex at 70 is left out), under a heading per site, numbered straight down.
        self.assertLess(out.index("*🌐 LINKEDIN* (1)"), out.index("*1. SDE 1 - Hooli*"))
        self.assertLess(out.index("*1. SDE 1 - Hooli*"), out.index("*🌐 INDEED* (1)"))
        self.assertLess(out.index("*🌐 INDEED* (1)"), out.index("*2. Backend Dev - Initech*"))
        self.assertLess(out.index("*2. Backend Dev - Initech*"), out.index("*🌐 NAUKRI* (1)"))
        self.assertLess(out.index("*🌐 NAUKRI* (1)"), out.index("*3. Node Dev - Acme*"))
        self.assertIn("https://in.indeed.com/viewjob?jk=4f2a9c1b7e3d5a60", out)
        self.assertNotIn("Globex", out)
        with open(r.stdout.strip()[:-3] + ".json") as f:
            shown = json.load(f)["shown"]
        self.assertEqual([(s["shown_n"], s["site"], s["company"]) for s in shown],
                         [(1, "linkedin", "Hooli"), (2, "indeed", "Initech"), (3, "naukri", "Acme")])

    def test_message_without_a_report(self):
        self.run_jobs("init")
        r = self.run_jobs("message")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no report yet", r.stderr)


if __name__ == "__main__":
    unittest.main()
