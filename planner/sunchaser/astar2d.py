"""The naive planner: shortest route across the grid, ignoring the Sun.

8-connected A* search. The cost of a route is its length in metres. The
heuristic is the "octile" distance: the length of the best possible route on
an empty grid (diagonal steps until lined up, then straight). It never
overestimates the true remaining distance, which is what guarantees A* returns
a shortest route.

This is the route a planner picks if it only looks at the map. At the lunar
south pole it tends to drive straight into shadow.
"""

import heapq

from .world import World


def shortest_path(world, start, target):
    """Shortest drivable route from start to target as a list of (row, col), or None."""
    s, g = world.idx(*start), world.idx(*target)
    if not world.moves[s] or not world.moves[g]:
        return None
    best = {s: 0.0}
    came = {}
    # Heap entries: (f, -g, cell). On equal f the larger g goes first (it is
    # closer to the target), which cuts the number of cells explored.
    heap = [(world.octile_m(s, g), 0.0, s)]
    while heap:
        f, neg_g, cur = heapq.heappop(heap)
        cost = -neg_g
        if cur == g:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return [world.rc(i) for i in reversed(path)]
        if cost > best[cur] + 1e-9:
            continue                                  # an older, worse entry
        for nb, _, _, dist in world.moves[cur]:
            ng = cost + dist
            if ng < best.get(nb, float("inf")) - 1e-9:
                best[nb] = ng
                came[nb] = cur
                heapq.heappush(heap, (ng + world.octile_m(nb, g), -ng, nb))
    return None


def astar_shortest_path(grid, start, target, rover):
    """Harril's original entry point (grid and rover as loaded from JSON)."""
    return shortest_path(World(grid, rover), tuple(start), tuple(target))
