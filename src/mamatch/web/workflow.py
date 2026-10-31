"""A read-only fictional walkthrough, evaluated with the actual release engine.

Each request uses a throwaway in-memory database. It cannot query or mutate mandates.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .. import config, release
from ..models import AdviserFirm, Base, Target, Teaser, User
from .common import render

router = APIRouter()
SCENARIOS = {'approved', 'missing-evidence', 'changed-content', 'changed-source', 'missing-seller', 'negative-revenue', 'loss-making'}


@router.get('/workflow', response_class=HTMLResponse)
def workflow(request: Request, scenario: str = 'approved'):
    if not config.DEMO_MODE:
        raise HTTPException(404)
    if scenario not in SCENARIOS:
        raise HTTPException(400, 'Unknown demonstration scenario')
    engine = create_engine('sqlite://')
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            reviewer = User(email='reviewer@example.invalid', password_hash='disabled', role='deal_manager', active=True)
            owner = User(email='owner@example.invalid', password_hash='disabled', role='seller', active=True)
            s.add_all([reviewer, owner]); s.flush()
            firm = AdviserFirm(name='Fictional demonstration adviser')
            s.add(firm); s.flush()
            target = Target(firm=firm, code_name='Project Willow', legal_name='Fictional withheld identity', province='浙江',
                            sector='industrial_services', revenue=30, net_profit=4, is_example=True,
                            seller_user_id=owner.id, authority_verified_at=datetime.now(timezone.utc))
            s.add(target); s.flush()
            language = getattr(request.state, 'lang', 'en')
            zh = language == 'zh'
            body = {'headline': '工业设备维护企业' if zh else 'Industrial equipment maintenance business',
                    'summary': '华东地区，服务制造及仓储客户。' if zh else 'Serving manufacturing and warehouse operators in East China.',
                    'highlights': ['年收入人民币20–50百万元' if zh else 'Annual revenue in the RMB 20–50m band',
                                   '重复服务业务' if zh else 'Repeat-service business']}
            artifact = Teaser(target=target, version=1, language=language, body=body, reid_score=0,
                              source_hash=release.source_digest(target))
            s.add(artifact); s.flush()
            release.demo_evidence(artifact)
            release.approve(artifact, reviewer)
            release.seller_approve(artifact, owner)
            if scenario == 'missing-evidence':
                artifact.body = {**body, 'highlights': body['highlights'] + ['未经证实的陈述' if zh else 'Unsupported new assertion']}
            elif scenario == 'changed-content':
                artifact.body = {**body, 'summary': '内容已修改' if zh else 'The wording has been edited after approval.'}
            elif scenario == 'changed-source':
                target.revenue = 35
            elif scenario == 'missing-seller':
                artifact.seller_approved_at = None
            elif scenario == 'negative-revenue':
                target.revenue = -30
            elif scenario == 'loss-making':
                target.net_profit = -2
                artifact.body = {**body, 'highlights': body['highlights'] + ['亏损企业' if zh else 'Loss-making business']}
                artifact.source_hash = release.source_digest(target)
                release.demo_evidence(artifact)
                release.approve(artifact, reviewer)
                release.seller_approve(artifact, owner)
            errors = release.validation_errors(artifact)
            checks = {'evidence': release.evidence_complete(artifact),
                      'analyst': release.analyst_current(artifact), 'seller': release.seller_current(artifact),
                      'authority': target.authority_verified_at is not None}
            return render(request, 'workflow.html', portal='public', scenario=scenario, checks=checks,
                          releasable=release.ready(artifact), content=artifact.body,
                          evidence=release.reviews(artifact), fingerprint=release.content_digest(artifact),
                          error_count=len(errors))
    finally:
        engine.dispose()
