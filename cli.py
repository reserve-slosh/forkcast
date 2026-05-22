import argparse

import planner


def main():
    parser = argparse.ArgumentParser(description="ForkCast – weekly vegetarian meal planner")
    parser.add_argument("--profile", metavar="NAME",
                        help="Preference profile (default: auto-detect from weekday)")
    parser.add_argument("--blacklist", nargs="*", metavar="ID", default=[],
                        help="Recipe IDs to exclude this week")
    parser.add_argument("--fixture", metavar="ID",
                        help="Fix this recipe; draw 2 others")
    parser.add_argument("--commit", action="store_true",
                        help="Save plan and recompute leftovers in state.json")
    parser.add_argument("--candidates", type=int, default=500, metavar="N",
                        help="Candidate sets to sample (default: 500)")
    args = parser.parse_args()

    recipes = planner.load_recipes()
    packages = planner.load_packages()
    state = planner.load_state()
    preferences = planner.load_preferences()

    planner.expire_leftovers(state)

    season = planner.current_season()
    weights = planner.active_profile(preferences, args.profile)
    recency_cfg = preferences.get("recency", {})

    best = planner.sample_best(
        recipes, state, weights, recency_cfg, season,
        n_candidates=args.candidates,
        blacklist=args.blacklist,
        fixture=args.fixture,
    )

    print("\n=== This Week's Meal Plan ===\n")
    for r in best:
        diet = "[V]" if r["diet"] == "vegan" else "[v]"
        cost = "$" if r["cost_category"] == "budget" else "$$"
        total_min = r["prep_time_min"] + r["cook_time_min"]
        print(f"  {diet} {cost}  {r['name']:<35} {r['cuisine']}  ({total_min} min)")

    shopping = planner.generate_shopping_list(best, state["leftovers"], packages)

    print("\n=== Shopping List ===")
    current_cat = None
    for item in shopping:
        if item["category"] != current_cat:
            print(f"\n  {item['category']}")
            current_cat = item["category"]
        print(f"    {item['name']:<30} {item['packages']}x {item['package_size']}{item['unit']}")

    if not shopping:
        print("\n  (all ingredients covered by leftovers)")

    if args.commit:
        planner.commit_plan(state, best, packages)
        planner.save_state(state)
        print("\n✓ Plan committed to state.json")
    else:
        print("\n(use --commit to save this plan and update leftovers)")


if __name__ == "__main__":
    main()
