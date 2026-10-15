import { useState } from 'react'
import type { Approval, ApprovalFacts, ApprovalMessage, ApprovalReview } from '../types.ts'
import { money } from '../summary.ts'

type Props = {
  approvals: Approval[]
  name: string
  onName: (name: string) => void
  busyId: number | null
  error: string | null
  onDecide: (id: number, approve: boolean) => void
}

function Case({ a, open = true }: { a: Approval; open?: boolean }) {
  const review = a.payload.review as ApprovalReview | undefined
  const facts = a.payload.facts as ApprovalFacts | undefined
  if (!review && !facts) return null
  const concerns = [...(facts?.warnings ?? []), ...(review?.concerns ?? [])]
  const message = a.kind === 'message' ? (a.payload as unknown as ApprovalMessage) : null
  return (
    <div className="case">
      {message && (
        <blockquote className="case-message">
          <p className="case-line">
            To {message.to}, ticket #{message.ticket_id}. <strong>{message.subject}</strong>
          </p>
          <p>{message.body}</p>
        </blockquote>
      )}
      {review && (
        <>
          <p className="case-why">
            <strong>Why:</strong> {review.justification}
          </p>
          {review.ticket_id && <p className="case-line">For ticket #{review.ticket_id}</p>}
        </>
      )}
      <p className={`case-concerns ${concerns.length ? 'has' : ''}`}>
        <strong>{concerns.length ? 'Concerns' : 'No concerns raised'}</strong>
      </p>
      {concerns.length > 0 && (
        <ul className="case-list concerns">
          {concerns.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
      {review?.margin_note && (
        <p className="case-line">
          <strong>Margin:</strong> {review.margin_note}
        </p>
      )}
      <details open={open}>
        <summary>What was checked</summary>
        {review && (
          <ul className="case-list">
            {review.checks.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
        {facts && (
          <ul className="case-list facts-list">
            <li>
              Cash {money(facts.cash_before)}
              {a.kind === 'payment' ? ` → ${money(facts.cash_after_this)} after this` : ''}
            </li>
            {facts.other_firm_obligations.map((o, i) => (
              <li key={i}>
                Also owed: {o.what}, {money(o.amount)}, due {o.due}
              </li>
            ))}
            <li>If everything open and owed were paid: {money(facts.cash_after_all_firm)}</li>
            {facts.vendor && (
              <li>
                {facts.vendor}: {facts.vendor_lead_days}-day lead time
              </li>
            )}
            <li>
              Open tickets: {facts.open_tickets.map((t) => `#${t.id} ${t.subject}`).join('; ')}
            </li>
          </ul>
        )}
      </details>
    </div>
  )
}

const KIND_LABEL: Record<Approval['kind'], string> = { payment: 'Payment', purchase: 'Purchase', message: 'Customer message' }

function Pile({ decided }: { decided: Approval[] }) {
  // The decided notes stack on the right; the top one is shown and the rest can be clicked through.
  const [pick, setPick] = useState<{ newest: number; id: number } | null>(null)
  const newest = decided[0]?.id
  const topIndex = Math.max(0, pick && pick.newest === newest ? decided.findIndex((a) => a.id === pick.id) : 0)
  const top = decided[topIndex]
  if (!top)
    return (
      <div className="pile">
        <div className="pile-head">
          <h3>Decided</h3>
        </div>
        <p className="muted small">Nothing decided yet.</p>
      </div>
    )
  const go = (step: number) => setPick({ newest, id: decided[(topIndex + step + decided.length) % decided.length].id })
  return (
    <div className="pile">
      <div className="pile-head">
        <h3>Decided</h3>
        {decided.length > 1 && (
          <div className="pile-nav">
            <button onClick={() => go(-1)} aria-label="Previous decision">‹</button>
            <span>
              {topIndex + 1} of {decided.length}
            </span>
            <button onClick={() => go(1)} aria-label="Next decision">›</button>
          </div>
        )}
      </div>
      <div className={`pile-stack count-${decided.length}`}>
        <div className={`approval ${top.status}`}>
          <span className={`status ${top.status}`}>
            {top.status === 'approved' ? '✓ Approved' : top.status === 'declined' ? 'Declined' : 'Failed'}
            {top.decided_by ? ` by ${top.decided_by}` : ''} · {KIND_LABEL[top.kind]}
          </span>
          <p>{top.summary}</p>
          {top.status !== 'failed' && <Case a={top} open={false} />}
          {top.status === 'failed' && top.result && <p className="err">{String(top.result.error ?? '')}</p>}
        </div>
      </div>
    </div>
  )
}

const clip = (t: string, n: number) => (t.length > n ? `${t.slice(0, n - 1)}…` : t)

function PendingStack({
  pending,
  noName,
  busyId,
  onDecide,
}: {
  pending: Approval[]
  noName: boolean
  busyId: number | null
  onDecide: (id: number, approve: boolean) => void
}) {
  // Any pending note can be brought to the front and decided in any order; the selection survives new notes arriving.
  const [pickedId, setPickedId] = useState<number | null>(null)
  if (pending.length === 0) return <div className="approval-stack empty" />
  const a = pending.find((p) => p.id === pickedId) ?? pending[0]
  return (
    <div className="approval-stack">
      {pending.length > 1 && (
        <div className="stack-chips" role="tablist" aria-label="Notes waiting for you">
          {pending.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={p.id === a.id}
              className={`chip ${p.id === a.id ? 'active' : ''} ${p.blocked ? 'blocked' : ''}`}
              onClick={() => setPickedId(p.id)}
              title={p.summary}
            >
              {KIND_LABEL[p.kind]}: {clip(p.summary.replace(/^(Pay|Place an order with|Reply to)\s*/, ''), 26)}
            </button>
          ))}
        </div>
      )}
      <div className={`pending-layers count-${Math.min(pending.length, 3)}`}>
        <div className="approval pending">
          <span className={`kind ${a.kind}`}>{KIND_LABEL[a.kind]}</span>
          <p>{a.summary}</p>
          <Case a={a} />
          {a.blocked && (
            <p className="blocked-warning" role="alert">
              ⚠ {a.block_reason}
            </p>
          )}
          <div className="actions">
            <button
              className="primary"
              disabled={noName || busyId === a.id || a.blocked}
              title={a.blocked ? (a.block_reason ?? undefined) : undefined}
              onClick={() => onDecide(a.id, true)}
            >
              {busyId === a.id ? 'Working…' : a.blocked ? 'Approval blocked' : 'Approve'}
            </button>
            <button disabled={noName || busyId === a.id} onClick={() => onDecide(a.id, false)}>
              Decline
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ApprovalsPanel({ approvals, name, onName, busyId, error, onDecide }: Props) {
  const pending = approvals.filter((a) => a.status === 'pending')
  // The three most recent decisions stay on the desk after approval, newest first.
  const decided = approvals
    .filter((a) => a.status !== 'pending')
    .sort((x, y) => (y.decided_at ?? '').localeCompare(x.decided_at ?? '') || y.id - x.id)
    .slice(0, 3)
  const noName = name.trim() === ''

  return (
    <div className="approvals">
      <div className="approval-control">
        <h2>
          Needs your approval {pending.length > 0 && <span className="count">{pending.length}</span>}
        </h2>
        <p className="muted small">
          Agents only prepare payments, purchases and customer messages. Cash changes only when you approve a payment or
          purchase here. An approved message is recorded on its ticket; nothing is sent.
        </p>
        <label className="name-field">
          Your name
          <input value={name} onChange={(e) => onName(e.target.value)} placeholder="Type your name to approve" maxLength={100} />
        </label>
        {error && <div className="banner error-banner">{error}</div>}
        {pending.length === 0 ? (
          <p className="muted">Nothing is waiting for you.</p>
        ) : (
          noName && <p className="muted small">Enter your name to enable the buttons.</p>
        )}
      </div>

      <PendingStack pending={pending} noName={noName} busyId={busyId} onDecide={onDecide} />

      <div className="approval-pile">
        <Pile decided={decided} />
      </div>
    </div>
  )
}
