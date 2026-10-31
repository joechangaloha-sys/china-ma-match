"""Server-enforced document release: evidence, version hashes, human approvals.

References are reviewed by humans, not verified merely because a string exists.
Fictional seed reviews are explicitly labelled; they are never evidence for real mandates.
"""
import hashlib
import json
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import object_session

from . import reid
from .models import Document, ReleaseClaim

SOURCE_FIELDS = ('code_name', 'legal_name', 'short_name', 'owner_name', 'brands', 'city', 'uscc',
                 'province', 'sector', 'founded_year', 'employees', 'revenue', 'net_profit',
                 'asking_value', 'deal_type', 'sale_reason', 'description', 'financials', 'disclosures',
                 'products_zh', 'products_en', 'normalized_earnings', 'show_earnings', 'premises',
                 'permits', 'inventory', 'stake_pct', 'payment_terms', 'founder_transition', 'keep_employees', 'timing')


def canonical(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Non-finite values cannot be released.')
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def digest(value):
    value = canonical(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                                     allow_nan=False).encode()).hexdigest()


def source_digest(target):
    return digest({key: getattr(target, key, None) for key in SOURCE_FIELDS})


def content_digest(artifact):
    return digest({'kind': kind(artifact), 'version': artifact.version, 'language': artifact.language,
                   'body': artifact.body, 'source_hash': artifact.source_hash})


def kind(artifact):
    return 'teaser' if artifact.__tablename__ == 'teasers' else 'memo'


def assertions(value, path='body'):
    """Every non-empty leaf is individually reviewed, including generated narrative and tables."""
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            result.extend(assertions(item, f'{path}.{key}'))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            result.extend(assertions(item, f'{path}.{i}'))
    elif value not in (None, ''):
        result.append((path, str(value)))
    return result


def reviews(artifact):
    session = object_session(artifact)
    if session is None or artifact.id is None:
        return []
    return session.scalars(select(ReleaseClaim).where(
        ReleaseClaim.artifact_kind == kind(artifact), ReleaseClaim.artifact_id == artifact.id,
        ReleaseClaim.target_id == artifact.target_id,
        ReleaseClaim.content_hash == content_digest(artifact))).all()


def review_claim(artifact, path, evidence_ref, user, document_id=None):
    if user is None or user.role != 'deal_manager' or not user.active:
        raise ValueError('Only an active deal manager may review evidence.')
    available = dict(assertions(artifact.body))
    if path not in available or not evidence_ref.strip():
        raise ValueError('Select a current claim and provide an evidence reference.')
    if len(evidence_ref.strip()) > 2000:
        raise ValueError('Evidence reference is too long.')
    doc = object_session(artifact).get(Document, document_id) if document_id else None
    if doc is None or doc.target_id != artifact.target_id or not doc.sha256:
        raise ValueError('Select an existing source document belonging to this mandate.')
    record = ReleaseClaim(document_id=doc.id, evidence_sha256=doc.sha256, target_id=artifact.target_id, artifact_kind=kind(artifact), artifact_id=artifact.id,
                          content_hash=content_digest(artifact), claim_path=path, statement=available[path],
                          evidence_ref=evidence_ref.strip(), reviewed_by=f'user:{user.id}',
                          reviewed_at=datetime.now(timezone.utc))
    object_session(artifact).add(record)
    return record


def evidence_complete(artifact):
    wanted = set(assertions(artifact.body))
    session = object_session(artifact)
    checked = set()
    for record in reviews(artifact):
        if not record.evidence_ref or not record.reviewed_by or not valid_time(record.reviewed_at):
            continue
        doc = session.get(Document, record.document_id) if record.document_id else None
        if doc is not None and doc.target_id == artifact.target_id and doc.sha256 == record.evidence_sha256:
            checked.add((record.claim_path, record.statement))
        elif artifact.target.is_example and record.reviewed_by == 'fictional-demo-reviewer':
            checked.add((record.claim_path, record.statement))
    return bool(wanted) and wanted <= checked


def demo_evidence(artifact):
    """Only called for explicitly fictional seed documents, never by an HTTP approval route."""
    if not artifact.target.is_example:
        raise ValueError('Fictional evidence is forbidden for real mandates.')
    session = object_session(artifact)
    checked = {(r.claim_path, r.statement) for r in reviews(artifact)}
    for path, statement in assertions(artifact.body):
        if (path, statement) not in checked:
            session.add(ReleaseClaim(target_id=artifact.target_id, artifact_kind=kind(artifact),
                artifact_id=artifact.id, content_hash=content_digest(artifact), claim_path=path,
                statement=statement, evidence_ref='FICTIONAL SEED: illustrative source, not a real supporting document',
                reviewed_by='fictional-demo-reviewer', reviewed_at=datetime.now(timezone.utc)))
    session.flush()


def validation_errors(artifact):
    target = artifact.target
    errors = []
    if not artifact.source_hash or artifact.source_hash != source_digest(target):
        errors.append('Source data changed; generate a new draft and review its evidence.')
    for field in ('revenue', 'net_profit', 'asking_value', 'employees'):
        value = getattr(target, field)
        if value is not None and (not math.isfinite(value) or (field != 'net_profit' and value < 0)):
            errors.append(f'Invalid financial or operating value: {field}.')
    for row in (target.financials or {}).values():
        for field, value in row.items():
            if value not in (None, ''):
                try:
                    n = float(value)
                    if not math.isfinite(n) or (field == 'revenue' and n < 0):
                        errors.append(f'Invalid financial table value: {field}.')
                except (TypeError, ValueError):
                    errors.append(f'Invalid financial table value: {field}.')
    if not evidence_complete(artifact):
        errors.append('Every assertion needs an evidence reference and a named human review.')
    score, found = reid.check(target, artifact.body)
    if kind(artifact) == 'teaser':
        if reid.risk_label(score) != 'low':
            errors.append('Resolve the re-identification findings before approval.')
    elif any(f['field'] in {'legal_name','short_name','owner_name','brands','city','uscc','registry_code','contact'} for f in found):
        errors.append('Remove identifying details before approving this info memo.')
    return errors


def valid_time(value):
    if not isinstance(value, datetime):
        return False
    value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)


def analyst_current(artifact):
    try:
        return (artifact.status == 'approved' and bool(artifact.analyst_approved_by)
                and valid_time(artifact.analyst_approved_at)
                and artifact.analyst_content_hash == content_digest(artifact)
                and not validation_errors(artifact))
    except (TypeError, ValueError):
        return False


def seller_current(artifact):
    return (analyst_current(artifact) and valid_time(artifact.seller_approved_at)
            and bool(artifact.seller_approved_by) and artifact.seller_content_hash == content_digest(artifact))


def ready(artifact):
    return seller_current(artifact) and artifact.target.authority_verified_at is not None


def approve(artifact, user=None):
    if user is None and artifact.target.is_example:
        from types import SimpleNamespace
        demo_evidence(artifact)
        user = SimpleNamespace(id='fictional-demo-reviewer', role='deal_manager', active=True)
    errors = validation_errors(artifact)
    if errors:
        raise ValueError(' '.join(errors))
    if user is None or user.role != 'deal_manager' or not user.active:
        raise ValueError('A named deal manager must approve this version.')
    artifact.status = 'approved'
    artifact.analyst_approved_by = f'user:{user.id}'
    artifact.analyst_approved_at = datetime.now(timezone.utc)
    artifact.analyst_content_hash = content_digest(artifact)
    artifact.seller_approved_at = None
    artifact.seller_approved_by = artifact.seller_content_hash = ''


def seller_approve(artifact, user=None):
    if not analyst_current(artifact):
        raise ValueError('The adviser has not approved this current version yet.')
    if user is None and artifact.target.is_example:
        from types import SimpleNamespace
        user = SimpleNamespace(id=artifact.target.seller_user_id, role='seller', active=True)
    if user is None or user.role != 'seller' or not user.active or user.id != artifact.target.seller_user_id:
        raise ValueError('Only the mandate owner may approve this version.')
    artifact.seller_approved_at = datetime.now(timezone.utc)
    artifact.seller_approved_by = f'user:{user.id}' if user.id is not None else 'fictional-demo-owner'
    artifact.seller_content_hash = content_digest(artifact)
