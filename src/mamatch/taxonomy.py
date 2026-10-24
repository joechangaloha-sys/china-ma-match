"""Sector and region vocabularies shared by buyer profiles, targets and matching.

Sectors are a deliberately small, adviser-friendly list grouped into narrow families, so that
adjacent sectors (same family, e.g. auto parts and metal fabrication) still score in matching. Map to GB/T 4754 or SW industry
codes later if buyers need finer filters.
"""

SECTORS: dict[str, tuple[str, str, str]] = {
    # code: (中文, English, family)
    "auto_parts": ("汽车零部件", "Auto parts", "mobility"),
    "machinery": ("通用/专用设备", "Machinery & equipment", "equipment"),
    "electronics": ("电子元器件", "Electronic components", "equipment"),
    "chemicals": ("化工新材料", "Chemicals & materials", "materials"),
    "metal_fab": ("金属制品加工", "Metal fabrication", "mobility"),
    "plastics": ("塑料与橡胶制品", "Plastics & rubber", "materials"),
    "packaging": ("包装印刷", "Packaging & printing", "packaging"),
    "textiles": ("纺织服装", "Textiles & apparel", "consumer"),
    "food": ("食品饮料", "Food & beverage", "consumer"),
    "consumer_goods": ("日用消费品", "Consumer goods", "consumer"),
    "medical_devices": ("医疗器械", "Medical devices", "healthcare"),
    "healthcare_services": ("医疗服务", "Healthcare services", "healthcare"),
    "software": ("软件与信息服务", "Software & IT services", "tech"),
    "industrial_services": ("工业服务(检测/维保)", "Industrial services", "services"),
    "logistics": ("物流仓储", "Logistics & warehousing", "services"),
    "b2b_distribution": ("工业品分销", "B2B distribution", "services"),
    "environmental": ("环保工程", "Environmental services", "services"),
    "education": ("职业教育培训", "Vocational training", "services"),
}

# Province -> macro-region. Yangtze River Delta is the MVP focus.
REGIONS: dict[str, str] = {
    "上海": "长三角", "江苏": "长三角", "浙江": "长三角", "安徽": "长三角",
    "广东": "珠三角", "福建": "东南",
    "北京": "京津冀", "天津": "京津冀", "河北": "京津冀",
    "山东": "华北", "河南": "华中", "湖北": "华中", "湖南": "华中", "江西": "华中",
    "四川": "西南", "重庆": "西南", "云南": "西南", "贵州": "西南",
    "陕西": "西北", "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
}

MACRO_REGIONS = list(dict.fromkeys(REGIONS.values()))

REGION_EN = {
    "长三角": "Yangtze River Delta", "珠三角": "Pearl River Delta", "东南": "Southeast", "京津冀": "Beijing–Tianjin–Hebei",
    "华北": "North China", "华中": "Central China", "西南": "Southwest", "西北": "Northwest", "东北": "Northeast",
    "中国": "China",
    "上海": "Shanghai", "江苏": "Jiangsu", "浙江": "Zhejiang", "安徽": "Anhui", "广东": "Guangdong", "福建": "Fujian",
    "北京": "Beijing", "天津": "Tianjin", "河北": "Hebei", "山东": "Shandong", "河南": "Henan", "湖北": "Hubei",
    "湖南": "Hunan", "江西": "Jiangxi", "四川": "Sichuan", "重庆": "Chongqing", "云南": "Yunnan", "贵州": "Guizhou",
    "陕西": "Shaanxi", "辽宁": "Liaoning", "吉林": "Jilin", "黑龙江": "Heilongjiang",
}

# Simple keyword map for the offline extractor (announcement titles and summaries).
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "auto_parts": ["汽车零部件", "汽配", "新能源汽车", "底盘", "热管理"],
    "machinery": ["设备", "装备", "机械", "自动化", "机床"],
    "electronics": ["电子", "元器件", "半导体", "PCB", "连接器", "传感器"],
    "chemicals": ["化工", "新材料", "涂料", "胶粘剂"],
    "metal_fab": ["金属", "铸造", "锻造", "钣金", "精密加工"],
    "plastics": ["塑料", "橡胶", "注塑"],
    "packaging": ["包装", "印刷"],
    "textiles": ["纺织", "服装", "面料"],
    "food": ["食品", "饮料", "乳业", "调味品"],
    "consumer_goods": ["日化", "家居", "消费品"],
    "medical_devices": ["医疗器械", "体外诊断", "耗材"],
    "healthcare_services": ["医院", "诊所", "医疗服务"],
    "software": ["软件", "信息技术", "SaaS", "数字化"],
    "industrial_services": ["检测", "维保", "认证", "工程服务"],
    "logistics": ["物流", "仓储", "供应链"],
    "b2b_distribution": ["分销", "贸易", "代理"],
    "environmental": ["环保", "固废", "水处理"],
    "education": ["职业教育", "培训"],
}

DEAL_TYPES = {
    "full_sale": "100%股权转让 / Full sale",
    "majority": "控股权转让 / Majority stake",
    "minority": "少数股权 / Minority stake",
    "asset_sale": "资产/业务转让 / Asset or business sale",
}

SALE_REASONS = {
    "succession": "创始人退休、无接班人 / Founder retiring, no successor",
    "strategic": "引入产业方做大 / Bring in an industrial partner",
    "focus": "剥离非核心业务 / Divest non-core business",
    "foreign_exit": "外资股东退出中国 / Foreign parent exiting China",
    "other": "其他 / Other",
}


PAYMENT_TERMS = {
    "cash": "交割时现金支付 Cash at closing",
    "cash_earnout": "现金为主，可接受部分对赌/分期 Mostly cash, earn-out or instalments possible",
    "flexible": "可协商 Open to discussion",
}

FOUNDER_TRANSITION = {
    "none": "交割后即退出 Leaves at closing",
    "6m": "留任约6个月协助交接 Stays about 6 months for handover",
    "12m": "留任约12个月 Stays about 12 months",
    "24m": "可留任2年以上 Can stay 2 years or more",
}

TIMING = {
    "asap": "尽快 As soon as possible",
    "6m": "6个月内 Within 6 months",
    "12m": "12个月内 Within 12 months",
    "flexible": "不急 No fixed timing",
}


BUYER_KINDS = {"listed": "上市公司 Listed company", "pe": "投资机构 Fund", "private": "非上市企业 Private company",
               "individual": "个人 Individual"}

FUNDING_EVIDENCE = {
    "bank_letter": "银行资信证明 Bank comfort letter",
    "account_statement": "账户余额证明 Account statement",
    "fund_commitment": "基金出资承诺 Fund commitment",
    "listed_company": "上市公司定期报告 Listed-company reports",
    "none": "暂未提供 Not yet provided",
}


def sector_label(code: str) -> str:
    zh, en, _ = SECTORS.get(code, (code, code, ""))
    return f"{zh} / {en}"


def sector_family(code: str) -> str:
    return SECTORS.get(code, ("", "", ""))[2]


def macro_region(province: str) -> str:
    return REGIONS.get(province, "")
