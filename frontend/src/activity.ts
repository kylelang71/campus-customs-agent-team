import type { AgentEvent, Run } from './types.ts'

export const AGENTS = ['Boss', 'Inventory', 'Accounting', 'Facilities', 'Customer Service'] as const
export type AgentName = (typeof AGENTS)[number]
export type Mode = 'idle' | 'working' | 'waiting' | 'exchanging'

export type AgentState = {
  mode: Mode
  partner: string | null // who they are exchanging with right now
  direction: 'out' | 'in' | null
  waitingOn: string[] // teammates this agent has handed work to and is still waiting for
  quietMs: number | null // how long a working agent has gone without logging anything
}
export type Link = { from: string; to: string; kind: 'handoff' | 'checkin' }
export type Wait = { from: string; to: string } // `from` is waiting on `to`

/** How long a hand-off (a task sent, an answer returned, a check-in) is shown as information changing hands. */
export const EXCHANGE_MS = 3500
const QUIET_NOTICE_MS = 45_000

const isAgent = (name: string | undefined): name is AgentName => !!name && (AGENTS as readonly string[]).includes(name)

type Task = { id: number; agent: string; parent: number | null; open: boolean }

/**
 * What each agent is doing right now, worked out from the events of runs that are still going.
 *
 * Every task an agent receives is tracked separately (the same agent can have several at once, for example
 * when it asked the Boss something and the Boss then asked it a question back), and each task knows which
 * task it was spawned from. A task is "waiting" only while a task it spawned is still open; the task at the
 * end of every chain is the one that is actually working. So somebody is always working while a run is
 * going, and "waiting" always names who the agent is waiting on.
 *
 *  - exchanging: a task, an answer or a check-in was passed between two agents in the last few seconds
 *  - working: it has a task and nobody it asked is still busy
 *  - waiting: every task it has is waiting on a teammate to finish
 *  - idle: no task
 */
export function deriveActivity(events: AgentEvent[], runs: Run[], nowMs: number) {
  const fresh = (e: AgentEvent) => nowMs - Date.parse(e.time) < EXCHANGE_MS
  const states = Object.fromEntries(
    AGENTS.map((a) => [a, { mode: 'idle', partner: null, direction: null, waitingOn: [], quietMs: null } as AgentState]),
  ) as Record<AgentName, AgentState>
  const links: Link[] = []
  const waits: Wait[] = []

  for (const run of runs.filter((r) => r.status === 'running')) {
    const tasks: Task[] = []
    const lastSeen = new Map<string, number>()
    const openTaskOf = (agent: string | undefined) => tasks.findLast((t) => t.open && t.agent === agent)

    for (const e of events.filter((x) => x.run_id === run.run_id)) {
      if (e.kind === 'usage') continue
      lastSeen.set(e.agent, Date.parse(e.time))
      if (e.kind === 'received') {
        tasks.push({ id: tasks.length, agent: e.agent, parent: openTaskOf(e.from)?.id ?? null, open: true })
        if (isAgent(e.from) && fresh(e)) links.push({ from: e.from, to: e.agent, kind: 'handoff' })
      } else if (e.kind === 'message' || e.kind === 'error') {
        const t = openTaskOf(e.agent)
        if (t) t.open = false
        if (e.kind === 'message' && isAgent(e.to) && fresh(e)) links.push({ from: e.agent, to: e.to, kind: 'handoff' })
      } else if (e.kind === 'tool_call' && e.tool === 'check_in' && isAgent(e.to) && fresh(e)) {
        links.push({ from: e.agent, to: e.to, kind: 'checkin' })
      }
    }

    const open = tasks.filter((t) => t.open && isAgent(t.agent))
    for (const t of open) {
      const children = open.filter((c) => c.parent === t.id)
      const s = states[t.agent as AgentName]
      if (children.length) {
        for (const c of children) {
          if (!s.waitingOn.includes(c.agent)) s.waitingOn.push(c.agent)
          waits.push({ from: t.agent, to: c.agent })
        }
        if (s.mode === 'idle') s.mode = 'waiting'
      } else {
        s.mode = 'working'
        const seen = lastSeen.get(t.agent)
        s.quietMs = seen ? Math.max(nowMs - seen, 0) : null
      }
    }
  }

  // Only show a "waiting on" arrow from an agent that is actually waiting (not one that is busy on another task).
  const waitingNow = waits.filter((w) => states[w.from as AgentName]?.mode === 'waiting')

  for (const l of links) {
    if (!isAgent(l.from) || !isAgent(l.to)) continue
    states[l.from] = { ...states[l.from], mode: 'exchanging', partner: l.to, direction: 'out' }
    states[l.to] = { ...states[l.to], mode: 'exchanging', partner: l.from, direction: 'in' }
  }
  return { states, links, waits: waitingNow }
}

const clock = (ms: number) => {
  const s = Math.round(ms / 1000)
  return s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`
}

export function caption(s: AgentState): string {
  if (s.mode === 'exchanging') return s.direction === 'out' ? `sending to ${s.partner}` : `hearing from ${s.partner}`
  if (s.mode === 'waiting') return `waiting on ${s.waitingOn.join(', ')}`
  if (s.mode === 'working') return s.quietMs !== null && s.quietMs > QUIET_NOTICE_MS ? `working, quiet ${clock(s.quietMs)}` : 'working'
  return 'idle'
}

/** Each agent's accent colour: used on the robot, its name tag and in the key. */
export const ACCENT: Record<string, string> = {
  Boss: '#1f3a5f',
  Inventory: '#1f8f84',
  Accounting: '#3b7d4f',
  Facilities: '#d9772b',
  'Customer Service': '#c4508a',
}
