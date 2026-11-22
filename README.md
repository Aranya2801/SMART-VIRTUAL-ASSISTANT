# ARIA: a small voice assistant that knows what it can't do

[![tests](https://github.com/Aranya2801/SMART-VIRTUAL-ASSISTANT/actions/workflows/ci.yml/badge.svg)](https://github.com/Aranya2801/SMART-VIRTUAL-ASSISTANT/actions/workflows/ci.yml)

ARIA is a Python voice assistant that runs on your own laptop. It handles
the usual things (time, weather, news, Wikipedia, reminders, alarms, timers,
quick maths, opening sites, playing music, sending email) and, more
importantly, it notices when you ask for something it *can't* do and says so
instead of guessing.

It started as our 3rd-year minor project at KIIT in 2023. That version
matched keywords in a long `if/elif` chain. This repo is a rewrite around a
proper NLU pipeline, plus a set of experiments on CLINC150 to back up the
design choices.

**Main results** (details in [docs/RESULTS.md](docs/RESULTS.md)):

- On the 18 CLINC150 intents ARIA supports, the original keyword router gets
  **28.8%** of requests right. A TF-IDF (word + char n-gram) logistic
  regression gets **89.6–93.6%**, depending on how it handles rejection.
- Training an explicit "reject" class from *some* unsupported intents still
  rejects **97.4%** of requests from 66 unsupported intents it never saw,
  vs. 91.6% for a tuned confidence threshold.
- Under simulated speech-recognition errors (30% of words corrupted),
  word-only features lose 20 points of accuracy, word+char features 14, and
  the class-balanced word+char model that ARIA ships with only 10.
- ~1 ms per utterance on CPU, no GPU or cloud NLU needed.

```
you: what's the weather like in pune
ARIA: In Pune it's 24 degrees with light rain. Humidity is 81 percent.
you: remind me to call mom
ARIA: When? For example 'in 20 minutes' or 'at 6 pm'.
you: in 20 minutes
ARIA: Okay, I'll remind you to call mom in 20 minutes.
you: what's my credit card balance
ARIA: I can't help with that one myself. Want me to search the web for it?
you: no
ARIA: No problem.
```

## How it works

```
 mic ──► SpeechRecognition (Google STT, en-IN)
                 │ text
                 ▼
        ┌──────────────────┐   intent + confidence
        │ intent classifier│──────────────┐
        │ TF-IDF word+char │              │ below threshold / "oos"
        │ + logistic reg.  │              ▼
        └──────────────────┘     "I can't do that, search the web?"
                 │
                 ▼
        slot extraction (regex: city, duration, clock time, topic, ...)
                 │
                 ▼
        dialogue manager ── missing slot? ask, wait for the next utterance
                 │
                 ▼
        skill handlers ──► scheduler thread (reminders / alarms / timers)
                 │
                 ▼
        TTS worker thread (pyttsx3) ──► speaker
```

A few things that were broken in the old version and how they're handled now:

| Problem in v2 | Now |
|---|---|
| Keyword matching: "stop" anywhere quit the app, "what is" always meant the calculator, unknown requests opened Google | Learned intent model with an out-of-scope class; web search only after you say yes |
| `eval()` on whatever the user said for the calculator | `ast`-based evaluator that only allows numbers and arithmetic (`aria/calc.py`) |
| Follow-up questions used `input()`, so voice mode needed a keyboard | Dialogue manager keeps the pending slot and fills it from the next utterance, spoken or typed |
| Every reminder spawned a sleeping thread and called `pyttsx3` from it, which isn't thread-safe | One scheduler thread for all jobs; one TTS thread owns the engine and everything else queues text |
| Alarms polled the clock every 30 s forever and couldn't be cancelled | Jobs can be listed ("what alarms do I have") and cancelled |
| "open xyz" went to `https://www.xyz.com` | Known sites from a list, everything else goes through a search |
| Volume/screenshot only worked on Linux via `os.system` | `pactl`/`amixer` on Linux, AppleScript on macOS, `pycaw` on Windows, Pillow for screenshots |
| API keys hard-coded as placeholders in the source | Config file or `ARIA_*` environment variables |
| Two diverging copies of the code (`assistant.py`, `src/assistant.py`), no tests | One package, 64 tests, CI |

## Running it

Needs Python 3.10+.

```bash
git clone https://github.com/Aranya2801/SMART-VIRTUAL-ASSISTANT.git
cd SMART-VIRTUAL-ASSISTANT
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m aria.train        # downloads CLINC150 (~2.5 MB) and trains the model, ~10 s
python -m aria              # text mode
python -m aria --voice      # microphone + speech
```

Voice mode needs PortAudio for the microphone and a TTS backend:

- Ubuntu/Debian: `sudo apt install portaudio19-dev espeak-ng`
- macOS: `brew install portaudio`
- Windows: `pip install pyaudio` usually just works now (wheels are on PyPI)

If the mic or TTS can't start, ARIA drops back to text mode and tells you why.
Add `--debug` to see the predicted intent, confidence and slots for each turn.

### API keys

Weather, news and email need credentials. Either export them:

```bash
export ARIA_WEATHER_API_KEY=...    # openweathermap.org, free tier is fine
export ARIA_NEWS_API_KEY=...       # newsapi.org
export ARIA_EMAIL=you@gmail.com
export ARIA_EMAIL_PASSWORD=...     # a Gmail *app password*, not your real one
```

or copy `config.example.json` to `config.json` and fill it in (it's
git-ignored). Any setting in `aria/config.py` can be set either way, e.g.
`ARIA_DEFAULT_CITY=Bhubaneswar`.

## Things you can say

| | examples |
|---|---|
| time / date | "what time is it", "what's the date today" |
| weather | "weather in delhi", "will it rain tomorrow" (uses `default_city`) |
| news | "read me the headlines" |
| Wikipedia | "who was ada lovelace", "tell me about black holes" |
| maths | "what is 15 percent of 240", "square root of 144", "12 times 7 plus 3" |
| reminders | "remind me to drink water in 30 minutes", "what reminders do I have", "cancel all reminders" |
| timers / alarms | "set a timer for 5 minutes", "wake me up at 6:30 am" |
| web | "open github", "search for gate syllabus", "play lofi on youtube" |
| system | "turn the volume down", "take a screenshot" |
| email | "send an email" (asks for recipient, subject and body, then confirms) |
| other | "tell me a joke", "fun fact", "motivate me", "what can you do", "bye" |

Say "never mind" in the middle of a follow-up question to drop it.

## Reproducing the experiments

```bash
pip install -r requirements-dev.txt
python experiments/run_benchmark.py          # full run, ~2-3 min
python experiments/run_benchmark.py --quick  # 1 seed, fewer settings
pytest
```

Results go to `results/` and are written up in
[docs/RESULTS.md](docs/RESULTS.md). CI runs the quick benchmark on every push
so the numbers can't silently rot.

## Layout

```
aria/
  __main__.py      CLI entry point (python -m aria)
  assistant.py     dialogue manager: pending slots, confirmations
  skills.py        one function per intent
  scheduler.py     reminders / alarms / timers on a single thread
  speech.py        TTS worker thread, microphone listener
  calc.py          safe spoken-arithmetic evaluator
  config.py        settings from config.json + ARIA_* env vars
  data.py          CLINC150 loading and intent mapping
  train.py         trains models/intent_clf.joblib
  nlu/
    classifier.py  TF-IDF + LR/SVM, save/load, rejection threshold
    rules.py       the original keyword router (kept as a baseline)
    slots.py       regex slot extractors
    intents.py     list of supported intents
data/aria_extra.tsv  hand-written examples for intents CLINC doesn't have
experiments/       benchmark + ASR noise simulation
results/           benchmark output (json + figures)
tests/             pytest suite, no network or audio needed
docs/              results write-up, 2023 report and screenshots
```

## Limitations and next steps

- Evaluated on typed text (CLINC150) with *simulated* recognition errors. The
  obvious next step is testing on real recordings, e.g. SLURP, or recording
  people reading the test set through the actual STT.
- English only. Hindi/Bengali-English code-mixing is a real gap for the
  people this was originally meant for.
- Speech recognition still goes to Google's free web API. Swapping in
  an offline model (Vosk or whisper.cpp) would make the whole thing work
  without internet.
- The most common false accepts are near-misses like "what time is it in
  Tokyo" being treated as plain `time`. More targeted negatives, or just
  implementing time zones, would fix most of them.
- Slots are regex-based. Fine for times and durations, weak for free-form
  things like song titles.

## History

The first version was built in April 2023 as the minor project for our
B.Tech (IT) at KIIT, Bhubaneswar, by Aritro Acharya, Aranya Ghosh, Souvik
Hazra and Rajdeep Ghosh, under the guidance of Mr. Madhabananda Das. The
original report is in [docs/minor-project-report.pdf](docs/minor-project-report.pdf)
and screenshots of that version are in [docs/screenshots](docs/screenshots).

Version 3 (this one) is a rewrite by Aranya Ghosh: the NLU pipeline,
dialogue manager, scheduler and the CLINC150 experiments.

## License

MIT, see [LICENSE](LICENSE). CLINC150 is CC BY 3.0 and is downloaded at
training time rather than included here.
