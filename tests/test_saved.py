"""Saved searches tests: CRUD, duplicate, run/touch, limits."""


def _make(client, name="My deals", q="pizza offer", **kw):
    body = {"name": name, "q": q, "chat_ids": [-1], "sender": "",
            "media": "", "date_from": "2026-01-01", "date_to": "",
            "sort": "desc"}
    body.update(kw)
    return client.post("/api/saved-searches", json=body)


def test_create_list_and_shape(api_client):
    r = _make(api_client)
    assert r.status_code == 200
    row = r.json()
    assert row["id"] > 0 and row["name"] == "My deals"
    assert row["chat_ids"] == [-1]           # JSON round-trips as a list
    assert row["last_used_at"]

    lst = api_client.get("/api/saved-searches").json()
    assert len(lst) == 1 and lst[0]["q"] == "pizza offer"


def test_rename_and_edit(api_client):
    sid = _make(api_client).json()["id"]
    r = api_client.patch(f"/api/saved-searches/{sid}",
                         json={"name": "Renamed", "q": "new query",
                               "chat_ids": [], "sender": "", "media": "1",
                               "date_from": "", "date_to": "", "sort": "asc"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Renamed" and body["q"] == "new query"
    assert body["media"] == "1" and body["sort"] == "asc"
    # invalid sort falls back rather than storing junk
    r = api_client.patch(f"/api/saved-searches/{sid}",
                         json={"name": "X", "q": "y", "chat_ids": [],
                               "sender": "", "media": "", "date_from": "",
                               "date_to": "", "sort": "nope"})
    assert r.json()["sort"] == "desc"


def test_duplicate_and_delete(api_client):
    sid = _make(api_client).json()["id"]
    dup = api_client.post(f"/api/saved-searches/{sid}/duplicate").json()
    assert dup["id"] != sid
    assert dup["name"].endswith("(copy)")
    assert dup["q"] == "pizza offer"

    assert api_client.delete(f"/api/saved-searches/{sid}").json()["ok"] is True
    assert api_client.delete(f"/api/saved-searches/{sid}").status_code == 404
    assert len(api_client.get("/api/saved-searches").json()) == 1


def test_run_updates_last_used(api_client):
    sid = _make(api_client).json()["id"]
    before = api_client.get("/api/saved-searches").json()[0]["last_used_at"]
    # freeze-ish: just make sure a later timestamp is stored
    import time
    time.sleep(1.1)
    row = api_client.post(f"/api/saved-searches/{sid}/run").json()
    assert row["last_used_at"] > before


def test_missing_returns_404(api_client):
    assert api_client.patch("/api/saved-searches/999",
                            json={"name": "x", "q": "y", "chat_ids": [],
                                  "sender": "", "media": "", "date_from": "",
                                  "date_to": "", "sort": "desc"}
                            ).status_code == 404
    assert api_client.post("/api/saved-searches/999/run").status_code == 404
    assert api_client.post("/api/saved-searches/999/duplicate"
                           ).status_code == 404


def test_saved_search_export(api_client):
    _make(api_client, name="عروض البيتزا", q="عرض")
    r = api_client.get("/api/export/saved-searches")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "عروض البيتزا" in r.text  # Arabic survives, UTF-8 intact
