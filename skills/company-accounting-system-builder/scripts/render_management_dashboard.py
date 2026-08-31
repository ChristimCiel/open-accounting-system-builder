#!/usr/bin/env python3
"""Render the human dashboard deterministically from management-report.json."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _amount(value, currency: str, language: str) -> str:
    if value is None or str(value).strip() == "":
        return "—"
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return "—"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{number:,.2f}"


def _per_100(value, revenue) -> str:
    try:
        denominator = Decimal(str(revenue))
        numerator = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return "—"
    if denominator == 0:
        return "N/A"
    return f"{(numerator / denominator * Decimal('100')):.2f}"


def _line_map(report_data) -> dict[str, dict]:
    return {
        str(item.get("line_id", "")): item
        for item in report_data.get("lines", [])
        if isinstance(item, dict)
    }


def render_management_dashboard(config, report_data) -> str:
    language = str(config.get("display_language", "zh-TW")) if isinstance(config, dict) else "zh-TW"
    english = language == "en"
    currency = str(report_data.get("reporting_currency", ""))
    lines = _line_map(report_data)

    def management(line_id: str):
        return lines.get(line_id, {}).get("management_amount")

    def financial(line_id: str):
        return lines.get(line_id, {}).get("financial_amount")

    def adjustment(line_id: str):
        return lines.get(line_id, {}).get("management_adjustment")

    net_revenue = management("NET_REVENUE")
    cash = report_data.get("cash_summary", {}) if isinstance(report_data.get("cash_summary"), dict) else {}
    available_cash = cash.get("available_cash") if cash.get("status") == "COMPLETE" else None
    cash_display = _amount(available_cash, currency, language) if available_cash is not None else ("Not enabled" if english else "未啟用")

    if english:
        labels = {
            "title": "Owner Management Dashboard",
            "summary": "30-second owner summary",
            "revenue": "Management-basis net revenue",
            "gross_per_100": "Management-basis gross profit per 100 revenue",
            "financial_net_profit": "Ledger accrual net profit / loss",
            "adjustment": "Management adjustment",
            "net_profit": "Management-basis net profit / loss",
            "cash": "Ledger-classified available cash",
            "cash_amount": "Ledger-classified amount",
            "exception_amount": "Exception amount",
            "waterfall": "How much remains from each 100 of management-basis revenue",
            "stage": "Stage",
            "amount": "Management-basis amount",
            "financial_amount": "Ledger accrual amount",
            "adjustment_amount": "Management adjustment",
            "per100": "Per 100 management-basis revenue",
            "status": "Data status",
            "cost": "Where costs are",
            "account": "Account",
            "nature": "Nature",
            "trace": "Traceability",
            "behavior": "Behavior",
            "dimension": "Management-basis profit by selected dimension",
            "dimension_name": "Dimension",
            "gross_profit": "Management-basis gross profit / loss",
            "cash_section": "Cash view kept separate from profit",
            "metric": "Metric",
            "basis": "Basis / source",
            "actions": "What to do next",
            "priority": "Priority",
            "action": "Action",
            "why": "Why",
            "owner": "Owner",
            "due": "Due",
            "trust": "What can be trusted and what is incomplete",
            "check": "Check",
            "count": "Count",
            "impact": "Impact",
            "source": "Source",
            "reviewer": "Professional reviewer",
            "reviewed_at": "Professional review time",
            "review_scope": "Professional review scope",
            "disclaimer": "> Internal management output generated from management-report.json. Ledger accrual profit, management adjustments, cash, tax, budget, and forecasts are not interchangeable. It is not a statutory financial statement; it is professionally reviewed only when the status and full written-review scope above say so.",
        }
    else:
        labels = {
            "title": "老闆經營儀表板",
            "summary": "30 秒經營摘要",
            "revenue": "本期管理口徑營業收入淨額",
            "gross_per_100": "每 100 元管理口徑收入留下的毛利",
            "financial_net_profit": "帳載權責淨利／淨損",
            "adjustment": "管理調整",
            "net_profit": "管理調整後淨利／淨損",
            "cash": "依帳載分類可動用現金",
            "cash_amount": "帳載分類金額",
            "exception_amount": "例外影響金額",
            "waterfall": "每 100 元管理口徑收入最後留下多少",
            "stage": "階段",
            "amount": "管理口徑金額",
            "financial_amount": "帳載權責金額",
            "adjustment_amount": "管理調整",
            "per100": "每 100 元管理口徑收入",
            "status": "資料狀態",
            "cost": "成本在哪裡",
            "account": "科目",
            "nature": "成本性質",
            "trace": "可追溯性",
            "behavior": "成本習性",
            "dimension": "產品、專案、門市或通路的管理口徑獲利",
            "dimension_name": "維度",
            "gross_profit": "管理口徑毛利／毛損",
            "cash_section": "與損益分開的現金視圖",
            "metric": "指標",
            "basis": "口徑／來源",
            "actions": "今天要處理",
            "priority": "優先",
            "action": "要做什麼",
            "why": "為什麼重要",
            "owner": "負責人",
            "due": "截止日",
            "trust": "這份報表可以信到什麼程度",
            "check": "檢查",
            "count": "筆數",
            "impact": "可能影響",
            "source": "來源",
            "reviewer": "專業覆核者",
            "reviewed_at": "專業覆核時間",
            "review_scope": "專業覆核範圍",
            "disclaimer": "> 本檔由 management-report.json 固定生成，屬內部管理輸出。帳載權責損益、管理調整、現金、稅務、預算與預測不可互換；本檔不是法定財務報表，只有上方狀態與完整書面覆核範圍同時明示時，才表示已專業覆核。",
        }

    professional_review = report_data.get("professional_review", {})
    if not isinstance(professional_review, dict):
        professional_review = {}
    scope = professional_review.get("scope", {})
    covered_areas = scope.get("covered_areas", []) if isinstance(scope, dict) else []
    review_status = str(professional_review.get("status", "NOT_REVIEWED"))
    reviewer_display = str(professional_review.get("reviewer_id", "")) if review_status == "REVIEWED" else "—"
    reviewed_at_display = str(professional_review.get("reviewed_at", "")) if review_status == "REVIEWED" else "—"
    review_scope_display = ", ".join(str(area) for area in covered_areas) if covered_areas else "—"

    output = [
        f"# {labels['title']}",
        "",
        f"- Report ID: {report_data.get('report_id', '')}",
        f"- Report revision: {report_data.get('revision', '')}",
        f"- Period: {report_data.get('period_start', '')} to {report_data.get('period_end', '')}",
        f"- As of: {report_data.get('as_of', '')}",
        f"- Basis: {report_data.get('basis', '')}",
        f"- Currency: {currency}",
        f"- Status: {report_data.get('status', '')}",
        f"- {labels['reviewer']}: {reviewer_display}",
        f"- {labels['reviewed_at']}: {reviewed_at_display}",
        f"- {labels['review_scope']}: {review_scope_display}",
        f"- Data refreshed at: {report_data.get('generated_at', '')}",
        "",
        f"## {labels['summary']}",
        "",
        f"| {labels['revenue']} | {labels['financial_net_profit']} | {labels['adjustment']} | {labels['net_profit']} | {labels['cash']} |",
        "|---:|---:|---:|---:|---:|",
        f"| {_amount(net_revenue, currency, language)} | {_amount(financial('NET_PROFIT'), currency, language)} | {_amount(adjustment('NET_PROFIT'), currency, language)} | {_amount(management('NET_PROFIT'), currency, language)} | {cash_display} |",
        "",
        f"## {labels['waterfall']}",
        "",
        f"| {labels['stage']} | {labels['financial_amount']} | {labels['adjustment_amount']} | {labels['amount']} | {labels['per100']} | {labels['status']} |",
        "|---|---:|---:|---:|---:|---|",
    ]
    waterfall = (
        ("NET_REVENUE", labels["revenue"]),
        ("COST_OF_SALES", "Operating costs" if english else "歸屬本期收入的營業成本"),
        ("GROSS_PROFIT", "Gross profit / loss" if english else "營業毛利／毛損"),
        ("OPERATING_EXPENSE", "Operating expenses" if english else "營業費用"),
        ("OPERATING_PROFIT", "Operating profit / loss" if english else "營業利益／損失"),
        ("NET_PROFIT", labels["net_profit"]),
    )
    for line_id, label in waterfall:
        line = lines.get(line_id, {})
        output.append(
            f"| {label} | {_amount(line.get('financial_amount'), currency, language)} | {_amount(line.get('management_adjustment'), currency, language)} | {_amount(line.get('management_amount'), currency, language)} | {_per_100(line.get('management_amount'), net_revenue)} | {line.get('data_status', '')} |"
        )

    output.extend(["", f"## {labels['cost']}", "", f"| {labels['account']} | {labels['financial_amount']} | {labels['adjustment_amount']} | {labels['amount']} | {labels['nature']} | {labels['trace']} | {labels['behavior']} | {labels['status']} |", "|---|---:|---:|---:|---|---|---|---|"])
    for item in report_data.get("cost_breakdown", []):
        if not isinstance(item, dict):
            continue
        output.append(
            f"| {item.get('account_code', '')} | {_amount(item.get('financial_amount'), currency, language)} | {_amount(item.get('management_adjustment'), currency, language)} | {_amount(item.get('management_amount'), currency, language)} | {item.get('cost_nature', '')} | {item.get('traceability', '')} | {item.get('cost_behavior', '')} | {item.get('data_status', '')} |"
        )
    if not report_data.get("cost_breakdown"):
        output.append("| — | — | — | — | — | — | — | — |")

    output.extend(["", f"## {labels['dimension']}", "", f"| {labels['dimension_name']} | {labels['revenue']} | {labels['gross_profit']} | {labels['net_profit']} | {labels['status']} |", "|---|---:|---:|---:|---|"])
    for item in report_data.get("dimension_summary", []):
        if not isinstance(item, dict):
            continue
        amounts = item.get("management_amounts", item.get("financial_amounts", {}))
        output.append(
            f"| {item.get('dimension_name', '')} | {_amount(amounts.get('NET_REVENUE'), currency, language)} | {_amount(amounts.get('GROSS_PROFIT'), currency, language)} | {_amount(amounts.get('NET_PROFIT'), currency, language)} | {item.get('data_status', '')} |"
        )
    if not report_data.get("dimension_summary"):
        output.append("| — | — | — | — | NOT_ENABLED |")

    output.extend(["", f"## {labels['cash_section']}", "", f"| {labels['metric']} | {labels['cash_amount']} | As of | {labels['basis']} | {labels['status']} |", "|---|---:|---|---|---|"])
    output.append(
        f"| {labels['cash']} | {cash_display} | {cash.get('as_of', '')} | {cash.get('basis', '')} / {cash.get('source_locator', '')} | {cash.get('status', '')} |"
    )

    output.extend(["", f"## {labels['actions']}", "", f"| {labels['priority']} | {labels['action']} | {labels['why']} | {labels['owner']} | {labels['due']} | {labels['status']} |", "|---:|---|---|---|---|---|"])
    for item in report_data.get("action_items", [])[:5]:
        if isinstance(item, dict):
            output.append(f"| {item.get('priority', '')} | {item.get('action', '')} | {item.get('why', '')} | {item.get('owner', '')} | {item.get('due_date', '')} | {item.get('status', '')} |")
    if not report_data.get("action_items"):
        output.append("| — | — | — | — | — | CLEAR |")

    output.extend(["", f"## {labels['trust']}", "", f"| {labels['check']} | {labels['status']} | {labels['count']} | {labels['exception_amount']} | {labels['impact']} | {labels['source']} |", "|---|---|---:|---:|---|---|"])
    for item in report_data.get("trust_summary", []):
        if isinstance(item, dict):
            output.append(f"| {item.get('check_id', '')} | {item.get('status', '')} | {item.get('count', '')} | {_amount(item.get('amount'), currency, language)} | {item.get('impact', '')} | {item.get('source_locator', '')} |")
    output.extend(["", labels["disclaimer"], ""])
    return "\n".join(line.rstrip() for line in output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an owner dashboard from a validated management report.")
    parser.add_argument("report_json")
    parser.add_argument("config_json")
    parser.add_argument("output_markdown")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_path = Path(args.output_markdown).expanduser().resolve()
    if output_path.exists() and not args.overwrite:
        parser.error("output already exists; review it and use --overwrite for an authorized regeneration")
    report_data = json.loads(Path(args.report_json).expanduser().read_text(encoding="utf-8"))
    config = json.loads(Path(args.config_json).expanduser().read_text(encoding="utf-8"))
    output_path.write_text(render_management_dashboard(config, report_data), encoding="utf-8")
    print(f"Rendered management dashboard: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
