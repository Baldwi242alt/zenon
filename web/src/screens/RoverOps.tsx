import { useEffect, useMemo, useRef, useState } from 'react'
import { LineChart, Panel, Placeholder, SitePicker, Status, Tile } from '../components/ui'
import { fmtTime, useJson, useRover } from '../data'
import { useStore } from '../store'
import type { Grid, Route, RouteFile, Site } from '../types'

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
  useEffect(() => {
    const cv = canvas.current!
    cv.width = N * PX; cv.height = N * PX
    const g = cv.getContext('2d')!
    const sun = grid.sun_pct[step]
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const lit = sun[r][c] / 100, sh = relief[r][c]
      const base = 18 + lit * 150 + sh * 60
      g.fillStyle = lit > 0 ? `rgb(${base + 22 * lit},${base + 12 * lit},${base - 6 * lit})` : `rgb(${10 + sh * 20},${14 + sh * 22},${24 + sh * 26})`
      g.fillRect(c * PX, r * PX, PX, PX)
      if (steep[r][c]) {
        g.strokeStyle = 'rgba(240,96,93,0.35)'; g.lineWidth = 1
        g.beginPath(); g.moveTo(c * PX, r * PX + PX); g.lineTo(c * PX + PX, r * PX); g.stroke()
      }
    }
    const cx = (c: number) => c * PX + PX / 2
    for (const route of rf.routes) {
      g.strokeStyle = COLORS[route.name]; g.lineWidth = route.name === 'shortest' ? 2 : 3
      g.setLineDash(route.name === 'sunchaser_safe' ? [5, 4] : []); g.globalAlpha = 0.9
      g.beginPath()
      route.steps.forEach((s, i) => (i ? g.lineTo(cx(s.col), cx(s.row)) : g.moveTo(cx(s.col), cx(s.row))))
      g.stroke(); g.setLineDash([]); g.globalAlpha = 1
    }
    // start and target
    for (const [p, label] of [[rf.start, 'START'], [rf.target, 'TARGET']] as const) {
      g.fillStyle = '#fff'; g.beginPath(); g.arc(cx(p.col), cx(p.row), 5, 0, 7); g.fill()
      g.font = '600 12px "IBM Plex Mono"'; g.fillStyle = '#fff'; g.fillText(label, cx(p.col) + 8, cx(p.row) - 8)
    }
    for (const route of rf.routes) {
      const p = posAt(route, t)
      g.fillStyle = COLORS[route.name]; g.strokeStyle = '#000'; g.lineWidth = 2
      g.beginPath(); g.arc(cx(p.c), cx(p.r), 7, 0, 7); g.fill(); g.stroke()
      if (p.frozen) {
        g.font = '700 14px "IBM Plex Sans Condensed"'; g.fillStyle = '#f0605d'
        g.fillText('FROZEN', cx(p.c) + 10, cx(p.r) + 5)
      }
    }
  }, [grid, rf, step, t, steep, relief, N])

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
          <canvas ref={canvas} aria-label={`Shadow map of a 5 km area at ${site.name} with the planned routes`} />
          <div className="player">
            <button className="btn primary" onClick={() => { if (t >= end) setT(0); setPlaying(p => !p) }}>{playing ? 'Pause' : t >= end ? 'Replay' : 'Play'}</button>
            <div className="seg" role="group" aria-label="Playback speed">
              {[1, 4, 12].map(s => <button key={s} className={speed === s ? 'on' : ''} onClick={() => setSpeed(s)}>{s} h/s</button>)}
            </div>
            <input type="range" min={0} max={end} step={0.05} value={t} onChange={e => { setPlaying(false); setT(+e.target.value) }} aria-label="Mission time" />
            <span className="mono">T+{t.toFixed(1)} h</span>
          </div>
          <p className="note mono">{fmtTime(now.toISOString().slice(0, 16) + 'Z')} · {grid.rows * grid.cell_size_m / 1000} km × {grid.cols * grid.cell_size_m / 1000} km, {grid.cell_size_m} m cells · bright = sunlit, dark = shadow, red hatching = too steep to drive</p>
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
