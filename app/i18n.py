from flask import current_app, request

TEXT = {
    "en": {
        "title": "JDA Reporting Workspace", "brand": "Reporting Workspace",
        "readonly": "Read-only access", "logout": "Sign out", "footer": "Internal reporting tool",
        "language": "Language", "login_title": "Sign in to your workspace",
        "login_help": "Use the account created for you by your administrator.",
        "username": "Username", "password": "Password", "login": "Sign in",
        "login_invalid": "Incorrect username or password.",
        "login_throttled": "Too many attempts. Please try again in 15 minutes.",
        "home_title": "Query and export reports",
        "home_help": "Choose an authorized report to preview data or download a CSV.",
        "report": "Report", "limit": "Maximum rows", "preview": "Preview data", "export": "Export CSV",
        "limit_help": "Up to 1,000 rows per query. Results are not sorted and are limited previews, not complete business reports.",
        "no_reports": "No reports configured yet",
        "no_reports_help": "Ask your administrator to add authorized report views so you can query and export data.",
        "query_failed": "The query could not be completed. Ask your administrator to check the connection, permissions, or report configuration.",
        "rows": "{count} rows", "no_rows": "Query completed. No data was returned.",
        "report_date": "Report date", "warehouse": "Warehouse",
        "daily_limit_help": "Sorted by event time. Up to the selected row limit; reaching that limit may mean more results are available.",
        "daily_modified_help": "Loads whose current last-modified timestamp falls on this date. This is a temporary creation-date proxy; later edits can change the date.",
        "daily_dispatch_help": "Outbound dispatch events on this date, including loads created earlier. A load dispatched multiple times may appear more than once.",
    },
    "zh-CN": {
        "title": "JDA 报表工作台", "brand": "报表工作台", "readonly": "只读查询",
        "logout": "退出登录", "footer": "内部报表工具", "language": "语言",
        "login_title": "登录报表工作台", "login_help": "使用管理员为你创建的账号登录。",
        "username": "用户名", "password": "密码", "login": "登录",
        "login_invalid": "用户名或密码错误。", "login_throttled": "尝试次数过多，请 15 分钟后再试。",
        "home_title": "查询与导出报表", "home_help": "选择已授权的报表，预览数据或下载 CSV。",
        "report": "报表", "limit": "最多返回行数", "preview": "预览数据", "export": "导出 CSV",
        "limit_help": "单次最多 1,000 行；未指定排序，结果仅用于有限预览，不代表完整业务报表。",
        "no_reports": "还没有配置报表", "no_reports_help": "请联系管理员添加已授权的报表视图，然后即可查询和导出。",
        "query_failed": "查询未完成，请联系管理员检查连接、权限或报表配置。",
        "rows": "{count} 行", "no_rows": "查询完成，没有符合条件的数据。",
        "report_date": "报表日期", "warehouse": "仓库",
        "daily_limit_help": "按事件时间排序，最多返回所选行数；达到上限时可能还有更多结果。",
        "daily_modified_help": "查询当前最后修改时间落在当天的 load，暂作创建日期参考；后续修改会改变这个日期。",
        "daily_dispatch_help": "查询当天的 outbound dispatch 事件，包含此前创建的 load；重复 dispatch 会出现多条。",
    },
}

REPORT_LABELS = {
    "库存明细（预览）": "Inventory details (preview)",
    "订单（预览）": "Orders (preview)",
    "出货（预览）": "Shipments (preview)",
}


def language():
    chosen = request.cookies.get("jda_language")
    return chosen if chosen in TEXT else current_app.config["DEFAULT_LANGUAGE"]


def translate(key, **values):
    return TEXT[language()][key].format(**values)


def report_label(report):
    locale = language()
    localized = report.get("label_en" if locale == "en" else "label_zh")
    if localized:
        return localized
    label = report["label"]
    return REPORT_LABELS.get(label, label) if locale == "en" else label
