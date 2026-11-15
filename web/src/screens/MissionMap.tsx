import { Link } from 'react-router-dom'
import basemap from '../assets/south_pole.jpg'
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

function Map({ sites, scores }: { sites: Site[]; scores: Scores }) {
  const { site, setSite } = useStore()
  const rank = Object.fromEntries(scores.sites.map(r => [r.site, r]))
  const sel = sites.find(s => s.id === site) ?? sites[0]
  const row = rank[sel.id]
  const top = scores.sites[0]
  const topName = sites.find(s => s.id === top.site)!.name
  return (
    <>
      <div className="hero">
        <h1>Where to land at the Moon's south pole, when, and how to keep your rover alive</h1>
        <p>
          The Sun never rises more than about 1.5° here, so shadows kilometres long sweep the ground all month, and Earth dips
          behind the terrain for days. Sunchaser computes sunlight and Earth contact hour by hour at NASA's nine Artemis III
          candidate regions from JPL ephemerides and LRO laser-altimeter terrain, then plans rover routes that survive the shadows.
        </p>
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
            <text x={986} y={504} className="axis" textAnchor="end" fill="#cfd6e3">90° E</text>
            <text x={500} y={990} className="axis" textAnchor="middle" fill="#cfd6e3">180°</text>
            <text x={14} y={504} className="axis" fill="#cfd6e3">90° W</text>
            {sites.map(s => {
              const [fx, fy] = mapXY(s.lat, s.lon)
              const r = rank[s.id]
              const isSel = s.id === sel.id
              return (
                <g key={s.id} className={`marker ${isSel ? 'sel' : ''}`} transform={`translate(${fx * 1000},${fy * 1000})`}
                   onClick={() => setSite(s.id)} role="button" aria-label={s.name}>
                  <circle className="ring" r={isSel ? 15 : 11} />
                  <circle className="dot" r={4} />
                  <text x={16} y={5}>{r ? `${r.rank}. ` : ''}{s.name}</text>
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
