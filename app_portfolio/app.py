"""FastAPI web app: application rationalization, license intelligence, checked contract terms."""

import json
import re
from collections import Counter
from datetime import date
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from mission_control import STATIC_PATH, install, install_help
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app_portfolio import audit_search
from app_portfolio import rules as rule_values
from app_portfolio.auth import (
    AuthSettings,
    User,
    load_auth_settings,
    user_from_claims,
    user_from_session,
    user_to_session,
)
from app_portfolio.config import PACKAGE_DIR, Settings, load_settings
from app_portfolio.db import audit, make_engine
from app_portfolio.directory import (
    DirectoryError,
    DirectorySettings,
    connect,
    load_directory_settings,
)
from app_portfolio.help_reference import reference
from app_portfolio.llm import LLMError, LLMProvider, build_provider
from app_portfolio.portfolio import (
    TERM_NAMES,
    PortfolioError,
    PortfolioStore,
    group_name,
    reading_input,
)
from app_portfolio.rules import RULES, TIME
from app_portfolio.suite import SuiteClient, SuiteError, SuiteSettings, load_suite_settings

USER_COOKIE = "ap_user"
# Each screen's help button opens the guide section about it (checked at start-up).
PAGE_HELP = {
    "portfolio.html": "portfolio#reading-the-2x2",
    "app_detail.html": "portfolio#why-an-app-got-its-proposal",
    "licenses.html": "licenses#notice-deadlines",
    "contracts.html": "contracts#how-a-contract-is-read",
    "contract.html": "contracts#what-the-checks-catch",
    "directory.html": "directory#what-ldap-can-tell-you",
    "audit.html": "audit#what-is-recorded",
    "restricted.html": "overview#who-does-what",
}
ITEM_KEYS = re.compile(r"APP-\d+|LIC-\d+", re.IGNORECASE)


def money(k: float) -> str:
    return f"${k / 1000:,.2f}M" if abs(k) >= 1000 else f"${k:,.0f}K"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else many or one + 's'}"


def _highlight(value: str, terms: list[str]) -> Markup:
    escaped = str(escape(value))
    if not terms:
        return Markup(escaped)
    pattern = re.compile("|".join(re.escape(str(escape(t))) for t in terms), re.IGNORECASE)
    return Markup(pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped))


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def create_app(settings: Settings | None = None, engine: Engine | None = None,
               auth: AuthSettings | None = None, provider: LLMProvider | None = None,
               suite: SuiteSettings | None = None, suite_client: SuiteClient | None = None,
               directory: DirectorySettings | None = None) -> FastAPI:
    settings = settings or load_settings()
    directory = directory or load_directory_settings()
    directory_fixture = settings.dataset_dir / "directory.json"
    engine = engine or make_engine(settings.db_path)
    auth = auth or load_auth_settings()
    provider = provider or build_provider(settings)
    suite = suite or load_suite_settings()
    suite_client = suite_client or SuiteClient(suite)
    ai_label = ("AI reading (recorded demo)" if provider.name == "replay"
                else f"AI reading ({settings.model})")
    store = PortfolioStore(engine, settings.dataset_dir)
    store.seed_if_empty(settings.dataset_dir, "Demo inventory (seed)")
    users = [User(u["id"], u["name"], u["role"], u.get("approver", False))
             for u in json.loads(settings.users_path.read_text())["users"]]

    app = FastAPI(title="App Portfolio")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy",
                                    "camera=(), microphone=(), geolocation=()")
        return response

    if auth.mode == "oidc":
        _enable_oidc(app, auth)
    app.state.engine = engine
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.globals.update(users=users, auth_mode=auth.mode,
                                 provider_name=provider.name, rules=RULES, time_options=TIME,
                                 limits=rule_values,
                                 suite_connected=suite.connected, term_names=TERM_NAMES,
                                 as_of=store.as_of, group_name=group_name)
    install(app, templates, "App Portfolio", suite.apps)
    templates.env.filters.update(
        plural=plural, money=money, highlight_terms=_highlight, group_name=group_name,
        dict_without=lambda params, key: {k: v for k, v in params.items() if k != key})

    def current_user(request: Request) -> User:
        if auth.mode == "oidc":
            user = user_from_session(request.session.get("user"))
            return user or User("anonymous", "Signed out", "", False)
        wanted = request.cookies.get(USER_COOKIE)
        return next((u for u in users if u.id == wanted), users[0])

    def actor(request: Request) -> str:
        return current_user(request).actor

    def render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
        return templates.TemplateResponse(
            request, name, {"nav": name, "user": current_user(request), **context},
            status_code=status_code)

    install_help(app, templates, render, PACKAGE_DIR / "help", reference=reference,
                 page_help=PAGE_HELP)

    def restricted(request: Request, what: str) -> HTMLResponse | None:
        if current_user(request).approver:
            return None
        with Session(engine) as s:
            audit(s, actor(request), "access_denied", what)
            s.commit()
        return render(request, "restricted.html", status_code=403, what=what)

    # ---------- portfolio ----------

    def portfolio_view(request: Request, message: str = "", notice: str = "") -> HTMLResponse:
        apps = store.apps()
        decisions = store.decisions()
        by = Counter(decisions[a.app.key].decision if a.app.key in decisions else a.proposal
                     for a in apps)
        cost = {t: sum(a.app.annual_cost_k for a in apps
                       if (decisions[a.app.key].decision if a.app.key in decisions
                           else a.proposal) == t) for t in TIME}
        return render(request, "portfolio.html", apps=apps, decisions=decisions, by=by,
                      cost=cost, total=sum(a.app.annual_cost_k for a in apps),
                      platform=store.platform, message=message, notice=notice)

    @app.get("/", response_class=HTMLResponse)
    def portfolio(request: Request):
        return portfolio_view(request)

    def app_view(request: Request, key: str, message: str = "", notice: str = "",
                 status_code: int = 200) -> HTMLResponse:
        a = store.app(key)
        if a is None:
            return portfolio_view(request, message=f"{key} is not in the inventory.")
        return render(request, "app_detail.html", a=a, d=store.decisions().get(key),
                      platform=store.platform, message=message, notice=notice,
                      status_code=status_code)

    @app.get("/apps/{key}", response_class=HTMLResponse)
    def app_page(request: Request, key: str):
        return app_view(request, key.upper())

    @app.post("/apps/{key}/decide", response_class=HTMLResponse)
    def decide(request: Request, key: str, decision: str = Form(""), reason: str = Form("")):
        if (denied := restricted(request, "app decision")) is not None:
            return denied
        try:
            store.decide(key.upper(), decision, reason, actor(request))
        except PortfolioError as e:
            return app_view(request, key.upper(), str(e), status_code=422)
        return app_view(request, key.upper(), notice=f"Recorded: {decision}.")

    @app.post("/apps/{key}/send", response_class=HTMLResponse)
    def send(request: Request, key: str):
        if (denied := restricted(request, "send to Backlog Pilot")) is not None:
            return denied
        key = key.upper()
        a, d = store.app(key), store.decisions().get(key)
        if a is None or d is None or d.decision not in ("Migrate", "Eliminate"):
            return app_view(request, key, "Only a Migrate or Eliminate decision can be sent.")
        verb = "Retire" if d.decision == "Eliminate" else "Migrate users off"
        text = (f"{verb} {a.app.name} ({a.app.vendor}, {a.app.category}, {a.app.business_unit}). "
                f"Decision: {d.decision} by {d.decided_by}"
                + (f" ({d.reason})" if d.reason else "") + ". "
                + "; ".join(a.why) + (f". Flags: {'; '.join(a.flags)}" if a.flags else "")
                + f". Annual cost {money(a.app.annual_cost_k)}; {a.app.integrations} "
                  f"integrations to replace; owner {a.app.owner}.")
        try:
            item = suite_client.send(f"{verb} {a.app.name}", text, key, f"/apps/{key}",
                                     current_user(request).name)
        except SuiteError as e:
            return app_view(request, key, str(e))
        store.mark_sent(d.id, item, actor(request))
        return app_view(request, key, notice="Sent to Backlog Pilot's intake inbox.")

    # ---------- licenses and contracts ----------

    @app.get("/licenses", response_class=HTMLResponse)
    def licenses(request: Request):
        rows = store.licenses()
        calendar = sorted((r for r in rows if r.notice_deadline),
                          key=lambda r: r.notice_deadline)
        return render(request, "licenses.html", rows=rows, calendar=calendar,
                      savings=sum(r.savings_k for r in rows),
                      trueup=sum(r.trueup_k for r in rows),
                      escalation=sum(r.escalation_k for r in rows))

    def contract_view(request: Request, name: str, message: str = "",
                      status_code: int = 200) -> HTMLResponse:
        c = store.contract(name)
        if c is None:
            return render(request, "contracts.html", views=store.contracts(),
                          message=f"{name} is not a known contract.", status_code=404)
        return render(request, "contract.html", v=store.contract_view(c), message=message,
                      status_code=status_code)

    @app.get("/contracts", response_class=HTMLResponse)
    def contracts(request: Request):
        return render(request, "contracts.html", views=store.contracts(), message="")

    @app.get("/contracts/{name}", response_class=HTMLResponse)
    def contract_page(request: Request, name: str):
        return contract_view(request, name)

    @app.post("/contracts/{name}/read", response_class=HTMLResponse)
    def read_contract(request: Request, name: str):
        if (denied := restricted(request, "contract reading")) is not None:
            return denied
        c = store.contract(name)
        if c is None:
            return contract_view(request, name)
        text = reading_input(c)
        try:
            terms = provider.read_contract(text)
        except LLMError as e:
            return contract_view(request, name, str(e))
        store.save_reading(c, text, terms, actor(request), ai_label)
        return RedirectResponse(f"/contracts/{name}", status_code=303)

    # ---------- directory (legacy apps on Active Directory) ----------

    def directory_view(request: Request, message: str = "", notice: str = "",
                       status_code: int = 200) -> HTMLResponse:
        counts = store.directory_counts()
        mapped = [a for a in store.apps() if a.app.ad_group]
        return render(request, "directory.html", mapped=mapped, counts=counts,
                      directory=directory, message=message, notice=notice,
                      status_code=status_code)

    @app.get("/directory", response_class=HTMLResponse)
    def directory_page(request: Request):
        return directory_view(request)

    @app.post("/directory/sync", response_class=HTMLResponse)
    def directory_sync(request: Request):
        if (denied := restricted(request, "directory sync")) is not None:
            return denied
        try:
            conn = connect(directory, directory_fixture)
        except DirectoryError as e:
            return directory_view(request, str(e), status_code=502)
        source = directory.url if directory.live else "demo directory (fictional)"
        try:
            synced, problems = store.sync_directory(conn, source, actor(request))
        finally:
            conn.unbind()
        if problems:
            return directory_view(request, "; ".join(problems))
        return directory_view(request, notice=f"Counted {synced} access groups.")

    # ---------- audit, user ----------

    @app.get("/audit", response_class=HTMLResponse)
    def audit_log(request: Request, q: str = "", actor_filter: str = "", category: str = "",
                  item: str = "", since: str = "", until: str = "", page: int = 1):
        if (denied := restricted(request, "audit log")) is not None:
            return denied
        page_size = 50
        query = audit_search.AuditQuery(
            text=q, actor=actor_filter, categories=[category] if category else [],
            item_keys=[k.upper() for k in ITEM_KEYS.findall(item)],
            since=_parse_date(since), until=_parse_date(until))
        results = audit_search.search(engine, query, limit=page_size,
                                      offset=(max(page, 1) - 1) * page_size)
        return render(request, "audit.html", events=results.events, total=results.total,
                      page=max(page, 1), page_size=page_size, query=query, ask="",
                      plan=None, answer=None, cited=[], unverified=[], summary={},
                      message="", questions=[], people=audit_search.actors(engine),
                      categories=audit_search.CATEGORY_LABELS,
                      terms=[t for t in re.findall(r"\w+", query.text) if len(t) > 1])

    @app.post("/user")
    def switch_user(request: Request, user_id: str = Form(...)):
        back = urlparse(request.headers.get("referer", "")).path
        if not back.startswith("/") or back.startswith("//"):
            back = "/"
        response = RedirectResponse(back, status_code=303)
        if any(u.id == user_id for u in users):
            response.set_cookie(USER_COOKIE, user_id, httponly=True, samesite="lax")
        return response

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


PUBLIC_PATHS = ("/static", STATIC_PATH, "/login", "/auth/callback", "/logout", "/healthz")


def _enable_oidc(app: FastAPI, auth: AuthSettings) -> None:
    """Sign-in with Microsoft Entra ID (or any OpenID Connect provider)."""
    from authlib.integrations.starlette_client import OAuth
    from starlette.middleware.sessions import SessionMiddleware

    oauth = OAuth()
    oauth.register("oidc", server_metadata_url=auth.metadata_url, client_id=auth.client_id,
                   client_secret=auth.client_secret,
                   client_kwargs={"scope": "openid profile email"})

    @app.middleware("http")
    async def require_sign_in(request: Request, call_next):
        if request.url.path.startswith(PUBLIC_PATHS) or request.session.get("user"):
            return await call_next(request)
        if request.method == "GET" and "hx-request" not in request.headers:
            request.session["next"] = request.url.path  # a sign-in prompt, not a refusal
            return RedirectResponse("/login", status_code=303)
        with Session(request.app.state.engine) as s:  # an action tried without signing in
            audit(s, "not signed in", "access_denied",
                  f"{request.method} {request.url.path} from "
                  f"{request.client.host if request.client else 'unknown'}")
            s.commit()
        return HTMLResponse("Sign in required.", status_code=401)

    app.add_middleware(SessionMiddleware, secret_key=auth.session_secret, same_site="lax",
                       https_only=auth.https_only, max_age=8 * 3600)

    @app.get("/login")
    async def login(request: Request):
        return await oauth.oidc.authorize_redirect(request, request.url_for("auth_callback"))

    @app.get("/auth/callback", name="auth_callback")
    async def auth_callback(request: Request):
        try:
            token = await oauth.oidc.authorize_access_token(request)  # verifies the ID token
            user = user_from_claims(token["userinfo"], auth)
        except Exception as e:  # any failure (state, token, claims) is refused and audited
            with Session(request.app.state.engine) as s:
                audit(s, "not signed in", "sign_in_failed",
                      f"{type(e).__name__} from "
                      f"{request.client.host if request.client else 'unknown'}")
                s.commit()
            return HTMLResponse('Sign-in failed. <a href="/login">Try again</a>.',
                                status_code=401)
        request.session["user"] = user_to_session(user)
        with Session(request.app.state.engine) as s:
            audit(s, user.actor, "signed_in", user.email or user.id)
            s.commit()
        return RedirectResponse(request.session.pop("next", "/"), status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)


def main() -> None:
    import uvicorn

    uvicorn.run("app_portfolio.app:create_app", factory=True, host="127.0.0.1", port=8040)


if __name__ == "__main__":
    main()
