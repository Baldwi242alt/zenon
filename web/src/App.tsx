import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
const Story = lazy(() => import('./story/Story'))
import Business from './screens/Business'
import Copilot from './screens/Copilot'
import LandingWindows from './screens/LandingWindows'
import LightComms from './screens/LightComms'
import Methods from './screens/Methods'
import MissionMap from './screens/MissionMap'
import RoverOps from './screens/RoverOps'

const NAV = [
  { to: '/', label: '← Story' },
  { to: '/map', label: 'Mission map' },
  { to: '/light', label: 'Light & comms' },
  { to: '/windows', label: 'Landing windows' },
  { to: '/rover', label: 'Rover ops' },
  { to: '/business', label: 'Business case' },
  { to: '/copilot', label: 'Copilot' },
  { to: '/methods', label: 'Methods' },
]

export default function App() {
  const loc = useLocation()
  if (loc.pathname === '/') return <Suspense fallback={<div className="story" style={{ minHeight: '100vh' }} />}><Story /></Suspense>
  const links = NAV.map(n => <NavLink key={n.to} to={n.to} end={n.to === '/'}>{n.label}</NavLink>)
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><span className="brand-dot" /><div><b>Sunchaser</b><small>Lunar Landing Site Navigator</small></div></div>
        <nav className="nav">{links}</nav>
        <div className="side-foot">Team Zenon · NASA Space Apps 2026<br />Data: JPL Horizons, LRO LOLA</div>
      </aside>
      <div>
        <nav className="mobile-nav">{links}</nav>
        <main className="main">
          <Routes>
            <Route path="/map" element={<MissionMap />} />
            <Route path="/light" element={<LightComms />} />
            <Route path="/windows" element={<LandingWindows />} />
            <Route path="/rover" element={<RoverOps />} />
            <Route path="/business" element={<Business />} />
            <Route path="/copilot" element={<Copilot />} />
            <Route path="/methods" element={<Methods />} />
            <Route path="*" element={<div className="status">That page doesn't exist. Use the menu to pick a screen.</div>} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
