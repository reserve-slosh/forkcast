"""Shared fixtures for ForkCast tests."""
import json
import pytest
from datetime import date, timedelta


def freeze_date(monkeypatch, frozen: date):
    """Patch planner.date so date.today() returns `frozen`."""
    import planner

    class FakeDate(date):
        @classmethod
        def today(cls):
            return frozen

        @classmethod
        def fromisoformat(cls, s):
            return date.fromisoformat(s)

    monkeypatch.setattr(planner, "date", FakeDate)


def make_recipe(id_, cuisine="Italienisch", diet="vegan", season=None,
               cost="budget", tags=None, ingredients=None):
    return {
        "id": id_,
        "name": id_.replace("_", " ").title(),
        "cuisine": cuisine,
        "diet": diet,
        "season": season or ["spring", "summer", "autumn", "winter"],
        "cost_category": cost,
        "prep_time_min": 10,
        "cook_time_min": 20,
        "servings": 4,
        "tags": tags or [],
        "ingredients": ingredients or [
            {"name": "Nudeln", "amount": 400, "unit": "g"},
        ],
    }


@pytest.fixture
def recipe_a():
    return make_recipe("recipe_a", cuisine="Italienisch",
                       tags=["Pasta"],
                       ingredients=[
                           {"name": "Karotte", "amount": 300, "unit": "g"},
                           {"name": "Zwiebel", "amount": 100, "unit": "g"},
                       ])


@pytest.fixture
def recipe_b():
    return make_recipe("recipe_b", cuisine="Indisch",
                       tags=["Hülsenfrüchte", "gesund"],
                       cost="medium",
                       ingredients=[
                           {"name": "Karotte", "amount": 200, "unit": "g"},
                           {"name": "Tomate", "amount": 400, "unit": "g"},
                       ])


@pytest.fixture
def recipe_c():
    return make_recipe("recipe_c", cuisine="Mexikanisch",
                       tags=["leicht", "frisch"],
                       ingredients=[
                           {"name": "Tomate", "amount": 300, "unit": "g"},
                           {"name": "Paprika", "amount": 200, "unit": "g"},
                       ])


@pytest.fixture
def meal_set(recipe_a, recipe_b, recipe_c):
    return [recipe_a, recipe_b, recipe_c]


@pytest.fixture
def empty_leftovers():
    return {}


@pytest.fixture
def empty_history():
    return []


@pytest.fixture
def empty_state():
    return {"week": 21, "leftovers": {}, "history": [], "ratings": {}}


@pytest.fixture
def packages():
    return {
        "Karotte": {"name": "Karotte", "package_size": 1000, "unit": "g",
                    "category": "Gemüse", "store_days": 14},
        "Zwiebel": {"name": "Zwiebel", "package_size": 500, "unit": "g",
                    "category": "Gemüse", "store_days": 21},
        "Tomate": {"name": "Tomate", "package_size": 500, "unit": "g",
                   "category": "Gemüse", "store_days": 7},
        "Paprika": {"name": "Paprika", "package_size": 3, "unit": "Stk",
                    "category": "Gemüse", "store_days": 7},
    }


@pytest.fixture
def flat_weights():
    """All weights equal to 1.0 for predictable scoring."""
    return {
        "reuse": 1.0, "repeat": 1.0, "season": 1.0,
        "variety": 1.0, "health": 1.0, "cost": 1.0, "recency": 1.0, "rating": 1.0,
    }


@pytest.fixture
def zero_weights():
    return {
        "reuse": 0.0, "repeat": 0.0, "season": 0.0,
        "variety": 0.0, "health": 0.0, "cost": 0.0, "recency": 0.0, "rating": 0.0,
    }


@pytest.fixture
def recency_cfg():
    return {"window_weeks": 6, "decay": "linear"}
