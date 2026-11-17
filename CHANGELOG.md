# Changelog

Newest first. Releases are tags (`vX.Y.Z`) with `VERSION` in vishvakarma/__init__.py.

## v0.6.0 -- 2026-11-17

- `job-hunt` searches eight more boards besides LinkedIn: **Indeed** and **Naukri**, plus **Hirist** (tech-only), **Cutshort** and **Wellfound** (startups), **Internshala** (fresher and 0-2 year jobs), **foundit** (ex-Monster India) and **Instahyre** (curated, matched to the profile). They are listed as `sites` in `job-hunt.toml`, all nine by default.
  - Every board is used signed in. Each run checks the sign-ins first and asks the user to sign in where needed; it never types a password or code. A board's own picks for the signed-in profile (Instahyre's Opportunities, Naukri's recommended jobs, LinkedIn's top picks) are read only where that account is the candidate's (`candidate_accounts`).
  - Scoring now leans toward getting hired quickly: fresh postings with few applicants, a named recruiter, and boards whose recruiters reply. `scripts/boards.js` reads their result lists and job pages (each card comes with its job's own link) and spots captcha or access-denied pages.
  - Reports and chat messages group the job links by the site they came from: a heading per site, numbered straight down the message. `jobs.py message` records the numbers it showed (`shown` in the report's .json), so "she applied to 2 and 5" finds the right jobs.
  - Each board's job id is kept (`indeed:<jk>`, `naukri:<number>`, …; LinkedIn's stays a bare number, so old ledgers still match). The same job found on two boards is shown once, matched by company and title.
- New skill `network`: grows the user's network on LinkedIn and X in their own browser. It finds startup founders and CTOs, tech recruiters, engineers at target companies and developers in their stack (hiring posts first), scores each one and sends LinkedIn connection requests. It saves a short, specific note for the best few, because Free accounts get only a handful each month. On X it follows people and lists posts worth a reply; it never DMs, replies or likes.
  - **The ledger** (`contacted.csv`, kept by `scripts/net.py`): every person ever requested, followed, skipped or found already connected, under one key per person (`linkedin:<slug>`, `x:<handle>`) whatever URL form the page gives. The skill runs `net.py check` before each click and `net.py log` right after it, so no one is contacted twice. Only a failed click can be retried.
  - Safe limits per run, day and week (LinkedIn) and per day (X), notes per month, and a note-length check. It stops at once on any limit, captcha or security page (`__nwLimit()` in `scripts/social.js`), and writes a report per run.
- New skill `job-hunt`: browses LinkedIn in the user's own browser, at a person's pace, for jobs that fit their resume, scores each one (why it fits, what's missing) and finds the recruiters and hiring team. It keeps the resume, a profile drawn from it, the jobs already applied to and those already shown in a data folder (`~/Documents/job-hunt` by default), so no job comes up twice. `scripts/jobs.py` keeps the lists and writes each run's report. It only reads: it never applies, connects or messages unless asked, and never guesses an email.
  - It works with LinkedIn's 2026 job search: the filters go in the search words, and each card is opened to get its job id. `scripts/linkedin.js` reads the result list, a job (header, hiring team, requirements) and a people search.
  - It fetches the resume from WhatsApp or mail through narada, once.
  - `jobs.py message` turns a report into a chat message (one block per job: place, why, gaps, link, contacts), and the skill sends or schedules it through narada.

## v0.5.0 -- 2026-11-09

- **Vim keys in the app, with `Space` as the leader**, the grammar every Vayu tool shares ([ADR 8](docs/adr/0008-the-space-grammar.md)). It opens in NORMAL mode; the filter and a new skill's name are INSERT. Counts (`4j`, `5G`), `gg`, `Ctrl+d`/`Ctrl+u`, `H`/`L` for the tabs (`Tab`, `h`/`l` and `1`-`3` still work), `/` with `n`/`N`, `yy` copies the path, `dd` takes back from an agent.
- After `Space` a which-key strip shows what can follow (after 0.3 s); `Space Space` is a palette of every action; `?` lists the keys of the tab you're on, generated from the same table.
- `x` (off / on for every agent) now asks first, and every question takes only `y` as yes: a stray `Enter` changes nothing.
- Moved, and they say so for one release: a new skill is `Space a s` (`n` is the next match now), settings `Space e c` (was `c`), take back `dd` (was `u`), sync `Space r s` (was `s`), doctor `Space c d` (was `d`), test `Space c t` (was `t`).
- The keys are data (`BINDS` in `vishvakarma/tui.py`), resolved by Vyom's keys module, vendored as `vishvakarma/keys.py` (standard library only); `scripts/keybinds.py` writes the `# keybind:` lines and CI checks them and the README table.

## v0.4.2 -- 2026-11-06

- `dsr`: never a one-liner. Every work row is at least 5 sentences (what, why, how, what was checked, the outcome), all from work that really happened; `dsr_render.py` refuses a shorter row (`min_sentences` in dsr.toml; the lunch row is exempt).

## v0.4.1 -- 2026-11-05

- `tool-identity`: every corner is rounded, in every tool (`╭╮╰╯`, never `┌┐└┘` or `┏┓┗┛`), and so are the website's callouts.

## v0.4.0 -- 2026-11-03

- A logo and a shloka at the top of the README and the website: every Vayu tool has them now.
- New skills: `tool-identity` (every tool's name, logo and shloka) and `post-about-tool` (posts carry an image; terminal tools are shot in their own big terminal, on demo data).

## v0.3.1 -- 2026-11-02

- **dsr: one fixed structure, a thread per week, links to the commits.**
  The skill no longer studies past DSRs for their format: it's written
  down (greeting, date, the Time | Tasks table, the day's commits grouped
  by project, sign-off) and `dsr_render.py` produces it. Weeks run Monday
  to Saturday: Monday's DSR is a new mail with the week's subject
  (`subject_template`), Tuesday to Saturday reply to everyone in that
  thread; Sunday is refused. Recipients are `to` and `cc` in dsr.toml (a
  name alone is looked up once, then saved with its address).
- `dsr_commits.py` gives each commit its GitHub or GitLab link and whether
  it's pushed; `dsr_render.py --commits` puts the pushed, non-merge ones
  at the bottom and refuses unpushed ones (their links wouldn't open)
  unless `--skip-unpushed`. It also writes `send.json`: new or reply, the
  subject, the search for the week's thread, to and cc.

## v0.3.0 -- 2026-11-02

- **Renamed from kaushal to vishvakarma** (विश्वकर्मा, the divine craftsman). The
  command is `vishvakarma`, the repository
  github.com/Theyashsawarkar/vishvakarma (the old address redirects), the
  service `vishvakarma.service`. The first run moves your skills and settings
  (`~/.config/kaushal`) to `~/.config/vishvakarma`; Vayu's MCP servers it hands
  to agents carry their new names too (narada, vaikhari, dvarapala).

## v0.2.2 -- 2026-11-02

- Fixed the tests after darshan joined (v0.2.1 failed CI, nothing else changed).

## v0.2.1 -- 2026-11-02

- darshan joins the MCP servers: agents can show you a file and hear what you ask about it.

## v0.2.0 -- 2026-10-28

- **The app, `kaushal ui`**: every skill, tool and agent in three tabs, in
  the look of Vayu's other terminal tools. Read, edit (Vayu's: your own
  copy) and create skills, edit their settings; test a tool (start it, do
  the MCP handshake, list its tools); see what every agent has and what a
  sync would change; sync, doctor, turn things off, take back one agent's,
  all without leaving it. Follows varna's theme.
- **`kaushal off NAME` / `kaushal on NAME`**: turn a skill or tool off for
  every agent and back (`~/.config/kaushal/off.toml`).
- A launcher entry ("kaushal"), installed by install.sh.
- **A Skills page** on the website: every skill as a card, and a page for
  each with its full instructions and files, linked from every page's top
  bar. The README's skills list is now written from skills/, so it never
  misses one (`scripts/site.py`, around the shared site generator).

- **prasar** joins the MCP servers: agents can check, draft and propose
  posts for X and LinkedIn; every post waits for the user's approval.

- **A website**: theyashsawarkar.github.io/kaushal, built from the README,
  this changelog and seven decision records (docs/adr/) by the generator
  every Vayu tool shares; a how-it-works diagram; the README explains how
  kaushal works in Vayu.

## v0.1.0 -- 2026-10-28

- **Skills for every agent.** Skills are folders with a SKILL.md (the open
  Agent Skills format): Vayu's ship in `skills/`, yours go in
  `~/.config/kaushal/skills/` (`kaushal new NAME`). `kaushal sync` links
  them into Claude Code (every vesha profile shares them), Codex and the
  shared `~/.agents/skills`, which opencode and other agents read; agents
  that don't read skill folders get an index in their instructions file.
- **Tools for every agent.** `mcp.toml` lists Vayu's MCP servers (anumati,
  ekatva, sandesh, sangam); sync registers the installed ones with Claude
  Code (every profile, vesha's included), Codex, Gemini CLI and opencode.
  `{agent}` in args or env becomes the agent's name. Yours go in
  `~/.config/kaushal/mcp.toml`; `enabled = false` leaves one out.
- **Never touches what isn't its own**: what it added is recorded, a
  skill or server removed from kaushal is removed from the agents, a
  folder or server of yours with the same name is left alone, and
  `kaushal unsync` takes everything back. `kaushal doctor` checks it all.
- **Synced at login** (`kaushal.service`) and on install, so a new agent
  or account gets everything without asking.
- **The `dsr` skill**: the Daily Status Report, from the day's commits to
  an HTML table sent as a reply-all in the DSR thread, with scripts that
  collect the commits (`dsr_commits.py`) and check and render the
  timetable (`dsr_render.py`).
