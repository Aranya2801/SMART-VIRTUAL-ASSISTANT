"""The intents ARIA knows how to handle.

Anything that doesn't map to one of these is OUT_OF_SCOPE and the assistant
should say so instead of guessing.
"""

OUT_OF_SCOPE = "oos"

INTENTS = (
    "weather",
    "time",
    "date",
    "alarm",
    "reminder",
    "list_reminders",
    "timer",
    "calculator",
    "joke",
    "fun_fact",
    "play_music",
    "volume",
    "definition",
    "greeting",
    "goodbye",
    "help",
    "about",
    # not covered by CLINC150, trained only on data/aria_extra.tsv
    "news",
    "open_website",
    "web_search",
    "send_email",
    "screenshot",
    "motivation",
)

# intents that appear in the CLINC150 benchmark (see experiments/data.py)
CLINC_COVERED = INTENTS[:17]
