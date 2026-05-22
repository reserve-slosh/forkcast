import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

RECIPES_FILE = Path("recipes.json")
PACKAGES_FILE = Path("ingredient_packages.json")
STATE_FILE = Path("state.json")
PREFERENCES_FILE = Path("preferences.json")

HEALTH_TAGS = {"gesund", "leicht", "frisch"}

DEFAULT_PREFERENCES = {
    "recency": {"window_weeks": 6, "decay": "linear"},
    "profiles": {
        "weekday": {
            "reuse": 1.0, "repeat": 1.0, "season": 0.5,
            "variety": 0.5, "health": 2.0, "cost": 1.0, "recency": 1.5, "rating": 1.5,
        },
        "weekend": {
            "reuse": 1.0, "repeat": 1.0, "season": 1.0,
            "variety": 2.0, "health": 0.5, "cost": 0.25, "recency": 1.0, "rating": 1.5,
        },
    },
}


def current_season():
    m = date.today().month
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    if m in (9, 10, 11):
        return "autumn"
    return "winter"


def load_recipes():
    return json.loads(RECIPES_FILE.read_text())["recipes"]


def load_packages():
    pkgs = json.loads(PACKAGES_FILE.read_text())["packages"]
    return {p["name"]: p for p in pkgs}


def load_state():
    if not STATE_FILE.exists():
        return {"week": date.today().isocalendar()[1], "leftovers": {}, "history": [], "ratings": {}}
    state = json.loads(STATE_FILE.read_text())
    state.setdefault("ratings", {})
    return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def load_preferences():
    if not PREFERENCES_FILE.exists():
        return DEFAULT_PREFERENCES
    prefs = json.loads(PREFERENCES_FILE.read_text())
    merged = {**DEFAULT_PREFERENCES, **prefs}
    merged["profiles"] = {**DEFAULT_PREFERENCES["profiles"], **prefs.get("profiles", {})}
    return merged


def expire_leftovers(state):
    today = date.today().isoformat()
    state["leftovers"] = {k: v for k, v in state["leftovers"].items() if v["expires"] >= today}


def active_profile(preferences, profile_name=None):
    profiles = preferences.get("profiles", {})
    if profile_name and profile_name in profiles:
        return profiles[profile_name]
    key = "weekday" if date.today().weekday() < 5 else "weekend"
    return profiles.get(key, {})


def _w(profile, key):
    return float(profile.get(key, 1.0))


def _weeks_since(date_str):
    try:
        return (date.today() - date.fromisoformat(date_str)).days // 7
    except (ValueError, TypeError):
        return 99


# --- Scoring components ---

def reuse_bonus(meal_set, leftovers):
    bonus = 0.0
    for recipe in meal_set:
        for ing in recipe["ingredients"]:
            lo = leftovers.get(ing["name"])
            if lo and lo["unit"] == ing["unit"] and ing["amount"] > 0:
                bonus += min(lo["amount"], ing["amount"]) / ing["amount"]
    return bonus


def same_ingredient_penalty(meal_set):
    counts = Counter(ing["name"] for r in meal_set for ing in r["ingredients"])
    return sum(1 for c in counts.values() if c >= 3)


def season_bonus(meal_set, season):
    return sum(1 for r in meal_set if season in r.get("season", []))


def variety_bonus(meal_set):
    cuisine_score = len({r["cuisine"] for r in meal_set}) - 1
    tag_sets = [set(r.get("tags", [])) for r in meal_set]
    overlap = sum(
        len(tag_sets[i] & tag_sets[j])
        for i in range(len(tag_sets))
        for j in range(i + 1, len(tag_sets))
    )
    return cuisine_score + max(0.0, 3.0 - overlap / 3.0)


def health_bonus(meal_set):
    return sum(1 for r in meal_set if HEALTH_TAGS & set(r.get("tags", [])))


def cost_penalty(meal_set):
    return sum(1 for r in meal_set if r.get("cost_category") == "medium")


def rating_bonus(meal_set, ratings):
    return sum(ratings.get(r["id"], 0) / 5.0 for r in meal_set)


def recency_penalty(meal_set, history, cfg):
    window = cfg.get("window_weeks", 6)
    ids = {r["id"] for r in meal_set}
    total = 0.0
    for entry in history:
        age = _weeks_since(entry.get("date", "2000-01-01"))
        if 0 < age < window:
            overlap = ids & set(entry.get("recipes", []))
            total += len(overlap) * max(0.0, 1.0 - age / window)
    return total


def score(meal_set, leftovers, history, weights, recency_cfg, season, ratings=None):
    s = 0.0
    s += _w(weights, "reuse")   * reuse_bonus(meal_set, leftovers)
    s -= _w(weights, "repeat")  * same_ingredient_penalty(meal_set)
    s += _w(weights, "season")  * season_bonus(meal_set, season)
    s += _w(weights, "variety") * variety_bonus(meal_set)
    s += _w(weights, "health")  * health_bonus(meal_set)
    s -= _w(weights, "cost")    * cost_penalty(meal_set)
    s -= _w(weights, "recency") * recency_penalty(meal_set, history, recency_cfg)
    if ratings:
        s += _w(weights, "rating") * rating_bonus(meal_set, ratings)
    return s


def sample_best(recipes, state, weights, recency_cfg, season,
                n_candidates=500, blacklist=None, fixture=None):
    pool = [r for r in recipes if not blacklist or r["id"] not in blacklist]
    fixture_recipe = next((r for r in recipes if r["id"] == fixture), None) if fixture else None

    if fixture_recipe:
        rest = [r for r in pool if r["id"] != fixture]
        if len(rest) < 2:
            raise ValueError("Not enough recipes after blacklist/fixture constraints")
        candidates = [[fixture_recipe] + random.sample(rest, 2) for _ in range(n_candidates)]
    else:
        if len(pool) < 3:
            raise ValueError("Not enough recipes after blacklist constraints")
        candidates = [random.sample(pool, 3) for _ in range(n_candidates)]

    leftovers = state["leftovers"]
    history = state["history"]
    ratings = state.get("ratings", {})
    return max(candidates, key=lambda ms: score(ms, leftovers, history, weights, recency_cfg, season, ratings))


def recipe_history(recipe_id, history):
    return [entry["date"] for entry in history if recipe_id in entry.get("recipes", [])]


def generate_shopping_list(meal_set, leftovers, packages):
    totals = defaultdict(lambda: {"amount": 0.0, "unit": None})
    for recipe in meal_set:
        for ing in recipe["ingredients"]:
            totals[ing["name"]]["amount"] += ing["amount"]
            totals[ing["name"]]["unit"] = ing["unit"]

    shopping = []
    for name, info in sorted(totals.items()):
        pkg = packages.get(name)
        if not pkg:
            continue  # pantry item — no package entry

        needed = info["amount"]
        lo = leftovers.get(name)
        if lo and lo["unit"] == info["unit"]:
            needed = max(0.0, needed - lo["amount"])

        if needed <= 0:
            continue

        n_packs = math.ceil(needed / pkg["package_size"])
        shopping.append({
            "name": name,
            "needed_total": info["amount"],
            "needed_buy": needed,
            "packages": n_packs,
            "package_size": pkg["package_size"],
            "unit": pkg["unit"],
            "category": pkg["category"],
        })

    shopping.sort(key=lambda x: (x["category"], x["name"]))
    return shopping


def commit_plan(state, recipes_chosen, packages):
    week = date.today().isocalendar()[1]
    today = date.today().isoformat()

    state["history"].append({
        "date": today,
        "week": week,
        "recipes": [r["id"] for r in recipes_chosen],
    })
    state["history"] = [e for e in state["history"] if _weeks_since(e.get("date", "2000-01-01")) <= 8]

    totals = defaultdict(lambda: {"amount": 0.0, "unit": None})
    for recipe in recipes_chosen:
        for ing in recipe["ingredients"]:
            totals[ing["name"]]["amount"] += ing["amount"]
            totals[ing["name"]]["unit"] = ing["unit"]

    for name, info in totals.items():
        pkg = packages.get(name)
        if not pkg:
            continue

        used = info["amount"]
        lo = state["leftovers"].get(name, {})
        existing = lo.get("amount", 0.0) if lo.get("unit") == info["unit"] else 0.0

        used_from_leftover = min(existing, used)
        still_needed = used - used_from_leftover
        remaining_from_old = existing - used_from_leftover

        n_packs = math.ceil(still_needed / pkg["package_size"]) if still_needed > 0 else 0
        leftover_amount = n_packs * pkg["package_size"] - still_needed + remaining_from_old

        expires = (date.today() + timedelta(days=pkg["store_days"])).isoformat()
        if leftover_amount > 0:
            state["leftovers"][name] = {"amount": leftover_amount, "unit": pkg["unit"], "expires": expires}
        else:
            state["leftovers"].pop(name, None)

    state["week"] = week
