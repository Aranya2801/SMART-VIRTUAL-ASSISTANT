"""Benchmark ARIA's intent detection on CLINC150.

    python experiments/run_benchmark.py            # everything, ~3-4 min on a laptop
    python experiments/run_benchmark.py --quick    # fewer seeds / noise levels

Writes results/results.json, results/*.png and prints markdown tables that
go into docs/RESULTS.md.

Questions:
  Q1  How much better is a small learned classifier than the original
      keyword router, on the same intents?
  Q2  Can the assistant tell when a request is something it doesn't support?
      Compare a confidence threshold alone vs. also training an explicit
      reject class, and check the reject class on unsupported intents it
      never saw in training.
  Q3  How robust are the models to ASR-style transcription errors?
  Q4  How many examples per intent are actually needed?
  Q5  Is it fast enough to run on-device (per-utterance latency)?
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aria.data import CLINC_TO_ARIA, build_split, load_clinc, unsupported_split  # noqa: E402
from aria.nlu import rules  # noqa: E402
from aria.nlu.classifier import IntentClassifier  # noqa: E402
from aria.nlu.intents import OUT_OF_SCOPE  # noqa: E402
from experiments.noise import corrupt_all  # noqa: E402

OUT = ROOT / "results"


# --- metrics ------------------------------------------------------------------

def score(pred, gold, groups) -> dict:
    pred, gold, groups = map(np.asarray, (pred, gold, groups))
    res = {}
    m = groups == "in"
    res["in_acc"] = float((pred[m] == gold[m]).mean())
    res["in_false_reject"] = float((pred[m] == OUT_OF_SCOPE).mean())
    for g in ("u_seen", "u_unseen", "oos"):
        m = groups == g
        if m.any():
            res[f"reject_{g}"] = float((pred[m] == OUT_OF_SCOPE).mean())
    # headline: harmonic mean of in-scope accuracy and recall on the
    # requests the model never saw anything like (unseen intents + CLINC oos)
    m = np.isin(groups, ["u_unseen", "oos"])
    rej = float((pred[m] == OUT_OF_SCOPE).mean()) if m.any() else float("nan")
    res["reject_novel"] = rej
    a = res["in_acc"]
    if m.any():
        res["hmean"] = 0.0 if a + rej == 0 else 2 * a * rej / (a + rej)
    return res


def tune_threshold(model: IntentClassifier, texts, gold, groups, grid=None) -> float:
    """Pick the threshold with the best in-acc / rejection h-mean on val."""
    grid = grid if grid is not None else np.round(np.arange(0.05, 0.96, 0.05), 2)
    probs = model.predict_proba(texts)
    classes = np.array(model.classes)
    raw = classes[probs.argmax(1)]
    conf = probs.max(1)
    gold, groups = np.asarray(gold), np.asarray(groups)
    best, best_t = -1.0, 0.5
    for t in grid:
        pred = np.where(conf < t, OUT_OF_SCOPE, raw)
        m_in = groups == "in"
        a = (pred[m_in] == gold[m_in]).mean()
        r = (pred[~m_in] == OUT_OF_SCOPE).mean()
        h = 2 * a * r / (a + r) if a + r else 0
        if h > best:
            best, best_t = h, float(t)
    return best_t


# --- systems --------------------------------------------------------------------

def make_systems(clinc, seen, per_intent=None, seed=0):
    tr_t, tr_l, tr_g = build_split(clinc, "train", seen, per_intent=per_intent, seed=seed)
    va_t, va_l, va_g = build_split(clinc, "val", seen)
    tr = list(zip(tr_t, tr_l, tr_g))
    va = list(zip(va_t, va_l, va_g))

    def subset(rows, allowed):
        rows = [r for r in rows if r[2] in allowed]
        return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]

    systems = {}
    # threshold only: train on in-scope only, tune threshold with CLINC oos val
    in_t, in_l, _ = subset(tr, {"in"})
    vt, vl, vg = subset(va, {"in", "oos"})
    for name, kw in [("LR word, threshold", dict(char=False)),
                     ("LR word+char, threshold", dict())]:
        m = IntentClassifier.train(in_t, in_l, **kw)
        m.threshold = tune_threshold(m, vt, vl, vg)
        systems[name] = m

    # explicit reject class: add seen-unsupported intents + CLINC oos_train
    rj_t, rj_l, _ = subset(tr, {"in", "u_seen", "oos"})
    vt, vl, vg = subset(va, {"in", "u_seen", "oos"})
    for name, kw in [("LR word+char, reject class", dict()),
                     ("LR word+char, reject class, balanced", dict(balanced=True)),
                     ("SVM word+char, reject class", dict(kind="svm"))]:
        m = IntentClassifier.train(rj_t, rj_l, **kw)
        m.threshold = tune_threshold(m, vt, vl, vg)
        systems[name] = m
    return systems


def predict(system, texts):
    if system == "rules (substring, original)":
        return [rules.classify(t, word_boundary=False) for t in texts]
    if system == "rules (word boundary)":
        return [rules.classify(t, word_boundary=True) for t in texts]
    return system.predict(texts)


RULE_SYSTEMS = ["rules (substring, original)", "rules (word boundary)"]


# --- experiments ----------------------------------------------------------------

def exp_main(clinc, seen, test, seeds):
    """Q1 + Q2. Models retrained per seed (the learners are deterministic,
    seeds change which unsupported intents count as 'seen')."""
    per_seed = []
    systems = None
    for s in seeds:
        seen_s, _ = unsupported_split(clinc, seed=s)
        te = build_split(clinc, "test", seen_s)
        systems = make_systems(clinc, seen_s)
        row = {}
        for name in RULE_SYSTEMS:
            row[name] = score(predict(name, te[0]), te[1], te[2])
        for name, m in systems.items():
            row[name] = score(m.predict(te[0]), te[1], te[2]) | {"threshold": m.threshold}
        per_seed.append(row)
    names = list(per_seed[0])
    agg = {}
    for n in names:
        keys = per_seed[0][n].keys()
        agg[n] = {k: (float(np.mean([r[n][k] for r in per_seed])),
                      float(np.std([r[n][k] for r in per_seed]))) for k in keys}
    return agg, systems


def exp_noise(clinc, seen, test, systems, levels, seeds):
    """Q3: in-scope accuracy under corruption."""
    te_t, te_l, te_g = test
    in_t = [t for t, g in zip(te_t, te_g) if g == "in"]
    in_l = [lbl for lbl, g in zip(te_l, te_g) if g == "in"]
    groups = ["in"] * len(in_t)
    names = ["rules (word boundary)", "LR word, threshold", "LR word+char, threshold",
             "LR word+char, reject class", "LR word+char, reject class, balanced"]
    out = {n: [] for n in names}
    examples = []
    for p in levels:
        for n in names:
            accs = []
            for s in seeds:
                noisy = corrupt_all(in_t, p, seed=1000 + s)
                sysobj = n if n in RULE_SYSTEMS else systems[n]
                accs.append(score(predict(sysobj, noisy), in_l, groups)["in_acc"])
            out[n].append((p, float(np.mean(accs)), float(np.std(accs))))
        if p in (0.1, 0.2):
            noisy = corrupt_all(in_t[:400:40], p, seed=1000)
            examples += [(p, a, b) for a, b in zip(in_t[:400:40], noisy) if a != b][:4]
    return out, examples


def exp_learning_curve(clinc, seen, test, ks, seeds, balanced=False):
    """Q4: examples per in-scope intent (reject class kept at full size)."""
    te_t, te_l, te_g = test
    out = []
    for k in ks:
        accs, rejs = [], []
        for s in seeds:
            tr_t, tr_l, tr_g = build_split(clinc, "train", seen, seed=s)
            rng = np.random.default_rng(s)
            keep, count = [], Counter()
            for i in rng.permutation(len(tr_t)):
                if tr_g[i] == "u_unseen":
                    continue
                if tr_g[i] == "in":
                    if count[tr_l[i]] >= k:
                        continue
                    count[tr_l[i]] += 1
                keep.append(i)
            m = IntentClassifier.train([tr_t[i] for i in keep], [tr_l[i] for i in keep],
                                       balanced=balanced)
            va = build_split(clinc, "val", seen)
            sel = [i for i, g in enumerate(va[2]) if g != "u_unseen"]
            m.threshold = tune_threshold(m, [va[0][i] for i in sel], [va[1][i] for i in sel],
                                         [va[2][i] for i in sel])
            r = score(m.predict(te_t), te_l, te_g)
            accs.append(r["in_acc"])
            rejs.append(r["reject_novel"])
        out.append((k, float(np.mean(accs)), float(np.std(accs)), float(np.mean(rejs))))
        print(f"  k={k:>3} balanced={balanced}  in_acc={np.mean(accs):.3f}  reject_novel={np.mean(rejs):.3f}")
    return out


def exp_latency(systems, texts, n=500):
    """Q5: single-utterance latency, which is what matters in a voice loop."""
    texts = texts[:n]
    out = {}
    for name in ["rules (word boundary)", "LR word+char, reject class",
                 "LR word+char, reject class, balanced", "SVM word+char, reject class"]:
        times = []
        for t in texts:
            t0 = time.perf_counter()
            if name in RULE_SYSTEMS:
                rules.classify(t)
            else:
                systems[name].predict_one(t)
            times.append((time.perf_counter() - t0) * 1000)
        out[name] = (float(np.percentile(times, 50)), float(np.percentile(times, 95)))
    return out


def error_analysis(clinc, seen, test, model):
    te_t, te_l, te_g = test
    pred = model.predict(te_t)
    orig = [lbl for _, lbl in clinc["test"]] + ["oos"] * len(clinc["oos_test"])
    confusions = Counter()
    leaks = Counter()
    for p, g, grp, o in zip(pred, te_l, te_g, orig):
        if grp == "in" and p != g:
            confusions[(g, p)] += 1
        elif grp != "in" and p != OUT_OF_SCOPE:
            leaks[(o, p)] += 1
    return confusions.most_common(8), leaks.most_common(10)


# --- reporting ------------------------------------------------------------------

def pct(x):
    return f"{100 * x:.1f}"


def main_table(agg):
    cols = [("in_acc", "In-scope acc"), ("reject_u_seen", "Reject: seen unsupp."),
            ("reject_u_unseen", "Reject: unseen unsupp."), ("reject_oos", "Reject: CLINC oos"),
            ("hmean", "H-mean")]
    lines = ["| System | " + " | ".join(c[1] for c in cols) + " |",
             "|---|" + "---:|" * len(cols)]
    for name, r in agg.items():
        cells = []
        for k, _ in cols:
            mean, sd = r[k]
            cells.append(pct(mean) + (f" ± {pct(sd)}" if sd > 0.0005 else ""))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def plots(noise, curve, curve_bal, systems, clinc, seen, test):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for name, pts in noise.items():
        xs = [100 * p for p, _, _ in pts]
        ys = [100 * m for _, m, _ in pts]
        ax.errorbar(xs, ys, yerr=[100 * s for _, _, s in pts], marker="o", ms=4, capsize=2, label=name)
    ax.set_xlabel("word corruption rate (%)")
    ax.set_ylabel("in-scope accuracy (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "noise_robustness.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ks = [k for k, *_ in curve]
    for c, tag, ls in ((curve, "unweighted", "--"), (curve_bal, "balanced", "-")):
        ax.errorbar(ks, [100 * m for _, m, _, _ in c], yerr=[100 * s for _, _, s, _ in c],
                    marker="o", ms=4, capsize=2, ls=ls, color="C0", label=f"in-scope acc ({tag})")
        ax.plot(ks, [100 * r for *_, r in c], marker="s", ms=4, ls=ls, color="C1",
                label=f"novel rejected ({tag})")
    ax.set_xscale("log")
    ax.set_xticks(ks)
    ax.set_xticklabels(ks)
    ax.set_xlabel("training examples per supported intent")
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "learning_curve.png", dpi=160)
    plt.close(fig)

    # threshold trade-off for the two LR word+char variants
    te_t, te_l, te_g = test
    te_l, te_g = np.asarray(te_l), np.asarray(te_g)
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    for name in ["LR word+char, threshold", "LR word+char, reject class",
                 "LR word+char, reject class, balanced"]:
        m = systems[name]
        probs = m.predict_proba(te_t)
        raw = np.array(m.classes)[probs.argmax(1)]
        conf = probs.max(1)
        xs, ys = [], []
        for t in np.linspace(0, 0.99, 60):
            pred = np.where(conf < t, OUT_OF_SCOPE, raw)
            novel = np.isin(te_g, ["u_unseen", "oos"])
            xs.append(100 * (pred[novel] == OUT_OF_SCOPE).mean())
            ys.append(100 * (pred[te_g == "in"] == te_l[te_g == "in"]).mean())
        ax.plot(xs, ys, label=name)
        pred = np.where(conf < m.threshold, OUT_OF_SCOPE, raw)
        ax.scatter([100 * (pred[np.isin(te_g, ['u_unseen', 'oos'])] == OUT_OF_SCOPE).mean()],
                   [100 * (pred[te_g == "in"] == te_l[te_g == "in"]).mean()], s=25, zorder=3)
    ax.set_xlim(60, 100)
    ax.set_ylim(60, 100)
    ax.set_xlabel("rejection of novel requests (%)")
    ax.set_ylabel("in-scope accuracy (%)")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "threshold_tradeoff.png", dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    seeds = [0] if args.quick else [0, 1, 2]
    levels = [0, 0.1, 0.2] if args.quick else [0, 0.05, 0.1, 0.15, 0.2, 0.3]
    ks = [5, 20, 100] if args.quick else [5, 10, 20, 50, 100]

    clinc = load_clinc()
    seen, unseen = unsupported_split(clinc, seed=0)
    test = build_split(clinc, "test", seen)
    print(f"supported CLINC intents: {len(CLINC_TO_ARIA)}  seen-unsupported: {len(seen)}  "
          f"unseen-unsupported: {len(unseen)}")
    print("test groups:", dict(Counter(test[2])))

    t0 = time.time()
    print("\n[Q1/Q2] main comparison")
    agg, systems = exp_main(clinc, seen, test, seeds)
    # exp_main leaves systems trained on the last seed; retrain on seed 0 for the rest
    systems = make_systems(clinc, seen)
    print(main_table(agg))

    print("\n[Q3] ASR-style noise")
    noise, noise_examples = exp_noise(clinc, seen, test, systems, levels, seeds)
    for n, pts in noise.items():
        print(f"  {n:<28}" + "  ".join(f"{100*p:>4.0f}%:{100*m:5.1f}" for p, m, _ in pts))

    print("\n[Q4] learning curve")
    curve = exp_learning_curve(clinc, seen, test, ks, seeds)
    curve_bal = exp_learning_curve(clinc, seen, test, ks, seeds, balanced=True)

    print("\n[Q5] latency")
    lat = exp_latency(systems, test[0])
    for n, (p50, p95) in lat.items():
        print(f"  {n:<28} p50 {p50:.2f} ms   p95 {p95:.2f} ms")

    conf, leaks = error_analysis(clinc, seen, test, systems["LR word+char, reject class"])
    print("\ntop in-scope confusions:", conf)
    print("top unsupported requests that got accepted:", leaks)

    plots(noise, curve, curve_bal, systems, clinc, seen, test)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "results.json", "w") as fh:
        json.dump({
            "seeds": seeds,
            "main": agg,
            "noise": noise,
            "noise_examples": noise_examples,
            "learning_curve": curve,
            "learning_curve_balanced": curve_bal,
            "latency_ms": lat,
            "confusions": [[list(k), v] for k, v in conf],
            "accepted_unsupported": [[list(k), v] for k, v in leaks],
            "thresholds": {n: m.threshold for n, m in systems.items()},
        }, fh, indent=2)
    print(f"\ndone in {time.time() - t0:.0f}s, wrote {OUT}/")


if __name__ == "__main__":
    main()
