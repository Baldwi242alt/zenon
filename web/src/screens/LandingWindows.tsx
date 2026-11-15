import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SlipChart } from '../components/Slip'
import { Panel, Placeholder, Status } from '../components/ui'
import { fetchJson, fmtTime, useCriteria, useJson } from '../data'
import { useStore } from '../store'
import type { Site, WindowRow, Windows } from '../types'

// Every landing time in 2027 (every 6 hours), every site: how many usable days does a mission get?
export default function LandingWindows() {
  const sites = useJson<Site[]>('sites.json')
  const [all, setAll] = useState<Windows[] | null>(null)
  useEffect(() => {
    if (sites.state !== 'ready') return
    Promise.all(sites.data.map(s => fetchJson<Windows>(`windows_${s.id}.json`))).then(setAll).catch(() => setAll([]))
  }, [sites])
  return (
    <Status res={sites} what="sites">{s => all === null
      ? <div className="status"><span className="spinner" /> Loading a year of landing windows…</div>
      : <Screen sites={s} all={all} />}</Status>
  )
}

const COL = (t: number) => {          // 0..1 -> dark navy to bright amber
  const stops = [[17, 24, 39], [58, 42, 14], [138, 90, 16], [245, 166, 35], [255, 226, 168]]
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x)), f = x - i
  const c = stops[i].map((v, k) => Math.round(v + (stops[i + 1][k] - v) * f))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

function Screen({ sites, all }: { sites: Site[]; all: Windows[] }) {
  const { setSite, setMonth, budget } = useStore()
  const { placeholder } = useCriteria()
  const nav = useNavigate()
  const ref = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null)
  const [pick, setPick] = useState<{ s: number; i: number } | null>(null)
  const cols = all[0].rows.length, rowH = 30
  const md = all[0].mission_days

  useEffect(() => {
    const c = ref.current!
    c.width = cols; c.height = all.length * rowH
    const g = c.getContext('2d')!
    all.forEach((w, s) => w.rows.forEach((r, i) => {
      g.fillStyle = COL(r.usable_days / md)
      g.fillRect(i, s * rowH, 1, rowH - 4)
      if (!r.survives) { g.fillStyle = 'rgba(255,93,93,0.85)'; g.fillRect(i, s * rowH + rowH - 9, 1, 4) }
    }))
    for (let m = 1; m < 12; m++) {          // month separators
      const i = all[0].rows.findIndex(r => r.landing.startsWith(`2027-${String(m + 1).padStart(2, '0')}`))
      g.fillStyle = 'rgba(11,15,23,0.9)'; g.fillRect(i, 0, 2, c.height)
    }
  }, [all, cols, md])

  const best = useMemo(() => {
    const cand: { s: number; i: number; r: WindowRow }[] = []
    all.forEach((w, s) => w.rows.forEach((r, i) => r.survives && cand.push({ s, i, r })))
    cand.sort((a, b) => b.r.usable_days - a.r.usable_days || a.r.longest_dark_h - b.r.longest_dark_h || b.r.contact_hours - a.r.contact_hours)
    const out: typeof cand = []
    for (const c of cand) { if (!out.some(o => o.s === c.s)) out.push(c); if (out.length === 3) break }
    return out
  }, [all])

  const locate = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const i = Math.floor(((e.clientX - r.left) / r.width) * cols), s = Math.floor(((e.clientY - r.top) / r.height) * all.length)
    return i >= 0 && i < cols && s >= 0 && s < all.length ? { s, i } : null
  }
  const h = hover ?? pick
  const hr = h ? all[h.s].rows[h.i] : null
  const name = (s: number) => sites.find(x => x.id === all[s].site)!.name
  const survivable = (w: Windows) => (100 * w.rows.filter(r => r.survives).length) / w.rows.length

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Landing windows, all of 2027</h2>
          <p>Each column is a landing time (every 6 hours); brightness is how many of the {md} mission days are usable. A red tick means the
            mission meets a dark spell longer than the rover can survive. Click a cell to see what a launch slip would cost.</p>
        </div>
      </div>
      <Placeholder show={placeholder} what="mission criteria (10-day mission, 12 sun hours and 4 contact hours per usable day, 18-hour dark limit)" />
      <Panel title="When you land matters as much as where"
             sub={`Survivable landing times per site: ${all.map(w => `${name(all.indexOf(w))} ${survivable(w).toFixed(0)}%`).join(' · ')}`}>
        <div className="heat-rows heat">
          <div className="heat-names">{all.map((w, s) => <div key={w.site}>{name(s)}</div>)}</div>
          <div>
            <canvas ref={ref} style={{ height: all.length * rowH }} onMouseMove={e => setHover(locate(e))} onMouseLeave={() => setHover(null)}
                    onClick={e => { const p = locate(e); if (p) setPick(p) }} />
            <div className="band-axis">{['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map(m => <span key={m}>{m}</span>)}</div>
          </div>
        </div>
        <div className="scale"><span>0 usable days</span><span className="ramp" /><span>{md} usable days</span>
          <span style={{ marginLeft: 16 }}><i style={{ display: 'inline-block', width: 14, height: 4, background: 'var(--danger)', verticalAlign: 'middle' }} /> not survivable</span></div>
        <p className="note mono">{hr && h ? `${name(h.s)} · land ${fmtTime(hr.landing)} · ${hr.usable_days} usable days · ${hr.sun_hours} h sun · ${hr.contact_hours} h Earth contact · longest dark ${hr.longest_dark_h} h · ${hr.survives ? 'survivable' : 'NOT survivable'}` : 'Hover the heatmap for details.'}</p>
      </Panel>

      <div className="grid2">
        <Panel title="Best landing windows of the year" sub="Survivable, most usable days, shortest dark spell; one per site">
          <div className="callouts">
            {best.map(b => (
              <button key={b.s} className="route-card" style={{ textAlign: 'left', cursor: 'pointer', color: 'inherit', font: 'inherit' }}
                      onClick={() => setPick({ s: b.s, i: b.i })}>
                <h4>{name(b.s)}</h4>
                <div className="mono">{fmtTime(b.r.landing)}</div>
                <div className="note">{b.r.usable_days} usable days · longest dark {b.r.longest_dark_h} h · {b.r.contact_hours} h contact</div>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Cost of a launch slip"
               sub={pick ? `${name(pick.s)}, landing ${fmtTime(all[pick.s].rows[pick.i].landing)}` : 'Click a cell or a best window'}
               right={pick && <button className="btn" onClick={() => { setSite(all[pick.s].site); setMonth(+all[pick.s].rows[pick.i].landing.slice(5, 7) - 1); nav('/light') }}>See light &amp; comms →</button>}>
          {pick ? <SlipChart win={all[pick.s]} landing={all[pick.s].rows[pick.i].landing} budget={budget} />
                : <div className="status">Pick a landing time to see how usable days, and cost per usable day, change if it slips 0-7 days.</div>}
        </Panel>
      </div>
    </>
  )
}
