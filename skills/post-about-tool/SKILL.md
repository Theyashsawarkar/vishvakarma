---
name: post-about-tool
description: Write and publish a social post (LinkedIn, X) about a tool, project or anything else with something to show, with its image attached, through the user's own browser with sutradhar. Use whenever the user asks to post, announce, share or write about a tool or project on LinkedIn or X. Covers getting the facts, finding or taking the image (never from the user's real data or desktop), checking lengths and the "see more" fold with scripts/check.py, and composing, attaching and publishing on each site.
---

# Posting about a tool

A post about something should show it. Attach the associated image whenever
one can exist; post without one only if the user says so or nothing can be
shown, and say so when you do.

Posts go out through **sutradhar**, in the user's own browser where they are
signed in to LinkedIn and X. Read the `sutradhar` skill first if you haven't:
the snapshot → act loop, refs, uploads and approvals are explained there.

## 1. Check it can go out

`browsers` must show a connected browser. Open each site (`navigate` to
`https://www.linkedin.com/feed/` and `https://x.com/home`) and `snapshot`: if a
sign-in page shows, `handoff {"task": "Sign in to LinkedIn", "why": "…"}` and
wait. Never type the user's password or codes.

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
- **A GUI, website, browser extension or phone app**: its demo mode, a demo
  page with made-up content, or public-domain content. A browser tool is shot
  in a throwaway headless browser profile (the tool's own test harness, if it
  has one), never the user's browser. On a phone, only with the user's
  agreement to use it.
- **A diagram** from the tool's README (`assets/diagrams/`) makes a good second
  image; render its SVG to PNG (`rsvg-convert -w 2000`).
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
until the post goes out (`~/Pictures/<tool>-post/`), not a temporary folder.

**Look at the image before attaching it**, every time. Read every name and line
in it. If anything could be real, don't use it.

## 4. Write it and check it

Write in the user's voice, and always use emojis: they make a post easier to read
and catch the eye. Open with one, and start each list item or short section with
one that suits it (not a row of them, and not one on every sentence).

Write one text for LinkedIn (up to 3000 characters; the first ~210 characters
or 3 lines show before "…see more", so the opening has to earn the click) and
a shorter one for X (280 weighted characters; emoji count 2, links 23). Save
each to a file and check it:

```sh
python3 scripts/check.py linkedin.txt --linkedin
python3 scripts/check.py x.txt --x       # too long: it shows the thread split ("---" forces a break)
```

Show the user both texts (and the images) before publishing, unless they
already said to go ahead: sutradhar doesn't ask before a Post click.

## 5. Publish

Do one site at a time, and take a fresh `snapshot` before each step: these
sites change their markup often, so find controls by their names, never by
remembered refs or selectors.

**LinkedIn** (`https://www.linkedin.com/feed/`):
1. `act` click **Start a post**; a dialog opens with the editor (a
   `textbox`, often named "Text editor for creating content").
2. `act` type the text into the editor (one `type` step; `\n` makes new lines).
3. Attach the images: `upload` with the composer's media button as the
   target (`{"do": "upload", "ref": "…", "paths": [...]}`); sutradhar hands the
   page the files and no file picker opens. The button is an unlabelled icon
   beside the emoji button; if `find` can't name it, target it by `x`/`y`
   from a `screenshot` (scale the screenshot's pixels to the viewport's).
   A link in the text makes LinkedIn show a link preview and hide the media
   buttons: attach the images first, or remove the preview (its ✕). Then
   press **Next** / **Done** in the image editor if it shows.
4. `snapshot` the dialog and check the text and images are there.
5. `act` click **Post** with a `why`.
6. Find the new post's link (the "View post" toast, or the first post on
   your profile's activity page) for the user.

**X** (`https://x.com/compose/post`):
1. The composer is a `textbox` ("Post text"). `act` type the text.
2. Images: `upload` onto the composer's `input[type=file]` (up to 4).
3. A thread: after the first post's text, click **Add post** (the "+"), then
   type the next one into the new textbox; repeat.
4. `snapshot` and check; then click **Post** (or **Post all**) with a `why`.
5. Open the post from your profile (`https://x.com/<handle>`) for its link.

To schedule instead of posting now, use the site's own schedule control in the
composer (LinkedIn: the clock beside Post; X: the calendar icon) and say the
time to the user.

Never claim a post went out unless the click returned `ok` and you saw the
post; give the user its link. If a site shows an error, a CAPTCHA or a
"verify it's you" page, `handoff` it to the user.
