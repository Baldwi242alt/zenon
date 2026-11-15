import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { LineChart, Panel, Placeholder, SitePicker, Status, Tile } from '../components/ui'
import { fmtTime, useJson, useRover } from '../data'
import { useStore } from '../store'
import type { Grid, Route, RouteFile, Site } from '../types'

const TerrainScene = lazy(() => import('../story/TerrainScene').then(m => ({ default: m.TerrainScene })))
// The real LROC NAC photo of each grid area (data/make_ground.py), drawn under the 2D shadow map.
const GROUND_URLS = Object.fromEntries(Object.entries(import.meta.glob('../assets/ground/*.jpg', { eager: true, query: '?url', import: 'default' }) as Record<string, string>)
  .map(([k, v]) => [k.split('/').pop()!.split('.')[0], v]))

const COLORS: Record<string, string> = { shortest: '#f0605d', sunchaser_fast: '#f2a541', sunchaser_safe: '#4cc38a' }

export default function RoverOps() {
  const sites = useJson<Site[]>('sites.json')
  const { site, setSite } = useStore()
  return (
    <Status res={sites} what="sites">{s => (
      <>
        <div className="page-head">
          <div>
            <h2>Rover ops</h2>
            <p>The same 4-5 km drive, two ways. The shortest route ignores the Sun. Sunchaser plans through space and time:
              it detours through sunlight, or parks while a shadow passes, and never lets its battery fall below the reserve.</p>
          </div>
          <div className="controls"><SitePicker sites={s} value={site} onChange={setSite} /></div>
        </div>
        <Loaded key={site} site={s.find(x => x.id === site)!} />
      </>
    )}</Status>
  )
}

function Loaded({ site }: { site: Site }) {
  const grid = useJson<Grid>(`grid_${site.id}.json`)
  const route = useJson<RouteFile>(`route_${site.id}.json`)
  return (
    <Status res={route} what="routes">{r => (
      <Status res={grid} what="shadow grid (about 4 MB)">{g => <Ops grid={g} rf={r} site={site} />}</Status>
    )}</Status>
  )
}

// Position along a route at time t: last step with t_h <= t, interpolated towards the next step.
function posAt(route: Route, t: number): { r: number; c: number; i: number; batt: number; frozen: boolean } {
  const st = route.steps
  let i = 0
  while (i + 1 < st.length && st[i + 1].t_h <= t) i++
  const a = st[i], b = st[i + 1]
  const frozen = route.frozen_at_index !== null && i >= route.frozen_at_index
  if (!b || frozen) return { r: a.row, c: a.col, i, batt: a.battery_wh, frozen }
  const f = (t - a.t_h) / (b.t_h - a.t_h || 1)
  return { r: a.row + (b.row - a.row) * f, c: a.col + (b.col - a.col) * f, i, batt: a.battery_wh + (b.battery_wh - a.battery_wh) * f, frozen }
}

function Ops({ grid, rf, site }: { grid: Grid; rf: RouteFile; site: Site }) {
  const { rover, placeholder } = useRover()
  const cap = rover.battery.capacity_wh, reserve = rover.battery.min_soc * cap
  const end = Math.max(...rf.routes.map(r => r.duration_h)) + 2
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(4)                  // simulated hours per real second
  const canvas = useRef<HTMLCanvasElement>(null)
  const N = grid.rows, PX = 8                              // canvas pixels per cell

  // Steep cells, drawn hatched: computed once.
  const steep = useMemo(() => grid.slope_deg.map(row => row.map(s => s > rover.drive.max_slope_deg)), [grid, rover])
  // Shaded relief, so terrain reads even in shadow.
  const relief = useMemo(() => {
    const e = grid.elevation_m, out: number[][] = []
    for (let r = 0; r < N; r++) {
      out.push([])
      for (let c = 0; c < N; c++) {
        const dx = (e[r][Math.min(N - 1, c + 1)] - e[r][Math.max(0, c - 1)]) / (2 * grid.cell_size_m)
        const dy = (e[Math.min(N - 1, r + 1)][c] - e[Math.max(0, r - 1)][c]) / (2 * grid.cell_size_m)
        out[r].push(Math.max(-0.35, Math.min(0.35, (-dx + dy) * 2)))
      }
    }
    return out
  }, [grid, N])

  useEffect(() => {
    if (!playing) return
    let last = performance.now(), id = 0
    const tick = (now: number) => {
      setT(v => { const nv = v + ((now - last) / 1000) * speed; if (nv >= end) { setPlaying(false); return end } return nv })
      last = now
      id = requestAnimationFrame(tick)
    }
    id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [playing, speed, end])

  const step = Math.min(grid.n_steps - 1, Math.floor(rf.depart_step + t))
  const [view, setView] = useState<'3d' | 'map'>('3d')
  const [hover, setHover] = useState<{ r: number; c: number } | null>(null)
  const [ground, setGround] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    setGround(null)
    const url = GROUND_URLS[grid.site]
    if (!url) return
    const im = new Image(); im.onload = () => setGround(im); im.src = url
  }, [grid.site])

  // 2D map: the sunlight field is painted at cell resolution, then scaled up with smoothing so
  // shadows have soft, interpolated edges instead of 80 m blocks. Routes glow; the part already
  // driven is bright and the rest is faint.
  useEffect(() => {
    if (view !== 'map') return
    const cv = canvas.current
    if (!cv) return
    const S = 1024, k = S / N
    cv.width = S; cv.height = S
    const g = cv.getContext('2d')!
    const field = document.createElement('canvas'); field.width = N; field.height = N
    const fg = field.getContext('2d')!, img = fg.createImageData(N, N)
    const sun = grid.sun_pct[step]
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const lit = sun[r][c] / 100, sh = relief[r][c], o = (r * N + c) * 4
      if (ground) {   // a light filter laid over the photo: clear where sunlit, deep blue in shadow
        img.data[o] = 34 + lit * 221; img.data[o + 1] = 46 + lit * 204; img.data[o + 2] = 78 + lit * 162
      } else {
        img.data[o] = lit * (205 + sh * 90) + (1 - lit) * (12 + sh * 30)
        img.data[o + 1] = lit * (192 + sh * 85) + (1 - lit) * (18 + sh * 34)
        img.data[o + 2] = lit * (165 + sh * 70) + (1 - lit) * (32 + sh * 40)
      }
      img.data[o + 3] = 255
    }
    fg.putImageData(img, 0, 0)
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'
    if (ground) {
      g.fillStyle = '#000'; g.fillRect(0, 0, S, S)
      g.drawImage(ground, k / 2, k / 2, S - k, S - k)     // the photo spans cell centre to cell centre
      g.globalCompositeOperation = 'multiply'
      g.drawImage(field, 0, 0, S, S)
      g.globalCompositeOperation = 'source-over'
    } else g.drawImage(field, 0, 0, S, S)
    // steep ground: fine red hatching
    g.strokeStyle = 'rgba(240,96,93,0.28)'; g.lineWidth = 1
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) if (steep[r][c]) {
      g.beginPath(); g.moveTo(c * k, r * k + k); g.lineTo(c * k + k, r * k); g.moveTo(c * k + k / 2, r * k + k); g.lineTo(c * k + k, r * k + k / 2); g.stroke()
    }
    // faint 1 km grid
    g.strokeStyle = 'rgba(255,255,255,0.06)'
    const km = 1000 / grid.cell_size_m
    for (let x = km; x < N; x += km) { g.beginPath(); g.moveTo(x * k, 0); g.lineTo(x * k, S); g.moveTo(0, x * k); g.lineTo(S, x * k); g.stroke() }
    const cx = (v: number) => v * k + k / 2
    for (const route of rf.routes) {
      const col = COLORS[route.name]
      g.setLineDash(route.name === 'sunchaser_safe' ? [10, 8] : [])
      g.lineCap = 'round'; g.lineJoin = 'round'
      g.globalAlpha = 0.3; g.strokeStyle = col; g.lineWidth = 3
      g.beginPath(); route.steps.forEach((st, i) => (i ? g.lineTo(cx(st.col), cx(st.row)) : g.moveTo(cx(st.col), cx(st.row)))); g.stroke()
      const p = posAt(route, t)
      g.globalAlpha = 1; g.lineWidth = 5; g.shadowColor = col; g.shadowBlur = 14
      g.beginPath()
      route.steps.slice(0, p.i + 1).forEach((st, i) => (i ? g.lineTo(cx(st.col), cx(st.row)) : g.moveTo(cx(st.col), cx(st.row))))
      g.lineTo(cx(p.c), cx(p.r)); g.stroke()
      g.shadowBlur = 0; g.setLineDash([])
    }
    for (const [pt, label] of [[rf.start, 'START'], [rf.target, 'TARGET']] as const) {
      g.strokeStyle = '#fff'; g.lineWidth = 2; g.beginPath(); g.arc(cx(pt.col), cx(pt.row), 11, 0, 7); g.stroke()
      g.fillStyle = '#fff'; g.beginPath(); g.arc(cx(pt.col), cx(pt.row), 3.5, 0, 7); g.fill()
      g.font = '13px "Traveling Typewriter", monospace'; g.fillText(label, cx(pt.col) + 16, cx(pt.row) - 12)
    }
    for (const route of rf.routes) {
      const p = posAt(route, t), col = p.frozen ? '#8fd0ff' : COLORS[route.name]
      const x = cx(p.c), y = cx(p.r)
      const halo = g.createRadialGradient(x, y, 0, x, y, 34); halo.addColorStop(0, col + 'aa'); halo.addColorStop(1, col + '00')
      g.fillStyle = halo; g.beginPath(); g.arc(x, y, 34, 0, 7); g.fill()
      g.fillStyle = col; g.strokeStyle = '#000'; g.lineWidth = 2.5; g.beginPath(); g.arc(x, y, 9, 0, 7); g.fill(); g.stroke()
      if (p.frozen) { g.font = '600 22px "STIX Two Text", serif'; g.fillStyle = '#8fd0ff'; g.fillText('FROZEN', x + 18, y + 7) }
    }
  }, [view, grid, rf, step, t, steep, relief, N, ground])

  const hoverCell = hover && {
    elev: grid.elevation_m[hover.r][hover.c], slope: grid.slope_deg[hover.r][hover.c], sun: grid.sun_pct[step][hover.r][hover.c],
  }
  const now = new Date(Date.parse(grid.window_start.replace('Z', ':00Z')) + (rf.depart_step + t) * 3600e3)
  const shortest = rf.routes.find(r => r.name === 'shortest')!
  const fast = rf.routes.find(r => r.name === 'sunchaser_fast')
  const caption = `${shortest.survived ? `Shortest path arrives in ${shortest.duration_h.toFixed(1)} h` : `Shortest path froze after ${shortest.duration_h.toFixed(1)} h`}` +
    (fast ? ` · Sunchaser arrives in ${fast.duration_h.toFixed(1)} h with ${fast.min_battery_pct.toFixed(0)}% battery left at its lowest` : '')

  return (
    <>
      <Placeholder show={placeholder} what="rover specifications (2,000 Wh battery, 245 W panel, 200 m/h)" />
      <div className="tiles">
        {rf.routes.map(r => (
          <Tile key={r.name} label={`${r.label}: chance of survival (${rf.monte_carlo_runs} simulated missions)`}
                value={`${(100 * r.survival_probability).toFixed(0)}%`} tone={r.survival_probability >= 0.9 ? 'both' : 'danger'} />
        ))}
      </div>
      <div className="ops">
        <div>
          <div className="view-toggle seg" role="group" aria-label="View">
            <button className={view === '3d' ? 'on' : ''} onClick={() => setView('3d')}>3D terrain</button>
            <button className={view === 'map' ? 'on' : ''} onClick={() => setView('map')}>Shadow map</button>
          </div>
          <div className="ops-stage">
            {view === '3d'
              ? <Suspense fallback={<div className="status"><span className="spinner" /> Building 3D terrain…</div>}><TerrainScene grid={grid} rf={rf} t={t} /></Suspense>
              : <canvas ref={canvas} aria-label={`Shadow map of a 5 km area at ${site.name} with the planned routes`}
                  onMouseMove={e => { const b = e.currentTarget.getBoundingClientRect(); setHover({ r: Math.min(N - 1, Math.floor(((e.clientY - b.top) / b.height) * N)), c: Math.min(N - 1, Math.floor(((e.clientX - b.left) / b.width) * N)) }) }}
                  onMouseLeave={() => setHover(null)} />}
            {view === 'map' && hoverCell && (
              <div className="ops-probe"><span>Cell {hover!.r}, {hover!.c}</span><b>{hoverCell.sun}% sun</b><em>{hoverCell.elev.toFixed(0)} m · slope {hoverCell.slope.toFixed(1)}°{hoverCell.slope > rover.drive.max_slope_deg ? ' · too steep' : ''}</em></div>
            )}
            <div className="ops-clock"><span>Mission time</span><b>T+{t.toFixed(1)} h</b></div>
          </div>
          <div className="player">
            <button className="btn primary" onClick={() => { if (t >= end) setT(0); setPlaying(p => !p) }}>{playing ? 'Pause' : t >= end ? 'Replay' : 'Play'}</button>
            <div className="seg" role="group" aria-label="Playback speed">
              {[1, 4, 12].map(s => <button key={s} className={speed === s ? 'on' : ''} onClick={() => setSpeed(s)}>{s} h/s</button>)}
            </div>
            <input type="range" min={0} max={end} step={0.05} value={t} onChange={e => { setPlaying(false); setT(+e.target.value) }} aria-label="Mission time" />
            <span className="mono">T+{t.toFixed(1)} h</span>
          </div>
          <p className="note mono">{fmtTime(now.toISOString().slice(0, 16) + 'Z')} · {grid.rows * grid.cell_size_m / 1000} km × {grid.cols * grid.cell_size_m / 1000} km, {grid.cell_size_m} m cells · {view === '3d' ? 'real LOLA terrain, heights ×3, drag to orbit' : 'LROC NAC photo (NASA) with computed shadows: blue = shadow, red hatching = too steep, hover for details'}</p>
        </div>
        <div>
          {rf.routes.map(r => {
            const p = posAt(r, t)
            const arrived = r.survived && t >= r.duration_h
            return (
              <div className="route-card" key={r.name}>
                <h4><span style={{ color: COLORS[r.name] }}>● {r.label}</span>
                  {p.frozen ? <span className="frozen">FROZEN</span> : arrived ? <span className="pill ok">ARRIVED</span> : <span className="pill sun">driving</span>}</h4>
                <div className="battery"><div style={{ width: `${(100 * p.batt) / cap}%`, background: p.frozen || p.batt < reserve ? 'var(--danger)' : COLORS[r.name] }} /></div>
                <p className="note mono">battery {p.batt.toFixed(0)} Wh ({((100 * p.batt) / cap).toFixed(0)}%) · {(r.distance_m / 1000).toFixed(2)} km · {r.duration_h.toFixed(1)} h · lowest {r.min_battery_pct.toFixed(0)}%</p>
              </div>
            )
          })}
          <Panel title="Battery over the drive" sub={`Dashed line: the ${(100 * rover.battery.min_soc).toFixed(0)}% safety reserve`}>
            <LineChart height={200} xFmt={x => `${x.toFixed(0)} h`} yFmt={y => `${y.toFixed(0)}`} yMin={0} yMax={cap} vLine={t}
              hLines={[{ y: reserve, label: 'reserve', color: 'var(--muted)' }]}
              series={rf.routes.map(r => ({ name: r.label, color: COLORS[r.name], points: r.steps.map(s => [s.t_h, s.battery_wh] as [number, number]) }))} />
          </Panel>
        </div>
      </div>
      <Panel title={caption} sub="Survival = share of 500 simulated missions (battery, panel and power draw each varied by ±10%, departure delayed 0-2 h) in which the rover never froze, on the way or in 24 hours parked at the target.">
        {rf.pareto && new Set(rf.pareto.map(p => `${p.duration_h}|${p.survival_probability}`)).size > 1 ? (
          <>
            <h3>Fast versus safe: what extra time buys</h3>
            <table><thead><tr><th>Battery reserve kept</th><th className="num">Trip time</th><th className="num">Survival</th></tr></thead>
              <tbody>{rf.pareto.map(p => <tr key={p.reserve_pct}><td>{p.reserve_pct}%</td><td className="num">{p.duration_h.toFixed(1)} h</td><td className="num">{(100 * p.survival_probability).toFixed(1)}%</td></tr>)}</tbody></table>
          </>
        ) : <p className="note">At this site the fastest safe route already has the most margin the planner can find.</p>}
      </Panel>
    </>
  )
}
