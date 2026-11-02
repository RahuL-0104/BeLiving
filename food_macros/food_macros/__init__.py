"""BeLiving food recognition: photo in -> food labels + macros out."""
from pathlib import Path

import os

from dotenv import dotenv_values

# Load only this module's own .env (food_macros/.env), never parent folders. Filled-in values win over
# stale system settings (e.g. an old GEMINI_MODEL); blank lines like "GEMINI_API_KEY=" don't wipe values
# a launcher or the platform's secret store already provided.
for _k, _v in dotenv_values(Path(__file__).resolve().parent.parent / ".env").items():
    if _v:
        os.environ[_k] = _v

from .analyzer import (  # noqa: E402
    AnalysisError,
    FoodAnalyzer,
    ImageError,
    ProviderUnavailable,
    analyze_food_image,
)
from .schema import FoodLabel, Macros, MealResult  # noqa: E402

__all__ = [
    "FoodAnalyzer", "analyze_food_image", "AnalysisError", "ImageError", "ProviderUnavailable",
    "MealResult", "FoodLabel", "Macros",
]
__version__ = "1.0.0"
