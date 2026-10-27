# contribography

Turn your GitHub contribution graph into pixel art.

`contribography.py` draws text, a pattern you sketch, or a built-in illustration
onto the 7 × 53 grid of your profile's contribution graph. It generates a
throwaway repo full of backdated commits — lots on the days that should be dark
green, none on the days that should be empty — and pushes it to GitHub.

```
Sun  ···███·····███·····███·····███·····███·····███······
Mon  ··█·░·█···█·░·█···█·░·█···█·░·█···█·░·█···█·░·█···█·
Tue  ·█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·
Wed  █·░·░·░·█·░·░·░·█·░·░·░·█·░·░·░·█·░·░·░·█·░·░·░·█·░·
Thu ··█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·░·░█·█░·
Fri ···█·░·█···█·░·█···█·░·█···█·░·█···█·░·█···█·░·█···█·
Sat ····███·····███·····███·····███·····███·····███·····
```
<sub>`--art helix`</sub>

## Requirements

- Python 3.8+ (standard library only)
- git
- SSH access to the GitHub repo you push to

## Quick start

1. Create an empty repo on GitHub to hold the generated commits, e.g.
   `you/contribography-commits`. Keep it separate from this one: every push
   replaces its entire history.
2. Preview the drawing in your terminal:

   ```sh
   ./contribography.py --text "HELLO" --font-height 5 --shade shadow --preview
   ```

3. Generate the commits and push them:

   ```sh
   ./contribography.py --text "HELLO" --font-height 5 --shade shadow \
       --name "Your Name" --email you@example.com \
       --clean --push --repo you/contribography-commits
   ```

GitHub can take up to a day to update the graph.

## What to draw

Pick exactly one source:

| Option | Draws |
| --- | --- |
| `--text "HELLO"` | Text in a built-in font. `--font-height 7` (5×7, about 8 characters, the default) or `--font-height 5` (3×5, about 13 characters). `--top N` moves shorter text up or down. |
| `--pattern art.txt` | A pattern you sketch yourself (format below). |
| `--art NAME` | A built-in illustration that fills the whole year (see below). |

Fonts cover A–Z, 0–9, `! ? - . < >`, space and `♥`.

### Built-in art

| Name | Picture | Commits at `--per-level 1` / `10` |
| --- | --- | --- |
| `helix` | DNA double helix: two strands crossing every 8 weeks, joined by light rungs | ~450 / ~4,500 |
| `invaders` | A row of space invaders in alternating shades | ~590 / ~5,900 |
| `heartbeat` | An ECG trace along Wednesday with a spike every 17 weeks | ~250 / ~2,500 |
| `waves` | Rolling swells shaded from dark troughs to light crests | ~530 / ~5,300 |

Counts are for a typical year and vary a little with the date. GitHub has
dropped weeks from pushes of a few thousand commits, so prefer
`--per-level 1` or `2` unless your real activity is heavy.

### Pattern files

Seven lines, Sunday to Saturday. Each character is one week:

- ` `, `.` or `0` — empty
- `1` to `4` — intensity, lightest to darkest
- anything else — darkest

```
.#...#.
##...##
.#...#.
.#.2.#.
.#...#.
.#...#.
###.###
```

### Shading

`--shade shadow` adds a lighter drop shadow down and to the right;
`--shade outline` surrounds the drawing with a lighter halo. `--shade-level`
(1–3) sets how light it is. The 5-row font leaves room above and below for
shading; the 7-row font fills the whole height, so shading gets clipped.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--offset N` | centred | Weeks from the left edge where the drawing starts. |
| `--per-level N` | 10 | Commits per intensity level, so the darkest days get 4 × N. |
| `--today DATE` | today | Pretend it's a different day (useful with `--preview`). |
| `--preview` | | Print the grid and exit without generating anything. |
| `--name`, `--email` | | Author for the commits. Required to generate. |
| `--out DIR` | `./contribography-commits` | Where to write the generated repo. |
| `--clean` | | Delete the repo from a previous run first. Only deletes a folder holding nothing but `.git` and `art.log`. |
| `--push [URL]` | | Force-push to `--repo`, or to any git remote given as `URL`. |
| `--repo OWNER/NAME` | | GitHub repo to push to, over SSH. Required with `--push` unless you give it a URL. |
| `--batch N` | 500 | Commits per push. |

Run `./contribography.py --help` for the full list.

## How it works

- **The grid.** Rows are days of the week, Sunday at the top; columns are
  weeks. The graph covers exactly one year up to today, so the first and last
  columns are usually partial weeks. Drawings are placed only on the 51–52
  full weeks in between, so they show up whole.
- **The commits.** Every commit is dated noon UTC on its day, so the day
  doesn't shift for viewers in other timezones (from UTC−12 through UTC+11).
  They're written with `git fast-import`, which makes thousands of commits in
  seconds.
- **Replacing old art.** Each run builds a brand-new history and force-pushes
  it to `main`, so drawings never stack on top of one another. Each run's
  commits also get new IDs, so GitHub treats a re-push as new work.
- **Batched pushes.** A single push of about 4,500 commits only showed the
  most recent ~14 weeks on the graph, so the history is pushed oldest-first in
  batches of 500.

## Making sure it shows up

GitHub only counts a commit on your graph if:

- its author email is verified on your GitHub account,
- it's on the repo's default branch (`main` here), and
- the repo isn't a fork.

If the repo is private, turn on **Include private contributions** in your
profile's contribution settings.

## Caveats

- **Colours are relative.** GitHub shades each day by comparing it with your
  other days, not by a fixed number. Raise `--per-level` if your real activity
  makes the drawing look washed out. Shading levels may all render as the same
  light green.
- **The drawing drifts.** GitHub's window moves forward every day, so the
  drawing slides one column left each week and eventually off the edge.
  Re-run the script (with `--clean`) every week or so to keep it in place.
- **Use a dedicated repo.** `--push` replaces the target repo's entire `main`
  history. Never point it at a repo with real work in it.
