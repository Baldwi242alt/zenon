import { useEffect, useMemo, useRef, useState } from 'react'
import type { TimelineRow } from '../types'

// The signature view: a 360-degree panorama of the real terrain horizon around a site, rebuilt
// from the timeline itself (each hour records the horizon height in the Sun's direction, and the
// Sun circles the whole sky once a lunar day), with the Sun's real path for the period over it.
// Where the path drops behind the ridge, the site is in shadow. Hover or drag to scrub the month.
const W = 1200, H = 340, PAD_B = 34

// Deterministic star field (same stars every render).
const STARS = Array.from({ length: 140 }, (_, i) => {
  const a = Math.sin(i * 12.9898) * 43758.5453, b = Math.sin(i * 78.233) * 12345.678
  return { x: (a - Math.floor(a)) * W, y: (b - Math.floor(b)), r: ((i * 7) % 10) / 10 }
})

export function Horizon({ rows, title }: { rows: TimelineRow[]; title: string }) {
  const top = Math.max(2, ...rows.map(r => Math.max(r.sun_elev_deg, r.sun_horizon_deg))) + 1
  const bottom = Math.min(-1, ...rows.map(r => Math.min(r.sun_elev_deg, r.sun_horizon_deg))) - 0.6
  const plotH = H - PAD_B
  const sy = (deg: number) => ((top - deg) / (top - bottom)) * plotH
  const sx = (az: number) => (az / 360) * W

  // Ridge height per 1-degree azimuth bin.
  const ridgeH = useMemo(() => {
    const bins: number[][] = Array.from({ length: 360 }, () => [])
    rows.forEach(r => bins[Math.floor(r.sun_az_deg) % 360].push(r.sun_horizon_deg))
    let last = 0
    return bins.map(b => (b.length ? (last = b.reduce((a, c) => a + c, 0) / b.length) : last))
  }, [rows])
  const ridgeLine = ridgeH.map((v, i) => `${i ? 'L' : 'M'}${sx(i + 0.5).toFixed(1)},${sy(v).toFixed(1)}`).join('')
  const ridgeFill = `M0,${plotH} L0,${sy(ridgeH[0]).toFixed(1)} ${ridgeLine.replace('M', 'L')} L${W},${sy(ridgeH[359]).toFixed(1)} L${W},${plotH} Z`

  // The Sun's track, split into lit and hidden pieces; break where azimuth wraps 360 -> 0.
  const tracks = useMemo(() => {
    const lit: string[] = [], dark: string[] = []
    let prev: TimelineRow | null = null
    for (const r of rows) {
      if (prev && Math.abs(r.sun_az_deg - prev.sun_az_deg) < 30) {
        const seg = `M${sx(prev.sun_az_deg).toFixed(1)},${sy(prev.sun_elev_deg).toFixed(1)}L${sx(r.sun_az_deg).toFixed(1)},${sy(r.sun_elev_deg).toFixed(1)}`
        ;(r.sun_frac >= 0.5 ? lit : dark).push(seg)
      }
      prev = r
    }
    return { lit: lit.join(''), dark: dark.join('') }
  }, [rows, top, bottom])  // eslint-disable-line react-hooks/exhaustive-deps

  // The Sun plays along its path (one lunar month in ~24 s) until the viewer takes over.
  const [k, setK] = useState(0)
  const held = useRef(false)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setK(Math.floor(rows.length / 3)); return }
    const id = setInterval(() => { if (!held.current) setK(i => (i + 1) % rows.length) }, 33)
    return () => clearInterval(id)
  }, [rows.length])
  const svgRef = useRef<SVGSVGElement>(null)
  const scrub = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
    held.current = true
    setK(Math.round(f * (rows.length - 1)))
  }

  const s = rows[Math.min(k, rows.length - 1)]
  const litShare = rows.filter(r => r.sun_frac >= 0.5).length / rows.length
  const sunLit = s && s.sun_frac >= 0.5
  const ticks = Array.from({ length: 13 }, (_, i) => i * 30)
  const label = (az: number) => ({ 0: 'N', 90: 'E', 180: 'S', 270: 'W', 360: 'N' } as Record<number, string>)[az] ?? `${az}°`
  const elevTicks = Array.from(new Set([Math.floor(top - 0.5), Math.round((top + 0) / 2), 0])).filter(d => d < top && d > bottom)

  return (
    <div className="horizon2" aria-label={`Terrain horizon and the Sun's path at ${title}`}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" onPointerMove={scrub} onPointerDown={scrub} onPointerLeave={() => (held.current = false)}>
        <defs>
          <linearGradient id="hz-sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#020203" /><stop offset="0.75" stopColor="#07080c" /><stop offset="1" stopColor="#15110a" />
          </linearGradient>
          <linearGradient id="hz-ground" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#4a463d" /><stop offset="0.08" stopColor="#2a2823" /><stop offset="0.5" stopColor="#141310" /><stop offset="1" stopColor="#070706" />
          </linearGradient>
          <radialGradient id="hz-sun"><stop offset="0" stopColor="#fff8e6" /><stop offset="0.35" stopColor="#ffd28a" /><stop offset="1" stopColor="#f2a541" stopOpacity="0" /></radialGradient>
        </defs>
        <rect width={W} height={plotH} fill="url(#hz-sky)" />
        {STARS.map((st, i) => (
          <circle key={i} cx={st.x} cy={st.y * plotH * 0.85} r={0.5 + st.r * 0.9} fill="#fff" opacity={0.15 + st.r * 0.45} />
        ))}
        {/* glow on the horizon where the Sun is */}
        {s && <ellipse cx={sx(s.sun_az_deg)} cy={sy(Math.max(0, s.sun_horizon_deg))} rx={170} ry={46} fill="url(#hz-sun)" opacity={sunLit ? 0.32 : 0.1} />}
        {elevTicks.map(d => (
          <g key={d}>
            <line x1={0} x2={W} y1={sy(d)} y2={sy(d)} stroke={d === 0 ? 'rgba(235,228,210,0.28)' : 'rgba(235,228,210,0.08)'} strokeDasharray={d === 0 ? '' : '1 7'} />
            <text x={W - 8} y={sy(d) - 6} className="hz-axis" textAnchor="end">{d > 0 ? '+' : ''}{d}°{d === 0 ? ' flat horizon' : ''}</text>
          </g>
        ))}
        <path d={tracks.dark} className="hz-track-dark" />
        <path d={ridgeFill} fill="url(#hz-ground)" />
        <path d={ridgeLine} className="hz-rim" />
        <path d={tracks.lit} className="hz-track-halo" /><path d={tracks.lit} className="hz-track-lit" />
        {s && (sunLit
          ? <g><circle cx={sx(s.sun_az_deg)} cy={sy(s.sun_elev_deg)} r={22} fill="url(#hz-sun)" /><circle cx={sx(s.sun_az_deg)} cy={sy(s.sun_elev_deg)} r={6.5} fill="#fff4dc" /></g>
          : <circle cx={sx(s.sun_az_deg)} cy={sy(s.sun_elev_deg)} r={6} fill="none" stroke="#f2a541" strokeDasharray="2 3" opacity={0.7} />)}
        {s && <line x1={sx(s.sun_az_deg)} x2={sx(s.sun_az_deg)} y1={plotH} y2={plotH + 8} stroke="#f2a541" />}
        <line x1={0} x2={W} y1={plotH} y2={plotH} stroke="rgba(235,228,210,0.2)" />
        {ticks.map(az => (
          <g key={az}>
            <line x1={sx(az)} x2={sx(az)} y1={plotH} y2={plotH + 5} stroke="rgba(235,228,210,0.3)" />
            <text x={Math.min(W - 10, Math.max(10, sx(az)))} y={plotH + 22} className={`hz-axis ${az % 90 ? '' : 'cardinal'}`} textAnchor="middle">{label(az)}</text>
          </g>
        ))}
      </svg>
      <div className="hz-read">
        <div><span>Time (UTC)</span><b>{s ? `${s.time.slice(5, 10)} · ${s.time.slice(11, 16)}` : '—'}</b></div>
        <div><span>Sun elevation</span><b>{s ? `${s.sun_elev_deg.toFixed(2)}°` : '—'}</b></div>
        <div><span>Ridge in that direction</span><b>{s ? `${s.sun_horizon_deg.toFixed(2)}°` : '—'}</b></div>
        <div className={sunLit ? 'lit' : 'dark'}><span>At the site</span><b>{s ? (sunLit ? 'Sunlit' : 'In shadow') : '—'}</b></div>
        <div><span>Lit this month</span><b>{(100 * litShare).toFixed(0)}%</b></div>
      </div>
      <p className="hz-cap">{title} · ridge: real terrain horizon from LRO LOLA · line: the Sun's path from JPL Horizons · hover or drag to scrub</p>
    </div>
  )
}
