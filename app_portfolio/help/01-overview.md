# App Portfolio

App Portfolio answers two questions for engineering IT: which applications should we keep,
and what are we about to pay for without meaning to?

## What it is for

- **Rationalization.** Engineering units collect tools: a CAD vault from an acquisition, three
  markup viewers, an in-house part search the PLM platform now does better. App Portfolio
  proposes Invest, Tolerate, Migrate, or Eliminate for each one, by rule, and records what a
  person decides.
- **Licenses and renewals.** Contracts renew automatically unless someone gives notice in
  time, and the notice window often closes months before the renewal. App Portfolio reads
  each contract, works out every notice deadline, and shows spare seats, true-up exposure,
  and built-in price increases.

## Who does what

| Who | Does what |
| --- | --- |
| **Rules (code)** | Score business fit, technical fit, and overlap with the PLM platform; propose a TIME outcome; compute utilization, spare seats, true-ups, and notice deadlines. |
| **The AI** | Reads contracts and extracts the renewal, notice, price, true-up, termination, and data terms, each with an exact quote. |
| **Code, again** | Checks every quote against the contract word for word, and every date and number against its quote. Only checked terms reach the rules. |
| **An approver** | Decides each app's future. Choosing something other than the rules' proposal needs a reason. |
| **The audit log** | Records every decision, contract reading, directory sync, hand-off, and refused attempt. |

## A typical review

1. Open **Portfolio** and look at the 2x2: where each app sits, and which ones are ringed
   because they duplicate the PLM platform.
2. Open an app to see why the rules proposed what they did, then record a decision.
3. Send Migrate and Eliminate decisions to Backlog Pilot as retirement work.
4. Check **Licenses** for notice deadlines due within 90 days, and act on them first.
5. Open a **Contract** to see the quoted terms behind a deadline before you rely on it.

The full list of rules, thresholds, and checks is in the
[rules and settings reference](reference).
