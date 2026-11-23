#!/usr/bin/env python3
"""Checks a post before it goes out on X and LinkedIn.

    python3 check.py post.txt            # both networks
    python3 check.py post.txt --x        # only X
    python3 check.py post.txt --linkedin # only LinkedIn

X: counts characters the way X does (most characters 1; emoji, CJK and other
wide characters 2; every link 23) against 280, and if it is longer, splits it
into a thread at paragraph or sentence breaks (a line holding only "---"
forces a break). LinkedIn: 3000 characters, and shows what readers see before
"…see more" (about 210 characters or 3 lines).

Prints a report; exits 1 if a post can't go out as written. Standard library only.
"""
import re
import sys
import unicodedata

X_LIMIT = 280
X_URL = 23
LI_LIMIT = 3000
LI_FOLD_CHARS = 210
LI_FOLD_LINES = 3
URL = re.compile(r"https?://\S+|\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|in|ai|app|co|me|sh)(?:/\S*)?", re.I)


def x_weight(text):
    """X's weighted length: links 23, wide characters and emoji 2, the rest 1."""
    total = 0
    pos = 0
    for m in URL.finditer(text):
        total += _chars(text[pos:m.start()]) + X_URL
        pos = m.end()
    return total + _chars(text[pos:])


def _chars(s):
    n = 0
    skip_next = False
    for ch in s:
        cp = ord(ch)
        if skip_next:
            skip_next = False
            continue
        if ch in "‍️︎" or 0x1F3FB <= cp <= 0x1F3FF:  # joiners, variation selectors, skin tones
            continue
        if cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or unicodedata.east_asian_width(ch) in ("W", "F"):
            n += 2
        elif 0x1100 <= cp and unicodedata.category(ch).startswith("L") and cp >= 0x3000:
            n += 2
        else:
            n += 1
    return n


def split_thread(text):
    """Splits into posts of at most 280 weighted characters, at "---", blank lines, then sentences."""
    blocks = [b.strip() for b in re.split(r"\n\s*---\s*\n", text)]
    posts = []
    for block in blocks:
        cur = ""
        for para in re.split(r"\n\s*\n", block):
            para = para.strip()
            pieces = [para] if x_weight(para) <= X_LIMIT - 6 else re.split(r"(?<=[.!?])\s+", para)
            for piece in pieces:
                cand = f"{cur}\n\n{piece}" if cur and piece is para else (f"{cur} {piece}" if cur else piece)
                if x_weight(cand) <= X_LIMIT - 6:
                    cur = cand
                else:
                    if cur:
                        posts.append(cur)
                    cur = piece
        if cur:
            posts.append(cur)
    if len(posts) > 1:
        posts = [f"{p} {i}/{len(posts)}" for i, p in enumerate(posts, 1)]
    return posts


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    text = open(argv[0], encoding="utf-8").read().strip()
    only_x, only_li = "--x" in argv, "--linkedin" in argv
    ok = True
    if not only_li:
        w = x_weight(re.sub(r"\n\s*---\s*\n", "\n\n", text))
        print(f"X: {w} / {X_LIMIT} weighted characters")
        if w > X_LIMIT or "\n---\n" in text:
            posts = split_thread(text)
            print(f"   → a thread of {len(posts)} posts:")
            for i, p in enumerate(posts, 1):
                pw = x_weight(p)
                print(f"\n   [{i}] {pw}/{X_LIMIT}" + ("  TOO LONG" if pw > X_LIMIT else ""))
                print("   " + p.replace("\n", "\n   "))
                ok &= pw <= X_LIMIT
    if not only_x:
        n = len(text)
        print(f"\nLinkedIn: {n} / {LI_LIMIT} characters" + ("  TOO LONG" if n > LI_LIMIT else ""))
        ok &= n <= LI_LIMIT
        lines = text.split("\n")
        seen, shown = 0, []
        for line in lines[:LI_FOLD_LINES]:
            if seen + len(line) > LI_FOLD_CHARS:
                shown.append(line[: LI_FOLD_CHARS - seen] + "…see more")
                break
            shown.append(line)
            seen += len(line)
        else:
            if len(lines) > LI_FOLD_LINES:
                shown[-1] += " …see more"
        print("   before the fold:\n   " + "\n   ".join(shown))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
