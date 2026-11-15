// Loading the shared files: fetch once, cache, and report loading / missing / ready.
import { useEffect, useState } from 'react'
import type { Criteria, Rover } from './types'

const cache = new Map<string, Promise<unknown>>()

export function fetchJson<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    const p = fetch(`/${name}`).then(r => {
      if (!r.ok) throw new Error(`${name}: ${r.status}`)
      return r.json()
    })
    p.catch(() => cache.delete(name))
    cache.set(name, p)
  }
  return cache.get(name) as Promise<T>
}

export type Loaded<T> = { state: 'loading' } | { state: 'missing'; error: string } | { state: 'ready'; data: T }

export function useJson<T>(name: string | null): Loaded<T> {
  const [res, setRes] = useState<Loaded<T>>({ state: 'loading' })
  useEffect(() => {
    if (!name) return
    let alive = true
    setRes({ state: 'loading' })
    fetchJson<T>(name)
      .then(data => alive && setRes({ state: 'ready', data }))
      .catch(e => alive && setRes({ state: 'missing', error: String(e) }))
    return () => { alive = false }
  }, [name])
  return res
}

// Rover and criteria belong to the engineering lead. Until shared/rover.json and
// shared/criteria.json exist, the example values from CLAUDE.md 2.6 / 2.7 are used, and every
// screen that relies on them says so.
export const PLACEHOLDER_ROVER: Rover = {
  name: 'Sunchaser reference rover', mass_kg: 120,
  panel: { area_m2: 0.6, efficiency: 0.3, mount: 'vertical_sun_tracking' },
  battery: { capacity_wh: 2000, min_soc: 0.15, charge_efficiency: 0.95 },
  power_w: { avionics: 30, comms_active: 25, heater_dark: 60, heater_lit: 0 },
  drive: { speed_m_per_h: 200, base_drive_w: 40, rolling_resistance: 0.15, drivetrain_efficiency: 0.5, max_slope_deg: 15 },
  comms: { dte_rate_kbps: 100 },
  uncertainty_pct: { battery_capacity: 10, panel_output: 10, power_draw: 10 },
  sources: 'CLAUDE.md 2.6 example values (placeholder)',
}
export const PLACEHOLDER_CRITERIA: Criteria = {
  mission_length_days: 10, usable_day: { min_sun_hours: 12, min_contact_hours: 4 },
  max_dark_spell_hours: 18, min_battery_reserve_pct: 15, min_survival_probability: 0.95,
}

export function useRover(): { rover: Rover; placeholder: boolean } {
  const r = useJson<Rover>('rover.json')
  return r.state === 'ready' ? { rover: r.data, placeholder: false } : { rover: PLACEHOLDER_ROVER, placeholder: true }
}
export function useCriteria(): { criteria: Criteria; placeholder: boolean } {
  const r = useJson<Criteria>('criteria.json')
  return r.state === 'ready' ? { criteria: r.data, placeholder: false } : { criteria: PLACEHOLDER_CRITERIA, placeholder: true }
}

// ---------- formatting ----------
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export function fmtTime(iso: string): string {
  const d = new Date(iso.replace('Z', ':00Z'))
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2, '0')}:00 UTC`
}
export function fmtDate(iso: string): string {
  const d = new Date(iso.replace('Z', ':00Z'))
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
}
export const pct = (x: number, d = 0) => `${(100 * x).toFixed(d)}%`
export const fmtNum = (x: number, d = 0) => x.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })
export function fmtMoney(x: number): string {
  if (x >= 1e9) return `${(x / 1e9).toFixed(2)} bn`
  if (x >= 1e6) return `${(x / 1e6).toFixed(2)} M`
  if (x >= 1e3) return `${(x / 1e3).toFixed(1)} k`
  return x.toFixed(0)
}

// Longest run of true values.
export function longestRun(flags: boolean[]): number {
  let best = 0, cur = 0
  for (const f of flags) { cur = f ? cur + 1 : 0; if (cur > best) best = cur }
  return best
}
