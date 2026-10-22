#!/usr/bin/env python3
"""Paint the GitHub contribution graph by generating backdated commits.

The graph is 7 rows (Sunday..Saturday) by ~53 columns (weeks). The leftmost
column is the week containing the day one year before "today"; the rightmost
is the current, partial week.

Usage:
    ./contribography.py --text "HELLO" --preview
    ./contribography.py --text "HELLO WORLD" --font-height 5 --preview
    ./contribography.py --text "HELLO" --font-height 5 --shade shadow --preview
    ./contribography.py --text "HI" --name "Your Name" --email you@example.com --push

Generated commits go into a fresh repo (default ./contribography-commits);
--push force-pushes it to main on the commits repo, replacing any earlier art.

A pattern file is 7 lines, one per weekday starting with Sunday. Each
character is one week: ' ' or '.' is empty, '1'-'4' is an intensity level,
and any other character is level 4 (darkest).

Commits are written with `git fast-import`, so tens of thousands of commits
take seconds. Each commit's author/committer date is noon UTC on its day so
the day can't shift across a timezone boundary.
"""

import argparse
import datetime as dt
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
LEVELS = " 1234"
SHADES = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}


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
    if len(lines) != ROWS:
        sys.exit(f"{path}: expected {ROWS} lines (Sun..Sat), got {len(lines)}")
    width = max(len(l) for l in lines)
    grid = []
    for line in lines:
        row = []
        for c in line.ljust(width):
            row.append(0 if c in " ." else int(c) if c in "1234" else 4)
        grid.append(row)
    return grid


SHADE_OFFSETS = {
    "shadow": [(1, 1)],
    "outline": [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc],
}


def shade(grid, style, level):
    """Fill empty cells next to lit ones with a lighter level. The grid gains
    a column on each side the shading can spill into; rows beyond Sun..Sat
    are clipped."""
    offsets = SHADE_OFFSETS[style]
    left = 1 if any(dc < 0 for _, dc in offsets) else 0
    right = 1 if any(dc > 0 for _, dc in offsets) else 0
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


def graph_start(today):
    """Sunday of the week containing today minus one year (leftmost column)."""
    year_ago = today - dt.timedelta(days=365)
    return year_ago - dt.timedelta(days=(year_ago.weekday() + 1) % 7)


def place(grid, today, offset):
    """Map grid cells to dates. Returns {date: level}."""
    start = graph_start(today)
    columns = (today - start).days // 7 + 1
    width = len(grid[0])
    if offset is None:
        offset = max(0, (columns - width) // 2)
    if offset + width > columns:
        sys.exit(f"art is {width} columns but only {columns - offset} fit "
                 f"(graph has {columns} columns, offset {offset})")
    cells = {}
    for r in range(ROWS):
        for c in range(width):
            if grid[r][c]:
                day = start + dt.timedelta(weeks=offset + c, days=r)
                if day > today:
                    sys.exit(f"cell row {r} col {c} lands on {day}, after today")
                cells[day] = grid[r][c]
    return start, columns, cells


def preview(start, columns, cells):
    names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    print(f"graph: {start} .. {start + dt.timedelta(weeks=columns) - dt.timedelta(days=1)}"
          f" ({columns} columns)")
    for r in range(ROWS):
        row = "".join(SHADES[cells.get(start + dt.timedelta(weeks=c, days=r), 0)]
                      for c in range(columns))
        print(f"{names[r]} {row}")


def generate(cells, out, name, email, per_level):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty")
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
    p.add_argument("--font-height", type=int, choices=sorted(FONTS), default=7,
                   help="font height in rows for --text: 7 (5x7, ~8 chars) or "
                        "5 (3x5, ~13 chars) (default 7)")
    p.add_argument("--top", type=int,
                   help="rows from Sunday to the top of the text "
                        "(default: vertically centered)")
    p.add_argument("--shade", choices=sorted(SHADE_OFFSETS),
                   help="add lighter boxes around the art: 'shadow' (down-right "
                        "drop shadow) or 'outline' (halo on all sides)")
    p.add_argument("--shade-level", type=int, choices=[1, 2, 3], default=1,
                   help="intensity of the shading boxes (default 1, lightest)")
    p.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                   help="last day of the graph (default: today)")
    p.add_argument("--offset", type=int,
                   help="column to start the art at (default: centered)")
    p.add_argument("--per-level", type=int, default=10,
                   help="commits per intensity level; level 4 = 4x this (default 10)")
    p.add_argument("--preview", action="store_true", help="print the grid and exit")
    p.add_argument("--name", help="author name for the commits")
    p.add_argument("--email", help="must be a verified email on your GitHub account")
    p.add_argument("--out", default="contribography-commits",
                   help="directory for the new repo (default ./contribography-commits)")
    p.add_argument("--push", nargs="?", const=DEFAULT_REMOTE, metavar="URL",
                   help="force-push the generated history to main on URL "
                        f"(default {DEFAULT_REMOTE})")
    a = p.parse_args()

    grid = (render_text(a.text, a.font_height, a.top) if a.text
            else load_pattern(a.pattern))
    if a.shade:
        grid = shade(grid, a.shade, a.shade_level)
    start, columns, cells = place(grid, a.today, a.offset)
    preview(start, columns, cells)
    if a.preview:
        return
    if not (a.name and a.email):
        sys.exit("--name and --email are required to generate commits")
    generate(cells, a.out, a.name, a.email, a.per_level)
    if a.push:
        push(a.out, a.push)


if __name__ == "__main__":
    main()
