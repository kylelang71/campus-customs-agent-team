import type { Budget } from '../types.ts'
import { money } from '../summary.ts'

const R = 34
const C = 2 * Math.PI * R

/** Floating allowance meter: a gray ring that fills with purple, clockwise, until $10 has been used. */
export default function BudgetRing({ budget, onClick }: { budget: Budget | null; onClick: () => void }) {
  const pct = budget ? budget.percent : 0
  const full = !!budget?.paused
  return (
    <button
      className={`budget-ring ${full ? 'full' : ''}`}
      onClick={onClick}
      title={budget ? `${money(budget.spent)} of ${money(budget.limit)} daily token allowance used` : 'Daily token allowance'}
      aria-label={budget ? `${money(budget.spent)} of ${money(budget.limit)} daily token allowance used` : 'Daily token allowance'}
    >
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={R} className="ring-track" />
        <circle
          cx="44"
          cy="44"
          r={R}
          className="ring-fill"
          strokeDasharray={`${(C * pct) / 100} ${C}`}
          transform="rotate(-90 44 44)"
        />
      </svg>
      <span className="ring-text">
        <strong>{budget ? money(budget.spent) : '…'}</strong>
        <small>{full ? 'paused' : `of ${budget ? money(budget.limit).replace('.00', '') : '$10'}`}</small>
      </span>
    </button>
  )
}
