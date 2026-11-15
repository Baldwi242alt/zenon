import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Horizon } from '../components/Horizon'
import { useJson, useRover } from '../data'
import type { Grid, RouteFile, Scores, Timeline } from '../types'
import im2Launch from '../assets/nasa/im2_launch.jpg'
import earthrise from '../assets/nasa/lro_earthrise.jpg'
import lrocPole from '../assets/nasa/lroc_south_pole.jpg'
import roverRidge from '../assets/viz/rover_ridge.jpg'
import { MoonScene } from './MoonScene'
import { Scrub } from './Scrub'
import { useReveal, useSectionProgress } from './useScroll'
import './story.css'

const TerrainScene = lazy(() => import('./TerrainScene').then(m => ({ default: m.TerrainScene })))

// Frame sequences extracted from the Higgsfield visualizations (see web/src/assets/viz/README.md).
const byName = (g: Record<string, string>) => Object.keys(g).sort().map(k => g[k])
const SHADOW_FRAMES = byName(import.meta.glob('../assets/viz/shadow/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>)
const ROVER_FRAMES = byName(import.meta.glob('../assets/viz/rover/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>)

// The landing page, in the style of our Celestial Archive: an editorial scroll story about the
// lunar south pole, built on NASA data and imagery, that hands off to the planning tools.
export default function Story() {
  return (
    <div className="ca">
      <Nav />
      <Hero />
      <Survey />
      <ShadowFeature />
      <HorizonFeature />
      <RoverIntro />
      <RoverFeature />
      <Results />
      <Business />
      <Validation />
      <Tools />
      <Footer />
    </div>
  )
}

function Nav() {
  return (
    <header className="ca-nav">
      <Link to="/" className="ca-brand"><span className="ca-brand-mark" aria-hidden="true" />SUNCHASER</Link>
      <nav aria-label="Main">
        <Link to="/map">Sites</Link><Link to="/light">Light</Link><Link to="/windows">Windows</Link>
        <Link to="/rover">Rover</Link><Link to="/business">Business</Link><Link to="/methods">Methods</Link>
        <Link to="/copilot" className="ca-nav-cta">Ask the copilot</Link>
      </nav>
    </header>
  )
}

// Sticky hero: the real LRO Moon turns its south pole toward you as you scroll.
function Hero() {
  const ref = useRef<HTMLElement>(null)
  const p = useSectionProgress(ref)
  const second = Math.max(0, Math.min(1, (p - 0.42) * 3))
  return (
    <section ref={ref} className="ca-hero" style={{ height: '250vh' }}>
      <div className="ca-sticky">
        <div className="ca-hero-glow" style={{ opacity: 0.6 + p * 0.4 }} />
        <div className="ca-hero-moon"><MoonScene progress={p} /></div>
        <div className="ca-hero-copy" style={{ opacity: 1 - p * 2.4, transform: `translateY(${-p * 80}px)` }}>
          <p className="ca-eyebrow">Team Zenon · NASA Space Apps 2026 · Lunar Landing Site Navigator</p>
          <h1 className="ca-title">SUNCHASER</h1>
          <p className="ca-subtitle">The Sun-Skimming Pole</p>
          <p className="ca-hint">Scroll to descend · drag to turn the Moon</p>
        </div>
        <div className="ca-hero-copy second" style={{ opacity: second, transform: `translateY(${(1 - second) * 40}px)` }}>
          <p className="ca-eyebrow">Interactive globe · LRO camera mosaic</p>
          <h2 className="ca-h1">Turn the Moon.<br />Find the light.</h2>
          <p className="ca-body">At the south pole the Sun never climbs more than about 1.5° above the horizon. It circles the sky once a month,
            skimming the crater rims. Land in the right place and it almost never sets. Land in the wrong one and your robot freezes.</p>
        </div>
      </div>
    </section>
  )
}

// Editorial survey with a sticky index, as on the Saturn and Mars pages.
const RECORDS = [
  { id: 'sun', title: 'The Sun barely rises' },
  { id: 'shadow', title: 'Shadows that never stop moving' },
  { id: 'earth', title: 'Earth on the horizon' },
  { id: 'cold', title: 'The cold is lethal' },
  { id: 'now', title: 'Landers are going now' },
]

function Survey() {
  const [active, setActive] = useState('sun')
  useEffect(() => {
    const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && setActive(e.target.id)), { rootMargin: '-45% 0px -50% 0px' })
    RECORDS.forEach(r => { const el = document.getElementById(r.id); if (el) io.observe(el) })
    return () => io.disconnect()
  }, [])
  return (
    <section className="ca-section ca-survey">
      <div className="ca-records">
        <Record id="sun" n="01" title="The Sun barely rises">
          The Moon's spin axis is tilted only about 1.5° from the plane of Earth's orbit, so at the pole the Sun never climbs more than about
          1.5° above a flat horizon. It is a disk half a degree wide, so near the horizon terrain often hides part of it. Sunchaser tracks the
          visible fraction of the Sun's disk, hour by hour, not just whether it is up.
        </Record>
        <Record id="shadow" n="02" title="Shadows that never stop moving"
          figure={<Figure src={lrocPole} tag="LROC WAC · South pole mosaic" credit="NASA/GSFC/Arizona State University" alt="LRO camera mosaic of the lunar south pole, with long shadows filling the craters" />}>
          With the Sun this low, every hill throws a shadow kilometres long. One lunar day lasts about 29.5 Earth days, so a ridge can stay lit
          for weeks while the crater beside it is dark for days. This is the real south pole, photographed by the Lunar Reconnaissance Orbiter.
        </Record>
        <Record id="earth" n="03" title="Earth on the horizon"
          figure={<Figure src={earthrise} tag="LRO · Earthrise over Compton crater" credit="NASA/GSFC/Arizona State University" alt="Earth rising over the lunar horizon, photographed by LRO" />}>
          A lander talks to Earth directly, through NASA's Deep Space Network dishes at Goldstone, Madrid and Canberra. From the south pole Earth
          sits low on the horizon and wobbles about ±6.7° over a month. At many sites terrain blocks it for days at a time.
        </Record>
        <Record id="cold" n="04" title="The cold is lethal">
          In shadow a solar rover gets no power and must spend its battery on heaters just to survive. At walking pace, keeping warm costs more
          energy than climbing hills. A route that is short on the map can be fatal if it crosses the wrong shadow at the wrong hour.
        </Record>
        <Record id="now" n="05" title="Landers are going now"
          figure={<Figure src={im2Launch} tag="CLPS IM-2 liftoff · 26 Feb 2025" credit="NASA" alt="Night launch of the Intuitive Machines IM-2 mission" tall />}>
          NASA's Commercial Lunar Payload Services pay companies to deliver robots to the Moon. Intuitive Machines landed IM-1 near the south pole
          in February 2024 and IM-2 in March 2025. Every one of those missions has a fixed budget and a limited number of working days.
        </Record>
      </div>
      <aside className="ca-index">
        <p className="ca-eyebrow">Lunar south pole</p>
        <h3 className="ca-h3">Where the Sun never sets</h3>
        <p className="ca-small">Everything here is drawn from NASA data. Follow the index to move through the survey.</p>
        <ol className="ca-index-list">
          {RECORDS.map(r => (
            <li key={r.id} className={active === r.id ? 'on' : ''}>
              <a href={`#${r.id}`}>{r.title}</a>{active === r.id && <span className="ca-reading">reading</span>}
            </li>
          ))}
        </ol>
        <Specs cells={[['Highest Sun', '≈ 1.5°'], ['Lunar day', '29.5 Earth days'], ['Gravity', '1.62 m/s²'], ['Earth swing', '± 6.7°']]} />
      </aside>
    </section>
  )
}

function Record({ id, n, title, children, figure }: { id: string; n: string; title: string; children: React.ReactNode; figure?: React.ReactNode }) {
  const ref = useReveal<HTMLElement>()
  return (
    <article ref={ref} id={id} className="ca-record reveal">
      <p className="ca-record-n">Record {n}</p>
      <h2 className="ca-h2">{title}</h2>
      <p className="ca-body">{children}</p>
      {figure}
    </article>
  )
}

function Figure({ src, tag, credit, alt, tall }: { src: string; tag: string; credit: string; alt: string; tall?: boolean }) {
  return (
    <figure className={`ca-figure ${tall ? 'tall' : ''}`}>
      <img src={src} alt={alt} loading="lazy" />
      <span className="ca-tag">{tag}</span>
      <figcaption>Image: {credit}</figcaption>
    </figure>
  )
}

function Specs({ cells }: { cells: [string, string][] }) {
  return <div className="ca-specs">{cells.map(([k, v]) => <div key={k}><span>{k}</span><b>{v}</b></div>)}</div>
}

// Scroll-scrubbed visualization of shadows sweeping across polar terrain.
function ShadowFeature() {
  const ref = useRef<HTMLElement>(null)
  const p = useSectionProgress(ref)
  return (
    <section ref={ref} className="ca-scrub-wrap" style={{ height: SHADOW_FRAMES.length ? '300vh' : 'auto' }}>
      <div className={SHADOW_FRAMES.length ? 'ca-sticky' : ''}>
        <div className="ca-scrub-head">
          <p className="ca-eyebrow center">Special feature · Shadow sequence</p>
          <h2 className="ca-display">Watch the light move.</h2>
          <p className="ca-body center">Scroll to move time forward. The Sun slides sideways along the horizon, and the shadows sweep with it.</p>
        </div>
        <div className="ca-frame">
          {SHADOW_FRAMES.length
            ? <Scrub frames={SHADOW_FRAMES} progress={p} alt="Visualization: shadows sweeping across polar terrain as the low Sun moves along the horizon" />
            : <img src={roverRidge} alt="" className="scrub" />}
          <span className="ca-tag tl">Polar day · time-lapse</span>
          <span className="ca-tag br">Illustrative · Higgsfield visualization</span>
          <div className="ca-progress"><i style={{ width: `${p * 100}%` }} /></div>
        </div>
      </div>
    </section>
  )
}

// The real thing: our terrain horizon and the Sun's computed path.
function HorizonFeature() {
  const ref = useReveal<HTMLElement>()
  const scores = useJson<Scores>('scores.json')
  const site = scores.state === 'ready' ? scores.data.sites[0].site : null
  const tl = useJson<Timeline>(site ? `timeline_${site}.json` : null)
  const month = scores.state === 'ready' ? scores.data.window_start.slice(0, 7) : ''
  const rows = useMemo(() => (tl.state === 'ready' ? tl.data.rows.filter(r => r.time.startsWith(month)) : null), [tl, month])
  return (
    <section ref={ref} className="ca-section ca-feature reveal">
      <div className="ca-split">
        <div>
          <p className="ca-eyebrow">Computed · LRO LOLA terrain · JPL Horizons</p>
          <h2 className="ca-h1">Now the real one.</h2>
        </div>
        <p className="ca-body">This is the true horizon around Peak near Cabeus B, ray-cast 150 km out over NASA's laser-altimeter terrain with the
          Moon's curvature included, and the Sun's real path through June 2027. Where the Sun's track dips behind the ridge, the site goes dark.</p>
      </div>
      {rows && <div className="ca-horizon"><Horizon rows={rows} title="Peak near Cabeus B · June 2027" /></div>}
    </section>
  )
}

// Rover introduction: a scrubbed visualization beside the reference rover's numbers.
function RoverIntro() {
  const ref = useRef<HTMLElement>(null)
  const p = useSectionProgress(ref)
  const { rover } = useRover()
  const peak = 1361 * rover.panel.area_m2 * rover.panel.efficiency
  return (
    <section ref={ref} className="ca-scrub-wrap" style={{ height: ROVER_FRAMES.length ? '220vh' : 'auto' }}>
      <div className={`ca-rover ${ROVER_FRAMES.length ? 'ca-sticky' : ''}`}>
        <div className="ca-frame wide">
          {ROVER_FRAMES.length
            ? <Scrub frames={ROVER_FRAMES} progress={p} alt="Visualization: a solar rover with a vertical panel driving along a sunlit polar ridge" />
            : <img src={roverRidge} alt="Visualization: a solar rover with a vertical panel on a sunlit polar ridge" className="scrub" />}
          <span className="ca-tag br">Illustrative · Higgsfield visualization</span>
        </div>
        <div className="ca-rover-copy">
          <p className="ca-eyebrow">The reference rover</p>
          <h2 className="ca-h2">Panels stand up, because the Sun is on the horizon.</h2>
          <p className="ca-body">South-pole rovers carry vertical, sun-tracking panels. Our energy model counts solar input, avionics, survival
            heaters, and drive power from slope and rolling resistance, hour by hour.</p>
          <Specs cells={[['Peak panel power', `${Math.round(peak)} W`], ['Battery', `${rover.battery.capacity_wh.toLocaleString()} Wh`],
            ['Heaters in shadow', `${rover.power_w.heater_dark} W`], ['Speed', `${rover.drive.speed_m_per_h} m/h`]]} />
          <p className="ca-small">Reference values from the project brief.</p>
        </div>
      </div>
    </section>
  )
}

// Slater Plain in 3D: scroll drives mission time while both rovers drive their planned routes.
function RoverFeature() {
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
    return (100 * route.steps[i].battery_wh) / route.steps[0].battery_wh
  }
  const shortFrozen = !!short && !short.survived && t >= short.duration_h
  const fastArrived = !!fast && t >= fast.duration_h
  return (
    <section ref={ref} className="ca-scrub-wrap" style={{ height: '320vh' }}>
      <div className="ca-sticky">
        {ready ? <Suspense fallback={null}><TerrainScene grid={grid.data} rf={rf.data} t={t} /></Suspense> : <div className="status"><span className="spinner" /> Loading Slater Plain terrain…</div>}
        <div className="ca-hud">
          <p className="ca-eyebrow">Special feature · Slater Plain · real LOLA terrain, computed shadows</p>
          <h2 className="ca-h2">Same 4 km drive.<br />One rover chases the Sun.</h2>
          <div className="ca-specs hud">
            <div className={shortFrozen ? 'dead' : ''}><span><i className="dot red" />Shortest path</span><b>{shortFrozen ? 'FROZEN' : `${batt(short).toFixed(0)}%`}</b>
              <em>{short ? `survives ${(100 * short.survival_probability).toFixed(0)}% of 500 runs` : ''}</em></div>
            <div><span><i className="dot amber" />Sunchaser</span><b>{fastArrived ? 'ARRIVED' : `${batt(fast).toFixed(0)}%`}</b>
              <em>{fast ? `survives ${(100 * fast.survival_probability).toFixed(0)}% of 500 runs` : ''}</em></div>
          </div>
          <p className="ca-small mono">T+{t.toFixed(1)} h · battery · scroll to drive · drag to orbit</p>
        </div>
      </div>
    </section>
  )
}

function Results() {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="ca-section reveal">
      <p className="ca-eyebrow">What Sunchaser computed</p>
      <h2 className="ca-h1">Where matters. When matters just as much.</h2>
      <Specs cells={[['Candidate regions', '9 Artemis III'], ['Hours computed per site', '8,760 in 2027'], ['Survivable landing times', '14–54% by site'], ['Monte Carlo runs per route', '500']]} />
    </section>
  )
}

function Business() {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="ca-section ca-feature reveal">
      <div className="ca-split">
        <div>
          <p className="ca-eyebrow">The business case</p>
          <h2 className="ca-h1">A three-day slip can halve your mission.</h2>
        </div>
        <div>
          <p className="ca-body">At Malapert, launching three days late cuts the usable days in half, so each one costs twice as much. Sunchaser
            scores every landing time in 2027, so a mission team can see what a slip costs before it happens, in days and in dollars.</p>
          <div className="ca-links"><Link to="/windows">See every landing window →</Link><Link to="/business">Cost per usable day →</Link></div>
        </div>
      </div>
    </section>
  )
}

function Validation() {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="ca-section reveal">
      <p className="ca-eyebrow">Checked against reality</p>
      <h2 className="ca-h1">It agrees with NASA's maps, and with the landers that went there.</h2>
      <Specs cells={[['Correlation with NASA, Sun', '0.98'], ['Correlation with NASA, Earth', '0.99'], ['IM-1 and IM-2 sites', 'Sun up, Earth in view'], ['Honest limits', 'On the Methods page']]} />
      <div className="ca-links"><Link to="/methods">How every number is computed →</Link></div>
    </section>
  )
}

const TOOLS: [string, string, string][] = [
  ['/map', 'Compare sites', 'Nine regions ranked by usable days, on the real LOLA map'],
  ['/light', 'Sun and Earth', 'Hour by hour: sunlight, Earth contact, Deep Space Network'],
  ['/windows', 'Landing windows', 'Every landing time in 2027, and what a slip costs'],
  ['/rover', 'Rover operations', 'Shortest path versus Sunchaser, with survival odds'],
  ['/business', 'Business case', 'Your budget, turned into cost per usable day'],
  ['/copilot', 'Mission copilot', 'Ask in plain English; answers cite the computed numbers'],
]

function Tools() {
  const ref = useReveal<HTMLElement>()
  return (
    <section ref={ref} className="ca-section reveal">
      <p className="ca-eyebrow center">The planner</p>
      <h2 className="ca-display">Plan your landing.</h2>
      <div className="ca-tools">
        {TOOLS.map(([to, name, what], i) => (
          <Link key={to} to={to} className="ca-tool" style={{ transitionDelay: `${i * 60}ms` }}>
            <b>{name}</b><span>{what}</span><i>Open →</i>
          </Link>
        ))}
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="ca-footer">
      <p className="ca-eyebrow center">Sunchaser · Team Zenon</p>
      <p className="ca-small center">Data: JPL Horizons, LRO LOLA elevation, NASA Goddard PGDA illumination maps. Globe: LROC WAC global mosaic via NASA Moon Trek.
        Photographs: NASA, NASA/GSFC/Arizona State University. Rover and shadow sequences are illustrative Higgsfield visualizations, not photographs.</p>
    </footer>
  )
}
