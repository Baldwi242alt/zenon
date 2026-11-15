import { useEffect, useState } from 'react'
import { SlipChart } from '../components/Slip'
import { Panel, Placeholder, Status, Tile } from '../components/ui'
import { fetchJson, fmtMoney, fmtTime, useJson, useRover } from '../data'
import { useStore } from '../store'
import type { Scores, Site, Timeline, Windows } from '../types'

// Business case: for a given budget, which site and landing give the most for the money?
// We never invent prices: the user enters their own mission budget.
export default function Business() {
  const sites = useJson<Site[]>('sites.json')
  const scores = useJson<Scores>('scores.json')
  return (
    <Status res={sites} what="sites">{s => <Status res={scores} what="scores">{sc => <Screen sites={s} scores={sc} />}</Status>}</Status>
  )
}

function Screen({ sites, scores }: { sites: Site[]; scores: Scores }) {
  const { budget, setBudget, site, setSite } = useStore()
  const { rover, placeholder } = useRover()
  const [input, setInput] = useState(budget ? String(budget / 1e6) : '')
  const [win, setWin] = useState<Record<string, Windows>>({})
  const [contact, setContact] = useState<Record<string, number>>({})
  useEffect(() => {
    sites.forEach(s => fetchJson<Windows>(`windows_${s.id}.json`).then(w => setWin(m => ({ ...m, [s.id]: w }))))
  }, [sites])
  useEffect(() => {
    // Earth-contact hours during each site's best 10-day mission (from the timeline).
    scores.sites.forEach(r => fetchJson<Timeline>(`timeline_${r.site}.json`).then(t => {
      const i = t.rows.findIndex(x => x.time === r.best_landing)
      const h = t.rows.slice(i, i + 240).filter(x => x.earth_visible && x.dsn_station).length
      setContact(m => ({ ...m, [r.site]: h }))
    }))
  }, [scores])

  const name = (id: string) => sites.find(s => s.id === id)!.name
  const gb = (hours: number) => (rover.comms.dte_rate_kbps * 1000 * 3600 * hours) / 8 / 1e9
  const ok = scores.sites.filter(r => r.survives && r.usable_days > 0)
  const best = ok[0], worst = ok[ok.length - 1]
  const ratio = best && worst ? best.usable_days / worst.usable_days : 1
  const month = new Date(scores.window_start).toLocaleString('en', { month: 'long', timeZone: 'UTC' })

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Business case</h2>
          <p>Surface days are the most expensive days of a mission. For the same budget, the right site and landing time buy more of them.</p>
        </div>
        <div className="controls">
          <label className="note" htmlFor="budget">Mission budget, millions (your currency)</label>
          <input id="budget" className="input mono" inputMode="decimal" placeholder="e.g. 50" value={input} style={{ width: 110 }}
                 onChange={e => { setInput(e.target.value); const v = parseFloat(e.target.value); setBudget(v > 0 ? v * 1e6 : 0) }} />
        </div>
      </div>
      <Placeholder show={placeholder} what={`rover radio rate (${rover.comms.dte_rate_kbps} kbps) and mission criteria`} />

      <div className="hero" style={{ padding: '18px 22px' }}>
        <div className="eyebrow">{month} 2027 · 10-day mission</div>
        <h1 style={{ fontSize: 28 }}>
          {best && worst && best !== worst
            ? `Landing at ${name(best.site)} instead of ${name(worst.site)} gives ${ratio.toFixed(1)}× the usable days for the same budget.`
            : 'Compare sites by what each surface day costs.'}
        </h1>
        <div className="kpi-row">
          <Tile label={`best site: ${name(best.site)}`} value={`${best.usable_days}`} unit="usable days" tone="both" />
          <Tile label="cost per usable day there" value={budget ? fmtMoney(budget / best.usable_days) : 'enter budget'} tone="sun" />
          <Tile label="best landing" value={fmtTime(best.best_landing)} />
        </div>
        <div className="brief">{best.brief}</div>
      </div>

      <Panel title="Every site, its best landing this month" sub="Data returned = hours with Earth in view and a Deep Space Network dish available × the rover's radio rate">
        <div className="scroll-x">
          <table>
            <thead><tr><th>#</th><th>Site</th><th>Best landing</th><th className="num">Usable days</th><th className="num">Longest dark</th>
              <th>Survives</th><th className="num">Cost per usable day</th><th className="num">Data returned</th></tr></thead>
            <tbody>
              {scores.sites.map(r => (
                <tr key={r.site} className={`clickable ${r.site === site ? 'selected' : ''}`} onClick={() => setSite(r.site)}>
                  <td className="num">{r.rank}</td><td>{name(r.site)}</td><td className="mono">{fmtTime(r.best_landing)}</td>
                  <td className="num">{r.usable_days}</td><td className="num">{r.longest_dark_h} h</td>
                  <td><span className={`pill ${r.survives ? 'ok' : 'bad'}`}>{r.survives ? 'yes' : 'no'}</span></td>
                  <td className="num">{budget && r.usable_days ? fmtMoney(budget / r.usable_days) : r.usable_days ? '—' : 'no usable days'}</td>
                  <td className="num">{contact[r.site] !== undefined ? `${gb(contact[r.site]).toFixed(1)} GB` : '…'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title={`What a launch slip costs at ${name(site)}`} sub="From this site's best landing this month, if landing slips by up to 7 days">
        {win[site] ? <SlipChart win={win[site]} landing={scores.sites.find(r => r.site === site)!.best_landing} budget={budget} />
                   : <div className="status"><span className="spinner" /> Loading…</div>}
      </Panel>
    </>
  )
}
