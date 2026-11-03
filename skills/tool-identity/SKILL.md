---
name: tool-identity
description: Give a Vayu tool its identity and its screen's manners - a Sanskrit name, a logo, a real Sanskrit shloka as its tag, colour that means something, and forms that can't be changed by accident. Use whenever creating, renaming or publishing a Vayu tool, building or changing its screen, writing or changing its README, website, site.toml, logo or about screen, or checking a tool against these rules.
---

# A tool's identity

Every Vayu tool has all three, with no exceptions:

1. **A Sanskrit name**, from Hindu mythology, history or culture, chosen for
   what the tool does, with its Devanagari and its true meaning.
2. **A logo**: `assets/logo.svg`, in the family's style (a rounded square
   tile with a gradient in the tool's colour and one simple line glyph).
   Copy another tool's file and change the colour, glyph and `aria-label`.
3. **A shloka**: one real verse that suits the tool, shown as its tag.

## The shloka

- **Never write or adapt a verse.** Quote a real one from a named work, exact
  to the syllable, and check it against a text you can read (for example
  gitasupersite.iitk.ac.in, sanskritdocuments.org, wisdomlib.org). Don't
  trust memory. If you can't verify it, pick another verse.
- Choose it for the tool: ideally it holds the tool's own word or idea.
- No two tools share a verse. Look at the others' `site.toml` first.
- The English gloss may cover part of the verse but must not bend its
  meaning to fit the tool.

## Where it goes

- **`site.toml`**: `shloka` (Devanagari, lines split with `\n`),
  `shloka_meaning` and `shloka_source`. The website's hero shows them
  (`scripts/build-site.py`).
- **`README.md`**: at the very top, under the title, between
  `<!-- identity -->` and `<!-- /identity -->`: the logo, the verse in bold,
  then the gloss and source. Below it, the line saying what the name means.
- **The tool's own screen**, if it has an about, settings or sidebar place
  for it: the logo and the verse.
  Always in Devanagari. Never as text in a terminal screen: tmux drops its vowel
  signs, which misquotes the verse. Draw it as a picture (vaikhari's
  `internal/tui/picture.go` does this in kitty), with Roman letters (IAST) only
  where pictures can't be drawn.

Then rebuild the site and add a CHANGELOG entry, as the tool's own notes say.

## Its screen

**Colour that means something.** A screen of one colour hides what matters. Use
the theme's colours, never hard-coded ones, and always for the same meanings:

- red: danger, errors, what can't be undone
- green: done, working
- yellow: waiting on you, not saved
- peach: what to look for or copy, what an agent wants
- blue and sky: networks and accounts, links
- the accent: where you are now
- muted: what's secondary

Leave ordinary text alone: when everything is coloured, nothing stands out.

**Nothing changes by accident.** A settings or credentials form opens read-only.
Only Enter starts editing a field, never a letter key, because stray typing
contains letters. Esc cancels that field. Saving is its own key, and a change
that signs someone out or can't be undone asks first.
