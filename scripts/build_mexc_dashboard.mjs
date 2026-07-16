import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "data/mexc/history/mexc_futures_position_history_2025-01-23_to_2026-01-23.xlsx";
const outputDir = "outputs/mexc_dashboard";
const outputPath = `${outputDir}/MEXC_Futures_Trade_Dashboard.xlsx`;

const sourceBlob = await FileBlob.load(sourcePath);
const sourceWorkbook = await SpreadsheetFile.importXlsx(sourceBlob);
const sourceSheet = sourceWorkbook.worksheets.getItemAt(0);
const sourceRows = sourceSheet.getUsedRange().values;

function numberFromUsdt(value) {
  return Number(String(value).replace("USDT", ""));
}

function dateFromValue(value) {
  if (value instanceof Date) return value;
  return new Date(String(value).replace(" ", "T"));
}

const trades = sourceRows.slice(1).map((row) => {
  const open = dateFromValue(row[2]);
  const close = dateFromValue(row[3]);
  return [
    row[0], row[1], open, close, row[4], Number(row[5]), Number(row[6]), row[7],
    Number(row[8]), numberFromUsdt(row[9]), numberFromUsdt(row[10]),
    new Date(close.getFullYear(), close.getMonth(), 1), row[11],
  ];
});

const monthKeys = [...new Map(trades.map((row) => {
  const date = row[11];
  return [`${date.getFullYear()}-${date.getMonth()}`, date];
})).values()].sort((a, b) => a - b);

const workbook = Workbook.create();
const dashboard = workbook.worksheets.add("Dashboard");
const tradeSheet = workbook.worksheets.add("Trade Data");
const monthly = workbook.worksheets.add("Monthly");

dashboard.showGridLines = false;
monthly.showGridLines = false;

tradeSheet.getRange(`A1:M${trades.length + 1}`).values = [[
  "UID", "Futures", "Open Time", "Close Time", "Margin Mode", "Avg Entry Price",
  "Avg Close Price", "Direction", "Closing Qty", "Fee (USDT)", "Realized P&L (USDT)",
  "Close Month", "Status",
], ...trades];
tradeSheet.getRange(`C2:D${trades.length + 1}`).format.numberFormat = "yyyy-mm-dd hh:mm";
tradeSheet.getRange(`F2:G${trades.length + 1}`).format.numberFormat = "#,##0.0000";
tradeSheet.getRange(`I2:I${trades.length + 1}`).format.numberFormat = "#,##0";
tradeSheet.getRange(`J2:K${trades.length + 1}`).format.numberFormat = "0.00;[Red](0.00);-";
tradeSheet.getRange(`L2:L${trades.length + 1}`).format.numberFormat = "mmm yyyy";
tradeSheet.getRange("A1:M1").format = {
  fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center",
};
tradeSheet.getRange(`A1:M${trades.length + 1}`).format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
tradeSheet.getRange("A:M").format.wrapText = false;
tradeSheet.getRange("A:M").format.autofitColumns();
tradeSheet.getRange("A:A").format.columnWidth = 13;
tradeSheet.getRange("B:B").format.columnWidth = 14;
tradeSheet.getRange("C:D").format.columnWidth = 19;
tradeSheet.freezePanes.freezeRows(1);

monthly.getRange(`A1:D${monthKeys.length + 1}`).values = [["Month", "Trades", "Realized P&L (USDT)", "Fees (USDT)"], ...monthKeys.map((date) => [date, null, null, null])];
monthly.getRange("B2").formulas = [[`=COUNTIF('Trade Data'!$L$2:$L$${trades.length + 1},A2)`]];
monthly.getRange("C2").formulas = [[`=SUMIF('Trade Data'!$L$2:$L$${trades.length + 1},A2,'Trade Data'!$K$2:$K$${trades.length + 1})`]];
monthly.getRange("D2").formulas = [[`=SUMIF('Trade Data'!$L$2:$L$${trades.length + 1},A2,'Trade Data'!$J$2:$J$${trades.length + 1})`]];
monthly.getRange(`B2:D${monthKeys.length + 1}`).fillDown();
monthly.getRange(`A2:A${monthKeys.length + 1}`).format.numberFormat = "mmm yyyy";
monthly.getRange(`B2:B${monthKeys.length + 1}`).format.numberFormat = "#,##0";
monthly.getRange(`C2:D${monthKeys.length + 1}`).format.numberFormat = "0.00;[Red](0.00);-";
monthly.getRange("A1:D1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
monthly.getRange(`A1:D${monthKeys.length + 1}`).format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
monthly.getRange("A:D").format.autofitColumns();

dashboard.getRange("A1:J1").merge();
dashboard.getRange("A1").values = [["MEXC Futures Performance Dashboard"]];
dashboard.getRange("A1").format = { fill: "#0B1F33", font: { bold: true, color: "#FFFFFF", size: 18 }, horizontalAlignment: "center", verticalAlignment: "center" };
dashboard.getRange("A1:J1").format.rowHeight = 30;
dashboard.getRange("A2:J2").merge();
dashboard.getRange("A2").values = [["Source: MEXC Position History export | Closed positions only | Currency: USDT"]];
dashboard.getRange("A2").format = { font: { italic: true, color: "#5B6573" }, horizontalAlignment: "center" };

dashboard.getRange("A4:B10").values = [
  ["Key metric", "Value"],
  ["Closed positions", null],
  ["Realized P&L", null],
  ["Listed fees", null],
  ["Win rate", null],
  ["Profit factor", null],
  ["Average P&L / trade", null],
];
dashboard.getRange("B5").formulas = [[`=COUNTA('Trade Data'!$A$2:$A$${trades.length + 1})`]];
dashboard.getRange("B6").formulas = [[`=SUM('Trade Data'!$K$2:$K$${trades.length + 1})`]];
dashboard.getRange("B7").formulas = [[`=SUM('Trade Data'!$J$2:$J$${trades.length + 1})`]];
dashboard.getRange("B8").formulas = [[`=COUNTIF('Trade Data'!$K$2:$K$${trades.length + 1},\">0\")/B5`]];
dashboard.getRange("B9").formulas = [[`=SUMIF('Trade Data'!$K$2:$K$${trades.length + 1},\">0\",'Trade Data'!$K$2:$K$${trades.length + 1})/ABS(SUMIF('Trade Data'!$K$2:$K$${trades.length + 1},\"<0\",'Trade Data'!$K$2:$K$${trades.length + 1}))`]];
dashboard.getRange("B10").formulas = [[`=AVERAGE('Trade Data'!$K$2:$K$${trades.length + 1})`]];
dashboard.getRange("A4:B4").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
dashboard.getRange("A5:B10").format = { fill: "#F7FAFC" };
dashboard.getRange("A4:B10").format.borders = { preset: "all", style: "thin", color: "#B8C6D9" };
dashboard.getRange("B6:B7").format.numberFormat = "0.00;[Red](0.00);-";
dashboard.getRange("B8").format.numberFormat = "0.0%";
dashboard.getRange("B9").format.numberFormat = "0.00x";
dashboard.getRange("B10").format.numberFormat = "0.00;[Red](0.00);-";

dashboard.getRange("D4:F7").values = [
  ["Direction", "Trades", "Realized P&L (USDT)"],
  ["Long", null, null],
  ["Short", null, null],
  ["Total", null, null],
];
dashboard.getRange("E5").formulas = [[`=COUNTIF('Trade Data'!$H$2:$H$${trades.length + 1},D5)`]];
dashboard.getRange("F5").formulas = [[`=SUMIF('Trade Data'!$H$2:$H$${trades.length + 1},D5,'Trade Data'!$K$2:$K$${trades.length + 1})`]];
dashboard.getRange("E5:F6").fillDown();
dashboard.getRange("E7").formulas = [["=SUM(E5:E6)"]];
dashboard.getRange("F7").formulas = [["=SUM(F5:F6)"]];
dashboard.getRange("D4:F4").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
dashboard.getRange("D5:F7").format = { fill: "#F7FAFC" };
dashboard.getRange("D4:F7").format.borders = { preset: "all", style: "thin", color: "#B8C6D9" };
dashboard.getRange("F5:F7").format.numberFormat = "0.00;[Red](0.00);-";

dashboard.getRange("A12:D12").merge();
dashboard.getRange("A12").values = [["Monthly performance (formula-linked to Trade Data)"]];
dashboard.getRange("A12").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" } };
dashboard.getRange(`A13:D${monthKeys.length + 12}`).formulas = monthKeys.map((_, index) => [
  `='Monthly'!A${index + 2}`, `='Monthly'!B${index + 2}`, `='Monthly'!C${index + 2}`, `='Monthly'!D${index + 2}`,
]);
dashboard.getRange(`A13:A${monthKeys.length + 12}`).format.numberFormat = "mmm yyyy";
dashboard.getRange(`B13:B${monthKeys.length + 12}`).format.numberFormat = "#,##0";
dashboard.getRange(`C13:D${monthKeys.length + 12}`).format.numberFormat = "0.00;[Red](0.00);-";
dashboard.getRange(`A13:D${monthKeys.length + 12}`).format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };

// Formula-linked helper ranges give each chart a single auditable series.
dashboard.getRange("H2:I4").values = [["Direction", "P&L (USDT)"], ["Long", null], ["Short", null]];
dashboard.getRange("I3:I4").formulas = [["=F5"], ["=F6"]];
dashboard.getRange(`H25:I${monthKeys.length + 25}`).values = [
  ["Month", "Realized P&L (USDT)"],
  ...monthKeys.map((date) => [date.toLocaleString("en-US", { month: "short", year: "numeric" }), null]),
];
dashboard.getRange(`I26:I${monthKeys.length + 25}`).formulas = monthKeys.map((_, index) => [`='Monthly'!C${index + 2}`]);

const pnlChart = dashboard.charts.add("line", dashboard.getRange(`H25:I${monthKeys.length + 25}`));
pnlChart.title = "Monthly Realized P&L (USDT)";
pnlChart.hasLegend = false;
pnlChart.xAxis = { axisType: "textAxis" };
pnlChart.yAxis = { numberFormatCode: "0.00;[Red](0.00);-" };
pnlChart.setPosition("G9", "J23");

const directionChart = dashboard.charts.add("column", dashboard.getRange("H2:I4"));
directionChart.title = "Long vs Short P&L (USDT)";
directionChart.hasLegend = false;
directionChart.xAxis = { axisType: "textAxis" };
directionChart.yAxis = { numberFormatCode: "0.00;[Red](0.00);-" };
directionChart.setPosition("G3", "J8");

dashboard.getRange("A:J").format.columnWidth = 14;
dashboard.getRange("A:A").format.columnWidth = 24;
dashboard.getRange("D:D").format.columnWidth = 16;
dashboard.getRange("F:F").format.columnWidth = 18;

const verification = await workbook.inspect({ kind: "table", range: "Dashboard!A1:F17", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 8 });
console.log(verification.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "Dashboard", range: "A1:J23", scale: 1.5, format: "png" });
await fs.writeFile(`${outputDir}/dashboard-preview.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
