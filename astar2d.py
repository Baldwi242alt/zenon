import heapq
import math

def astar_shortest_path(grid, start, target, rover):
    """
    Finds the shortest path from start to target using 8-connected A*.
    Ignores the sun entirely (that's the point - it's the naive route).
    """
    rows = grid["rows"]
    cols = grid["cols"]
    cell_size = grid["cell_size_m"]
    max_slope = rover["drive"]["max_slope_deg"]
    
    def get_neighbors(r, c):
        # 8 directions (N, S, E, W, NE, NW, SE, SW)
        dirs = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]
        neighbors = []
        
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                # Check slope limits
                if grid["slope_deg"][nr][nc] > max_slope:
                    continue
                
                # Distance (diagonal is longer)
                if dr != 0 and dc != 0:
                    cost = cell_size * math.sqrt(2)
                else:
                    cost = cell_size
                    
                neighbors.append(((nr, nc), cost))
        return neighbors

    def heuristic(r, c):
        # Octile distance to target (admissible for 8-connected grids)
        dr = abs(r - target[0])
        dc = abs(c - target[1])
        return cell_size * (max(dr, dc) + (math.sqrt(2) - 1) * min(dr, dc))

    # A* Algorithm
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    came_from = {}
    g_score = {start: 0}
    
    while open_set:
        current_f, current = heapq.heappop(open_set)
        
        if current == target:
            # Rebuild path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
            
        for neighbor, move_cost in get_neighbors(current[0], current[1]):
            tentative_g = g_score[current] + move_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor[0], neighbor[1])
                heapq.heappush(open_set, (f_score, neighbor))
                
    return None # No path found