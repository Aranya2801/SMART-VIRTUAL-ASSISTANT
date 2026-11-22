"""Run the assistant.

    python -m aria            # text mode (type commands)
    python -m aria --voice    # microphone + speech
"""

from __future__ import annotations

import argparse
import logging
import sys

from .assistant import Assistant
from .config import load_settings
from .speech import ConsoleSpeaker


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aria")
    ap.add_argument("--voice", action="store_true", help="use the microphone and TTS")
    ap.add_argument("--text", action="store_true", help="force text mode")
    ap.add_argument("--config", help="path to a config.json")
    ap.add_argument("--debug", action="store_true", help="print intent/confidence for each turn")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings(args.config)
    voice = args.voice or (settings.mode == "voice" and not args.text)

    listener = None
    if voice:
        from .speech import Listener, TTSSpeaker
        try:
            speaker = TTSSpeaker(settings.voice_rate, settings.voice_volume, settings.voice_index)
            listener = Listener(settings.language)
        except Exception as exc:  # no mic, no portaudio, no espeak...
            print(f"voice mode unavailable ({exc}); falling back to text", file=sys.stderr)
            speaker, listener = ConsoleSpeaker(), None
    else:
        speaker = ConsoleSpeaker()

    bot = Assistant(settings, speaker)
    if bot.nlu.model is None:
        print("(no trained model found - using keyword rules. Run `python -m aria.train` for the real thing)",
              file=sys.stderr)
    bot.handle("hello")
    try:
        while bot.running:
            if listener:
                speaker.wait()  # don't listen to ourselves talking
                print("listening...", flush=True)
                text = listener.listen()
                if text:
                    print(f"you: {text}")
            else:
                try:
                    text = input("you: ")
                except EOFError:
                    break
            if args.debug and text and bot.nlu.model is not None:
                p = bot.nlu.parse(text)
                print(f"  [{p.intent} {p.confidence:.2f} {p.slots}]", file=sys.stderr)
            bot.handle(text)
    except KeyboardInterrupt:
        print()
    finally:
        speaker.wait()
        bot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
