#!/usr/bin/env node
/** Build a formula-backed owner workbook with native charts from a validated report. */

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const VISUAL_TO_CHART = {
  "VIZ-PNL-COLUMNS": "PNL_COLUMNS",
  "VIZ-PNL-BRIDGE": "PNL_BRIDGE_COLUMNS",
  "VIZ-COST-BARS": "COST_BARS",
  "VIZ-COST-DONUT": "COST_DONUT",
  "VIZ-DIMENSION-PROFIT": "DIMENSION_PROFIT_BARS",
};

const PNL_LABELS = {
  "zh-TW": {
    GROSS_REVENUE: "營業收入",
    REVENUE_DEDUCTIONS: "退款、折讓與收入減項",
    NET_REVENUE: "營業收入淨額",
    COST_OF_SALES: "歸屬本期收入的營業成本",
    GROSS_PROFIT: "營業毛利／毛損",
    OPERATING_EXPENSE: "營業費用",
    OPERATING_PROFIT: "營業利益／損失",
    OTHER_INCOME: "營業外收入",
    OTHER_EXPENSE: "營業外費用",
    PRETAX_PROFIT: "稅前淨利／淨損",
    INCOME_TAX: "所得稅費用／利益",
    CONTINUING_PROFIT: "繼續營業損益",
    DISCONTINUED_OPERATIONS: "停業單位損益",
    NET_PROFIT: "本期淨利／淨損",
  },
  en: {
    GROSS_REVENUE: "Operating revenue",
    REVENUE_DEDUCTIONS: "Revenue deductions",
    NET_REVENUE: "Net operating revenue",
    COST_OF_SALES: "Operating costs",
    GROSS_PROFIT: "Gross profit / loss",
    OPERATING_EXPENSE: "Operating expenses",
    OPERATING_PROFIT: "Operating profit / loss",
    OTHER_INCOME: "Other income",
    OTHER_EXPENSE: "Other expense",
    PRETAX_PROFIT: "Profit / loss before tax",
    INCOME_TAX: "Income tax expense / benefit",
    CONTINUING_PROFIT: "Continuing operations profit / loss",
    DISCONTINUED_OPERATIONS: "Discontinued operations",
    NET_PROFIT: "Net profit / loss",
  },
};

const COLORS = {
  ink: "#0F172A",
  muted: "#64748B",
  light: "#E2E8F0",
  panel: "#F8FAFC",
  teal: "#0F766E",
  tealLight: "#CCFBF1",
  blue: "#2563EB",
  blueLight: "#DBEAFE",
  amber: "#D97706",
  amberLight: "#FEF3C7",
  red: "#B91C1C",
  redLight: "#FEE2E2",
  white: "#FFFFFF",
  gray: "#94A3B8",
};


function usage() {
  return [
    "Usage:",
    "  node render_management_workbook.mjs <management-report.json> <management-dashboard-config.json> <output.xlsx> [--preview <dashboard.png>] [--overwrite]",
    "",
    "The input report must already pass validate_company_pack.py --stage close.",
  ].join("\n");
}


function parseArgs(argv) {
  const positional = [];
  let preview = "";
  let overwrite = false;
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--overwrite") {
      overwrite = true;
    } else if (value === "--preview") {
      preview = argv[index + 1] || "";
      index += 1;
    } else if (value === "--help" || value === "-h") {
      console.log(usage());
      process.exit(0);
    } else {
      positional.push(value);
    }
  }
  if (positional.length !== 3 || (argv.includes("--preview") && !preview)) {
    throw new Error(usage());
  }
  return {
    reportPath: path.resolve(positional[0]),
    configPath: path.resolve(positional[1]),
    outputPath: path.resolve(positional[2]),
    previewPath: preview ? path.resolve(preview) : "",
    overwrite,
  };
}


async function ensureWritableTarget(targetPath, overwrite) {
  if (!targetPath) return;
  try {
    await fs.access(targetPath);
    if (!overwrite) {
      throw new Error(`Output already exists: ${targetPath}. Review it, then rerun with --overwrite.`);
    }
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  await fs.mkdir(path.dirname(targetPath), { recursive: true });
}


function numberOrNull(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const number = Number(String(value).replaceAll(",", ""));
  if (!Number.isFinite(number)) throw new Error(`Invalid numeric report value: ${value}`);
  return number;
}


function quotedSheet(name) {
  return `'${String(name).replaceAll("'", "''")}'`;
}


function formulaRef(sheetName, cell) {
  return `=${quotedSheet(sheetName)}!${cell}`;
}


function applyTitle(sheet, rangeAddress, title) {
  const range = sheet.getRange(rangeAddress);
  range.merge();
  range.values = [[title]];
  range.format = {
    fill: COLORS.ink,
    font: { bold: true, color: COLORS.white, size: 18 },
    verticalAlignment: "center",
  };
  range.format.rowHeightPx = 38;
}


function applyHeader(range) {
  range.format = {
    fill: COLORS.teal,
    font: { bold: true, color: COLORS.white },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: COLORS.teal },
  };
  range.format.rowHeightPx = 30;
}


function applyTableBody(range) {
  range.format = {
    borders: {
      insideHorizontal: { style: "thin", color: COLORS.light },
      bottom: { style: "thin", color: COLORS.light },
    },
    verticalAlignment: "center",
  };
}


function applyMoneyFormat(range) {
  range.format.numberFormat = '#,##0;[Red](#,##0);-';
}


function enabledChartIds(config, report) {
  const requested = new Set(
    (config.visualizations || [])
      .filter((item) => item && String(item.status).toUpperCase() === "ENABLED")
      .map((item) => VISUAL_TO_CHART[item.visual_id])
      .filter(Boolean),
  );
  const referenced = new Set((report.charts || []).map((item) => item?.chart_id).filter(Boolean));
  return new Set([...requested].filter((chartId) => referenced.has(chartId)));
}


function addBarChart(sheet, sourceRange, title, position, direction, currency, colors = []) {
  const chart = sheet.charts.add("bar", sourceRange);
  chart.title = title;
  chart.titleTextStyle.fontSize = 13;
  chart.hasLegend = sourceRange.columnCount > 2;
  chart.legend = { position: "bottom" };
  chart.barOptions.direction = direction;
  chart.barOptions.grouping = "clustered";
  chart.barOptions.gapWidth = 70;
  chart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
  chart.yAxis = { numberFormatCode: `${currency} #,##0`, textStyle: { fontSize: 9 } };
  chart.setPosition(position[0], position[1]);
  chart.series.items.forEach((series, index) => {
    if (colors[index]) series.fill = colors[index];
  });
  return chart;
}


function addStandardChart(sheet, type, sourceRange, title, position, currency) {
  const chart = sheet.charts.add(type, sourceRange);
  chart.title = title;
  chart.titleTextStyle.fontSize = 13;
  chart.hasLegend = type === "doughnut";
  chart.legend = { position: "right" };
  if (type !== "doughnut" && type !== "pie") {
    chart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
    chart.yAxis = { numberFormatCode: `${currency} #,##0`, textStyle: { fontSize: 9 } };
  }
  chart.setPosition(position[0], position[1]);
  return chart;
}


async function buildWorkbook(report, config) {
  const language = config.display_language === "en" ? "en" : "zh-TW";
  const labels = PNL_LABELS[language];
  const currency = String(report.reporting_currency || report.functional_currency || "");
  const enabledCharts = enabledChartIds(config, report);
  const workbook = Workbook.create();
  const dashboard = workbook.worksheets.add("Dashboard");
  const pnl = workbook.worksheets.add("P&L");
  const cost = workbook.worksheets.add("Cost Analysis");
  const dimension = workbook.worksheets.add("Dimension Profit");
  const chartData = workbook.worksheets.add("Chart Data");
  const lineage = workbook.worksheets.add("Data & Lineage");
  const checks = workbook.worksheets.add("Checks");
  const sheets = [dashboard, pnl, cost, dimension, chartData, lineage, checks];
  sheets.forEach((sheet) => {
    sheet.showGridLines = false;
  });

  const reportLines = Array.isArray(report.lines) ? report.lines : [];
  if (reportLines.length === 0) throw new Error("management-report.json has no P&L lines");
  const sortedCosts = [...(report.cost_breakdown || [])].sort(
    (left, right) => (numberOrNull(right.management_amount) || 0) - (numberOrNull(left.management_amount) || 0),
  );
  const dimensions = Array.isArray(report.dimension_summary) ? report.dimension_summary : [];

  applyTitle(lineage, "A1:J1", language === "en" ? "Validated report snapshot and lineage" : "已驗證報表快照與來源");
  lineage.getRange("A3:B8").values = [
    ["Report ID", report.report_id || ""],
    ["Revision", report.revision ?? ""],
    ["Period", `${report.period_start || ""} to ${report.period_end || ""}`],
    ["Status", report.status || ""],
    ["Ledger SHA-256", report.ledger_sha256 || ""],
    ["Generated at", report.generated_at ? `'${report.generated_at}` : ""],
  ];
  lineage.getRange("A10:J10").values = [[
    "Line ID", "Label", "Ledger accrual", "Management adjustment", "Management basis",
    "Budget", "Variance", "Currency", "Source entries", "Data status",
  ]];
  applyHeader(lineage.getRange("A10:J10"));
  const pnlSnapshot = reportLines.map((item) => [
    item.line_id || "",
    labels[item.line_id] || item.line_id || "",
    numberOrNull(item.financial_amount),
    numberOrNull(item.management_adjustment),
    numberOrNull(item.management_amount),
    numberOrNull(item.budget_amount),
    numberOrNull(item.variance_amount),
    item.currency || currency,
    numberOrNull(item.source_entry_count),
    item.data_status || "",
  ]);
  lineage.getRangeByIndexes(10, 0, pnlSnapshot.length, 10).values = pnlSnapshot;
  applyTableBody(lineage.getRangeByIndexes(10, 0, pnlSnapshot.length, 10));
  applyMoneyFormat(lineage.getRangeByIndexes(10, 2, pnlSnapshot.length, 5));

  const costStartRow = 10;
  lineage.getRange("L10:T10").values = [[
    "Cost ID", "Account", "Nature", "Behavior", "Traceability", "Ledger accrual",
    "Management adjustment", "Management basis", "Data status",
  ]];
  applyHeader(lineage.getRange("L10:T10"));
  if (sortedCosts.length > 0) {
    const costSnapshot = sortedCosts.map((item) => [
      item.cost_id || "", item.account_code || "", item.cost_nature || "",
      item.cost_behavior || "", item.traceability || "", numberOrNull(item.financial_amount),
      numberOrNull(item.management_adjustment), numberOrNull(item.management_amount), item.data_status || "",
    ]);
    lineage.getRangeByIndexes(costStartRow, 11, costSnapshot.length, 9).values = costSnapshot;
    applyTableBody(lineage.getRangeByIndexes(costStartRow, 11, costSnapshot.length, 9));
    applyMoneyFormat(lineage.getRangeByIndexes(costStartRow, 16, costSnapshot.length, 3));
  }

  const dimensionStartRow = Math.max(28, 12 + sortedCosts.length);
  lineage.getRangeByIndexes(dimensionStartRow - 1, 11, 1, 8).values = [[
    "Dimension type", "Dimension ID", "Dimension name", "Ledger revenue", "Management revenue",
    "Ledger net profit", "Management adjustment", "Management net profit",
  ]];
  applyHeader(lineage.getRangeByIndexes(dimensionStartRow - 1, 11, 1, 8));
  if (dimensions.length > 0) {
    const dimensionSnapshot = dimensions.map((item) => [
      item.dimension_type || "", item.dimension_id || "", item.dimension_name || "",
      numberOrNull(item.financial_amounts?.NET_REVENUE),
      numberOrNull(item.management_amounts?.NET_REVENUE),
      numberOrNull(item.financial_amounts?.NET_PROFIT),
      numberOrNull(item.management_adjustments?.NET_PROFIT),
      numberOrNull(item.management_amounts?.NET_PROFIT),
    ]);
    lineage.getRangeByIndexes(dimensionStartRow, 11, dimensionSnapshot.length, 8).values = dimensionSnapshot;
    applyTableBody(lineage.getRangeByIndexes(dimensionStartRow, 11, dimensionSnapshot.length, 8));
    applyMoneyFormat(lineage.getRangeByIndexes(dimensionStartRow, 14, dimensionSnapshot.length, 5));
  }

  const checksumRows = Object.entries(report.source_checksums || {});
  const checksumStartRow = Math.max(34, 13 + reportLines.length);
  lineage.getRangeByIndexes(checksumStartRow - 1, 0, 1, 2).values = [["Source", "SHA-256"]];
  applyHeader(lineage.getRangeByIndexes(checksumStartRow - 1, 0, 1, 2));
  if (checksumRows.length > 0) {
    lineage.getRangeByIndexes(checksumStartRow, 0, checksumRows.length, 2).values = checksumRows;
    applyTableBody(lineage.getRangeByIndexes(checksumStartRow, 0, checksumRows.length, 2));
  }
  lineage.freezePanes.freezeRows(10);
  lineage.getRange("A:T").format.autofitColumns();
  lineage.getRange("B:B").format.columnWidthPx = 210;
  lineage.getRange("A:A").format.columnWidthPx = 170;

  applyTitle(pnl, "A1:H1", language === "en" ? "Profit and loss: ledger accrual vs management basis" : "損益：帳載權責與管理口徑並列");
  pnl.getRange("A3:H4").values = [
    ["Report ID", report.report_id || "", "Period", `${report.period_start || ""} to ${report.period_end || ""}`, "Currency", currency, "Status", report.status || ""],
    ["Ledger SHA-256", report.ledger_sha256 || "", "Generated at", report.generated_at || "", "", "", "", ""],
  ];
  pnl.getRange("A6:H6").values = [[
    "Line ID", "損益項目 / P&L line", "帳載權責 / Ledger accrual", "管理調整 / Adjustment",
    "管理口徑 / Management basis", "預算 / Budget", "差異 / Variance", "資料狀態 / Status",
  ]];
  applyHeader(pnl.getRange("A6:H6"));
  const pnlRows = reportLines.map((item, index) => {
    const sourceRow = 11 + index;
    return {
      values: [item.line_id || "", labels[item.line_id] || item.line_id || ""],
      formulas: [
        formulaRef("Data & Lineage", `C${sourceRow}`),
        formulaRef("Data & Lineage", `D${sourceRow}`),
        formulaRef("Data & Lineage", `E${sourceRow}`),
        `=IF(${quotedSheet("Data & Lineage")}!F${sourceRow}="","",${quotedSheet("Data & Lineage")}!F${sourceRow})`,
        `=IF(${quotedSheet("Data & Lineage")}!G${sourceRow}="","",${quotedSheet("Data & Lineage")}!G${sourceRow})`,
        formulaRef("Data & Lineage", `J${sourceRow}`),
      ],
    };
  });
  pnlRows.forEach((row, index) => {
    const targetRow = 7 + index;
    pnl.getRange(`A${targetRow}:B${targetRow}`).values = [row.values];
    pnl.getRange(`C${targetRow}:H${targetRow}`).formulas = [row.formulas];
  });
  const pnlLastRow = 6 + pnlRows.length;
  applyTableBody(pnl.getRange(`A7:H${pnlLastRow}`));
  applyMoneyFormat(pnl.getRange(`C7:G${pnlLastRow}`));
  pnl.getRange(`A7:H${pnlLastRow}`).conditionalFormats.add("expression", {
    formula: "=$E7<0",
    format: { font: { color: COLORS.red } },
  });
  pnl.freezePanes.freezeRows(6);
  pnl.getRange("A:H").format.autofitColumns();
  pnl.getRange("B:B").format.columnWidthPx = 240;

  applyTitle(cost, "A1:H1", language === "en" ? "Cost analysis" : "成本分析");
  cost.getRange("A3:H4").values = [[
    "Definition", language === "en" ? "Costs and operating expenses, sorted by management-basis amount" : "營業成本與營業費用，依管理口徑金額由大到小",
    "Currency", currency, "Period", `${report.period_start || ""} to ${report.period_end || ""}`, "", "",
  ], ["Rule", language === "en" ? "A doughnut is allowed only for a valid non-negative whole." : "甜甜圈圖只用於完整、非負且總額大於零的成本構成。", "", "", "", "", "", ""]];
  cost.getRange("A6:H6").values = [[
    "Cost ID", "科目 / Account", "成本性質 / Nature", "可追溯性 / Traceability",
    "習性 / Behavior", "帳載權責", "管理調整", "管理口徑",
  ]];
  applyHeader(cost.getRange("A6:H6"));
  sortedCosts.forEach((item, index) => {
    const sourceRow = costStartRow + 1 + index;
    const targetRow = 7 + index;
    cost.getRange(`A${targetRow}:E${targetRow}`).formulas = [[
      formulaRef("Data & Lineage", `L${sourceRow}`), formulaRef("Data & Lineage", `M${sourceRow}`),
      formulaRef("Data & Lineage", `N${sourceRow}`), formulaRef("Data & Lineage", `P${sourceRow}`),
      formulaRef("Data & Lineage", `O${sourceRow}`),
    ]];
    cost.getRange(`F${targetRow}:H${targetRow}`).formulas = [[
      formulaRef("Data & Lineage", `Q${sourceRow}`), formulaRef("Data & Lineage", `R${sourceRow}`),
      formulaRef("Data & Lineage", `S${sourceRow}`),
    ]];
  });
  const costLastRow = Math.max(7, 6 + sortedCosts.length);
  if (sortedCosts.length > 0) {
    applyTableBody(cost.getRange(`A7:H${costLastRow}`));
    applyMoneyFormat(cost.getRange(`F7:H${costLastRow}`));
  }
  cost.freezePanes.freezeRows(6);
  cost.getRange("A:H").format.autofitColumns();
  cost.getRange("C:C").format.columnWidthPx = 170;

  applyTitle(dimension, "A1:H1", language === "en" ? "Management-basis profit by dimension" : "依維度查看管理口徑獲利");
  dimension.getRange("A3:H3").values = [[
    "Dimension type", "Dimension ID", "Dimension name", "Ledger revenue", "Management revenue",
    "Ledger net profit", "Management adjustment", "Management net profit",
  ]];
  applyHeader(dimension.getRange("A3:H3"));
  dimensions.forEach((item, index) => {
    const sourceRow = dimensionStartRow + 1 + index;
    const targetRow = 4 + index;
    const sourceColumns = ["L", "M", "N", "O", "P", "Q", "R", "S"];
    dimension.getRange(`A${targetRow}:H${targetRow}`).formulas = [[
      ...sourceColumns.map((column) => formulaRef("Data & Lineage", `${column}${sourceRow}`)),
    ]];
  });
  const dimensionLastRow = Math.max(4, 3 + dimensions.length);
  if (dimensions.length > 0) {
    applyTableBody(dimension.getRange(`A4:H${dimensionLastRow}`));
    applyMoneyFormat(dimension.getRange(`D4:H${dimensionLastRow}`));
  } else {
    dimension.getRange("A4:H4").values = [["", "", language === "en" ? "Not enabled" : "未啟用", "", "", "", "", ""]];
  }
  dimension.getRange("A:H").format.autofitColumns();
  dimension.getRange("C:C").format.columnWidthPx = 200;

  applyTitle(chartData, "A1:P1", language === "en" ? "Visible, formula-backed chart sources" : "可見且可追溯的圖表來源");
  const pnlChartLineIds = ["NET_REVENUE", "GROSS_PROFIT", "OPERATING_PROFIT", "NET_PROFIT"];
  chartData.getRange("A3:C3").values = [["損益階段 / P&L stage", "帳載權責", "管理口徑"]];
  applyHeader(chartData.getRange("A3:C3"));
  pnlChartLineIds.forEach((lineId, index) => {
    const reportIndex = reportLines.findIndex((item) => item.line_id === lineId);
    if (reportIndex < 0) throw new Error(`Missing chart P&L line: ${lineId}`);
    const pnlRow = 7 + reportIndex;
    const targetRow = 4 + index;
    chartData.getRange(`A${targetRow}:C${targetRow}`).formulas = [[
      formulaRef("P&L", `B${pnlRow}`), formulaRef("P&L", `C${pnlRow}`), formulaRef("P&L", `E${pnlRow}`),
    ]];
  });
  applyTableBody(chartData.getRange("A4:C7"));
  applyMoneyFormat(chartData.getRange("B4:C7"));

  const waterfallIds = ["NET_REVENUE", "COST_OF_SALES", "OPERATING_EXPENSE", "OTHER_INCOME", "OTHER_EXPENSE", "INCOME_TAX", "NET_PROFIT"];
  const waterfallNegative = new Set(["COST_OF_SALES", "OPERATING_EXPENSE", "OTHER_EXPENSE", "INCOME_TAX"]);
  chartData.getRange("E3:F3").values = [["損益橋接 / P&L bridge", "管理口徑"]];
  applyHeader(chartData.getRange("E3:F3"));
  waterfallIds.forEach((lineId, index) => {
    const reportIndex = reportLines.findIndex((item) => item.line_id === lineId);
    const pnlRow = 7 + reportIndex;
    const targetRow = 4 + index;
    chartData.getRange(`E${targetRow}`).formulas = [[formulaRef("P&L", `B${pnlRow}`)]];
    chartData.getRange(`F${targetRow}`).formulas = [[
      `${waterfallNegative.has(lineId) ? "=-" : "="}${quotedSheet("P&L")}!E${pnlRow}`,
    ]];
  });
  applyTableBody(chartData.getRange("E4:F10"));
  applyMoneyFormat(chartData.getRange("F4:F10"));

  const costBarCount = Math.min(6, sortedCosts.length);
  chartData.getRange("H3:I3").values = [["主要成本 / Major cost", "管理口徑"]];
  applyHeader(chartData.getRange("H3:I3"));
  for (let index = 0; index < costBarCount; index += 1) {
    const costRow = 7 + index;
    const targetRow = 4 + index;
    chartData.getRange(`H${targetRow}:I${targetRow}`).formulas = [[
      formulaRef("Cost Analysis", `C${costRow}`), formulaRef("Cost Analysis", `H${costRow}`),
    ]];
  }
  if (costBarCount > 0) {
    applyTableBody(chartData.getRange(`H4:I${3 + costBarCount}`));
    applyMoneyFormat(chartData.getRange(`I4:I${3 + costBarCount}`));
  }

  const donutEligible = sortedCosts.length >= 2
    && sortedCosts.every((item) => (numberOrNull(item.management_amount) || 0) >= 0)
    && sortedCosts.reduce((total, item) => total + (numberOrNull(item.management_amount) || 0), 0) > 0;
  let donutRows = 0;
  chartData.getRange("K3:L3").values = [["成本構成 / Cost mix", "管理口徑"]];
  applyHeader(chartData.getRange("K3:L3"));
  if (donutEligible) {
    const directCount = Math.min(5, sortedCosts.length);
    for (let index = 0; index < directCount; index += 1) {
      const costRow = 7 + index;
      const targetRow = 4 + index;
      chartData.getRange(`K${targetRow}:L${targetRow}`).formulas = [[
        formulaRef("Cost Analysis", `C${costRow}`), formulaRef("Cost Analysis", `H${costRow}`),
      ]];
    }
    donutRows = directCount;
    if (sortedCosts.length > directCount) {
      const targetRow = 4 + directCount;
      chartData.getRange(`K${targetRow}`).values = [[language === "en" ? "Other" : "其他"]];
      chartData.getRange(`L${targetRow}`).formulas = [[`=SUM(${quotedSheet("Cost Analysis")}!H${7 + directCount}:H${6 + sortedCosts.length})`]];
      donutRows += 1;
    }
    applyTableBody(chartData.getRange(`K4:L${3 + donutRows}`));
    applyMoneyFormat(chartData.getRange(`L4:L${3 + donutRows}`));
  } else {
    chartData.getRange("K4:L4").values = [[
      language === "en" ? "Not rendered: invalid part-to-whole data" : "未產生：成本構成不符合圓餅圖條件",
      null,
    ]];
  }

  chartData.getRange("N3:O3").values = [["維度 / Dimension", "管理口徑淨利"]];
  applyHeader(chartData.getRange("N3:O3"));
  dimensions.forEach((item, index) => {
    const dimensionRow = 4 + index;
    chartData.getRange(`N${dimensionRow}:O${dimensionRow}`).formulas = [[
      formulaRef("Dimension Profit", `C${dimensionRow}`), formulaRef("Dimension Profit", `H${dimensionRow}`),
    ]];
  });
  if (dimensions.length > 0) {
    applyTableBody(chartData.getRange(`N4:O${3 + dimensions.length}`));
    applyMoneyFormat(chartData.getRange(`O4:O${3 + dimensions.length}`));
  }
  chartData.getRange("A:P").format.autofitColumns();
  chartData.getRange("A:A").format.columnWidthPx = 200;
  chartData.getRange("E:E").format.columnWidthPx = 200;
  chartData.getRange("H:H").format.columnWidthPx = 190;
  chartData.getRange("K:K").format.columnWidthPx = 220;
  chartData.getRange("N:N").format.columnWidthPx = 190;

  applyTitle(dashboard, "A1:P1", language === "en" ? "Owner management dashboard" : "老闆經營儀表板");
  const dashboardMetadata = [
    ["A2", "Report ID", "B2:C2", report.report_id || ""],
    ["D2", "Period", "E2:G2", `${report.period_start || ""} to ${report.period_end || ""}`],
    ["H2", "Currency", "I2", currency],
    ["J2", "Status", "K2:P2", report.status || ""],
    ["A3", "Generated at", "B3:D3", report.generated_at ? `'${report.generated_at}` : ""],
    ["E3", "Basis", "F3", report.basis || ""],
    ["G3", "Professional", "H3:J3", report.professional_review?.status || "NOT_REVIEWED"],
    ["K3", "Ledger SHA", "L3:P3", String(report.ledger_sha256 || "").slice(0, 16)],
  ];
  dashboardMetadata.forEach(([labelCell, label, valueRange, value]) => {
    dashboard.getRange(labelCell).values = [[label]];
    dashboard.getRange(labelCell).format = { font: { bold: true, color: COLORS.muted, size: 9 } };
    const target = dashboard.getRange(valueRange);
    if (valueRange.includes(":")) target.merge();
    target.values = [[value]];
    target.format = { font: { color: COLORS.ink, size: 9 }, wrapText: false };
  });
  dashboard.getRange("A2:P3").format.rowHeightPx = 22;
  const netProfitIndex = reportLines.findIndex((item) => item.line_id === "NET_PROFIT");
  const netRevenueIndex = reportLines.findIndex((item) => item.line_id === "NET_REVENUE");
  const netProfitRow = 7 + netProfitIndex;
  const netRevenueRow = 7 + netRevenueIndex;
  const cardRanges = ["A5:C9", "E5:G9", "I5:K9", "M5:P9"];
  const cardTitles = language === "en"
    ? ["Management-basis net revenue", "Ledger accrual net profit / loss", "Management adjustment", "Management-basis net profit / loss"]
    : ["管理口徑營業收入淨額", "帳載權責淨利／淨損", "管理調整", "管理調整後淨利／淨損"];
  const cardFormulas = [
    formulaRef("P&L", `E${netRevenueRow}`), formulaRef("P&L", `C${netProfitRow}`),
    formulaRef("P&L", `D${netProfitRow}`), formulaRef("P&L", `E${netProfitRow}`),
  ];
  cardRanges.forEach((address, index) => {
    const range = dashboard.getRange(address);
    range.merge();
    range.formulas = [[cardFormulas[index]]];
    range.format = {
      fill: index === 3 ? COLORS.tealLight : COLORS.panel,
      font: { bold: true, color: index === 3 ? COLORS.teal : COLORS.ink, size: 17 },
      verticalAlignment: "center",
      horizontalAlignment: "center",
      borders: { preset: "outside", style: "thin", color: index === 3 ? COLORS.teal : COLORS.light },
      numberFormat: `${currency} #,##0;[Red](${currency} #,##0);-`,
    };
    dashboard.getRange(address.split(":")[0]).format.rowHeightPx = 34;
    const [start] = address.split(":");
    const match = start.match(/([A-Z]+)(\d+)/);
    const labelRow = Number(match[2]) - 1;
    const endColumn = address.split(":")[1].match(/[A-Z]+/)[0];
    const labelRange = dashboard.getRange(`${match[1]}${labelRow}:${endColumn}${labelRow}`);
    labelRange.merge();
    labelRange.values = [[cardTitles[index]]];
    labelRange.format = { fill: COLORS.ink, font: { bold: true, color: COLORS.white, size: 10 }, horizontalAlignment: "center" };
  });
  dashboard.getRange("A5:P9").conditionalFormats.add("cellIs", {
    operator: "lessThan",
    formula: 0,
    format: { font: { color: COLORS.red } },
  });

  if (enabledCharts.has("PNL_COLUMNS")) {
    addBarChart(
      dashboard, chartData.getRange("A3:C7"),
      language === "en" ? `Ledger vs management P&L (${currency})` : `帳載權責與管理口徑損益（${currency}）`,
      ["A12", "H29"], "column", currency, [COLORS.gray, COLORS.teal],
    );
  }
  if (enabledCharts.has("COST_DONUT") && donutEligible) {
    addStandardChart(
      dashboard, "doughnut", chartData.getRange(`K3:L${3 + donutRows}`),
      language === "en" ? `Cost mix (${currency})` : `成本構成（${currency}）`, ["I12", "P29"], currency,
    );
  }
  if (enabledCharts.has("PNL_BRIDGE_COLUMNS")) {
    addBarChart(
      dashboard, chartData.getRange("E3:F10"),
      language === "en" ? `P&L positive and negative drivers (${currency})` : `損益正負影響柱狀圖（${currency}）`,
      ["A31", "H48"], "column", currency, [COLORS.blue],
    );
  }
  if (enabledCharts.has("COST_BARS") && costBarCount > 0) {
    addBarChart(
      dashboard, chartData.getRange(`H3:I${3 + costBarCount}`),
      language === "en" ? `Largest costs (${currency})` : `主要成本排行（${currency}）`,
      ["I31", "P48"], "bar", currency, [COLORS.amber],
    );
  }
  if (enabledCharts.has("DIMENSION_PROFIT_BARS") && dimensions.length > 0) {
    addBarChart(
      dimension, chartData.getRange(`N3:O${3 + dimensions.length}`),
      language === "en" ? `Management profit by dimension (${currency})` : `各維度管理口徑獲利（${currency}）`,
      ["J3", "Q20"], "column", currency, [COLORS.blue],
    );
  }
  dashboard.getRange("A:P").format.columnWidthPx = 78;
  dashboard.freezePanes.freezeRows(3);

  applyTitle(checks, "A1:E1", language === "en" ? "Workbook checks" : "工作簿檢查");
  checks.getRange("A3:E3").values = [["Check", "Status", "Delta / Count", "Where to fix", "Notes"]];
  applyHeader(checks.getRange("A3:E3"));
  const requestedDonut = enabledCharts.has("COST_DONUT");
  checks.getRange("A4:E8").values = [
    ["REPORT_RECONCILIATION", report.reconciliation?.status === "RECONCILED" ? "PASS" : "FAIL", numberOrNull(report.reconciliation?.difference), "management-report.json", "Ledger P&L must reconcile."],
    ["PNL_LINE_COUNT", reportLines.length === 14 ? "PASS" : "FAIL", reportLines.length, "management-report.json lines", "Fixed P&L requires 14 lines."],
    ["CHART_REFERENCES", enabledCharts.size > 0 ? "PASS" : "INFO", enabledCharts.size, "management-dashboard-config.json", [...enabledCharts].join(", ") || "No visual selected."],
    ["COST_DONUT_ELIGIBILITY", !requestedDonut || donutEligible ? "PASS" : "FAIL", sortedCosts.length, "cost_breakdown", donutEligible ? "Valid non-negative part-to-whole." : "Use bars; do not force a pie/doughnut."],
    ["PROFESSIONAL_BOUNDARY", "PASS", 0, "professional_review", "Internal management output; professional status follows the validated report scope."],
  ];
  applyTableBody(checks.getRange("A4:E8"));
  checks.getRange("A10:B10").values = [["MODEL STATUS", ""]];
  checks.getRange("B10").formulas = [["=IF(COUNTIF(B4:B8,\"FAIL\")=0,\"PASS\",\"FAIL\")"]];
  checks.getRange("A10:B10").format = { fill: COLORS.ink, font: { bold: true, color: COLORS.white } };
  checks.getRange("B4:B8").conditionalFormats.add("containsText", { text: "FAIL", format: { fill: COLORS.redLight, font: { color: COLORS.red, bold: true } } });
  checks.getRange("B4:B8").conditionalFormats.add("containsText", { text: "PASS", format: { fill: COLORS.tealLight, font: { color: COLORS.teal, bold: true } } });
  checks.getRange("A:E").format.autofitColumns();
  checks.getRange("D:E").format.columnWidthPx = 260;
  checks.freezePanes.freezeRows(3);

  return { workbook, enabledCharts, donutEligible };
}


async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (path.extname(args.outputPath).toLowerCase() !== ".xlsx") {
    throw new Error("Output must use the .xlsx extension.");
  }
  await ensureWritableTarget(args.outputPath, args.overwrite);
  await ensureWritableTarget(args.previewPath, args.overwrite);
  const report = JSON.parse(await fs.readFile(args.reportPath, "utf8"));
  const config = JSON.parse(await fs.readFile(args.configPath, "utf8"));
  if (!["OWNER_APPROVED_MANAGEMENT", "PROFESSIONALLY_REVIEWED"].includes(report.status)) {
    throw new Error("Workbook generation requires an owner-approved or professionally reviewed management report.");
  }
  const { workbook, enabledCharts, donutEligible } = await buildWorkbook(report, config);
  const inspection = await workbook.inspect({
    kind: "table,drawing",
    sheetId: "Dashboard",
    range: "A1:P48",
    include: "values,formulas,id,name",
    tableMaxRows: 14,
    tableMaxCols: 16,
    maxChars: 7000,
  });
  console.log(inspection.ndjson);
  const formulaErrors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 200 },
    summary: "final formula error scan",
  });
  if (/\"matchCount\":\s*[1-9]/.test(formulaErrors.ndjson)) {
    throw new Error(`Formula error scan failed: ${formulaErrors.ndjson}`);
  }
  if (args.previewPath) {
    const preview = await workbook.render({ sheetName: "Dashboard", range: "A1:P48", scale: 1, format: "png" });
    await fs.writeFile(args.previewPath, new Uint8Array(await preview.arrayBuffer()));
  }
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(args.outputPath);
  console.log(`Workbook: ${args.outputPath}`);
  if (args.previewPath) console.log(`Preview: ${args.previewPath}`);
  console.log(`Charts: ${[...enabledCharts].join(", ") || "none"}`);
  console.log(`Cost doughnut eligible: ${donutEligible}`);
}


main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
