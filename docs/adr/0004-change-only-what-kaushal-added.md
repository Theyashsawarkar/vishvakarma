# 4. Change only what vishvakarma added

**Status:** Accepted  
**Date:** 2026-10-28

## Context

The files vishvakarma writes are the user's: `~/.claude.json` holds Claude Code's whole state, `config.toml` the user's Codex settings, and they may already have their own skills and MCP servers, some with the same names as vishvakarma's. A sync that rewrote those files, or removed what it didn't recognise, would destroy work.

## Decision

- vishvakarma records what it added to each agent (`~/.local/state/vishvakarma/state.json`) and only ever changes or removes that.
- In text files it writes only inside its own marked block; in JSON files only its own keys.
- A skill folder or server of the user's with the same name wins; one identical to vishvakarma's is adopted.
- Files are written atomically, keep their permissions, and a TOML file is parsed before it's written.
- `vishvakarma unsync` takes back everything it added.

## Consequences

- Syncing is safe to run any time, as often as wanted, and changes nothing when nothing changed.
- Removing a skill or server from vishvakarma removes it from every agent on the next sync.
- A user's own server of the same name means that agent keeps theirs; `vishvakarma doctor` notes it rather than failing.
