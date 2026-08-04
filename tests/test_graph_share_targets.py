# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import pytest

from reed.graph import GraphService


@pytest.fixture
def graph(tmp_path):
    g = GraphService(str(tmp_path / "test.kuzu"))
    yield g
    g.close()


class TestFreshInstallSeeding:
    def test_seeds_exactly_two_copy_targets(self, graph):
        targets = graph.list_share_targets()
        types = sorted(t["type"] for t in targets)
        assert types == ["copy_link", "copy_markdown"]

    def test_seeded_targets_are_enabled(self, graph):
        targets = graph.list_share_targets()
        assert all(t["enabled"] for t in targets)

    def test_seeded_targets_have_empty_config(self, graph):
        targets = graph.list_share_targets()
        assert all(t["config"] == {} for t in targets)


class TestCreateShareTarget:
    def test_creates_and_returns_target(self, graph):
        target = graph.create_share_target(
            "webhook", "My webhook", {"url": "https://example.com/hook"}
        )
        assert target["type"] == "webhook"
        assert target["name"] == "My webhook"
        assert target["config"] == {"url": "https://example.com/hook"}
        assert target["enabled"] is True

    def test_config_round_trips_through_json(self, graph):
        target = graph.create_share_target(
            "raindrop", "Raindrop", {"token": "secret-token", "collection_id": "123"}
        )
        fetched = graph.get_share_target(target["id"])
        assert fetched["config"] == {"token": "secret-token", "collection_id": "123"}

    def test_id_is_uuid(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        assert len(target["id"]) == 36


class TestGetShareTarget:
    def test_returns_none_for_unknown_id(self, graph):
        assert graph.get_share_target("00000000-0000-0000-0000-000000000000") is None


class TestUpdateShareTarget:
    def test_updates_name(self, graph):
        target = graph.create_share_target("webhook", "Original", {"url": "https://x.com"})
        updated = graph.update_share_target(target["id"], name="Renamed")
        assert updated["name"] == "Renamed"

    def test_updates_enabled(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        updated = graph.update_share_target(target["id"], enabled=False)
        assert updated["enabled"] is False

    def test_updates_config(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        updated = graph.update_share_target(target["id"], config={"url": "https://y.com"})
        assert updated["config"] == {"url": "https://y.com"}

    def test_returns_none_for_unknown_id(self, graph):
        assert graph.update_share_target("00000000-0000-0000-0000-000000000000", name="X") is None

    def test_partial_update_leaves_other_fields_unchanged(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        updated = graph.update_share_target(target["id"], name="New Name")
        assert updated["config"] == {"url": "https://x.com"}
        assert updated["enabled"] is True


class TestDeleteShareTarget:
    def test_deletes_and_returns_true(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        assert graph.delete_share_target(target["id"]) is True
        assert graph.get_share_target(target["id"]) is None

    def test_returns_false_for_unknown_id(self, graph):
        assert graph.delete_share_target("00000000-0000-0000-0000-000000000000") is False


class TestListShareTargets:
    def test_includes_disabled_targets(self, graph):
        target = graph.create_share_target("webhook", "W", {"url": "https://x.com"})
        graph.update_share_target(target["id"], enabled=False)
        ids = {t["id"] for t in graph.list_share_targets()}
        assert target["id"] in ids
