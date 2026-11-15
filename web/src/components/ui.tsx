import { useMemo, useRef, useState, type ReactNode } from 'react'
import type { Loaded } from '../data'
import type { Site } from '../types'

export function Tile({ label, value, unit, tone, hint }: { label: string; value: string; unit?: string; tone?: string; hint?: string }) {
  return (
    <div className={`tile ${tone ?? ''}`} title={hint}>
      <div className={`tile-value ${value.length > 9 ? 'text' : ''}`}>{value}{unit && <span className="tile-unit">{unit}</span>}</div>
      <div className="tile-label">{label}</div>
    </div>
  )
}

export function Panel({ title, sub, children, right }: { title: ReactNode; sub?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div><h3>{title}</h3>{sub && <p className="panel-sub">{sub}</p>}</div>
        {right}
      </header>
      {children}
    </section>
  )
}

export function Status<T>({ res, what, children }: { res: Loaded<T>; what: string; children: (d: T) => ReactNode }) {
  if (res.state === 'loading') return <div className="status"><span className="spinner" /> Loading {what}…</div>
  if (res.state === 'missing') return <div className="status warn">{what} isn't available yet. ({res.error})</div>
  return <>{children(res.data)}</>
}

export function Placeholder({ show, what }: { show: boolean; what: string }) {
  if (!show) return null
  return <p className="note">Uses placeholder {what} from the project brief until the engineering lead's sourced values are committed.</p>
}

export function SitePicker({ sites, value, onChange, only }: { sites: Site[]; value: string; onChange: (s: string) => void; only?: string[] }) {
  return (
    <select className="select" value={value} onChange={e => onChange(e.target.value)} aria-label="Site">
      {sites.filter(s => !only || only.includes(s.id)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
    </select>
  )
}

// ---------- a small SVG line chart (time series, several lines, optional shading and markers) ----------
export interface Series { name: string; color: string; points: [number, number][]; dashed?: boolean; width?: number }
export interface Band { x0: number; x1: number; color: string }

export function LineChart({ series, height = 220, xLabel, yLabel, xFmt = (x: number) => x.toFixed(0), yFmt = (y: number) => y.toFixed(1),
  bands = [], hLines = [], vLine, yMin, yMax, legend = true }: {
  series: Series[]; height?: number; xLabel?: string; yLabel?: string; xFmt?: (x: number) => string; yFmt?: (y: number) => string
  bands?: Band[]; hLines?: { y: number; label: string; color: string }[]; vLine?: number; yMin?: number; yMax?: number; legend?: boolean
}) {
  const W = 800, H = height, L = 52, R = 12, T = 12, B = 34
  const ref = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const all = series.flatMap(s => s.points)
  const xs = all.map(p => p[0]), ys = all.map(p => p[1]).concat(hLines.map(h => h.y))
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  let y0 = yMin ?? Math.min(...ys), y1 = yMax ?? Math.max(...ys)
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1 }
  const pad = (y1 - y0) * 0.06
  if (yMin === undefined) y0 -= pad
  if (yMax === undefined) y1 += pad
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R)
  const sy = (y: number) => T + (1 - (y - y0) / (y1 - y0)) * (H - T - B)
  const ticks = (a: number, b: number, n: number) => Array.from({ length: n + 1 }, (_, i) => a + ((b - a) * i) / n)
  const paths = useMemo(() => series.map(s => {
    // Decimate long series to ~1,600 points for speed; keep min/max of each bucket so spikes survive.
    const pts = s.points, step = Math.max(1, Math.floor(pts.length / 800))
    const kept: [number, number][] = []
    for (let i = 0; i < pts.length; i += step) {
      const chunk = pts.slice(i, i + step)
      let lo = chunk[0], hi = chunk[0]
      for (const p of chunk) { if (p[1] < lo[1]) lo = p; if (p[1] > hi[1]) hi = p }
      kept.push(...(lo[0] <= hi[0] ? [lo, hi] : [hi, lo]))
    }
    return kept.map((p, i) => `${i ? 'L' : 'M'}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join('')
  }), [series, x0, x1, y0, y1])  // eslint-disable-line react-hooks/exhaustive-deps

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const x = x0 + (((e.clientX - r.left) / r.width) * W - L) / (W - L - R) * (x1 - x0)
    setHover(Math.max(x0, Math.min(x1, x)))
  }
  const near = (s: Series, x: number) => {
    let best = s.points[0]
    for (const p of s.points) if (Math.abs(p[0] - x) < Math.abs(best[0] - x)) best = p
    return best
  }
  return (
    <div className="chart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {bands.map((b, i) => <rect key={i} x={sx(b.x0)} y={T} width={Math.max(0.5, sx(b.x1) - sx(b.x0))} height={H - T - B} fill={b.color} />)}
        {ticks(y0, y1, 4).map((t, i) => (
          <g key={i}><line x1={L} x2={W - R} y1={sy(t)} y2={sy(t)} className="grid" /><text x={L - 6} y={sy(t) + 4} className="axis" textAnchor="end">{yFmt(t)}</text></g>
        ))}
        {ticks(x0, x1, 6).map((t, i) => <text key={i} x={sx(t)} y={H - 12} className="axis" textAnchor="middle">{xFmt(t)}</text>)}
        {hLines.map((h, i) => (
          <g key={i}><line x1={L} x2={W - R} y1={sy(h.y)} y2={sy(h.y)} stroke={h.color} strokeDasharray="6 4" strokeWidth={1.4} />
            <text x={W - R - 4} y={sy(h.y) - 5} className="axis" textAnchor="end" fill={h.color}>{h.label}</text></g>
        ))}
        {series.map((s, i) => <path key={s.name} d={paths[i]} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.8}
          strokeDasharray={s.dashed ? '5 4' : undefined} vectorEffect="non-scaling-stroke" />)}
        {vLine !== undefined && <line x1={sx(vLine)} x2={sx(vLine)} y1={T} y2={H - B} stroke="var(--text)" strokeWidth={1} opacity={0.7} />}
        {hover !== null && <line x1={sx(hover)} x2={sx(hover)} y1={T} y2={H - B} stroke="var(--muted)" strokeDasharray="3 3" />}
        {xLabel && <text x={W - R} y={H - 1} className="axis" textAnchor="end">{xLabel}</text>}
        {yLabel && <text x={4} y={T + 2} className="axis" dominantBaseline="hanging">{yLabel}</text>}
      </svg>
      {hover !== null && (
        <div className="chart-tip">
          <b>{xFmt(hover)}</b>
          {series.map(s => <span key={s.name}><i style={{ background: s.color }} />{s.name}: {yFmt(near(s, hover)[1])}</span>)}
        </div>
      )}
      {legend && <div className="legend">{series.map(s => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}</div>}
    </div>
  )
}
