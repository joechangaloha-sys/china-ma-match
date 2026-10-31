"""Read-only mandate readiness, using existing version and access gates."""
from . import documents, handoff, release


def latest(items, language):
    return max((item for item in items if item.language == language),
               key=lambda item: (item.version, item.id or 0), default=None)


def snapshot(target, language):
    teaser = latest(target.teasers, language)
    memo = latest(target.memos, language)
    teaser_ready = bool(teaser and release.ready(teaser))
    memo_ready = bool(memo and release.ready(memo))
    matches = [m for m in target.matches if m.stage != 'dropped']
    qualified = [m for m in matches if m.buyer.status == 'verified']
    hands = [(m, handoff.get(m)) for m in qualified]
    active = sum(handoff.access_status(h) == 'active' for _, h in hands)
    attention = [(m, handoff.access_status(h)) for m, h in hands
                 if handoff.access_status(h) != 'active']
    terminal = target.status in {'closed', 'withdrawn', 'rejected'}
    if terminal:
        action = 'terminal'
    elif not target.authority_verified_at:
        action = 'authority'
    elif not teaser_ready:
        action = 'teaser'
    elif not memo_ready:
        action = 'memo'
    elif not target.is_example:
        action = 'providers'
    elif not qualified:
        action = 'buyers'
    elif not active:
        action = 'handoff'
    else:
        action = 'diligence'
    return {'target': target, 'teaser': teaser, 'memo': memo,
            'teaser_ready': teaser_ready, 'memo_ready': memo_ready,
            'missing': documents.missing_kinds(target), 'qualified': len(qualified),
            'active': active, 'attention': attention, 'next': action,
            'loi_stage': sum(m.stage in {'loi', 'closing', 'closed'} for m in matches)}
