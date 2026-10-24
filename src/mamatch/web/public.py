"""Public pages: how it works, anonymised opportunities, intake, sign-in.

Only seller-approved, anonymised listing fields are ever shown here. Nothing about buyers is public.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, listing, offers, teaser
from ..buyers import new_token
from ..models import Buyer, Target, User
from ..taxonomy import BUYER_KINDS, DEAL_TYPES, REGIONS, SALE_REASONS, SECTORS
from .common import COOKIE, I, back, current_user, firm, get_lang, get_session, not_found, num, render

router = APIRouter()
PAGES = {"sell": "page_sell.html", "buy": "page_buy.html", "fees": "page_fees.html", "security": "page_security.html"}


def _home_for(user: User | None) -> str:
    return {"deal_manager": I, "seller": "/seller", "buyer": "/buyer"}.get(user.role if user else "", "/")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user: User | None = Depends(current_user), s: Session = Depends(get_session)):
    if getattr(request.state, "lang", None) is None:
        # The neutral homepage opens an edition: remembered switch choice, else the browser's language.
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"/{get_lang(request)}/{query}", status_code=302)
    rows = listing.public_board(s)[:3]
    return render(request, "home.html", user, portal="public", rows=rows, cards={t.id: listing.card(t) for t in rows})


SEARCH_KEYS = ("q", "revenue_min", "revenue_max", "employees_min", "employees_max", "years_min", "price_max",
               "profitable", "margin_min")


@router.get("/opportunities", response_class=HTMLResponse)
def opportunities(request: Request, sector: str = "", macro: str = "", user: User | None = Depends(current_user),
                  s: Session = Depends(get_session)):
    qp = request.query_params
    filters = {k: qp.get(k, "") for k in SEARCH_KEYS}
    filters["reasons"] = [r for r in qp.getlist("reasons") if r in SALE_REASONS]
    filters["deal_types"] = [d for d in qp.getlist("deal_types") if d in DEAL_TYPES]
    rows = listing.public_board(s, sector, macro, **filters)
    detailed = any(filters[k] for k in SEARCH_KEYS if k != "q") or filters["reasons"] or filters["deal_types"]
    return render(request, "listings.html", user, portal="public", rows=rows,
                  cards={t.id: listing.card(t) for t in rows}, sector=sector, macro=macro, f=filters,
                  detailed=detailed, total=len(listing.public_board(s)),
                  edges={"revenue": teaser.REVENUE_EDGES, "employees": teaser.EMPLOYEE_EDGES,
                         "years": teaser.YEARS_EDGES, "price": listing.PRICE_EDGES, "margin": listing.MARGIN_EDGES})


def _listed(s: Session, target_id: int) -> Target:
    t = s.get(Target, target_id)
    if t is None or t.visibility != "listed":
        not_found()
    return t


@router.get("/opportunities/{target_id}", response_class=HTMLResponse)
def opportunity(target_id: int, request: Request, user: User | None = Depends(current_user),
                s: Session = Depends(get_session)):
    t = _listed(s, target_id)
    requested = False
    if user and user.role == "buyer" and user.buyer_id:
        requested = any(m.buyer_id == user.buyer_id and m.stage != "dropped" for m in t.matches)
    return render(request, "listing.html", user, portal="public", t=t, card=listing.card(t), requested=requested)


@router.post("/opportunities/{target_id}/inquiry")
def opportunity_inquiry(target_id: int, s: Session = Depends(get_session), name: str = Form(""),
                        company: str = Form(""), kind: str = Form("private"), contact: str = Form(""),
                        message: str = Form(""), consent: str = Form("")):
    t = _listed(s, target_id)
    try:
        offers.public_inquiry(s, t, name=name, company=company, kind=kind if kind in BUYER_KINDS else "private",
                              contact=contact, message=message, consent=bool(consent))
    except ValueError as exc:
        return back(f"/opportunities/{t.id}#inquiry", str(exc))
    return back(f"/opportunities/{t.id}", "感谢您的咨询，顾问会尽快与您联系。Thank you: the adviser will contact you shortly.")


@router.post("/opportunities/{target_id}/request")
def opportunity_request(target_id: int, user: User | None = Depends(current_user), s: Session = Depends(get_session)):
    t = _listed(s, target_id)
    if user is None or user.role != "buyer" or not user.buyer_id:
        return back(f"/login?next=/opportunities/{t.id}", "请先以买方身份登录 Sign in as a buyer first.")
    try:
        m = offers.express_interest(s, t, s.get(Buyer, user.buyer_id))
    except ValueError as exc:
        return back(f"/opportunities/{t.id}", str(exc))
    auth.log(s, user, "introduction_request", target_id=t.id, match_id=m.id)
    return back("/buyer#deals", "已提交引荐申请，顾问审核后会通知您。Request sent; the adviser will review it.")


@router.post("/sell")
def seller_intake(s: Session = Depends(get_session), company: str = Form(""), name: str = Form(""),
                  contact: str = Form(""), sector: str = Form(""), province: str = Form(""),
                  revenue: str = Form(""), net_profit: str = Form(""), deal_type: str = Form("full_sale"),
                  sale_reason: str = Form("succession"), notes: str = Form(""), consent: str = Form("")):
    if not consent:
        return back("/sell#intake", "请同意顾问与您联系 Please agree to be contacted.")
    if not (company.strip() and name.strip() and contact.strip()):
        return back("/sell#intake", "请填写公司、姓名和联系方式 Company, name and contact are required.")
    try:
        rev, np_ = num(revenue), num(net_profit)
    except ValueError:
        return back("/sell#intake", "收入和利润请填写数字 Revenue and profit must be numbers.")
    t = Target(firm=firm(s), code_name="待定 New", legal_name=company.strip()[:200], contact_name=name.strip()[:50],
               contact_info=contact.strip()[:100], sector=sector if sector in SECTORS else "industrial_services",
               province=province if province in REGIONS else "上海", revenue=rev, net_profit=np_,
               deal_type=deal_type if deal_type in DEAL_TYPES else "full_sale",
               sale_reason=sale_reason if sale_reason in SALE_REASONS else "other",
               description=notes.strip()[:4000], seller_token=new_token(), status="draft")
    s.add(t)
    s.flush()
    t.code_name = f"Project {t.id:03d}"
    auth.log(s, None, "seller_intake", target_id=t.id)
    return back("/sell", "已收到，顾问会在一个工作日内与您联系。保密处理。Received. An adviser will call you within one business day, in confidence.")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "", user: User | None = Depends(current_user)):
    return render(request, "login.html", user, portal="public", next=next)


def _safe_next(nxt: str, user: User) -> str:
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else _home_for(user)


@router.post("/login")
def login(request: Request, s: Session = Depends(get_session), email: str = Form(""), password: str = Form(""),
          next: str = Form("")):
    user = auth.authenticate(s, email, password)
    if user is None:
        auth.log(s, None, "sign_in_failed", email=email.strip().lower()[:200])
        return back(f"/login?next={next}", "邮箱或密码不正确 Wrong email or password.")
    resp = RedirectResponse(_safe_next(next, user), status_code=303)
    resp.set_cookie(COOKIE, auth.start_session(s, user), httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=auth.SESSION_DAYS * 86400)
    return resp


@router.post("/logout")
def logout(request: Request, s: Session = Depends(get_session)):
    auth.end_session(s, request.cookies.get(COOKIE))
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: User | None = Depends(current_user)):
    return render(request, "register.html", user, portal="public")


@router.post("/register")
def register(request: Request, s: Session = Depends(get_session), email: str = Form(""), password: str = Form(""),
             name: str = Form(""), organization: str = Form(""), kind: str = Form("private"), consent: str = Form("")):
    if not consent:
        return back("/register", "请同意服务条款与隐私说明 Please accept the terms and privacy notice.")
    buyer = Buyer(name=(organization or name).strip()[:200] or "Buyer", kind=kind if kind in BUYER_KINDS else "private",
                  source="self", status="invited", contact_name=name.strip()[:50], contact_email=email.strip()[:200],
                  invite_token=new_token())
    s.add(buyer)
    s.flush()
    try:
        user = auth.create_user(s, email=email, password=password, role="buyer", name=name, organization=organization,
                                buyer_id=buyer.id)
    except ValueError as exc:
        s.delete(buyer)
        return back("/register", str(exc))
    resp = RedirectResponse("/buyer#thesis", status_code=303)
    resp.set_cookie(COOKIE, auth.start_session(s, user), httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=auth.SESSION_DAYS * 86400)
    return resp


@router.get("/invite/{token}", response_class=HTMLResponse)
def invite_page(token: str, request: Request, s: Session = Depends(get_session)):
    t = s.scalar(select(Target).where(Target.seller_token == token)) if token else None
    if t is None:
        not_found()
    return render(request, "invite.html", None, portal="public", t=t, token=token)


@router.post("/invite/{token}")
def invite_accept(token: str, request: Request, s: Session = Depends(get_session), email: str = Form(""),
                  password: str = Form(""), name: str = Form("")):
    t = s.scalar(select(Target).where(Target.seller_token == token)) if token else None
    if t is None:
        not_found()
    try:
        user = auth.create_user(s, email=email, password=password, role="seller", name=name)
    except ValueError as exc:
        return back(f"/invite/{token}", str(exc))
    t.seller_user_id, t.seller_token = user.id, ""
    auth.log(s, user, "seller_account_created", target_id=t.id)
    resp = RedirectResponse(f"/seller/{t.id}", status_code=303)
    resp.set_cookie(COOKIE, auth.start_session(s, user), httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=auth.SESSION_DAYS * 86400)
    return resp


# Last: a catch-all for the static information pages.
@router.get("/{page}", response_class=HTMLResponse)
def info_page(page: str, request: Request, user: User | None = Depends(current_user)):
    if page not in PAGES:
        not_found()
    return render(request, PAGES[page], user, portal="public")
