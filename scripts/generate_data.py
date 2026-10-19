"""Write the fictional application inventory and license data used by the offline demo.

Hand-curated rather than random, so each TIME outcome has a clear story. Writes
data/demo/apps.csv, licenses.csv, and platform.json. Every name, vendor, and number is
invented. Contracts are hand-written Markdown in data/demo/contracts/.

Usage: python scripts/generate_data.py
"""

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "demo"

PLATFORM = {
    "name": "PLM platform (strategic)",
    "as_of": "2026-10-01",
    "capabilities": ["part management", "BOM management", "engineering change",
                     "document management", "CAD data management", "workflow approvals",
                     "classification", "3D viewer", "requirements management",
                     "supplier collaboration", "where-used reporting", "access control"],
}

# key, name, vendor, category, unit, capabilities, licensed, active 90d, cost $K/yr,
# support end, hosting, open findings, integrations, owner
APPS = [
    ("APP-01", "Vaultline Classic", "Ardent Systems", "CAD data management", "eMobility",
     "CAD data management;document management;access control;where-used reporting",
     480, 402, 310, "2027-03-31", "on-prem", 4, 6, "Grace Whitfield"),
    ("APP-02", "ChangeDesk", "Northbridge Software", "Engineering change", "Industrial Controls",
     "engineering change;workflow approvals;document management", 220, 61, 145, "", "SaaS",
     0, 2, "Hannah Liu"),
    ("APP-03", "SpecTrack 5", "Calder Tools", "Requirements", "Aerospace Systems",
     "requirements management;traceability;verification planning", 160, 132, 120, "", "SaaS",
     0, 3, "Marcus Bell"),
    ("APP-04", "PartFinder", "in-house", "Part search", "Electrical Products",
     "part management;classification;where-used reporting", 900, 118, 85, "2026-12-31",
     "on-prem", 2, 1, "Hannah Liu"),
    ("APP-05", "SimuForge", "Helix Engineering", "Simulation", "Aerospace Systems",
     "structural simulation;thermal simulation;results management", 70, 64, 410, "", "hosted",
     0, 2, "Marcus Bell"),
    ("APP-06", "DrawShare", "in-house", "Drawing distribution", "Global Supply Chain",
     "3D viewer;supplier collaboration;document management", 350, 210, 60, "2026-06-30",
     "on-prem", 5, 3, "Daniel Okafor"),
    ("APP-07", "TestBench Data", "Quorra Labs", "Test data", "eMobility",
     "test data management;results management;lab scheduling", 90, 71, 95, "", "SaaS", 0, 2,
     "Grace Whitfield"),
    ("APP-08", "BOMBridge", "in-house", "Integration", "Electrical Products",
     "BOM management;ERP integration", 40, 38, 140, "2027-09-30", "on-prem", 1, 4,
     "Elena Kovacs"),
    ("APP-09", "ClassiFy", "Meridian Data", "Classification", "Trade Compliance",
     "classification;export screening", 60, 12, 48, "", "SaaS", 0, 1, "Tomas Rivera"),
    ("APP-10", "CircuitStudio Pro", "Voltaic", "Electrical CAD", "Electrical Products",
     "schematic design;PCB layout;library management", 210, 188, 520, "", "on-prem", 0, 2,
     "Priya Raman"),
    ("APP-11", "RedlineQ", "Sablewood", "Markup", "Industrial Controls",
     "3D viewer;markup", 150, 22, 18, "", "SaaS", 0, 0, "Hannah Liu"),
    ("APP-12", "ToolRoom Tracker", "in-house", "Tooling", "Plant Operations",
     "tooling records;maintenance scheduling", 45, 41, 12, "", "on-prem", 1, 0,
     "Elena Kovacs"),
    ("APP-13", "QualityLoop", "Northbridge Software", "Quality", "Global Supply Chain",
     "nonconformance;corrective action;supplier collaboration", 260, 198, 175, "", "SaaS", 0,
     3, "Daniel Okafor"),
    ("APP-14", "DocuVault 9", "Ardent Systems", "Document management", "Aerospace Systems",
     "document management;access control;workflow approvals", 300, 95, 130, "2027-01-31",
     "on-prem", 3, 2, "Marcus Bell"),
    ("APP-15", "MaterialsDB", "in-house", "Materials", "Electrical Products",
     "material properties;compliance declarations", 120, 104, 22, "", "on-prem", 0, 1,
     "Priya Raman"),
    ("APP-16", "PlantView", "Sablewood", "Viewer", "Plant Operations",
     "3D viewer", 400, 380, 40, "", "SaaS", 0, 1, "Elena Kovacs"),
    ("APP-17", "FormFlow", "Calder Tools", "Workflow", "Industrial Controls",
     "workflow approvals;forms", 180, 30, 55, "", "SaaS", 0, 1, "Hannah Liu"),
    ("APP-18", "HarnessCAD", "Voltaic", "Wire harness design", "eMobility",
     "harness design;library management", 55, 50, 160, "", "on-prem", 0, 2,
     "Grace Whitfield"),
]

# Legacy on-premises apps grant access through Active Directory groups (see directory.py).
BASE_DN = "DC=corp,DC=example,DC=com"
AD_GROUPS = {
    "APP-01": "GG-Vaultline-Users",
    "APP-04": "GG-PartFinder-Users",
    "APP-06": "GG-DrawShare-Users",
    "APP-08": "GG-BOMBridge-Operators",
    "APP-10": "GG-CircuitStudio-Users",
    "APP-12": "GG-ToolRoom-Users",
    "APP-14": "GG-DocuVault-Users",
    "APP-15": "GG-MaterialsDB-Users",
    "APP-18": "GG-HarnessCAD-Users",
}
# Where "active users" comes from; "" means no app-level source, so the directory's
# domain sign-in proxy is used once it has been synced.
ACTIVE_SOURCE = {
    "APP-01": "app audit log",
    "APP-04": "app audit log",
    "APP-06": "",
    "APP-08": "app audit log",
    "APP-10": "license server",
    "APP-12": "",
    "APP-14": "app audit log",
    "APP-15": "",
    "APP-18": "license server",
}

# product key, product, vendor, model, entitlement, peak 90d, active named 90d,
# unit $K per seat/yr, renewal date, contract file
LICENSES = [
    ("LIC-01", "PLM platform engineer seats", "Keystone PLM", "concurrent", 900, 612, 1180,
     2.4, "2027-01-31", "keystone-plm.md"),
    ("LIC-02", "CircuitStudio Pro", "Voltaic", "named", 210, 188, 214, 2.2, "2026-12-15",
     "voltaic.md"),
    ("LIC-03", "SimuForge solver tokens", "Helix Engineering", "token", 70, 69, 64, 5.8,
     "2027-04-30", "helix.md"),
    ("LIC-04", "Vaultline Classic", "Ardent Systems", "named", 480, 402, 402, 0.55,
     "2026-11-30", "ardent.md"),
    ("LIC-05", "SpecTrack 5", "Calder Tools", "named", 160, 132, 132, 0.75, "2027-06-30",
     "calder.md"),
    ("LIC-06", "QualityLoop", "Northbridge Software", "named", 260, 198, 198, 0.65,
     "2027-02-28", "northbridge.md"),
    ("LIC-07", "RedlineQ", "Sablewood", "named", 150, 22, 22, 0.12, "2026-12-31", ""),
    ("LIC-08", "HarnessCAD", "Voltaic", "named", 55, 50, 58, 2.9, "2026-12-15", "voltaic.md"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "platform.json").write_text(json.dumps(
        {"_note": "Fictional: capabilities the strategic PLM platform already provides.",
         **PLATFORM}, indent=1) + "\n")
    with (OUT / "apps.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "name", "vendor", "category", "business_unit", "capabilities",
                    "users_licensed", "active_users_90d", "annual_cost_k", "support_end",
                    "hosting", "open_security_findings", "integrations", "owner", "ad_group",
                    "active_source"])
        for row in APPS:
            group = AD_GROUPS.get(row[0], "")
            w.writerow([*row, f"CN={group},OU=Groups,{BASE_DN}" if group else "",
                        ACTIVE_SOURCE.get(row[0], "SaaS sign-in log")])
    with (OUT / "licenses.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "product", "vendor", "model", "entitlement", "peak_90d",
                    "active_named_90d", "unit_cost_k", "renewal_date", "contract"])
        w.writerows(LICENSES)
    print(f"{len(APPS)} apps, {len(LICENSES)} licenses")


if __name__ == "__main__":
    main()
