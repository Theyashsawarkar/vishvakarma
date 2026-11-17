#!/usr/bin/env python3
"""The job-hunt skill's ledger: the jobs already applied to and already shown, and each run's report.

    jobs.py init                      make the data folder (resume goes in it)
    jobs.py status                    where everything is; is the profile older than the resume?
    jobs.py filter candidates.json    split found jobs into new / already applied / shown before
    jobs.py report candidates.json    write today's report and remember its jobs as shown
    jobs.py applied add --url U --company C --title T [--via V] [--contact X] [--notes N] [--date D]
    jobs.py applied list
    jobs.py message [--report R] [--top N] [--tip T]   a report as a WhatsApp/chat message, ready to send

candidates.json is a list of jobs, each:
    {"url", "site", "company", "title", "location", "posted", "workplace", "easy_apply", "experience",
     "score", "why": [...], "gaps": [...], "contacts": [{"name", "role", "profile", "email", "source"}]}
"site" is the job board it came from (linkedin, indeed, naukri, hirist, cutshort, wellfound,
internshala, foundit, instahyre, or anything else); left out, it is read from the url. Reports and messages
group the jobs by site.
A job matches a ledger row by its job id (LinkedIn's number, "indeed:<jk>", "naukri:<number>", ...), or by
company and title: boards repost a job under a new id, the same job is often on several boards, and
jobs applied to on a company site have no id at all.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tomllib

CONFIG = os.path.expanduser("~/.config/vishvakarma/job-hunt.toml")
APPLIED = ["date", "company", "title", "url", "job_id", "via", "contact", "status", "notes"]
SEEN = ["date", "company", "title", "url", "job_id", "score"]
NOISE = {"inc", "ltd", "llc", "llp", "pvt", "private", "limited", "corp", "corporation", "co", "plc", "gmbh"}
# The boards the skill searches, in the order reports and messages list them; anything else comes last.
SITES = {"linkedin": "LinkedIn", "indeed": "Indeed", "naukri": "Naukri", "hirist": "Hirist",
         "cutshort": "Cutshort", "wellfound": "Wellfound", "internshala": "Internshala", "foundit": "foundit", "instahyre": "Instahyre"}
# Each board's job link -> its id (kept as "<board>:<id>"; LinkedIn's stays a bare number, as the
# ledgers have always kept it).
IDS = [
    ("", r"(?:linkedin\.com/jobs/view/(?:[^/?#]*?-)?|currentJobId=)(\d{6,})"),
    ("indeed", r"indeed\.[a-z.]+/.*[?&](?:jk|vjk)=([0-9a-f]{8,})"),
    ("naukri", r"naukri\.com/job-listings-[^?#]*?-(\d{6,})(?:[/?#]|$)"),
    ("hirist", r"hirist\.[a-z]+/j/[^?#]*?-(\d{5,})(?:\.html)?(?:[/?#]|$)"),
    ("cutshort", r"cutshort\.io/job/[^?#]*-([A-Za-z0-9]{8})(?:[/?#]|$)"),
    ("wellfound", r"wellfound\.com/jobs/(\d{4,})"),
    ("internshala", r"internshala\.com/job/detail/[^?#]*?(\d{9,})(?:[/?#]|$)"),
    ("foundit", r"foundit\.in/job/[^?#]*?-(\d{6,})(?:[/?#]|$)"),
    ("instahyre", r"instahyre\.com/job-(\d{4,})-"),
]


def config(path=CONFIG):
    cfg = {}
    if os.path.exists(path):
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    cfg["data_dir"] = os.path.expanduser(cfg.get("data_dir", "~/Documents/job-hunt"))
    return cfg


def paths(data_dir):
    return {
        "dir": data_dir,
        "applied": os.path.join(data_dir, "applied.csv"),
        "seen": os.path.join(data_dir, "seen.csv"),
        "profile": os.path.join(data_dir, "profile.md"),
        "reports": os.path.join(data_dir, "reports"),
    }


def resume(data_dir):
    """The newest resume.* in the data folder, or None."""
    if not os.path.isdir(data_dir):
        return None
    found = [os.path.join(data_dir, n) for n in os.listdir(data_dir) if n.lower().startswith("resume.")]
    return max(found, key=os.path.getmtime) if found else None


def job_id(url):
    """The board's id for a job link: LinkedIn's bare number, "<board>:<id>" for the other boards
    (indeed:<jk>, naukri:<number>, ...); "" for a link that isn't a known board's job."""
    for board, pattern in IDS:
        m = re.search(pattern, url or "")
        if m:
            return f"{board}:{m.group(1)}" if board else m.group(1)
    return ""


def site(job):
    """Which board a job came from: its "site", else read from its link ("other" when neither says)."""
    named = (job.get("site") or "").strip().lower()
    if named:
        return named
    host = re.sub(r"^https?://", "", job.get("url") or "").split("/")[0].lower()
    for key in SITES:
        if key in host:
            return key
    return "other"


def site_name(key):
    return SITES.get(key) or ("Other sites" if key == "other" else key.title())


def by_site(jobs):
    """The jobs grouped by board, boards in SITES order (others after), each group in the given order."""
    order = list(SITES) + sorted({site(j) for j in jobs} - set(SITES) - {"other"}) + ["other"]
    groups = [(key, [j for j in jobs if site(j) == key]) for key in order]
    return [(key, js) for key, js in groups if js]


def norm(text):
    words = re.sub(r"[^a-z0-9+#]+", " ", (text or "").lower()).split()
    return " ".join(w for w in words if w not in NOISE)


def same(job, row):
    jid = job.get("job_id") or job_id(job.get("url", ""))
    if jid and jid == (row.get("job_id") or job_id(row.get("url", ""))):
        return True
    c, t = norm(job.get("company")), norm(job.get("title"))
    return bool(c and t) and c == norm(row.get("company")) and t == norm(row.get("title"))


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(path, fields, rows):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def split(jobs, applied, seen):
    """Sort found jobs into new, already applied, and shown before (deduplicated within the run too)."""
    out = {"new": [], "applied": [], "seen": []}
    kept = []
    for job in jobs:
        job = dict(job, job_id=job.get("job_id") or job_id(job.get("url", "")), site=site(job))
        if any(same(job, k) for k in kept):
            continue
        kept.append(job)
        hit = next((r for r in applied if same(job, r)), None)
        if hit:
            out["applied"].append(dict(job, applied_on=hit.get("date", ""), status=hit.get("status", "")))
            continue
        hit = next((r for r in seen if same(job, r)), None)
        if hit:
            out["seen"].append(dict(job, seen_on=hit.get("date", "")))
        else:
            out["new"].append(job)
    for key in ("new", "seen"):
        out[key].sort(key=lambda j: -float(j.get("score") or 0))
    return out


def contact_line(c):
    bits = [c.get("name") or "?"]
    if c.get("role"):
        bits.append(c["role"])
    line = " - ".join(bits)
    links = [x for x in (c.get("profile"), c.get("email")) if x]
    if links:
        line += " · " + " · ".join(links)
    if c.get("source"):
        line += f" _({c['source']})_"
    return line


def render(groups, today, profile_note=""):
    lines = [f"# Jobs - {today}", ""]
    if profile_note:
        lines += [profile_note, ""]
    lines += [f"{len(groups['new'])} new, {len(groups['seen'])} shown before and still open, "
              f"{len(groups['applied'])} skipped as already applied.", ""]

    def job_block(n, j, extra=""):
        head = f"### {n}. {j.get('title', '?')} - {j.get('company', '?')}"
        if j.get("score") not in (None, ""):
            head += f"  ({j['score']}/100)"
        out = [head + extra, "", j.get("url", "")]
        meta = [x for x in (j.get("location"), j.get("workplace"), j.get("experience"), j.get("posted")) if x]
        if j.get("easy_apply"):
            meta.append("Easy Apply")
        if meta:
            out.append(" · ".join(meta))
        out.append("")
        for label, key in (("Why it fits", "why"), ("Gaps", "gaps")):
            if j.get(key):
                out.append(f"**{label}:**")
                out += [f"- {x}" for x in j[key]]
                out.append("")
        if j.get("contacts"):
            out.append("**Who to reach:**")
            out += [f"- {contact_line(c)}" for c in j["contacts"]]
            out.append("")
        return out

    for title, jobs in (("", groups["new"]), ("Shown before, not applied yet", groups["seen"])):
        if not jobs:
            continue
        if title:
            lines += ["---", "", f"# {title}", ""]
        for key, js in by_site(jobs):
            lines += [f"## {site_name(key)} ({len(js)})", ""]
            for j in js:
                lines += job_block(j["n"], j, f"  _(first shown {j['seen_on']})_" if j.get("seen_on") else "")
    if groups["applied"]:
        lines += ["---", "", "# Skipped: already applied", ""]
        lines += [f"- {j.get('title')} - {j.get('company')} (applied {j.get('applied_on', '')})"
                  for j in groups["applied"]]
        lines.append("")
    return "\n".join(lines)


def number(groups):
    """Number the report's jobs in the order it shows them: new before shown-before, then by board,
    best first within a board. The numbers go in the report's .json as "n"."""
    n = 0
    for key in ("new", "seen"):
        for _, js in by_site(groups.get(key, [])):
            for j in js:
                n += 1
                j["n"] = n
    return groups


def pick(groups, top):
    """The jobs a message shows: the best `top` (new before shown-before, best first), grouped by board
    and numbered 1.. in that order, so the numbers the candidate sees run straight down the message."""
    best = (sorted(groups.get("new", []), key=lambda j: -float(j.get("score") or 0))
            + sorted(groups.get("seen", []), key=lambda j: -float(j.get("score") or 0)))[:top]
    out, n = [], 0
    for _, js in by_site(best):
        for j in js:
            n += 1
            out.append(dict(j, shown_n=n))
    return out


def chat_message(groups, day, top=10, tip=""):
    """The report's jobs as a chat message: WhatsApp formatting (*bold*), grouped under the board each
    job is on (a heading per board), one block per job, links in full."""
    jobs = pick(groups, top)
    if not jobs:
        return ""
    when = dt.date.fromisoformat(day).strftime("%-d %b") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else day
    out = [f"*💼 Jobs for you - {when}*", "Roles that match your resume, grouped by the site to apply on. "
           "Best ones first.", ""]
    for key, js in by_site(jobs):
        out += ["━━━━━━━━━━━━━━━", f"*🌐 {site_name(key).upper()}* ({len(js)})", ""]
        for j in js:
            out += job_lines(j)
    out[-1] = "━━━━━━━━━━━━━━━"
    if tip:
        out += ["", f"*👉 Tip:* {tip}"]
    return "\n".join(out)


def job_lines(j):
    """One job's block in a chat message, ending in a blank line."""
    out = [f"*{j['shown_n']}. {j.get('title', '?')} - {j.get('company', '?')}*"]
    place = " · ".join(x for x in (j.get("location"), j.get("workplace"), j.get("experience")) if x)
    if j.get("easy_apply"):
        place = (place + " · " if place else "") + "⚡ Easy Apply"
    if place:
        out.append(f"📍 {place}")
    if j.get("why"):
        out.append("✅ " + "; ".join(j["why"][:2]))
    if j.get("gaps"):
        out.append("⚠️ " + "; ".join(j["gaps"][:2]))
    if j.get("url"):
        out.append(f"🔗 {j['url']}")
    for c in (j.get("contacts") or [])[:2]:
        who = c.get("name", "?") + (f" - {c['role']}" if c.get("role") else "")
        out.append(f"👤 {who}")
        out += [x for x in (c.get("profile"), c.get("email")) if x]
    out.append("")
    return out


def latest_report(reports):
    found = sorted(n for n in os.listdir(reports) if n.endswith(".json")) if os.path.isdir(reports) else []
    found.sort(key=lambda n: os.path.getmtime(os.path.join(reports, n)))
    return os.path.join(reports, found[-1]) if found else None


def report_path(reports, today):
    os.makedirs(reports, exist_ok=True)
    path, n = os.path.join(reports, f"{today}.md"), 2
    while os.path.exists(path):
        path, n = os.path.join(reports, f"{today}-{n}.md"), n + 1
    return path


def read_jobs(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        sys.exit("candidates file must hold a JSON list of jobs")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    for name in ("filter", "report"):
        p = sub.add_parser(name)
        p.add_argument("candidates")
        p.add_argument("--note", default="", help="a line for the report's top (report only)")
    ap_applied = sub.add_parser("applied").add_subparsers(dest="action", required=True)
    add = ap_applied.add_parser("add")
    for flag in ("url", "company", "title", "via", "contact", "notes", "date"):
        add.add_argument(f"--{flag}", default="")
    add.add_argument("--status", default="applied")
    ap_applied.add_parser("list")
    msg = sub.add_parser("message")
    msg.add_argument("--report", default="", help="a report's .json (default: the latest)")
    msg.add_argument("--top", type=int, default=10)
    msg.add_argument("--tip", default="")
    a = ap.parse_args(argv)

    cfg = config(a.config)
    p = paths(cfg["data_dir"])
    today = dt.date.today().isoformat()

    if a.cmd == "init":
        os.makedirs(p["reports"], exist_ok=True)
        for key, fields in (("applied", APPLIED), ("seen", SEEN)):
            if not os.path.exists(p[key]):
                append(p[key], fields, [])
        print(f"ready: {p['dir']}")
        if not resume(p["dir"]):
            print(f"no resume yet: put it in {p['dir']} as resume.pdf, resume.md, resume.txt or resume.docx")
        return 0

    if a.cmd == "status":
        r = resume(p["dir"])
        stale = r and (not os.path.exists(p["profile"]) or os.path.getmtime(r) > os.path.getmtime(p["profile"]))
        print(json.dumps({
            "data_dir": p["dir"], "resume": r, "profile": p["profile"] if os.path.exists(p["profile"]) else None,
            "profile_stale": bool(stale), "applied": len(load(p["applied"])), "seen": len(load(p["seen"])),
            "config": a.config if os.path.exists(a.config) else None,
        }, indent=2))
        return 0

    if a.cmd in ("filter", "report"):
        groups = split(read_jobs(a.candidates), load(p["applied"]), load(p["seen"]))
        if a.cmd == "filter":
            print(json.dumps(groups, indent=2))
            return 0
        number(groups)
        path = report_path(p["reports"], today)
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(groups, today, a.note))
        with open(path[:-3] + ".json", "w", encoding="utf-8") as f:
            json.dump(dict(groups, date=today), f, indent=2, ensure_ascii=False)
        append(p["seen"], SEEN, [dict(j, date=today) for j in groups["new"]])
        print(path)
        return 0

    if a.cmd == "message":
        src = a.report or latest_report(p["reports"])
        if not src:
            sys.exit("no report yet: run a search first")
        with open(src, encoding="utf-8") as f:
            groups = json.load(f)
        text = chat_message(groups, groups.get("date", ""), a.top, a.tip)
        if not text:
            sys.exit(f"no jobs in {src}")
        # Keep what the message numbered, so "she applied to 2 and 5" finds the right jobs.
        groups["shown"] = [{k: j.get(k, "") for k in ("shown_n", "site", "company", "title", "url")}
                           for j in pick(groups, a.top)]
        with open(src, "w", encoding="utf-8") as f:
            json.dump(groups, f, indent=2, ensure_ascii=False)
        print(text)
        return 0

    if a.cmd == "applied" and a.action == "list":
        rows = load(p["applied"])
        for r in rows:
            print(f"{r['date']}  {r['company']} - {r['title']}  [{r.get('status', '')}]  {r.get('url', '')}")
        print(f"{len(rows)} applied")
        return 0

    if a.cmd == "applied" and a.action == "add":
        if not (a.company and a.title) and not job_id(a.url):
            sys.exit("need --company and --title (and --url when there is one)")
        row = {"date": a.date or today, "company": a.company, "title": a.title, "url": a.url,
               "job_id": job_id(a.url), "via": a.via, "contact": a.contact, "status": a.status, "notes": a.notes}
        hit = next((r for r in load(p["applied"]) if same(row, r)), None)
        if hit:
            print(f"already applied on {hit['date']}: {hit['company']} - {hit['title']}")
            return 1
        os.makedirs(p["dir"], exist_ok=True)
        append(p["applied"], APPLIED, [row])
        print(f"added: {row['company']} - {row['title']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
