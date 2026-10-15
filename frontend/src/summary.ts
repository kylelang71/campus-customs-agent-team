import type { Run, Ticket } from './types.ts'

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export const clip = (text: string, max = 200) => (text.length > max ? `${text.slice(0, max).trimEnd()}…` : text)

/** Agents often answer with a JSON object (a typed reply); show the point of it, not the raw JSON. */
export function shortMessage(raw: string): string {
  try {
    const v: unknown = JSON.parse(raw)
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const o = v as Record<string, unknown>
      if (typeof o.verdict === 'string') {
        const why = Array.isArray(o.reasons) && o.reasons.length ? `: ${String(o.reasons[0])}` : ''
        const msg = typeof o.approved_message === 'string' ? ` “${o.approved_message}”` : ''
        return clip(`${o.verdict}${msg}${why}`)
      }
      if (Array.isArray(o.items)) return `${o.items.length} row${o.items.length === 1 ? '' : 's'} of data`
      if (typeof o.total_outflows === 'number')
        return `cash outlook: ${money(o.total_outflows)} owed, ${money(Number(o.cash_after_all))} left if all paid`
      return clip(Object.keys(o).join(', '), 80)
    }
  } catch {
    /* plain text */
  }
  return clip(raw)
}

export type Badge = { label: string; short: string; tone: 'open' | 'working' | 'finished' | 'resolved' | 'failed' }

/** What to show for a ticket: resolved only when the ticket is actually closed. */
export function ticketBadge(ticket: Ticket, latest: Run | undefined): Badge {
  if (ticket.state === 'resolved') return { label: 'Resolved', short: 'Resolved', tone: 'resolved' }
  if (ticket.team_working || latest?.status === 'running') return { label: 'Team working…', short: 'Working…', tone: 'working' }
  if (latest?.status === 'done') return { label: 'Run finished, not resolved yet', short: 'Run finished', tone: 'finished' }
  if (latest?.status === 'stopped') return { label: 'Run stopped (budget)', short: 'Stopped', tone: 'failed' }
  if (latest?.status === 'error') return { label: 'Run failed', short: 'Failed', tone: 'failed' }
  return { label: 'Open', short: 'Open', tone: 'open' }
}
