import { useEffect, useRef, useState } from 'react'
import { ACCENT, type Mode } from '../activity.ts'

type Props = { agent: string; mode: Mode; look: -1 | 0 | 1; caption: string }

const EYE_L = { x: 27, y: 34 }
const EYE_R = { x: 46, y: 34 }

/** The shape of the head and the eyes differ by role, so the five agents are easy to tell apart. */
function Eyes({ agent }: { agent: string }) {
  switch (agent) {
    case 'Boss': // a single wide visor
      return <rect x="22" y="34" width="40" height="9" rx="4.5" className="eye" />
    case 'Inventory': // round eyes
      return (
        <>
          <circle cx="33" cy="38" r="5.5" className="eye" />
          <circle cx="51" cy="38" r="5.5" className="eye" />
        </>
      )
    case 'Accounting': // small eyes behind glasses
      return (
        <>
          <rect x="28" y="36" width="9" height="6" rx="2.5" className="eye" />
          <rect x="47" y="36" width="9" height="6" rx="2.5" className="eye" />
        </>
      )
    case 'Facilities': // square eyes
      return (
        <>
          <rect x={EYE_L.x} y="35" width="10" height="10" rx="2" className="eye" />
          <rect x={EYE_R.x} y="35" width="10" height="10" rx="2" className="eye" />
        </>
      )
    default: // Customer Service: wide ovals
      return (
        <>
          <ellipse cx="33" cy="39" rx="7" ry="4.6" className="eye" />
          <ellipse cx="51" cy="39" rx="7" ry="4.6" className="eye" />
        </>
      )
  }
}

function Head({ agent }: { agent: string }) {
  switch (agent) {
    case 'Boss':
      return (
        <>
          <rect x="6" y="17" width="72" height="51" rx="9" className="head" />
          <rect x="22" y="17" width="40" height="6" rx="3" className="trim" />
          <rect x="18" y="26" width="48" height="33" rx="7" className="face" />
        </>
      )
    case 'Inventory':
      return (
        <>
          <line x1="30" y1="17" x2="30" y2="8" className="antenna" />
          <line x1="54" y1="17" x2="54" y2="8" className="antenna" />
          <rect x="27" y="4" width="6" height="5" rx="1" className="trim" />
          <rect x="51" y="4" width="6" height="5" rx="1" className="trim" />
          <rect x="14" y="17" width="56" height="52" rx="7" className="head" />
          <rect x="19" y="26" width="46" height="33" rx="5" className="face" />
          <rect x="36" y="19" width="5" height="5" className="trim" />
          <rect x="43" y="19" width="5" height="5" className="trim" />
        </>
      )
    case 'Accounting':
      return (
        <>
          <line x1="42" y1="17" x2="42" y2="8" className="antenna" />
          <rect x="38" y="3" width="8" height="6" rx="1.5" className="trim" />
          <rect x="11" y="17" width="62" height="51" rx="23" className="head" />
          <rect x="18" y="26" width="48" height="33" rx="15" className="face" />
          <g className="glasses">
            <rect x="25" y="33" width="15" height="12" rx="4" />
            <rect x="44" y="33" width="15" height="12" rx="4" />
            <line x1="40" y1="39" x2="44" y2="39" />
          </g>
        </>
      )
    case 'Facilities':
      return (
        <>
          <rect x="11" y="24" width="62" height="44" rx="13" className="head" />
          <rect x="18" y="30" width="48" height="29" rx="9" className="face" />
          <path d="M 14 27 Q 14 3 42 3 Q 70 3 70 27 Z" className="hat" />
          <rect x="7" y="25" width="70" height="6" rx="3" className="hat" />
          <rect x="38" y="6" width="8" height="12" rx="2" className="hat-ridge" />
        </>
      )
    default: // Customer Service: round head with a headset
      return (
        <>
          <rect x="14" y="17" width="56" height="52" rx="25" className="head" />
          <rect x="20" y="26" width="44" height="33" rx="15" className="face" />
          <path d="M 13 42 A 29 27 0 0 1 71 42" className="band" />
          <rect x="6" y="36" width="9" height="19" rx="4.5" className="cup" />
          <rect x="69" y="36" width="9" height="19" rx="4.5" className="cup" />
          <path d="M 10 54 Q 12 66 30 64" className="boom" />
          <circle cx="31" cy="64" r="3" className="cup" />
        </>
      )
  }
}

/** A small, flat robot. Only the head clears the window sill; the body stays hidden behind the wall. */
export default function Robot({ agent, mode, look, caption }: Props) {
  const [hop, setHop] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  // The hop lasts 0.6s; a timer (not animationend) resets it, so it replays every time and never sticks.
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const startHop = () => {
    if (hop) return
    setHop(true)
    timer.current = window.setTimeout(() => setHop(false), 650)
  }

  return (
    <div className={`robot-col mode-${mode}`} style={{ ['--accent' as string]: ACCENT[agent] }}>
      <div className={`robot-hop ${hop ? 'hop' : ''}`} onMouseEnter={startHop}>
        <div className="robot-bob">
          <svg viewBox="0 0 84 100" width="84" height="100" role="img" aria-label={`${agent}: ${caption}`}>
            <rect x="22" y="68" width="40" height="32" rx="9" className="body" />
            <Head agent={agent} />
            <circle cx="68" cy="22" r="3.6" className="led" />
            <g className="eyes" style={{ transform: `translateX(${look * 4}px)` }}>
              <Eyes agent={agent} />
            </g>
            <g className="mouth">
              {[0, 1, 2, 3].map((i) => (
                <rect key={i} x={33 + i * 5.5} y="49" width="3" height="7" rx="1.5" className={`bar bar-${i}`} />
              ))}
            </g>
            <g className="wait-dots" transform={agent === 'Facilities' ? 'translate(0 -8)' : undefined}>
              <circle cx="32" cy="-4" r="3" />
              <circle cx="42" cy="-4" r="3" />
              <circle cx="52" cy="-4" r="3" />
            </g>
          </svg>
        </div>
      </div>
    </div>
  )
}
