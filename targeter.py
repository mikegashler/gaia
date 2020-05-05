from typing import Optional, Tuple, List, Deque, Mapping, Any
import civ
import terrain
import sprite
import collections

class Spot():
	def __init__(self, tile: Tuple[int, int], steps: int, prev: Optional['Spot']) -> None:
		self.tile = tile
		self.steps = steps
		self.prev = prev
		self.enemy = False

class Targeter():
	def __init__(self, terr: terrain.Terrain, civs: List['civ.Civ']) -> None:
		self.sprites: List[List[Optional[sprite.Sprite]]] = [[None for i in range(terr.w)] for j in range(terr.h)]
		self.civs: List[List[int]] = [[-1 for i in range(terr.w)] for j in range(terr.h)]
		for i, civ in enumerate(civs):
			for sprite in civ.population:
				self.sprites[sprite.tile[1]][sprite.tile[0]] = sprite
				self.civs[sprite.tile[1]][sprite.tile[0]] = i

	def occupant(self, tile: Tuple[int, int]) -> Tuple[Optional[sprite.Sprite], int]:
		return self.sprites[tile[1]][tile[0]], self.civs[tile[1]][tile[0]]

	def nearest_open_spot(self, tile: Tuple[int, int], terr: terrain.Terrain, allow_water: bool) -> Tuple[int, int]:
		s = set()
		q: Deque[Tuple[int, int]] = collections.deque()
		s.add(tile)
		q.append(tile)
		while len(q) > 0:
			spot = q.popleft()
			for neigh in terr.adjacent(spot):
				if neigh in s:
					continue # Already been there
				if terr.tile(neigh) == 1 and not allow_water:
					continue # Don't go on water
				if self.occupant(neigh)[0] is None:
					return neigh # Found one!
				s.add(neigh)
				q.append(neigh)
		return -1, -1 # No available spot

	def get_move_targets(self,
		start: Tuple[int, int],
		terr: terrain.Terrain,
		steps: int,
		can_enter_water: bool,
		can_move_on_water: bool,
	) -> List[Spot]:
		started_on_water = (terr.tile(start) == 1)
		s = set()
		q: Deque[Spot] = collections.deque()
		s.add(start)
		q.append(Spot(start, 0, None))
		targets: List[Spot] = []
		while len(q) > 0:
			spot = q.popleft()
			spr, civ = self.occupant(spot.tile)
			if spr is None:
				targets.append(spot)
			keep_going = True
			if spot.steps >= steps: keep_going = False
			if started_on_water:
				if terr.tile(spot.tile) != 1 and not can_move_on_water: keep_going = False
			else:
				if terr.tile(spot.tile) == 1 and not can_move_on_water: keep_going = False
			if keep_going:
				for neigh in terr.adjacent(spot.tile):
					if neigh in s: continue # Already been there
					if not started_on_water and terr.tile(neigh) == 1 and not can_enter_water: continue # Don't go on water
					s.add(neigh)
					q.append(Spot(neigh, spot.steps + 1, spot))
		return targets

	def get_attack_targets(self,
		start: Tuple[int, int],
		terr: terrain.Terrain,
		steps: int,
		active_civ: int,
		shoot: bool,
	) -> List[Spot]:
		s = set()
		q: Deque[Spot] = collections.deque()
		s.add(start)
		q.append(Spot(start, 0, None))
		targets: List[Spot] = []
		while len(q) > 0:
			spot = q.popleft()
			spr, civ = self.occupant(spot.tile)
			keep_going = True
			if spot.steps >= steps: keep_going = False
			if spot.steps > 0 and spr is not None:
				if not civ == active_civ: targets.append(spot)
				if not shoot: keep_going = False
			if keep_going:
				for neigh in terr.adjacent(spot.tile):
					if neigh in s: continue # Already been there
					if terr.tile(neigh) == 1 and not shoot: continue # Don't go on water
					s.add(neigh)
					q.append(Spot(neigh, spot.steps + 1, spot))
		return targets
