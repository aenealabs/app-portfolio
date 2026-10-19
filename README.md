# App Portfolio

Application rationalization and license intelligence for engineering IT. Part of **Mission
Control**, with Backlog Pilot, Leadership Pilot, PLM Insight, and Support Pilot: same stack,
Brightlayer UI styling, and governance rules (code scores and computes deadlines, the model
only reads contracts, code checks every quote and number, a person decides).

## Quick start

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python -m app_portfolio.app      # http://127.0.0.1:8040
```

The demo loads a fictional inventory of 18 engineering apps, 8 licenses, and 6 contract
excerpts (`scripts/generate_data.py`, `data/demo/contracts/`), plus a fictional Active
Directory for the legacy apps (`scripts/generate_directory.py`).

## What M1 does

- **Overlap with the platform, computed.** Each app's capabilities against what the strategic
  PLM platform already provides.
- **A TIME proposal by rule** (Invest, Tolerate, Migrate, Eliminate) from business fit (active
  users), technical fit (vendor support, open security findings, hosting), and overlap, with
  the rule and numbers shown. A 2x2 shows the whole portfolio; apps that duplicate the
  platform are ringed.
- **A person decides.** Differing from the rules needs a reason. Migrate and Eliminate
  decisions can be sent to Backlog Pilot as retirement work.
- **Contract terms read by AI, checked by code.** The model extracts term end, automatic
  renewal, notice period, price increase, true-up premium, early termination, and data
  export, each with an exact quote. Code checks the quote word for word, that a date appears
  in its quote as written, and that every number appears in its quote. Only checked terms
  are used; anything else is shown and flagged.
- **License intelligence.** Utilization against entitlement, spare seats and what they cost,
  true-up exposure (with the checked contract premium), built-in renewal increases, and a
  calendar of notice deadlines, flagging any that have already passed.

## Built-in Help

**Help** in the side menu explains every screen, and the **?** in the app bar opens the
section about the screen you are on. The **rules and settings reference** is generated from
the same constants the rules run on, so it always matches what the app does; tests fail if a
screen has no help section or a setting is undocumented. Every app also serves the shared
*How Mission Control works* guide (from `mission-control-common`).

Across the suite, overriding a proposed score, rating, placement, or fix, rejecting a draft,
or dropping anything the AI drafted needs a reason; rewording a draft keeps the AI's original
beside it. Every refused attempt is audited, including actions tried without signing in and
failed sign-ins.

## Legacy apps on Active Directory (LDAP)

Many older engineering apps (on-premises vaults, license-served CAD, in-house tools) have no
single sign-on and no SaaS sign-in log; access is granted by membership of an AD group. The
**Directory** page reads those groups over LDAP, read-only:

- **Entitled users:** enabled user accounts in the app's access group, including nested
  groups. Loops between nested groups are handled and members that no longer exist are
  counted, not fatal.
- **Disabled accounts still in the group:** leavers who were never removed, flagged on the app
  as an access-review finding.
- **Signed in (90 days):** `lastLogonTimestamp`, which means a domain sign-in, not use of the
  app, and can lag about 14 days. It is labeled as a proxy and only replaces active users for
  apps with no better source; where an app audit log or license server exists, that wins.
  Each app shows where its licensed and active numbers came from.

Only counts are stored, never names. Each sync is audited. To read a real directory, set:

```bash
AP_LDAP_URL=ldaps://dc01.corp.example.com:636   # LDAPS only
AP_LDAP_BIND_DN=CN=svc-mission-control,OU=Service Accounts,DC=corp,DC=example,DC=com
AP_LDAP_PASSWORD=...
```

The service account needs read access to the groups and to `userAccountControl` and
`lastLogonTimestamp` on users; nothing else. Plain `ldap://` is refused unless
`AP_LDAP_ALLOW_INSECURE=true` (lab directories only). Without `AP_LDAP_URL` the page reads the
in-memory demo directory. Apps on Microsoft Entra ID should use sign-in logs from Microsoft
Graph instead; LDAP is for the ones that cannot.

## Roadmap

- **M1 (this release):** rationalization rules and decisions, checked contract terms, license
  utilization and notice deadlines, hand-off to Backlog Pilot, read-only AD group counts for
  legacy apps.
- **M2:** AI rationale per app (checked against the inventory); vendor risk view.
- **M3:** polish.

## Data and branding

All apps, vendors, contracts, and numbers are fictional. The UI uses the open-source
Brightlayer UI color and theme values (BSD-3-Clause) and reads directories with ldap3
(LGPL-3.0); see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This is an independent project, not affiliated with or endorsed by Eaton.

## License

Copyright (c) 2026 aenealabs. All rights reserved.
