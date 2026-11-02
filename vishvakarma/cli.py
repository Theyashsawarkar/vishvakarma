"""vishvakarma's commands."""
import os
import sys

from . import VERSION, ops
from .store import REPO, config_dir, move_former, servers, set_off, skills

HELP = f"""vishvakarma {VERSION}: skills and tools for every AI agent on this machine

  vishvakarma                 what there is: skills, MCP servers, agents
  vishvakarma ui              the app: every skill, tool and agent; sync, doctor, test, turn off
  vishvakarma sync [-n]       give every agent all of it (-n: only say what would change)
  vishvakarma doctor          check every agent has everything; exit 1 if not
  vishvakarma off NAME        turn a skill or tool off for every agent (`vishvakarma on NAME` undoes it)
  vishvakarma unsync          take back everything vishvakarma added
  vishvakarma new NAME        start a skill of your own in {os.path.join(config_dir(), "skills")}
  vishvakarma path [NAME]     where the skills (or one skill) live

Skills are folders with a SKILL.md (the open Agent Skills format): Vayu's
ship in {os.path.join(REPO, "skills")}, yours go in {os.path.join(config_dir(), "skills")}.
MCP servers come from mcp.toml there and in {config_dir()}."""


def run_sync(dry: bool, quiet: bool, take_back: bool = False) -> int:
    results, w = ops.sync(dry=dry, take_back=take_back)
    failed = 0
    for r in results:
        label = f"{r.target.agent.label} ({ops.short(r.target.path)})"
        if r.error:
            print(f"{label}: {r.error}", file=sys.stderr)
            failed += 1
        elif r.changes or not quiet:
            print(f"{label}: " + ("; ".join(r.changes) if r.changes else "up to date"))
    if w.missing and not quiet and not take_back:
        print("not installed, so not given to agents: " + ", ".join(f"{s.name} ({s.command})" for s in w.missing))
    return 1 if failed else 0


def doctor() -> int:
    notes, problems, summary = ops.diagnose()
    for n in notes:
        print("· " + n)
    for p in problems:
        print("✗ " + p)
    if not problems:
        print("✓ " + summary)
    return 1 if problems else 0


def overview() -> int:
    w = ops.wanted()
    print("Skills:")
    for s in w.all_skills:
        flag = f"  ✗ {'; '.join(s.problems)}" if s.problems else "  (off)" if s.name in w.off["skills"] else ""
        print(f"  {s.name:<16} {s.origin:<6} {s.description[:90]}{'…' if len(s.description) > 90 else ''}{flag}")
    if not w.all_skills:
        print("  (none)")
    print("MCP servers:")
    for s in w.all_servers:
        note = "  (off)" if s.name in w.off["servers"] else "" if s.installed() else "  (not installed)"
        print(f"  {s.name:<16} {s.command} {' '.join(s.args)}{note}")
    print("Agents: " + (", ".join(dict.fromkeys(t.agent.label for t in ops.targets())) or "none found"))
    return 0


SKELETON = """---
name: {name}
description: What this skill does and when an agent should use it (agents pick skills by this line).
---

# {name}

Steps the agent follows, in order. Put helper scripts in scripts/ and refer
to them by path relative to this file.
"""


def new_skill(name: str) -> str:
    """Creates ~/.config/vishvakarma/skills/NAME/SKILL.md from the template; returns its path."""
    folder = os.path.join(config_dir(), "skills", name)
    if os.path.exists(folder):
        raise FileExistsError(f"{ops.short(folder)} already exists")
    os.makedirs(folder)
    path = os.path.join(folder, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SKELETON.format(name=name))
    return path


def new(name: str) -> int:
    from .store import NAME_RE
    if not NAME_RE.match(name):
        print("vishvakarma: a skill's name is lowercase letters, digits and dashes", file=sys.stderr)
        return 1
    try:
        path = new_skill(name)
    except FileExistsError as e:
        print(f"vishvakarma: {e}", file=sys.stderr)
        return 1
    print(f"{ops.short(path)}: edit it, then `vishvakarma sync`")
    return 0


def kind_of(name: str) -> str | None:
    if any(s.name == name for s in skills()):
        return "skills"
    if any(s.name == name for s in servers()):
        return "servers"
    return None


def switch(name: str, is_off: bool) -> int:
    kind = kind_of(name)
    if not kind:
        print(f"vishvakarma: no skill or tool called {name}", file=sys.stderr)
        return 1
    set_off(kind, name, is_off)
    print(f"{name} {'off' if is_off else 'on'} for every agent")
    return run_sync(dry=False, quiet=True)


def main(argv: list[str]) -> int:
    move_former()
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if cmd == "--version":
        print(VERSION)
        return 0
    if "--help" in rest or "-h" in rest:
        print(HELP)
        return 0
    if cmd == "":
        return overview()
    if cmd == "ui":
        from .tui import run
        return run()
    if cmd == "sync":
        return run_sync(dry="-n" in rest or "--dry-run" in rest, quiet="-q" in rest or "--quiet" in rest)
    if cmd == "doctor":
        return doctor()
    if cmd == "unsync":
        return run_sync(dry="-n" in rest, quiet=False, take_back=True)
    if cmd in ("off", "on") and len(rest) == 1:
        return switch(rest[0], cmd == "off")
    if cmd == "new" and len(rest) == 1:
        return new(rest[0])
    if cmd == "path":
        if rest:
            match = [s for s in skills() if s.name == rest[0]]
            if not match:
                print(f"vishvakarma: no skill {rest[0]}", file=sys.stderr)
                return 1
            print(match[0].path)
        else:
            print(os.path.join(REPO, "skills"))
            print(os.path.join(config_dir(), "skills"))
        return 0
    print(f"vishvakarma: unknown command {cmd!r}\n\n{HELP}", file=sys.stderr)
    return 2
