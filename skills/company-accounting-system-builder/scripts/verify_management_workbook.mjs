#!/usr/bin/env node
/** Verify exported workbook sheets, formulas, native chart objects, and dashboard rendering. */

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";


const REQUIRED_SHEETS = new Set([
  "Dashboard",
  "P&L",
  "Cost Analysis",
  "Dimension Profit",
  "Chart Data",
  "Data & Lineage",
  "Checks",
]);


function usage() {
  return "Usage: node verify_management_workbook.mjs <management-dashboard.xlsx> [--min-charts <n>] [--preview <dashboard.png>] [--overwrite]";
}


function parseArgs(argv) {
  const positional = [];
  let previewPath = "";
  let minCharts = 1;
  let overwrite = false;
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--preview") {
      previewPath = argv[index + 1] || "";
      index += 1;
    } else if (value === "--min-charts") {
      minCharts = Number(argv[index + 1]);
      index += 1;
    } else if (value === "--overwrite") {
      overwrite = true;
    } else if (value === "--help" || value === "-h") {
      console.log(usage());
      process.exit(0);
    } else {
      positional.push(value);
    }
  }
  if (positional.length !== 1 || !Number.isInteger(minCharts) || minCharts < 0) {
    throw new Error(usage());
  }
  return {
    workbookPath: path.resolve(positional[0]),
    previewPath: previewPath ? path.resolve(previewPath) : "",
    minCharts,
    overwrite,
  };
}


async function ensurePreviewTarget(targetPath, overwrite) {
  if (!targetPath) return;
  try {
    await fs.access(targetPath);
    if (!overwrite) throw new Error(`Preview already exists: ${targetPath}`);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  await fs.mkdir(path.dirname(targetPath), { recursive: true });
}


function parseNdjson(ndjson) {
  return String(ndjson)
    .split("\n")
    .filter((line) => line.trim().startsWith("{"))
    .map((line) => JSON.parse(line));
}


async function main() {
  const args = parseArgs(process.argv.slice(2));
  await ensurePreviewTarget(args.previewPath, args.overwrite);
  const input = await FileBlob.load(args.workbookPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const structure = await workbook.inspect({
    kind: "sheet,drawing",
    include: "id,name",
    maxChars: 12000,
  });
  const records = parseNdjson(structure.ndjson);
  const sheetNames = new Set(
    records.filter((item) => item.kind === "sheet").map((item) => item.name),
  );
  const missingSheets = [...REQUIRED_SHEETS].filter((name) => !sheetNames.has(name));
  if (missingSheets.length > 0) throw new Error(`Missing workbook sheets: ${missingSheets.join(", ")}`);
  const chartCount = records.filter((item) => item.kind === "drawing" && item.drawingType === "chart").length;
  if (chartCount < args.minCharts) {
    throw new Error(`Expected at least ${args.minCharts} native charts after XLSX import; found ${chartCount}`);
  }
  const formulaErrors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "imported workbook formula error scan",
  });
  if (/\"matchCount\":\s*[1-9]/.test(formulaErrors.ndjson)) {
    throw new Error(`Formula errors found after XLSX import: ${formulaErrors.ndjson}`);
  }
  const keyRange = await workbook.inspect({
    kind: "table",
    sheetId: "Dashboard",
    range: "A1:P10",
    include: "values,formulas",
    tableMaxRows: 10,
    tableMaxCols: 16,
    maxChars: 5000,
  });
  console.log(keyRange.ndjson);
  if (args.previewPath) {
    const preview = await workbook.render({ sheetName: "Dashboard", range: "A1:P48", scale: 1, format: "png" });
    await fs.writeFile(args.previewPath, new Uint8Array(await preview.arrayBuffer()));
  }
  console.log(`Verified workbook: ${args.workbookPath}`);
  console.log(`Native charts after import: ${chartCount}`);
  if (args.previewPath) console.log(`Verified preview: ${args.previewPath}`);
}


main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
