from uuid import uuid4

from fastapi.testclient import TestClient

from clear_context.main import create_app


def test_groups_organize_history_without_touching_reports(settings):
    with TestClient(create_app(settings)) as client:
        investigation = client.post("/api/investigations", json={"text": "A claim."}).json()
        report_before = client.get(f"/api/investigations/{investigation['id']}/report").json()

        group = client.post("/api/groups", json={"name": "  Storm   claims "}).json()
        assert group["name"] == "Storm claims" and group["position"] == 0
        second = client.post("/api/groups", json={"name": "Elections"}).json()
        assert second["position"] == 1

        response = client.put(
            f"/api/investigations/{investigation['id']}/group", json={"group_id": group["id"]}
        )
        assert response.status_code == 204
        listed = client.get("/api/investigations").json()
        assert listed[0]["group_id"] == group["id"]

        renamed = client.patch(f"/api/groups/{group['id']}", json={"name": "Storms"})
        assert renamed.json()["name"] == "Storms"
        assert [g["name"] for g in client.get("/api/groups").json()] == ["Storms", "Elections"]

        # Deleting a group ungroups its investigations and leaves the report as it was.
        assert client.delete(f"/api/groups/{group['id']}").status_code == 204
        assert client.get("/api/investigations").json()[0]["group_id"] is None
        report_after = client.get(f"/api/investigations/{investigation['id']}/report").json()
        assert report_after == report_before


def test_groups_reject_unknown_ids_and_empty_names(settings):
    with TestClient(create_app(settings)) as client:
        investigation = client.post("/api/investigations", json={"text": "A claim."}).json()
        assert client.post("/api/groups", json={"name": "   "}).status_code == 422
        assert client.post("/api/groups", json={"name": "x" * 61}).status_code == 422
        assert client.patch(f"/api/groups/{uuid4()}", json={"name": "Nope"}).status_code == 404
        assert client.delete(f"/api/groups/{uuid4()}").status_code == 404
        unknown_group = client.put(
            f"/api/investigations/{investigation['id']}/group", json={"group_id": str(uuid4())}
        )
        assert unknown_group.status_code == 404
        unknown_investigation = client.put(
            f"/api/investigations/{uuid4()}/group", json={"group_id": None}
        )
        assert unknown_investigation.status_code == 404
        assert client.get("/api/investigations").json()[0]["group_id"] is None
