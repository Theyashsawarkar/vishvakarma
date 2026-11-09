"""The app's keys: the table is consistent and the annotations match it."""
import curses
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vishvakarma import keys, tui  # noqa: E402

VERBS = {"add", "cancel", "clear", "confirm", "copy", "edit", "jump", "move", "open", "quit", "reload", "run",
         "scroll", "search", "show", "switch", "take", "toggle", "update"}


def table(view):
    return {b.seq: b for b in tui.BINDS if b.applies("normal", view)}


class Keys(unittest.TestCase):
    def test_annotations_are_generated(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "keybinds.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_descriptions_start_with_a_verb(self):
        for b in tui.BINDS + tui.TYPING:
            if b.desc:
                self.assertIn(b.desc.split()[0].lower(), VERBS, b.desc)

    def test_reserved_groups_keep_their_meaning(self):
        # Every leader key lives in a reserved group (or vishvakarma's own c,
        # a free letter) and means what the group says.
        meaning = {"  ": ("palette",), " ?": ("help",), " q": ("quit",), " t": ("tab:",), " f": ("search",),
                   " a": ("new",), " e": ("edit", "settings"), " d": ("takeback",), " r": ("reload", "sync"),
                   " c": ("doctor", "test"), " m": ("toggle",), " y": ("copy",), " o": ("editfile", "folder")}
        for b in tui.BINDS:
            if b.seq.startswith(" ") and len(b.seq) > 1:
                g = b.seq[:2]
                self.assertTrue(g in keys.GROUPS or g in tui.OWN_GROUPS, b.seq)
                self.assertTrue(b.action.startswith(meaning[g]), (b.seq, b.action))
        for g in tui.OWN_GROUPS:
            self.assertIn(g[1], keys.FREE, g)

    def test_no_key_hides_another_in_the_same_tab(self):
        for view in tui.TABS:
            t = table(view)
            for seq in t:
                longer = [s for s in t if s != seq and s.startswith(seq)]
                self.assertFalse(longer, f"{view}: {seq!r} would never run, {longer} start with it")

    def test_sequences(self):
        km = keys.Keymap(list(table("agents").values()), tui.OWN_GROUPS)
        m = keys.Machine()
        self.assertEqual(m.feed(km, "4").kind, "pending")
        r = m.feed(km, "j")
        self.assertEqual((r.kind, r.bind.action, r.count), ("run", "move:1", 4))
        # 1-3 are the tabs (an exact digit bind wins over a count)
        self.assertEqual(m.feed(km, "2").bind.action, "tab:tools")
        for tok in (" ", "r"):
            self.assertEqual(m.feed(km, tok).kind, "pending")
        self.assertEqual(m.feed(km, "s").bind.action, "sync")
        self.assertEqual(m.feed(km, "d").kind, "pending")
        self.assertEqual(m.feed(km, "d").bind.action, "takeback")
        self.assertEqual(m.feed(km, " ").kind, "pending")
        self.assertEqual(m.feed(km, "<Esc>").kind, "cancel")

    def test_moved_keys_say_where(self):
        for view, key, new in (("skills", "c", "Space e c"), ("agents", "u", "dd"), ("skills", "s", "Space r s"),
                               ("tools", "d", "Space c d"), ("tools", "t", "Space c t")):
            b = table(view)[key]
            self.assertTrue(b.action.startswith(f"moved:{new}:"), (view, key, b.action))
            self.assertTrue(b.hidden)

    def test_x_and_take_back_ask_first(self):
        src = (ROOT / "vishvakarma" / "tui.py").read_text()
        toggle = src[src.index("    def act_toggle"):src.index("    def act_take_back")]
        self.assertIn("self.ask(", toggle)
        self.assertNotIn("set_off(", toggle.split("def yes")[0])   # nothing changes before y

    def test_curses_tokens(self):
        self.assertEqual(tui.curses_token(10), "<CR>")
        self.assertEqual(tui.curses_token(4), "<C-d>")
        self.assertEqual(tui.curses_token(ord(" ")), " ")
        self.assertEqual(tui.curses_token(curses.KEY_DOWN), "<Down>")
        self.assertEqual(tui.curses_token("\n"), "<CR>")
        self.assertEqual(tui.curses_token("j"), "j")
        self.assertIsNone(tui.curses_token(curses.KEY_F1))      # F1 types nothing into a prompt
        self.assertIsNone(tui.curses_token(curses.KEY_IC))
        self.assertEqual(tui.curses_token(chr(curses.KEY_UP)), chr(curses.KEY_UP))   # "ă" is a letter, not Up

    def test_vendored_keys_header(self):
        first = (ROOT / "vishvakarma" / "keys.py").read_text().splitlines()[0]
        self.assertTrue(re.match(r"# Vendored from Vyom's vyom/keys.py v\d", first), first)


if __name__ == "__main__":
    unittest.main()
