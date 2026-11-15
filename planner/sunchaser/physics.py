import math

def panel_peak_w(rover):
    """Calculates the absolute maximum power the solar panel can generate (in Watts)."""
    # 1361 W/m^2 is the solar constant at the Moon
    return 1361.0 * rover["panel"]["area_m2"] * rover["panel"]["efficiency"]

def power_in_w(rover, sun_pct):
    """Calculates current solar power generation based on sun percentage (0-100)."""
    peak = panel_peak_w(rover)
    return peak * (sun_pct / 100.0)

def heater_w(rover, sun_pct):
    """Calculates heater power. If sun < 5%, it's dark and cold, so heaters turn on."""
    if sun_pct < 5:
        return rover["power_w"]["heater_dark"]
    else:
        return rover["power_w"]["heater_lit"]

def drive_w(rover, elev_here, elev_next, horizontal_m):
    """Calculates power needed to drive. Includes slope and rolling resistance."""
    if horizontal_m == 0:
        return 0.0
        
    v = rover["drive"]["speed_m_per_h"] / 3600.0  # speed in m/s
    mass = rover["mass_kg"]
    g = 1.62  # lunar gravity m/s^2
    
    # Calculate slope angle in radians
    theta = math.atan((elev_next - elev_here) / horizontal_m)
    
    # Mechanical power = mass * gravity * velocity * (rolling_resistance * cos(theta) + sin(theta))
    rr = rover["drive"]["rolling_resistance"]
    mech_w = mass * g * v * (rr * math.cos(theta) + math.sin(theta))
    
    # No energy recovered downhill (max 0)
    mech_w = max(0.0, mech_w)
    
    # Add base drive power and divide by drivetrain efficiency
    total_drive_w = rover["drive"]["base_drive_w"] + (mech_w / rover["drive"]["drivetrain_efficiency"])
    return total_drive_w

def battery_step(rover, energy_wh, power_in, power_out, dt_h):
    """Updates the battery energy based on net power over a time step (dt_h)."""
    capacity = rover["battery"]["capacity_wh"]
    eff = rover["battery"]["charge_efficiency"]
    
    net_power = power_in - power_out
    
    if net_power > 0:
        # Charging (apply efficiency)
        energy_wh += net_power * eff * dt_h
    else:
        # Discharging
        energy_wh += net_power * dt_h
        
    # Battery cannot exceed capacity
    energy_wh = min(energy_wh, capacity)
    
    # Check if dead
    frozen = energy_wh <= 0
    
    # Check if below minimum safe reserve (15% by default)
    reserve = rover["battery"]["min_soc"] * capacity
    reserve_breached = energy_wh < reserve
    
    return energy_wh, frozen, reserve_breached
