import { useEffect, useMemo, useState } from 'react'
import type { TimelineRow } from '../types'

// The signature: a 360-degree panorama of the terrain horizon around a site, rebuilt from the
// timeline itself (each hour records the horizon height in the Sun's direction, and the Sun
// circles the whole sky once a lunar day), with the Sun's real path for the period drawn over it.
// Where the path drops behind the ridge, the site is in shadow.
export function Horizon({ rows, title }: { rows: TimelineRow[]; title: string }) {
  const W = 1000, H = 230
  // Vertical range from the data: the ridge and the Sun's track, with a little headroom.
  const top = Math.max(2, ...rows.map(r => Math.max(r.sun_elev_deg, r.sun_horizon_deg))) + 0.6
  const bottom = Math.min(-1, ...rows.map(r => Math.min(r.sun_elev_deg, r.sun_horizon_deg))) - 0.4
  const gridLines = Array.from(new Set([Math.floor(top), Math.round(top / 2), 0, Math.ceil(bottom)])).filter(d => d < top && d > bottom)
  const sy = (deg: number) => ((top - deg) / (top - bottom)) * H
  const sx = (az: number) => (az / 360) * W

  const ridge = useMemo(() => {
    // 1-degree bins of azimuth: horizon height seen toward the Sun at that azimuth.
    const bins: number[][] = Array.from({ length: 360 }, () => [])
    rows.forEach(r => bins[Math.floor(r.sun_az_deg) % 360].push(r.sun_horizon_deg))
    let last = 0
    const h = bins.map(b => (b.length ? (last = b.reduce((a, c) => a + c, 0) / b.length) : last))
    return `M0,${H} ` + h.map((v, i) => `L${sx(i + 0.5).toFixed(1)},${sy(v).toFixed(1)}`).join(' ') + ` L${W},${H} Z`
  }, [rows, top, bottom])  // eslint-disable-line react-hooks/exhaustive-deps

  // The Sun's track, split into lit and shadowed pieces; break where azimuth wraps 360 -> 0.
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
  }, [rows])  // eslint-disable-line react-hooks/exhaustive-deps

  // The Sun moves along its path (one lunar month in ~24 s), unless reduced motion is preferred.
  const [k, setK] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setK(Math.floor(rows.length / 3)); return }
    const id = setInterval(() => setK(i => (i + 1) % rows.length), 33)
    return () => clearInterval(id)
  }, [rows.length])
  const s = rows[k]
  const litShare = rows.filter(r => r.sun_frac >= 0.5).length / rows.length

  return (
    <div className="horizon" aria-label={`Terrain horizon and the Sun's path at ${title}`}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img">
        {gridLines.map(d => (
          <g key={d}><line x1={0} x2={W} y1={sy(d)} y2={sy(d)} stroke={d === 0 ? '#3a475f' : '#1a2334'} strokeDasharray={d === 0 ? '' : '2 6'} />
            <text x={4} y={sy(d) - 4} className="axis">{d > 0 ? '+' : ''}{d}°</text></g>
        ))}
        <path className="ridge" d={ridge} />
        <path className="track-dark" d={tracks.dark} />
        <path className="track-lit" d={tracks.lit} />
        {['N', 'E', 'S', 'W'].map((c, i) => <text key={c} x={sx(i * 90) + (i ? 0 : 10)} y={H - 6} className="axis" textAnchor="middle" fill="#cfd6e3">{c}</text>)}
        {s && <circle className="sun" cx={sx(s.sun_az_deg)} cy={sy(s.sun_elev_deg)} r={s.sun_frac >= 0.5 ? 7 : 5} opacity={s.sun_frac >= 0.5 ? 1 : 0.45} />}
      </svg>
      <div className="cap">
        <span>{title}: the ridge is the real terrain horizon (LRO LOLA); the line is the Sun's path (JPL Horizons)</span>
        <span>{s ? `${s.time.slice(0, 10)} ${s.time.slice(11, 16)} UTC · Sun ${s.sun_elev_deg.toFixed(2)}° · ${s.sun_frac >= 0.5 ? 'sunlit' : 'in shadow'}` : ''} · lit {(100 * litShare).toFixed(0)}% of this month</span>
      </div>
    </div>
  )
}
