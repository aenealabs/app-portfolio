"""Read-only Active Directory over LDAP, for legacy engineering apps that grant access through
AD groups instead of single sign-on.

What LDAP can tell us, and what it cannot:
- Entitled users: the enabled user accounts in the app's access group, including nested
  groups. Disabled accounts still in the group are counted separately (leavers who were never
  removed are a finding in their own right).
- Active users: AD does not record which app someone used. The best LDAP-readable signal is
  lastLogonTimestamp, which says someone signed in to the domain (it can lag by up to about
  14 days). It is shown as a proxy, never as app usage; the app's own logs or license server
  are better sources where they exist.

Only counts are stored, never names. The connection is read-only, LDAPS only (plain LDAP needs
an explicit lab-only override), with one service account. Groups are expanded by reading
member entries rather than with AD's matching-rule filters, so the same code works against
Active Directory, other LDAP directories, and the offline demo directory.
"""

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ldap3 import BASE, MOCK_SYNC, OFFLINE_AD_2012_R2, Connection, Server
from ldap3.core.exceptions import LDAPException

ACCOUNTDISABLE = 0x2  # userAccountControl flag
NEVER = datetime(1971, 1, 1, tzinfo=UTC)  # AD returns 1601-01-01 for "never signed in"


class DirectoryError(Exception):
    """The directory could not be reached or read; the message is user-facing."""


@dataclass(frozen=True)
class DirectorySettings:
    url: str = ""  # ldaps://dc01.corp.example.com:636
    bind_dn: str = ""  # the read-only service account
    password: str = ""
    allow_insecure: bool = False  # plain ldap:// for a lab directory only

    @property
    def live(self) -> bool:
        return bool(self.url)


def load_directory_settings() -> DirectorySettings:
    return DirectorySettings(os.getenv("AP_LDAP_URL", "").strip(),
                             os.getenv("AP_LDAP_BIND_DN", "").strip(),
                             os.getenv("AP_LDAP_PASSWORD", ""),
                             os.getenv("AP_LDAP_ALLOW_INSECURE", "").lower() in ("1", "true"))


def connect(settings: DirectorySettings, demo_fixture: Path) -> Connection:
    """A bound, read-only connection: the live directory if configured, else the demo one."""
    if not settings.live:
        return demo_connection(demo_fixture)
    if not settings.url.lower().startswith("ldaps://") and not settings.allow_insecure:
        raise DirectoryError("Use ldaps:// so the service account's password and the directory "
                             "data are encrypted in transit.")
    try:
        server = Server(settings.url, use_ssl=settings.url.lower().startswith("ldaps://"),
                        connect_timeout=10)
        conn = Connection(server, user=settings.bind_dn, password=settings.password,
                          read_only=True, auto_range=True, receive_timeout=30)
        if not conn.bind():
            raise DirectoryError("The directory refused the service account's sign-in. Check "
                                 "AP_LDAP_BIND_DN and the password.")
    except LDAPException as e:
        raise DirectoryError(f"Could not reach the directory: {e}") from e
    return conn


def demo_connection(fixture: Path) -> Connection:
    """An in-memory directory loaded from the fictional demo fixture."""
    data = json.loads(fixture.read_text())
    server = Server("demo-directory", get_info=OFFLINE_AD_2012_R2)
    conn = Connection(server, user=data["service_account"], password="demo",
                      client_strategy=MOCK_SYNC, read_only=True)
    conn.strategy.add_entry(data["service_account"],
                            {"objectClass": ["user"], "userPassword": "demo"})
    for e in data["entries"]:
        conn.strategy.add_entry(e["dn"], e["attributes"])
    conn.bind()
    return conn


@dataclass
class GroupCount:
    group: str
    entitled: int  # enabled user accounts, including through nested groups
    active: int  # of those, signed in to the domain within the window
    disabled: int  # disabled accounts still in the group
    nested_groups: int
    missing: int  # member entries that could not be read

    def caveat(self, days: int = 90) -> str:
        return (f"active means signed in to the domain within {days} days (lastLogonTimestamp, "
                "which can lag about 14 days), not use of this app")


def _read(conn: Connection, dn: str, attributes: list[str]):
    if not conn.search(dn, "(objectClass=*)", search_scope=BASE, attributes=attributes):
        return None
    return conn.entries[0] if conn.entries else None


def count_group(conn: Connection, group_dn: str, as_of: date, days: int = 90) -> GroupCount:
    group = _read(conn, group_dn, ["objectClass", "member"])
    if group is None or "group" not in [c.lower() for c in group.objectClass.values]:
        raise DirectoryError(f"{group_dn} is not a group in the directory.")
    cutoff = datetime.combine(as_of - timedelta(days=days), datetime.min.time(), tzinfo=UTC)
    queue, seen = [group_dn], {group_dn.lower()}
    users: dict[str, datetime | None] = {}
    disabled = nested = missing = 0
    while queue:
        g = _read(conn, queue.pop(0), ["member"])
        for member in (g.member.values if g is not None and "member" in g else []):
            if member.lower() in seen:
                continue  # also stops cycles between nested groups
            seen.add(member.lower())
            e = _read(conn, member, ["objectClass", "userAccountControl", "lastLogonTimestamp"])
            if e is None:
                missing += 1
                continue
            classes = [c.lower() for c in e.objectClass.values]
            if "group" in classes:
                nested += 1
                queue.append(member)
            elif "user" in classes and "computer" not in classes:
                flags = int(e.userAccountControl.value or 0) if "userAccountControl" in e else 0
                if flags & ACCOUNTDISABLE:
                    disabled += 1
                    continue
                seen_at = e.lastLogonTimestamp.value if "lastLogonTimestamp" in e else None
                users[member.lower()] = seen_at if seen_at and seen_at > NEVER else None
    active = sum(1 for t in users.values() if t and t >= cutoff)
    return GroupCount(group_dn, len(users), active, disabled, nested, missing)
