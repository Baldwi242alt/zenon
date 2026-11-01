import math
from . import physics

def simulate_route(rover, grid, depart_step, path):
    """
    Simulates a rover driving along a path.
    path: list of (row, col) tuples.
    """
    cell_size = grid["cell_size_m"]
    capacity = rover["battery"]["capacity_wh"]
    speed = rover["drive"]["speed_m_per_h"]
    max_slope = rover["drive"]["max_slope_deg"]
    
    # Start with full battery
    current_energy = capacity 
    total_time_h = 0.0
    total_distance_m = 0.0
    
    steps_log = []
    frozen_at_index = None
    min_battery = capacity
    
    # Log the starting position
    r_start, c_start = path[0]
    sun_start = grid["sun_pct"][depart_step][r_start][c_start]
    steps_log.append({
        "t_h": 0.0, "row": r_start, "col": c_start, "action": "start", 
        "sun_pct": sun_start, "power_in_w": physics.power_in_w(rover, sun_start), 
        "power_out_w": physics.power_out_w(rover, sun_start), 
        "battery_wh": current_energy
    })

    # Loop through the path (from step 1 because we already logged step 0)
    for i in range(1, len(path)):
        r_prev, c_prev = path[i-1]
        r_curr, c_curr = path[i]
        
        # Calculate distance (side or diagonal)
        dr = abs(r_curr - r_prev)
        dc = abs(c_curr - c_prev)
        if dr > 0 and dc > 0:
            dist_m = cell_size * math.sqrt(2)
        else:
            dist_m = cell_size
            
        total_distance_m += dist_m
        
        # Calculate how long this move takes
        move_time_h = dist_m / speed
        
        # We simulate in sub-steps (max 0.25h) so we don't miss shadows moving
        steps_needed = math.ceil(move_time_h / 0.25)
        dt = move_time_h / steps_needed
        
        for _ in range(steps_needed):
            total_time_h += dt
            
            # What hour is it in the grid? (limit to max steps)
            current_step = min(int(depart_step + total_time_h), grid["n_steps"] - 1)
            
            # Get sun level
            sun_pct = grid["sun_pct"][current_step][r_curr][c_curr]
            
            # Calculate power
            p_in = physics.power_in_w(rover, sun_pct)
            
            # If driving, add drive power
            elev_here = grid["elevation_m"][r_prev][c_prev]
            elev_next = grid["elevation_m"][r_curr][c_curr]
            p_drive = physics.drive_w(rover, elev_here, elev_next, dist_m)
            
            heater = physics.heater_w(rover, sun_pct)
            p_out = rover["power_w"]["avionics"] + heater + p_drive
            
            # Update battery
            new_energy, frozen, reserve_breached = physics.battery_step(rover, current_energy, p_in, p_out, dt)
            current_energy = new_energy
            min_battery = min(min_battery, current_energy)
            
            if frozen:
                frozen_at_index = len(steps_log)
                break # Rover dies
                
        # Log the end of this move
        steps_log.append({
            "t_h": round(total_time_h, 2), "row": r_curr, "col": c_curr, "action": "move", 
            "sun_pct": sun_pct, "power_in_w": round(p_in, 1), "power_out_w": round(p_out, 1), 
            "battery_wh": round(current_energy, 1)
        })
        
        if frozen_at_index is not None:
            break # Stop simulating if dead

    return {
        "survived": frozen_at_index is None,
        "frozen_at_index": frozen_at_index,
        "distance_m": round(total_distance_m, 1),
        "duration_h": round(total_time_h, 2),
        "energy_used_wh": round(capacity - current_energy, 1),
        "min_battery_pct": round((min_battery / capacity) * 100, 1),
        "steps": steps_log
    }