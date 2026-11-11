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
    {"url", "company", "title", "location", "posted", "workplace", "easy_apply",
     "score", "why": [...], "gaps": [...], "contacts": [{"name", "role", "profile", "email", "source"}]}
A job matches a ledger row by its LinkedIn job id, or by company and title (LinkedIn reposts a job
under a new id, and jobs applied to off LinkedIn have none).
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
    m = re.search(r"(?:/jobs/view/(?:[^/?#]*?-)?|currentJobId=)(\d{6,})", url or "")
    return m.group(1) if m else ""


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
        job = dict(job, job_id=job.get("job_id") or job_id(job.get("url", "")))
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
        head = f"## {n}. {j.get('title', '?')} - {j.get('company', '?')}"
        if j.get("score") not in (None, ""):
            head += f"  ({j['score']}/100)"
        out = [head + extra, "", j.get("url", "")]
        meta = [x for x in (j.get("location"), j.get("workplace"), j.get("posted")) if x]
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

    n = 0
    for j in groups["new"]:
        n += 1
        lines += job_block(n, j)
    if groups["seen"]:
        lines += ["---", "", "# Shown before, not applied yet", ""]
        for j in groups["seen"]:
            n += 1
            lines += job_block(n, j, f"  _(first shown {j.get('seen_on', '')})_")
    if groups["applied"]:
        lines += ["---", "", "# Skipped: already applied", ""]
        lines += [f"- {j.get('title')} - {j.get('company')} (applied {j.get('applied_on', '')})"
                  for j in groups["applied"]]
        lines.append("")
    return "\n".join(lines)


def chat_message(groups, day, top=10, tip=""):
    """The report's jobs as a chat message: WhatsApp formatting (*bold*), one block per job, links in full."""
    jobs = (groups.get("new", []) + groups.get("seen", []))[:top]
    if not jobs:
        return ""
    when = dt.date.fromisoformat(day).strftime("%-d %b") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else day
    out = [f"*💼 Jobs for you - {when}*", "Roles that match your resume. Best ones first.", "", "━━━━━━━━━━━━━━━"]
    for n, j in enumerate(jobs, 1):
        out.append(f"*{n}. {j.get('title', '?')} - {j.get('company', '?')}*")
        place = " · ".join(x for x in (j.get("location"), j.get("workplace")) if x)
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
    out[-1] = "━━━━━━━━━━━━━━━"
    if tip:
        out += ["", f"*👉 Tip:* {tip}"]
    return "\n".join(out)


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
