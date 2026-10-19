import json
from dataclasses import replace
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app_portfolio.app import create_app
from app_portfolio.config import load_settings
from app_portfolio.db import make_engine
from app_portfolio.llm.replay import ReplayProvider
from app_portfolio.models import ContractTerms, Term
from app_portfolio.portfolio import check_term, check_terms, reading_input, to_terms
from app_portfolio.record_demos import demo_contracts
from app_portfolio.rules import App, License, Terms, assess_app, assess_license
from app_portfolio.suite import SuiteClient, SuiteSettings

AS_OF = date(2026, 10, 1)
PLATFORM = ["part management", "document management", "engineering change"]
TEXT = ("The term ends January 31, 2027. It renews automatically for twelve (12) months unless "
        "either party gives notice at least one hundred twenty (120) days before. Fees "
        "increase by five percent (5%).")


def app(**kw):
    base = dict(key="APP-99", name="X", vendor="V", category="C", business_unit="U",
                capabilities=["document management", "engineering change"], users_licensed=100,
                active_users_90d=80, annual_cost_k=50.0, support_end=None, hosting="SaaS",
                open_security_findings=0, integrations=1, owner="O")
    return App(**(base | kw))


def test_time_rules():
    assert assess_app(app(), PLATFORM, AS_OF).proposal == "Migrate"  # used, fully overlapping
    assert assess_app(app(active_users_90d=10), PLATFORM, AS_OF).proposal == "Eliminate"
    unique = ["simulation"]
    assert assess_app(app(capabilities=unique), PLATFORM, AS_OF).proposal == "Invest"
    old = assess_app(app(capabilities=unique, support_end=date(2027, 1, 31)), PLATFORM, AS_OF)
    assert old.proposal == "Migrate" and old.technical == 40 and "support ends" in old.flags[0]
    assert assess_app(app(capabilities=unique, active_users_90d=5), PLATFORM,
                      AS_OF).proposal == "Tolerate"


def test_license_rules():
    lic = License("LIC-9", "P", "V", "named", 100, 60, 112, 2.0, date(2026, 12, 15), "c.md")
    r = assess_license(lic, Terms(notice_days=60, escalator_pct=6, trueup_premium_pct=15), AS_OF)
    assert r.trueup_users == 12 and r.trueup_k == 27.6  # 12 x 2.0 x 1.15
    assert r.notice_deadline == date(2026, 10, 16) and r.notice_state == "urgent"
    assert r.escalation_k == 12.0
    over = assess_license(replace(lic, model="concurrent", peak_90d=50), None, AS_OF)
    assert over.spare == 45 and over.savings_k == 90.0 and over.notice_state == "unknown"
    gone = assess_license(lic, Terms(notice_days=90, end_date=date(2026, 11, 30)), AS_OF)
    assert gone.notice_state == "passed" and "contract says" in gone.notes[0]


def test_term_checks():
    ok = check_term("notice_days", Term(value="120", quote="notice at least one hundred twenty "
                                                          "(120) days before"), TEXT)
    assert ok.ok
    wrong = check_term("notice_days", Term(value="90", quote="notice at least one hundred "
                                                             "twenty (120) days before"), TEXT)
    assert not wrong.ok and "not in the quote" in wrong.problem
    invented = check_term("escalator_pct", Term(value="5", quote="prices rise 5% each year"), TEXT)
    assert "not in the contract" in invented.problem
    date_ok = check_term("end_date", Term(value="2027-01-31", quote="The term ends January 31, "
                                                                     "2027."), TEXT)
    date_bad = check_term("end_date", Term(value="2027-02-28", quote="The term ends January 31, "
                                                                      "2027."), TEXT)
    assert date_ok.ok and not date_bad.ok
    terms = ContractTerms(end_date=None, auto_renew=Term(value="yes", quote="It renews "
                          "automatically for twelve (12) months"), notice_days=wrong.term,
                          escalator_pct=Term(value="5", quote="Fees increase by five percent "
                                                              "(5%)."),
                          trueup_premium_pct=None, termination=None, data_export=None,
                          watch_outs=[])
    t = to_terms(check_terms(terms, TEXT))
    assert t.auto_renew is True and t.escalator_pct == 5.0
    assert t.notice_days is None  # the wrong number never reaches the rules


def test_a_zero_needs_the_quote_to_say_there_is_none():
    text = ("Named users above the licensed quantity are invoiced quarterly at the contracted "
            "unit rate. Fees increase by three percent (3%).")
    none = check_term("trueup_premium_pct", Term(value="0", quote="Named users above the licensed "
                      "quantity are invoiced quarterly at the contracted unit rate."), text)
    assert none.ok
    guessed = check_term("trueup_premium_pct", Term(value="0", quote="Fees increase by three "
                         "percent (3%)."), text)
    assert not guessed.ok


class Reader:
    name = "stub"

    def read_contract(self, text):
        return ContractTerms(
            end_date=Term(value="2026-11-30", quote="Support for Vaultline Classic is provided "
                                                    "through November 30, 2026."),
            auto_renew=Term(value="yes", quote="This agreement renews automatically for an "
                                               "additional twelve (12) months"),
            notice_days=Term(value="90", quote="at least ninety (90) days prior to the end of "
                                               "the current term"),
            escalator_pct=Term(value="10", quote="increase by eight percent (8%)"),
            trueup_premium_pct=None, termination=None, data_export=None,
            watch_outs=["The notice window has closed."])


@pytest.fixture
def client(tmp_path):
    settings = replace(load_settings(), db_path=str(tmp_path / "t.db"))
    sent = []
    suite = SuiteSettings(backlog_url="http://bp", token="t", public_url="http://ap")
    transport = httpx.MockTransport(lambda r: sent.append(json.loads(r.content))
                                    or httpx.Response(201, json={"id": 3}))
    c = TestClient(create_app(settings, engine=make_engine(settings.db_path), provider=Reader(),
                              suite=suite, suite_client=SuiteClient(suite, transport)))
    c.sent = sent
    return c


def test_reading_feeds_deadlines_only_with_checked_terms(client):
    assert "not read yet" in client.get("/contracts").text
    page = client.post("/contracts/ardent.md/read", follow_redirects=True).text
    assert "1 flagged" in page and "10 is not in the quote" in page
    licenses = client.get("/licenses").text
    row = licenses.split("Vaultline Classic")[1].split("</tr>")[0]
    assert "Sep 01, 2026" in row and "passed: renews automatically" in row
    assert "+10%" not in licenses  # the unchecked escalator is not used
    client.cookies.set("ap_user", "eng")
    assert client.post("/contracts/ardent.md/read").status_code == 403


def test_decide_and_send_retirement_work(client):
    page = client.post("/apps/APP-02/decide", data={"decision": "Tolerate"}).text
    assert "Say why you chose Tolerate" in page
    client.post("/apps/APP-02/decide", data={"decision": "Eliminate"})
    page = client.post("/apps/APP-02/send").text
    assert "Sent to Backlog Pilot" in page and client.sent[0]["title"] == "Retire ChangeDesk"
    assert "in backlog" in client.get("/").text
    assert "app_decided" in client.get("/audit").text


def test_offline_demo_has_the_contract_readings():
    settings = load_settings()
    replay = ReplayProvider(settings.replay_dir)
    for c in demo_contracts(settings):
        terms = replay.read_contract(reading_input(c))
        flagged = [x.name for x in check_terms(terms, c.text) if x.term and not x.ok]
        assert not flagged, (c.name, flagged)


def test_flags_keep_the_case_of_dates_and_names(client):
    page = client.get("/apps/APP-04").text
    assert "Vendor support ends Dec 31, 2026" in page  # not "dec 31" (Jinja's capitalize)
