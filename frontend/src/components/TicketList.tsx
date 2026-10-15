import type { Run, Ticket } from '../types.ts'
import { ticketBadge } from '../summary.ts'

type Props = {
  tickets: Ticket[]
  latestRun: (ticketId: number) => Run | undefined
  selectedId: number | null
  startingId: number | null
  paused: boolean
  busyTicket: number | null // the ticket the team is working on right now, if any
  onSelect: (id: number) => void
  onStart: (id: number) => void
}

export default function TicketList({ tickets, latestRun, selectedId, startingId, paused, busyTicket, onSelect, onStart }: Props) {
  return (
    <ul className="papers">
      {tickets.map((t) => {
        const run = latestRun(t.id)
        const badge = ticketBadge(t, run)
        const busy = badge.tone === 'working' || startingId === t.id
        const teamBusyElsewhere = busyTicket !== null && busyTicket !== t.id
        const resolved = t.state === 'resolved'
        return (
          <li key={t.id}>
            <div
              className={`ticket-card ${resolved ? 'is-resolved' : ''} ${selectedId === t.id ? 'is-selected' : ''}`}
              onClick={() => onSelect(t.id)}
            >
              <div className="ticket-top">
                <span className="ticket-id">#{t.id}</span>
                <span className={`badge ${badge.tone}`}>
                  {resolved && <span aria-hidden="true">✓ </span>}
                  {badge.tone === 'working' && <span className="spinner" aria-hidden="true" />}
                  {badge.short}
                </span>
              </div>
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-meta">
                {t.type.replace('_', ' ')} · {t.requester}
              </div>
              <button
                className="primary"
                disabled={resolved || busy || paused || teamBusyElsewhere}
                title={paused ? 'The daily allowance is used. Allow the team to continue first.' : teamBusyElsewhere ? `The team is busy with ticket #${busyTicket}. One ticket at a time.` : undefined}
                onClick={(e) => {
                  e.stopPropagation()
                  onStart(t.id)
                }}
              >
                {resolved ? 'Resolved' : busy ? 'Working…' : teamBusyElsewhere ? `Team busy on #${busyTicket}` : run ? 'Run the team again' : 'Start the team'}
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
