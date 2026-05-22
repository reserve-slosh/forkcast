# ForkCast – Project Context

## Goal
Weekly meal planner: randomly select 3 vegetarian/vegan recipes per week, generate a shopping list,
and optimize ingredient reuse across weeks (e.g. carry-over carrots from last week reduce this week's shopping).

## Stack
- Python-first, PEP 8, no unnecessary abstractions
- Files are flat in repo root (no src/ layout)
- Docker available, Linux/Ubuntu
- Web UI: Flask + HTMX (no JS build step)

## File Overview

### `recipes.json`
70 vegetarian/vegan recipes. Current schema per recipe:
```json
{
  "id": "dal_tadka",
  "name": "Dal Tadka",
  "cuisine": "Indisch",
  "diet": "vegan | vegetarisch",
  "season": ["spring", "summer", "autumn", "winter"],
  "cost_category": "budget | medium",
  "prep_time_min": 10,
  "cook_time_min": 30,
  "servings": 4,
  "tags": ["Indisch", "Hülsenfrüchte"],
  "ingredients": [
    {"name": "Rote Linsen", "amount": 300, "unit": "g"}
  ]
}
```

**Planned LLM enrichment fields** (optional, rendered in UI when present):
```json
{
  "description": "Short 1–2 sentence description of the dish.",
  "instructions": ["Step 1", "Step 2"],
  "image_url": "https://..."
}
```
These will be generated via LLM + free/generated images in a future pass. All three fields are
optional — templates silently skip them when absent. `image_url` may be a freely-licensed URL
or a generated image.

### `ingredient_packages.json`
105 entries with typical German supermarket package sizes. Schema:
```json
{
  "name": "Karotte",
  "package_size": 1000,
  "unit": "g",
  "category": "Gemüse",
  "store_days": 14
}
```

### `state.json` (generated at runtime, not in repo)
Persistent weekly state. Schema:
```json
{
  "week": 21,
  "leftovers": {
    "Karotte": {"amount": 600, "unit": "g", "expires": "2026-05-28"}
  },
  "history": [
    {"date": "2026-05-20", "week": 21, "recipes": ["dal_tadka", "pasta_tomatensosse"]}
  ],
  "ratings": {
    "dal_tadka": 4,
    "spaghetti_aglio_olio": 5
  }
}
```

- `history` entries use `"date"` (ISO string) for recency calculation — year-boundary safe
- `ratings` maps recipe ID → star count (1–5); absent key = unrated; persisted across sessions
- History is trimmed to the last 8 weeks automatically on commit
- Missing `ratings` key in existing files is defaulted to `{}` on load (no migration needed)

### `planner.py`
Core logic (built):
- `load_state` / `save_state` / `expire_leftovers` — state I/O and leftover expiry
- `load_preferences` / `active_profile` — profile selection (auto-detect weekday/weekend)
- `current_season` — maps current month to spring/summer/autumn/winter
- Scoring components: `reuse_bonus`, `same_ingredient_penalty`, `season_bonus`, `variety_bonus`,
  `health_bonus`, `cost_penalty`, `recency_penalty`, `rating_bonus`
- `score(meal_set, leftovers, history, weights, recency_cfg, season, ratings=None)` — full weighted score
- `sample_best(recipes, state, weights, recency_cfg, season, n_candidates=500, blacklist=None, fixture=None)`
- `generate_shopping_list(meal_set, leftovers, packages)` — aggregates, subtracts leftovers, rounds up to package sizes, sorted by category; pantry detection is implicit (no package entry = pantry item)
- `commit_plan(state, recipes_chosen, packages)` — appends history, recomputes leftovers
- `recipe_history(recipe_id, history)` — returns list of dates when a recipe was committed

### `cli.py`
Thin CLI wrapper. Usage:
```
python3 cli.py [--profile weekday|weekend] [--blacklist ID ...] [--fixture ID] [--commit] [--candidates N]
```

### `app.py`
Flask web UI. Routes:
- `GET /` — renders full page with plan, shopping list, history panel
- `POST /plan` — HTMX: regenerates plan (accepts `profile`, `blacklist`, `fixture`); returns `_results.html` partial
- `POST /commit` — saves plan to state.json, returns `_committed.html` partial
- `GET /recipe/<recipe_id>` — HTMX: returns `_recipe_detail.html` partial for the modal
- `POST /rate` — HTMX: saves star rating (1–5) to state.json, returns `_stars.html` partial;
  clicking the same star again toggles it off

`_human_date(date_str)` is registered as a Jinja global (returns "Today", "Yesterday", "N days ago", "N weeks ago").

### `templates/`
- `index.html` — full page: planner form, `#results` div, history panel, native `<dialog>` modal
- `_results.html` — HTMX partial: clickable recipe cards (open modal), week cost estimate,
  commit button, shopping list with localStorage checkboxes
- `_stars.html` — reusable star widget; uses `hx-swap="outerHTML"` so the `id` persists across swaps.
  Expects `recipe_id` and `rating` (int 0–5) in template context.
- `_recipe_detail.html` — modal content: ingredients, cook history, stars, future-proof
  guards for `description`, `image_url`, `instructions`
- `_committed.html` — commit confirmation partial

## Constraints
- No meat, no fish (all recipes already vegetarian/vegan)
- No cinnamon, no vanilla
- Max 0.5 tsp chili flakes per recipe
- 4 servings default
- Pantry items (salt, spices) are excluded from shopping list and package tracking

## Scoring Logic

```python
def score(meal_set, leftovers, history, weights, recency_cfg, season, ratings=None):
    s += weights["reuse"]   * reuse_bonus(meal_set, leftovers)
    s -= weights["repeat"]  * same_ingredient_penalty(meal_set)
    s += weights["season"]  * season_bonus(meal_set, season)
    s += weights["variety"] * variety_bonus(meal_set)
    s += weights["health"]  * health_bonus(meal_set)   # tags: gesund, leicht, frisch
    s -= weights["cost"]    * cost_penalty(meal_set)   # penalise "medium" cost recipes
    s -= weights["recency"] * recency_penalty(meal_set, history, recency_cfg)
    if ratings:
        s += weights["rating"] * rating_bonus(meal_set, ratings)  # normalised 0–1 per recipe
```

`health_bonus` uses tags: `gesund`, `leicht`, `frisch`.
`rating_bonus` = sum of (stars / 5.0) for rated recipes in the set.
500 candidates sampled; best by score is returned.

## Recency Penalty
Linear decay: `penalty = 1 - weeks_ago / window`. Resets fully after `window_weeks` (default 6).
Age is computed from `entry["date"]` (ISO string) — year-boundary safe.

## Preference Profiles

Defined in `preferences.json` (user-created, not in repo). Selected via `--profile` CLI flag or
auto-detected (Mon–Fri → weekday, Sat–Sun → weekend). Missing weight keys default to `1.0`.

```json
{
  "recency": {"window_weeks": 6, "decay": "linear"},
  "profiles": {
    "weekday": {
      "reuse": 1.0, "repeat": 1.0, "season": 0.5, "variety": 0.5,
      "health": 2.0, "cost": 1.0, "recency": 1.5, "rating": 1.5
    },
    "weekend": {
      "reuse": 1.0, "repeat": 1.0, "season": 1.0, "variety": 2.0,
      "health": 0.5, "cost": 0.25, "recency": 1.0, "rating": 1.5
    }
  }
}
```

## Web UI Features
- **Recipe cards** — clickable; opens native `<dialog>` modal via HTMX + `htmx:afterSwap` listener
- **Recipe detail modal** — ingredients table, cook history ("2 weeks ago"), star rating, future-proof sections for description/image/instructions
- **Star ratings** — 5-star HTMX widget on cards and in modal; click same star to unrate; persisted to state.json; feeds back into scoring
- **History panel** — past meals grouped by week, reverse chronological; each recipe links to detail modal
- **"Cook again"** — button on each history recipe; POSTs to `/plan` with that recipe as fixture, includes current profile/blacklist via `hx-include`
- **Week cost estimate** — "X budget · Y medium" shown above the commit button
- **Shopping list checkboxes** — tick off items as you shop; checked state persisted in `localStorage`; resets naturally when a new plan is generated

## Planned Next Steps
- LLM enrichment pass: generate `description`, `instructions`, and source/generate `image_url` for all 70 recipes
- Image sourcing: freely-licensed photos (e.g. Wikimedia, Unsplash) or generated images
