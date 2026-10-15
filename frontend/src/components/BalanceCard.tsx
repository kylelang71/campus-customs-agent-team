import type { Balance } from '../types.ts'
import { money } from '../summary.ts'

export type BalanceChange = { amount: number; id: number }

export default function BalanceCard({ balance, change }: { balance: Balance | null; change: BalanceChange | null }) {
  return (
    <div className="balance" aria-live="polite">
      <span className="balance-label">Checking balance</span>
      <span className="balance-amount">{balance ? money(balance.balance) : '…'}</span>
      {change && (
        <span key={change.id} className={`balance-change ${change.amount < 0 ? 'down' : 'up'}`}>
          {change.amount < 0 ? '−' : '+'}
          {money(Math.abs(change.amount))}
        </span>
      )}
      {balance && <span className="balance-date">shop date {balance.shop_date}</span>}
    </div>
  )
}
