"""CLI: python -m app.evaluation.run_benchmark [--write]
--write stores the result as benchmarks/expected_results/benchmark_results.json (the 'saved results')."""
import sys

from app.evaluation.benchmark import run_benchmark, saved_results_path


def _f(x):
    return "n/a" if x is None else f"{x:.3f}"


def main() -> None:
    r = run_benchmark()
    print(f"{'split':<9}{'cases':>6}{'TP':>5}{'FP':>5}{'TN':>5}{'FN':>5}{'prec':>8}{'recall':>8}{'FPR':>8}")
    for name, m in (("overall", r.overall), ("dev", r.dev), ("heldout", r.heldout)):
        print(f"{name:<9}{m.scenarios:>6}{m.tp:>5}{m.fp:>5}{m.tn:>5}{m.fn:>5}{_f(m.precision):>8}{_f(m.recall):>8}{_f(m.false_positive_rate):>8}")
    print("\nMisses and false alarms:")
    for s in r.scenario_results:
        if s.false_positives or s.false_negatives:
            print(f"  {s.scenario_id} ({s.split}): FP={s.false_positives} FN={s.false_negatives}")
    if "--write" in sys.argv:
        p = saved_results_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(r.model_dump_json(indent=2))
        print("\nwrote", p)


if __name__ == "__main__":
    main()
