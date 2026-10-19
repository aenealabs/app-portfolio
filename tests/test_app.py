from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app_portfolio.app import create_app
from app_portfolio.config import load_settings
from app_portfolio.db import make_engine


@pytest.fixture
def settings(tmp_path):
    return replace(load_settings(), db_path=str(tmp_path / "t.db"))


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings, engine=make_engine(settings.db_path)))


def test_pages_render(client):
    for path in ["/", "/apps/APP-01", "/licenses", "/contracts", "/contracts/ardent.md",
                 "/audit"]:
        assert client.get(path).status_code == 200, path
