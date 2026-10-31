"""Read-only fictional document previews. No mandate, signature or offer is created."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from .. import config
from .common import render

router = APIRouter()
# Chinese / English pairs; sample terms are deliberately separate from real deal documents.
DOCUMENTS = {
 'info-memo': {
  'title': ('信息备忘录', 'Information memorandum'), 'code': 'IM',
  'subtitle': ('保密买方资料预览', 'Confidential buyer material preview'),
  'sections': [
   ('交易概览', 'Transaction overview', 'Project Willow 为虚构的华东工业设备维护企业。拟出售80%股权，创始人保留20%。本演示不披露真实主体。', 'Project Willow is a fictional East China industrial equipment maintenance business. The illustrative transaction is an 80% share sale with 20% retained by the founder. No real identity is disclosed.'),
   ('业务与客户', 'Business and customers', '提供预防性维护、紧急维修及零部件安装。制造与仓储客户为示例客户群；客户集中度、合同续约及服务质量仍需尽调。', 'Preventive maintenance, emergency repair and replacement-parts installation for manufacturing and warehouse operators. Customer concentration, contract renewals and service quality remain diligence items.'),
   ('财务概况', 'Financial profile', '2025财年收入区间为人民币2,500万至4,000万元，调整后EBITDA为400万至700万元。均为虚构区间，非审计数据；不得以区间中点作为盈利预测。', 'FY2025 revenue: RMB 25–40m; adjusted EBITDA: RMB 4–7m. These fictional bands are not audited accounts. Their midpoints are not earnings forecasts.'),
   ('盈利调整与营运资金', 'Earnings adjustments and working capital', 'EBITDA调整明细、净债务、现金、租赁义务及正常营运资金目标均待确认。没有足够依据计算股权价值。', 'The EBITDA bridge, net debt, cash, lease obligations and normal working-capital target are unconfirmed. There is insufficient evidence to calculate equity value.'),
   ('交易结构与交接', 'Structure and transition', '演示假设为股权交易，创始人拟支持六个月交接。交接范围、关键员工留任及任何监管要求尚未商定。', 'The sample assumes a share transaction and a proposed six-month founder transition. Scope, key-employee retention and any regulatory requirements are not agreed.'),
   ('风险与待核实事项', 'Risks and open diligence', '应核实重复服务收入占比55%至65%的定义、客户集中度、应收账款账龄、员工与租赁、许可及关联交易。不存在回报保证。', 'Diligence should verify the definition of 55–65% recurring/repeat-service revenue, customer concentration, receivables ageing, employees and leases, permits and related-party transactions. No return is guaranteed.'),
   ('来源及分发', 'Sources and circulation', '数据沿用Kimi简介的虚构示例，新增交易假设明确为演示。真实备忘录须逐项证据审核、卖方确认及有效保密协议与资料室授权。', 'Figures follow Kimi’s fictional teaser; added transaction assumptions are illustrative. A real memo requires claim-level evidence review, seller approval and valid NDA/VDR access.')],
  'states': [('draft','草稿：证据待核实','Draft: evidence outstanding'),('review','卖方审核预览','Seller review preview'),('buyer','买方视图模拟','Simulated buyer view')],
  'notes': {'draft': ('缺少证据与确认；真实备忘录分发将被阻止。', 'Evidence and approvals are outstanding; real memo circulation would be blocked.'), 'review': ('展示卖方审核阶段；没有记录真实确认。', 'Shows the seller-review stage; no actual approval is recorded.'), 'buyer': ('仅模拟已签NDA后的版式；不授予任何真实买方权限。', 'Simulates the post-NDA layout only; it grants no actual buyer access.')}},
 'nda': {
  'title': ('保密协议', 'Non-disclosure agreement'), 'code': 'NDA',
  'subtitle': ('条款与签署流程演示', 'Terms and signing-flow demonstration'),
  'sections': [
   ('当事人与用途', 'Parties and purpose', '披露方：虚构卖方A；接收方：虚构买方B。用途限于评估Project Willow的潜在收购。真实名称、统一社会信用代码、地址及签署权限均未填写。', 'Disclosing party: Fictional Seller A. Recipient: Fictional Buyer B. Purpose: evaluating a potential acquisition of Project Willow. Real names, registration identifiers, addresses and signing authority are not populated.'),
   ('保密信息', 'Confidential information', '示例范围包括非公开财务、客户、员工、技术及交易信息和由其形成的分析。不含已公开、合法先前持有、独立开发或合法第三方取得的信息。具体范围需律师确定。', 'Illustrative scope includes non-public financial, customer, employee, technical and transaction information and derived analyses. Exclusions include public information, lawful prior possession, independent development and lawful third-party receipt. Counsel must settle the scope.'),
   ('使用及披露限制', 'Use and disclosure limits', '仅用于约定评估目的；仅向确有需要且承担相应保密义务的代表提供。不得擅自联系员工或客户。依法强制披露的程序需另行约定。', 'Use only for the agreed evaluation purpose; share only with need-to-know representatives subject to appropriate confidentiality obligations. No unauthorised employee/customer contact. Procedures for legally compelled disclosure remain to be agreed.'),
   ('期限及资料处置', 'Duration and materials', '演示假设保密义务持续两年；商业秘密及依法保存的资料另行约定。交易终止后按约定返还或删除资料，备份与法定留存例外需明确。', 'Illustrative confidentiality period: two years; trade secrets and legally retained records require separate treatment. Return or delete materials as agreed when discussions end; backup and statutory-retention exceptions must be specified.'),
   ('不承诺交易与救济', 'No transaction commitment and remedies', '披露资料不构成交易承诺或准确性保证。责任分配、救济、适用法律及争议解决机构均待律师审核，不在演示中预设。', 'Disclosure creates no commitment to transact or warranty of accuracy. Liability, remedies, governing law and dispute forum are unresolved and require counsel review.'),
   ('签署与资料室', 'Signing and data-room access', '签署栏为占位符，没有签名。真实流程须核验主体与权限、采用已接入的签署服务，并取得卖方单独授权后才能开通限时资料室。签署NDA本身不会自动开放资料。', 'Signature blocks are placeholders with no signatures. A real flow requires verified parties and authority, an integrated signing provider and separate seller approval before time-limited VDR access. An NDA alone does not open the room.')],
  'states': [('draft','草稿：条款待审核','Draft: terms for review'),('sent','模拟待签署','Simulated awaiting signature'),('complete','模拟完成','Simulated completion')],
  'notes': {'draft': ('没有创建签署请求，条款尚未完成法律审核。', 'No signing request exists; legal review is outstanding.'), 'sent': ('仅演示待签状态；没有发送邮件或签署链接。', 'Demonstrates a pending state; no email or signing link is sent.'), 'complete': ('纯视觉完成示例；没有签署凭证，资料室仍未授权。', 'Visual completion example only; no signature evidence exists and VDR access remains ungranted.')}},
 'loi': {
  'title': ('收购意向书', 'Letter of intent'), 'code': 'LOI',
  'subtitle': ('指示性条款与版本演示', 'Indicative terms and version demonstration'),
  'sections': [
   ('交易双方与标的', 'Parties and transaction', '虚构买方B拟向虚构卖方A收购Project Willow的80%股权，创始人保留20%。本文件未发送给任何人，也不构成报价。', 'Fictional Buyer B proposes to acquire 80% of Project Willow from Fictional Seller A; the founder retains 20%. This document has not been sent to anyone and is not an offer.'),
   ('估值口径', 'Valuation basis', '演示企业价值为人民币2,000万元，对应100%业务口径，假设无现金、无债务并包含正常营运资金。为虚构谈判假设，不是估值结论。', 'Illustrative enterprise value: RMB 20m for 100% of the business, assumed cash-free/debt-free with normal working capital. This is a fictional negotiating assumption, not a valuation conclusion.'),
   ('股权对价与支付', 'Equity consideration and payment', '80%股权价格并非直接等于企业价值的80%。须先按约定现金、债务及营运资金调整为股权价值，再计算收购比例。支付时间、托管及任何递延对价均未商定。', 'The price for 80% is not automatically 80% of enterprise value. First bridge to equity value using agreed cash, debt and working-capital adjustments, then apply the acquired stake. Payment timing, escrow and any deferred consideration are unresolved.'),
   ('条件与尽调', 'Conditions and diligence', '拟以财务、法律、税务及商业尽调、内部审批、融资（如需）、适用监管审批及正式协议为前提。演示尽调期为60天，非已承诺的完成时间。', 'Subject to financial, legal, tax and commercial diligence, internal approvals, financing if needed, applicable regulatory approvals and definitive agreements. Illustrative diligence period: 60 days, not a committed completion timetable.'),
   ('排他与保密', 'Exclusivity and confidentiality', '演示排他期为30天，但没有授予真实排他权。保密安排拟另行沿用经签署的NDA；具体约束性条款及期限须明确协商并由律师审核。', 'Illustrative exclusivity: 30 days; no actual exclusivity is granted. Confidentiality is intended to refer to a separately executed NDA. Any binding provisions and their duration require explicit negotiation and counsel review.'),
   ('约束性与签署', 'Binding effect and signatures', '商业条款拟为非约束性。保密、排他、费用及争议解决是否具有约束力须在最终文本中逐项明确。本演示未形成任何协议，无签字或接受操作。', 'Commercial terms are intended to be non-binding. Any binding confidentiality, exclusivity, costs or dispute provisions must be identified expressly in the final text. This demo forms no agreement and provides no signature or acceptance action.')],
  'states': [('draft','草稿：条款讨论','Draft: terms discussion'),('review','交易经理审核','Deal-manager review'),('revised','修订版：待重新审核','Revised: review required')],
  'notes': {'draft': ('初始商业假设，未经买卖双方批准。', 'Initial commercial assumptions; neither party has approved them.'), 'review': ('展示审核清单，不代表已经批准或送达。', 'Displays a review checklist, not approval or delivery.'), 'revised': ('价格或条款变化后须重新审核；本预览不保留任何真实批准。', 'Changed price or terms require fresh review; this preview retains no real approvals.')}}
}

@router.get('/document-demos', response_class=HTMLResponse)
def document_demo_hub(request: Request):
    if not config.DEMO_MODE:
        raise HTTPException(404)
    return render(request, 'document_demos.html', None, documents=DOCUMENTS, kind=None, portal='public')

@router.get('/document-demos/{kind}', response_class=HTMLResponse)
def document_demo(request: Request, kind: str, state: str = 'draft'):
    if not config.DEMO_MODE or kind not in DOCUMENTS:
        raise HTTPException(404)
    doc = DOCUMENTS[kind]
    if state not in {s[0] for s in doc['states']}:
        raise HTTPException(400, 'Unknown demonstration state')
    return render(request, 'document_demos.html', None, documents=DOCUMENTS, kind=kind, doc=doc,
                  state=state, portal='public')
