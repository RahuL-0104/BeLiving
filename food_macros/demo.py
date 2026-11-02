"""Food Scan: type a photo path, get food labels, size and macros.

Run from VS Code: open demo.py and click Run (the play button), then paste a photo path.
Or:  python demo.py                 (asks for paths one by one)
     python demo.py photo1.jpg ...  (scans the given photos and exits)
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESKTOP = HERE.parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))


def _bootstrap() -> None:
    """If run with a Python that lacks the packages (e.g. VS Code's Run button),
    build food_macros/.venv once and re-launch inside it."""
    try:
        import dotenv, fastapi, google.genai, openai, PIL, pydantic  # noqa: F401,E401
        return
    except ImportError:
        pass
    venv_py = HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if Path(sys.executable).resolve() == venv_py.resolve():
        subprocess.check_call([str(venv_py), "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        return
    if not venv_py.exists():
        print("First run: creating .venv and installing packages (1-2 min)...", flush=True)
        subprocess.check_call([sys.executable, "-m", "venv", str(HERE / ".venv")])
        subprocess.check_call([str(venv_py), "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    sys.exit(subprocess.call([str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]]))


_bootstrap()

from dotenv import dotenv_values, load_dotenv  # noqa: E402

# Key: this folder's .env first, else reuse the chatbot's Gemini key (read locally, never printed).
load_dotenv(HERE / ".env")
if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
    for env in (DESKTOP / "chatbot" / ".env",):
        if env.exists():
            vals = dotenv_values(env)
            key = vals.get("GEMINI_API_KEY") or vals.get("GOOGLE_API_KEY")
            if key:
                os.environ["GEMINI_API_KEY"] = key
                print(f"Using Gemini key from {env.parent.name}\\.env\n")
                break

# Use this module's model unless food_macros/.env names one (ignores stale system-wide GEMINI_MODEL).
_local_env = dotenv_values(HERE / ".env") if (HERE / ".env").exists() else {}
os.environ["GEMINI_MODEL"] = _local_env.get("GEMINI_MODEL") or "gemini-3.8-flash"

import logging  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  ... %(message)s")

from food_macros import AnalysisError, FoodAnalyzer  # noqa: E402

def show(path: Path, analyzer: FoodAnalyzer) -> None:
    print("=" * 96)
    print(f"PHOTO: {path.name}")
    print("=" * 96)
    try:
        r = analyzer.analyze(path)
    except AnalysisError as exc:
        print(f"  Failed: {exc}\n")
        return
    if not r.is_food:
        print("  No food detected.\n")
        return
    print(f"  {'Food':24} {'Size':34} {'kcal':>6} {'Prot':>6} {'Carb':>6} {'Fat':>6} {'Fib':>5}")
    print("  " + "-" * 92)
    for i in r.items:
        s, m = i.size, i.macros
        name = i.name + (" (?)" if i.needs_confirmation else "")
        count = f"{s.pieces:g}x{s.piece_g:g}g=" if s.pieces else ""
        size = f"{s.category.upper()} {count}{s.grams:.0f}g" + (f"/{s.ml:.0f}ml" if s.ml else "") + f" {s.description}"
        print(f"  {name[:24]:24} {size[:34]:34} {m.kcal:6.0f} {m.protein_g:6.1f} {m.carbs_g:6.1f} "
              f"{m.fat_g:6.1f} {m.fiber_g:5.1f}")
        print(f"  {'':24} {f'{s.servings}x serving, {i.confidence:.0%} sure, macros from {i.macro_source}':60}")
    t = r.totals
    print("  " + "-" * 92)
    print(f"  {'TOTAL':59} {t.kcal:6.0f} {t.protein_g:6.1f} {t.carbs_g:6.1f} {t.fat_g:6.1f} {t.fiber_g:5.1f}")
    for w in r.warnings:
        print(f"  ! {w}")
    print(f"  ({r.model}, {r.latency_ms / 1000:.1f}s)\n")


class _Tee:
    """Print to the terminal and also save to demo_output.txt."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()

    def flush(self):
        for st in self.streams:
            st.flush()


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".avif"}


def clean_path(raw: str) -> Path:
    """Accept paths pasted from Explorer ('Copy as path' adds quotes) or relative to the Desktop."""
    p = Path(raw.strip().strip('"').strip("'").strip())
    if not p.is_absolute() and not p.exists() and (DESKTOP / p).exists():
        p = DESKTOP / p
    return p


def main() -> int:
    sys.stdout = _Tee(sys.__stdout__, open(HERE / "demo_output.txt", "a", encoding="utf-8"))
    try:
        analyzer = FoodAnalyzer()
    except Exception as exc:  # noqa: BLE001
        print(f"Setup problem: {exc}\nPaste GEMINI_API_KEY into food_macros\\.env and run again.")
        return 1

    if sys.argv[1:]:  # paths given on the command line: scan them and exit
        for a in sys.argv[1:]:
            show(clean_path(a), analyzer)
        return 0

    print("BeLiving Food Scan")
    print("Paste a photo path and press Enter (e.g. C:\\Users\\you\\Desktop\\thali.jpg or just thali.jpg).")
    print("Type q to quit.\n")
    while True:
        try:
            raw = input("Photo path> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if raw.strip().lower() in {"q", "quit", "exit"}:
            break
        if not raw.strip():
            continue
        path = clean_path(raw)
        if not path.is_file():
            print(f"  Can't find that file: {path}\n")
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            print(f"  That's not an image ({path.suffix}). Use .jpg, .png or .webp.\n")
            continue
        show(path, analyzer)
    print("Bye! Results are saved in demo_output.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
