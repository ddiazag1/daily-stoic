"""Resolve content/months/*.yaml against the corpus and write data/entries.json.

Fails loudly (exit 1) when:
  - a key matches nothing (or matches more than one passage: ambiguous)
  - two days use the same or overlapping quote anywhere in the year
  - a quote is under 6 or over 110 words
  - the year is not exactly 366 days (Feb 29 included)
  - a reflection is outside 40-60 words, a practice is 18+ words, a title is outside 2-5 words

Usage:
  python scripts/build.py                 # full build + report
  python scripts/build.py --month 03      # check one month only (no output file)
  python scripts/build.py --pool 03       # list the passages reserved for a month
  python scripts/build.py --spotcheck 20  # verify N random quotes against the raw source files
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import glob
import html
import json
import os
import random
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus  # noqa: E402

ROOT = corpus.ROOT
MONTHS_DIR = os.path.join(ROOT, "content", "months")
OUT = os.path.join(ROOT, "data", "entries.json")
DAYS_IN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

THEMES = [
    "What Is Yours", "Mastering Emotion", "Seeing Clearly", "The Work in Front of You",
    "Character", "Living With Others", "The Obstacle", "Time and the Present",
    "Enough", "Nature and Change", "Mortality", "The Examined Day",
]

QUOTE_MIN, QUOTE_MAX = 6, 110
REFL_MIN, REFL_MAX = 40, 60
PRACTICE_MAX = 17          # "under 18 words"
TITLE_MIN, TITLE_MAX = 2, 5


def words(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9À-ɏ'’\-]+", s or ""))


pools = corpus.pools


def load_month(m: int) -> dict:
    path = os.path.join(MONTHS_DIR, f"{m:02d}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_month(m: int, doc: dict, pool: set[str], errors: list[str], used: dict) -> list[dict]:
    entries = []
    days = doc.get("days") or []
    tag = f"{m:02d}"
    if doc.get("theme") != THEMES[m - 1]:
        errors.append(f"{tag}: theme should be '{THEMES[m - 1]}', got '{doc.get('theme')}'")
    if not (doc.get("intro") or "").strip():
        errors.append(f"{tag}: missing month intro")
    seen_days = set()
    for d in days:
        day = d.get("day")
        where = f"{tag}-{day:02d}" if isinstance(day, int) else f"{tag}-?"
        if day in seen_days:
            errors.append(f"{where}: day listed twice")
        seen_days.add(day)
        src = d.get("source")
        key = d.get("key", "")
        after, before = int(d.get("after", 0)), int(d.get("before", 0))
        hits = corpus.find(key, after=after, before=before, source=src)
        if not hits:
            errors.append(f"{where}: key matches nothing [{src}] '{key}'")
            continue
        if len(hits) > 1:
            cites = ", ".join(f"{h.unit.uid}#{h.start}" for h in hits[:6])
            errors.append(f"{where}: key is ambiguous ({len(hits)} hits: {cites}) '{key}'")
            continue
        h = hits[0]
        if h.unit.uid not in pool:
            errors.append(f"{where}: {h.unit.uid} is outside month {m}'s passage pool")
        q = h.text
        nq = words(q)
        if not QUOTE_MIN <= nq <= QUOTE_MAX:
            errors.append(f"{where}: quote is {nq} words (needs {QUOTE_MIN}-{QUOTE_MAX}) [{h.unit.uid}] {q[:80]}")
        span = (h.unit.uid, h.start, h.end)
        for (uid, a, b), other in used.items():
            if uid == span[0] and not (span[2] < a or span[1] > b):
                errors.append(f"{where}: quote overlaps {other} ({uid} sentences {a}-{b})")
        used[span] = where
        title = (d.get("title") or "").strip()
        refl = " ".join((d.get("reflection") or "").split())
        prac = " ".join((d.get("practice") or "").split())
        if not TITLE_MIN <= words(title) <= TITLE_MAX:
            errors.append(f"{where}: title is {words(title)} words: '{title}'")
        if not REFL_MIN <= words(refl) <= REFL_MAX:
            errors.append(f"{where}: reflection is {words(refl)} words (needs {REFL_MIN}-{REFL_MAX})")
        if not prac or words(prac) > PRACTICE_MAX:
            errors.append(f"{where}: practice is {words(prac)} words (needs 1-{PRACTICE_MAX})")
        entries.append({
            "id": f"{m:02d}-{day:02d}" if isinstance(day, int) else where,
            "month": m, "day": day,
            "title": title, "quote": q, "cite": h.citation, "src": h.unit.source, "uid": h.unit.uid,
            "reflection": refl, "practice": prac,
        })
    expect = set(range(1, DAYS_IN[m - 1] + 1))
    missing = sorted(expect - seen_days)
    extra = sorted(d for d in seen_days if d not in expect)
    if missing:
        errors.append(f"{tag}: missing days {missing}")
    if extra:
        errors.append(f"{tag}: invalid days {extra}")
    authors = {e["src"] for e in entries}
    if authors != {"M", "E", "S"}:
        errors.append(f"{tag}: month must mix all three authors (has {sorted(authors)})")
    return sorted(entries, key=lambda e: e["day"] if isinstance(e["day"], int) else 99)


def spotcheck(n: int) -> int:
    """Re-locate N random built quotes inside the raw downloaded source text."""
    with open(OUT, encoding="utf-8") as f:
        data = json.load(f)
    entries = [e for mo in data["months"] for e in mo["entries"]]
    raw = {
        "M": open(os.path.join(corpus.RAW, "meditations.txt"), encoding="utf-8-sig").read(),
        "E": open(os.path.join(corpus.RAW, "epictetus.txt"), encoding="utf-8-sig").read(),
    }
    def sen_raw(n_):
        p = os.path.join(corpus.RAW, "seneca", f"letter_{n_:03d}.html")
        return html.unescape(re.sub(r"<[^>]+>", " ", open(p, encoding="utf-8").read()))

    def squash(s):  # compare on letters/digits only: line wraps, dashes, footnote markers removed
        s = s.replace("--", " ").replace("—", " ")
        s = re.sub(r"\[[A-Z0-9]{1,3}\]", "", s)
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    random.seed(dt.date.today().toordinal())
    sample = random.sample(entries, min(n, len(entries)))
    bad = 0
    for e in sample:
        hay = raw[e["src"]] if e["src"] in raw else sen_raw(int(e["uid"].split(":")[1]))
        # each sentence of the quote must appear contiguously in the raw text
        sents = corpus.split_sentences(e["quote"])
        ok = all(squash(s)[:200] in squash(hay) for s in sents)
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {e['id']} {e['cite']}: {e['quote'][:90]}")
    print(f"spot-check: {len(sample) - bad}/{len(sample)} quotes found verbatim in the raw source")
    return bad


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int)
    ap.add_argument("--pool", type=int)
    ap.add_argument("--spotcheck", type=int)
    ap.add_argument("--dev", action="store_true", help="write whatever months exist (preview only, never ship)")
    a = ap.parse_args(argv)
    P = pools()

    if a.pool:
        units = {u.uid: u for u in corpus.load()}
        for uid in sorted(P[a.pool], key=lambda x: (x[0], x)):
            u = units[uid]
            label = getattr(u, "title", "")
            print(f"{uid:10s} {u.citation}{'  — ' + label if label else ''}  ({len(u.sentences)} sentences)")
        return 0
    if a.spotcheck:
        return 1 if spotcheck(a.spotcheck) else 0

    months = [a.month] if a.month else list(range(1, 13))
    errors: list[str] = []
    used: dict = {}
    out_months = []
    for m in months:
        try:
            doc = load_month(m)
        except FileNotFoundError as e:
            errors.append(f"{m:02d}: file missing ({e})")
            continue
        except yaml.YAMLError as e:
            errors.append(f"{m:02d}: YAML error: {str(e).splitlines()[0]} ({getattr(e, 'problem_mark', '')})")
            continue
        ents = resolve_month(m, doc, P[m], errors, used)
        out_months.append({"month": m, "name": calendar.month_name[m], "theme": doc.get("theme"),
                           "intro": " ".join((doc.get("intro") or "").split()), "entries": ents})

    total = sum(len(mo["entries"]) for mo in out_months)
    if not a.month and total != 366:
        errors.append(f"year has {total} entries, expected exactly 366")

    # report
    print(f"months checked: {len(out_months)}   entries resolved: {total}")
    by = {"M": 0, "E": 0, "S": 0}
    for mo in out_months:
        for e in mo["entries"]:
            by[e["src"]] += 1
    print(f"by author: Marcus {by['M']}  Epictetus {by['E']}  Seneca {by['S']}")
    if out_months:
        ql = [words(e["quote"]) for mo in out_months for e in mo["entries"]]
        rl = [words(e["reflection"]) for mo in out_months for e in mo["entries"]]
        if ql:
            print(f"quote words: min {min(ql)} max {max(ql)} avg {sum(ql)/len(ql):.0f}   "
                  f"reflection words: min {min(rl)} max {max(rl)}")
    if a.dev:
        # preview: fill absent months with placeholders so the app can be exercised
        have = {mo["month"] for mo in out_months}
        for m in range(1, 13):
            if m not in have:
                out_months.append({"month": m, "name": calendar.month_name[m], "theme": THEMES[m - 1],
                                   "intro": "(placeholder month for preview)", "entries": [
                    {"id": f"{m:02d}-{d:02d}", "month": m, "day": d, "title": "Placeholder day",
                     "quote": "Placeholder quote for preview only.", "cite": "Preview", "src": "M", "uid": "x",
                     "reflection": "Placeholder.", "practice": "Placeholder."} for d in range(1, DAYS_IN[m - 1] + 1)]})
        out_months.sort(key=lambda mo: mo["month"])
        write_output(out_months)
        print(f"DEV build written with {len(errors)} unresolved problem(s); do not ship this.")
        return 0
    if errors:
        print(f"\nBUILD FAILED: {len(errors)} problem(s)")
        for e in errors:
            print("  x", e)
        return 1
    if a.month:
        print("month OK")
        return 0
    write_output(out_months)
    print(f"\nBUILD OK: wrote {OUT} ({os.path.getsize(OUT)//1024} KB)")
    return 0


APP_FILES = ["index.html", "styles.css", "app.js", "manifest.webmanifest"]


def write_output(out_months):
    """Write data/entries.json and stamp a content hash into sw.js so caches bust on any change."""
    import hashlib

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    body = json.dumps(out_months, ensure_ascii=False, separators=(",", ":"))
    h = hashlib.sha256(body.encode("utf-8"))
    for name in APP_FILES:
        with open(os.path.join(ROOT, name), "rb") as f:
            h.update(f.read())
    version = h.hexdigest()[:10]
    payload = {"version": version, "months": out_months}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    sw = os.path.join(ROOT, "sw.js")
    with open(sw, encoding="utf-8") as f:
        src = f.read()
    src = re.sub(r'const VERSION = "[^"]*";', f'const VERSION = "{version}";', src, count=1)
    with open(sw, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print(f"version {version} stamped into sw.js")


if __name__ == "__main__":
    sys.exit(main())
