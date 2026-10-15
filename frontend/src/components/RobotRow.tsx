import { useLayoutEffect, useRef, useState } from 'react'
import { ACCENT, AGENTS, caption, type AgentState, type Link, type Wait } from '../activity.ts'
import type { Heartbeat } from '../types.ts'
import Robot from './Robot.tsx'

type Props = { states: Record<string, AgentState>; links: Link[]; waits: Wait[] }

const HEAD_TOP = 74 // y of the top of a head inside the row, used to anchor the lines between robots
const ARC = 48

const STALE_BEAT_S = 6 // the backend ticks every 2 s; this many seconds without a tick means something is wrong
const SLOW_MODEL_S = 30 // a model call longer than this is called slow

/** The heartbeat line for one agent: a pulsing heart, what it is doing right now and for how long. */
function BeatLine({ beat, fetchedAt, now }: { beat: Heartbeat | undefined; fetchedAt: number; now: number }) {
  if (!beat) return null
  const since = Math.max(0, (now - fetchedAt) / 1000)
  const secs = Math.round(beat.seconds_in_step + since)
  const stale = beat.beat_age > STALE_BEAT_S // as measured by the backend when it answered, so a slow browser poll can't cause a false alarm
  const slow = beat.doing === 'waiting for the model' && secs > SLOW_MODEL_S
  const text = stale ? `no heartbeat for ${Math.round(beat.beat_age)}s` : `${beat.doing} · ${secs}s${slow ? ' (slow reply)' : ''}`
  return (
    <span className={`nt-beat ${stale ? 'stale' : ''} ${slow ? 'slow' : ''}`} title={`Heartbeat ${beat.beats}: working for ${Math.round(beat.seconds_running + since)}s in total`}>
      <span className="nt-heart" aria-hidden="true">♥</span> {text}
    </span>
  )
}

/** Name tags clipped to the top of the wall, one under each robot, with the agent's colour, what it is doing and its heartbeat. */
export function NameTags({ states, beats, fetchedAt, now }: { states: Record<string, AgentState>; beats: Heartbeat[]; fetchedAt: number; now: number }) {
  return (
    <div className="tags">
      {AGENTS.map((name) => {
        // an agent can have several tasks running; show the one that changed most recently
        const beat = beats.filter((b) => b.agent === name).sort((a, b) => a.seconds_in_step - b.seconds_in_step)[0]
        return (
          <div key={name} className={`tag-slot mode-${states[name].mode}`}>
            <div className="nametag" style={{ borderLeftColor: ACCENT[name] }}>
              <span className="nt-name">{name}</span>
              <span className="nt-state">{caption(states[name])}</span>
              <BeatLine beat={beat} fetchedAt={fetchedAt} now={now} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** What the robot poses mean. */
export function Legend() {
  const items: [string, string, string][] = [
    ['idle', 'Idle', 'no task'],
    ['working', 'Working', 'on its own'],
    ['exchanging', 'Passing information', 'to a teammate'],
    ['waiting', 'Waiting', 'for a teammate to finish'],
  ]
  return (
    <ul className="legend" aria-label="What the robots are doing">
      {items.map(([mode, name, note]) => (
        <li key={mode}>
          <span className={`swatch ${mode}`} aria-hidden="true" />
          <strong>{name}</strong> <span>{note}</span>
        </li>
      ))}
    </ul>
  )
}

export default function RobotRow({ states, links, waits }: Props) {
  const row = useRef<HTMLDivElement>(null)
  const [centers, setCenters] = useState<Record<string, number>>({})
  const [width, setWidth] = useState(0)

  useLayoutEffect(() => {
    const measure = () => {
      const el = row.current
      if (!el) return
      const next: Record<string, number> = {}
      el.querySelectorAll<HTMLElement>('.robot-slot').forEach((slot) => {
        next[slot.dataset.agent!] = slot.offsetLeft + slot.offsetWidth / 2
      })
      setCenters(next)
      setWidth(el.clientWidth)
    }
    measure()
    const ro = new ResizeObserver(measure)
    if (row.current) ro.observe(row.current)
    return () => ro.disconnect()
  }, [])

  const arc = (a: number, b: number, lift: number) => `M ${a} ${HEAD_TOP} Q ${(a + b) / 2} ${HEAD_TOP - lift} ${b} ${HEAD_TOP}`

  return (
    <div className="robots" ref={row}>
      {AGENTS.map((name) => {
        const s = states[name]
        const toward = s.mode === 'exchanging' ? s.partner : s.mode === 'waiting' ? s.waitingOn[0] : null
        const look = toward ? (AGENTS.indexOf(toward as never) > AGENTS.indexOf(name) ? 1 : -1) : 0
        return (
          <div key={name} className="robot-slot" data-agent={name}>
            <Robot agent={name} mode={s.mode} look={look as -1 | 0 | 1} caption={caption(s)} />
          </div>
        )
      })}
      <svg className="links" width={width} height={HEAD_TOP + 10} aria-hidden="true">
        <defs>
          <marker id="wait-arrow" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 8 4 L 0 8 z" className="wait-arrow" />
          </marker>
        </defs>
        {waits.map((w, i) => {
          const a = centers[w.from]
          const b = centers[w.to]
          if (a === undefined || b === undefined) return null
          return <path key={`w-${w.from}-${w.to}-${i}`} d={arc(a, b, 26)} className="wait-line" markerEnd="url(#wait-arrow)" />
        })}
        {links.map((l, i) => {
          const a = centers[l.from]
          const b = centers[l.to]
          if (a === undefined || b === undefined) return null
          const d = arc(a, b, ARC)
          return (
            <g key={`${l.from}-${l.to}-${i}`} className={l.kind}>
              <path d={d} className="link-line" />
              <circle r="4.5" className="link-dot">
                <animateMotion dur="1.1s" repeatCount="indefinite" path={d} />
              </circle>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
