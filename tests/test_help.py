import re
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app_portfolio import rules
from app_portfolio.app import PAGE_HELP, create_app
from app_portfolio.config import PACKAGE_DIR, load_settings
from app_portfolio.db import make_engine
from app_portfolio.help_reference import SETTINGS


def client(tmp_path):
    settings = replace(load_settings(), db_path=str(tmp_path / "t.db"))
    return TestClient(create_app(settings, engine=make_engine(settings.db_path)))


def test_help_pages_reference_and_suite_guide(tmp_path):
    c = client(tmp_path)
    assert "Who does what" in c.get("/help").text
    for slug in ("portfolio", "licenses", "contracts", "directory", "data-sources", "audit"):
        assert c.get(f"/help/{slug}").status_code == 200, slug
    ref = c.get("/help/reference").text
    assert f"Within {rules.NOTICE_URGENT_DAYS} days: urgent" in ref  # live values, not copies
    assert rules.RULES["technical"] in ref and "AP_LDAP_URL" in ref
    assert "How Mission Control works" in c.get("/help/mission-control").text


def test_every_screen_has_a_help_section(tmp_path):
    screens = {p.name for p in (PACKAGE_DIR / "templates").glob("*.html")} - {"base.html"}
    assert screens == set(PAGE_HELP)  # startup also checks each target section exists
    page = client(tmp_path).get("/licenses").text
    assert f'href="/help/{PAGE_HELP["licenses.html"]}"' in page


def test_every_setting_the_code_reads_is_documented():
    source = "\n".join(p.read_text() for p in Path(PACKAGE_DIR).rglob("*.py"))
    used = set(re.findall(r'"((?:AP|ANTHROPIC)_[A-Z_]+|MISSION_CONTROL_APPS)"', source))
    assert {"AP_LDAP_URL", "AP_SUITE_TOKEN", "AP_OIDC_CLIENT_ID"} <= used  # the scan works
    assert used - set(SETTINGS) == set()
