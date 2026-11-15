import { useLocation } from 'react-router-dom'
import im2Launch from '../assets/nasa/im2_launch.jpg'
import goldstone from '../assets/nasa/goldstone_70m.jpg'
import earthrise from '../assets/nasa/lro_earthrise.jpg'
import lrocPole from '../assets/nasa/lroc_south_pole.jpg'
import lolaRelief from '../assets/south_pole.jpg'
import polarDawn from '../assets/viz/polar_dawn.webp'
import roverRidge from '../assets/viz/rover_ridge.jpg'
import roverLoop from '../assets/viz/rover_loop.mp4'
import shadowLoop from '../assets/viz/shadow_loop.mp4'

// Each tool page opens like a Celestial Archive entry: an uppercase serif title, an italic
// epithet, and an image that fades into the void. Images are NASA unless labelled illustrative.
type Hero = { eyebrow: string; title: string; epithet: string; img: string; credit: string; pos?: string; video?: string }
const HEROES: Record<string, Hero> = {
  '/map': { eyebrow: 'Mission map · nine Artemis III candidate regions', title: 'SITES', epithet: 'Where to land at the pole', img: lrocPole, credit: 'LROC WAC south pole mosaic · NASA/GSFC/Arizona State University' },
  '/light': { eyebrow: 'Light and communications · every hour of 2027', title: 'LIGHT', epithet: 'The Sun on the rim, the Earth on the edge', img: earthrise, credit: 'LRO Earthrise · NASA/GSFC/Arizona State University', pos: 'center 30%' },
  '/windows': { eyebrow: 'Landing windows · every six hours of 2027', title: 'WINDOWS', epithet: 'When the light lines up', img: polarDawn, video: shadowLoop, credit: 'Illustrative · Higgsfield visualization' },
  '/rover': { eyebrow: 'Rover operations · space-time A* with Monte Carlo survival', title: 'ROVER', epithet: 'Drive where the Sun will be', img: roverRidge, video: roverLoop, credit: 'Illustrative · Higgsfield visualization' },
  '/business': { eyebrow: 'Business case · cost per usable day', title: 'BUSINESS', epithet: 'What a day on the Moon is worth', img: im2Launch, credit: 'CLPS IM-2 liftoff, 26 Feb 2025 · NASA', pos: 'center 25%' },
  '/copilot': { eyebrow: 'Mission copilot · answers only from computed data', title: 'COPILOT', epithet: 'Ask the mission in plain English', img: goldstone, credit: 'Goldstone 70 m antenna, Deep Space Network · NASA/JPL-Caltech', pos: 'center 35%' },
  '/methods': { eyebrow: 'Methods, validation and limits', title: 'METHODS', epithet: 'How every number is made', img: lolaRelief, credit: 'Shaded relief from LRO LOLA elevation · NASA' },
}

export function PageHero() {
  const { pathname } = useLocation()
  const h = HEROES[pathname]
  if (!h) return null
  const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  return (
    <section className="pg-hero" key={pathname}>
      {h.video && !still
        ? <video className="pg-hero-img pg-hero-video" src={h.video} poster={h.img} autoPlay muted loop playsInline aria-label={h.credit} />
        : <div className="pg-hero-img" style={{ backgroundImage: `url(${h.img})`, backgroundPosition: h.pos ?? 'center' }} role="img" aria-label={h.credit} />}
      <div className="pg-hero-copy">
        <p className="ca-eyebrow">{h.eyebrow}</p>
        <h1 className="pg-title">{h.title}</h1>
        <p className="ca-subtitle">{h.epithet}</p>
      </div>
      <span className="pg-credit">{h.credit}</span>
    </section>
  )
}
