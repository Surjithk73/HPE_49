import type { ChartKind } from '../components/ChartView'

// Colour palette matching the HPE reference charts
export const COLORS = [
  '#4472C4', // blue  — User Processes / Primary Writes
  '#ED7D31', // orange — Backup Disk / Primary Reads
  '#A5A5A5', // grey  — Primary Disk Process
  '#FFC000', // yellow — Other / Mirror Writes
  '#5B9BD5', // light blue — Interrupt / Mirror Reads
  '#70AD47', // green — Average line
  '#FF0000', // red   — Average Disk Utilization line
  '#264478', // dark blue
  '#9E480E', // dark orange
]

// Per-series chart kind. scatter/stacked-bar are global modes, not per-series.
export type SeriesKind = 'bar' | 'line' | 'area'

export interface SeriesConfig {
  column: string
  kind: SeriesKind
  color: string
  visible: boolean
}

export interface ChartConfig {
  xColumn: string
  series: SeriesConfig[] // order defines line1, line2, …
}

// Reduce a global ChartKind to a per-series baseline kind.
// stacked-bar renders as bars; scatter has no per-series kind (treat as line).
function baseSeriesKind(kind: ChartKind): SeriesKind {
  if (kind === 'stacked-bar' || kind === 'bar') return 'bar'
  if (kind === 'area') return 'area'
  return 'line'
}

// True when a column's values are numeric (or numeric strings) — mirrors the
// original ChartView Y-axis detection.
function isNumericColumn(col: string, rows: Record<string, unknown>[]): boolean {
  const sample = rows[0]?.[col]
  return (
    typeof sample === 'number' ||
    (typeof sample === 'string' && !isNaN(Number(sample)) && sample !== '')
  )
}

// Columns eligible to be plotted as Y-series (numeric, excluding the X column).
export function numericColumns(
  columns: string[],
  rows: Record<string, unknown>[],
  exclude?: string,
): string[] {
  return columns.filter(c => c !== exclude && isNumericColumn(c, rows))
}

// Default X-axis pick: prefer timestamp, then name/label cols, then first column.
export function defaultXColumn(columns: string[]): string {
  return (
    columns.find(c => c.includes('timestamp')) ||
    columns.find(
      c =>
        c.includes('name') ||
        c.includes('device') ||
        c.includes('num') ||
        c.includes('cpu'),
    ) ||
    columns[0]
  )
}

// Build the default chart configuration for a result set. This is the single
// source of truth for "what the chart shows if you don't touch anything".
export function buildDefaultConfig(
  columns: string[],
  rows: Record<string, unknown>[],
  baseKind: ChartKind,
): ChartConfig {
  const xColumn = defaultXColumn(columns)
  const kind = baseSeriesKind(baseKind)
  const series: SeriesConfig[] = numericColumns(columns, rows, xColumn)
    .slice(0, 8)
    .map((column, i) => ({
      column,
      kind,
      color: COLORS[i % COLORS.length],
      visible: true,
    }))
  return { xColumn, series }
}

// Re-derive the series list after the X column changes: drop the new X from the
// series, and re-introduce the previous X if it is numeric. Preserves existing
// series order/kind/color/visibility where possible.
export function reconcileForXChange(
  config: ChartConfig,
  newX: string,
  columns: string[],
  rows: Record<string, unknown>[],
): ChartConfig {
  const eligible = numericColumns(columns, rows, newX)
  const existing = new Map(config.series.map(s => [s.column, s]))

  // Keep prior order for columns that are still eligible…
  const kept: SeriesConfig[] = config.series.filter(s =>
    eligible.includes(s.column),
  )
  // …then append any newly-eligible columns (e.g. the old X) not already present.
  const keptCols = new Set(kept.map(s => s.column))
  let nextColorIdx = kept.length
  for (const col of eligible) {
    if (keptCols.has(col)) continue
    const prior = existing.get(col)
    kept.push(
      prior ?? {
        column: col,
        kind: kept[0]?.kind ?? 'line',
        color: COLORS[nextColorIdx++ % COLORS.length],
        visible: true,
      },
    )
  }
  return { xColumn: newX, series: kept }
}

// Reset every series to a new baseline kind (used when the global chart-kind
// picker changes). Keeps X-axis, order, colors, and visibility.
export function applyGlobalKind(config: ChartConfig, kind: ChartKind): ChartConfig {
  const seriesKind = baseSeriesKind(kind)
  return {
    ...config,
    series: config.series.map(s => ({ ...s, kind: seriesKind })),
  }
}
