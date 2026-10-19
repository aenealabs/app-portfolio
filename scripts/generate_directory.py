"""Write the fictional Active Directory used by the offline demo (data/demo/directory.json).

AD access groups for the on-premises legacy apps, with nested groups (and one nesting cycle),
users who have not signed in for months, and disabled accounts left in groups after people
left. Seeded, so the counts are the same everywhere. Every name is invented.

Usage: python scripts/generate_directory.py
"""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "demo" / "directory.json"
BASE = "DC=corp,DC=example,DC=com"
AS_OF = datetime(2026, 10, 1, tzinfo=UTC)
rng = random.Random(20261018)

# app key: (access group, direct users, nested groups as (name, users), disabled left behind,
#           share of enabled users who signed in to the domain in the last 90 days)
GROUPS = {
    "APP-01": ("GG-Vaultline-Users", 140, [("GG-eMobility-Design", 230), ("GG-eMobility-Mfg", 95)],
               38, 0.86),
    "APP-04": ("GG-PartFinder-Users", 60, [("GG-All-Engineering", 820)], 74, 0.81),
    "APP-06": ("GG-DrawShare-Users", 120, [("GG-Supplier-Quality", 190)], 22, 0.88),
    "APP-08": ("GG-BOMBridge-Operators", 34, [], 3, 0.95),
    "APP-10": ("GG-CircuitStudio-Users", 85, [("GG-EP-Electrical-Design", 120)], 9, 0.93),
    "APP-12": ("GG-ToolRoom-Users", 44, [], 2, 0.91),
    "APP-14": ("GG-DocuVault-Users", 110, [("GG-Aero-Programs", 160)], 61, 0.62),
    "APP-15": ("GG-MaterialsDB-Users", 70, [("GG-Materials-Lab", 48)], 5, 0.9),
    "APP-18": ("GG-HarnessCAD-Users", 31, [("GG-eMobility-Harness", 25)], 4, 0.92),
}


def filetime(dt: datetime) -> int:
    """Windows FILETIME (100 ns since 1601), as AD stores lastLogonTimestamp."""
    return int((dt.timestamp() + 11644473600) * 10_000_000)


def main() -> None:
    entries, n = [], 0

    def user(active_share: float, disabled: bool = False) -> str:
        nonlocal n
        n += 1
        dn = f"CN=user{n:05d},OU=Users,OU=Engineering,{BASE}"
        days_ago = rng.randint(1, 85) if rng.random() < active_share else rng.randint(95, 700)
        attrs = {"objectClass": ["top", "person", "organizationalPerson", "user"],
                 "sAMAccountName": f"user{n:05d}",
                 "userAccountControl": 514 if disabled else 512,
                 "lastLogonTimestamp": filetime(AS_OF - timedelta(days=days_ago))}
        entries.append({"dn": dn, "attributes": attrs})
        return dn

    def group(name: str, members: list[str]) -> str:
        dn = f"CN={name},OU=Groups,{BASE}"
        entries.append({"dn": dn, "attributes": {"objectClass": ["top", "group"],
                                                 "sAMAccountName": name, "member": members}})
        return dn

    mapping = {}
    for key, (name, direct, nested, disabled, share) in GROUPS.items():
        members = [user(share) for _ in range(direct)]
        members += [user(share, disabled=True) for _ in range(disabled)]
        for sub, size in nested:
            members.append(group(sub, [user(share) for _ in range(size)]))
        mapping[key] = group(name, members)
    # a nesting cycle: the harness group is also nested back inside its own child group
    for e in entries:
        if e["dn"].startswith("CN=GG-eMobility-Harness,"):
            e["attributes"]["member"].append(mapping["APP-18"])
    # a member that no longer exists (deleted account still referenced)
    for e in entries:
        if e["dn"] == mapping["APP-14"]:
            e["attributes"]["member"].append(f"CN=deleted-user,OU=Users,OU=Engineering,{BASE}")
    OUT.write_text(json.dumps({
        "_note": "Fictional Active Directory for the offline demo (scripts/generate_directory.py).",
        "service_account": f"CN=svc-mission-control,OU=Service Accounts,{BASE}",
        "as_of": AS_OF.date().isoformat(), "groups": mapping, "entries": entries}) + "\n")
    print(f"{n} users, {len(entries) - n} groups -> {OUT.name}")


if __name__ == "__main__":
    main()
