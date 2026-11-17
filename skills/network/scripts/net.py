#!/usr/bin/env python3
"""The network skill's ledger: everyone ever sent a connection request, followed or skipped, on
LinkedIn and X, so no one is contacted twice, and the limits that keep the account safe.

    net.py init                         make the data folder
    net.py status                       profile, what was sent today / this week / this month, what is left
    net.py filter people.json           split found people into new / already in the ledger / excluded
    net.py check --platform P --profile URL       exit 0 if the person is new, 1 if already contacted
    net.py log --platform P --profile URL --action A --status S [--name --headline --company
               --category --score --note --why]   record one action, right after doing it
    net.py mark --platform P --profile URL --status S   change a row's status (accepted, withdrawn...)
    net.py note-check "text"            is a connection note within the limit?
    net.py list [--platform P] [--days N]
    net.py report --since TS [--engage engage.json] [--note N]   the run's report (Markdown)

A person is one key: "linkedin:<profile slug>" or "x:<handle>", lowercased, whatever URL form is
given (www., mobile, query strings, /recent-activity/...). Every status blocks a second contact
except "failed" (a click that did not go through), which may be tried again.

people.json is a list of {"platform", "profile", "name", "headline", "company", "category",
"score", "why"}; engage.json a list of {"profile", "name", "url", "text", "reply_idea"}.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tomllib
import urllib.parse

CONFIG = os.path.expanduser("~/.config/vishvakarma/network.toml")
FIELDS = ["ts", "platform", "key", "profile", "name", "headline", "company", "category", "score",
          "action", "note", "status", "why"]
ACTIONS = {"connect", "follow", "skip"}
STATUSES = {"sent", "followed", "pending", "accepted", "already", "skipped", "failed", "withdrawn"}
RETRY = {"failed"}
DEFAULTS = {
    "data_dir": "~/Documents/network",
    "linkedin_per_run": 15, "linkedin_per_day": 20, "linkedin_per_week": 80,
    "notes_per_month": 5, "note_chars": 200,
    "x_per_run": 15, "x_per_day": 25,
    "min_score": 55, "exclude_companies": [], "exclude_people": [],
}
X_RESERVED = {"home", "explore", "search", "i", "notifications", "messages", "settings", "intent", "share",
              "compose", "hashtag", "tos", "privacy", "login", "signup"}


def config(path=CONFIG):
    cfg = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path, "rb") as f:
            cfg.update(tomllib.load(f))
    cfg["data_dir"] = os.path.expanduser(cfg["data_dir"])
    return cfg


def paths(data_dir):
    return {"dir": data_dir, "ledger": os.path.join(data_dir, "contacted.csv"),
            "profile": os.path.join(data_dir, "profile.md"), "reports": os.path.join(data_dir, "reports")}


def key(platform, profile):
    """The one key for a person, or "" if the profile can't be read."""
    platform = (platform or "").lower().strip()
    s = urllib.parse.unquote((profile or "").strip()).lower()
    if platform == "linkedin":
        m = re.search(r"linkedin\.com/in/([^/?#\s]+)", s) or re.fullmatch(r"([a-z0-9][\w-]{1,99})", s)
        return f"linkedin:{m.group(1)}" if m else ""
    if platform == "x":
        m = re.search(r"(?:x|twitter)\.com/([a-z0-9_]{1,15})(?:[/?#]|$)", s) or re.fullmatch(r"@?([a-z0-9_]{1,15})", s)
        return f"x:{m.group(1)}" if m and m.group(1) not in X_RESERVED else ""
    return ""


def canonical(platform, k):
    slug = k.split(":", 1)[1]
    return f"https://www.linkedin.com/in/{slug}/" if platform == "linkedin" else f"https://x.com/{slug}"


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def append(path, row):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def blocking(rows, k):
    """The ledger row that stops a new contact with this person, or None."""
    hits = [r for r in rows if r.get("key") == k and r.get("status") not in RETRY]
    return hits[-1] if hits else None


def norm(text):
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", (text or "").lower()).split())


def excluded(person, cfg):
    company = norm(person.get("company")) + " " + norm(person.get("headline"))
    for c in cfg.get("exclude_companies", []):
        if norm(c) and re.search(rf"\b{re.escape(norm(c))}\b", company):
            return f"works at {c}"
    for p in cfg.get("exclude_people", []):
        if key(person.get("platform"), p) and key(person.get("platform"), p) == person.get("key"):
            return "on exclude_people"
    return ""


def split(people, rows, cfg):
    out = {"new": [], "done": [], "excluded": []}
    taken = set()
    for p in people:
        k = key(p.get("platform"), p.get("profile"))
        if not k or k in taken:
            continue
        taken.add(k)
        p = dict(p, key=k, profile=canonical(p["platform"].lower(), k))
        hit = blocking(rows, k)
        why = excluded(p, cfg)
        if hit:
            out["done"].append(dict(p, last=f"{hit['action']} {hit['status']} {hit['ts'][:10]}"))
        elif why:
            out["excluded"].append(dict(p, reason=why))
        elif float(p.get("score") or 0) < float(cfg["min_score"]):
            out["excluded"].append(dict(p, reason=f"score under {cfg['min_score']}"))
        else:
            out["new"].append(p)
    out["new"].sort(key=lambda p: -float(p.get("score") or 0))
    return out


def ts_of(row):
    try:
        return dt.datetime.fromisoformat(row["ts"])
    except (KeyError, ValueError):
        return dt.datetime.min


def usage(rows, cfg, now):
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week, month = now - dt.timedelta(days=7), day.replace(day=1)
    sent = [r for r in rows if r["platform"] == "linkedin" and r["action"] == "connect"
            and r["status"] in ("sent", "pending", "accepted", "withdrawn")]
    follows = [r for r in rows if r["platform"] == "x" and r["action"] == "follow" and r["status"] == "followed"]
    used = {
        "linkedin_today": sum(ts_of(r) >= day for r in sent),
        "linkedin_week": sum(ts_of(r) >= week for r in sent),
        "notes_month": sum(ts_of(r) >= month and bool(r.get("note")) for r in sent),
        "x_today": sum(ts_of(r) >= day for r in follows),
    }
    left = {
        "linkedin": max(0, min(cfg["linkedin_per_run"], cfg["linkedin_per_day"] - used["linkedin_today"],
                               cfg["linkedin_per_week"] - used["linkedin_week"])),
        "notes": max(0, cfg["notes_per_month"] - used["notes_month"]),
        "x": max(0, min(cfg["x_per_run"], cfg["x_per_day"] - used["x_today"])),
    }
    return used, left


def note_problem(text, limit):
    text = text or ""
    if len(text) > limit:
        return f"{len(text)} characters, the limit is {limit}: cut {len(text) - limit}"
    if re.search(r"\{|\}|\[name\]|<name>|lorem", text, re.I):
        return "still holds a placeholder"
    return ""


def render(rows, engage, since, note=""):
    lines = [f"# Networking run - {since[:16].replace('T', ' ')}", ""]
    if note:
        lines += [note, ""]
    by = lambda pred: [r for r in rows if pred(r)]
    li = by(lambda r: r["platform"] == "linkedin" and r["action"] == "connect" and r["status"] in ("sent", "pending"))
    xf = by(lambda r: r["platform"] == "x" and r["status"] == "followed")
    other = by(lambda r: r not in li and r not in xf)
    lines += [f"{len(li)} LinkedIn requests ({sum(bool(r['note']) for r in li)} with a note), "
              f"{len(xf)} followed on X, {len(other)} skipped, already connected or failed.", ""]

    def people(title, group):
        if not group:
            return []
        out = [f"## {title}", ""]
        for r in group:
            head = f"- **{r['name'] or '?'}**"
            if r.get("headline"):
                head += f" - {r['headline'][:90]}"
            out.append(f"{head}  ({r['category'] or '?'}, {r['score'] or '?'}/100)")
            out.append(f"  {r['profile']}")
            if r.get("why"):
                out.append(f"  Why: {r['why']}")
            if r.get("note"):
                out.append(f"  Note: \"{r['note']}\"")
        return out + [""]

    lines += people("LinkedIn requests sent", li)
    lines += people("Followed on X", xf)
    if engage:
        lines += ["## Worth a reply on X", "", "Reply in your own words; a useful reply beats a compliment.", ""]
        for e in engage:
            lines.append(f"- **{e.get('name', '?')}**: {(e.get('text') or '').strip()[:160]}")
            lines.append(f"  {e.get('url', '')}")
            if e.get("reply_idea"):
                lines.append(f"  Idea: {e['reply_idea']}")
        lines.append("")
    if other:
        lines += ["## Not contacted", ""]
        lines += [f"- {r['name'] or r['key']} ({r['platform']}): {r['status']}"
                  + (f" - {r['why']}" if r.get("why") else "") for r in other]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("filter").add_argument("people")
    for name in ("check", "log", "mark"):
        p = sub.add_parser(name)
        p.add_argument("--platform", required=True, choices=["linkedin", "x"])
        p.add_argument("--profile", required=True)
        if name != "check":
            p.add_argument("--status", required=name == "mark", choices=sorted(STATUSES))
        if name == "log":
            p.add_argument("--action", required=True, choices=sorted(ACTIONS))
            for flag in ("name", "headline", "company", "category", "score", "note", "why"):
                p.add_argument(f"--{flag}", default="")
    sub.add_parser("note-check").add_argument("text")
    ls = sub.add_parser("list")
    ls.add_argument("--platform", choices=["linkedin", "x"])
    ls.add_argument("--days", type=int, default=0)
    rp = sub.add_parser("report")
    rp.add_argument("--since", required=True, help="the run's start, from status's \"now\"")
    rp.add_argument("--engage", default="")
    rp.add_argument("--note", default="")
    a = ap.parse_args(argv)

    cfg = config(a.config)
    p = paths(cfg["data_dir"])
    rows = load(p["ledger"])
    now = dt.datetime.now().replace(microsecond=0)

    if a.cmd == "init":
        os.makedirs(p["reports"], exist_ok=True)
        if not os.path.exists(p["ledger"]):
            save(p["ledger"], [])
        print(f"ready: {p['dir']}")
        return 0

    if a.cmd == "status":
        used, left = usage(rows, cfg, now)
        print(json.dumps({
            "now": now.isoformat(), "data_dir": p["dir"],
            "profile": p["profile"] if os.path.exists(p["profile"]) else None,
            "config": a.config if os.path.exists(a.config) else None,
            "in_ledger": {"linkedin": sum(r["platform"] == "linkedin" for r in rows),
                          "x": sum(r["platform"] == "x" for r in rows)},
            "used": used, "left_this_run": left, "note_chars": cfg["note_chars"], "min_score": cfg["min_score"],
        }, indent=2))
        return 0

    if a.cmd == "filter":
        with open(a.people, encoding="utf-8") as f:
            people = json.load(f)
        if not isinstance(people, list):
            sys.exit("people file must hold a JSON list")
        print(json.dumps(split(people, rows, cfg), indent=2, ensure_ascii=False))
        return 0

    if a.cmd == "note-check":
        problem = note_problem(a.text, cfg["note_chars"])
        print(problem or f"ok: {len(a.text)}/{cfg['note_chars']} characters")
        return 1 if problem else 0

    if a.cmd in ("check", "log", "mark"):
        k = key(a.platform, a.profile)
        if not k:
            sys.exit(f"can't read a {a.platform} profile from {a.profile!r}")
        hit = blocking(rows, k)
        if a.cmd == "check":
            if hit:
                print(f"already: {hit['action']} {hit['status']} on {hit['ts'][:10]} ({hit['name']})")
                return 1
            print("new")
            return 0
        if a.cmd == "mark":
            mine = [r for r in rows if r["key"] == k]
            if not mine:
                sys.exit(f"{k} is not in the ledger")
            mine[-1]["status"] = a.status
            save(p["ledger"], rows)
            print(f"{k}: {a.status}")
            return 0
        if hit:
            print(f"already in the ledger: {hit['action']} {hit['status']} on {hit['ts'][:10]}; not logged again")
            return 1
        status = a.status or {"connect": "sent", "follow": "followed", "skip": "skipped"}[a.action]
        if a.note and (problem := note_problem(a.note, cfg["note_chars"])):
            sys.exit(f"note: {problem}")
        os.makedirs(p["dir"], exist_ok=True)
        append(p["ledger"], {"ts": now.isoformat(), "platform": a.platform, "key": k,
                             "profile": canonical(a.platform, k), "name": a.name, "headline": a.headline,
                             "company": a.company, "category": a.category, "score": a.score,
                             "action": a.action, "note": a.note, "status": status, "why": a.why})
        print(f"logged: {k} {a.action} {status}")
        return 0

    if a.cmd == "list":
        cut = now - dt.timedelta(days=a.days) if a.days else dt.datetime.min
        shown = [r for r in rows if (not a.platform or r["platform"] == a.platform) and ts_of(r) >= cut]
        for r in shown:
            print(f"{r['ts'][:16]}  {r['platform']:8} {r['action']:7} {r['status']:9} {r['name'] or '?'}  {r['profile']}")
        print(f"{len(shown)} rows")
        return 0

    if a.cmd == "report":
        since = dt.datetime.fromisoformat(a.since)
        run = [r for r in rows if ts_of(r) >= since]
        engage = []
        if a.engage:
            with open(a.engage, encoding="utf-8") as f:
                engage = json.load(f)
        os.makedirs(p["reports"], exist_ok=True)
        path, n = os.path.join(p["reports"], f"{since.date()}.md"), 2
        while os.path.exists(path):
            path, n = os.path.join(p["reports"], f"{since.date()}-{n}.md"), n + 1
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(run, engage, a.since, a.note))
        print(path)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
