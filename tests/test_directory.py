import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_portfolio.app import create_app
from app_portfolio.config import load_settings
from app_portfolio.db import make_engine
from app_portfolio.directory import (
    DirectoryError,
    DirectorySettings,
    connect,
    count_group,
    demo_connection,
)

FIXTURE = load_settings().dataset_dir / "directory.json"
BASE = "DC=corp,DC=example,DC=com"
NEW = 133800000000000000  # a FILETIME far in the past; tests set recent ones explicitly


def tiny(tmp_path: Path) -> Path:
    """A small directory: nesting, a cycle, a disabled user, a deleted member, a computer."""
    def user(n, flags=512, last=134055000000000000):  # ~2025-10, recent relative to 2025-11
        return {"dn": f"CN=u{n},OU=Users,{BASE}",
                "attributes": {"objectClass": ["top", "person", "user"],
                               "userAccountControl": flags, "lastLogonTimestamp": last}}
    entries = [user(1), user(2, last=NEW), user(3, flags=514), user(4),
               {"dn": f"CN=pc1,OU=Computers,{BASE}",
                "attributes": {"objectClass": ["top", "computer", "user"],
                               "userAccountControl": 4096}},
               {"dn": f"CN=inner,OU=Groups,{BASE}",
                "attributes": {"objectClass": ["top", "group"],
                               "member": [f"CN=u4,OU=Users,{BASE}", f"CN=outer,OU=Groups,{BASE}"]}},
               {"dn": f"CN=outer,OU=Groups,{BASE}",
                "attributes": {"objectClass": ["top", "group"],
                               "member": [f"CN=u1,OU=Users,{BASE}", f"CN=u2,OU=Users,{BASE}",
                                          f"CN=u3,OU=Users,{BASE}", f"CN=pc1,OU=Computers,{BASE}",
                                          f"CN=inner,OU=Groups,{BASE}",
                                          f"CN=gone,OU=Users,{BASE}"]}}]
    path = tmp_path / "dir.json"
    path.write_text(json.dumps({"service_account": f"CN=svc,{BASE}", "entries": entries}))
    return path


def test_count_group_handles_nesting_cycles_disabled_and_missing(tmp_path):
    conn = demo_connection(tiny(tmp_path))
    g = count_group(conn, f"CN=outer,OU=Groups,{BASE}", date(2025, 11, 15))
    assert (g.entitled, g.disabled, g.nested_groups, g.missing) == (3, 1, 1, 1)
    assert g.active == 2  # u2 has not signed in for years
    with pytest.raises(DirectoryError, match="not a group"):
        count_group(conn, f"CN=u1,OU=Users,{BASE}", date(2025, 11, 15))


def test_ldaps_is_required():
    with pytest.raises(DirectoryError, match="ldaps://"):
        connect(DirectorySettings(url="ldap://dc01.corp.example.com"), FIXTURE)


@pytest.fixture
def client(tmp_path):
    settings = replace(load_settings(), db_path=str(tmp_path / "t.db"))
    return TestClient(create_app(settings, engine=make_engine(settings.db_path),
                                 directory=DirectorySettings()))


def test_sync_feeds_entitlement_and_flags_but_not_app_usage(client):
    assert "not counted yet" in client.get("/directory").text
    page = client.post("/directory/sync").text
    assert "Counted 9 access groups" in page
    vault = client.get("/apps/APP-01").text  # has an app audit log
    assert "Licensed: AD group GG-Vaultline-Users" in vault
    assert "Active: app audit log" in vault and "402 of 465 licensed" in vault
    assert "38 disabled accounts still in the access group" in vault
    parts = client.get("/apps/APP-04").text  # domain activity must not inflate app usage
    assert "118 of 880 licensed" in parts and "Eliminate" in parts
    tool = client.get("/apps/APP-12").text  # no app-level source: the proxy, labeled
    assert "domain sign-ins (proxy" in tool
    assert "directory_synced" in client.get("/audit").text


def test_only_approvers_sync(client):
    client.cookies.set("ap_user", "eng")
    assert client.post("/directory/sync").status_code == 403
