from typing import List, Deque, Tuple, Mapping, Any, Optional
import pygame
import terrain
import sprite
import random
import targeter
import collections

class Civ():
	im_food = pygame.image.load("pics/game/food.png")
	im_wood = pygame.image.load("pics/game/wood.png")
	im_gold = pygame.image.load("pics/game/gold.png")

	def __init__(self, terr: terrain.Terrain) -> None:
		self.alive = True
		self.human = True
		self.terr = terr
		self.population: List[sprite.Sprite] = []
		self.food = 7
		self.wood = 7
		self.gold = 1
		self.last_state: Mapping[str, Any] = {}
		self.last_history_pos: int = 0

	def marshall(self) -> Mapping[str, Any]:
		return {
			'alive': self.alive,
			'pop': [ s.marshall() for s in self.population ],
			'food': self.food,
			'wood': self.wood,
			'gold': self.gold,
		}

	def unmarshall(self, ob: Mapping[str, Any], old_civ: Optional['Civ'] = None) -> None:
		self.alive = ob['alive']
		self.population = []
		for s in ob['pop']:
			self.population.append(sprite.Sprite.unmarshall(s))
		self.food = ob['food']
		self.wood = ob['wood']
		self.gold = ob['gold']
		if old_civ is not None:
			self.last_state = old_civ.last_state
			self.last_history_pos = old_civ.last_history_pos

	def place_starter_hut(self, civs: List['Civ']) -> None:
		# Find a starting spot
		candidates = self.terr.get_tile_spots([2, 3, 4, 5])
		start_spot = (0, 0)
		aloneness = 0
		for attempt in range(12):
			spot = candidates[random.randrange(len(candidates))]

			# Approximate the closest sprite
			closest_dist = 1000000
			for civ in civs:
				for s in civ.population:
					crude_dist = (spot[0] - s.tile[0]) ** 2 + (spot[1] - s.tile[1]) ** 2
					closest_dist = min(closest_dist, crude_dist)

			# Evaluate the spot
			if closest_dist > aloneness:
				aloneness = closest_dist
				start_spot = spot

		# Place a hut
		hut = sprite.Building()
		hut.set_tile_and_pos(start_spot, self.terr)
		self.population.append(hut)

	def set_last_state(self, state: Mapping[str, Any], history_pos: int) -> None:
		self.last_state = state
		self.last_history_pos = history_pos

	def start_turn(self, civs: List['Civ'], active: int) -> None:
		if not self.alive:
			return

		# Farms and mines produce
		creature_count = 0
		building_count = 0
		farm_count = 0
		for spr in civs[active].population:
			if spr.is_farm():
				civs[active].food += 1
				spr.exhausted = True
				farm_count += 1
			elif spr.is_mine():
				civs[active].gold += 1
				spr.exhausted = True
			elif spr.is_creature():
				creature_count += 1
			elif spr.is_building():
				building_count += 1
		if creature_count == 0 and (building_count == 0 or (self.food < 2 and farm_count == 0)):
			self.alive = False

	def make_visibility_map(self) -> List[List[bool]]:
		vis = [ [ False for x in range(16) ] for y in range(16) ]
		for spr in self.population:
			s = set()
			q: Deque[Tuple[Tuple[int, int], int]] = collections.deque()
			s.add(spr.tile)
			q.append((spr.tile, 0))
			vis[spr.tile[1]][spr.tile[0]] = True
			while len(q) > 0:
				spot, depth = q.popleft()
				if depth < spr.visibility():
					for neigh in terrain.Terrain.adjacent(spot):
						if neigh in s:
							continue # Already been there
						vis[neigh[1]][neigh[0]] = True
						s.add(neigh)
						q.append((neigh, depth + 1))
		return vis


	def draw_resources(self, screen: pygame.Surface) -> None:
		# Draw food
		x = 1200
		y = 10
		im_rect = Civ.im_food.get_rect()
		for i in range(min(self.food, 38)):
			screen.blit(Civ.im_food, (x, y, x + im_rect.w, y + im_rect.h))
			x += 43
			if x > 1520:
				x = 1200
				y += 22
				if (y // 22) % 2 == 1:
					x += 22

		# Draw wood
		x = 1276
		y = 130
		im_rect = Civ.im_wood.get_rect()
		for i in range(min(self.wood, 36)):
			screen.blit(Civ.im_wood, (x, y, x + im_rect.w, y + im_rect.h))
			x += 26
			if x > 1520:
				y += 46
				x = 1200 + y // 2

		# Draw gold
		x = 1360
		y = 320
		im_rect = Civ.im_gold.get_rect()
		for i in range(min(self.gold, 37)):
			screen.blit(Civ.im_gold, (x, y, x + im_rect.w, y + im_rect.h))
			x += 20
			if x > 1520:
				y += 46
				x = 1200 + y // 2
