import { useMemo, useRef, useState } from 'react'
import { LineChart, Panel, SitePicker, Status, Tile } from '../components/ui'
import { MONTH_NAMES, fmtTime, longestRun, useJson } from '../data'
import { useStore } from '../store'
import type { Site, Timeline, TimelineRow } from '../types'

// NASA's core requirement: when are the Sun and Earth above the local (terrain) horizon?
export default function LightComms() {
  const sites = useJson<Site[]>('sites.json')
  return <Status res={sites} what="sites">{s => <Screen sites={s} />}</Status>
}

function Screen({ sites }: { sites: Site[] }) {
  const { site, setSite, month, setMonth } = useStore()
  const [compare, setCompare] = useState<string[]>([])
  const shown = [site, ...compare.filter(c => c !== site)].slice(0, 3)
  return (
    <>
      <div className="page-head">
        <div>
          <h2>Light &amp; comms</h2>
          <p>Hour by hour: is at least half the Sun's disk above the real terrain horizon (power), and is Earth in view (direct-to-Earth radio)?</p>
        </div>
        <div className="controls">
          <SitePicker sites={sites} value={site} onChange={setSite} />
          <select className="select" value={month} onChange={e => setMonth(+e.target.value)} aria-label="Month">
            {MONTH_NAMES.map((m, i) => <option key={m} value={i}>{m} 2027</option>)}
          </select>
          <select className="select" value="" onChange={e => e.target.value && setCompare(c => [...c, e.target.value].slice(-2))} aria-label="Compare">
            <option value="">+ compare a site</option>
            {sites.filter(s => !shown.includes(s.id)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {compare.length > 0 && <button className="btn" onClick={() => setCompare([])}>clear compare</button>}
        </div>
      </div>
      {shown.map((id, i) => <SiteMonth key={id} site={sites.find(s => s.id === id)!} month={month} detail={i === 0} />)}
    </>
  )
}

function SiteMonth({ site, month, detail }: { site: Site; month: number; detail: boolean }) {
  const tl = useJson<Timeline>(`timeline_${site.id}.json`)
  return (
    <Status res={tl} what={`${site.name} timeline`}>{t => {
      const prefix = `2027-${String(month + 1).padStart(2, '0')}`
      const rows = t.rows.filter(r => r.time.startsWith(prefix))
      return <MonthView site={site} rows={rows} month={month} detail={detail} />
    }}</Status>
  )
}

function MonthView({ site, rows, month, detail }: { site: Site; rows: TimelineRow[]; month: number; detail: boolean }) {
  const lit = rows.map(r => r.sun_frac >= 0.5)
  const earth = rows.map(r => r.earth_visible)
  const both = rows.map((_, i) => lit[i] && earth[i])
  const n = rows.length
  const share = (f: boolean[]) => `${((100 * f.filter(Boolean).length) / n).toFixed(0)}%`
  const darkest = longestRun(lit.map(x => !x)), gap = longestRun(earth.map(x => !x))
  const temps = rows.map(r => r.surface_temp_k).filter((x): x is number => x !== null)
  return (
    <Panel title={`${site.name} · ${MONTH_NAMES[month]} 2027`} sub={`${n} hours · terrain horizons from LRO LOLA, Sun and Earth positions from JPL Horizons`}>
      <div className="tiles">
        <Tile label="hours sunlit" value={share(lit)} tone="sun" />
        <Tile label="hours with Earth in view" value={share(earth)} tone="earth" />
        <Tile label="hours with both" value={share(both)} tone="both" />
        <Tile label="longest dark spell" value={String(darkest)} unit="h" tone={darkest > 18 ? 'danger' : ''} />
        <Tile label="longest contact gap" value={String(gap)} unit="h" />
        {temps.length > 0 && <Tile label="surface temperature range" value={`${Math.min(...temps).toFixed(0)}–${Math.max(...temps).toFixed(0)}`} unit="K" />}
      </div>
      <Bands rows={rows} lit={lit} earth={earth} both={both} />
      {detail && <Elevations rows={rows} />}
    </Panel>
  )
}

function Bands({ rows, lit, earth, both }: { rows: TimelineRow[]; lit: boolean[]; earth: boolean[]; both: boolean[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const n = rows.length
  // Merge consecutive hours with the same state into one rectangle: fast even for long ranges.
  const runs = (val: (i: number) => string) => {
    const out: { a: number; b: number; v: string }[] = []
    for (let i = 0; i < n; i++) {
      const v = val(i)
      if (out.length && out[out.length - 1].v === v) out[out.length - 1].b = i + 1
      else out.push({ a: i, b: i + 1, v })
    }
    return out
  }
  const sunRuns = useMemo(() => runs(i => (lit[i] ? 'var(--sun)' : rows[i].sun_frac > 0 ? 'var(--sun-dim)' : '')), [rows])  // eslint-disable-line react-hooks/exhaustive-deps
  const earthRuns = useMemo(() => runs(i => (earth[i] ? 'var(--earth)' : '')), [rows])  // eslint-disable-line react-hooks/exhaustive-deps
  const bothRuns = useMemo(() => runs(i => (both[i] ? 'var(--both)' : '')), [rows])  // eslint-disable-line react-hooks/exhaustive-deps
  const band = (rs: typeof sunRuns) => (
    <svg className="band" viewBox={`0 0 ${n} 1`} preserveAspectRatio="none">
      {rs.filter(r => r.v).map(r => <rect key={r.a} x={r.a} width={r.b - r.a} y={0} height={1} fill={r.v} />)}
      {hover !== null && <rect x={hover} width={Math.max(1, n / 400)} y={0} height={1} fill="#fff" />}
    </svg>
  )
  const onMove = (e: React.MouseEvent) => {
    const el = ref.current!.querySelector('.band')!.getBoundingClientRect()
    const i = Math.floor(((e.clientX - el.left) / el.width) * n)
    setHover(i >= 0 && i < n ? i : null)
  }
  const h = hover !== null ? rows[hover] : null
  return (
    <div ref={ref} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <div className="bands">
        <span className="lab">Sun</span>{band(sunRuns)}
        <span className="lab">Earth</span>{band(earthRuns)}
        <span className="lab">Both</span>{band(bothRuns)}
        <div className="band-axis">{[0, 0.25, 0.5, 0.75, 1].map(f => <span key={f}>{rows[Math.min(n - 1, Math.floor(f * (n - 1)))].time.slice(5, 10)}</span>)}</div>
      </div>
      <p className="note">
        {h ? <span className="mono">{fmtTime(h.time)} · Sun {h.sun_elev_deg.toFixed(2)}° vs horizon {h.sun_horizon_deg.toFixed(2)}° ({(h.sun_frac * 100).toFixed(0)}% of disk) ·
            Earth {h.earth_elev_deg.toFixed(2)}° vs horizon {h.earth_horizon_deg.toFixed(2)}° ({h.earth_visible ? `in view${h.dsn_station ? ', via ' + h.dsn_station : ''}` : 'hidden'})
            {h.surface_temp_k !== null && ` · ${h.surface_temp_k.toFixed(0)} K`}</span>
          : <>Amber: at least half the Sun visible (faint amber: partly visible). Blue: Earth in view. Green: both. Hover for the hour's geometry.</>}
      </p>
    </div>
  )
}

function Elevations({ rows }: { rows: TimelineRow[] }) {
  const x = (i: number) => i / 24
  const day = (d: number) => `day ${(d + 1).toFixed(0)}`
  const sunBands = useMemo(() => spans(rows.map(r => r.sun_frac >= 0.5)).map(([a, b]) => ({ x0: x(a), x1: x(b), color: 'rgba(245,166,35,0.12)' })), [rows])
  const earthBands = useMemo(() => spans(rows.map(r => r.earth_visible)).map(([a, b]) => ({ x0: x(a), x1: x(b), color: 'rgba(78,163,255,0.12)' })), [rows])
  return (
    <div className="grid2" style={{ marginTop: 14 }}>
      <div>
        <h3>Why the site goes dark: Sun vs terrain</h3>
        <LineChart height={210} xFmt={day} yFmt={y => `${y.toFixed(1)}°`} bands={sunBands} series={[
          { name: 'Sun elevation', color: 'var(--sun)', points: rows.map((r, i) => [x(i), r.sun_elev_deg]) },
          { name: 'terrain horizon toward the Sun', color: 'var(--terrain)', dashed: true, points: rows.map((r, i) => [x(i), r.sun_horizon_deg]) },
        ]} />
      </div>
      <div>
        <h3>Earth vs terrain</h3>
        <LineChart height={210} xFmt={day} yFmt={y => `${y.toFixed(1)}°`} bands={earthBands} series={[
          { name: 'Earth elevation', color: 'var(--earth)', points: rows.map((r, i) => [x(i), r.earth_elev_deg]) },
          { name: 'terrain horizon toward Earth', color: 'var(--terrain)', dashed: true, points: rows.map((r, i) => [x(i), r.earth_horizon_deg]) },
        ]} />
      </div>
    </div>
  )
}

function spans(flags: boolean[]): [number, number][] {
  const out: [number, number][] = []
  flags.forEach((f, i) => {
    if (!f) return
    if (out.length && out[out.length - 1][1] === i) out[out.length - 1][1] = i + 1
    else out.push([i, i + 1])
  })
  return out
}
