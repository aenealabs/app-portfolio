# Audit log

Everything that changes something, or is refused, is recorded with who did it and when.
Only approvers can open the log.

## What is recorded

| Event | Recorded when |
| --- | --- |
| Inventory loaded | The app first loads the inventory, licenses, and contracts into an empty database |
| App decided | An approver records a decision (with the rules' proposal and any reason) |
| Sent to backlog | A decision goes to Backlog Pilot's inbox |
| Contract read | The AI reads a contract (with how many terms passed the checks and how many were flagged) |
| Directory synced | Access groups are counted |
| Signed in | Someone signs in with single sign-on |
| Access denied | Someone without approver rights tries to decide, send, read a contract, sync the directory, or open this log |
| Access denied (not signed in) | With single sign-on, someone tries an action without signing in (opening a page just asks them to sign in) |
| Sign-in failed | A sign-in could not be completed or verified |

## Searching

Search by words, filter by category (apps, contracts, sign-in and access), or by an app or license key
such as `APP-04`. Matching words are highlighted.
