"""The inventory, contract readings, and decisions.

Contract terms come from the model, but a term is used only if code confirms it: the quote
must appear word for word in the contract, a date must appear in the quote as written, and
every number must appear in its quote. Unchecked terms are shown, flagged, and ignored by
the rules. A person decides each app's future; Migrate and Eliminate decisions can be sent
to Backlog Pilot as retirement work.
"""

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, select

from app_portfolio.db import audit, utcnow
from app_portfolio.llm.prompts import contract_message
from app_portfolio.models import ContractTerms, Term
from app_portfolio.rules import (
    ACCESS_REVIEW_IDLE,
    ACTIVE_WINDOW_DAYS,
    TIME,
    App,
    AppAssessment,
    License,
    LicenseAssessment,
    Terms,
    assess_app,
    assess_license,
)

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
NUMERIC = ("notice_days", "escalator_pct", "trueup_premium_pct")
TERM_NAMES = {"end_date": "Term ends", "auto_renew": "Renews automatically",
              "notice_days": "Notice to stop renewal (days)",
              "escalator_pct": "Renewal increase (%)",
              "trueup_premium_pct": "True-up premium (%)", "termination": "Ending early",
              "data_export": "Getting the data out"}


class PortfolioError(ValueError):
    """Invalid input or decision; the message is user-facing."""


class AppRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    data: str  # JSON of the inventory row


class LicenseRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    data: str


class Contract(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # file name
    text: str


class Reading(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    contract: str = Field(index=True)
    input_text: str
    output: str
    drafted_by: str
    requested_by: str
    created_at: datetime = Field(default_factory=utcnow)


class DirectoryCount(SQLModel, table=True):
    """Counts from the app's AD access group (never names)."""
    id: int | None = Field(default=None, primary_key=True)
    app: str = Field(index=True)
    group_dn: str
    entitled: int
    active: int
    disabled: int
    nested_groups: int
    missing: int
    source: str  # the directory it came from
    synced_by: str
    synced_at: datetime = Field(default_factory=utcnow)


class Decision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    app: str = Field(index=True)
    decision: str
    reason: str
    decided_by: str
    sent_to_backlog: int | None = None  # Backlog Pilot inbox item
    at: datetime = Field(default_factory=utcnow)


# ---------- checking contract terms ----------

# A zero is never written as a number; accept it only when the quote says there is none.
NONE_STATED = re.compile(r"\bno\b|\bnot\b|\bwithout\b|at the contracted (unit )?(rate|price)")


def _norm(s: str) -> str:
    return " ".join(s.replace("**", "").split()).lower()


@dataclass
class CheckedTerm:
    name: str
    term: Term | None
    ok: bool
    problem: str = ""


def check_term(name: str, term: Term | None, contract_text: str) -> CheckedTerm:
    if term is None:
        return CheckedTerm(name, None, False, "Not stated in the contract.")
    quote, value = _norm(term.quote), term.value.strip()
    if len(quote) < 10 or quote not in _norm(contract_text):
        return CheckedTerm(name, term, False, "The quote is not in the contract word for word.")
    if name == "end_date":
        try:
            d = date.fromisoformat(value)
        except ValueError:
            return CheckedTerm(name, term, False, f"'{value}' is not a date (YYYY-MM-DD).")
        if _norm(f"{MONTHS[d.month - 1]} {d.day}, {d.year}") not in quote:
            return CheckedTerm(name, term, False, f"{d:%B %d, %Y} is not what the quote says.")
    elif name == "auto_renew":
        if value.lower() not in ("yes", "no") or "renew" not in quote:
            return CheckedTerm(name, term, False, "The quote does not say whether it renews.")
        if value.lower() == "no" and not re.search(r"not renew|unless|without renewal", quote):
            return CheckedTerm(name, term, False, "The quote does not say it stops.")
    elif name in NUMERIC:
        number = re.sub(r"[^\d.]", "", value)
        if number and float(number) == 0 and NONE_STATED.search(quote):
            return CheckedTerm(name, term, True)  # "no true-up", "at the contracted unit rate"
        if not number or not re.search(rf"(?<![\d.]){re.escape(number)}(?![\d.])", quote):
            return CheckedTerm(name, term, False, f"{value} is not in the quote.")
    return CheckedTerm(name, term, True)


def check_terms(terms: ContractTerms, contract_text: str) -> list[CheckedTerm]:
    return [check_term(n, getattr(terms, n), contract_text) for n in TERM_NAMES]


def to_terms(checked: list[CheckedTerm]) -> Terms:
    """Only checked values reach the rules."""
    ok = {c.name: c.term.value for c in checked if c.ok and c.term}
    return Terms(
        end_date=date.fromisoformat(ok["end_date"]) if "end_date" in ok else None,
        auto_renew={"yes": True, "no": False}.get(ok.get("auto_renew", "").lower()),
        notice_days=int(float(ok["notice_days"])) if "notice_days" in ok else None,
        escalator_pct=float(ok["escalator_pct"]) if "escalator_pct" in ok else None,
        trueup_premium_pct=float(ok["trueup_premium_pct"]) if "trueup_premium_pct" in ok
        else None)


# ---------- store ----------

def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def app_from(row: dict) -> App:
    return App(row["key"], row["name"], row["vendor"], row["category"], row["business_unit"],
               [c.strip() for c in row["capabilities"].split(";") if c.strip()],
               int(row["users_licensed"]), int(row["active_users_90d"]),
               float(row["annual_cost_k"]), _date(row["support_end"]), row["hosting"],
               int(row["open_security_findings"]), int(row["integrations"]), row["owner"],
               row.get("ad_group", "") or "", row.get("active_source", "") or "")


def license_from(row: dict) -> License:
    return License(row["key"], row["product"], row["vendor"], row["model"],
                   int(row["entitlement"]), int(row["peak_90d"]), int(row["active_named_90d"]),
                   float(row["unit_cost_k"]), date.fromisoformat(row["renewal_date"]),
                   row["contract"])


@dataclass
class ContractView:
    contract: Contract
    reading: Reading | None
    checked: list[CheckedTerm] = field(default_factory=list)
    terms: ContractTerms | None = None

    @property
    def flagged(self) -> int:
        return sum(1 for c in self.checked if not c.ok and c.term is not None)


class PortfolioStore:
    def __init__(self, engine: Engine, dataset_dir: Path):
        self.engine = engine
        meta = json.loads((dataset_dir / "platform.json").read_text())
        self.platform: list[str] = meta["capabilities"]
        self.as_of = date.fromisoformat(meta["as_of"])

    def seed_if_empty(self, dataset_dir: Path, actor: str) -> None:
        with Session(self.engine) as s:
            if s.exec(select(AppRow)).first() is not None:
                return
            for r in csv.DictReader(io.StringIO((dataset_dir / "apps.csv").read_text())):
                s.add(AppRow(key=r["key"], data=json.dumps(r)))
            for r in csv.DictReader(io.StringIO((dataset_dir / "licenses.csv").read_text())):
                s.add(LicenseRow(key=r["key"], data=json.dumps(r)))
            for path in sorted((dataset_dir / "contracts").glob("*.md")):
                s.add(Contract(name=path.name, text=path.read_text()))
            audit(s, actor, "inventory_loaded", "demo inventory, licenses, and contracts")
            s.commit()

    # apps
    def apps(self) -> list[AppAssessment]:
        with Session(self.engine) as s:
            rows = s.exec(select(AppRow).order_by(AppRow.key)).all()
        counts = self.directory_counts()
        out = []
        for r in rows:
            app = app_from(json.loads(r.data))
            sources = {"licensed": "inventory", "active": app.active_source or "inventory"}
            count = counts.get(app.key)
            if count is not None:
                # the directory is authoritative for who has access
                app.users_licensed = count.entitled
                sources["licensed"] = (f"AD group {group_name(count.group_dn)} "
                                       f"({count.synced_at:%Y-%m-%d})")
                if not app.active_source:  # nothing better: the domain sign-in proxy
                    app.active_users_90d = count.active
                    sources["active"] = ("domain sign-ins (proxy: signed in to the domain, "
                                         "not necessarily this app)")
            a = assess_app(app, self.platform, self.as_of)
            a.sources = sources
            if count is not None:
                if count.disabled:
                    a.flags.append(f"{count.disabled} disabled account"
                                   f"{'' if count.disabled == 1 else 's'} still in the access "
                                   "group")
                idle = count.entitled - count.active
                if count.entitled and idle / count.entitled >= ACCESS_REVIEW_IDLE:
                    a.flags.append(f"access review: {idle} of {count.entitled} entitled "
                                   "accounts have not signed in to the domain in "
                                   f"{ACTIVE_WINDOW_DAYS} days")
            out.append(a)
        return out

    # directory
    def directory_counts(self) -> dict[str, "DirectoryCount"]:
        with Session(self.engine) as s:
            rows = s.exec(select(DirectoryCount).order_by(DirectoryCount.id)).all()
        return {c.app: c for c in rows}  # latest per app

    def sync_directory(self, conn, source: str, actor: str) -> tuple[int, list[str]]:
        """Count every mapped app's AD group. Returns (apps synced, problems)."""
        from app_portfolio.directory import DirectoryError, count_group

        synced, problems = 0, []
        with Session(self.engine) as s:
            for r in s.exec(select(AppRow).order_by(AppRow.key)).all():
                app = app_from(json.loads(r.data))
                if not app.ad_group:
                    continue
                try:
                    g = count_group(conn, app.ad_group, self.as_of, ACTIVE_WINDOW_DAYS)
                except DirectoryError as e:
                    problems.append(f"{app.key}: {e}")
                    continue
                s.add(DirectoryCount(app=app.key, group_dn=app.ad_group, entitled=g.entitled,
                                     active=g.active, disabled=g.disabled,
                                     nested_groups=g.nested_groups, missing=g.missing,
                                     source=source, synced_by=actor))
                synced += 1
            audit(s, actor, "directory_synced",
                  f"{source}: {synced} access groups counted"
                  + (f"; {len(problems)} problems" if problems else ""))
            s.commit()
        return synced, problems

    def app(self, key: str) -> AppAssessment | None:
        return next((a for a in self.apps() if a.app.key == key), None)

    def decisions(self) -> dict[str, Decision]:
        with Session(self.engine) as s:
            rows = s.exec(select(Decision).order_by(Decision.id)).all()
        return {d.app: d for d in rows}  # latest per app

    def decide(self, key: str, decision: str, reason: str, actor: str) -> Decision:
        if decision not in TIME:
            raise PortfolioError("Choose Invest, Tolerate, Migrate, or Eliminate.")
        a = self.app(key)
        if a is None:
            raise PortfolioError("That app is not in the inventory.")
        if decision != a.proposal and not reason.strip():
            raise PortfolioError(f"The rules propose {a.proposal}. Say why you chose "
                                 f"{decision}.")
        d = Decision(app=key, decision=decision, reason=reason.strip(), decided_by=actor)
        with Session(self.engine) as s:
            s.add(d)
            audit(s, actor, "app_decided",
                  f"{key} {a.app.name}: {decision} (rules proposed {a.proposal})"
                  + (f": {reason.strip()}" if reason.strip() else ""))
            s.commit()
            s.refresh(d)
        return d

    def mark_sent(self, decision_id: int, item_id: int, actor: str) -> None:
        with Session(self.engine) as s:
            d = s.get(Decision, decision_id)
            d.sent_to_backlog = item_id
            s.add(d)
            audit(s, actor, "app_sent_to_backlog", f"{d.app} {d.decision}: inbox item {item_id}")
            s.commit()

    # contracts
    def contract(self, name: str) -> Contract | None:
        with Session(self.engine) as s:
            return s.exec(select(Contract).where(Contract.name == name)).first()

    def contracts(self) -> list[ContractView]:
        with Session(self.engine) as s:
            rows = s.exec(select(Contract).order_by(Contract.name)).all()
        return [self.contract_view(c) for c in rows]

    def contract_view(self, c: Contract) -> ContractView:
        with Session(self.engine) as s:
            r = s.exec(select(Reading).where(Reading.contract == c.name)
                       .order_by(Reading.id.desc())).first()
        if r is None:
            return ContractView(c, None)
        terms = ContractTerms.model_validate_json(r.output)
        return ContractView(c, r, check_terms(terms, c.text), terms)

    def save_reading(self, c: Contract, input_text: str, terms: ContractTerms, actor: str,
                     drafted_by: str) -> Reading:
        r = Reading(contract=c.name, input_text=input_text, output=terms.model_dump_json(),
                    drafted_by=drafted_by, requested_by=actor)
        checked = check_terms(terms, c.text)
        with Session(self.engine) as s:
            s.add(r)
            audit(s, actor, "contract_read",
                  f"{c.name} ({drafted_by}): {sum(x.ok for x in checked)} terms checked, "
                  f"{sum(1 for x in checked if not x.ok and x.term)} flagged")
            s.commit()
            s.refresh(r)
        return r

    # licenses
    def licenses(self) -> list[LicenseAssessment]:
        with Session(self.engine) as s:
            rows = s.exec(select(LicenseRow).order_by(LicenseRow.key)).all()
        views = {v.contract.name: v for v in self.contracts()}
        out = []
        for r in rows:
            lic = license_from(json.loads(r.data))
            v = views.get(lic.contract)
            terms = to_terms(v.checked) if v and v.reading else None
            out.append(assess_license(lic, terms, self.as_of))
        return out


def group_name(dn: str) -> str:
    """'CN=GG-Vaultline-Users,OU=Groups,...' -> 'GG-Vaultline-Users'."""
    first = dn.split(",", 1)[0]
    return first.split("=", 1)[1] if "=" in first else dn


def reading_input(c: Contract) -> str:
    return contract_message(c.name, c.text)
