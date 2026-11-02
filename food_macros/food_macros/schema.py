"""Data contracts.

Two layers:
  * LLM* models  -> what we ask the vision model to return (validated, never trusted blindly)
  * Food*/Meal*  -> what this module returns to the app (stable API contract)
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- What the vision model must return ----------

class Per100g(BaseModel):
    kcal: float = Field(ge=0, le=950)
    protein_g: float = Field(ge=0, le=100)
    carbs_g: float = Field(ge=0, le=100)
    fat_g: float = Field(ge=0, le=100)
    fiber_g: float = Field(default=0, ge=0, le=60)

    @field_validator("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", mode="before")
    @classmethod
    def _none_to_zero(cls, v):
        return 0 if v is None or v == "" else v


class LLMFoodItem(BaseModel):
    name: str
    canonical_key: str = Field(description="snake_case dish key, e.g. masala_dosa")
    portion_description: str = ""
    pieces: Optional[float] = Field(default=None, description="count of discrete pieces (idlis, rotis, naans, papads)")
    estimated_grams: float = Field(gt=0)
    estimated_ml: Optional[float] = Field(default=None, ge=0, description="only for liquids/gravies/drinks")
    typical_serving_g: Optional[float] = Field(default=None, gt=0, description="one normal Indian serving of this dish")
    confidence: float = Field(ge=0, le=1)
    per_100g: Per100g
    notes: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _pct_to_fraction(cls, v):  # model sometimes says 90 instead of 0.9
        if v is None:
            return 0.5
        v = float(v)
        return v / 100 if v > 1 else v

    @field_validator("portion_description", "notes", mode="before")
    @classmethod
    def _none_to_str(cls, v):
        return v or ""

    @field_validator("pieces", mode="before")
    @classmethod
    def _pieces(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return round(v * 2) / 2 if 0 < v <= 50 else None  # allow halves ("1.5 rotis")

    @field_validator("estimated_ml", "typical_serving_g", mode="before")
    @classmethod
    def _zero_to_none(cls, v):
        return None if v in (None, "", 0, 0.0) else v


class LLMResponse(BaseModel):
    is_food: bool
    items: List[dict] = Field(default_factory=list)  # validated per item in analyzer
    overall_notes: str = ""

    @field_validator("items", mode="before")
    @classmethod
    def _items_list(cls, v):
        return [i for i in (v or []) if isinstance(i, dict)]

    @field_validator("overall_notes", mode="before")
    @classmethod
    def _notes_str(cls, v):
        return v or ""


# ---------- What the app receives ----------

class Macros(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float


class FoodSize(BaseModel):
    grams: float
    ml: Optional[float] = None
    pieces: Optional[float] = Field(default=None, description="counted pieces; app shows -/+ and recalculates")
    piece_g: Optional[float] = Field(default=None, description="grams per piece used for the calculation")
    description: str
    category: Literal["small", "regular", "large"]
    servings: float = Field(description="grams / typical serving, e.g. 1.5 = one and a half servings")


class FoodLabel(BaseModel):
    name: str
    canonical_key: str
    size: FoodSize
    portion: str
    grams: float
    macros: Macros
    per_100g: Macros
    confidence: float
    needs_confirmation: bool
    macro_source: Literal["food_db", "model"]
    notes: str = ""


class MealResult(BaseModel):
    ok: bool = True
    is_food: bool
    items: List[FoodLabel]
    totals: Macros
    warnings: List[str] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: int
    cached: bool = False
    disclaimer: str = (
        "Estimates from a photo. Portion size is the biggest source of error; "
        "let the user adjust grams before logging."
    )
