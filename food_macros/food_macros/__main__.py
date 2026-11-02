"""CLI:  python -m food_macros path/to/photo.jpg [--hint "home cooked, less oil"] [--json]"""
import argparse
import sys

from . import AnalysisError, analyze_food_image


def main() -> int:
    ap = argparse.ArgumentParser(description="Food photo -> labels + macros")
    ap.add_argument("image")
    ap.add_argument("--hint", default=None)
    ap.add_argument("--json", action="store_true", help="print raw JSON")
    args = ap.parse_args()

    try:
        r = analyze_food_image(args.image, hint=args.hint)
    except (AnalysisError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(r.model_dump_json(indent=2))
        return 0

    if not r.is_food:
        print("No food detected.")
        return 0
    print(f"{'Item':26} {'Size':30} {'g':>6} {'kcal':>6} {'P':>5} {'C':>5} {'F':>5}")
    for i in r.items:
        flag = " ?" if i.needs_confirmation else ""
        m = i.macros
        sz = f"{i.size.category}, {i.size.description}" + (f", {i.size.ml:.0f} ml" if i.size.ml else "")
        print(f"{(i.name + flag)[:26]:26} {sz[:30]:30} {i.grams:6.0f} {m.kcal:6.0f} "
              f"{m.protein_g:5.1f} {m.carbs_g:5.1f} {m.fat_g:5.1f}")
    t = r.totals
    print(f"{'TOTAL':57} {t.kcal:6.0f} {t.protein_g:5.1f} {t.carbs_g:5.1f} {t.fat_g:5.1f}")
    for w in r.warnings:
        print(f"! {w}")
    print(f"({r.provider}/{r.model}, {r.latency_ms} ms{', cached' if r.cached else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
