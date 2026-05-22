"""Focused tests for recency penalty and the _weeks_since helper."""
import pytest
from datetime import date, timedelta
import planner
from planner import recency_penalty, _weeks_since
from conftest import freeze_date

TODAY = date(2026, 5, 22)


class TestWeeksSince:
    def test_today_returns_zero(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        assert _weeks_since(TODAY.isoformat()) == 0

    def test_seven_days_ago_is_one_week(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        one_week_ago = (TODAY - timedelta(days=7)).isoformat()
        assert _weeks_since(one_week_ago) == 1

    def test_year_boundary_safe(self, monkeypatch):
        today = date(2026, 1, 7)
        freeze_date(monkeypatch, today)
        last_year = date(2025, 12, 31).isoformat()
        assert _weeks_since(last_year) == 1

    def test_invalid_date_returns_99(self):
        assert _weeks_since("not-a-date") == 99

    def test_none_returns_99(self):
        assert _weeks_since(None) == 99


class TestRecencyPenalty:
    def _meal_set(self, *ids):
        return [{"id": id_} for id_ in ids]

    def _cfg(self, window=6):
        return {"window_weeks": window, "decay": "linear"}

    def test_no_history(self):
        assert recency_penalty(self._meal_set("a"), [], self._cfg()) == 0.0

    def test_age_zero_excluded(self, monkeypatch):
        # age == 0 → `0 < age < window` is False → no penalty
        freeze_date(monkeypatch, TODAY)
        history = [{"date": TODAY.isoformat(), "recipes": ["a"]}]
        assert recency_penalty(self._meal_set("a"), history, self._cfg()) == 0.0

    def test_age_at_window_excluded(self, monkeypatch):
        # age == window_weeks → not strictly less than window → no penalty
        freeze_date(monkeypatch, TODAY)
        six_weeks_ago = (TODAY - timedelta(weeks=6)).isoformat()
        history = [{"date": six_weeks_ago, "recipes": ["a"]}]
        assert recency_penalty(self._meal_set("a"), history, self._cfg(window=6)) == 0.0

    def test_one_week_penalty_formula(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        one_week_ago = (TODAY - timedelta(weeks=1)).isoformat()
        history = [{"date": one_week_ago, "recipes": ["a"]}]
        penalty = recency_penalty(self._meal_set("a"), history, self._cfg(window=6))
        expected = 1.0 - 1.0 / 6.0
        assert penalty == pytest.approx(expected, rel=1e-6)

    def test_three_week_penalty_formula(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        three_weeks_ago = (TODAY - timedelta(weeks=3)).isoformat()
        history = [{"date": three_weeks_ago, "recipes": ["a"]}]
        penalty = recency_penalty(self._meal_set("a"), history, self._cfg(window=6))
        expected = 1.0 - 3.0 / 6.0
        assert penalty == pytest.approx(expected, rel=1e-6)

    def test_multiple_history_entries_accumulate(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        w1 = (TODAY - timedelta(weeks=1)).isoformat()
        w2 = (TODAY - timedelta(weeks=2)).isoformat()
        history = [
            {"date": w1, "recipes": ["a"]},
            {"date": w2, "recipes": ["a"]},
        ]
        penalty = recency_penalty(self._meal_set("a"), history, self._cfg(window=6))
        expected = (1.0 - 1.0 / 6.0) + (1.0 - 2.0 / 6.0)
        assert penalty == pytest.approx(expected, rel=1e-6)

    def test_only_overlapping_recipes_penalised(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        one_week_ago = (TODAY - timedelta(weeks=1)).isoformat()
        history = [{"date": one_week_ago, "recipes": ["other"]}]
        assert recency_penalty(self._meal_set("a"), history, self._cfg()) == 0.0

    def test_wider_window_increases_penalty_reach(self, monkeypatch):
        freeze_date(monkeypatch, TODAY)
        five_weeks_ago = (TODAY - timedelta(weeks=5)).isoformat()
        history = [{"date": five_weeks_ago, "recipes": ["a"]}]
        meal = self._meal_set("a")
        assert recency_penalty(meal, history, self._cfg(window=4)) == 0.0
        assert recency_penalty(meal, history, self._cfg(window=8)) > 0.0
