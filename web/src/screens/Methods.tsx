import validation from '../../../data/sites/validation.json'
import { Panel } from '../components/ui'

type VSite = { name: string; sun_any: number; nasa_sun: number; earth_any: number; nasa_earth: number }
const v = validation as unknown as { maps: { summary: Record<string, number>; sites: VSite[] } }
const s = v.maps.summary

export default function Methods() {
  return (
    <div className="prose">
      <div className="page-head"><div><h2>Methods, validation and limits</h2>
        <p>How every number on this site is computed, how we checked it, and what is simplified.</p></div></div>

      <Panel title="Data sources (all NASA, all free)">
        <ul>
          <li><a href="https://ssd.jpl.nasa.gov/api/horizons.api">JPL Horizons</a> (DE441 ephemeris): Sun and Earth position at each site every hour of 2027; the Moon's elevation at the Goldstone, Madrid and Canberra Deep Space Network dishes.</li>
          <li><a href="https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/">LRO LOLA polar elevation models</a> (20 m, 30 m and 120 m): terrain heights, slopes and horizons.</li>
          <li><a href="https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/">NASA's nine Artemis III candidate regions</a> (Oct 2024), with 77 published landing points inside them (JGR Planets 2025, doi:10.1029/2025JE009434). We keep the best-lit point per region.</li>
          <li><a href="https://pgda.gsfc.nasa.gov/products/69">LOLA illumination maps</a> (NASA Goddard) and the IM-1 and IM-2 landing records, for validation.</li>
          <li><a href="https://trek.nasa.gov/moon/">NASA Moon Trek</a>: the LROC NAC south-pole mosaic (LRO_NAC_AvgMosaic_SPole855_1mp) draped on the 3D terrain and the rover shadow map, and the LROC WAC global mosaic on the globe. Sites beyond the NAC mosaic (about 85.5° S) are filled with LOLA 20 m relief.</li>
          <li>Hayne et al. 2017 (JGR Planets 122, 2371) regolith properties, fitted to LRO Diviner, for surface temperature.</li>
        </ul>
      </Panel>

      <Panel title="How it's computed">
        <h3>Terrain horizon</h3>
        <p>From each point we walk outward in 720 directions to 150 km: on the 20 m elevation map within 15 km (where small bumps matter), on the
          120 m map beyond. Distant ground drops below a straight line of sight by d²/2R (29 m at 10 km, 720 m at 50 km), so lunar curvature is included.
          The highest angle found in each direction is the horizon there. The observer is a 2 m mast.</p>
        <h3>Sunlight and Earth contact</h3>
        <p>The Sun is a disk 0.53° wide, so we compute the fraction of it above the horizon, not just up or down. An hour counts as sunlit when at
          least half the disk is visible. Earth is in view when its centre is above the horizon; a Deep Space Network dish is available when the Moon is
          at least 10° above that dish's horizon (98% of 2027).</p>
        <h3>Usable days and landing windows</h3>
        <p>A usable day has at least 12 sunlit hours and 4 hours of Earth contact. Every landing time in 2027 (every 6 hours) is scored for a 10-day
          mission; it is survivable if no dark spell exceeds 18 hours. These are placeholder criteria from the project brief until the engineering
          lead's values are committed.</p>
        <h3>Shadow grids and rover routes</h3>
        <p>Around each site, a 5.1 km area of 80 m cells gets its own horizons per cell, and sunlight hour by hour for 14 days. The rover model counts
          solar input, avionics, survival heaters and drive power from slope and rolling resistance. The shortest route ignores the Sun. Sunchaser
          searches over position, time and battery together (space-time A* with dominance pruning), may wait in sunlight, and never lets the battery
          fall below a 15% reserve. Each route is replayed 500 times with battery, panel output and power draw varied by ±10% and departure delayed
          0-2 hours; survival probability is the share that never froze, on the way or in 24 hours parked at the target.</p>
        <h3>Surface temperature</h3>
        <p>A 1D heat model of the top half-metre of soil on each site's own slope. On a lunar equator day it gives 385 K at noon and 92 K before dawn;
          LRO Diviner measured about 390 K and 95 K.</p>
      </Panel>

      <Panel title="Validation" sub="Our 18.6-year average versus NASA's published LOLA illumination maps: share of time any part of the Sun (or Earth) is above the terrain">
        <div className="tiles">
          <div className="tile"><div className="tile-value">{s.sun_correlation.toFixed(3)}</div><div className="tile-label">correlation with NASA, Sun</div></div>
          <div className="tile"><div className="tile-value">{s.earth_correlation.toFixed(3)}</div><div className="tile-label">correlation with NASA, Earth</div></div>
          <div className="tile"><div className="tile-value">{s.sun_mean_abs_diff_pts.toFixed(1)}<span className="tile-unit">pts</span></div><div className="tile-label">mean difference, Sun</div></div>
        </div>
        <div className="scroll-x"><table>
          <thead><tr><th>Site</th><th className="num">Sun: ours</th><th className="num">Sun: NASA</th><th className="num">Earth: ours</th><th className="num">Earth: NASA</th></tr></thead>
          <tbody>{v.maps.sites.map(r => <tr key={r.name}><td>{r.name}</td><td className="num">{(100 * r.sun_any).toFixed(1)}%</td><td className="num">{(100 * r.nasa_sun).toFixed(1)}%</td>
            <td className="num">{(100 * r.earth_any).toFixed(1)}%</td><td className="num">{(100 * r.nasa_earth).toFixed(1)}%</td></tr>)}</tbody>
        </table></div>
        <p>Ours runs {s.sun_mean_diff_pts.toFixed(1)} points higher for the Sun on average. With the observer on the ground instead of a 2 m mast it runs
          {' '}{Math.abs(s.sun_mean_diff_no_mast_pts).toFixed(1)} points lower: NASA's map sits between the two, because a couple of metres matter when the Sun is this low.</p>
        <p><b>Real landings.</b> At the IM-1 (Feb 2024) and IM-2 (Mar 2025) sites and times, the model shows the Sun up and Earth in view, as both landers
          needed to communicate. One honest mismatch: IM-1 shut down on 29 February with the Sun still about 5° up, 2.5 days before our terrain sunset;
          the lander had come to rest tilted on its side.</p>
      </Panel>

      <Panel title="Limits">
        <ul>
          <li>Rover specifications and mission criteria are placeholders from the project brief until sourced values are committed.</li>
          <li>Terrain features smaller than 20 m near a site (80 m in the grids) are not seen; IM-2 came to rest in a 20 m crater no orbital map resolves.</li>
          <li>The rover model has no wheel slip, an on/off heater, and no radio power while driving. Everything is computed for 2027.</li>
          <li>Surface temperatures ignore heat from surrounding terrain, so shadowed hours read too cold.</li>
        </ul>
      </Panel>

      <Panel title="How we used AI">
        <p>We used AI coding assistants to help write, test and document the code, from our own design, physics references and data contract; results
          were checked against hand-worked cases, NASA's maps and real landings. The copilot uses Google Gemini (free tier) to choose which data tool to call and
          to phrase the answer, but any answer containing a number that is not in the computed data is rejected, and a rule-based fact finder with no
          AI answers when no model is available.</p>
      </Panel>

      <Panel title="Team Zenon">
        <p>Baldwin (data, AI and tech lead) · Harril (robotics lead) · Dhiran (engineering and business lead). NASA Space Apps Challenge 2026, Lunar Landing Site Navigator.
          Code: <a href="https://github.com/Baldwi242alt/zenon">github.com/Baldwi242alt/zenon</a>.</p>
      </Panel>
    </div>
  )
}
