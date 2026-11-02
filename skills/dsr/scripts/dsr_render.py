#!/usr/bin/env python3
"""Checks a Daily Status Report and writes it in its one fixed structure, as
plain text and as HTML (email clients show the table; the text is its
fallback), plus how to send it this day of the week.

  dsr_render.py ROWS.json [--start "11:30 AM"] [--end "09:00 PM"]
                [--commits COMMITS.json] [--skip-unpushed] [--out DIR]

ROWS.json: {"date": "26/10/2026", "rows": [["11:30 AM", "01:00 PM", "Worked on ..."], ...]}
(date also as YYYY-MM-DD). COMMITS.json: `dsr_commits.py DATE --json`; its
pushed, non-merge commits become the links at the bottom.

Exits 2 listing every problem, unless: the date isn't a Sunday (DSR weeks
run Monday to Saturday); the rows run back to back with no gap or overlap,
each ends after it starts; the day starts at --start and ends at --end when
given; the lunch break from ~/.config/vishvakarma/dsr.toml (default 01:00 PM to
02:00 PM) is a row of its own when the day spans it; every commit has a web
link and is pushed (--skip-unpushed leaves unpushed ones out instead).

Writes DIR/dsr.txt, DIR/dsr.html and DIR/send.json (DIR defaults to the
folder of ROWS.json) and prints the table and the send plan.
"""
import argparse
import datetime as dt
import html
import json
import os
import subprocess
import sys
import tomllib

CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "vishvakarma", "dsr.toml")
SUBJECT = "Daily Status Report: {week_start} to {week_end}"
FONT = "font-family:Arial,sans-serif;font-size:14px"
TD = f"border:1px solid #999;padding:6px 10px;vertical-align:top;{FONT}"
TH = TD.replace("vertical-align:top", "background:#f2f2f2;text-align:left")


def settings() -> dict:
    try:
        with open(CONFIG, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def clock(text: str) -> dt.datetime:
    t = " ".join(text.strip().upper().replace(".", "").split())
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return dt.datetime.strptime(t, fmt)
        except ValueError:
            pass
    raise ValueError(f"can't read the time {text!r} (like 11:30 AM)")


def show(t: dt.datetime) -> str:
    return t.strftime("%I:%M %p")


def parse_date(text: str) -> dt.date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"can't read the date {text!r}")


def week(day: dt.date) -> tuple[dt.date, dt.date]:
    """The DSR week a day belongs to: its Monday and Saturday."""
    monday = day - dt.timedelta(days=day.weekday())
    return monday, monday + dt.timedelta(days=5)


def check(rows: list[tuple[dt.datetime, dt.datetime, str]], start: str | None, end: str | None, lunch: str | None,
          lunch_task: str) -> list[str]:
    problems = []
    if not rows:
        return ["no rows"]
    for i, (a, b, task) in enumerate(rows):
        if b <= a:
            problems.append(f"row {i + 1} ({show(a)} to {show(b)}) ends before it starts")
        if not task.strip():
            problems.append(f"row {i + 1} has no task")
        if i and rows[i - 1][1] != a:
            gap = "a gap" if rows[i - 1][1] < a else "an overlap"
            problems.append(f"{gap} between {show(rows[i - 1][1])} and {show(a)} (rows {i} and {i + 1})")
    if start and rows[0][0] != clock(start):
        problems.append(f"the day starts at {show(rows[0][0])}, not {show(clock(start))}")
    if end and rows[-1][1] != clock(end):
        problems.append(f"the day ends at {show(rows[-1][1])}, not {show(clock(end))}")
    if lunch:
        la, lb = (clock(x) for x in lunch.split(" to "))
        if rows[0][0] < la and rows[-1][1] > lb and not any(a == la and b == lb and t.strip() == lunch_task for a, b, t in rows):
            problems.append(f"no \"{lunch_task}\" row from {show(la)} to {show(lb)}")
    return problems


def links(data: dict | None, skip_unpushed: bool) -> tuple[list[tuple[str, str, str]], list[str], list[str]]:
    """(project, subject, url) of each pushed, non-merge commit, oldest
    first; the problems; the commits left out."""
    out, problems, left_out = [], [], []
    for repo, found in ((data or {}).get("repos") or {}).items():
        for c in found:
            if c.get("merge"):
                continue
            name = f"{c.get('project') or os.path.basename(repo)}: {c['subject']}"
            if not c.get("url"):
                problems.append(f"{name}: no web link (its origin remote isn't GitHub or GitLab)")
            elif not c.get("pushed"):
                (left_out if skip_unpushed else problems).append(
                    f"{name}: not pushed, so its link won't open" + ("" if skip_unpushed else
                                                                      " (push it, or pass --skip-unpushed)"))
            else:
                out.append((c.get("time", ""), c.get("project") or os.path.basename(repo), c["subject"], c["url"]))
    out.sort()
    return [x[1:] for x in out], problems, left_out


def signoff(cfg: dict) -> list[str]:
    if cfg.get("signoff"):
        return [line for line in str(cfg["signoff"]).splitlines() if line.strip()]
    name = cfg.get("name") or subprocess.run(["git", "config", "--global", "user.name"],
                                             capture_output=True, text=True).stdout.strip()
    return ["Regards,", name] if name else ["Regards,"]


def render(date: str, rows, greeting: str, commits=(), closing=("Regards,",)) -> tuple[str, str]:
    """The DSR, always the same structure: greeting, date, the Time | Tasks
    table, the day's commits (grouped by project), the sign-off."""
    projects: dict[str, list[tuple[str, str]]] = {}
    for project, subject, url in commits:
        projects.setdefault(project, []).append((subject, url))
    plain = f"{greeting}\n\nDate : {date}\n\nTime\tTasks\n" + "".join(f"{show(a)} to {show(b)}\t{t}\n" for a, b, t in rows)
    trs = "\n".join(f'<tr><td style="{TD}" nowrap>{show(a)} to {show(b)}</td><td style="{TD}">{html.escape(t)}</td></tr>'
                    for a, b, t in rows)
    page = (f'<div style="{FONT}">\n<p>{html.escape(greeting)}</p>\n<p>Date : {date}</p>\n'
            f'<table style="border-collapse:collapse" cellpadding="0" cellspacing="0">\n'
            f'<tr><th style="{TH}">Time</th><th style="{TH}">Tasks</th></tr>\n{trs}\n</table>\n')
    if projects:
        plain += "\nCommits:\n"
        page += "<p><b>Commits:</b></p>\n"
        for project, items in projects.items():
            plain += f"\n{project}\n" + "".join(f"- {s}\n  {u}\n" for s, u in items)
            page += (f"<p>{html.escape(project)}</p>\n<ul>\n"
                     + "".join(f'<li><a href="{html.escape(u)}">{html.escape(s)}</a></li>\n' for s, u in items) + "</ul>\n")
    plain += "\n" + "\n".join(closing) + "\n"
    page += "<p>" + "<br>\n".join(html.escape(line) for line in closing) + "</p>\n</div>\n"
    return plain, page


def plan(day: dt.date, cfg: dict) -> dict:
    """How this day's DSR goes out: Monday starts the week's thread, every
    other day replies to everyone in it."""
    monday, saturday = week(day)
    subject = cfg.get("subject_template", SUBJECT).format(
        week_start=f"{monday:%d/%m/%Y}", week_end=f"{saturday:%d/%m/%Y}", date=f"{day:%d/%m/%Y}")
    to, cc = list(cfg.get("to") or []), list(cfg.get("cc") or [])
    return {"date": f"{day:%d/%m/%Y}", "weekday": f"{day:%A}", "subject": subject,
            "mode": "new" if day == monday else "reply",
            "thread_query": f'in:sent subject:"{subject}"', "to": to, "cc": cc,
            "unresolved": [r for r in to + cc if "@" not in r]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rows")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--commits")
    ap.add_argument("--skip-unpushed", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = settings()
    try:
        with open(a.rows, encoding="utf-8") as f:
            data = json.load(f)
        day = parse_date(data["date"])
        rows = [(clock(r[0]), clock(r[1]), str(r[2])) for r in data["rows"]]
        commit_data = None
        if a.commits:
            with open(a.commits, encoding="utf-8") as f:
                commit_data = json.load(f)
    except (OSError, KeyError, IndexError, TypeError, ValueError) as e:
        print(f"dsr_render: {e}", file=sys.stderr)
        return 2
    lunch_task = cfg.get("lunch_task", "Lunch Break")
    problems = [] if day.weekday() != 6 else [f"{day:%d/%m/%Y} is a Sunday: DSR weeks run Monday to Saturday"]
    problems += check(rows, a.start, a.end, cfg.get("lunch", "01:00 PM to 02:00 PM") or None, lunch_task)
    commits, link_problems, left_out = links(commit_data, a.skip_unpushed)
    problems += link_problems
    if problems:
        print("dsr_render: fix these and run it again:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 2
    plain, page = render(f"{day:%d/%m/%Y}", rows, cfg.get("greeting", "Hello,"), commits, signoff(cfg))
    send = plan(day, cfg)
    out = a.out or os.path.dirname(os.path.abspath(a.rows))
    os.makedirs(out, exist_ok=True)
    for name, text in (("dsr.txt", plain), ("dsr.html", page), ("send.json", json.dumps(send, indent=2) + "\n")):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    print(plain)
    for c in left_out:
        print(f"left out: {c}")
    how = ("a NEW mail (Monday starts the week's thread)" if send["mode"] == "new"
           else "REPLY-ALL in the week's thread (to the previous DSR)")
    print(f"send: {send['weekday']} {send['date']}, {how}\n  subject: {send['subject']}\n"
          f"  to: {', '.join(send['to']) or '(none set)'}\n  cc: {', '.join(send['cc']) or '(none)'}")
    if send["unresolved"]:
        print(f"  no address yet for: {', '.join(send['unresolved'])}")
    print(f"\nwrote dsr.txt, dsr.html and send.json in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
