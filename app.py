from datetime import date

from flask import Flask, render_template, request

import planner

app = Flask(__name__)

_recipes = None
_packages = None


def _human_date(date_str):
    try:
        d = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date_str
    delta = (date.today() - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 14:
        return f"{delta} days ago"
    weeks = delta // 7
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


app.jinja_env.globals["human_date"] = _human_date


def _load():
    global _recipes, _packages
    if _recipes is None:
        _recipes = planner.load_recipes()
        _packages = planner.load_packages()


def _run_planner(profile=None, blacklist=None, fixture=None):
    _load()
    state = planner.load_state()
    prefs = planner.load_preferences()
    planner.expire_leftovers(state)
    season = planner.current_season()
    weights = planner.active_profile(prefs, profile)
    recency_cfg = prefs.get("recency", {})
    meal_set = planner.sample_best(
        _recipes, state, weights, recency_cfg, season,
        blacklist=blacklist or [],
        fixture=fixture or None,
    )
    shopping = planner.generate_shopping_list(meal_set, state["leftovers"], _packages)
    recipe_map = {r["id"]: r for r in _recipes}
    ratings = state.get("ratings", {})
    return meal_set, shopping, state, recipe_map, ratings


@app.route("/")
def index():
    meal_set, shopping, state, recipe_map, ratings = _run_planner()
    return render_template(
        "index.html",
        meal_set=meal_set,
        shopping=shopping,
        state=state,
        recipe_map=recipe_map,
        ratings=ratings,
    )


@app.route("/plan", methods=["POST"])
def plan():
    profile = request.form.get("profile") or None
    blacklist_raw = request.form.get("blacklist", "")
    blacklist = [x.strip() for x in blacklist_raw.split(",") if x.strip()]
    fixture = request.form.get("fixture") or None
    meal_set, shopping, state, recipe_map, ratings = _run_planner(
        profile=profile, blacklist=blacklist, fixture=fixture
    )
    return render_template(
        "_results.html",
        meal_set=meal_set,
        shopping=shopping,
        state=state,
        recipe_map=recipe_map,
        ratings=ratings,
    )


@app.route("/commit", methods=["POST"])
def commit():
    _load()
    recipe_ids = request.form.get("recipe_ids", "").split(",")
    recipe_map = {r["id"]: r for r in _recipes}
    chosen = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]
    if not chosen:
        return "<p class='text-red-600 p-4'>No valid recipes to commit.</p>", 400
    state = planner.load_state()
    planner.expire_leftovers(state)
    planner.commit_plan(state, chosen, _packages)
    planner.save_state(state)
    return render_template("_committed.html", meal_set=chosen)


@app.route("/recipe/<recipe_id>")
def recipe_detail(recipe_id):
    _load()
    state = planner.load_state()
    recipe_map = {r["id"]: r for r in _recipes}
    recipe = recipe_map.get(recipe_id)
    if not recipe:
        return "<p class='text-red-600 p-4'>Recipe not found.</p>", 404
    cooked_on = planner.recipe_history(recipe_id, state["history"])
    rating = state.get("ratings", {}).get(recipe_id, 0)
    return render_template(
        "_recipe_detail.html", recipe=recipe, cooked_on=cooked_on, rating=rating
    )


@app.route("/rate", methods=["POST"])
def rate():
    recipe_id = request.form.get("recipe_id", "").strip()
    try:
        stars = int(request.form.get("stars", 0))
    except ValueError:
        stars = 0
    stars = max(0, min(5, stars))
    if recipe_id:
        state = planner.load_state()
        existing = state["ratings"].get(recipe_id, 0)
        stars = 0 if stars == existing else stars  # toggle off if same star clicked
        if stars:
            state["ratings"][recipe_id] = stars
        else:
            state["ratings"].pop(recipe_id, None)
        planner.save_state(state)
    return render_template("_stars.html", recipe_id=recipe_id, rating=stars)


if __name__ == "__main__":
    app.run(debug=True)
