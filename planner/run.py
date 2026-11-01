import json
import os
import sys

# Tell Python to look in the current folder for the 'sunchaser' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sunchaser.astar2d import astar_shortest_path
from sunchaser.astar_st import astar_spacetime
from sunchaser.sim import simulate_route

def main():
    print("🚀 Starting Sunchaser Planner...")
    
    # Get the folder path for run.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Look for the JSON files INSIDE the 'fake' folder
    grid_path = os.path.join(base_dir, "fake", "grid_fake.json")
    rover_path = os.path.join(base_dir, "fake", "rover_fake.json")
    
    try:
        with open(grid_path, "r") as f:
            grid = json.load(f)
        with open(rover_path, "r") as f:
            rover = json.load(f)
    except FileNotFoundError:
        print("❌ Error: Could not find grid_fake.json or rover_fake.json. Did you run make_fake.py?")
        return

    # ... (Leave the rest of the file exactly as it is)
    # 2. Set Start and Target
    # Let's start on the left side and try to get to the right side
    start = (5, 5)    # (row, col)
    target = (35, 35) # (row, col)
    depart_step = 0   # Start at hour 0

    print(f"📍 Start: {start} | Target: {target} | Departure: Hour {depart_step}\n")

    # --- ROUTE 1: The Naive Shortest Path ---
    print("🧠 Running Naive A* (Shortest Path)...")
    path_shortest = astar_shortest_path(grid, start, target, rover)
    
    if path_shortest:
        # Simulate it to see if it survives
        sim_shortest = simulate_route(rover, grid, depart_step, path_shortest)
        print(f"   ✅ Path found! Distance: {sim_shortest['distance_m']}m")
        print(f"   🛑 Survived? {sim_shortest['survived']}")
        if not sim_shortest['survived']:
            print(f"   💀 Froze at step index: {sim_shortest['frozen_at_index']} (Time: {sim_shortest['duration_h']}h)")
        else:
            print(f"   🔋 Min Battery: {sim_shortest['min_battery_pct']}%")
    else:
        print("   ❌ No path found.")

    print("\n--------------------------------------------------\n")

    # --- ROUTE 2: The Sunchaser Space-Time A* ---
    print("☀️ Running Sunchaser A* (Space-Time)...")
    path_sunchaser = astar_spacetime(grid, rover, start, target, depart_step)
    
    if path_sunchaser:
        # The astar_st returns states: (row, col, t, e). We need to extract just (row, col) for the simulator
        # But wait, the simulator handles the time. We just need the path.
        simple_path = [(state[0], state[1]) for state in path_sunchaser]
        
        # We also need to know if the smart AI decided to WAIT.
        # The simulator assumes driving continuously. To show waiting, we'd need a more advanced simulator.
        # For Core tier, if it returns a path, we simulate it. If the path detoured, it will survive.
        
        sim_sunchaser = simulate_route(rover, grid, depart_step, simple_path)
        
        print(f"   ✅ Path found! Distance: {sim_sunchaser['distance_m']}m")
        print(f"   🛑 Survived? {sim_sunchaser['survived']}")
        if not sim_sunchaser['survived']:
            print(f"   💀 Froze at step index: {sim_sunchaser['frozen_at_index']} (Time: {sim_sunchaser['duration_h']}h)")
        else:
            print(f"   🔋 Min Battery: {sim_sunchaser['min_battery_pct']}%")
            print(f"   ⏱️ Total Time: {sim_sunchaser['duration_h']}h")
    else:
        print("   ❌ No safe path found. The rover cannot survive this journey.")

if __name__ == "__main__":
    main()