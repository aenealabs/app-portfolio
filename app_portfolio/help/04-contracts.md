# Contracts

The AI reads each contract; code decides whether to believe it.

## How a contract is read

An approver clicks **Read the contract**. The AI extracts seven terms (when the term ends,
whether it renews automatically, the notice period, the price increase, the true-up premium,
early termination, and data export), each with the exact sentence it came from. It also lists
what to act on before the renewal.

In the offline demo, readings come from recordings made earlier by the same AI, so the demo
works without an AI account.

## What the checks catch

Before a term is used, code checks that:

- the quote is in the contract word for word;
- a date appears in the quote the way the contract writes it;
- every number appears in its quote (a zero only when the quote says there is none).

A term that fails is shown with a flag and the reason, and the rules ignore it. A term the
contract does not mention shows as "not stated". The exact checks are in the
[reference](reference#contract-checks).

## When a term is flagged

Read the quote against the contract text beside it. If the contract is ambiguous, settle it
with the vendor or Legal; do not override the check. **Read again** asks the AI to read the
contract afresh, and the new reading is checked the same way.
