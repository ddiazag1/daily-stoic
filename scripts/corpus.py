"""Build a clean, sentence-split corpus from three public-domain Stoic translations.

Sources (downloaded at build time, cached under raw/):
  M  Marcus Aurelius, Meditations, tr. George Long       (Project Gutenberg #15877)
  E  Epictetus, Discourses (selection) + Enchiridion, tr. George Long (Project Gutenberg #10661)
  S  Seneca, Moral Letters to Lucilius, tr. R. M. Gummere (English Wikisource, letters 1-124)

Every quote the app shows is pulled from here by script, never typed by hand.

Usage:
  python scripts/corpus.py stats
  python scripts/corpus.py search WORD [WORD ...] [--source M|E|S] [--max 40]
  python scripts/corpus.py find "key phrase" [--source M] [--after 1] [--before 0]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
UA = {"User-Agent": "daily-stoic-build/1.0 (personal reader; github.com/ddiazag1/daily-stoic)"}

URLS = {
    "meditations": "https://www.gutenberg.org/cache/epub/15877/pg15877.txt",
    "epictetus": "https://www.gutenberg.org/cache/epub/10661/pg10661.txt",
    "seneca": "https://en.wikisource.org/wiki/Moral_letters_to_Lucilius/Letter_{n}?action=render",
}

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = ROMAN[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


# ---------------------------------------------------------------- download

def _get(url: str) -> str:
    import requests

    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:  # network hiccup: back off and retry
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch(name: str, path: str, url: str, refresh: bool = False) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if refresh or not os.path.exists(path):
        text = _get(url)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


# ---------------------------------------------------------------- cleaning

def gutenberg_body(t: str) -> str:
    s = t.find("*** START")
    s = t.find("\n", s) + 1 if s >= 0 else 0
    e = t.find("*** END")
    return t[s:e if e >= 0 else len(t)]


def drop_indented_blocks(text: str) -> str:
    """Long puts footnotes and editorial notes in paragraphs indented 4+ spaces."""
    keep = []
    for para in re.split(r"\n\s*\n", text):
        lines = [l for l in para.split("\n") if l.strip()]
        if lines and all(l.startswith("    ") for l in lines):
            continue
        if lines and re.match(r"\s*\[(?:[A-Z]{1,2}|\d{1,3})\]\s", lines[0]):
            continue  # unindented footnote paragraph: "[A] See Aristophanes..."
        if lines and re.match(r"\s*\[(?:Illustration|Footnote)", lines[0]):
            continue
        keep.append(para)
    return "\n\n".join(keep)


XREF = re.compile(
    r"\s*\((?:[ivxlc]+\.\s*\d+[^()]*?|see\s+[ivxlc]+\.[^()]*?|[ivxlc]+\.\s*\d+(?:\s*\([^()]*\))?[^()]*?)\)",
    re.I,
)


def clean_text(s: str) -> str:
    s = s.replace("\r", "")
    s = re.sub(r"\[(?:Illustration|Footnote):[^\]]*\]", "", s)  # inline illustration/footnote tags
    s = re.sub(r"\[Greek:[^\]]*\]", "", s)              # Greek glosses
    s = re.sub(r"\[(?:[A-Z]{1,2}|\d{1,3})\]", "", s)     # footnote markers [A] [B] [12]
    s = XREF.sub("", s)                                  # cross-refs (vii. 58; iv. 48)
    s = s.replace("+", "")                               # stray + marks
    s = re.sub(r"_([^_]+)_", r"\1", s)                   # Gutenberg _italics_
    s = s.replace("​", "").replace(" ", " ")
    s = s.replace("--", "—")                        # typographic dash only
    s = re.sub(r"\s*—\s*", "—", s)
    s = re.sub(r"\(\s*\)", "", s)                        # emptied parens after Greek removal
    s = re.sub(r"\s+([,;:.!?])", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------- sentences

_CLOSE = "\"'”’)\\]"
_SPLIT = re.compile(
    r"(?<=[.!?])[" + _CLOSE + r"]*\s+(?=[\"'“‘(\[]?[A-Z0-9])"
)
_ABBR = re.compile(r"(?:\b(?:Mr|Mrs|Dr|St|i\.e|e\.g|cf|viz|vol|ch|tr|p|pp|ep|Epp|lib|c|No)\.|\b[A-Z]\.)$", re.I)


def split_sentences(text: str) -> list[str]:
    """Split on . ! ? (optionally followed by closing quotes/brackets) + space + capital/opening quote."""
    out: list[str] = []
    pos = 0
    for m in _SPLIT.finditer(text):
        # include closing quote chars in the sentence: m.start() is after the punctuation
        end = m.start()
        seg_end = end
        while seg_end < len(text) and text[seg_end] in _CLOSE:
            seg_end += 1
        candidate = text[pos:seg_end].strip()
        if _ABBR.search(text[pos:end]) and len(candidate) < 400:
            continue  # abbreviation, not a sentence end
        out.append(candidate)
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


# ---------------------------------------------------------------- units

@dataclass
class Unit:
    source: str            # M / E / S
    citation: str          # "Marcus Aurelius, Meditations 4.49"
    uid: str               # stable id, e.g. "M:4.49"
    text: str
    sentences: list[str] = field(default_factory=list)


def parse_meditations(refresh=False) -> list[Unit]:
    t = gutenberg_body(fetch("meditations", os.path.join(RAW, "meditations.txt"), URLS["meditations"], refresh))
    books = list(re.finditer(r"^([IVXL]+)\.\s*$", t, re.M))
    idx = t.find("INDEXES.", books[-1].start())
    units = []
    for bi, b in enumerate(books):
        bnum = roman_to_int(b.group(1))
        end = books[bi + 1].start() if bi + 1 < len(books) else idx
        body = drop_indented_blocks(t[b.end():end])
        # sections: first is unnumbered (1), then "N. " at line start
        parts = re.split(r"(?m)^(\d{1,3})\.\s", body)
        chunks = [("1", parts[0])] + list(zip(parts[1::2], parts[2::2]))
        for num, txt in chunks:
            txt = clean_text(txt)
            if bnum == 1 and num == "17":
                txt = re.sub(r"\s*Among the Quadi at the Granua\.?$", "", txt)
            if bnum == 2 and num == "17":
                txt = re.sub(r"\s*This in Carnuntum\.?$", "", txt)
            if txt:
                units.append(Unit("M", f"Marcus Aurelius, Meditations {bnum}.{int(num)}", f"M:{bnum}.{int(num)}", txt))
    return units


def parse_epictetus(refresh=False) -> list[Unit]:
    t = gutenberg_body(fetch("epictetus", os.path.join(RAW, "epictetus.txt"), URLS["epictetus"], refresh))
    d = t.find("A SELECTION FROM THE DISCOURSES OF EPICTETUS.", 2000)
    ench = t.find("THE ENCHEIRIDION, OR MANUAL.", d)
    units: list[Unit] = []

    # Discourses: chapters start with an ALL-CAPS title ending in an em dash.
    disc = drop_indented_blocks(t[d + len("A SELECTION FROM THE DISCOURSES OF EPICTETUS."):ench])
    disc = re.sub(r"\[(?:Footnote|Illustration):[^\]]*\]", "", disc)
    disc = re.sub(r"\s*\(?\[Greek:[^\]]*\]\)?", "", disc)
    # A chapter title starts a line, contains no lowercase letters (may wrap lines),
    # and ends in ".—" or "—".
    heads = [m for m in re.finditer(r"(?m)^([A-Z][^a-z—]{8,}?)—", disc)
             if len(m.group(1).split()) >= 2]
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(disc)
        title = re.sub(r"\s+", " ", h.group(1)).strip().rstrip(".")
        body = clean_text(disc[h.end():end])
        if body:
            units.append(Unit("E", "Epictetus, Discourses", f"E:D{i + 1}", body))
            units[-1].title = title.title()  # type: ignore[attr-defined]

    # Encheiridion: chapters I. .. LII.
    en = drop_indented_blocks(t[ench:])
    chs = list(re.finditer(r"(?m)^([IVXL]+)\.\s*$", en))
    for i, c in enumerate(chs):
        end = chs[i + 1].start() if i + 1 < len(chs) else len(en)
        n = roman_to_int(c.group(1))
        body = clean_text(en[c.end():end])
        if body:
            units.append(Unit("E", f"Epictetus, Enchiridion {n}", f"E:N{n}", body))
    return units


def _seneca_text(raw_html: str) -> str:
    s = raw_html
    k = s.find('class="prp-pages-output"')
    s = s[k:] if k >= 0 else s
    s = re.sub(r"(?s)<style.*?</style>", "", s)
    s = re.sub(r"(?s)<span[^>]*class=\"[^\"]*pagenum[^\"]*\".*?</span>\s*</span>", "", s)  # page-number spans
    s = re.sub(r"(?s)<sup[^>]*class=\"[^\"]*reference[^\"]*\".*?</sup>", "", s)          # footnote refs
    s = re.sub(r"(?s)<(ol|div)[^>]*class=\"[^\"]*(references|reflist)[^\"]*\".*", "", s)  # footnote list
    paras = []
    for p in re.findall(r"(?s)<p[^>]*>(.*?)</p>", s):
        txt = html.unescape(re.sub(r"<[^>]+>", "", p))
        txt = txt.replace("​", "").strip()
        if not txt:
            continue
        if re.match(r"^(?:[IVXLC]+\.\s+)?[A-Z][A-Z ,'’;:\-\.]+$", txt):   # title line "XIII. ON GROUNDLESS FEARS"
            continue
        if txt.startswith("Greetings from Seneca to his friend Lucilius"):
            continue
        if txt.startswith(".mw-parser-output") or "{" in txt[:40]:
            continue                                          # stray CSS
        txt = re.sub(r"^\d{1,3}\.\s+", "", txt)              # section number at paragraph start
        txt = re.sub(r"\s\d{1,3}\.\s(?=[A-Z])", " ", txt)    # inline section numbers
        txt = re.sub(r"\[\d{1,3}\]", "", txt)                  # footnote markers
        paras.append(txt)
    # trailing footnote paragraphs start with "[1]" style or digits; already removed by marker strip,
    # but drop paragraphs that look like bare notes ("Cf. ...", "i.e. ...") after the valediction.
    out, ended = [], False
    for ptxt in paras:
        if ended:
            break
        out.append(ptxt)
        if re.search(r"\bFarewell\.?\s*$", ptxt):
            ended = True
    return clean_text(" ".join(out))


def parse_seneca(refresh=False) -> list[Unit]:
    units = []
    for n in range(1, 125):
        path = os.path.join(RAW, "seneca", f"letter_{n:03d}.html")
        raw = fetch("seneca", path, URLS["seneca"].format(n=n), refresh)
        body = _seneca_text(raw)
        if body:
            units.append(Unit("S", f"Seneca, Letters {n}", f"S:{n}", body))
    return units


@lru_cache(maxsize=1)
def load(refresh: bool = False) -> tuple[Unit, ...]:
    units = parse_meditations(refresh) + parse_epictetus(refresh) + parse_seneca(refresh)
    for u in units:
        u.sentences = split_sentences(u.text)
    return tuple(units)


# ---------------------------------------------------------------- search

def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = s.replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Hit:
    unit: Unit
    start: int   # first sentence index (inclusive)
    end: int     # last sentence index (inclusive)

    @property
    def text(self) -> str:
        return " ".join(self.unit.sentences[self.start:self.end + 1])

    @property
    def citation(self) -> str:
        return self.unit.citation


def find(key: str, after: int = 0, before: int = 0, source: str | None = None) -> list[Hit]:
    """Return every hit whose sentence contains `key` (case/punctuation-insensitive),
    widened by `before` sentences before and `after` sentences after."""
    k = norm(key)
    hits = []
    for u in load():
        if source and u.source != source:
            continue
        for i, s in enumerate(u.sentences):
            if k and k in norm(s):
                a = max(0, i - before)
                b = min(len(u.sentences) - 1, i + after)
                hits.append(Hit(u, a, b))
    return hits


THEME_WORDS = {
    1: "power control will choice choose own mine yours faculty free freedom slave master depend impediment hinder opinion assent purpose",
    2: "anger angry passion passions fear afraid grief grieve sorrow desire desires pleasure pain disturbed lament weep envy emotion calm tranquil",
    3: "appearance appearances opinion opinions judgment judge impression impressions seem seems true truth false error deceived perceive examine",
    4: "work works act acts action duty duties task labour labor morning busy business rise employment occupy diligent toil",
    5: "virtue virtuous character just justice honest honour honor good man modest faithful integrity noble temperance courage shame",
    6: "men man others neighbour neighbor friend friends friendship kind kindness social society community anger offend wrong forgive help companion",
    7: "obstacle obstacles hindrance hindrances difficulty difficulties misfortune hardship endure endurance adversity suffer trial exile poverty sickness",
    8: "present time moment now past future today hour hours day days delay postpone procrastinate brief short swift",
    9: "wealth rich riches poverty poor enough simple simplicity luxury money possessions gold want need little superfluous frugal",
    10: "nature natural change changes universe whole flux transformation element elements decay world matter cause causes",
    11: "death die dying dies mortal mortality life short end corpse grave dust old age funeral",
    12: "examine examination review evening night day account conscience progress philosophy philosopher improve learn study reason practice",
}


@lru_cache(maxsize=1)
def pools() -> dict[int, frozenset[str]]:
    """Disjoint, theme-aware passage pools. Each passage is scored by how densely it uses each
    month's theme words; pairs are assigned best-first under a per-source cap, so every passage
    belongs to exactly one month and no two months can draw the same passage."""
    import math

    units = load()
    out: dict[int, set[str]] = {m: set() for m in range(1, 13)}
    for src in "MES":
        su = [u for u in units if u.source == src]
        cap = math.ceil(len(su) / 12)
        pairs = []
        for u in su:
            toks = norm(u.text).split()
            n = max(len(toks), 1)
            for m, ws in THEME_WORDS.items():
                kw = set(ws.split())
                hits = sum(1 for t in toks if t in kw)
                pairs.append((hits / n ** 0.5, u.uid, m))
        pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
        taken: set[str] = set()
        for score, uid, m in pairs:
            if uid in taken or len([x for x in out[m] if x[0] == src]) >= cap:
                continue
            out[m].add(uid)
            taken.add(uid)
        assert len(taken) == len(su), f"unassigned {src} passages"
    return {m: frozenset(v) for m, v in out.items()}


def search(words: list[str], source: str | None = None, max_words: int = 90, limit: int = 40,
           month: int | None = None) -> list[tuple[Unit, int, str]]:
    """Candidate search: sentences containing ALL words (normalized), shortest first."""
    ws = [norm(w) for w in words]
    allowed = pools()[month] if month else None
    out = []
    for u in load():
        if source and u.source != source:
            continue
        if allowed is not None and u.uid not in allowed:
            continue
        for i, s in enumerate(u.sentences):
            ns = norm(s)
            if all(w in ns for w in ws):
                n = len(s.split())
                if 6 <= n <= max_words:
                    out.append((u, i, s))
    out.sort(key=lambda x: len(x[2]))
    return out[:limit]


def stats() -> dict:
    us = load()
    by = {}
    for u in us:
        by.setdefault(u.source, [0, 0])
        by[u.source][0] += 1
        by[u.source][1] += len(u.sentences)
    return {k: {"units": v[0], "sentences": v[1]} for k, v in by.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    sub.add_parser("refresh")
    s = sub.add_parser("search")
    s.add_argument("words", nargs="+")
    s.add_argument("--source", choices=list("MES"))
    s.add_argument("--max", type=int, default=40)
    s.add_argument("--month", type=int, help="only passages in this month's pool")
    s.add_argument("--maxwords", type=int, default=90)
    r = sub.add_parser("read", help="print every numbered sentence of one passage, e.g. M:4.49 or S:13")
    r.add_argument("uid")
    f = sub.add_parser("find")
    f.add_argument("key")
    f.add_argument("--source", choices=list("MES"))
    f.add_argument("--after", type=int, default=0)
    f.add_argument("--before", type=int, default=0)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "refresh":
        load.cache_clear()
        load(True)
        print(json.dumps(stats(), indent=1))
    elif a.cmd == "stats":
        print(json.dumps(stats(), indent=1))
    elif a.cmd == "search":
        for u, i, s in search(a.words, a.source, max_words=a.maxwords, limit=a.max, month=a.month):
            print(f"[{u.source}] {u.uid} {u.citation} #{i} ({len(s.split())}w): {s}")
    elif a.cmd == "read":
        u = next((x for x in load() if x.uid == a.uid), None)
        if not u:
            print("no such passage"); return
        print(u.citation, getattr(u, "title", ""))
        for i, s in enumerate(u.sentences):
            print(f"#{i} ({len(s.split())}w) {s}")
    elif a.cmd == "find":
        hits = find(a.key, a.after, a.before, a.source)
        print(f"{len(hits)} hit(s)")
        for h in hits:
            print(f"- {h.citation} [{h.start}-{h.end}] ({len(h.text.split())}w): {h.text}")


if __name__ == "__main__":
    main()
