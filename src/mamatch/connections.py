"""Deferred external setup. No credentials, outbound calls or automated procurement."""
TODOS = (
    ('esign-account', '腾讯电子签企业认证及第三方应用 Tencent eSign company verification and third-party application',
     '运营公司管理员完成账号及授权；由用户决定何时启动。 Operating-company admin completes onboarding when the user resumes connections.'),
    ('esign-sandbox', '电子签沙箱应用及回调鉴权 Signing sandbox application and authenticated callbacks',
     '独立应用、签名令牌、加密密钥、安全存储及回调重试核对。 Dedicated app, signature token, encryption key, secret storage and callback retry/reconciliation checks.'),
    ('nda-counsel', '律师审定保密协议和签署权限 Counsel-approved NDA and signing authority',
     '确认签约主体、授权、期限、适用法律、语言及留存政策。 Confirm parties, authority, term, governing law, language and retention.'),
    ('vdr-trial', 'Docutone试用、境内托管及报价 Docutone trial, mainland hosting and quotation',
     '书面确认主备数据、日志、缓存、支持访问、权限到期与撤销、归档及费用。 Written confirmation of primary/backup data, logs, caches, support access, expiry/revocation, archiving and fees.'),
    ('vdr-api', '专业资料室接口与最小权限 Professional VDR API and least privilege',
     '核对接口文档、套餐及建房、邀请、权限、到期、撤销、审计导出的能力。 Verify API documentation/plan and room, invitation, permissions, expiry, revocation and audit-export capabilities.'),
    ('hosting', '真实数据环境与域名 Real-data environment and domain',
     '当前新加坡演示仅用虚构资料；真实数据上线前另行确定域名、部署及访问安排。 Singapore demo remains fictional; agree domain, deployment and access arrangements before real data.'),
)

ACCESS_LABELS = {
    'not_requested': '尚未申请 Not requested', 'awaiting_seller': '等待卖方批准 Awaiting seller approval',
    'pending_provisioning': '等待开通 Pending provisioning', 'active': '演示访问有效 Demo access active',
    'expired': '访问已到期 Access expired', 'revoked': '访问已撤销 Access revoked', 'blocked': '访问已锁定 Access blocked',
}
NDA_LABELS = {'draft': '草稿 Draft', 'requested': '等待模拟签署 Awaiting mock signature',
              'completed': '模拟签署完成 Mock signing completed', 'cancelled': '已取消 Cancelled'}
