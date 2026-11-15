import { Link, NavLink } from 'react-router-dom'

// One navigation bar for every page: Orbitron wordmark, serif links, the copilot as the call to action.
const LINKS = [
  { to: '/map', label: 'Sites' },
  { to: '/light', label: 'Light' },
  { to: '/windows', label: 'Windows' },
  { to: '/rover', label: 'Rover' },
  { to: '/business', label: 'Business' },
  { to: '/methods', label: 'Methods' },
]

export function SiteNav() {
  return (
    <header className="ca-nav">
      <Link to="/" className="ca-brand" aria-label="Sunchaser home"><span className="ca-brand-mark" aria-hidden="true" />SUNCHASER</Link>
      <nav aria-label="Main">
        {LINKS.map(l => <NavLink key={l.to} to={l.to}>{l.label}</NavLink>)}
        <NavLink to="/copilot" className="ca-nav-cta">Ask Gemini</NavLink>
      </nav>
      <nav className="ca-nav-mobile" aria-label="Main (mobile)">
        <NavLink to="/" end>Home</NavLink>
        {LINKS.map(l => <NavLink key={l.to} to={l.to}>{l.label}</NavLink>)}
        <NavLink to="/copilot">Ask Gemini</NavLink>
      </nav>
    </header>
  )
}
