import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from './api.ts'
import type { AgentEvent, Approval, Balance, Budget, Heartbeat, Run, Ticket } from './types.ts'
import { deriveActivity } from './activity.ts'
import BalanceCard, { type BalanceChange } from './components/BalanceCard.tsx'
import TicketList from './components/TicketList.tsx'
import TicketDetail from './components/TicketDetail.tsx'
import ApprovalsPanel from './components/ApprovalsPanel.tsx'
import RobotRow, { Legend, NameTags } from './components/RobotRow.tsx'
import Skyline from './components/Skyline.tsx'
import BudgetRing from './components/BudgetRing.tsx'
import PauseModal from './components/PauseModal.tsx'

const POLL_MS = 2000
const NAME_KEY = 'approverName'
export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [balance, setBalance] = useState<Balance | null>(null)
  const [change, setChange] = useState<BalanceChange | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [budget, setBudget] = useState<Budget | null>(null)
  const [beats, setBeats] = useState<{ at: number; agents: Heartbeat[] }>({ at: Date.now(), agents: [] })
  const [pauseOpen, setPauseOpen] = useState(true)
  const [resetBusy, setResetBusy] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [startingId, setStartingId] = useState<number | null>(null)
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? '')
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [approvalError, setApprovalError] = useState<string | null>(null)

  const cursor = useRef(0)
  const lastBalance = useRef<number | null>(null)
  const changeId = useRef(0)
  const changeTimer = useRef<number | undefined>(undefined)

  const refresh = useCallback(async () => {
    try {
      const [t, b, r, a, bu, hb] = await Promise.all([
        api.getTickets(),
        api.getBalance(),
        api.getRuns(),
        api.getApprovals(),
        api.getBudget(),
        api.getHeartbeats().catch(() => null), // the heartbeat is extra: if it fails, only the heartbeat lines go away
      ])
      setBudget(bu)
      setBeats({ at: Date.now(), agents: hb ? hb.agents : [] })
      setTickets(t.tickets)
      setRuns(r.runs)
      setApprovals(a.approvals)
      setBalance(b)
      setConnectionError(null)

      // Show how much the balance moved (for example after a payment is approved).
      if (lastBalance.current !== null && b.balance !== lastBalance.current) {
        changeId.current += 1
        setChange({ amount: Math.round((b.balance - lastBalance.current) * 100) / 100, id: changeId.current })
        window.clearTimeout(changeTimer.current)
        changeTimer.current = window.setTimeout(() => setChange(null), 12000)
      }
      lastBalance.current = b.balance

      // Pull every event we have not seen yet.
      let more = true
      while (more) {
        const e = await api.getEvents(cursor.current)
        cursor.current = e.next
        if (e.events.length) {
          setEvents((prev) => {
            const seen = new Set(prev.map((x) => x.index))
            return [...prev, ...e.events.filter((x) => !seen.has(x.index))]
          })
        }
        more = e.next < e.total && e.events.length > 0
      }
    } catch (err) {
      setConnectionError(err instanceof api.ApiError ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => void refresh(), POLL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [])

  // Each time the allowance runs out, ask again (it stays quiet once the person has chosen to stay paused).
  const wasPaused = useRef(false)
  useEffect(() => {
    if (budget?.paused && !wasPaused.current) setPauseOpen(true)
    wasPaused.current = !!budget?.paused
  }, [budget?.paused])

  useEffect(() => {
    if (selectedId === null && tickets.length > 0) setSelectedId((tickets.find((t) => t.state === 'open') ?? tickets[0]).id)
  }, [tickets, selectedId])

  const runsByTicket = useMemo(() => {
    const map = new Map<number, Run[]>()
    for (const r of runs) map.set(r.ticket_id, [...(map.get(r.ticket_id) ?? []), r])
    return map
  }, [runs])

  const latestRun = useCallback((id: number) => runsByTicket.get(id)?.at(-1), [runsByTicket])

  const eventsForTicket = useCallback(
    (id: number) => {
      // Only runs started since the backend last started, so a fresh start (or a database reset) shows a clean board.
      const mine = new Set(runs.filter((r) => r.ticket_id === id).map((r) => r.run_id))
      return events.filter((e) => mine.has(e.run_id))
    },
    [events, runs],
  )

  const startTicket = async (id: number) => {
    setActionError(null)
    setStartingId(id)
    setSelectedId(id)
    try {
      await api.runTicket(id)
      await refresh()
    } catch (err) {
      setActionError(err instanceof api.ApiError ? err.message : String(err))
    } finally {
      setStartingId(null)
    }
  }

  const decide = async (id: number, approve: boolean) => {
    setApprovalError(null)
    setBusyApproval(id)
    try {
      await (approve ? api.approve(id, name.trim()) : api.decline(id, name.trim()))
    } catch (err) {
      setApprovalError(err instanceof api.ApiError ? err.message : String(err))
    } finally {
      setBusyApproval(null)
      await refresh()
    }
  }

  const changeName = (value: string) => {
    setName(value)
    localStorage.setItem(NAME_KEY, value)
  }

  const { states, links, waits } = useMemo(() => deriveActivity(events, runs, now), [events, runs, now])

  const continueTeam = async () => {
    setResetError(null)
    setResetBusy(true)
    try {
      setBudget(await api.resetBudget(name.trim()))
      setPauseOpen(false)
    } catch (err) {
      setResetError(err instanceof api.ApiError ? err.message : String(err))
    } finally {
      setResetBusy(false)
      await refresh()
    }
  }

  const paused = !!budget?.paused
  const busyTicket = tickets.find((t) => t.team_working)?.id ?? runs.find((r) => r.status === 'running')?.ticket_id ?? null
  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const pendingCount = approvals.filter((a) => a.status === 'pending').length

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Campus Customs Agent Board</h1>
          <p className="muted">
            Pick a ticket on your desk and start the team. Nothing runs on its own.
            {pendingCount > 0 && <strong className="attention"> {pendingCount} waiting for your approval.</strong>}
          </p>
        </div>
        <Legend />
      </header>

      {connectionError && <div className="banner error-banner">{connectionError}</div>}
      {actionError && <div className="banner error-banner">{actionError}</div>}
      {paused && !pauseOpen && (
        <div className="banner paused-banner">
          Paused: the daily token allowance is used. Approvals still work.{' '}
          <button onClick={() => setPauseOpen(true)}>Review</button>
        </div>
      )}

      <div className="office">
        <div className="window">
          <Skyline />
          <span className="mullion m1" />
          <span className="mullion m2" />
          <RobotRow states={states} links={links} waits={waits} />
        </div>

        <div className="cubicle">
          <NameTags states={states} beats={beats.agents} fetchedAt={beats.at} now={now} />
          <div className="wall">
            {selected ? (
              <TicketDetail ticket={selected} runs={runsByTicket.get(selected.id) ?? []} events={eventsForTicket(selected.id)} />
            ) : (
              <p className="wall-empty">{connectionError ? '' : 'Loading tickets…'}</p>
            )}
          </div>

          <div className="desk">
            <div className="desk-ledger">
              <BalanceCard balance={balance} change={change} />
            </div>
            <section className="desk-tickets">
              <h2>On your desk</h2>
              <TicketList
                tickets={tickets}
                latestRun={latestRun}
                selectedId={selectedId}
                startingId={startingId}
                paused={paused}
                busyTicket={busyTicket}
                onSelect={setSelectedId}
                onStart={(id) => void startTicket(id)}
              />
            </section>
            <aside className="desk-notes">
              <ApprovalsPanel
                approvals={approvals}
                name={name}
                onName={changeName}
                busyId={busyApproval}
                error={approvalError}
                onDecide={(id, approve) => void decide(id, approve)}
              />
            </aside>
          </div>
        </div>
      </div>

      <BudgetRing budget={budget} onClick={() => budget?.paused && setPauseOpen(true)} />
      {budget && paused && pauseOpen && (
        <PauseModal
          budget={budget}
          name={name}
          onName={changeName}
          busy={resetBusy}
          error={resetError}
          onContinue={() => void continueTeam()}
          onStay={() => setPauseOpen(false)}
        />
      )}
    </div>
  )
}
