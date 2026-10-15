// A calm New York skyline seen through the office window: pale sky, drifting clouds, layered towers,
// with the Chrysler Building, the Empire State Building and One World Trade Center standing out.

function seeded(seed: number) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return s / 2147483647
  }
}

function towers(seed: number, count: number, minH: number, maxH: number, from: number, to: number) {
  const rand = seeded(seed)
  const out: { x: number; w: number; h: number }[] = []
  const step = (to - from) / count
  for (let i = 0; i < count; i++) {
    const w = step * (0.7 + rand() * 0.6)
    out.push({ x: from + i * step + rand() * step * 0.3, w, h: minH + rand() * (maxH - minH) })
  }
  return out
}

const FAR = towers(7, 46, 50, 150, -20, 1220)
const MID = towers(21, 30, 90, 200, -20, 1220)
const NEAR = towers(5, 22, 40, 118, -20, 1220)

function Lights({ list, base }: { list: { x: number; w: number; h: number }[]; base: number }) {
  const rand = seeded(99)
  return (
    <>
      {list.flatMap((b, i) =>
        Array.from({ length: Math.floor(b.h / 24) }, (_, r) =>
          rand() > 0.55 ? <rect key={`${i}-${r}`} x={b.x + b.w * 0.25} y={base - b.h + 8 + r * 24} width={b.w * 0.18} height="5" className="lit" /> : null,
        ),
      )}
    </>
  )
}

export default function Skyline() {
  const base = 330
  return (
    <svg className="skyline" viewBox="0 0 1200 330" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#86b3e6" />
          <stop offset="0.7" stopColor="#d5e5f6" />
          <stop offset="1" stopColor="#eef4fb" />
        </linearGradient>
        <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <rect width="1200" height="330" fill="url(#sky)" />

      <g className="clouds">
        <g className="cloud c1">
          <ellipse cx="180" cy="70" rx="90" ry="16" />
          <ellipse cx="240" cy="62" rx="60" ry="14" />
          <ellipse cx="140" cy="62" rx="50" ry="11" />
        </g>
        <g className="cloud c2">
          <ellipse cx="620" cy="46" rx="110" ry="14" />
          <ellipse cx="690" cy="40" rx="64" ry="12" />
        </g>
        <g className="cloud c3">
          <ellipse cx="980" cy="86" rx="100" ry="15" />
          <ellipse cx="920" cy="80" rx="54" ry="11" />
        </g>
      </g>

      <g fill="#b3c4d9">
        {FAR.map((b, i) => (
          <rect key={i} x={b.x} y={base - b.h} width={b.w} height={b.h} />
        ))}
      </g>

      <g fill="#7f94b2">
        {MID.map((b, i) => (
          <rect key={i} x={b.x} y={base - b.h} width={b.w} height={b.h} />
        ))}
        {/* Chrysler Building */}
        <rect x="505" y="150" width="44" height="180" />
        <path d="M 505 150 Q 527 96 549 150 Z" />
        <path d="M 513 138 Q 527 104 541 138" fill="#6a809f" />
        <rect x="525.5" y="62" width="3" height="48" />
        {/* Empire State Building */}
        <rect x="738" y="180" width="62" height="150" />
        <rect x="747" y="140" width="44" height="40" />
        <rect x="755" y="108" width="28" height="32" />
        <rect x="761" y="80" width="16" height="28" />
        <polygon points="763,80 775,80 771,46 767,46" />
        <rect x="768" y="14" width="2.5" height="34" />
        {/* One World Trade Center */}
        <polygon points="962,330 1004,330 996,110 970,110" />
        <polygon points="978,110 988,110 984.5,24 981.5,24" />
        <rect x="982.8" y="2" width="2.4" height="26" />
      </g>

      <g fill="#42536c">
        {NEAR.map((b, i) => (
          <rect key={i} x={b.x} y={base - b.h} width={b.w} height={b.h} />
        ))}
      </g>
      <g className="lights">
        <Lights list={NEAR} base={base} />
      </g>
      <rect y="210" width="1200" height="120" fill="url(#haze)" />
    </svg>
  )
}
