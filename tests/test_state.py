"""Unit tests for state load/save and leftover expiry."""
import json
import pytest
from datetime import date, timedelta
from pathlib import Path

import planner
from planner import load_state, save_state, expire_leftovers


@pytest.fixture(autouse=True)
def isolate_state_file(tmp_path, monkeypatch):
    """Redirect STATE_FILE to a temp directory for every test."""
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(planner, "STATE_FILE", state_path)
    return state_path


class TestLoadState:
    def test_returns_default_when_no_file(self):
        state = load_state()
        assert state["leftovers"] == {}
        assert state["history"] == []
        assert state["ratings"] == {}
        assert "week" in state

    def test_loads_existing_file(self, isolate_state_file):
        data = {"week": 10, "leftovers": {}, "history": [], "ratings": {"r1": 4}}
        isolate_state_file.write_text(json.dumps(data))
        state = load_state()
        assert state["week"] == 10
        assert state["ratings"] == {"r1": 4}

    def test_missing_ratings_key_defaults_to_empty(self, isolate_state_file):
        data = {"week": 10, "leftovers": {}, "history": []}
        isolate_state_file.write_text(json.dumps(data))
        state = load_state()
        assert state["ratings"] == {}


class TestSaveState:
    def test_roundtrip(self, isolate_state_file):
        original = {"week": 21, "leftovers": {}, "history": [], "ratings": {"r1": 3}}
        save_state(original)
        loaded = json.loads(isolate_state_file.read_text())
        assert loaded == original

    def test_unicode_preserved(self, isolate_state_file):
        state = {"week": 1, "leftovers": {"Möhre": {"amount": 100, "unit": "g"}},
                 "history": [], "ratings": {}}
        save_state(state)
        loaded = json.loads(isolate_state_file.read_text())
        assert "Möhre" in loaded["leftovers"]


class TestExpireLeftovers:
    def test_removes_expired(self, monkeypatch):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        state = {
            "leftovers": {
                "Karotte": {"amount": 100, "unit": "g", "expires": yesterday},
            }
        }
        expire_leftovers(state)
        assert "Karotte" not in state["leftovers"]

    def test_keeps_unexpired(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        state = {
            "leftovers": {
                "Karotte": {"amount": 100, "unit": "g", "expires": tomorrow},
            }
        }
        expire_leftovers(state)
        assert "Karotte" in state["leftovers"]

    def test_keeps_expiring_today(self):
        today = date.today().isoformat()
        state = {
            "leftovers": {
                "Karotte": {"amount": 100, "unit": "g", "expires": today},
            }
        }
        expire_leftovers(state)
        assert "Karotte" in state["leftovers"]

    def test_mixed_expiry(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        state = {
            "leftovers": {
                "Karotte": {"amount": 100, "unit": "g", "expires": yesterday},
                "Zwiebel": {"amount": 200, "unit": "g", "expires": tomorrow},
            }
        }
        expire_leftovers(state)
        assert "Karotte" not in state["leftovers"]
        assert "Zwiebel" in state["leftovers"]

    def test_empty_leftovers_unchanged(self):
        state = {"leftovers": {}}
        expire_leftovers(state)
        assert state["leftovers"] == {}
