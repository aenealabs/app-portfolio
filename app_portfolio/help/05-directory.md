# Legacy apps on Active Directory

Older engineering apps often have no single sign-on: access is granted by membership of an
Active Directory group. The Directory page reads those groups over LDAP, read-only.

## What LDAP can tell you

- **Entitled users:** enabled accounts in the group, including through nested groups. Loops
  between groups and members that no longer exist are handled, not fatal.
- **Disabled accounts still in the group:** people who left but were never removed. Each one
  is flagged on the app, because removing them is cheap and auditors ask.
- **Who signed in to the domain recently** (lastLogonTimestamp, within 90 days).

## What it cannot tell you

Active Directory does not record which app someone used. A domain sign-in means the person
logged in to the network, and the timestamp can lag about 14 days. So the rules use it as
**active users only when the app has nothing better**: an app audit log, a license server,
or a SaaS sign-in log always wins. The app's page says which source each number came from.

## Access reviews

When 20% or more of a group's enabled accounts have not signed in to the domain in 90 days,
the app is flagged for an access review. Combined with disabled accounts left in the group,
this is the list to send to the app owner.

## Setting up a real directory

1. Ask the directory team for a read-only service account that can read the access groups'
   `member` attribute and users' `userAccountControl` and `lastLogonTimestamp`. Nothing else.
2. Set `AP_LDAP_URL` (for example `ldaps://dc01.corp.example.com:636`), `AP_LDAP_BIND_DN`,
   and `AP_LDAP_PASSWORD`. Plain `ldap://` is refused unless `AP_LDAP_ALLOW_INSECURE=true`,
   which is for lab directories only.
3. Add each legacy app's group to the inventory (`ad_group`), then click
   **Count groups now**.

Only counts are stored, never names, and each sync is in the audit log. Apps on Microsoft
Entra ID should use their sign-in logs from Microsoft Graph instead; LDAP is for the ones
that cannot.
