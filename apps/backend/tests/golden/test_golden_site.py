"""The golden site itself; runs without a browser."""

import httpx
import pytest

from . import site as site_module
from .site import FIELDS, GoldenSite


def test_item_pages_expose_five_fields_and_inject_faults(monkeypatch):
    monkeypatch.setattr(site_module, "FIRST_LOAD_DELAY_SECONDS", 0.2)
    with GoldenSite() as site:
        ok = httpx.get(f"{site.base_url}/item/a1")
        assert ok.status_code == 200
        for field in FIELDS:
            assert f"id={field}>{field}-a1<" in ok.text
        assert httpx.get(f"{site.base_url}/item/gone-1").status_code == 404
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"{site.base_url}/item/timeout-1", timeout=0.05)
        assert (
            httpx.get(f"{site.base_url}/item/timeout-1", timeout=2).status_code == 200
        )
        assert site.hits("/item/") == 4


def test_form_submits_once_and_lost_responses_never_answer(monkeypatch):
    monkeypatch.setattr(site_module, "LOST_RESPONSE_HOLD_SECONDS", 0.3)
    with GoldenSite() as site:
        form = httpx.get(f"{site.base_url}/form?name=row-1")
        assert "action='/submit?name=row-1'" in form.text
        assert "value='row-1'" in form.text
        done = httpx.post(f"{site.base_url}/submit", data={"name": "row-1"})
        assert done.text == "<p id=result>ok:row-1</p>"
        with pytest.raises(httpx.HTTPError):
            httpx.post(f"{site.base_url}/submit", data={"name": "lose-1"}, timeout=2)
        assert site.submissions("row-1") == 1
        assert site.submissions("lose-1") == 1


def test_explicit_lost_response_flag_survives_the_form_action(monkeypatch):
    monkeypatch.setattr(site_module, "LOST_RESPONSE_HOLD_SECONDS", 0.02)
    with GoldenSite() as site:
        form = httpx.get(f"{site.base_url}/form?name=ordinary&lose=1")
        assert "action='/submit?name=ordinary&amp;lose=1'" in form.text
        with pytest.raises(httpx.RemoteProtocolError):
            httpx.post(
                f"{site.base_url}/submit?name=ordinary&lose=1",
                data={"name": "ordinary"},
            )
        assert site.submissions("ordinary") == 1
