# Portfolio and decisions

The Portfolio page shows every engineering app with what the rules propose and what people
decided.

## Reading the 2x2

Each dot is an app. Up is **business fit** (how many licensed users are active); right is
**technical fit** (vendor support, open security findings, hosting). Dot size is annual cost.
Color is the proposal, or the decision once one is made.

A **ring** means most of the app's capabilities are already in the PLM platform. Ringed apps
are proposed for Migrate (if people use them) or Eliminate (if they do not), wherever they sit.

## Why an app got its proposal

Open the app. **Rules propose** lists the reasons with the numbers behind them, for example
"118 of 900 licensed users active (13%)" or "vendor support ends Dec 31, 2026". Expand
**The rules** to see the exact rules. Flags (support ending, open security findings, disabled
accounts in the access group) are shown even when they do not change the proposal.

The **Inventory record** shows where the user counts came from: an app audit log, a license
server, a SaaS sign-in log, or the Active Directory group (see [Directory](directory)).

## Recording a decision

Approvers pick Invest, Tolerate, Migrate, or Eliminate and click **Record decision**. If you
choose something other than the rules' proposal, a reason is required, for example "the
replacement is already funded for Q2". The decision, who made it, and the reason go into the
audit log. Recording a new decision keeps the earlier ones in the log.

## Sending retirement work

Once an app is decided Migrate or Eliminate, **Send retirement work to Backlog Pilot** puts it
in Backlog Pilot's inbox with the decision, the reasons, the flags, the cost, and the number
of integrations to replace. Someone in Backlog Pilot turns it into stories. The button appears
only when the two apps are connected.
