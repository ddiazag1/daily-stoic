# Daily Stoic

A Stoic reader with one page for each of the 366 days of the year. It installs to the home screen and works offline.

**Live:** https://ddiazag1.github.io/daily-stoic/

Each day has:

- a passage from Marcus Aurelius, Epictetus or Seneca;
- a short original reflection;
- one concrete thing to practise.

The app opens on today's page, using your local date. Navigation:

- swipe left or right, or use the arrow keys (press `t` to jump back to today);
- browse the year month by month;
- save the days you want to keep.

Notes are stored only on your device. You can export and import them as JSON.

## Sources

All three source texts are public-domain translations. They are downloaded at build time, and every quote is extracted from them by script. None is typed by hand.

| Author | Work | Translator | Source |
|---|---|---|---|
| Marcus Aurelius | *Meditations* | George Long | [Gutenberg #15877](https://www.gutenberg.org/cache/epub/15877/pg15877.txt) |
| Epictetus | *Discourses* and *Enchiridion* | George Long | [Gutenberg #10661](https://www.gutenberg.org/cache/epub/10661/pg10661.txt) |
| Seneca | *Moral Letters to Lucilius* 1–124 | Richard M. Gummere | [Wikisource](https://en.wikisource.org/wiki/Moral_letters_to_Lucilius) |

The titles, reflections, practices and month introductions are original writing for this project. **No text from Ryan Holiday's *The Daily Stoic*** (or any other modern book) is used. The project is not affiliated with that book or its authors.

## The year

| | Theme | | Theme |
|---|---|---|---|
| Jan | What Is Yours | Jul | The Obstacle |
| Feb | Mastering Emotion | Aug | Time and the Present |
| Mar | Seeing Clearly | Sep | Enough |
| Apr | The Work in Front of You | Oct | Nature and Change |
| May | Character | Nov | Mortality |
| Jun | Living With Others | Dec | The Examined Day |

All three authors appear every month. Across the year the count is Marcus 125, Epictetus 119 and Seneca 122.

## How it is built

```
scripts/corpus.py      download + clean the three texts, split sentences, find(key)
scripts/build.py       content/months/*.yaml  ->  data/entries.json  (+ verification)
content/months/MM.yaml one file per month: theme, intro, and the days
```

**Corpus.** `corpus.py` caches the raw downloads in `raw/`. That folder is not committed; `python scripts/corpus.py refresh` downloads the texts again. It then cleans them:

- strips the Gutenberg header, footer and Long's index;
- removes footnotes and markers like `[A]`, `[Greek: …]` glosses, cross-references like `(vii. 58; iv. 48)` and stray `+` marks;
- removes Wikisource page numbers, styles and references, plus Seneca's title lines.

Finally it splits each passage into sentences. The sentence splitter handles closing quotes after punctuation.

Citations look like *Marcus Aurelius, Meditations 4.49*, *Epictetus, Enchiridion 5*, *Epictetus, Discourses* and *Seneca, Letters 13*.

**Entries.** A day stores only a *key* (a short phrase from the passage) and optional `after` / `before` counts. The quote is the sentence containing the key, plus that many sentences before and after it, taken from the cleaned text. For example:

```yaml
- day: 14
  source: M            # M = Marcus, E = Epictetus, S = Seneca
  key: "Whatever man thou meetest with"
  after: 0
  before: 0
  title: What Do They Believe
  reflection: >
    Behavior makes more sense once you know what a person thinks is good. ...
  practice: In one conversation today, quietly guess what the other person values most.
```

**Verification.** `build.py` fails with a list of every problem if:

- a key matches nothing, or matches more than one place;
- two days use the same or overlapping sentences anywhere in the year;
- a quote is outside 6–110 words;
- the year is not exactly 366 days (Feb 29 included);
- a reflection is outside 40–60 words, a practice is 18 words or more, or a title is outside 2–5 words;
- a month is missing an author.

`--spotcheck N` re-finds N random built quotes in the *raw* downloaded files.

## Edit an entry and rebuild

```sh
pip install requests pyyaml
python scripts/corpus.py find "one poor leg" --source E   # check a key resolves to one passage
# edit content/months/10.yaml
python scripts/build.py --month 10                        # check just that month
python scripts/build.py                                   # full build -> data/entries.json
python scripts/build.py --spotcheck 20
```

Each build stamps a content hash into `sw.js`. Installed copies pick up the new version the next time they open online.

Two other commands help when choosing quotes. `python scripts/corpus.py search WORDS --source S --month 10` looks for candidate passages. `python scripts/build.py --pool 10` lists the passages reserved for October.

## Run locally

```sh
python -m http.server 8765
# open http://127.0.0.1:8765/
```

## Deploy

The site is plain static files. GitHub Pages serves this repo from `main` at the root. Push a rebuilt `data/entries.json` and `sw.js` along with any changed files, and Pages redeploys on its own.

## Choices made where the brief was open

- **The Ryan Holiday rule.** The instruction was truncated. It is read as *no text from that book*, which also matches copyright.
- **Quotes stay unique.** Each month draws from its own reserved set of passages, picked by theme keywords. No passage serves two months, and the full build also checks for any repeated sentence.
- **Light typographic changes.** These are made only when quotes are extracted: Gutenberg's `--` becomes an em dash and `_underscores_` for italics are dropped. Spelling and wording are untouched, including Long's "thou" and Gummere's "connexion".
- **Unnumbered Discourses.** Long's *Discourses* chapters have titles but no numbers in this edition, so they are cited simply as "Epictetus, Discourses".
- **No tracking.** No analytics, accounts or server. Saved days and notes stay in your browser's `localStorage`. Use Export to back them up or move them to another device.

## Design

The look is cool limestone with a verdigris accent. The one bold element is a large Roman-numeral day number, set to look carved into stone. Text is set in [Spectral](https://fonts.google.com/specimen/Spectral) (SIL Open Font License) at about 65 characters per line.

- Dark mode follows the system setting.
- Motion is reduced when the system asks for it.
- Keyboard focus is clearly visible.
- Text colours meet WCAG AA contrast.

Built with no framework: `index.html`, `app.js`, `styles.css` and a service worker.
