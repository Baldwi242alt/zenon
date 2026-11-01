import heapq
import math
from . import physics

def astar_spacetime(grid, rover, start, target, depart_step):
    """
    Space-Time A*: Finds a route that minimizes time, but NEVER drops below the battery reserve.
    It can move in 8 directions, or WAIT 1 hour to charge.
    """
    rows = grid["rows"]
    cols = grid["cols"]
    cell_size = grid["cell_size_m"]
    max_slope = rover["drive"]["max_slope_deg"]
    speed = rover["drive"]["speed_m_per_h"]
    
    capacity = rover["battery"]["capacity_wh"]
    reserve = rover["battery"]["min_soc"] * capacity

    def get_neighbors(r, c):
        dirs = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]
        neighbors = []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid["slope_deg"][nr][nc] <= max_slope:
                    dist = cell_size * math.sqrt(2) if (dr != 0 and dc != 0) else cell_size
                    neighbors.append(((nr, nc), dist))
        return neighbors

    def heuristic(r, c):
        dr = abs(r - target[0])
        dc = abs(c - target[1])
        # Min time = shortest distance / speed
        return (cell_size * (max(dr, dc) + (math.sqrt(2) - 1) * min(dr, dc))) / speed

    # State is: (row, col, time_h, energy_wh)
    start_state = (start[0], start[1], 0.0, capacity)
    open_set = []
    heapq.heappush(open_set, (heuristic(start[0], start[1]), 0.0, start_state))
    
    came_from = {}
    best_cost = {start_state: 0.0} # Keyed by state, cost is time_h
    
    # To prevent the memory from exploding, we limit how far ahead we can see.
    max_time_h = grid["n_steps"] - depart_step

    while open_set:
        f, current_time, current_state = heapq.heappop(open_set)
        r, c, t, e = current_state
        
        # Arrived!
        if (r, c) == target:
            path = []
            while current_state in came_from:
                path.append(current_state)
                current_state = came_from[current_state]
            path.append(start_state)
            path.reverse()
            return path

        # --- ACTION 1: WAIT (Let's charge in the sun!) ---
        wait_time = 1.0 # Wait 1 hour
        new_t_wait = t + wait_time
        
        if new_t_wait <= max_time_h:
            current_step = min(int(depart_step + t), grid["n_steps"] - 1)
            sun = grid["sun_pct"][current_step][r][c]
            
            p_in = physics.power_in_w(rover, sun)
            heater = physics.heater_w(rover, sun)
            p_out = rover["power_w"]["avionics"] + heater
            
            new_e_wait, frozen, _ = physics.battery_step(rover, e, p_in, p_out, wait_time)
            
            if not frozen and new_e_wait >= reserve:
                new_state = (r, c, new_t_wait, new_e_wait)
                cost_wait = current_time + wait_time
                
                if new_state not in best_cost or cost_wait < best_cost[new_state]:
                    best_cost[new_state] = cost_wait
                    came_from[new_state] = current_state
                    heapq.heappush(open_set, (cost_wait + heuristic(r, c), cost_wait, new_state))

        # --- ACTION 2: MOVE ---
        for (nr, nc), dist_m in get_neighbors(r, c):
            move_time = dist_m / speed
            new_t_move = t + move_time
            
            if new_t_move > max_time_h:
                continue
            
            # Sub-step the movement to handle changing shadows
            sub_steps = max(1, math.ceil(move_time / 0.25))
            dt = move_time / sub_steps
            temp_e = e
            dead = False
            
            for _ in range(sub_steps):
                # Calculate time at this exact sub-step
                sub_t = t + (_ * dt)
                current_step = min(int(depart_step + sub_t), grid["n_steps"] - 1)
                
                # Use current cell's sun for the sub-step
                sun = grid["sun_pct"][current_step][r][c]
                p_in = physics.power_in_w(rover, sun)
                
                elev_here = grid["elevation_m"][r][c]
                elev_next = grid["elevation_m"][nr][nc]
                p_drive = physics.drive_w(rover, elev_here, elev_next, dist_m)
                
                heater = physics.heater_w(rover, sun)
                p_out = rover["power_w"]["avionics"] + heater + p_drive
                
                temp_e, frozen, _ = physics.battery_step(rover, temp_e, p_in, p_out, dt)
                if frozen:
                    dead = True
                    break
            
            if not dead and temp_e >= reserve:
                new_state = (nr, nc, new_t_move, temp_e)
                cost_move = current_time + move_time
                
                if new_state not in best_cost or cost_move < best_cost[new_state]:
                    best_cost[new_state] = cost_move
                    came_from[new_state] = current_state
                    heapq.heappush(open_set, (cost_move + heuristic(nr, nc), cost_move, new_state))

    return None # No safe route found