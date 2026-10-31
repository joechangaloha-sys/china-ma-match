"""Approved display terminology for the mainland Chinese edition.

Only application-authored labels pass through here; stored deal data is not rewritten.
"""
import re

TERMS = {
    'Project Willow': '柳树项目', 'Project Jade': '玉石项目', 'Project Delta': '德尔塔项目', 'Project Kiln': '窑炉项目',
    'Project Harbour': '港湾项目', 'Project Harbor': '港湾项目',
    'BizBuySell': '美国企业买卖平台', 'Axial': '美国中型企业交易平台',
    'business broker': '企业转让经纪机构', 'Kimi': '原型',
    'EBITDA': '息税折旧及摊销前利润', 'NDA': '保密协议', 'LOI': '收购意向书',
    'VDR': '虚拟资料室', 'PDF': '便携式文档', 'AI': '人工智能', 'RMB': '人民币',
    'MAMATCH': '中小企业并购平台', 'mamatch': '中小企业并购平台',
    'UTC': '协调世界时',
}

def mainland(text):
    if not isinstance(text, str):
        return text
    if not re.search(r'[\u4e00-\u9fff]', text) and text not in TERMS:
        return text
    for source, target in TERMS.items():
        text = re.sub(r'(?<![A-Za-z])' + re.escape(source) + r'(?![A-Za-z])', target, text)
    text = text.replace('交易经理', '项目负责人').replace('尽调', '尽职调查').replace('成交价', '交易对价')
    return re.sub(r'(?<=[\u4e00-\u9fff]) +(?=[\u4e00-\u9fff])', '', text)
