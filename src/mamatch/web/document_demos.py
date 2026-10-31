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
  'subtitle': ('供潜在投资方审阅的保密资料', 'Confidential buyer material preview'),
  'sections': [
   ('交易概览', 'Transaction overview', '柳树项目的标的公司为一家虚构的华东地区工业设备维护企业。拟议交易为转让标的公司80%股权，创始股东保留20%股权。本演示不涉及真实交易主体。', 'Project Willow is a fictional East China industrial equipment maintenance business. The illustrative transaction is an 80% share sale with 20% retained by the founder. No real identity is disclosed.'),
   ('业务与客户', 'Business and customers', '标的公司主要提供预防性维护、应急维修及零部件安装服务，示例客户主要来自制造业及仓储行业。客户集中度、合同续签情况及服务质量尚待尽职调查核实。', 'Preventive maintenance, emergency repair and replacement-parts installation for manufacturing and warehouse operators. Customer concentration, contract renewals and service quality remain diligence items.'),
   ('财务概况', 'Financial profile', '2025年度营业收入区间为人民币2,500万元至4,000万元，经调整的息税折旧及摊销前利润区间为人民币400万元至700万元。上述数据均为虚构示例，未经审计；区间中值不构成盈利预测。', 'FY2025 revenue: RMB 25–40m; adjusted EBITDA: RMB 4–7m. These fictional bands are not audited accounts. Their midpoints are not earnings forecasts.'),
   ('盈利调整及营运资金', 'Earnings adjustments and working capital', '经调整的息税折旧及摊销前利润的调节明细、净债务、现金、租赁负债及正常营运资金水平尚待核实，目前尚不具备测算股权价值的充分依据。', 'The EBITDA bridge, net debt, cash, lease obligations and normal working-capital target are unconfirmed. There is insufficient evidence to calculate equity value.'),
   ('交易结构及过渡安排', 'Structure and transition', '本示例假设采用股权转让方式，创始股东拟提供六个月的过渡支持。具体过渡安排、核心人员留任及适用的监管要求尚待交易各方协商确定。', 'The sample assumes a share transaction and a proposed six-month founder transition. Scope, key-employee retention and any regulatory requirements are not agreed.'),
   ('主要风险及待核实事项', 'Risks and open diligence', '应重点核实持续性或重复性服务收入占比55%至65%的统计口径、客户集中度、应收账款账龄、劳动用工、租赁安排、业务资质及关联交易情况。本资料不构成任何收益承诺。', 'Diligence should verify the definition of 55–65% recurring/repeat-service revenue, customer concentration, receivables ageing, employees and leases, permits and related-party transactions. No return is guaranteed.'),
   ('来源及分发', 'Sources and circulation', '财务数据沿用原型项目简介中的虚构示例，新增交易安排均为演示假设。正式信息备忘录对外提供前，应完成逐项资料核验及卖方确认，并核实保密协议效力及资料室访问授权。', 'Figures follow Kimi’s fictional teaser; added transaction assumptions are illustrative. A real memo requires claim-level evidence review, seller approval and valid NDA/VDR access.')],
  'states': [('draft','初稿：资料待核实','Draft: evidence outstanding'),('review','卖方确认阶段预览','Seller review preview'),('buyer','投资方阅览视图演示','Simulated buyer view')],
  'notes': {'draft': ('缺少证据与确认；真实备忘录分发将被阻止。', 'Evidence and approvals are outstanding; real memo circulation would be blocked.'), 'review': ('展示卖方审核阶段；没有记录真实确认。', 'Shows the seller-review stage; no actual approval is recorded.'), 'buyer': ('仅模拟已签NDA后的版式；不授予任何真实买方权限。', 'Simulates the post-NDA layout only; it grants no actual buyer access.')}},
 'nda': {
  'title': ('保密协议', 'Non-disclosure agreement'), 'code': 'NDA',
  'subtitle': ('保密条款及签署流程演示', 'Terms and signing-flow demonstration'),
  'sections': [
   ('协议主体及使用目的', 'Parties and purpose', '信息披露方为虚构卖方甲，信息接收方为虚构买方乙。保密信息仅限用于评估柳树项目拟议收购事宜。真实主体名称、统一社会信用代码、住所及签署权限均未录入。', 'Disclosing party: Fictional Seller A. Recipient: Fictional Buyer B. Purpose: evaluating a potential acquisition of Project Willow. Real names, registration identifiers, addresses and signing authority are not populated.'),
   ('保密信息', 'Confidential information', '示例保密信息范围包括未公开的财务、客户、员工、技术及交易资料，以及基于该等资料形成的分析成果。已公开、合法事先持有、独立开发或自有权披露的第三方合法取得的信息不在此限。具体范围及例外情形应经法律顾问审核确定。', 'Illustrative scope includes non-public financial, customer, employee, technical and transaction information and derived analyses. Exclusions include public information, lawful prior possession, independent development and lawful third-party receipt. Counsel must settle the scope.'),
   ('使用及披露义务', 'Use and disclosure limits', '接收方仅可为约定评估目的使用保密信息，并仅向确有知悉必要且承担相应保密义务的代表披露。未经许可，不得擅自接触标的公司员工或客户。依法应披露信息的通知及处理程序尚待约定。', 'Use only for the agreed evaluation purpose; share only with need-to-know representatives subject to appropriate confidentiality obligations. No unauthorised employee/customer contact. Procedures for legally compelled disclosure remain to be agreed.'),
   ('保密期限及资料返还', 'Duration and materials', '本示例假设保密期限为两年；商业秘密及依法留存资料的处理应另行约定。交易磋商终止后，应按约定返还或销毁资料，并明确备份及法定留存的例外安排。', 'Illustrative confidentiality period: two years; trade secrets and legally retained records require separate treatment. Return or delete materials as agreed when discussions end; backup and statutory-retention exceptions must be specified.'),
   ('交易承诺及违约救济', 'No transaction commitment and remedies', '资料披露不构成达成交易的承诺或对资料准确性的保证。责任承担、违约救济、法律适用及争议解决条款尚待法律顾问审核，本演示不预设具体安排。', 'Disclosure creates no commitment to transact or warranty of accuracy. Liability, remedies, governing law and dispute forum are unresolved and require counsel review.'),
   ('签署与资料室', 'Signing and data-room access', '签署信息仅作占位展示，尚无任何签名。正式流程须核验交易主体及签署权限，使用已接入的电子签署服务，并另行取得卖方授权后，方可开通限时资料室访问权限。签署保密协议不等同于取得资料访问授权。', 'Signature blocks are placeholders with no signatures. A real flow requires verified parties and authority, an integrated signing provider and separate seller approval before time-limited VDR access. An NDA alone does not open the room.')],
  'states': [('draft','初稿：条款待审核','Draft: terms for review'),('sent','待签署状态演示','Simulated awaiting signature'),('complete','签署完成状态演示','Simulated completion')],
  'notes': {'draft': ('尚未发起签署申请，相关条款尚待法律顾问审核。', 'No signing request exists; legal review is outstanding.'), 'sent': ('仅展示待签署状态，未发送任何邮件或签署链接。', 'Demonstrates a pending state; no email or signing link is sent.'), 'complete': ('仅展示签署完成状态，不存在有效签署凭证，亦未授予资料室访问权限。', 'Visual completion example only; no signature evidence exists and VDR access remains ungranted.')}},
 'loi': {
  'title': ('收购意向书', 'Letter of intent'), 'code': 'LOI',
  'subtitle': ('意向性交易条款及版本管理演示', 'Indicative terms and version demonstration'),
  'sections': [
   ('交易双方与标的', 'Parties and transaction', '虚构买方乙拟向虚构卖方甲收购柳树项目标的公司80%股权，创始股东保留20%股权。本文件未向任何主体发送，不构成收购要约。', 'Fictional Buyer B proposes to acquire 80% of Project Willow from Fictional Seller A; the founder retains 20%. This document has not been sent to anyone and is not an offer.'),
   ('估值口径', 'Valuation basis', '本示例假设标的公司整体企业价值为人民币2,000万元，按无现金、无债务并维持正常营运资金水平的口径确定。该金额仅为虚构的磋商假设，不构成估值意见。', 'Illustrative enterprise value: RMB 20m for 100% of the business, assumed cash-free/debt-free with normal working capital. This is a fictional negotiating assumption, not a valuation conclusion.'),
   ('股权转让对价及支付安排', 'Equity consideration and payment', '标的股权转让对价不应直接按企业价值的80%计算。应先根据约定的现金、债务及营运资金调整机制确定股权价值，再按拟收购股权比例测算。支付进度、资金托管及递延支付安排尚待协商。', 'The price for 80% is not automatically 80% of enterprise value. First bridge to equity value using agreed cash, debt and working-capital adjustments, then apply the acquired stake. Payment timing, escrow and any deferred consideration are unresolved.'),
   ('先决条件及尽职调查', 'Conditions and diligence', '拟议交易以完成财务、法律、税务及商业尽职调查，履行内部决策程序，落实必要融资，取得适用的监管批准并签署正式交易协议为先决条件。本示例假设尽职调查期限为60天，不构成交易完成时间的承诺。', 'Subject to financial, legal, tax and commercial diligence, internal approvals, financing if needed, applicable regulatory approvals and definitive agreements. Illustrative diligence period: 60 days, not a committed completion timetable.'),
   ('排他期及保密安排', 'Exclusivity and confidentiality', '本示例假设排他性磋商期限为30天，不产生实际排他权利。保密义务拟按另行有效签署的保密协议执行。具有法律约束力的具体条款及其期限，应由交易各方明确约定并经法律顾问审核。', 'Illustrative exclusivity: 30 days; no actual exclusivity is granted. Confidentiality is intended to refer to a separately executed NDA. Any binding provisions and their duration require explicit negotiation and counsel review.'),
   ('法律约束力及签署安排', 'Binding effect and signatures', '本文件所列商业条款拟不具有法律约束力。保密、排他、费用承担及争议解决条款是否具有法律约束力，应在正式文本中逐项明确。本演示不形成任何协议，亦不提供签署或接受功能。', 'Commercial terms are intended to be non-binding. Any binding confidentiality, exclusivity, costs or dispute provisions must be identified expressly in the final text. This demo forms no agreement and provides no signature or acceptance action.')],
  'states': [('draft','初稿：条款磋商','Draft: terms discussion'),('review','项目负责人审核','Deal-manager review'),('revised','修订稿：待重新审核','Revised: review required')],
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
