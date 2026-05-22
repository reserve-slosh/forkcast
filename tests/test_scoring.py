"""Unit tests for planner.py scoring components."""
import pytest
from datetime import date, timedelta
import planner
from conftest import freeze_date
from planner import (
    reuse_bonus,
    same_ingredient_penalty,
    season_bonus,
    variety_bonus,
    health_bonus,
    cost_penalty,
    rating_bonus,
    recency_penalty,
    score,
)


# --- reuse_bonus ---

class TestReuseBonus:
    def test_no_leftovers(self, meal_set):
        assert reuse_bonus(meal_set, {}) == 0.0

    def test_full_coverage(self, recipe_a):
        # 300g of Karotte needed, 300g in leftovers → ratio 1.0
        leftovers = {"Karotte": {"amount": 300, "unit": "g"}}
        bonus = reuse_bonus([recipe_a], leftovers)
        assert bonus == pytest.approx(1.0)

    def test_partial_coverage(self, recipe_a):
        # 300g needed, 150g leftover → ratio 0.5
        leftovers = {"Karotte": {"amount": 150, "unit": "g"}}
        bonus = reuse_bonus([recipe_a], leftovers)
        assert bonus == pytest.approx(0.5)

    def test_excess_leftover_capped_at_one(self, recipe_a):
        # 300g needed, 1000g leftover → ratio capped at 1.0
        leftovers = {"Karotte": {"amount": 1000, "unit": "g"}}
        bonus = reuse_bonus([recipe_a], leftovers)
        assert bonus == pytest.approx(1.0)

    def test_unit_mismatch_ignored(self, recipe_a):
        # Leftover in kg but recipe uses g → no bonus
        leftovers = {"Karotte": {"amount": 1, "unit": "kg"}}
        assert reuse_bonus([recipe_a], leftovers) == 0.0

    def test_multiple_recipes_accumulate(self, recipe_a, recipe_b):
        # Both recipes have Karotte; leftovers cover a portion of each
        leftovers = {"Karotte": {"amount": 500, "unit": "g"}}
        bonus = reuse_bonus([recipe_a, recipe_b], leftovers)
        # recipe_a: min(500,300)/300=1.0, recipe_b: min(500,200)/200=1.0
        assert bonus == pytest.approx(2.0)


# --- same_ingredient_penalty ---

class TestSameIngredientPenalty:
    def test_no_shared_ingredients(self):
        recipes = [
            {"ingredients": [{"name": "A"}]},
            {"ingredients": [{"name": "B"}]},
            {"ingredients": [{"name": "C"}]},
        ]
        assert same_ingredient_penalty(recipes) == 0

    def test_two_recipes_share_ingredient_no_penalty(self, recipe_a, recipe_b):
        # Karotte in recipe_a and recipe_b — count=2, threshold is >=3
        assert same_ingredient_penalty([recipe_a, recipe_b]) == 0

    def test_three_way_shared_triggers_penalty(self):
        recipes = [
            {"ingredients": [{"name": "Karotte"}]},
            {"ingredients": [{"name": "Karotte"}]},
            {"ingredients": [{"name": "Karotte"}]},
        ]
        assert same_ingredient_penalty(recipes) == 1

    def test_multiple_shared_accumulate(self):
        recipes = [
            {"ingredients": [{"name": "X"}, {"name": "Y"}]},
            {"ingredients": [{"name": "X"}, {"name": "Y"}]},
            {"ingredients": [{"name": "X"}, {"name": "Y"}]},
        ]
        assert same_ingredient_penalty(recipes) == 2


# --- season_bonus ---

class TestSeasonBonus:
    def test_all_in_season(self, meal_set):
        # All test recipes include "spring"
        bonus = season_bonus(meal_set, "spring")
        assert bonus == 3

    def test_none_in_season(self):
        recipes = [
            {"season": ["winter"]},
            {"season": ["winter"]},
            {"season": ["winter"]},
        ]
        assert season_bonus(recipes, "summer") == 0

    def test_partial(self):
        recipes = [
            {"season": ["summer"]},
            {"season": ["winter"]},
            {"season": ["summer"]},
        ]
        assert season_bonus(recipes, "summer") == 2

    def test_no_season_field(self):
        recipes = [{"id": "x"}, {"id": "y"}]
        assert season_bonus(recipes, "spring") == 0


# --- variety_bonus ---

class TestVarietyBonus:
    def test_all_same_cuisine(self):
        recipes = [
            {"cuisine": "Italienisch", "tags": ["A"]},
            {"cuisine": "Italienisch", "tags": ["B"]},
            {"cuisine": "Italienisch", "tags": ["C"]},
        ]
        # cuisine_score = 1-1 = 0; no tag overlap
        bonus = variety_bonus(recipes)
        assert bonus == pytest.approx(0 + 3.0)  # max overlap benefit

    def test_three_different_cuisines(self):
        recipes = [
            {"cuisine": "A", "tags": []},
            {"cuisine": "B", "tags": []},
            {"cuisine": "C", "tags": []},
        ]
        # cuisine_score = 2; no tag overlap → overlap=0, tag term = 3.0
        bonus = variety_bonus(recipes)
        assert bonus == pytest.approx(2 + 3.0)

    def test_high_tag_overlap_reduces_bonus(self):
        tags = ["X", "Y", "Z"]
        recipes = [
            {"cuisine": "A", "tags": tags},
            {"cuisine": "B", "tags": tags},
            {"cuisine": "C", "tags": tags},
        ]
        # Overlap per pair = 3, three pairs → total overlap = 9
        # tag term = max(0, 3 - 9/3) = max(0, 0) = 0
        bonus = variety_bonus(recipes)
        assert bonus == pytest.approx(2 + 0.0)


# --- health_bonus ---

class TestHealthBonus:
    def test_no_health_tags(self, recipe_a):
        # recipe_a has tags=["Pasta"]
        assert health_bonus([recipe_a]) == 0

    def test_gesund_tag(self, recipe_b):
        # recipe_b has tags=["Hülsenfrüchte", "gesund"]
        assert health_bonus([recipe_b]) == 1

    def test_leicht_and_frisch(self, recipe_c):
        # recipe_c has tags=["leicht", "frisch"]
        assert health_bonus([recipe_c]) == 1

    def test_multiple_health_recipes(self, recipe_b, recipe_c):
        assert health_bonus([recipe_b, recipe_c]) == 2


# --- cost_penalty ---

class TestCostPenalty:
    def test_all_budget(self, recipe_a, recipe_c):
        assert cost_penalty([recipe_a, recipe_c]) == 0

    def test_one_medium(self, recipe_b):
        # recipe_b has cost_category="medium"
        assert cost_penalty([recipe_b]) == 1

    def test_mixed(self, recipe_a, recipe_b, recipe_c):
        # only recipe_b is medium
        assert cost_penalty([recipe_a, recipe_b, recipe_c]) == 1


# --- rating_bonus ---

class TestRatingBonus:
    def test_no_ratings(self, meal_set):
        assert rating_bonus(meal_set, {}) == 0.0

    def test_one_max_rating(self, recipe_a):
        ratings = {"recipe_a": 5}
        assert rating_bonus([recipe_a], ratings) == pytest.approx(1.0)

    def test_partial_rating(self, recipe_a):
        ratings = {"recipe_a": 3}
        assert rating_bonus([recipe_a], ratings) == pytest.approx(0.6)

    def test_multiple_recipes(self, recipe_a, recipe_b):
        ratings = {"recipe_a": 5, "recipe_b": 5}
        assert rating_bonus([recipe_a, recipe_b], ratings) == pytest.approx(2.0)

    def test_unrated_recipe_contributes_zero(self, recipe_a, recipe_b):
        ratings = {"recipe_a": 5}
        # recipe_b is unrated → 0
        assert rating_bonus([recipe_a, recipe_b], ratings) == pytest.approx(1.0)


# --- recency_penalty ---

class TestRecencyPenalty:
    def test_empty_history(self, meal_set, recency_cfg):
        assert recency_penalty(meal_set, [], recency_cfg) == 0.0

    def test_very_old_entry_ignored(self, meal_set, recency_cfg):
        # age >= window_weeks (6) means no penalty
        history = [{"date": "2020-01-01", "recipes": ["recipe_a"]}]
        assert recency_penalty(meal_set, history, recency_cfg) == 0.0

    def test_recent_entry_penalised(self, meal_set, recency_cfg, monkeypatch):
        today = date(2026, 5, 22)
        freeze_date(monkeypatch, today)
        one_week_ago = (today - timedelta(weeks=1)).isoformat()

        history = [{"date": one_week_ago, "recipes": ["recipe_a"]}]
        penalty = recency_penalty(meal_set, history, recency_cfg)
        assert penalty == pytest.approx(1.0 - 1.0 / 6.0, rel=1e-3)

    def test_penalty_decays_with_age(self, meal_set, recency_cfg, monkeypatch):
        today = date(2026, 5, 22)
        freeze_date(monkeypatch, today)

        one_week = (today - timedelta(weeks=1)).isoformat()
        three_weeks = (today - timedelta(weeks=3)).isoformat()

        h1 = [{"date": one_week, "recipes": ["recipe_a"]}]
        h3 = [{"date": three_weeks, "recipes": ["recipe_a"]}]
        p1 = recency_penalty(meal_set, h1, recency_cfg)
        p3 = recency_penalty(meal_set, h3, recency_cfg)
        assert p1 > p3

    def test_no_overlap_means_no_penalty(self, meal_set, recency_cfg, monkeypatch):
        today = date(2026, 5, 22)
        freeze_date(monkeypatch, today)
        one_week_ago = (today - timedelta(weeks=1)).isoformat()

        history = [{"date": one_week_ago, "recipes": ["other_recipe"]}]
        assert recency_penalty(meal_set, history, recency_cfg) == 0.0


# --- score (integration of components) ---

class TestScore:
    def test_zero_weights_gives_zero(self, meal_set, empty_leftovers, empty_history,
                                     zero_weights, recency_cfg):
        s = score(meal_set, empty_leftovers, empty_history, zero_weights, recency_cfg, "spring")
        assert s == 0.0

    def test_reuse_weight_increases_score(self, recipe_a, recipe_b, recipe_c,
                                          empty_history, recency_cfg):
        meal = [recipe_a, recipe_b, recipe_c]
        leftovers = {"Karotte": {"amount": 300, "unit": "g"}}

        low_w = {"reuse": 0.0, "repeat": 0.0, "season": 0.0, "variety": 0.0,
                 "health": 0.0, "cost": 0.0, "recency": 0.0, "rating": 0.0}
        high_w = {**low_w, "reuse": 2.0}

        s_low = score(meal, leftovers, empty_history, low_w, recency_cfg, "spring")
        s_high = score(meal, leftovers, empty_history, high_w, recency_cfg, "spring")
        assert s_high > s_low

    def test_cost_weight_penalises_medium_recipes(self, recipe_a, recipe_b, recipe_c,
                                                   empty_leftovers, empty_history, recency_cfg):
        meal = [recipe_a, recipe_b, recipe_c]
        no_cost_w = {"reuse": 0.0, "repeat": 0.0, "season": 0.0, "variety": 0.0,
                     "health": 0.0, "cost": 0.0, "recency": 0.0, "rating": 0.0}
        with_cost_w = {**no_cost_w, "cost": 1.0}

        s_no = score(meal, empty_leftovers, empty_history, no_cost_w, recency_cfg, "spring")
        s_with = score(meal, empty_leftovers, empty_history, with_cost_w, recency_cfg, "spring")
        # recipe_b is medium → score should be lower with cost weight
        assert s_with < s_no

    def test_ratings_absent_when_none_passed(self, meal_set, empty_leftovers,
                                              empty_history, flat_weights, recency_cfg):
        s_no_ratings = score(meal_set, empty_leftovers, empty_history,
                              flat_weights, recency_cfg, "spring", ratings=None)
        s_zero_ratings = score(meal_set, empty_leftovers, empty_history,
                               flat_weights, recency_cfg, "spring", ratings={})
        # ratings=None skips the block; ratings={} contributes 0
        assert s_no_ratings == pytest.approx(s_zero_ratings)
