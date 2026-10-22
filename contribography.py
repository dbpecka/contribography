#!/usr/bin/env python3
"""Paint the GitHub contribution graph by generating backdated commits.

The graph is 7 rows (Sunday..Saturday) by 53 or 54 columns (weeks), covering
one year up to "today". The leftmost and rightmost columns are usually partial
weeks, so art is laid out on the full weeks in between (51 or 52 of them).

Usage:
    ./contribography.py --text "HELLO" --preview
    ./contribography.py --text "HELLO WORLD" --font-height 5 --preview
    ./contribography.py --text "HELLO" --font-height 5 --shade shadow --preview
    ./contribography.py --art helix --preview
    ./contribography.py --text "HI" --name "Your Name" --email you@example.com --push
    ./contribography.py --art helix --name "Your Name" --email you@example.com --clean --push

Generated commits go into a fresh repo (default ./contribography-commits);
--clean replaces one left by an earlier run, and --push force-pushes it to main
on the commits repo, replacing any earlier art.

A pattern file is 7 lines, one per weekday starting with Sunday. Each
character is one week: ' ', '.' or '0' is empty, '1'-'4' is an intensity
level, and any other character is level 4 (darkest).

Commits are written with `git fast-import`, so tens of thousands of commits
take seconds. Each commit's author/committer date is noon UTC on its day so
the day can't shift across a timezone boundary.
"""

import argparse
import datetime as dt
import math
import shutil
import subprocess
import sys
from pathlib import Path

# 5-wide x 7-tall bitmap font. Each glyph is 7 strings of 5 chars.
FONT_7 = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#### ", "    #", "    #", " ### ", "    #", "    #", "#### "],
    "4": ["#   #", "#   #", "#   #", "#####", "    #", "    #", "    #"],
    "5": ["#####", "#    ", "#    ", "#### ", "    #", "    #", "#### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", "     ", "  #  "],
    "<": ["   # ", "  #  ", " #   ", "#    ", " #   ", "  #  ", "   # "],
    ">": [" #   ", "  #  ", "   # ", "    #", "   # ", "  #  ", " #   "],
    "♥": [" # # ", "#####", "#####", "#####", " ### ", "  #  ", "     "],
    " ": ["   ", "   ", "   ", "   ", "   ", "   ", "   "],
}

# 3-wide x 5-tall bitmap font; fits ~13 characters instead of ~8.
FONT_5 = {
    "A": ["###", "# #", "###", "# #", "# #"],
    "B": ["## ", "# #", "## ", "# #", "## "],
    "C": ["###", "#  ", "#  ", "#  ", "###"],
    "D": ["## ", "# #", "# #", "# #", "## "],
    "E": ["###", "#  ", "## ", "#  ", "###"],
    "F": ["###", "#  ", "## ", "#  ", "#  "],
    "G": ["###", "#  ", "# #", "# #", "###"],
    "H": ["# #", "# #", "###", "# #", "# #"],
    "I": ["###", " # ", " # ", " # ", "###"],
    "J": ["  #", "  #", "  #", "# #", "###"],
    "K": ["# #", "# #", "## ", "# #", "# #"],
    "L": ["#  ", "#  ", "#  ", "#  ", "###"],
    "M": ["# #", "###", "###", "# #", "# #"],
    "N": ["## ", "# #", "# #", "# #", "# #"],
    "O": ["###", "# #", "# #", "# #", "###"],
    "P": ["###", "# #", "###", "#  ", "#  "],
    "Q": ["###", "# #", "# #", "###", "  #"],
    "R": ["###", "# #", "## ", "# #", "# #"],
    "S": ["###", "#  ", "###", "  #", "###"],
    "T": ["###", " # ", " # ", " # ", " # "],
    "U": ["# #", "# #", "# #", "# #", "###"],
    "V": ["# #", "# #", "# #", "# #", " # "],
    "W": ["# #", "# #", "###", "###", "# #"],
    "X": ["# #", "# #", " # ", "# #", "# #"],
    "Y": ["# #", "# #", "###", " # ", " # "],
    "Z": ["###", "  #", " # ", "#  ", "###"],
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", "###", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    "!": ["#", "#", "#", " ", "#"],
    "?": ["###", "  #", " ##", "   ", " # "],
    "-": ["   ", "   ", "###", "   ", "   "],
    ".": [" ", " ", " ", " ", "#"],
    "<": ["  #", " # ", "#  ", " # ", "  #"],
    ">": ["#  ", " # ", "  #", " # ", "#  "],
    "♥": ["## ##", "#####", "#####", " ### ", "  #  "],
    " ": ["  ", "  ", "  ", "  ", "  "],
}

FONTS = {7: FONT_7, 5: FONT_5}

ROWS = 7
DEFAULT_REMOTE = "https://github.com/dbpecka/contribography-commits"
SHADES = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}


def non_negative(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {n}")
    return n


def render_text(text, height=7, top=None):
    """Render text in the font of the given height, placed `top` rows below
    Sunday (default: vertically centered)."""
    font = FONTS[height]
    if top is None:
        top = (ROWS - height) // 2
    if not 0 <= top <= ROWS - height:
        sys.exit(f"--top must be between 0 and {ROWS - height} for a "
                 f"{height}-row font")
    rows = [""] * height
    for i, ch in enumerate(text.upper()):
        glyph = font.get(ch)
        if glyph is None:
            sys.exit(f"no glyph for {ch!r}; available: {''.join(sorted(font))}")
        for r in range(height):
            rows[r] += glyph[r] + (" " if i < len(text) - 1 else "")
    width = len(rows[0])
    rows = [" " * width] * top + rows + [" " * width] * (ROWS - height - top)
    return [[4 if c == "#" else 0 for c in row] for row in rows]


def load_pattern(path):
    lines = Path(path).read_text().splitlines()
    # Tolerate blank lines after Saturday, but not blank Sunday..Saturday rows
    # going missing.
    while len(lines) > ROWS and not lines[-1].strip():
        lines.pop()
    if len(lines) != ROWS:
        sys.exit(f"{path}: expected {ROWS} lines (Sun..Sat), got {len(lines)}")
    width = max(len(l) for l in lines)
    grid = []
    for line in lines:
        row = []
        for c in line.ljust(width):
            row.append(0 if c in " .0" else int(c) if c in "1234" else 4)
        grid.append(row)
    return grid


SHADE_OFFSETS = {
    "shadow": [(1, 1)],
    "outline": [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc],
}


def shade_padding(style):
    """(left, right) columns that shading adds around the art."""
    offsets = SHADE_OFFSETS[style]
    return (int(any(dc < 0 for _, dc in offsets)),
            int(any(dc > 0 for _, dc in offsets)))


def shade(grid, style, level):
    """Fill empty cells next to lit ones with a lighter level. The grid gains
    a column on each side the shading can spill into; rows beyond Sun..Sat
    are clipped."""
    offsets = SHADE_OFFSETS[style]
    left, right = shade_padding(style)
    out = [[0] * left + row + [0] * right for row in grid]
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if not v:
                continue
            for dr, dc in offsets:
                rr, cc = r + dr, c + left + dc
                if 0 <= rr < ROWS and not out[rr][cc]:
                    out[rr][cc] = level
    return out


def helix(width):
    """DNA double helix: two dark strands crossing every 8 weeks, joined by
    light rungs every other week."""
    period = 16
    grid = [[0] * width for _ in range(ROWS)]
    for c in range(width):
        s = math.sin(2 * math.pi * c / period)
        a, b = round(3 + 3 * s), round(3 - 3 * s)
        if c % 2 == 0:
            for r in range(min(a, b) + 1, max(a, b)):
                grid[r][c] = 1
        grid[a][c] = grid[b][c] = 4
    return grid


# Built-in illustrations for --art. Each takes the number of columns to fill
# and returns a 7-row grid of levels.
ART = {"helix": helix}


def year_ago(today):
    """First day of the graph's one-year window."""
    try:
        return today.replace(year=today.year - 1)
    except ValueError:  # Feb 29
        return today.replace(year=today.year - 1, day=28)


def graph_start(today):
    """Sunday of the week containing the day one year ago (leftmost column)."""
    first = year_ago(today)
    return first - dt.timedelta(days=(first.weekday() + 1) % 7)


def full_weeks(today):
    """(first column, column count) of the weeks lying entirely inside the
    window. The edge columns are usually partial: the leftmost starts mid-week
    one year ago and the rightmost ends today. Depending on the weekday the
    graph has 53 or 54 columns, so art is laid out on full weeks only, which
    GitHub always shows in full whatever its exact window."""
    start = graph_start(today)
    # Skip column 0 even when it starts exactly a year ago, in case GitHub's
    # window excludes that day.
    first = 1
    last = (today - start).days // 7
    if (today - start).days % 7 != 6:  # current week is still partial
        last -= 1
    return first, last - first + 1


def place(grid, today, offset):
    """Map grid cells to dates. Returns {date: level}. `offset` counts from
    the first full week."""
    start = graph_start(today)
    first, count = full_weeks(today)
    width = len(grid[0])
    if offset is None:
        offset = max(0, (count - width) // 2)
    if offset >= count:
        sys.exit(f"--offset {offset} is past the last of the {count} full weeks")
    if offset + width > count:
        sys.exit(f"art is {width} columns but only {count - offset} fit "
                 f"({count} full weeks, offset {offset})")
    cells = {}
    for r in range(ROWS):
        for c in range(width):
            if grid[r][c]:
                cells[start + dt.timedelta(weeks=first + offset + c, days=r)] = grid[r][c]
    return start, cells


def preview(today, start, cells):
    names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    columns = (today - start).days // 7 + 1
    print(f"graph: {year_ago(today)} .. {today} ({columns} columns, "
          f"{full_weeks(today)[1]} full weeks)")
    for r in range(ROWS):
        row = ""
        for c in range(columns):
            day = start + dt.timedelta(weeks=c, days=r)
            # Days outside the one-year window aren't drawn by GitHub.
            row += " " if not year_ago(today) <= day <= today else SHADES[cells.get(day, 0)]
        print(f"{names[r]} {row}")


def is_generated_repo(path):
    """True if path looks like a repo this script wrote: nothing but .git and
    art.log."""
    return {p.name for p in path.iterdir()} <= {".git", "art.log"} \
        and (path / ".git").is_dir()


def generate(cells, out, name, email, per_level, clean):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        if not clean:
            sys.exit(f"{out} exists and is not empty (use --clean to replace "
                     f"a previously generated repo)")
        if not is_generated_repo(out):
            sys.exit(f"{out} doesn't look like a generated repo; not deleting it")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(out)], check=True)

    stream = []
    mark = 0
    for day in sorted(cells):
        for n in range(cells[day] * per_level):
            mark += 1
            ts = int(dt.datetime(day.year, day.month, day.day, 12, 0, n % 60,
                                 tzinfo=dt.timezone.utc).timestamp())
            ident = f"{name} <{email}> {ts} +0000"
            msg = f"{day} #{n + 1}\n".encode()
            content = f"{day} #{n + 1}\n".encode()
            stream.append(b"commit refs/heads/main\n")
            stream.append(f"mark :{mark}\n".encode())
            stream.append(f"author {ident}\ncommitter {ident}\n".encode())
            stream.append(f"data {len(msg)}\n".encode() + msg)
            if mark > 1:
                stream.append(f"from :{mark - 1}\n".encode())
            stream.append(f"M 644 inline art.log\ndata {len(content)}\n".encode()
                          + content + b"\n")
    subprocess.run(["git", "-C", str(out), "fast-import", "--quiet"],
                   input=b"".join(stream), check=True)
    subprocess.run(["git", "-C", str(out), "checkout", "-q", "main"], check=True)
    print(f"wrote {mark} commits across {len(cells)} days to {out}")


def push(out, remote):
    # Force: each run regenerates the whole history, replacing the old art.
    subprocess.run(["git", "-C", str(out), "push", "--force", remote,
                    "main:main"], check=True)
    print(f"pushed to {remote}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="render this text with a built-in font")
    src.add_argument("--pattern", help="7-line pattern file")
    src.add_argument("--art", choices=sorted(ART),
                     help="draw a built-in illustration across every full week")
    p.add_argument("--font-height", type=int, choices=sorted(FONTS),
                   help="font height in rows for --text: 7 (5x7, ~8 chars) or "
                        "5 (3x5, ~13 chars) (default 7)")
    p.add_argument("--top", type=non_negative,
                   help="rows from Sunday to the top of the text "
                        "(default: vertically centered)")
    p.add_argument("--shade", choices=sorted(SHADE_OFFSETS),
                   help="add lighter boxes around the art: 'shadow' (down-right "
                        "drop shadow) or 'outline' (halo on all sides)")
    p.add_argument("--shade-level", type=int, choices=[1, 2, 3], default=1,
                   help="intensity of the shading boxes (default 1, lightest)")
    p.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                   help="last day of the graph (default: today)")
    p.add_argument("--offset", type=non_negative,
                   help="weeks from the first full week to the start of the art "
                        "(default: centered)")
    p.add_argument("--per-level", type=int, default=10,
                   help="commits per intensity level; level 4 = 4x this (default 10)")
    p.add_argument("--preview", action="store_true", help="print the grid and exit")
    p.add_argument("--name", help="author name for the commits")
    p.add_argument("--email", help="must be a verified email on your GitHub account")
    p.add_argument("--out", default="contribography-commits",
                   help="directory for the new repo (default ./contribography-commits)")
    p.add_argument("--clean", action="store_true",
                   help="delete a previously generated --out repo before "
                        "writing the new one")
    p.add_argument("--push", nargs="?", const=DEFAULT_REMOTE, metavar="URL",
                   help="force-push the generated history to main on URL "
                        f"(default {DEFAULT_REMOTE})")
    a = p.parse_args()
    if not a.text and (a.font_height is not None or a.top is not None):
        p.error("--font-height and --top only apply to --text")
    for flag, value in (("--name", a.name), ("--email", a.email)):
        # These go into "author Name <email>" lines of the fast-import stream.
        if value is not None and (not value.strip() or set(value) & set("<>\n")):
            p.error(f"{flag} can't be blank or contain '<', '>' or line breaks")

    if a.text:
        grid = render_text(a.text, a.font_height or 7, a.top)
    elif a.art:
        # Leave room for the columns shading adds so the result still fits.
        pad = sum(shade_padding(a.shade)) if a.shade else 0
        width = full_weeks(a.today)[1] - (a.offset or 0) - pad
        if width <= 0:
            sys.exit(f"--offset {a.offset} leaves no room for the art")
        grid = ART[a.art](width)
    else:
        grid = load_pattern(a.pattern)
    if a.shade:
        grid = shade(grid, a.shade, a.shade_level)
    start, cells = place(grid, a.today, a.offset)
    preview(a.today, start, cells)
    if not cells:
        sys.exit("nothing to draw: the art has no filled boxes")
    if a.preview:
        return
    if not (a.name and a.email):
        sys.exit("--name and --email are required to generate commits")
    generate(cells, a.out, a.name, a.email, a.per_level, a.clean)
    if a.push:
        push(a.out, a.push)


if __name__ == "__main__":
    main()
