# -*- coding: utf-8 -*-
"""
功能配置注册表
读取 features.yaml，提供功能启用状态查询 + 导航树生成
"""
from pathlib import Path
from typing import Any
import os

# ── 功能定义 ──
# key: features.yaml 中的功能标识符
# 每个功能包含：
#   label       — 中文显示名称
#   group       — 导航分组
#   icon        — SVG 图标 ID
#   page_path   — 页面路由路径（None 表示无独立页面）
#   routers     — app.include_router 对应的路由器变量
#   resources   — _RESOURCE_CN_MAP 中对应的 key
#   has_detail  — 是否有详情页（如 /members/{id}）
#   exact_match — 导航高亮是否精确匹配路径

FEATURE_DEFS: dict[str, dict[str, Any]] = {
    # ── 会员 ──
    "member": {
        "label": "会员管理", "group": "会员", "icon": "users",
        "page_path": "/members",
        "routers": ["member"],
        "resources": ["members"],
        "has_detail": True,
    },
    "member_assets": {
        "label": "资产残值", "group": "会员",
        "page_path": "/member-assets",
        "routers": ["asset_value"],
        "resources": [],
    },
    "recharge": {
        "label": "会员充值", "group": "会员",
        "page_path": "/recharges",
        "routers": ["recharge"],
        "resources": ["recharges"],
    },
    "body_measurement": {
        "label": "体测记录", "group": "会员",
        "page_path": "/body-measurements",
        "routers": ["body_measurement"],
        "resources": ["body-measurements"],
    },
    "membership_card": {
        "label": "会籍卡", "group": "会员",
        "page_path": "/membership-cards",
        "routers": ["membership_card"],
        "resources": ["membership-cards"],
    },
    # ── 课程 ──
    "course": {
        "label": "课程管理", "group": "课程", "icon": "book",
        "page_path": "/courses",
        "routers": ["course"],
        "resources": ["courses"],
    },
    "package": {
        "label": "课程包管理", "group": "课程",
        "page_path": "/packages",
        "routers": ["package"],
        "resources": ["packages"],
    },
    "sale": {
        "label": "售课记录", "group": "课程",
        "page_path": "/sales",
        "routers": ["sale"],
        "resources": ["sales"],
    },
    "class_record": {
        "label": "上课记录", "group": "课程",
        "page_path": "/class-records",
        "routers": ["class_record"],
        "resources": ["class-records"],
    },
    "product": {
        "label": "商品零售", "group": "课程",
        "page_path": "/products",
        "routers": ["product"],
        "resources": ["products", "product-sales"],
    },
    # ── 进场 ──
    "checkin": {
        "label": "进场核销", "group": "进场", "icon": "check-circle",
        "page_path": "/checkin",
        "routers": ["checkin"],
        "resources": ["checkins"],
    },
    "booking": {
        "label": "预约管理", "group": "进场",
        "page_path": "/booking",
        "routers": ["booking"],
        "resources": ["booking"],
    },
    "wristband": {
        "label": "手环管理", "group": "进场",
        "page_path": "/wristband",
        "routers": [],
        "resources": ["wristbands"],
    },
    # ── 员工 ──
    "staff": {
        "label": "员工管理", "group": "员工", "icon": "user",
        "page_path": "/staff",
        "routers": ["staff"],
        "resources": ["staff"],
    },
    "schedule": {
        "label": "教练排班", "group": "员工",
        "page_path": "/schedule",
        "routers": ["schedule"],
        "resources": [],
    },
    "commission": {
        "label": "梯度提成", "group": "员工",
        "page_path": "/commission",
        "routers": ["commission"],
        "resources": ["commission"],
    },
    # ── 财务 ──
    "finance": {
        "label": "收支报表", "group": "财务", "icon": "currency-dollar",
        "page_path": "/finance",
        "routers": ["finance"],
        "resources": ["finance"],
    },
    "finance_review": {
        "label": "支出审核", "group": "财务",
        "page_path": "/finance-review",
        "routers": ["finance_review"],
        "resources": ["finance-review"],
    },
    "finance_budget": {
        "label": "预算管理", "group": "财务",
        "page_path": "/finance-budget",
        "routers": ["finance_budget"],
        "resources": ["finance-budget"],
    },
    "finance_profit": {
        "label": "利润表", "group": "财务",
        "page_path": "/finance-profit",
        "routers": ["finance_profit"],
        "resources": ["finance-profit"],
    },
    "performance": {
        "label": "业绩统计", "group": "财务",
        "page_path": "/performance",
        "routers": ["performance"],
        "resources": [],
    },
    "analytics": {
        "label": "数据分析看板", "group": "财务",
        "page_path": "/analytics",
        "routers": ["analytics"],
        "resources": ["analytics"],
    },
    # ── 系统 ──
    "alert": {
        "label": "到期提醒", "group": "系统", "icon": "cog",
        "page_path": "/alerts",
        "routers": ["alert"],
        "resources": ["alerts"],
    },
    "log": {
        "label": "操作日志", "group": "系统",
        "page_path": "/logs",
        "routers": ["operation_log"],
        "resources": [],
    },
    "export_data": {
        "label": "数据导出", "group": "系统",
        "page_path": "/export",
        "routers": ["export_data"],
        "resources": ["export"],
    },
    "import_data": {
        "label": "数据导入", "group": "系统",
        "page_path": "/import",
        "routers": ["import_data"],
        "resources": [],
    },
    "chat": {
        "label": "AI 助手", "group": "系统",
        "page_path": "/chat",
        "routers": ["chat_router"],
        "resources": ["chat"],
    },
}

# ── 导航树 ──
# 与 base.html 的 6 个分组一致
NAV_TREE: list[dict[str, Any]] = [
    {
        "group": "会员", "icon": "users",
        "items": [
            {"label": "会员管理",     "feature": "member"},
            {"label": "资产残值",     "feature": "member_assets"},
            {"label": "会员充值",     "feature": "recharge"},
            {"label": "体测记录",     "feature": "body_measurement"},
            {"label": "会籍卡",       "feature": "membership_card"},
        ],
    },
    {
        "group": "课程", "icon": "book",
        "items": [
            {"label": "课程管理",     "feature": "course"},
            {"label": "课程包管理",   "feature": "package", "path": "/packages?v=4"},
            {"label": "售课记录",     "feature": "sale"},
            {"label": "上课记录",     "feature": "class_record"},
            {"label": "商品零售",     "feature": "product"},
        ],
    },
    {
        "group": "进场", "icon": "check-circle",
        "items": [
            {"label": "进场核销",     "feature": "checkin"},
            {"label": "预约管理",     "feature": "booking"},
            {"label": "手环管理",     "feature": "wristband"},
        ],
    },
    {
        "group": "员工", "icon": "user",
        "items": [
            {"label": "员工管理",     "feature": "staff"},
            {"label": "教练排班",     "feature": "schedule"},
            {"label": "梯度提成",     "feature": "commission"},
        ],
    },
    {
        "group": "财务", "icon": "currency-dollar",
        "items": [
            {"label": "收支报表",     "feature": "finance"},
            {"label": "支出审核",     "feature": "finance_review"},
            {"label": "预算管理",     "feature": "finance_budget"},
            {"label": "利润表",       "feature": "finance_profit"},
            {
                "type": "section", "label": "业绩总览", "icon": "chart-bar",
                "children": [
                    {"label": "业绩总览",   "feature": "performance"},
                    {"label": "售课业绩",   "feature": "performance_sales", "path": "/performance/sales"},
                    {"label": "课程包业绩", "feature": "performance_packages", "path": "/performance/packages"},
                    {"label": "会籍卡业绩", "feature": "performance_cards", "path": "/performance/cards"},
                    {"label": "进场统计",   "feature": "performance_checkins", "path": "/performance/checkins"},
                ],
            },
            {"label": "数据分析看板", "feature": "analytics"},
        ],
    },
    {
        "group": "系统", "icon": "cog",
        "items": [
            {"label": "到期提醒",     "feature": "alert"},
            {"label": "操作日志",     "feature": "log"},
            {"label": "数据导出",     "feature": "export_data"},
            {"label": "数据导入",     "feature": "import_data"},
            {"label": "AI 助手",      "feature": "chat"},
        ],
    },
]

# 性能相关子功能（跟随主 performance 开关）
_PERFORMANCE_SUB_FEATURES = {"performance_sales", "performance_packages", "performance_cards", "performance_checkins"}

# 始终启用的功能（认证/系统核心）
_ALWAYS_ENABLED = {"auth", "dashboard", "mcp"}

# ── 路径 → feature key 映射（用于导航高亮）──
_PATH_TO_FEATURE: dict[str, str] = {}
for _key, _def in FEATURE_DEFS.items():
    if _def.get("page_path"):
        _PATH_TO_FEATURE[_def["page_path"]] = _key
# 额外注册性能子页面路径 → performance
_PATH_TO_FEATURE["/performance/sales"] = "performance"
_PATH_TO_FEATURE["/performance/packages"] = "performance"
_PATH_TO_FEATURE["/performance/cards"] = "performance"
_PATH_TO_FEATURE["/performance/checkins"] = "performance"
_PATH_TO_FEATURE["/import"] = "import_data"

# 子路径匹配（用于导航高亮）
_SUBPATH_MAP: dict[str, str] = {
    "/performance": "performance",
}


class FeatureRegistry:
    """功能注册表 — 读取 features.yaml，提供启用状态查询"""

    def __init__(self, yaml_path: str | None = None):
        self._enabled: dict[str, bool] = {}
        self._yaml_path = yaml_path or str(
            Path(__file__).parent / "features.yaml"
        )
        self._load()

    def _load(self):
        """加载 features.yaml"""
        # 默认全部启用
        for key in FEATURE_DEFS:
            self._enabled[key] = True

        yaml_path = self._yaml_path
        if not os.path.isfile(yaml_path):
            return  # 配置文件不存在，全部默认启用

        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return
            for key, val in data.items():
                if key in FEATURE_DEFS:
                    self._enabled[key] = bool(val)
        except Exception as exc:
            print(f"[feature_registry] 加载 features.yaml 失败: {exc}")
            print("[feature_registry] 回退到全功能模式")

    def is_enabled(self, feature_key: str) -> bool:
        """判断功能是否启用"""
        # 性能子功能跟随主开关
        if feature_key in _PERFORMANCE_SUB_FEATURES:
            return self._enabled.get("performance", True)
        if feature_key in _ALWAYS_ENABLED:
            return True
        return self._enabled.get(feature_key, True)

    def get_enabled_features(self) -> set[str]:
        """返回所有已启用的功能 key 集合"""
        result = set()
        for key in FEATURE_DEFS:
            if self.is_enabled(key):
                result.add(key)
        return result

    def get_nav_tree(self) -> list[dict[str, Any]]:
        """返回过滤后的导航树（只包含已启用的功能），注入路径信息"""
        filtered = []
        for group in NAV_TREE:
            items = self._filter_nav_items(group["items"])
            if items:
                filtered.append({
                    "group": group["group"],
                    "icon": group["icon"],
                    "items": items,
                })
        return filtered

    def _inject_path(self, item: dict) -> dict:
        """为导航条目注入 path（从 FEATURE_DEFS 查找）"""
        if "path" in item:
            return item
        feature = item.get("feature", "")
        if feature in FEATURE_DEFS:
            pp = FEATURE_DEFS[feature].get("page_path", "")
            if pp:
                item = {**item, "path": pp}
        return item

    def _filter_nav_items(self, items: list) -> list:
        """递归过滤导航条目"""
        result = []
        for item in items:
            if item.get("type") == "section":
                children = self._filter_nav_items(item.get("children", []))
                if children:
                    result.append({**item, "children": children})
            else:
                feature = item.get("feature", "")
                if self.is_enabled(feature):
                    result.append(self._inject_path(item))
        return result

    def get_active_routers(self) -> set[str]:
        """返回需要注册的 router 变量名集合"""
        routers = set()
        for key in FEATURE_DEFS:
            if self.is_enabled(key):
                for r in FEATURE_DEFS[key].get("routers", []):
                    routers.add(r)
        return routers

    def get_active_resource_map(self) -> dict[str, str]:
        """返回过滤后的 _RESOURCE_CN_MAP"""
        _RESOURCE_CN_MAP = {
            "members": "会员", "staff": "员工", "courses": "课程",
            "sales": "售课记录", "class-records": "上课记录", "checkins": "进场记录",
            "wristbands": "手环", "body-measurements": "体测记录", "recharges": "充值记录",
            "alerts": "到期提醒", "membership-cards": "会籍卡", "products": "商品",
            "product-sales": "商品零售", "finance": "财务",
            "commission": "提成管理", "booking": "预约管理",
            "packages": "课程包", "export": "数据导出",
            "mcp": "MCP 工具", "chat": "AI 对话",
            "system": "系统设置",
            "finance-review": "财务审核", "finance-budget": "预算管理",
            "finance-profit": "利润表", "analytics": "数据分析",
        }
        # 收集所有已启用功能对应的 resource key
        active_resources = set()
        for key in FEATURE_DEFS:
            if self.is_enabled(key):
                active_resources.update(FEATURE_DEFS[key].get("resources", []))
        return {k: v for k, v in _RESOURCE_CN_MAP.items() if k in active_resources}

    def get_feature_for_path(self, path: str) -> str | None:
        """根据请求路径获取对应的 feature key"""
        # 精确匹配
        if path in _PATH_TO_FEATURE:
            return _PATH_TO_FEATURE[path]
        # 子路径匹配（如 /performance/sales → performance）
        for prefix, feature in _SUBPATH_MAP.items():
            if path.startswith(prefix) and path != prefix:
                return feature
        return None

    def get_group_names(self) -> list[str]:
        """返回导航分组名称列表（供 JS 使用）"""
        return [g["group"] for g in self.get_nav_tree()]


# 模块级单例
registry = FeatureRegistry()
