"""Structured output the model returns. Every term carries an exact quote that code checks
against the contract before any rule uses it."""

from pydantic import BaseModel, Field


class Term(BaseModel):
    value: str = Field(description="The value in the requested format.")
    quote: str = Field(description="The sentence or clause it comes from, copied exactly.")


class ContractTerms(BaseModel):
    end_date: Term | None = Field(description="End of the current term, as YYYY-MM-DD. Null "
                                  "if not stated.")
    auto_renew: Term | None = Field(description="'yes' if the term renews automatically, "
                                    "'no' if it does not. Null if not stated.")
    notice_days: Term | None = Field(description="Days of notice needed to stop renewal, as a "
                                     "whole number. Null if not stated.")
    escalator_pct: Term | None = Field(description="Price increase at renewal, as a number of "
                                       "percent (the maximum if 'up to'). Null if not stated.")
    trueup_premium_pct: Term | None = Field(description="Premium over list or unit price for "
                                            "users above the licensed quantity, as a number "
                                            "of percent; '0' if billed at the unit rate. Null "
                                            "if not stated.")
    termination: Term | None = Field(description="One sentence: how the customer can end it "
                                     "early. Null if not stated.")
    data_export: Term | None = Field(description="One sentence: how the customer gets its data "
                                     "out, and any fee. Null if not stated.")
    watch_outs: list[str] = Field(description="Up to three terms a buyer should act on before "
                                  "renewal, each one sentence, in plain words.")
