export type Ticket = {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'closed'
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
  team_working: boolean
}

export type TicketsResponse = { tickets: Ticket[]; open: number; resolved: number }

export type Balance = { account: string; balance: number; balance_date: string; shop_date: string }

export type Run = {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'stopped' | 'error'
  result: string | null
  error: string | null
}

export type AgentEvent = {
  index: number
  summary: string
  time: string
  run_id: string
  agent: string
  kind: 'received' | 'tool_call' | 'message' | 'status' | 'approval' | 'usage' | 'budget_reset' | 'error'
  step?: number
  from?: string
  to?: string
  tool?: string
  arguments?: Record<string, unknown>
  returned?: unknown
  message?: string
}

export type Budget = { limit: number; spent: number; remaining: number; percent: number; paused: boolean }

export type EventsResponse = { events: AgentEvent[]; next: number; total: number }

export type ApprovalReview = {
  justification: string
  checks: string[]
  concerns: string[]
  margin_note: string | null
  ticket_id: number | null
}

export type ApprovalFacts = {
  shop_date: string
  cash_before: number
  cash_after_this: number
  other_firm_obligations: { what: string; amount: number; due: string }[]
  other_firm_obligations_total: number
  cash_after_all_firm: number
  open_tickets: { id: number; type: string; subject: string }[]
  warnings: string[]
  due?: string
  days_overdue?: number
  days_until_due?: number
  vendor?: string
  vendor_lead_days?: number
}

export type ApprovalMessage = { ticket_id: number; to: string; subject: string; body: string }

export type Heartbeat = {
  agent: string
  run_id: string
  doing: string
  seconds_running: number
  seconds_in_step: number
  beat_age: number // seconds since the agent's last heartbeat tick, when the backend answered
  beats: number
}

export type Approval = {
  id: number
  kind: 'payment' | 'purchase' | 'message'
  payload: Record<string, unknown>
  summary: string
  status: 'pending' | 'approved' | 'declined' | 'failed'
  created_at: string
  decided_at: string | null
  decided_by: string | null
  result: Record<string, unknown> | null
  blocked?: boolean // a pending payment that would take checking below zero
  block_reason?: string | null
}
