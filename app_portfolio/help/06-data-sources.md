# Where the data comes from

Every input is read-only: App Portfolio never writes back to the systems it reads.

## In the demo

The demo reads fictional files in `data/demo`: the inventory (`apps.csv`), licenses
(`licenses.csv`), the PLM platform's capabilities (`platform.json`), six contract excerpts,
and an in-memory Active Directory. Every name, vendor, and number is invented.

## In a real deployment

| Data | Typical source | How it gets in |
| --- | --- | --- |
| Application inventory, owners, hosting | CMDB or application portfolio register (for example, ServiceNow) | Export to the inventory file |
| Active users | The app's audit log or license server; SaaS sign-in logs; AD groups for legacy apps | Export, or the Directory page for AD |
| Licenses and entitlements | License servers (FlexNet and similar), vendor portals, SaaS admin consoles | Export to the licenses file |
| Costs | Procurement or accounts payable | Export to the inventory and licenses files |
| Vendor support end dates | Vendor lifecycle notices | Kept in the inventory |
| Open security findings | Vulnerability management (scanners, the security team's tracker) | Count per app in the inventory |
| Contracts | The contract repository or CLM system | Text of each contract |
| Platform capabilities | The PLM platform team | `platform.json` |

Today the files are loaded once, into an empty database; an import page is planned. Whatever the source, the
rules and checks are the same, and the app page shows where each user count came from.
