import json
import math
import os

def generate_fake_world():
    print("Generating fake lunar grid...")
    
    # 1. Grid Settings
    rows = 40
    cols = 40
    cell_size = 40.0 # meters
    base_elev = 1800.0 # meters
    n_steps = 72 # hourly steps
    
    # 2. Build Terrain (Elevation)
    elevation = [[base_elev for _ in range(cols)] for _ in range(rows)]
    
    for r in range(rows):
        for c in range(cols):
            # Hill 1
            elevation[r][c] += 150.0 * math.exp(-(((r-10)**2)/(2*5**2) + ((c-10)**2)/(2*5**2)))
            # Hill 2
            elevation[r][c] += 200.0 * math.exp(-(((r-30)**2)/(2*6**2) + ((c-30)**2)/(2*6**2)))
            # Hill 3
            elevation[r][c] += 100.0 * math.exp(-(((r-15)**2)/(2*4**2) + ((c-35)**2)/(2*4**2)))
            
    # Steep ridge with a gap
    for r in range(rows):
        if 10 < c < 30:
            if r < 15 or r > 25:
                elevation[r][30] += 300.0

    elevation = [[round(e, 1) for e in row] for row in elevation]

    # 3. Calculate Slope
    slope_deg = [[0.0 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            r_up = max(0, r-1)
            r_dn = min(rows-1, r+1)
            c_lf = max(0, c-1)
            c_rt = min(cols-1, c+1)
            
            dz_dr = (elevation[r_dn][c] - elevation[r_up][c]) / (2 * cell_size)
            dz_dc = (elevation[r][c_rt] - elevation[r][c_lf]) / (2 * cell_size)
            
            slope_rad = math.atan(math.sqrt(dz_dr**2 + dz_dc**2))
            slope_deg[r][c] = round(math.degrees(slope_rad), 2)

    # 4. Calculate Sun Shadows
    sun_pct = []
    sun_elev = 1.0
    
    for step in range(n_steps):
        sun_az = (step * 0.5) % 360.0 
        step_shadows = [[100 for _ in range(cols)] for _ in range(rows)]
        
        az_rad = math.radians(sun_az)
        dx = math.sin(az_rad)
        dy = -math.cos(az_rad) 
        
        for r in range(rows):
            for c in range(cols):
                current_elev = elevation[r][c]
                for dist in range(1, 50):
                    check_r = int(r + dy * dist)
                    check_c = int(c + dx * dist)
                    if check_r < 0 or check_r >= rows or check_c < 0 or check_c >= cols:
                        break 
                    dist_m = dist * cell_size
                    terrain_rise = elevation[check_r][check_c] - current_elev
                    terrain_angle = math.degrees(math.atan(terrain_rise / dist_m))
                    if terrain_angle > sun_elev:
                        step_shadows[r][c] = 0
                        break
        sun_pct.append(step_shadows)

    # 5. Write Grid JSON
    grid_data = {
        "site": "site_fake",
        "window_start": "2027-01-01T00:00Z",
        "step_h": 1,
        "n_steps": n_steps,
        "rows": rows,
        "cols": cols,
        "cell_size_m": cell_size,
        "center": {"lat": -89.45, "lon": 137.3},
        "orientation_note": "Fake grid.",
        "elevation_m": elevation,
        "slope_deg": slope_deg,
        "sun_pct": sun_pct
    }
    
    # Save inside the fake folder
    grid_path = os.path.join(os.path.dirname(__file__), "grid_fake.json")
    with open(grid_path, "w") as f:
        json.dump(grid_data, f, indent=2)

    # 6. Write Rover JSON
    rover_data = {
      "name": "Sunchaser reference rover",
      "mass_kg": 120,
      "panel": {"area_m2": 0.6, "efficiency": 0.30, "mount": "vertical_sun_tracking"},
      "battery": {"capacity_wh": 2000, "min_soc": 0.15, "charge_efficiency": 0.95},
      "power_w": {"avionics": 30, "comms_active": 25, "heater_dark": 60, "heater_lit": 0},
      "drive": {
        "speed_m_per_h": 200,
        "base_drive_w": 40,
        "rolling_resistance": 0.15,
        "drivetrain_efficiency": 0.5,
        "max_slope_deg": 15
      },
      "comms": {"dte_rate_kbps": 100},
      "uncertainty_pct": {"battery_capacity": 10, "panel_output": 10, "power_draw": 10},
      "sources": "web/SOURCES.md"
    }
    
    rover_path = os.path.join(os.path.dirname(__file__), "rover_fake.json")
    with open(rover_path, "w") as f:
        json.dump(rover_data, f, indent=2)

    print("✅ Success! Created grid_fake.json and rover_fake.json inside planner/fake/")

if __name__ == "__main__":
    generate_fake_world()