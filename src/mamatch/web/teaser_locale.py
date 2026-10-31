"""Localise the canonical teaser shell without introducing a second layout."""
from html import escape
from html.parser import HTMLParser

ZH = {
'Project Willow · Teaser Automation Demo':'柳树项目 · 项目简介演示',
'Fictional-data teaser automation demo for a China M&A listing platform.':'中小企业并购平台项目简介演示，所涉资料均为虚构。',
'mamatch navigation':'平台导航','← Back to mamatch':'← 返回并购平台',
'Kimi’s original standalone teaser · English · fictional data':'独立项目简介 · 中文版 · 虚构资料',
'Chinese edition →':'英文版 →','Info memo · NDA · LOI →':'信息备忘录 · 保密协议 · 收购意向书 →','Approval workflow →':'审核流程 →',
'Jump to controls':'跳至文档操作','Skip to teaser':'跳至项目简介','M&A Match demonstration platform':'中小企业并购演示平台','MA':'并购','M&A Match':'中小企业并购',
'Demo sections':'演示栏目','Teaser':'项目简介','Automation':'自动编排','Data spec':'数据说明','Deployment':'部署说明','Fictional data':'虚构资料',
'Teaser automation v0.1':'项目简介自动编排 · 版本0.1','Project Willow':'柳树项目',
'A fictional teaser rendered from structured demonstration data. The layout separates buyer-facing content from provenance, checks and release controls.':'本页根据结构化虚构资料生成项目简介，分别展示投资方阅览内容、资料来源、核查结果及对外提供控制。',
'Current release state':'当前文档状态','Release state':'文档状态','Fictional preview':'虚构场景预览',
'Illustrative approval records only · no live publication':'审核记录仅为示例 · 未对外提供',
'Confidential business-sale teaser':'企业股权转让项目简介 · 保密资料','Demonstration data only':'仅限虚构演示资料',
'Loading teaser data…':'正在加载项目资料……','Control room':'演示控制台','Teaser automation':'项目简介自动编排',
'Deterministic rendering and illustrative source-claim checks. This page does not approve or publish deals.':'按固定规则编排文档，并展示陈述与来源的对应核查。本页不产生交易批准或对外提供授权。',
'Demo actions':'演示操作','Render teaser':'生成项目简介','Run checks':'执行核查','Copy teaser':'复制简介正文','Download JSON':'下载结构化资料','Print / save PDF':'打印或另存文档','Awaiting action.':'等待操作。',
'Approval workflow':'审核流程','Structured data':'结构化资料','Five source claims loaded':'已加载五项示例陈述','Anonymity check':'匿名化核查','No direct identifiers detected':'未检出直接识别信息',
'Seller confirmation':'卖方确认','15 Oct 2026 · 10:30 CST':'2026年10月15日 · 北京时间10:30','Internal approval':'内部审核','16 Oct 2026 · deal manager':'2026年10月16日 · 项目负责人',
'WeChat alert card':'微信项目推送卡片','New matching listing':'新增匹配项目','Industrial services · East China':'工业服务 · 华东地区','Revenue':'营业收入','RMB 25m–40m':'人民币2,500万元至4,000万元','Adjusted EBITDA':'经调整的息税折旧及摊销前利润','RMB 4m–7m':'人民币400万元至700万元','Review teaser':'查看项目简介',
'Illustrative alert only. Production WeChat delivery requires the verified account and active user subscription.':'仅展示推送卡片样式。正式微信推送须完成账号认证，并取得用户有效订阅授权。',
'Technical panels':'资料及核查面板','Checks':'核查结果','Data':'结构化资料','Rules':'编排规则','Run checks to inspect the current teaser record.':'请执行核查以查看当前示例资料。','Loading JSON…':'正在加载结构化资料……',
'Every public figure must match the approved input record.':'对外提供的每项数据均应与获批资料一致。',
'Demo highlights reference illustrative claim IDs; this does not verify supporting evidence.':'项目要点与示例陈述编号对应，不代表已核实支持性资料。',
'Verification wording is inserted deterministically.':'核查说明按固定规则插入。',
'Seller and internal approvals are required in the server-side workflow before real publication.':'正式对外提供前，须在业务系统中完成卖方确认及内部审核。',
'Any post-approval edit creates a new teaser version.':'获批后修改内容，应形成新版本并重新审核。',
'Structured contract':'结构化资料规范','Data specification':'数据字段说明','The public teaser is assembled from controlled field groups rather than free-form AI output.':'项目简介由受控字段组编排生成，不采用人工智能自由生成的文本。',
'Identity':'项目基本信息','Project code, headline, sector, broad region, service categories and customer mix.':'项目代号、标题、所属行业、概括性地区、服务类别及客户结构。',
'Transaction':'交易安排','Transaction type, stake description, process timeline, buyer types and NDA requirement.':'交易方式、拟转让股权、流程安排、潜在投资方类型及保密协议要求。',
'Financial':'财务及经营指标','Period, currency, revenue range, profit metric, employee range and site range.':'报告期间、币种、营业收入区间、盈利指标、员工人数区间及经营网点数量。',
'Verification':'资料核查','Claim IDs, reviewer role, checks completed, information date and approval records.':'陈述编号、审核人员角色、已完成核查事项、资料基准日及审核记录。',
'Tencent Lighthouse demo':'腾讯云轻量应用服务器演示','Deployment boundary':'部署及使用范围',
'This is Kimi’s original standalone fictional-data prototype, now served inside the passcode-gated mamatch Tencent Lighthouse demo. Its layout, rendering controls, JSON download and print/PDF view are preserved. It contains no real seller information, AI calls or confidential documents.':'本页与英文版共用独立项目简介的页面结构、编排功能及样式，通过并购平台的腾讯云演示访问密码验证后提供。支持生成简介、资料下载及打印，不包含真实卖方信息、人工智能调用或机密文件。',
'Browser checks here are demonstrations only. Real claim/evidence review, version-bound approval and publication gates belong to the separate server-side mandate workflow. This page never calls those publication actions.':'浏览器核查仅用于演示。真实项目的陈述及依据核验、版本审核和对外提供控制，应在业务系统的委托项目流程中完成。本页不调用任何对外提供操作。',
'Demonstration teaser using fictional data. Not an offer, recommendation, valuation or guarantee.':'本项目简介使用虚构资料，仅供演示，不构成要约、投资建议、估值意见或任何保证。','Back to top':'返回顶部',
}

class ChineseShell(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
    def handle_decl(self, decl):
        self.output.append('<!' + decl + '>')
    def handle_starttag(self, tag, attrs):
        translated = []
        for key, value in attrs:
            if value is None:
                translated.append(key); continue
            if key == 'lang': value = 'zh-CN'
            elif key in ('aria-label', 'content') and value in ZH: value = ZH[value]
            elif key == 'href' and value.startswith('/en/'): value = value.replace('/en/', '/zh/', 1)
            elif key == 'href' and value == '/zh/teaser-demo/': value = '/en/teaser-demo/'
            translated.append(f'{key}="{escape(value, quote=True)}"')
        self.output.append('<' + tag + (' ' if translated else '') + ' '.join(translated) + '>')
    def handle_endtag(self, tag): self.output.append('</' + tag + '>')
    def handle_data(self, data):
        text = data.strip()
        if text.isdigit():
            self.output.append(text); return
        if not text:
            self.output.append(data); return
        if text not in ZH:
            raise ValueError(f'Missing Chinese teaser shell translation: {text}')
        self.output.append(escape(ZH[text]))


def chinese_shell(html):
    parser = ChineseShell(); parser.feed(html)
    return ''.join(parser.output)
