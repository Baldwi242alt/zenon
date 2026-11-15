import { LineChart } from './ui'
import { fmtMoney, fmtTime } from '../data'
import type { Windows } from '../types'

// Cost of a launch slip: if landing slips by 0-7 days from a chosen time, how many usable days
// remain, and what does each usable day then cost? cost per usable day = budget / usable days.
export function slipRows(win: Windows, landing: string) {
  const i0 = win.rows.findIndex(r => r.landing === landing)
  if (i0 < 0) return []
  const perDay = Math.round(24 / win.step_h)
  const out = []
  for (let k = 0; k <= 7 * perDay && i0 + k < win.rows.length; k++) {
    const r = win.rows[i0 + k]
    out.push({ slip_h: k * win.step_h, ...r })
  }
  return out
}

export function SlipChart({ win, landing, budget }: { win: Windows; landing: string; budget: number }) {
  const rows = slipRows(win, landing)
  if (!rows.length) return null
  const days = (h: number) => `+${(h / 24).toFixed(h % 24 ? 1 : 0)} d`
  const base = rows[0]
  const at = (d: number) => rows.find(r => r.slip_h === d * 24)
  const two = at(2)
  return (
    <div>
      {budget > 0 ? (
        <LineChart height={200} xFmt={days} yFmt={y => fmtMoney(y)} legend={false} series={[{
          name: 'cost per usable day', color: 'var(--sun)', width: 2.4,
          points: rows.filter(r => r.usable_days > 0).map(r => [r.slip_h, budget / r.usable_days]),
        }]} />
      ) : (
        <LineChart height={200} xFmt={days} yFmt={y => y.toFixed(0)} legend={false} yMin={0} yMax={win.mission_days} series={[{
          name: 'usable days', color: 'var(--both)', width: 2.4, points: rows.map(r => [r.slip_h, r.usable_days]),
        }]} />
      )}
      <p className="note">
        From {fmtTime(landing)}: {base.usable_days} usable days{budget > 0 && base.usable_days > 0 && ` (${fmtMoney(budget / base.usable_days)} per usable day)`}.
        {two && <> A 2-day slip leaves {two.usable_days}{budget > 0 && two.usable_days > 0 && ` (${fmtMoney(budget / two.usable_days)} per usable day)`}{!two.survives && ', and that landing is not survivable'}.</>}
        {budget === 0 && ' Enter a mission budget on the Business screen to see this in money.'}
        {rows.some(r => r.usable_days === 0) && ' Gaps: slips that leave no usable day at all.'}
      </p>
    </div>
  )
}
