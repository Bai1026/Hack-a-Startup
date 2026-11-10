# Appealio demo video: what to run and what to say

The demo plays itself. You start the app, start the screen recorder, press Space,
and read the lines below. Every take is identical.

## 1. One-time setup

```bash
make setup        # Python env + node modules
make demo         # runs the AI pipeline on the 3 cases (needs ANTHROPIC_API_KEY in .env)
make check        # optional: re-verify the pipeline output against the source PDFs
```

`make demo` has already been run. Its output is in `data/cases/<id>/analysis.json`, and
model responses are cached in `out/cache/`, so running it again is free and gives the
same result.

## 2. Record

```bash
make web          # leave this running; app is on http://localhost:5173
```

1. Open Chrome at **http://localhost:5173/?autoplay=45**
2. Make the window full screen (`Ctrl+Cmd+F`). Record at 1920x1080.
3. Start the screen recorder (`Cmd+Shift+5` on macOS, record the whole screen).
4. Press **Space**. The demo runs for 45 seconds and ends on the Appealio title card.
5. Stop the recording. Trim the second before you pressed Space.

To do another take, reload the page and press Space again.

| URL | Length | Use |
|---|---|---|
| `/?autoplay=45` | 45 s | **Default.** One case, three beats. |
| `/?autoplay=30` | 30 s | Tight cut. Skips the "linked evidence" click. |
| `/?autoplay=60` | 60 s | Adds a second case where the app declines to recommend an appeal. |

Options you can add to the URL:

- `&captions=0` hides the subtitle bar (use this if you add a voiceover and your own subtitles).
- `&cursor=0` hides the animated pointer.
- `&source=gold` loads the hand-written answer key instead of the pipeline output. **Do not
  record with this.** The footer shows which one is loaded: it should read
  `source: pipeline (claude-sonnet-5-5)`.

## 3. What to say (45 second cut)

The subtitle bar shows each line at the moment you should say it. Read it live, or
record the voice afterwards and lay it over the video.

| Time | What happens on screen | Say |
|---|---|---|
| 0:00 | Case B-3117 opens. The denial reason is highlighted in the insurer's letter. | "Home health was denied. The insurer says the record does not show the patient is homebound." |
| 0:06 | **Analyze** is clicked. Six policy requirements resolve: two green, one red, three green. The recommendation banner slides in. | (pause) |
| 0:10 | An evidence chip is clicked. The record jumps to page 5, lines 10-11, key phrases highlighted. | "Appealio breaks the policy into requirements and links each one to the exact lines in the record." |
| 0:18 | The red requirement opens: **Evidence missing**, with the three closest passages. At 0:22 the first one is clicked: the blank form field on page 5. | "For homebound status, nothing qualifies. The form section was left blank. So it says evidence missing. It does not write around the gap." |
| 0:28 | **Use this basis** is clicked. The alternative basis §3.3 is selected, 3 of 3 supported, and the draft letter appears. | "The same policy covers home care in place of a facility stay, and the record supports all three conditions." |
| 0:32 | The cost evidence is clicked: page 6, both dollar figures highlighted. | "Including cost: 4,350 dollars at home against 10,400 in a facility." |
| 0:39 | The draft panel pulses; the pointer rests on the citation for the cost sentence. | "The draft says only what the record shows. Every sentence links back. Staff review and submit." |
| 0:45 | Title card: "Every claim links back to the record." | (silence, or your closing line) |

**60 second cut** adds, after 0:45:

| Time | What happens on screen | Say |
|---|---|---|
| 0:45 | Case C-4420 opens (lumbar MRI denied). | "And when the record does not support any route, it says that too." |
| 0:51 | The amber requirement opens: found 4 weeks, required at least 6. Red banner, draft marked "Not ready to send", Export disabled. | "Four of six weeks of therapy documented. No alternative basis. Next step: get the missing records." |

**30 second cut**: same lines, minus the 0:10 line. Speak a little faster.

## 4. The pitch in one breath (for the intro or outro slide)

> Hospitals lose appeals because nobody has time to prove each claim from the chart.
> Appealio reads the denial, the policy and the record, links every claim to the exact
> line, shows what is missing instead of writing around it, and finds the route the
> record actually supports. The AI proposes; code verifies every quote; staff decide.

Three things the judges should remember, in the order the video shows them:

1. **Linked evidence**: every requirement points to exact lines in the record.
2. **A visible gap**: "Evidence missing", with the near misses and why each one falls short.
3. **An alternative basis**: the same policy offers another route, and the record supports it 3 of 3.

## 5. If something goes wrong

| Problem | Fix |
|---|---|
| Page is blank or says "Loading…" | `make web` is not running, or port 5173 is taken by another app. |
| Footer says `source: gold` | The pipeline output is missing. Run `make demo`, then reload. |
| `make demo` fails on the API key | Put `ANTHROPIC_API_KEY=...` in `.env` at the repo root. |
| Space does nothing | Click once on the page so it has keyboard focus, then press Space. |
| Text looks small in the video | Record full screen at 1920x1080; do not zoom the browser. |

## 6. Clicking through by hand (for live Q&A)

Open **http://localhost:5173** with no parameters and click **Analyze**. Everything in
the autoplay is a real click: evidence chips, the clause numbers (they open the policy),
the denial quote (opens the letter), "Use this basis", and the numbered citations in the
draft. The case switcher at the top right loads the other two cases:

- **A-2048**: every requirement supported. Green banner, appeal on the stated basis.
- **C-4420**: 4 of 6 weeks of therapy, and the exception is contradicted by the record.
  Red banner, no appeal recommended.

All data is synthetic. Keep "Synthetic demo data" and "Review required" visible in the recording.
