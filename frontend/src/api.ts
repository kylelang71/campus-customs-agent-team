import type { Approval, Balance, Budget, EventsResponse, Heartbeat, Run, Ticket, TicketsResponse } from './types.ts'

// The board calls the backend directly at http://localhost:8000 (the backend allows this page's origin).
// Set VITE_API_BASE to point somewhere else.
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the backend at ${BASE}. Start it from the backend folder with: uvicorn main:app --reload --port 8000`,
    )
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const getTickets = () => request<TicketsResponse>('/api/tickets')
export const getBalance = () => request<Balance>('/api/balance')
export const getRuns = () => request<{ runs: Run[] }>('/api/runs')
export const getEvents = (after: number) => request<EventsResponse>(`/api/events?after=${after}&limit=1000`)
export const getHeartbeats = () => request<{ interval: number; agents: Heartbeat[] }>('/api/heartbeats')
export const getBudget = () => request<Budget>('/api/budget')
export const getApprovals = () => request<{ approvals: Approval[] }>('/api/approvals')

export const runTicket = (id: number) => post<{ run_id: string; ticket_id: number }>(`/api/tickets/${id}/run`)
export const approve = (id: number, name: string) => post<Approval>(`/api/approvals/${id}/approve`, { name })
export const resetBudget = (name: string) => post<Budget>('/api/budget/reset', { name })
export const decline = (id: number, name: string) => post<Approval>(`/api/approvals/${id}/decline`, { name })

export type { Ticket }
