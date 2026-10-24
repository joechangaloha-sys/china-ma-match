"""Example data so the workspace opens in a realistic state.

All records here are fictional and flagged is_example; the UI labels them. Real buyers come
from `mamatch ingest-cninfo`; real targets are entered by advisers.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AdviserFirm, Buyer, BuyerSignal, Target

NOW = datetime.now(timezone.utc)

EXAMPLE_BUYERS = [
    dict(name="示例·华东精密科技", kind="listed", province="江苏", sectors=["auto_parts"],
         target_sectors=["auto_parts", "metal_fab"], target_regions=["江苏", "浙江", "安徽"],
         deal_size_min=40, deal_size_max=300, rationale="补强新能源汽车热管理零部件产能，向长三角整合中小供应商。",
         signal=("关于收购某汽车零部件公司60%股权的公告", 45)),
    dict(name="示例·浙东新材料", kind="listed", province="浙江", sectors=["chemicals"],
         target_sectors=["chemicals", "plastics"], target_regions=["浙江", "山东"],
         deal_size_min=50, deal_size_max=200, rationale="延伸功能性涂料产业链，收购区域性配方企业。",
         signal=("关于收购某新材料科技有限公司控制权的公告", 20)),
    dict(name="示例·长江产业并购基金", kind="pe", province="上海", sectors=[],
         target_sectors=["machinery", "industrial_services", "electronics"], target_regions=[],
         deal_size_min=30, deal_size_max=150, rationale="专注长三角制造业传承类控股收购，平台化整合。",
         signal=None),
    dict(name="示例·苏南智能装备", kind="listed", province="江苏", sectors=["machinery"],
         target_sectors=["machinery", "electronics"], target_regions=["江苏", "上海"],
         deal_size_min=80, deal_size_max=500, rationale="收购细分领域自动化设备商以补齐产品线。",
         signal=("关于签署股权收购意向协议的公告", 400)),
    dict(name="示例·粤港检测认证", kind="listed", province="广东", sectors=["industrial_services"],
         target_sectors=["industrial_services"], target_regions=["广东", "福建"],
         deal_size_min=20, deal_size_max=100, rationale="区域实验室网络扩张。",
         signal=("关于收购某检测技术有限公司100%股权的公告", 90)),
    dict(name="示例·皖江食品", kind="listed", province="安徽", sectors=["food"],
         target_sectors=["food", "packaging"], target_regions=["安徽", "江苏"],
         deal_size_min=30, deal_size_max=120, rationale="并购区域调味品品牌，扩充渠道。",
         signal=("关于购买资产暨收购某食品公司股权的公告", 800)),
]

EXAMPLE_TARGETS = [
    dict(code_name="Project Jade", legal_name="示例宁波恒泰汽车部件有限公司", short_name="恒泰部件",
         owner_name="王建国", city="宁波市", province="浙江", sector="auto_parts",
         founded_year=2003, employees=180, revenue=126.0, net_profit=11.5, asking_value=90.0,
         deal_type="full_sale", sale_reason="succession", brands=["恒泰"],
         description="恒泰部件由王建国于2003年在宁波创办，生产汽车空调管路及热交换器支架，主要客户为两家合资整车厂的一级供应商。"
                     "创始人62岁，子女在海外不愿接班。工厂自有土地约25亩，IATF16949认证。"),
    dict(code_name="Project Kiln", legal_name="示例无锡新锐涂层材料有限公司", short_name="新锐涂层",
         owner_name="李梅", city="无锡市", province="江苏", sector="chemicals",
         founded_year=2011, employees=65, revenue=48.0, net_profit=6.2, asking_value=45.0,
         deal_type="majority", sale_reason="strategic", brands=[],
         description="工业防腐涂料配方企业，服务长三角钢结构与风电塔筒客户，拥有12项发明专利。创始人希望引入产业方做大并保留30%股权。"),
]


def seed(session: Session) -> None:
    firm = session.scalar(select(AdviserFirm).limit(1))
    if firm is None:
        firm = AdviserFirm(name="示例·长三角并购顾问事务所", city="上海")
        session.add(firm)
        session.flush()

    if not session.scalar(select(Buyer.id).where(Buyer.is_example)):
        for i, spec in enumerate(EXAMPLE_BUYERS):
            spec = dict(spec)
            signal = spec.pop("signal")
            buyer = Buyer(source="example", external_id=f"EX{i:03d}", is_example=True, **spec)
            session.add(buyer)
            if signal:
                title, days_ago = signal
                session.add(BuyerSignal(buyer=buyer, kind="announcement", title=title,
                                        url=f"example://{i}", published_at=NOW - timedelta(days=days_ago),
                                        extracted={"generated_by": "example"}))

    if not session.scalar(select(Target.id).where(Target.is_example)):
        for spec in EXAMPLE_TARGETS:
            session.add(Target(firm=firm, is_example=True, **spec))
    session.flush()
