import { lazy, Suspense, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Horizon } from '../components/Horizon'
import { useJson } from '../data'
import type { Grid, RouteFile, Scores, Timeline } from '../types'
import { MoonScene } from './MoonScene'
import { useReveal, useSectionProgress } from './useScroll'

const TerrainScene = lazy(() => import('./TerrainScene').then(m => ({ default: m.TerrainScene })))

// The landing page: a scroll story, then the tools.
export default function Story() {
  return (
    <div className="story">
      <header className="story-nav">
        <Link to="/" className="story-brand"><span className="brand-dot" /> Sunchaser</Link>
        <nav>
          <Link to="/map">Sites</Link><Link to="/light">Light</Link><Link to="/rover">Rover</Link><Link to="/business">Business</Link>
          <Link to="/copilot" className="story-cta">Ask the copilot</Link>
        </nav>
      </header>

      <Hero />

      <Chapter eyebrow="The problem" title="Land in the wrong place, at the wrong time, or drive the wrong way, and your robot freezes.">
        A solar rover in shadow gets no power and must burn 60 W on heaters just to survive. Commercial landers are heading to the south
        pole now, and surface days are the most expensive days of any mission.
      </Chapter>

      <HorizonChapter />

      <Numbers />

      <RoverChapter />

      <Chapter eyebrow="What it's worth" title="A 3-day launch slip at Malapert halves the usable days, and doubles what each one costs.">
        Sunchaser scores every landing time in 2027, so a mission team can see what a slip costs before it happens. The business screen
        turns your own budget into cost per usable day.
        <div className="cta-row"><Link className="btn primary" to="/windows">See every landing window</Link><Link className="btn" to="/business">Business case</Link></div>
      </Chapter>

      <Chapter eyebrow="Checked against reality" title="It agrees with NASA's own maps, and with the landers that went there.">
        Our sunlight and Earth-visibility averages correlate 0.98 and 0.99 with NASA's published LOLA illumination maps. At the IM-1 and
        IM-2 landing sites the model shows the Sun up and Earth in view, as both landers needed. Every limit is stated on the Methods page.
        <div className="cta-row"><Link className="btn" to="/methods">How it's computed</Link></div>
      </Chapter>

      <section className="finale">
        <h2 className="big">Plan your landing.</h2>
        <p className="lede">Nine NASA Artemis III candidate regions. Every hour of 2027. Real terrain, real ephemerides.</p>
        <div className="tools">
          {TOOLS.map(([to, name, what]) => (
            <Link key={to} to={to}><Tilt className="tool"><b>{name}</b><span>{what}</span><i>Open →</i></Tilt></Link>
          ))}
        </div>
        <p className="foot">Data: JPL Horizons, LRO LOLA, NASA Goddard PGDA. The globe beyond 75° S is illustrative; the south polar cap is real LOLA terrain. Team Zenon: Baldwin, Harril, Dhiran.</p>
      </section>
    </div>
  )
}

// Sticky hero: the Moon turns its south pole toward you as you scroll; a ring shows the Sun's
// path skimming the polar horizon. Kept in its own component so scroll updates re-render only this.
function Hero() {
  const heroRef = useRef<HTMLElement>(null)
  const heroP = useSectionProgress(heroRef)
  return (
    <section ref={heroRef} className="sticky-wrap" style={{ height: '260vh' }}>
        <div className="sticky">
          <MoonScene progress={heroP} />
          <div className="orbit" style={{ transform: `translate(-50%, -50%) scale(${1 + heroP * 0.5}) rotateX(76deg)`, opacity: 1 - heroP * 1.4 }} aria-hidden="true">
            <div className="orbit-sun" />
          </div>
          <div className="hero-copy" style={{ opacity: 1 - heroP * 2.2, transform: `translateY(${-heroP * 120}px)` }}>
            <div className="eyebrow">Team Zenon · NASA Space Apps 2026</div>
            <h1 className="mega">Sunchaser</h1>
            <p className="lede">Where to land at the Moon's south pole, when, and how to keep your rover alive.</p>
            <p className="hint">Scroll · drag the Moon</p>
          </div>
          <div className="hero-copy second" style={{ opacity: Math.max(0, Math.min(1, (heroP - 0.45) * 3)) }}>
            <h2 className="big">At the south pole the Sun never climbs more than 1.5°.</h2>
            <p className="lede">It circles the horizon once a month. Every hill throws a shadow kilometres long, and the shadows never stop moving.</p>
          </div>
        </div>
    </section>
  )
}

// A card that tilts toward the pointer (CSS 3D transform; no React state, so it costs nothing).
function Tilt({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = e.currentTarget, r = el.getBoundingClientRect()
    el.style.setProperty('--ry', `${((e.clientX - r.left) / r.width - 0.5) * 14}deg`)
    el.style.setProperty('--rx', `${-((e.clientY - r.top) / r.height - 0.5) * 14}deg`)
  }
  const leave = (e: React.PointerEvent<HTMLDivElement>) => { e.currentTarget.style.setProperty('--rx', '0deg'); e.currentTarget.style.setProperty('--ry', '0deg') }
  return <div className={`tilt ${className}`} onPointerMove={move} onPointerLeave={leave}><div className="tilt-inner">{children}</div></div>
}

const TOOLS: [string, string, string][] = [
  ['/map', 'Compare sites', 'Nine regions ranked by usable days, on the real LOLA map'],
  ['/light', 'Sun and Earth', 'Hour by hour: sunlight, Earth contact, Deep Space Network'],
  ['/windows', 'Landing windows', 'Every landing time in 2027, and what a slip costs'],
  ['/rover', 'Rover ops', 'Shortest path versus Sunchaser, with survival odds'],
  ['/business', 'Business case', 'Your budget, turned into cost per usable day'],
  ['/copilot', 'Mission copilot', 'Ask in plain English; answers cite the computed numbers'],
]

function Chapter({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="chapter reveal">
      <div className="eyebrow">{eyebrow}</div>
      <h2 className="big">{title}</h2>
      <div className="lede">{children}</div>
    </section>
  )
}

function HorizonChapter() {
  const ref = useReveal<HTMLElement>()
  const scores = useJson<Scores>('scores.json')
  const site = scores.state === 'ready' ? scores.data.sites[0].site : null
  const tl = useJson<Timeline>(site ? `timeline_${site}.json` : null)
  const month = scores.state === 'ready' ? scores.data.window_start.slice(0, 7) : ''
  const rows = useMemo(() => (tl.state === 'ready' ? tl.data.rows.filter(r => r.time.startsWith(month)) : null), [tl, month])
  return (
    <section ref={ref} className="chapter wide reveal">
      <div className="eyebrow">Real terrain, real Sun</div>
      <h2 className="big">One ridge decides whether you have power.</h2>
      <p className="lede">This is the actual horizon around Peak near Cabeus B, ray-cast 150 km out over NASA laser-altimeter terrain, with the Sun's
        real path for June 2027. Where the Sun slips behind the ridge, the site goes dark.</p>
      {rows && <Horizon rows={rows} title="Peak near Cabeus B, June 2027" />}
    </section>
  )
}

function Numbers() {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="numbers reveal">
      <Tilt><b>9</b><span>NASA Artemis III candidate regions, each at its best-lit published landing point</span></Tilt>
      <Tilt><b>8,760</b><span>hours of Sun and Earth visibility computed for every site in 2027</span></Tilt>
      <Tilt><b>14–54%</b><span>of landing times are survivable, depending on the site. When matters as much as where.</span></Tilt>
    </section>
  )
}

function RoverChapter() {
  const ref = useRef<HTMLElement>(null)
  const p = useSectionProgress(ref)
  const grid = useJson<Grid>('grid_slater_plain.json')
  const rf = useJson<RouteFile>('route_slater_plain.json')
  const ready = grid.state === 'ready' && rf.state === 'ready'
  const r = rf.state === 'ready' ? rf.data : null
  const end = r ? Math.max(...r.routes.map(x => x.duration_h)) + 1 : 1
  const t = p * end
  const short = r?.routes.find(x => x.name === 'shortest')
  const fast = r?.routes.find(x => x.name === 'sunchaser_fast')
  const batt = (route?: RouteFile['routes'][number]) => {
    if (!route) return 0
    let i = 0
    while (i + 1 < route.steps.length && route.steps[i + 1].t_h <= t) i++
    return route.steps[i].battery_wh / 20
  }
  const shortFrozen = short && !short.survived && t >= short.duration_h
  const fastArrived = fast && t >= fast.duration_h
  return (
    <section ref={ref} className="sticky-wrap" style={{ height: '320vh' }}>
      <div className="sticky">
        {ready ? <Suspense fallback={null}><TerrainScene grid={grid.data} rf={rf.data} t={t} /></Suspense> : <div className="status"><span className="spinner" /> Loading Slater Plain terrain…</div>}
        <div className="hud">
          <div className="eyebrow">Slater Plain · 31 Oct 2027 · real LOLA terrain, computed shadows</div>
          <h2 className="big small">Same 4 km drive. One rover chases the Sun.</h2>
          <div className="hud-row">
            <div className={`hud-card ${shortFrozen ? 'dead' : ''}`}>
              <span className="dot red" />Shortest path
              <b>{shortFrozen ? 'FROZEN' : `${batt(short).toFixed(0)}%`}</b>
              <small>{short ? `survives ${(100 * short.survival_probability).toFixed(0)}% of 500 simulated missions` : ''}</small>
            </div>
            <div className="hud-card">
              <span className="dot amber" />Sunchaser
              <b>{fastArrived ? 'ARRIVED' : `${batt(fast).toFixed(0)}%`}</b>
              <small>{fast ? `survives ${(100 * fast.survival_probability).toFixed(0)}% of 500 simulated missions` : ''}</small>
            </div>
          </div>
          <div className="hud-time">T+{t.toFixed(1)} h · scroll to drive · drag to orbit</div>
        </div>
      </div>
    </section>
  )
}
