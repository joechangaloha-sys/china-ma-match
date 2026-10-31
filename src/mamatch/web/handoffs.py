"""Internal handoff controls and an isolated, public fictional walkthrough."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .. import config, connections, handoff
from ..models import AdviserFirm, Base, Buyer, Match, Target, User
from .common import I, back, get_session, not_found, render, require

router = APIRouter()
dm = require('deal_manager')
SCENARIOS = ('awaiting-signature', 'missing-review', 'awaiting-seller', 'pending-provisioning', 'active', 'expired', 'revoked', 'changed-parties', 'cancelled')


@router.get('/internal/connections', response_class=HTMLResponse)
def connection_todos(request: Request, user: User = Depends(dm)):
    return render(request, 'connections.html', user, portal='internal', todos=connections.TODOS)


@router.get('/internal/handoffs/{match_id}', response_class=HTMLResponse)
def handoff_page(match_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    match = s.get(Match, match_id) or not_found()
    record = handoff.get(match)
    return render(request, 'handoff_internal.html', user, portal='internal', m=match, h=record,
                  history=handoff.events(record) if record else [])


@router.post('/internal/handoffs/{match_id}/{action}')
def handoff_action(match_id: int, action: str, reference: str = Form(''), days: int = Form(7),
                   user: User = Depends(dm), s: Session = Depends(get_session)):
    match = s.get(Match, match_id) or not_found()
    try:
        h = handoff.get(match)
        if action == 'start':
            handoff.start(match, user)
        elif h is None:
            raise ValueError('Prepare a fictional NDA request first.')
        elif action == 'complete':
            handoff.apply_completion(h, handoff.MockSignatureProvider.completion(h), user)
        elif action == 'review':
            handoff.review_authority(h, user, reference)
        elif action == 'request-access':
            handoff.request_access(h, user, days)
        elif action == 'provision':
            handoff.provision(h, user)
        elif action == 'revoke':
            handoff.revoke(h, user)
        elif action == 'expire':
            handoff.expire_demo(h, user)
        elif action == 'cancel':
            handoff.cancel(h, user)
        else:
            not_found()
    except ValueError as exc:
        return back(f'{I}/handoffs/{match_id}', str(exc))
    return back(f'{I}/handoffs/{match_id}', '虚构流程已更新 Fictional workflow updated')


@router.get('/handoff', response_class=HTMLResponse)
def handoff_demo(request: Request, scenario: str = 'active'):
    if not config.DEMO_MODE:
        raise HTTPException(404)
    if scenario not in SCENARIOS:
        raise HTTPException(400, 'Unknown demonstration scenario')
    engine = create_engine('sqlite://')
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            manager = User(email='manager@example.invalid', password_hash='disabled', role='deal_manager', active=True)
            seller = User(email='owner@example.invalid', password_hash='disabled', role='seller', active=True)
            firm = AdviserFirm(name='Fictional demonstration adviser')
            buyer = Buyer(name='Fictional qualified participant', kind='private', status='verified')
            s.add_all([manager, seller, firm, buyer]); s.flush()
            target = Target(firm=firm, code_name='Project Willow', legal_name='Fictional withheld identity',
                sector='industrial_services', province='浙江', is_example=True, seller_user_id=seller.id,
                authority_verified_at=datetime.now(timezone.utc))
            s.add(target); s.flush()
            match = Match(target=target, buyer=buyer, score=1, stage='interested', seller_approved_at=handoff.now())
            s.add(match); s.flush()
            h = handoff.start(match, manager)
            if scenario not in {'awaiting-signature', 'cancelled'}:
                handoff.apply_completion(h, handoff.MockSignatureProvider.completion(h), manager)
            if scenario not in {'awaiting-signature', 'missing-review', 'cancelled'}:
                handoff.review_authority(h, manager, 'FICTIONAL: illustrative signatory-authority review')
                handoff.request_access(h, manager, days=7)
            if scenario not in {'awaiting-signature', 'missing-review', 'awaiting-seller', 'cancelled'}:
                handoff.seller_approve(h, seller)
            if scenario in {'active', 'expired', 'revoked', 'changed-parties'}:
                handoff.provision(h, manager)
            if scenario == 'expired':
                handoff.expire_demo(h, manager)
            elif scenario == 'revoked':
                handoff.revoke(h, seller)
            elif scenario == 'changed-parties':
                buyer.uscc = 'fictional-replacement-entity'
            elif scenario == 'cancelled':
                handoff.cancel(h, manager)
            checks = {'signature': handoff.signature_complete(h), 'evidence': handoff.evidence_reviewed(h),
                      'seller': handoff.approval_current(h), 'access': handoff.access_active(h)}
            return render(request, 'handoff_demo.html', portal='public', h=h, scenario=scenario, checks=checks,
                          access_status=handoff.access_status(h), event_count=len(handoff.events(h)))
    finally:
        engine.dispose()
