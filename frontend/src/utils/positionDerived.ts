const MS_PER_DAY = 86_400_000

export function computeDaysOpen(openedAt: string, closedAt: string | null): number {
  const end = closedAt ? new Date(closedAt).getTime() : Date.now()
  return Math.floor((end - new Date(openedAt).getTime()) / MS_PER_DAY)
}

export function computePnlTotal(netCashFlow: string): number {
  return Number(netCashFlow)
}

export function computeRoi(pnlTotal: number, capitalUsed: string | null): string | null {
  const capital = Number(capitalUsed)
  if (!capitalUsed || capital <= 0) return null
  return ((pnlTotal / capital) * 100).toFixed(2)
}

export type PositionResult = 'Win' | 'Loss' | 'Breakeven'

export function computeResult(pnlRealized: string | null): PositionResult | null {
  if (pnlRealized === null) return null
  const val = Number(pnlRealized)
  if (val > 0) return 'Win'
  if (val < 0) return 'Loss'
  return 'Breakeven'
}

export function formatAmount(value: number | string, currency: string): string {
  const n = typeof value === 'string' ? Number(value) : value
  const formatted = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(n)
  return `${currency} ${formatted}`
}
