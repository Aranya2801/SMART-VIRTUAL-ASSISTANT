"""Train the intent model that the assistant uses at runtime.

    python -m aria.train                 # writes models/intent_clf.joblib
    python -m aria.train --threshold 0.5
"""

from __future__ import annotations

import argparse
import time

from .data import build_split, load_clinc, training_set, unsupported_split
from .nlu.classifier import IntentClassifier


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="models/intent_clf.joblib")
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--kind", choices=["logreg", "svm"], default="logreg")
    ap.add_argument("--unweighted", action="store_true",
                    help="don't balance class weights (see docs/RESULTS.md for the trade-off)")
    ap.add_argument("--no-extra", action="store_true", help="CLINC only, skip data/aria_extra.tsv")
    args = ap.parse_args(argv)

    clinc = load_clinc()
    texts, labels = training_set(clinc, include_extra=not args.no_extra)
    # val is only needed for picking hyper-parameters (done in experiments/),
    # for the shipped model use it as extra training data
    seen, _ = unsupported_split(clinc)
    vt, vl, vg = build_split(clinc, "val", seen)
    for t, lbl, g in zip(vt, vl, vg):
        if g != "u_unseen":
            texts.append(t)
            labels.append(lbl)

    t0 = time.perf_counter()
    model = IntentClassifier.train(texts, labels, threshold=args.threshold, kind=args.kind,
                                   balanced=not args.unweighted)
    print(f"trained on {len(texts)} utterances, {len(set(labels))} classes "
          f"in {time.perf_counter() - t0:.1f}s")
    model.save(args.out)
    print(f"saved to {args.out}")


if __name__ == "__main__":
    main()
