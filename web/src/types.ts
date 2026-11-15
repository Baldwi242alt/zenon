// Types for every shared file (CLAUDE.md Section 2). One owner per file; the web app only reads.

export interface Site {
  id: string; name: string; lat: number; lon: number; elevation_m: number; source: string; notes: string
}

export interface TimelineRow {
  time: string
  sun_elev_deg: number; sun_az_deg: number; sun_horizon_deg: number; sun_frac: number
  earth_elev_deg: number; earth_az_deg: number; earth_horizon_deg: number; earth_visible: boolean
  dsn_station: 'Goldstone' | 'Madrid' | 'Canberra' | null
  surface_temp_k: number | null
}
export interface Timeline { site: string; start: string; step_h: number; rows: TimelineRow[] }

export interface Grid {
  site: string; window_start: string; step_h: number; n_steps: number; rows: number; cols: number
  cell_size_m: number; center: { lat: number; lon: number }; orientation_note: string
  elevation_m: number[][]; slope_deg: number[][]; sun_pct: number[][][]
}

export interface WindowRow {
  landing: string; usable_days: number; sun_hours: number; contact_hours: number; both_hours: number
  longest_dark_h: number; survives: boolean
}
export interface Windows { site: string; mission_days: number; step_h: number; rows: WindowRow[] }

export interface ScoreRow {
  site: string; rank: number; usable_days: number; sun_hours: number; contact_hours: number; both_hours: number
  longest_dark_h: number; survives: boolean; best_landing: string; brief: string
}
export interface Scores { generated: string; window_start: string; window_end: string; sites: ScoreRow[] }

export interface RouteStep {
  t_h: number; row: number; col: number; action: 'start' | 'move' | 'wait'; sun_pct: number
  power_in_w: number; power_out_w: number; battery_wh: number
}
export interface Route {
  name: 'shortest' | 'sunchaser_fast' | 'sunchaser_safe'; label: string; survived: boolean
  frozen_at_index: number | null; distance_m: number; duration_h: number; energy_used_wh: number
  min_battery_pct: number; survival_probability: number; steps: RouteStep[]
}
export interface RouteFile {
  site: string; start: { row: number; col: number }; target: { row: number; col: number }
  depart_step: number; monte_carlo_runs: number; routes: Route[]
  pareto?: { reserve_pct: number; duration_h: number; survival_probability: number }[]
}

export interface Rover {
  name: string; mass_kg: number
  panel: { area_m2: number; efficiency: number; mount: string }
  battery: { capacity_wh: number; min_soc: number; charge_efficiency: number }
  power_w: { avionics: number; comms_active: number; heater_dark: number; heater_lit: number }
  drive: { speed_m_per_h: number; base_drive_w: number; rolling_resistance: number; drivetrain_efficiency: number; max_slope_deg: number }
  comms: { dte_rate_kbps: number }
  uncertainty_pct: { battery_capacity: number; panel_output: number; power_draw: number }
  sources: string
}
export interface Criteria {
  mission_length_days: number; usable_day: { min_sun_hours: number; min_contact_hours: number }
  max_dark_spell_hours: number; min_battery_reserve_pct: number; min_survival_probability: number
}

export interface Fact { label: string; value: string }
export interface CopilotReply { answer: string; facts_used: Fact[] }
