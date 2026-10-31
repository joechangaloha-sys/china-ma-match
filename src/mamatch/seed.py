"""Example data so the workspace opens in a realistic state.

All records here are fictional and flagged is_example; the UI labels them. Real buyers are
invited by the operator (CNINFO suggests listed companies); real targets are entered by advisers.
Running the seed again adds what is missing and leaves existing records alone.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import buyers as buyer_reg
from . import auth, authority, config, release
from . import datacheck, fees, infomemo, listing, matching, offers, pipeline, plans, teaser
from .models import Adviser, AdviserFirm, Buyer, BuyerSignal, SellerCharge, Target, User

NOW = datetime.now(timezone.utc)

EXAMPLE_BUYERS = [
    dict(name="示例·华东精密科技", kind="listed", province="江苏", sectors=["auto_parts"],
         target_sectors=["auto_parts", "metal_fab"], target_regions=["江苏", "浙江", "安徽"],
         deal_size_min=40, deal_size_max=300, rationale="补强新能源汽车热管理零部件产能，向长三角整合中小供应商。",
         signal=("关于收购某汽车零部件公司60%股权的公告", 45)),
    dict(name="示例·浙东新材料", kind="listed", province="浙江", sectors=["chemicals"],
         target_sectors=["chemicals", "plastics"], target_regions=["浙江", "山东"],
         deal_size_min=50, deal_size_max=200, rationale="延伸功能性涂料产业链，收购区域性配方企业。",
         signal=("关于收购某新材料科技有限公司控制权的公告", 20)),
    dict(name="示例·长江产业并购基金", kind="pe", province="上海", sectors=[],
         target_sectors=["machinery", "industrial_services", "electronics"], target_regions=[],
         deal_size_min=30, deal_size_max=150, rationale="专注长三角制造业传承类控股收购，平台化整合。",
         signal=None),
    dict(name="示例·苏南智能装备", kind="listed", province="江苏", sectors=["machinery"],
         target_sectors=["machinery", "electronics"], target_regions=["江苏", "上海"],
         deal_size_min=80, deal_size_max=500, rationale="收购细分领域自动化设备商以补齐产品线。",
         signal=("关于签署股权收购意向协议的公告", 400)),
    dict(name="示例·粤港检测认证", kind="listed", province="广东", sectors=["industrial_services"],
         target_sectors=["industrial_services"], target_regions=["广东", "福建"],
         deal_size_min=20, deal_size_max=100, rationale="区域实验室网络扩张。",
         signal=("关于收购某检测技术有限公司100%股权的公告", 90)),
    dict(name="示例·皖江食品", kind="listed", province="安徽", sectors=["food"],
         target_sectors=["food", "packaging"], target_regions=["安徽", "江苏"],
         deal_size_min=30, deal_size_max=120, rationale="并购区域调味品品牌，扩充渠道。",
         signal=("关于购买资产暨收购某食品公司股权的公告", 800)),
]

# Verified buyers with no announcement history, so matching has realistic candidates.
# (count, kind, target_sectors, target_regions, size range, deal types)
GENERATED_BUYERS = [
    (4, "listed", ["auto_parts"], ["江苏", "浙江"], (20, 100), []),
    (5, "private", ["auto_parts", "metal_fab"], ["浙江"], (10, 60), ["full_sale", "majority"]),
    (3, "listed", ["auto_parts"], [], (50, 300), ["full_sale", "majority"]),
    (5, "pe", ["chemicals", "plastics"], ["江苏", "上海"], (30, 150), ["majority"]),
    (6, "listed", ["machinery", "electronics"], ["江苏", "上海", "浙江"], (30, 200), []),
    (2, "private", ["machinery"], ["安徽"], (10, 40), ["full_sale"]),
    (4, "private", ["food", "consumer_goods"], ["安徽", "江苏"], (10, 50), ["full_sale"]),
    (3, "pe", ["industrial_services"], [], (20, 80), []),
]

EXAMPLE_TARGETS = [
    dict(code_name="Project Jade", legal_name="示例宁波恒泰汽车部件有限公司", short_name="恒泰部件",
         owner_name="王建国", city="宁波市", province="浙江", sector="auto_parts",
         founded_year=2003, employees=180, revenue=126.0, net_profit=11.5, asking_value=90.0,
         deal_type="full_sale", sale_reason="succession", brands=["恒泰"],
         description="恒泰部件由王建国于2003年在宁波创办，生产汽车空调管路及热交换器支架，主要客户为两家合资整车厂的一级供应商。"
                     "创始人62岁，子女在海外不愿接班。工厂自有土地约25亩，IATF16949认证。"),
    dict(code_name="Project Kiln", legal_name="示例无锡新锐涂层材料有限公司", short_name="新锐涂层",
         owner_name="李梅", city="无锡市", province="江苏", sector="chemicals",
         founded_year=2011, employees=65, revenue=48.0, net_profit=6.2, asking_value=45.0,
         deal_type="majority", sale_reason="strategic", brands=[],
         description="工业防腐涂料配方企业，服务长三角钢结构与风电塔筒客户，拥有12项发明专利。创始人希望引入产业方做大并保留30%股权。"),
    dict(code_name="Project Delta", legal_name="示例苏州精工自动化设备有限公司", short_name="精工自动化",
         owner_name="陈志强", city="苏州市", province="江苏", sector="machinery",
         founded_year=2008, employees=120, revenue=85.0, net_profit=9.0, asking_value=70.0,
         deal_type="full_sale", sale_reason="succession", brands=["精工"],
         description="非标自动化装配线集成商，客户以长三角家电与汽车零部件厂为主。创始人计划三年内退休。"),
]

# Public product/service lines and seller-approved earnings for the examples (adviser-written, no names).
EXAMPLE_PUBLIC = {
    "Project Jade": dict(products_zh="汽车空调管路及热交换器支架，供应一级汽车零部件供应商",
                         products_en="Air-conditioning pipes and heat-exchanger brackets for tier-one auto suppliers",
                         normalized_earnings=11.0, show_earnings=True),
    "Project Kiln": dict(products_zh="工业防腐涂料配方，用于钢结构和风电塔筒",
                         products_en="Industrial anti-corrosion coatings for steel structures and wind towers",
                         normalized_earnings=6.0, show_earnings=True),
    "Project Delta": dict(products_zh="非标自动化装配线设计与集成，服务家电和汽车零部件工厂",
                          products_en="Custom automated assembly lines for appliance and auto-parts plants"),
}

# The seller's ask and what each sale includes (fixed vocabulary, see taxonomy.py).
EXAMPLE_ASK = {
    "Project Jade": dict(premises="owned_included", permits="company", inventory="included",
                         payment_terms="cash", founder_transition="6m"),
    "Project Kiln": dict(premises="leased", permits="company", inventory="included",
                         payment_terms="cash_earnout", founder_transition="24m"),
    "Project Delta": dict(premises="leased", permits="none", inventory="extra",
                          payment_terms="cash", founder_transition="12m"),
}

# How each example target is set up for the v2 demo: (visibility, seller plan, listed days ago)
EXAMPLE_SETUP = {"Project Jade": ("private", "paid", None), "Project Kiln": ("listed", "free", 12),
                 "Project Delta": ("listed", "free", 2)}


# Preparation-pack data for one example: three years of figures (RMB m) and checklist answers,
# with the kind of issues the data check should catch (uninvoiced revenue, social insurance gaps,
# a permit in the founder's name).
EXAMPLE_PREP = {
    "Project Jade": dict(
        financials={"-3": dict(revenue=104.0, gross_profit=21.0, net_profit=8.9, total_assets=96.0,
                               total_liabilities=41.0, cash=12.0),
                    "-2": dict(revenue=118.0, gross_profit=24.5, net_profit=10.2, total_assets=101.0,
                               total_liabilities=43.0, cash=15.5),
                    "-1": dict(revenue=126.0, gross_profit=26.0, net_profit=11.5, total_assets=108.0,
                               total_liabilities=44.0, cash=18.0)},
        disclosures=dict(invoiced_revenue=108.0, top_customer_share=38, related_party_share=5, employees_insured=132,
                         permits_personal=True, land="owned", owner_guarantees=True, pending_disputes=False,
                         notes="排污许可证登记在创始人个人名下。"),
    ),
}


# Demo sign-ins for local testing only (fictional people, .test domain). Never reuse in production.
DEMO_PASSWORD = "demo-pass-2026"
DEMO_USERS = [
    ("dm@demo.mamatch.test", "deal_manager", "示例·交易经理", None, None),
    ("seller.jade@demo.mamatch.test", "seller", "示例·王先生", "Project Jade", None),
    ("buyer.huadong@demo.mamatch.test", "buyer", "示例·华东精密 并购部", None, "EX000"),
    ("buyer.pending@demo.mamatch.test", "buyer", "示例·待审核买方A", None, "EXP001"),
    ("adviser@demo.mamatch.test", "adviser", "示例·李会计师", None, None),
]


def _example_authority(t: Target) -> None:
    """Example sellers: authority stated by the owner and checked by the deal manager."""
    if t.authority_verified_at is None:
        t.owner_role = t.owner_role or "legal_rep"
        t.owner_confirmed_at = t.owner_confirmed_at or NOW
        t.authority_verified_at = NOW
        t.authority_note = "示例：营业执照法定代表人与股东名册一致 Example: licence and shareholder register checked"


def _uscc(i: int) -> str:
    return f"91320500MA{i:08d}"  # format-valid, fictional



def seed(session: Session) -> None:
    firm = session.scalar(select(AdviserFirm).limit(1))
    if firm is None:
        firm = AdviserFirm(name="示例·长三角并购顾问事务所", city="上海")
        session.add(firm)
        session.flush()

    existing = {b.external_id: b for b in session.scalars(select(Buyer).where(Buyer.is_example))}
    for i, spec in enumerate(EXAMPLE_BUYERS):
        spec = dict(spec)
        signal = spec.pop("signal")
        buyer = existing.get(f"EX{i:03d}")
        if buyer is None:
            buyer = Buyer(source="example", external_id=f"EX{i:03d}", is_example=True, **spec)
            session.add(buyer)
            if signal:
                title, days_ago = signal
                session.add(BuyerSignal(buyer=buyer, kind="announcement", title=title,
                                        url=f"example://{i}", published_at=NOW - timedelta(days=days_ago),
                                        extracted={"generated_by": "example"}))
        if buyer.status in (None, "suggested"):  # None: new object, column default not applied yet
            _make_verified(buyer, i)

    n = 0
    for count, kind, sectors, regions, (lo, hi), deal_types in GENERATED_BUYERS:
        for _ in range(count):
            n += 1
            ext = f"EXG{n:03d}"
            if ext in existing:
                continue
            buyer = Buyer(name=f"示例·注册买方{n:02d}", kind=kind, source="example", external_id=ext, is_example=True,
                          target_sectors=sectors, target_regions=regions, deal_size_min=lo, deal_size_max=hi,
                          target_deal_types=deal_types)
            session.add(buyer)
            _make_verified(buyer, 100 + n)

    # Two buyers part-way through registration, to show the operator's queue.
    for ext, name, status in (("EXP001", "示例·待审核买方A", "registered"), ("EXP002", "示例·已邀请买方B", "invited")):
        if ext in existing:
            continue
        buyer = Buyer(name=name, kind="private", source="example", external_id=ext, is_example=True,
                      target_sectors=["auto_parts"], target_regions=["浙江"], deal_size_min=20, deal_size_max=80)
        session.add(buyer)
        buyer_reg.invite(buyer)
        if status == "registered":
            buyer.status, buyer.uscc = "registered", _uscc(900)
            buyer.registered_at = buyer.criteria_confirmed_at = NOW

    have = {t.code_name: t for t in session.scalars(select(Target).where(Target.is_example))}
    for spec in EXAMPLE_TARGETS:
        if spec["code_name"] not in have:
            have[spec["code_name"]] = Target(firm=firm, is_example=True, **spec)
            session.add(have[spec["code_name"]])
    session.flush()

    for code, t in have.items():
        if code in EXAMPLE_SETUP and t.status == "draft":
            if not t.teasers:
                _setup_target(session, t, *EXAMPLE_SETUP[code])
            else:  # example database from before seller approval and deal status existed
                _example_authority(t)
                for tz in t.teasers:
                    if tz.status == "approved" and not tz.seller_approved_at:
                        teaser.seller_approve(tz)
                t.status = "in_market"
    session.flush()
    for code, t in have.items():
        if code in EXAMPLE_PUBLIC and not t.products_zh:
            for k, v in EXAMPLE_PUBLIC[code].items():
                setattr(t, k, v)
    for code, t in have.items():
        if code in EXAMPLE_ASK and not t.premises:
            for k, v in EXAMPLE_ASK[code].items():
                if not getattr(t, k):
                    setattr(t, k, v)
    _seed_users(session, have)
    for code, t in have.items():
        if t.seller_plan == "paid" and not any(c.kind == "outreach" for c in t.charges):
            # Example databases from before the fee ledger: record the retainer they already show as paid.
            t.charges.append(SellerCharge(kind="outreach", amount=config.SELLER_PLAN_FEE_RMB,
                                          invoice_ref=t.plan_invoice_ref,
                                          detail={"platform_share": config.SELLER_PLAN_FEE_RMB * config.PLATFORM_SHARE}))
        if code in EXAMPLE_PREP and not fees.prep_pack_paid(t):
            _setup_prep(session, t, EXAMPLE_PREP[code])
    session.flush()
    for t in have.values():
        _seed_language_versions(session, t)
    if "Project Jade" in have:
        _seed_offers(session, have["Project Jade"])
    from . import handoff
    handoff.seed_examples(session)
    session.flush()


# Two example indicative offers on Project Jade, so the seller's comparison table has something to compare.
EXAMPLE_OFFERS = [
    dict(price_low=85, price_high=95, stake_pct=100, cash_at_close_pct=80, consideration="cash_earnout",
         financing="bank_loan", diligence_weeks=8, target_close="6m", keeps_staff=True, founder_role="12m",
         conditions="以财务和税务尽调结果为准；需取得并购贷款审批 Subject to financial and tax diligence and bank loan approval"),
    dict(price_low=70, price_high=80, stake_pct=100, cash_at_close_pct=100, consideration="cash",
         financing="own_funds", diligence_weeks=6, target_close="asap", keeps_staff=True, founder_role="6m",
         conditions="以尽调结果为准 Subject to diligence"),
]


def _seed_language_versions(session: Session, t: Target) -> None:
    """Each example has an approved teaser in both languages (and the memo, where there is one), drafted in
    one language each; older example drafts that mixed both languages are replaced."""
    def mixed(body) -> bool:
        text = str({k: v for k, v in body.items() if k not in {"facts", "listing_claims"}})
        return "Full sale" in text or "successor" in text or "Majority stake" in text

    for lang in ("zh", "en"):
        tz = next((x for x in t.teasers if x.language == lang and release.ready(x)), None)
        if tz is None or (lang == "zh" and mixed(tz.body)):
            new = teaser.draft(session, t, lang, use_llm=False)
            teaser.approve(new)
            teaser.seller_approve(new)
            if tz is not None:
                tz.status = "draft"
        if fees.prep_pack_paid(t):
            m = next((x for x in t.memos if x.language == lang and release.ready(x)), None)
            if m is None or (lang == "zh" and mixed(m.body)):
                new_m = infomemo.draft(session, t, lang, use_llm=False)
                infomemo.approve(new_m)
                infomemo.seller_approve(new_m)
                if m is not None:
                    m.status = "draft"
    session.flush()


def _seed_offers(session: Session, t: Target) -> None:
    if any(m.offers for m in t.matches):
        for m in t.matches:  # example databases from before the conditions were bilingual
            for o in m.offers:
                for spec in EXAMPLE_OFFERS:
                    if o.conditions and spec["conditions"].startswith(o.conditions) and o.conditions != spec["conditions"]:
                        o.conditions = spec["conditions"]
        return
    from . import handoff
    handoff.seed_examples(session)
    after = [m for m in t.matches if m.stage in offers.AFTER_NDA]
    for m in offers.outreach_candidates(t)[: max(0, 2 - len(after))]:
        offers.approve_and_send(session, m)
        offers.buyer_respond(session, m, interested=True)
        manager = session.scalar(select(User).where(User.role == 'deal_manager'))
        offers.accept_nda(session, m, manager)
        from . import handoff
        handoff.review_authority(handoff.get(m), manager, 'FICTIONAL SEED: illustrative signatory-authority review')
        after.append(m)
    for m, spec in zip(after, EXAMPLE_OFFERS):
        offers.submit_offer(session, m, None, **spec)


def _seed_users(session: Session, targets: dict[str, Target]) -> None:
    for email, role, name, target_code, buyer_ext in DEMO_USERS:
        existing = session.scalar(select(User).where(User.email == email))
        if existing:
            existing.is_demo = True
            continue
        buyer = session.scalar(select(Buyer).where(Buyer.external_id == buyer_ext)) if buyer_ext else None
        user = auth.create_user(session, email=email, password=DEMO_PASSWORD, role=role, name=name,
                                organization=buyer.name if buyer else "", buyer_id=buyer.id if buyer else None)
        user.is_demo = True
        if target_code and target_code in targets:
            targets[target_code].seller_user_id = user.id
            targets[target_code].seller_token = ""  # invite used
    for t in targets.values():
        if t.is_example:
            _example_authority(t)
    adviser_user = session.scalar(select(User).where(User.email == "adviser@demo.mamatch.test"))
    if adviser_user and not session.scalar(select(Adviser.id).where(Adviser.user_id == adviser_user.id)):
        adv = authority.register_adviser(session, adviser_user, firm="示例·长三角会计师事务所", profession="accountant",
                                         license_no="EX-CPA-000001", firm_uscc="91320500MA00008888")
        authority.verify_adviser(session, adv, adviser_user)
        if "Project Delta" in targets:
            a = authority.start_mandate(session, adv, targets["Project Delta"])
            a.status, a.confirmed_at, a.verified_at = "verified", NOW, NOW
    if (b := session.scalar(select(Buyer).where(Buyer.external_id == "EX000"))) and not b.funding_max:
        b.funding_min, b.funding_max, b.funding_evidence = 30, 300, "bank_letter"
        b.thesis_text = "补强新能源汽车热管理零部件产能，收购长三角中小汽配供应商。"
        b.experience = "上市汽车零部件企业，已完成三次同业收购。"


def _setup_prep(session: Session, t: Target, spec: dict) -> None:
    """Preparation pack paid, data submitted and checked, IM approved; the furthest buyer signs the NDA."""
    ys = datacheck.years()
    t.financials = {ys[int(k)]: v for k, v in spec["financials"].items()}
    t.disclosures = dict(spec["disclosures"])
    fees.record_prep_pack(t, "PILOT-EX-002")
    datacheck.run(session, t, use_llm=False)
    infomemo.approve(infomemo.draft(session, t, "zh", use_llm=False))
    session.flush()
    for m in t.matches:
        if m.stage == "interested":
            pipeline.move(session, m, "nda_signed", "NDA signed")
            break

def _make_verified(buyer: Buyer, i: int) -> None:
    buyer.invite_token = buyer.invite_token or buyer_reg.new_token()
    buyer.uscc = buyer.uscc or _uscc(i)
    buyer.status = "verified"
    buyer.registered_at = buyer.verified_at = buyer.criteria_confirmed_at = NOW


def _setup_target(session: Session, t: Target, visibility: str, plan: str, listed_days_ago: int | None) -> None:
    t.seller_token = buyer_reg.new_token()
    _example_authority(t)
    if not any(tz.status == "approved" for tz in t.teasers):
        tz = teaser.draft(session, t, "zh", use_llm=False)
        teaser.approve(tz)
        teaser.seller_approve(tz)
        session.flush()  # matching.refresh() reloads the target; unflushed approvals would be lost
    if plan == "paid":
        plans.mark_seller_paid(t, "PILOT-EX-001")
    t.status = "seller_approval"
    if visibility == "listed":
        listing.publish(t)
        t.listed_at = NOW - timedelta(days=listed_days_ago or 0)
        return
    t.status = "in_market"
    # Private and paid: three shortlisted buyers waiting for the seller, one already sent and answered.
    matches = [m for m in matching.refresh(session, t) if m.stage == "suggested"][:4]
    for m in matches:
        pipeline.move(session, m, "shortlisted", "Adviser shortlist")
    if matches:
        offers.approve_and_send(session, matches[0])
        offers.buyer_respond(session, matches[0], interested=True)
