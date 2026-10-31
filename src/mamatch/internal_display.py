"""Edition-specific UI labels and aliases for explicitly fictional seed records.

Never edits original records, legal names, evidence or stored audit JSON.
"""
import re
from . import i18n

EXAMPLES = {
    '示例·长三角并购顾问事务所':'Example · Yangtze River Delta M&A Advisers',
    '示例·长三角会计师事务所':'Example · Yangtze River Delta Accounting Firm',
    '示例·李会计师':'Example · Accountant Li', '示例·王先生':'Example · Mr Wang',
    '示例宁波恒泰汽车部件有限公司':'Example Ningbo Hengtai Auto Components Co., Ltd.',
    '王建国':'Wang Jianguo', '宁波市':'Ningbo',
    '排污许可证登记在创始人个人名下。':'The emissions permit is registered in the founder’s personal name.',
    'Adviser shortlist':'顾问初选', 'NDA signed':'保密协议演示签署完成',
    'Fictional signing completion; no external provider connected':'虚构签署完成记录；未连接外部服务',
}
ZH_NOTES={'Adviser shortlist','NDA signed','Fictional signing completion; no external provider connected'}


def record(value, lang):
    if not isinstance(value,str):return value
    if lang=='zh':
        legacy = re.fullmatch(r'NDA v([0-9-]+) accepted online', value)
        if legacy:return '演示：已在线确认保密协议，版本'+legacy[1]
        if value in ZH_NOTES:return EXAMPLES[value]
        return i18n.tr(value,lang).replace('示例·待审核买方A','示例·待审核买方甲')
    if value in EXAMPLES and value not in ZH_NOTES:return EXAMPLES[value]
    if value.startswith('恒泰部件由王建国于2003年在宁波创办'):
        return 'Hengtai Components was founded by Wang Jianguo in Ningbo in 2003. It manufactures automotive air-conditioning pipes and heat-exchanger brackets, supplying tier-one vendors to two joint-venture vehicle manufacturers. The founder is 62 and seeks succession. The business owns approximately 25 mu of land and holds IATF16949 certification.'
    if value.startswith('示例·注册买方'):return 'Example · Registered buyer '+value.removeprefix('示例·注册买方')
    if value.startswith('示例·待审核买方'):return 'Example · Buyer pending review '+value.removeprefix('示例·待审核买方')
    if value.startswith('示例·'):return 'Example buyer'  # only explicitly fictional labels, never real company names
    for source,translated in EXAMPLES.items():
        if source not in ZH_NOTES:value=value.replace(source,translated)
    if re.match('[A-Za-z]',value) and re.search('[一-鿿]',value):return value
    return i18n.tr(value,lang)

ACTIONS={
    'sign_in':'登录', 'sign_out_all':'退出全部设备','sign_in_failed':'登录失败',
    'offer_submitted':'提交意向报价','nda_accept':'确认保密协议演示',
    'authorization_requested':'申请顾问授权','adviser_verified':'核验顾问资格','adviser_registered':'登记顾问',
    'document_upload':'上传文件','document_scan':'文件安全扫描','document_view':'查看文件','document_denied':'拒绝文件访问',
    'field_review':'审核财务数值','extraction_run':'提取财务数值','data_room_flag':'调整资料室文件范围',
    'seller_account_created':'开通卖方账户','personal_account_activated':'开通个人账户',
    'mfa_failed':'身份验证失败','mfa_enabled':'启用多因素认证','mfa_verified':'完成身份验证','mfa_recovery_used':'使用恢复码',
}
DETAILS={'price_high':'报价上限','price_low':'报价下限','stake':'股权比例','version':'版本',
'adviser_id':'顾问编号','status':'状态','sha256':'文件校验值','filename':'文件名','document_id':'文件编号',
'email':'邮箱','note':'备注','fields':'数值数量','field':'财务科目','period':'期间','decision':'决定',
'corrected':'是否更正','method':'方法','in_data_room':'是否列入资料室','days':'天数'}


def audit_action(code,lang):
    return ACTIONS.get(code,'其他操作') if lang=='zh' else code.replace('_',' ').capitalize()


def audit_details(detail,lang):
    rows=[]
    for key,value in (detail or {}).items():
        label=DETAILS.get(key,'其他字段') if lang=='zh' else key.replace('_',' ').capitalize()
        if isinstance(value,bool):value=('是' if value else '否') if lang=='zh' else ('Yes' if value else 'No')
        elif lang=='zh' and key in ('decision','method','field'):
            value={'confirmed':'已确认','rejected':'已驳回','accepted':'已采纳','rules':'规则方法','offline':'模板方法','revenue':'营业收入','net_profit':'净利润','gross_profit':'毛利润','cash':'货币资金','total_assets':'资产总额','total_liabilities':'负债总额'}.get(str(value),value)
        elif lang=='zh' and key=='version':value=re.sub(r'^v','',str(value))
        elif lang=='zh' and key=='status':value={'clean':'扫描通过','infected':'检测到风险','error':'扫描未完成','quarantined':'隔离待检'}.get(str(value),'已记录')
        rows.append((label,record(value,lang)))
    return rows
