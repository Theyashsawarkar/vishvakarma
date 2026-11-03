---
name: post-about-tool
description: Write and publish a social post (LinkedIn, X) about a tool, project or anything else with something to show, with its image attached. Use whenever the user asks to post, announce, share or write about a tool or project on LinkedIn or X, through vaikhari. Covers finding or taking the image; terminal tools are shot in their own big terminal, never from the user's real data or desktop.
---

# Posting about a tool

A post about something should show it. Attach the associated image whenever
one can exist; post without one only if the user says so or nothing can be
shown, and say so when you do.

## 1. Check it can go out

Call `post_accounts`. If a network isn't ready, save a draft with `post_draft`,
tell the user what's missing, and stop.

## 2. Get the facts

Read the tool's README. Every claim in the post must be true of the tool as it
is now, down to defaults and numbers. Anything written as the user's personal
experience is your guess: point it out so they can change it.

Lead with what makes the tool what it is. If agents can use it (an MCP server),
the post says so plainly: Vayu's tools are agent-first.

## 3. Get the image

Public posts must never show real data: no real mail, names, messages, repos,
clients, accounts or desktops.

- **A terminal tool**: run it in its own big terminal and shoot that, so it
  reads well on a phone: 1920x1080, a font around 13pt. Use its demo mode
  (`<tool> demo`) or made-up data. Never shoot the user's desktop or their
  own session of the tool.
- **A GUI, website or phone app**: its demo mode, or public-domain or made-up
  content. On a phone, only with the user's agreement to use it.
- **Otherwise**: the tool's `assets/screenshots/`, if they're current; else its
  logo.

Shoot on a private headless screen, never on the user's live desktop. The order
of these lines matters: the runtime folder is set BEFORE the private bus starts,
or its services overwrite the user's real accessibility bus.

```sh
export XDG_RUNTIME_DIR=/run/user/$UID/vs      # short: sway's socket path must fit
rm -rf "$XDG_RUNTIME_DIR"; mkdir -m700 -p "$XDG_RUNTIME_DIR"
unset SWAYSOCK I3SOCK WAYLAND_DISPLAY DISPLAY LD_PRELOAD TMUX TMUX_PANE
export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman
export GTK_A11Y=none NO_AT_BRIDGE=1 GDK_DEBUG=no-portals GTK_USE_PORTAL=0
cat > "$XDG_RUNTIME_DIR/cfg" <<CFG
output HEADLESS-1 resolution 1920x1080 scale 1
default_border none
exec kitty -o font_size=13 -o window_padding_width=12 <tool> demo
CFG
dbus-run-session -- sh -c '
  sway -c "$XDG_RUNTIME_DIR/cfg" & pid=$!
  sleep 5
  WAYLAND_DISPLAY=$(ls "$XDG_RUNTIME_DIR" | grep -m1 "^wayland-[0-9]*$") grim "$OUT"
  kill $pid'
rm -rf "$XDG_RUNTIME_DIR"
```

Set `OUT` to an absolute path. Never run a bare `swaymsg` or `pkill sway` here:
they can reach the user's real desktop. Keep the image somewhere that lasts
until the post goes out, not a temporary folder.

**Look at the image before attaching it**, every time. Read every name and line
in it. If anything could be real, don't use it.

## 4. Write it, check it, publish it

Write in the user's voice, and always use emojis: they make a post easier to read
and catch the eye. Open with one, and start each list item or short section with
one that suits it (not a row of them, and not one on every sentence). X counts each
emoji as two characters. `post_check` it: lengths, X's thread split, and where
LinkedIn folds at "…see more" (the opening has to earn the click).

Then `post_publish` with `images`, and a `note` saying why this post. The user
approves every post in a popup and may edit it. Never claim it went out unless
the result says so; give them the link it returns. X needs the user's own click
on X's page, so an X post is waiting until they confirm it.
