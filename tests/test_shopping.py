"""Unit tests for generate_shopping_list."""
import pytest
from planner import generate_shopping_list


class TestAggregation:
    def test_single_recipe_single_item(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert len(result) == 1
        assert result[0]["name"] == "Karotte"
        assert result[0]["needed_total"] == 300

    def test_pantry_item_excluded(self, packages):
        # "Salz" has no entry in packages → pantry item
        recipes = [{"ingredients": [
            {"name": "Karotte", "amount": 300, "unit": "g"},
            {"name": "Salz", "amount": 5, "unit": "g"},
        ]}]
        result = generate_shopping_list(recipes, {}, packages)
        names = [r["name"] for r in result]
        assert "Salz" not in names
        assert "Karotte" in names

    def test_amounts_aggregated_across_recipes(self, packages):
        recipes = [
            {"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]},
            {"ingredients": [{"name": "Karotte", "amount": 200, "unit": "g"}]},
        ]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["needed_total"] == 500

    def test_multiple_ingredients(self, packages):
        recipes = [{"ingredients": [
            {"name": "Karotte", "amount": 300, "unit": "g"},
            {"name": "Zwiebel", "amount": 100, "unit": "g"},
        ]}]
        result = generate_shopping_list(recipes, {}, packages)
        names = [r["name"] for r in result]
        assert "Karotte" in names
        assert "Zwiebel" in names


class TestLeftoverSubtraction:
    def test_leftover_reduces_needed_buy(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        leftovers = {"Karotte": {"amount": 100, "unit": "g"}}
        result = generate_shopping_list(recipes, leftovers, packages)
        assert result[0]["needed_buy"] == 200

    def test_leftover_fully_covers_need(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        leftovers = {"Karotte": {"amount": 400, "unit": "g"}}
        result = generate_shopping_list(recipes, leftovers, packages)
        # Fully covered → item removed from shopping list
        names = [r["name"] for r in result]
        assert "Karotte" not in names

    def test_leftover_unit_mismatch_ignored(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        leftovers = {"Karotte": {"amount": 1, "unit": "kg"}}
        result = generate_shopping_list(recipes, leftovers, packages)
        assert result[0]["needed_buy"] == 300

    def test_no_leftover_for_ingredient(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        leftovers = {"Zwiebel": {"amount": 200, "unit": "g"}}
        result = generate_shopping_list(recipes, leftovers, packages)
        assert result[0]["needed_buy"] == 300


class TestPackageRounding:
    def test_exact_package_fit(self, packages):
        # 1000g needed, package is 1000g → 1 pack
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 1000, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["packages"] == 1

    def test_rounds_up_to_next_package(self, packages):
        # 300g needed, package is 1000g → 1 pack (ceil(300/1000)=1)
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["packages"] == 1

    def test_two_packages_needed(self, packages):
        # 1100g needed, package 1000g → 2 packs
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 1100, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["packages"] == 2

    def test_package_size_and_unit_in_result(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["package_size"] == 1000
        assert result[0]["unit"] == "g"


class TestSorting:
    def test_sorted_by_category_then_name(self, packages):
        recipes = [{"ingredients": [
            {"name": "Zwiebel", "amount": 100, "unit": "g"},
            {"name": "Karotte", "amount": 300, "unit": "g"},
        ]}]
        result = generate_shopping_list(recipes, {}, packages)
        names = [r["name"] for r in result]
        # Both are "Gemüse", sorted alphabetically within category
        assert names == sorted(names)

    def test_category_in_result(self, packages):
        recipes = [{"ingredients": [{"name": "Karotte", "amount": 300, "unit": "g"}]}]
        result = generate_shopping_list(recipes, {}, packages)
        assert result[0]["category"] == "Gemüse"
