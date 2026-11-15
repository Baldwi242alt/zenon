import { lazy, Suspense } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { PageHero } from './components/PageHero'
import { SiteNav } from './components/SiteNav'
import Business from './screens/Business'
import Copilot from './screens/Copilot'
import LandingWindows from './screens/LandingWindows'
import LightComms from './screens/LightComms'
import Methods from './screens/Methods'
import MissionMap from './screens/MissionMap'
import RoverOps from './screens/RoverOps'

const Story = lazy(() => import('./story/Story'))

// Every page shares the same navigation bar; tool pages open with an archive-style header.
export default function App() {
  const loc = useLocation()
  if (loc.pathname === '/') return <Suspense fallback={<div className="arch" style={{ minHeight: '100vh' }} />}><Story /></Suspense>
  return (
    <div className="arch">
      <SiteNav />
      <PageHero />
      <main className="main">
        <Routes>
          <Route path="/map" element={<MissionMap />} />
          <Route path="/light" element={<LightComms />} />
          <Route path="/windows" element={<LandingWindows />} />
          <Route path="/rover" element={<RoverOps />} />
          <Route path="/business" element={<Business />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/methods" element={<Methods />} />
          <Route path="*" element={<div className="status">That page doesn't exist. Use the navigation above to pick a page.</div>} />
        </Routes>
      </main>
      <footer className="ca-footer">
        <p className="ca-eyebrow center">Sunchaser · Team Zenon · NASA Space Apps 2026</p>
        <p className="ca-small center">Data: JPL Horizons, LRO LOLA, NASA Goddard PGDA. Photographs: NASA, NASA/GSFC/Arizona State University, NASA/JPL-Caltech.
          Images marked illustrative are Higgsfield visualizations, not photographs.</p>
      </footer>
    </div>
  )
}
