"""Rationalization and license rules. Pure functions, no AI.

Every proposal and flag carries the rule text and the numbers behind it. Contract terms reach
these rules only after code has checked them against the contract (see contracts.py).
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

TIME = ("Invest", "Tolerate", "Migrate", "Eliminate")

# Every threshold the rules use. The rule text below, the screens, and the Help reference are
# all built from these, so changing one changes what the rules do and what they say they do.
ACTIVE_WINDOW_DAYS = 90  # "active" means used in this many days
BUSINESS_ACTIVE_SHARE = 0.5  # share of licensed users active for high business fit
BUSINESS_MIN_USERS = 20  # and at least this many active users
SUPPORT_SOON_MONTHS, SUPPORT_SOON_PENALTY = 6, 60
SUPPORT_LATER_MONTHS, SUPPORT_LATER_PENALTY = 18, 40
FINDING_PENALTY, FINDING_PENALTY_CAP = 10, 40
ON_PREM_PENALTY = 10
TECHNICAL_HIGH = 60
OVERLAP_HIGH = 0.6
UNDER_USED = 0.75  # below this share of the entitlement in use, seats are spare
HEADROOM = 0.10  # spare seats leave this much above the peak
NEAR_CAPACITY = 0.95
NOTICE_URGENT_DAYS, NOTICE_SOON_DAYS = 30, 90
ACCESS_REVIEW_IDLE = 0.2  # share of an AD group not signed in that calls for a review


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


RULES = {
    "business": f"Business fit is high when at least {_pct(BUSINESS_ACTIVE_SHARE)} of the "
                f"licensed users were active in the last {ACTIVE_WINDOW_DAYS} days, and at "
                f"least {BUSINESS_MIN_USERS} people use it",
    "technical": f"Technical fit starts at 100: minus {SUPPORT_SOON_PENALTY} if vendor support "
                 f"ends within {SUPPORT_SOON_MONTHS} months (or has ended), minus "
                 f"{SUPPORT_LATER_PENALTY} within {SUPPORT_LATER_MONTHS} months, minus "
                 f"{FINDING_PENALTY} per open security finding (up to {FINDING_PENALTY_CAP}), "
                 f"minus {ON_PREM_PENALTY} if on-premises; high at {TECHNICAL_HIGH} or more",
    "overlap": "Overlap is the share of the app's capabilities the PLM platform already "
               f"provides; {_pct(OVERLAP_HIGH)} or more is high",
    "time": "High overlap: Migrate if people use it, else Eliminate. Otherwise, by fit: "
            "Invest (both high), Migrate (business high, technical low), Tolerate (business "
            "low, technical high), Eliminate (both low)",
    "over": f"Over-licensed: under {_pct(UNDER_USED)} of the entitlement used; spare seats are "
            f"those above the {ACTIVE_WINDOW_DAYS}-day peak plus {_pct(HEADROOM)} headroom",
    "trueup": "True-up exposure: named users above the entitlement, at the unit cost plus any "
              "checked contract premium",
    "capacity": f"Near capacity: {_pct(NEAR_CAPACITY)} or more of the entitlement used",
    "access": f"Access review: {_pct(ACCESS_REVIEW_IDLE)} or more of an access group's enabled "
              f"accounts have not signed in to the domain in {ACTIVE_WINDOW_DAYS} days; any "
              "disabled account still in the group is flagged",
    "notice": "Notice deadline: renewal date minus the checked notice period; passed, within "
              f"{NOTICE_URGENT_DAYS} days, or within {NOTICE_SOON_DAYS} days",
}


@dataclass
class App:
    key: str
    name: str
    vendor: str
    category: str
    business_unit: str
    capabilities: list[str]
    users_licensed: int
    active_users_90d: int
    annual_cost_k: float
    support_end: date | None
    hosting: str
    open_security_findings: int
    integrations: int
    owner: str
    ad_group: str = ""  # DN of the AD access group, for legacy apps
    active_source: str = ""  # where active users comes from; "" = no app-level source


@dataclass
class AppAssessment:
    app: App
    usage: float
    business_high: bool
    technical: int
    technical_high: bool
    overlap: float
    shared: list[str]
    proposal: str
    why: list[str]
    flags: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # field -> where the number came from

    @property
    def business(self) -> int:
        return round(100 * self.usage)


def assess_app(app: App, platform: list[str], as_of: date) -> AppAssessment:
    usage = app.active_users_90d / app.users_licensed if app.users_licensed else 0.0
    business_high = usage >= BUSINESS_ACTIVE_SHARE and app.active_users_90d >= BUSINESS_MIN_USERS
    technical, why = 100, []
    flags = []
    if app.support_end:
        months = (app.support_end - as_of).days / 30.4
        if months <= SUPPORT_SOON_MONTHS:
            technical -= SUPPORT_SOON_PENALTY
            flags.append(f"vendor support {'ended' if months < 0 else 'ends'} "
                         f"{app.support_end:%b %d, %Y}")
        elif months <= SUPPORT_LATER_MONTHS:
            technical -= SUPPORT_LATER_PENALTY
            flags.append(f"vendor support ends {app.support_end:%b %d, %Y}")
    if app.open_security_findings:
        technical -= min(FINDING_PENALTY_CAP, FINDING_PENALTY * app.open_security_findings)
        flags.append(f"{app.open_security_findings} open security finding"
                     f"{'' if app.open_security_findings == 1 else 's'}")
    if app.hosting == "on-prem":
        technical -= ON_PREM_PENALTY
    technical = max(technical, 0)
    technical_high = technical >= TECHNICAL_HIGH
    platform_set = {c.lower() for c in platform}
    shared = [c for c in app.capabilities if c.lower() in platform_set]
    overlap = len(shared) / len(app.capabilities) if app.capabilities else 0.0
    if overlap >= OVERLAP_HIGH:
        proposal = "Migrate" if business_high else "Eliminate"
        why.append(f"{round(100 * overlap)}% of its capabilities are in the PLM platform "
                   f"({', '.join(shared)})")
        why.append(f"{app.active_users_90d} of {app.users_licensed} licensed users active "
                   f"({round(100 * usage)}%): " + ("move them to the platform" if business_high
                                                   else "few would need to move"))
    else:
        proposal = {(True, True): "Invest", (True, False): "Migrate",
                    (False, True): "Tolerate", (False, False): "Eliminate"}[
            (business_high, technical_high)]
        why.append(f"business fit {'high' if business_high else 'low'}: "
                   f"{app.active_users_90d} of {app.users_licensed} users active "
                   f"({round(100 * usage)}%)")
        why.append(f"technical fit {'high' if technical_high else 'low'}: score {technical}"
                   + (f" ({'; '.join(flags)})" if flags else ""))
    return AppAssessment(app, usage, business_high, technical, technical_high, overlap, shared,
                         proposal, why, flags)


# ---------- licenses ----------

@dataclass
class License:
    key: str
    product: str
    vendor: str
    model: str  # concurrent | named | token
    entitlement: int
    peak_90d: int
    active_named_90d: int
    unit_cost_k: float
    renewal_date: date
    contract: str


@dataclass
class Terms:
    """Checked contract terms; None where the contract has no checked value."""
    end_date: date | None = None
    auto_renew: bool | None = None
    notice_days: int | None = None
    escalator_pct: float | None = None
    trueup_premium_pct: float | None = None


@dataclass
class LicenseAssessment:
    lic: License
    used: int  # seats in use by the measure that matters for the model
    utilization: float
    spare: int
    savings_k: float
    trueup_users: int
    trueup_k: float
    near_capacity: bool
    notice_deadline: date | None
    notice_state: str  # passed | urgent | soon | ok | unknown | no auto-renewal
    escalation_k: float
    terms: Terms
    notes: list[str] = field(default_factory=list)


def assess_license(lic: License, terms: Terms | None, as_of: date) -> LicenseAssessment:
    terms = terms or Terms()
    used = lic.peak_90d if lic.model in ("concurrent", "token") else lic.active_named_90d
    util = used / lic.entitlement if lic.entitlement else 0.0
    spare, savings = 0, 0.0
    if util < UNDER_USED:
        spare = max(0, lic.entitlement - math.ceil(round(used * (1 + HEADROOM), 6)))
        savings = round(spare * lic.unit_cost_k, 1)
    trueup_users = max(0, lic.active_named_90d - lic.entitlement) if lic.model == "named" else 0
    premium = (terms.trueup_premium_pct or 0) / 100
    trueup = round(trueup_users * lic.unit_cost_k * (1 + premium), 1)
    notes = []
    if terms.end_date and terms.end_date != lic.renewal_date:
        notes.append(f"the contract says the term ends {terms.end_date:%b %d, %Y}, but the "
                     f"license record says {lic.renewal_date:%b %d, %Y}")
    renewal = terms.end_date or lic.renewal_date
    deadline, state = None, "unknown"
    if terms.auto_renew is False:
        state = "no auto-renewal"
    elif terms.notice_days is not None:
        deadline = renewal - timedelta(days=terms.notice_days)
        days = (deadline - as_of).days
        state = ("passed" if days < 0 else "urgent" if days <= NOTICE_URGENT_DAYS
                 else "soon" if days <= NOTICE_SOON_DAYS
                 else "ok")
    annual = lic.entitlement * lic.unit_cost_k
    escalation = round(annual * (terms.escalator_pct or 0) / 100, 1)
    return LicenseAssessment(lic, used, util, spare, savings, trueup_users, trueup,
                             util >= NEAR_CAPACITY, deadline, state, escalation, terms, notes)
