/** A chart's inline data as a table: the no-JavaScript and screen-reader view of every chart. */
export interface DataTable {
  columns: string[];
  rows: unknown[][];
}

type Node = { [key: string]: unknown };

function isNode(value: unknown): value is Node {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function rowsOf(spec: Node): Node[] | undefined {
  const data = spec.data;
  if (isNode(data) && Array.isArray(data.values)) return data.values.filter(isNode);
  if (Array.isArray(spec.layer)) {
    for (const layer of spec.layer) {
      if (isNode(layer)) {
        const found = rowsOf(layer);
        if (found !== undefined) return found;
      }
    }
  }
  if (isNode(spec.datasets)) {
    const first = Object.values(spec.datasets).find(Array.isArray);
    if (first !== undefined) return first.filter(isNode);
  }
  return undefined;
}

/** The first inline dataset of a Vega-Lite spec (top level, layers, then named datasets). */
export function inlineTable(spec: unknown): DataTable | undefined {
  if (!isNode(spec)) return undefined;
  const rows = rowsOf(spec);
  if (rows === undefined || rows.length === 0) return undefined;
  const columns: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!columns.includes(key)) columns.push(key);
    }
  }
  return { columns, rows: rows.map((row) => columns.map((column) => row[column] ?? null)) };
}
