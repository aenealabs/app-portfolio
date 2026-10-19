"""The Help reference: rules, checks, and settings, built from the code that uses them.

Thresholds come from rules.py, contract checks from portfolio.py, and directory limits from
directory.py, so the reference cannot say something the app does not do. SETTINGS documents
every environment setting; a test fails if the code reads one that is not listed here.
"""

from mission_control import ReferenceSection

from app_portfolio import rules as r
from app_portfolio.directory import ACCOUNTDISABLE
from app_portfolio.portfolio import NUMERIC, TERM_NAMES

SETTINGS = {
    "AP_DB_PATH": "Where the app keeps its database (SQLite file).",
    "AP_LLM_PROVIDER": "replay (offline demo, recorded readings), anthropic (Claude API), or "
                       "foundry (Claude on Microsoft Foundry).",
    "AP_MODEL": "The Claude model that reads contracts.",
    "AP_RECORD": "true to save live readings as recordings for the offline demo.",
    "ANTHROPIC_API_KEY": "Claude API key, when AP_LLM_PROVIDER=anthropic (or use workload "
                         "identity federation instead of a key).",
    "ANTHROPIC_FOUNDRY_API_KEY": "Key for Claude on Microsoft Foundry; without it, Azure sign-in "
                                 "(managed identity) is used.",
    "AP_AUTH": "demo (pick a fictional person) or oidc (single sign-on).",
    "AP_OIDC_METADATA_URL": "Your identity provider's OpenID Connect metadata address.",
    "AP_OIDC_CLIENT_ID": "The app registration's client ID.",
    "AP_OIDC_CLIENT_SECRET": "The app registration's client secret.",
    "AP_SESSION_SECRET": "A long random value that signs the sign-in cookie.",
    "AP_SESSION_HTTPS_ONLY": "false only for local testing over plain http.",
    "AP_APPROVER_ROLE": "The app role that makes someone an approver.",
    "AP_APPROVER_EMAILS": "Comma-separated emails that are approvers even without the role.",
    "AP_BACKLOG_URL": "Backlog Pilot's address, to send retirement work to its inbox.",
    "AP_LEADERSHIP_URL": "Leadership Pilot's address (older single-link menu).",
    "AP_SUITE_TOKEN": "The shared Mission Control token; the same value as BP_SUITE_TOKEN.",
    "AP_PUBLIC_URL": "This app's own address, so items sent to the inbox link back here.",
    "AP_LDAP_URL": "The directory to read, ldaps://host:636. Unset: the demo directory.",
    "AP_LDAP_BIND_DN": "The read-only service account's distinguished name.",
    "AP_LDAP_PASSWORD": "The service account's password.",
    "AP_LDAP_ALLOW_INSECURE": "true to allow plain ldap:// (lab directories only).",
    "MISSION_CONTROL_APPS": "The suite's apps and addresses, the same in every app.",
}

CHECKS = [
    ("Quote", "Must appear in the contract word for word (spacing, case, and Markdown bold "
              "ignored) and be at least 10 characters."),
    (TERM_NAMES["end_date"], "A real date, written in the quote the way contracts write it "
                             "(for example, January 31, 2027)."),
    (TERM_NAMES["auto_renew"], "Yes or no, from a quote that mentions renewal; \"no\" also needs "
                               "the quote to say it does not renew."),
    (", ".join(TERM_NAMES[n] for n in NUMERIC),
     "The number must appear in the quote. Zero is never written as a number, so 0 is accepted "
     "only when the quote says there is none (\"no true-up\", \"at the contracted unit rate\")."),
    ("Anything that fails", "Shown with the reason and a flag, and not used by the rules."),
]


def reference() -> list[ReferenceSection]:
    pct = r._pct
    return [
        ReferenceSection("Rules", [(k.replace("trueup", "true-up").capitalize(), v + ".")
                                   for k, v in r.RULES.items()],
                         intro="Every proposal and flag shows the rule and the numbers behind it."),
        ReferenceSection("Thresholds", [
            ("Active", f"Used in the last {r.ACTIVE_WINDOW_DAYS} days"),
            ("High business fit", f"{pct(r.BUSINESS_ACTIVE_SHARE)} of licensed users active, "
                                  f"and at least {r.BUSINESS_MIN_USERS}"),
            ("High technical fit", f"Score of {r.TECHNICAL_HIGH} or more (out of 100)"),
            ("High overlap", f"{pct(r.OVERLAP_HIGH)} of capabilities in the PLM platform"),
            ("Spare seats", f"Under {pct(r.UNDER_USED)} used; keep the peak plus "
                            f"{pct(r.HEADROOM)}"),
            ("Near capacity", f"{pct(r.NEAR_CAPACITY)} of the entitlement in use"),
            ("Notice deadline urgency", f"Within {r.NOTICE_URGENT_DAYS} days: urgent; within "
                                        f"{r.NOTICE_SOON_DAYS}: soon"),
            ("Access review", f"{pct(r.ACCESS_REVIEW_IDLE)} of an access group idle"),
        ], columns=("Threshold", "Value")),
        ReferenceSection("Contract checks", CHECKS, columns=("Term", "What code checks"),
                         intro="The AI reads each contract and quotes its source for every "
                               "term. A term is used only if it passes these checks."),
        ReferenceSection("Directory (LDAP)", [
            ("Entitled", "Enabled user accounts in the access group, including nested groups; "
                         "computer accounts are skipped"),
            ("Disabled", f"userAccountControl flag 0x{ACCOUNTDISABLE:X} set"),
            ("Signed in", f"lastLogonTimestamp within {r.ACTIVE_WINDOW_DAYS} days; a domain "
                          "sign-in, not use of the app, and it can lag about 14 days"),
            ("Used for active users", "Only when the app has no audit log or license server"),
            ("Stored", "Counts only, never names; each sync is in the audit log"),
            ("Connection", "LDAPS only, read-only, one service account"),
        ], columns=("Item", "How it is counted")),
        ReferenceSection("Settings", sorted(SETTINGS.items()),
                         columns=("Setting", "What it does"),
                         intro="Environment settings (or a .env file next to the app)."),
    ]
