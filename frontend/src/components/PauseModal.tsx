import type { Budget } from '../types.ts'
import { money } from '../summary.ts'

type Props = {
  budget: Budget
  name: string
  onName: (name: string) => void
  busy: boolean
  error: string | null
  onContinue: () => void
  onStay: () => void
}

export default function PauseModal({ budget, name, onName, busy, error, onContinue, onStay }: Props) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="pause-title">
      <div className="modal">
        <h2 id="pause-title">Paused: the daily allowance is used</h2>
        <p>
          The team has used {money(budget.spent)} of its {money(budget.limit)} token allowance for today, so everything is paused.
          Continuing starts a fresh {money(budget.limit)} allowance.
        </p>
        <label className="name-field">
          Your name (recorded with your permission)
          <input value={name} onChange={(e) => onName(e.target.value)} placeholder="Type your name" maxLength={100} />
        </label>
        {error && <div className="banner error-banner">{error}</div>}
        <div className="actions">
          <button className="primary" disabled={busy || name.trim() === ''} onClick={onContinue}>
            {busy ? 'Working…' : `Allow another ${money(budget.limit).replace('.00', '')} and continue`}
          </button>
          <button disabled={busy} onClick={onStay}>
            Stay paused
          </button>
        </div>
      </div>
    </div>
  )
}
