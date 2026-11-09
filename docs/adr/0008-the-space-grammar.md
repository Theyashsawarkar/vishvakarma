# 8. The app speaks the Space grammar

**Status:** Accepted  
**Date:** 2026-11-09

## Context

The app had keys of its own: one letter per action (`s` sync, `d` doctor, `n` new skill, `u` take back, `x` off/on with no question), a single `g` for the top, `h`/`l` for tabs. Every Vayu tool had picked its letters separately, so the same key meant different things one popup apart (`d` deleted in one tool and ran the doctor here; `u` undid in one and took back here), and `x` changed every agent on one key press.

## Decision

The app follows the grammar every Vayu tool shares (Vyom ADR 8; vesha ADR 10 is the same change in its sibling switcher): NORMAL mode by default and INSERT only in the filter and the name prompt; `Space` is the leader, and its groups mean the same thing everywhere (`t` tabs, `f` find, `a` add, `e` edit, `d` delete, `r` refresh, `m` mark, `y` copy, `o` open, `Space` the palette). `c` is a free letter, used for this app's own group, "check" (`Space c d` doctor, `Space c t` test). `H`/`L` switch tabs, `1`-`3` still do (so a count starts at 4). Anything that changes every agent asks first, and only `y` says yes.

The keys are data (`BINDS` in `vishvakarma/tui.py`), resolved by Vyom's keys module, vendored as `vishvakarma/keys.py` (standard library only, so vishvakarma keeps no dependencies). Help, palette, which-key strip and the `# keybind:` lines all come from that table; `scripts/keybinds.py --check` keeps the annotations in step, and CI checks the README lists every key.

## Consequences

- Six keys moved (`n` `c` `u` `s` `d` `t`); for one release each says where it went.
- `x` asks first; a stray `Enter` on a question changes nothing.
- A change to the shared grammar reaches vishvakarma by vendoring keys.py again (`vendor-keys.sh --check` finds a stale copy).
