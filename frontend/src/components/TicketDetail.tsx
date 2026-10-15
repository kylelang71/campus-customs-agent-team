import type { AgentEvent, Run, Ticket } from '../types.ts'
import { clip, shortMessage, ticketBadge } from '../summary.ts'

type Props = { ticket: Ticket; runs: Run[]; events: AgentEvent[] }

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function eventLine(e: AgentEvent): string {
  if (e.kind === 'status' && e.message) return `Boss to you: “${e.message}”`
  if (e.kind === 'message' && e.message) return `${e.summary}: “${shortMessage(e.message)}”`
  if (e.kind === 'received' && e.message) return `${e.summary}: “${clip(e.message, 140)}”`
  return e.summary
}

export default function TicketDetail({ ticket, runs, events }: Props) {
  const latest = runs[runs.length - 1]
  const badge = ticketBadge(ticket, latest)
  const timeline = events.filter((e) => e.kind !== 'usage')
  const statuses = events.filter((e) => e.kind === 'status' && e.message)
  const latestStatus = statuses[statuses.length - 1]
  const working = badge.tone === 'working'

  return (
    <div className="detail">
      <header className="detail-head">
        <h2>
          Ticket #{ticket.id}: {ticket.subject}
        </h2>
        <span className={`badge big ${badge.tone}`}>
          {ticket.state === 'resolved' && <span aria-hidden="true">✓ </span>}
          {badge.tone === 'working' && <span className="spinner" aria-hidden="true" />}
          {badge.label}
        </span>
      </header>

      {ticket.state === 'resolved' && (
        <div className="banner resolved-banner">
          ✓ The team resolved this ticket{latest?.status === 'done' ? ' and the run has finished' : ''}.
        </div>
      )}
      {ticket.state !== 'resolved' && latest?.status === 'done' && (
        <div className="banner finished-banner">
          The run finished but the ticket is still open. It may be waiting for a human approval on the right.
        </div>
      )}
      {latest?.error && <div className="banner error-banner">{latest.error}</div>}

      {(latestStatus || working || latest?.result) && (
        <div className={`boss-note ${working ? 'live' : ''}`} aria-live="polite">
          <div className="boss-note-head">
            <strong>From the Boss</strong>
            {working && <span className="spinner" aria-hidden="true" />}
            {latestStatus && <span className="boss-note-time">{time(latestStatus.time)}</span>}
          </div>
          <p>{latestStatus?.message ?? (working ? 'Getting started…' : shortMessage(latest?.result ?? ''))}</p>
          {statuses.length > 1 && (
            <details>
              <summary>Earlier updates ({statuses.length - 1})</summary>
              <ul>
                {statuses
                  .slice(0, -1)
                  .reverse()
                  .map((e) => (
                    <li key={e.index}>
                      <span className="ev-time">{time(e.time)}</span> {e.message}
                    </li>
                  ))}
              </ul>
            </details>
          )}
        </div>
      )}

      <dl className="facts">
        <dt>Request</dt>
        <dd>
          {ticket.type.replace('_', ' ')} from {ticket.requester}
          {ticket.sku ? `, ${ticket.qty ?? ''} × ${ticket.sku}${ticket.size ? ` (size ${ticket.size})` : ''}` : ''}
        </dd>
        <dt>Notes</dt>
        <dd>{ticket.notes ?? 'None'}</dd>
      </dl>

      <h3>Timeline</h3>
      {timeline.length === 0 ? (
        <p className="muted">No agent has worked on this ticket yet. Press “Start the team” to begin.</p>
      ) : (
        <ol className="timeline">
          {timeline.map((e) => (
            <li key={e.index} className={`ev ${e.kind}`}>
              <span className="ev-time">{time(e.time)}</span>
              <span className="ev-text">{eventLine(e)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
