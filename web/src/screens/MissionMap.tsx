import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import basemap from '../assets/south_pole.jpg'
import { Horizon } from '../components/Horizon'
import { Panel, Status, Tile } from '../components/ui'
import { fmtTime, useJson } from '../data'
import { useStore } from '../store'
import type { Scores, Site, Timeline, Windows } from '../types'

// The basemap is LOLA's 80 m south-polar DEM (80 deg S to the pole), shaded. Its projection is
// polar stereographic on a 1737.4 km sphere, 0 deg longitude up; so a site's place on the image
// follows exactly from these formulas (same as data/sunchaser_data/dem.py). No calibration needed.
const R = 1737400, SCALE = 80, OFFSET = 3799.5, N = 7600
export function mapXY(lat: number, lon: number): [number, number] {
  const rad = Math.PI / 180
  const r = 2 * R * Math.tan(Math.PI / 4 + (lat * rad) / 2)
  const x = r * Math.sin(lon * rad), y = r * Math.cos(lon * rad)
  return [(OFFSET + x / SCALE) / N, (OFFSET - y / SCALE) / N]
}

export default function MissionMap() {
  const sites = useJson<Site[]>('sites.json')
  const scores = useJson<Scores>('scores.json')
  return (
    <Status res={sites} what="sites">{s => (
      <Status res={scores} what="scores">{sc => <Map sites={s} scores={sc} />}</Status>
    )}</Status>
  )
}


// Label placement: try positions around each marker (nearest first, then farther ones with a
// leader line) and keep the first whose box hits no other label, marker or map edge. Sites are
// placed in rank order, so the best sites get the best spots. Units are the 1000 x 1000 viewBox.
type Placed = { dx: number; dy: number; anchor: 'start' | 'end' | 'middle'; leader: boolean }
const CANDIDATES: Placed[] = [
  { dx: 17, dy: 5, anchor: 'start', leader: false }, { dx: -17, dy: 5, anchor: 'end', leader: false },
  { dx: 0, dy: -19, anchor: 'middle', leader: false }, { dx: 0, dy: 29, anchor: 'middle', leader: false },
  { dx: 14, dy: -14, anchor: 'start', leader: false }, { dx: 14, dy: 24, anchor: 'start', leader: false },
  { dx: -14, dy: -14, anchor: 'end', leader: false }, { dx: -14, dy: 24, anchor: 'end', leader: false },
  { dx: 38, dy: -32, anchor: 'start', leader: true }, { dx: -38, dy: -32, anchor: 'end', leader: true },
  { dx: 38, dy: 42, anchor: 'start', leader: true }, { dx: -38, dy: 42, anchor: 'end', leader: true },
]
type Box = [number, number, number, number]   // x0, y0, x1, y1
const hit = (a: Box, b: Box) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]
function labelBox(x: number, y: number, c: Placed, text: string): Box {
  const w = text.length * 8.6 + 6, lx = x + c.dx, ly = y + c.dy
  const x0 = c.anchor === 'start' ? lx : c.anchor === 'end' ? lx - w : lx - w / 2
  return [x0, ly - 15, x0 + w, ly + 5]
}
export function placeLabels(items: { id: string; x: number; y: number; text: string }[], fixed: Box[]): Record<string, Placed> {
  const boxes: Box[] = [...fixed, ...items.map(i => [i.x - 16, i.y - 16, i.x + 16, i.y + 16] as Box)]
  const out: Record<string, Placed> = {}
  for (const it of items) {
    let best = CANDIDATES[0], bestScore = Infinity
    for (const c of CANDIDATES) {
      const b = labelBox(it.x, it.y, c, it.text)
      const own: Box = [it.x - 16, it.y - 16, it.x + 16, it.y + 16]
      const out_ = b[0] < 8 || b[2] > 992 || b[1] < 30 || b[3] > 975
      const clashes = boxes.filter(o => !(o[0] === own[0] && o[1] === own[1]) && hit(b, o)).length + (out_ ? 5 : 0)
      const score = clashes * 100 + CANDIDATES.indexOf(c)
      if (score < bestScore) { bestScore = score; best = c }
      if (clashes === 0) break
    }
    out[it.id] = best
    boxes.push(labelBox(it.x, it.y, best, it.text))
  }
  return out
}

function Map({ sites, scores }: { sites: Site[]; scores: Scores }) {
  const { site, setSite } = useStore()
  const rank = Object.fromEntries(scores.sites.map(r => [r.site, r]))
  const sel = sites.find(s => s.id === site) ?? sites[0]
  const row = rank[sel.id]
  const top = scores.sites[0]
  const topName = sites.find(s => s.id === top.site)!.name
  const labels = useMemo(() => {
    const items = [...sites].sort((a, b) => (rank[a.id]?.rank ?? 99) - (rank[b.id]?.rank ?? 99)).map(st => {
      const [fx, fy] = mapXY(st.lat, st.lon)
      return { id: st.id, x: fx * 1000, y: fy * 1000, text: `${rank[st.id] ? `${rank[st.id].rank}. ` : ''}${st.name}` }
    })
    // fixed obstacles: the pole marker and the compass labels
    const fixed: [number, number, number, number][] = [[494, 480, 600, 506], [470, 8, 530, 34], [880, 488, 992, 512], [460, 972, 540, 998], [8, 488, 120, 512]]
    return placeLabels(items, fixed)
  }, [sites, rank])
  return (
    <>
      <div className="hero">
        <div className="eyebrow">Lunar south pole · NASA Artemis III candidate regions · 2027</div>
        <h1>Here the Sun never climbs more than a degree or two. One ridge decides whether your rover lives.</h1>
        <p>
          Sunchaser shows where to land, when, and how to drive so a solar rover survives the shadows: sunlight and Earth contact
          hour by hour at nine sites, from JPL ephemerides and LRO laser-altimeter terrain.
        </p>
        <HeroHorizon siteId={top.site} name={topName} month={scores.window_start.slice(0, 7)} />
        <div className="kpi-row">
          <Tile label={`best site, ${new Date(scores.window_start).toLocaleString('en', { month: 'long', timeZone: 'UTC' })} 2027`} value={topName} tone="sun" />
          <Tile label="candidate sites analysed" value={String(sites.length)} />
          <Tile label="hours of Sun and Earth computed per site" value="8,760" />
          <Tile label="sites where the shortest route freezes" value="7 of 9" tone="danger" hint="Rover Ops: real 2027 scenarios found by search" />
        </div>
      </div>

      <div className="map-wrap">
        <div className="map">
          <img src={basemap} alt="Shaded relief of the lunar south pole from LRO LOLA elevation data, 80 degrees south to the pole" />
          <svg viewBox="0 0 1000 1000">
            <circle cx={500} cy={500} r={4} fill="#fff" opacity={0.8} />
            <text x={508} y={496} className="axis" fill="#fff">South Pole</text>
            <text x={500} y={22} className="axis" textAnchor="middle" fill="#cfd6e3">0°</text>
            <text x={982} y={504} className="axis" textAnchor="end" fill="#cfd6e3">90° E</text>
            <text x={500} y={990} className="axis" textAnchor="middle" fill="#cfd6e3">180°</text>
            <text x={18} y={504} className="axis" fill="#cfd6e3">90° W</text>
            {sites.map(s => {
              const [fx, fy] = mapXY(s.lat, s.lon)
              const r = rank[s.id]
              const isSel = s.id === sel.id
              return (
                <g key={s.id} className={`marker ${isSel ? 'sel' : ''}`} transform={`translate(${fx * 1000},${fy * 1000})`}
                   onClick={() => setSite(s.id)} role="button" aria-label={s.name}>
                  <circle className="ring" r={isSel ? 15 : 11} />
                  <circle className="dot" r={4} />
                  {labels[s.id]?.leader && <line className="leader" x1={labels[s.id].dx > 0 ? 9 : -9} y1={labels[s.id].dy > 0 ? 9 : -9} x2={labels[s.id].dx * 0.82} y2={labels[s.id].dy - 6} />}
                  <text x={labels[s.id]?.dx ?? 16} y={labels[s.id]?.dy ?? 5} textAnchor={labels[s.id]?.anchor ?? 'start'}>{r ? `${r.rank}. ` : ''}{s.name}</text>
                </g>
              )
            })}
          </svg>
        </div>

        <div>
          <Panel title={`Ranking for ${new Date(scores.window_start).toLocaleString('en', { month: 'long', timeZone: 'UTC' })} 2027`}
                 sub="Best landing in the month for a 10-day mission. Ranked by survival first, then usable days.">
            <ul className="site-list">
              {scores.sites.map(r => {
                const s = sites.find(x => x.id === r.site)!
                return (
                  <li key={r.site} className={r.site === sel.id ? 'sel' : ''} onClick={() => setSite(r.site)}>
                    <span className={`rank ${r.rank <= 3 ? 'top' : ''}`}>{r.rank}</span>
                    <span>{s.name}</span>
                    <span className={`pill ${r.survives ? 'ok' : 'bad'}`}>{r.usable_days} / 10 d</span>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>
      </div>

      <SiteCard site={sel} row={row} />
    </>
  )
}

function HeroHorizon({ siteId, name, month }: { siteId: string; name: string; month: string }) {
  const tl = useJson<Timeline>(`timeline_${siteId}.json`)
  if (tl.state !== 'ready') return <div className="horizon status"><span className="spinner" /> Loading the horizon…</div>
  return <Horizon rows={tl.data.rows.filter(r => r.time.startsWith(month))} title={`${name}, ${month}`} />
}

function SiteCard({ site, row }: { site: Site; row: Scores['sites'][number] }) {
  const tl = useJson<Timeline>(`timeline_${site.id}.json`)
  const win = useJson<Windows>(`windows_${site.id}.json`)
  const year = tl.state === 'ready' ? tl.data.rows : null
  const lit = year ? year.filter(r => r.sun_frac >= 0.5).length / year.length : null
  const earth = year ? year.filter(r => r.earth_visible).length / year.length : null
  const ok = win.state === 'ready' ? win.data.rows.filter(r => r.survives).length / win.data.rows.length : null
  return (
    <Panel title={site.name} sub={`${Math.abs(site.lat).toFixed(3)}° S, ${Math.abs(site.lon).toFixed(3)}° ${site.lon >= 0 ? 'E' : 'W'} · ${site.elevation_m.toLocaleString()} m · ${site.notes}`}
           right={<div className="controls"><Link className="btn" to="/light">Light &amp; comms →</Link><Link className="btn" to="/rover">Rover ops →</Link></div>}>
      <div className="tiles">
        <Tile label="best landing this month" value={fmtTime(row.best_landing)} />
        <Tile label="usable days of 10" value={String(row.usable_days)} tone={row.survives ? 'both' : 'danger'} />
        <Tile label="longest dark spell" value={String(row.longest_dark_h)} unit="h" tone={row.survives ? '' : 'danger'} />
        <Tile label="sunlit, all of 2027" value={lit === null ? '…' : `${(100 * lit).toFixed(0)}%`} tone="sun" />
        <Tile label="Earth in view, all of 2027" value={earth === null ? '…' : `${(100 * earth).toFixed(0)}%`} tone="earth" />
        <Tile label="landing times the rover survives" value={ok === null ? '…' : `${(100 * ok).toFixed(0)}%`} />
      </div>
      <div className="brief">{row.brief}</div>
      <p className="note">Source: {site.source}</p>
    </Panel>
  )
}
