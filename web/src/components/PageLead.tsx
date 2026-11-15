import { useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import validation from '../../../data/sites/validation.json'
import { MONTH_NAMES, useJson } from '../data'
import { useStore } from '../store'
import type { RouteFile, Scores, Site, Timeline, Windows } from '../types'

// Every tool page opens with its answer: one sentence computed from the data, plus a visual
// that belongs to that page alone. The detailed tools follow underneath.
export function PageLead() {
  const { pathname } = useLocation()
  const sites = useJson<Site[]>('sites.json')
  const names = useMemo(() => (sites.state === 'ready' ? Object.fromEntries(sites.data.map(s => [s.id, s.name])) : {}), [sites]) as Record<string, string>
  const body = ({
    '/map': <SitesLead names={names} />,
    '/light': <LightLead names={names} />,
    '/windows': <WindowsLead names={names} />,
    '/rover': <RoverLead names={names} />,
    '/business': <BusinessLead names={names} />,
    '/copilot': <CopilotLead />,
    '/methods': <MethodsLead />,
  } as Record<string, React.ReactNode>)[pathname]
  return body ? <section className="lead" key={pathname}>{body}</section> : null
}

function Lead({ eyebrow, children, visual }: { eyebrow: string; children: React.ReactNode; visual?: React.ReactNode }) {
  return (
    <>
      <div className="lead-copy">
        <p className="ca-eyebrow">{eyebrow}</p>
        <h2 className="lead-answer">{children}</h2>
      </div>
      {visual && <div className="lead-visual">{visual}</div>}
    </>
  )
}

type N = { names: Record<string, string> }

// Sites: the ranking itself, as bars of usable days.
function SitesLead({ names }: N) {
  const scores = useJson<Scores>('scores.json')
  if (scores.state !== 'ready') return null
  const s = scores.data, top = s.sites[0], max = Math.max(...s.sites.map(r => r.usable_days), 1)
  const month = MONTH_NAMES[+s.window_start.slice(5, 7) - 1]
  return (
    <Lead eyebrow={`The answer · ${month} 2027 · 10-day mission`} visual={
      <ol className="lead-bars">
        {s.sites.map(r => (
          <li key={r.site} className={r.rank === 1 ? 'top' : ''}>
            <span className="lb-rank">{r.rank}</span><span className="lb-name">{names[r.site] ?? r.site}</span>
            <span className="lb-bar"><i style={{ width: `${(100 * r.usable_days) / max}%` }} /></span><b>{r.usable_days}</b>
          </li>
        ))}
      </ol>}>
      In {month} 2027, land at <em>{names[top.site] ?? top.site}</em>. It gives {top.usable_days} usable days out of 10, with {top.sun_hours} hours of sunlight and Earth in view for {top.contact_hours}.
    </Lead>
  )
}

// Light: a month clock. 720 hourly ticks around a ring, coloured by what the site can see.
function LightLead({ names }: N) {
  const { site, month } = useStore()
  const tl = useJson<Timeline>(`timeline_${site}.json`)
  const rows = useMemo(() => {
    if (tl.state !== 'ready') return []
    const key = `2027-${String(month + 1).padStart(2, '0')}`
    return tl.data.rows.filter(r => r.time.startsWith(key))
  }, [tl, month])
  if (!rows.length) return null
  const sun = rows.filter(r => r.sun_frac >= 0.5).length / rows.length
  const earth = rows.filter(r => r.earth_visible).length / rows.length
  const both = rows.filter(r => r.sun_frac >= 0.5 && r.earth_visible).length / rows.length
  const R1 = 92, R2 = 140
  return (
    <Lead eyebrow={`The answer · ${names[site] ?? site} · ${MONTH_NAMES[month]} 2027`} visual={
      <svg viewBox="-160 -160 320 320" className="lead-ring" role="img" aria-label="Month clock: each tick is one hour; amber is sunlight, blue is Earth in view, green is both">
        {rows.map((r, i) => {
          const a = (i / rows.length) * Math.PI * 2 - Math.PI / 2
          const lit = r.sun_frac >= 0.5, e = r.earth_visible
          const c = lit && e ? '#5fd39b' : lit ? '#f2a541' : e ? '#8db8ff' : '#1b1b1d'
          return <line key={i} x1={Math.cos(a) * R1} y1={Math.sin(a) * R1} x2={Math.cos(a) * R2} y2={Math.sin(a) * R2} stroke={c} strokeWidth={1.1} />
        })}
        <circle r={R1 - 8} fill="none" stroke="rgba(235,228,210,0.12)" />
        <text y={-6} textAnchor="middle" className="ring-big">{Math.round(100 * sun)}%</text>
        <text y={18} textAnchor="middle" className="ring-small">SUNLIT</text>
        <text y={-148} textAnchor="middle" className="ring-small">DAY 1</text>
      </svg>}>
      {names[site] ?? site} is sunlit <em>{Math.round(100 * sun)}%</em> of {MONTH_NAMES[month]}, can see Earth <em className="earth">{Math.round(100 * earth)}%</em> of the time, and has both power and radio <em className="both">{Math.round(100 * both)}%</em>.
    </Lead>
  )
}

// Windows: a 12-month calendar of how many landing times are survivable.
function WindowsLead({ names }: N) {
  const { site } = useStore()
  const w = useJson<Windows>(`windows_${site}.json`)
  if (w.state !== 'ready') return null
  const rows = w.data.rows
  const best = rows.reduce((a, b) => (b.usable_days > a.usable_days ? b : a), rows[0])
  const months = MONTH_NAMES.map((m, i) => {
    const rs = rows.filter(r => +r.landing.slice(5, 7) === i + 1)
    return { m, share: rs.length ? rs.filter(r => r.survives).length / rs.length : 0 }
  })
  const share = rows.filter(r => r.survives).length / rows.length
  const d = new Date(best.landing)
  return (
    <Lead eyebrow={`The answer · ${names[site] ?? site} · all of 2027`} visual={
      <div className="lead-cal">
        {months.map(({ m, share }) => (
          <div key={m} className={m === MONTH_NAMES[d.getUTCMonth()] ? 'best' : ''}>
            <span className="cal-fill" style={{ height: `${Math.max(3, 100 * share)}%` }} />
            <b>{Math.round(100 * share)}%</b><small>{m.slice(0, 3)}</small>
          </div>
        ))}
      </div>}>
      The best time to land at {names[site] ?? site} is <em>{d.getUTCDate()} {MONTH_NAMES[d.getUTCMonth()]}, {String(d.getUTCHours()).padStart(2, '0')}:00 UTC</em>: {best.usable_days} usable days. Only {Math.round(100 * share)}% of landing times in 2027 are survivable here.
    </Lead>
  )
}

// Rover: two survival gauges.
function Gauge({ p, label, color }: { p: number; label: string; color: string }) {
  const a = Math.PI * (1 - p), r = 70
  const x = Math.cos(a) * r, y = -Math.sin(a) * r
  return (
    <figure className="gauge">
      <svg viewBox="-90 -86 180 100">
        <path d={`M${-r},0 A${r},${r} 0 0 1 ${r},0`} fill="none" stroke="rgba(235,228,210,0.1)" strokeWidth={12} />
        {p > 0.001 && <path d={`M${-r},0 A${r},${r} 0 0 1 ${x.toFixed(2)},${y.toFixed(2)}`} fill="none" stroke={color} strokeWidth={12} />}
        <text y={-8} textAnchor="middle" className="ring-big">{Math.round(100 * p)}%</text>
      </svg>
      <figcaption>{label}</figcaption>
    </figure>
  )
}
function RoverLead({ names }: N) {
  const { site } = useStore()
  const rf = useJson<RouteFile>(`route_${site}.json`)
  if (rf.state !== 'ready') return null
  const short = rf.data.routes.find(r => r.name === 'shortest'), fast = rf.data.routes.find(r => r.name === 'sunchaser_fast')
  if (!short || !fast) return null
  return (
    <Lead eyebrow={`The answer · ${names[site] ?? site} · ${rf.data.monte_carlo_runs} simulated missions per route`} visual={
      <div className="lead-gauges"><Gauge p={short.survival_probability} label="Shortest path" color="#f0605d" /><Gauge p={fast.survival_probability} label="Sunchaser" color="#f2a541" /></div>}>
      The shortest route survives <em className="danger">{Math.round(100 * short.survival_probability)}%</em> of the time. Sunchaser takes {Math.round(fast.duration_h - short.duration_h)} hours longer, chases the light, and survives <em>{Math.round(100 * fast.survival_probability)}%</em>.
    </Lead>
  )
}

// Business: what a three-day launch slip does to the best June window.
function BusinessLead({ names }: N) {
  const { site, budget } = useStore()
  const w = useJson<Windows>(`windows_${site}.json`)
  if (w.state !== 'ready') return null
  const rows = w.data.rows, per = 24 / w.data.step_h
  const june = rows.map((r, i) => ({ r, i })).filter(x => x.r.landing.startsWith('2027-06'))
  const best = june.reduce((a, b) => (b.r.usable_days > a.r.usable_days ? b : a), june[0])
  const late = rows[Math.min(rows.length - 1, best.i + 3 * per)]
  const a = best.r.usable_days, b = late.usable_days
  const cost = (d: number) => (budget > 0 && d > 0 ? `$${(budget / d / 1e6).toFixed(1)}M per day` : d > 0 ? '' : 'no usable days')
  return (
    <Lead eyebrow={`The answer · ${names[site] ?? site} · best June 2027 landing vs three days late`} visual={
      <div className="lead-slip">
        {[['On time', a], ['3 days late', b]].map(([k, v]) => (
          <div key={k as string}><span>{k}</span><i style={{ width: `${(100 * (v as number)) / 10}%` }} /><b>{v} days</b><small>{cost(v as number)}</small></div>
        ))}
      </div>}>
      {a === b ? <>At {names[site] ?? site}, a three-day slip from the best June landing keeps <em>{a} usable days</em>. Check other sites: at some, the same slip is far more costly.</>
        : <>At {names[site] ?? site}, slipping three days from the best June landing turns <em>{a} usable days</em> into <em className="danger">{b}</em>. {budget > 0 ? 'Each remaining day costs more.' : 'Enter your budget below to see the cost per day.'}</>}
    </Lead>
  )
}

function CopilotLead() {
  const steps = [['You ask', 'A question in plain English, about any site, month or route.'], ['It looks up', 'A model picks which of eight data tools to call; the tools read Sunchaser\'s computed files.'],
    ['It checks', 'Every number in the answer must appear in the data, or the answer is rejected. The facts used are listed.']]
  return (
    <Lead eyebrow="How the copilot answers" visual={
      <ol className="lead-steps">{steps.map(([k, v], i) => <li key={k}><span>{String(i + 1).padStart(2, '0')}</span><b>{k}</b><p>{v}</p></li>)}</ol>}>
      A mission assistant that <em>cannot invent numbers</em>: it only answers from what Sunchaser computed.
    </Lead>
  )
}

function MethodsLead() {
  const s = (validation as unknown as { maps: { summary: Record<string, number> } }).maps.summary
  return (
    <Lead eyebrow="Checked against NASA" visual={
      <div className="lead-figs">
        <div><b>{s.sun_correlation.toFixed(2)}</b><span>correlation with NASA's sunlight map</span></div>
        <div><b>{s.earth_correlation.toFixed(2)}</b><span>correlation with NASA's Earth-visibility map</span></div>
        <div><b>2 / 2</b><span>real landings (IM-1, IM-2) with Sun up and Earth in view</span></div>
      </div>}>
      Every number on this site comes from <em>NASA data</em>, and our results agree with NASA's own published maps.
    </Lead>
  )
}
