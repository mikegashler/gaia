from typing import List, Tuple, Optional, Mapping, Any
import cv2
import random
import numpy as np
import image

class Terrain():
	w = 16
	h = 16
	images: List[np.ndarray] = [
		cv2.imread('pics/game/fog.png', -1),     # 0
		cv2.imread('pics/game/water.png', -1),   # 1
		cv2.imread('pics/game/forest.png', -1),  # 2
		cv2.imread('pics/game/land.png', -1),    # 3
		cv2.imread('pics/game/desert.png', -1),  # 4
		cv2.imread('pics/game/mountain.png', -1),# 5
	]
	borders: List[np.ndarray] = [
		cv2.imread('pics/civ0/border.png', -1),
		cv2.imread('pics/civ1/border.png', -1),
		cv2.imread('pics/civ2/border.png', -1),
		cv2.imread('pics/civ3/border.png', -1),
	]
	borders_dotted: List[np.ndarray] = [
		cv2.imread('pics/civ0/border_dotted.png', -1),
		cv2.imread('pics/civ1/border_dotted.png', -1),
		cv2.imread('pics/civ2/border_dotted.png', -1),
		cv2.imread('pics/civ3/border_dotted.png', -1),
	]

	def __init__(self) -> None:
		self.qw = 88
		self.hh = 152
		self.scale = 0.36
		self.tiles: List[List[int]] = [[1 for i in range(self.w)] for j in range(self.h)] # all water

	def marshall(self) -> List[List[int]]:
		return self.tiles

	def unmarshall(self, ob: List[List[int]]) -> None:
		assert len(ob) == 16 and len(ob[0]) == 16
		self.tiles = ob

	def tile(self, spot: Tuple[int, int]) -> int:
		return self.tiles[spot[1]][spot[0]]

	def set_tile(self, spot: Tuple[int, int], t: int) -> None:
		self.tiles[spot[1]][spot[0]] = t

	def generate_terrain(self) -> None:
		min_islands = 6
		max_islands = 12
		min_island_size = 15
		max_island_size = 45
		consistency = 8

		# Add some islands
		num_islands = random.randrange(min_islands, max_islands)
		for i in range(num_islands):
			# Start in a random place
			x = random.randrange(self.w)
			y = random.randrange(self.h)
			island_size = random.randrange(min_island_size, max_island_size)
			tile_type = random.randrange(2, 6)

			# Grow the land
			for j in range(island_size):
				if random.randrange(consistency) == 0:
					tile_type = random.randrange(2, 6)
				self.tiles[y][x] = tile_type
				adj = self.adjacent((x, y))
				x, y = adj[random.randrange(len(adj))]

	def corner(self, x: int, y: int) -> Tuple[int, int]:
		xx = 3 * x * self.qw
		yy = (2 * y + (0 if (x & 1) == 0 else 1)) * self.hh
		return (int(xx * self.scale), int(yy * self.scale))

	def update_canvas(self, owned_spots: List[List[Tuple[int, int, bool]]], visibility: List[List[bool]]) -> None:
		# Make a scaling transform
		corners_bef = np.float32([[[0., 0.]], [[1., 0.]], [[1., 1.]], [[0., 1.]]])
		corners_aft = np.float32([[[0., 0.]], [[self.scale, 0.]], [[self.scale, self.scale]], [[0., self.scale]]])
		transform = cv2.getPerspectiveTransform(corners_bef, corners_aft)

		# Make a canvas
		wid = int((1 + (3 * self.w)) * self.qw * self.scale)
		hgt = int((1 + (2 * self.h)) * self.hh * self.scale)
		canvas = np.full((hgt, wid, 3), 0, dtype = np.uint8)

		# Draw the tiles
		for y in range(self.h):
			for x in range(self.w):
				xx, yy = self.corner(x, y)
				offset = np.eye(3)
				offset[0, 2] = xx
				offset[1, 2] = yy
				corrected_transform = np.matmul(offset, transform)
				tile = 0
				if visibility[y][x]:
					tile = self.tiles[y][x]
				image.perspective_blit4(canvas, self.images[tile], corrected_transform)

		# Draw ownership borders
		for i in range(len(owned_spots)):
			spots = owned_spots[i]
			for spot in spots:
				if visibility[spot[1]][spot[0]]:
					xx, yy = self.corner(spot[0], spot[1])
					offset = np.eye(3)
					offset[0, 2] = xx
					offset[1, 2] = yy
					corrected_transform = np.matmul(offset, transform)
					if spot[2]:
						pic = self.borders_dotted[i]
					else:
						pic = self.borders[i]
					image.perspective_blit4(canvas, pic, corrected_transform)

		# Tilt the canvas back
		h, w = canvas.shape[0:2]
		ww = 0.6 * w
		hh = 0.4 * h
		corners_bef = np.float32([[[0., 0.]], [[w, 0.]], [[w, h]], [[0., h]]])
		corners_aft = np.float32([[[(w - ww) / 2., 0.]], [[(w - ww) / 2. + ww, 0.]], [[w, hh]], [[0., hh]]])
		self.transform = cv2.getPerspectiveTransform(corners_bef, corners_aft)
		self.untransform = np.linalg.pinv(self.transform)
		self.canvas = cv2.warpPerspective(canvas, self.transform, (int(w), int(hh)))

	def tile_to_pixel(self, x: int, y: int) -> Tuple[int, int]:
		xx, yy = self.corner(x, y)
		point_bef = np.float32([[[2 * self.qw * self.scale + xx, self.hh * self.scale + yy]]])
		point_aft = cv2.perspectiveTransform(point_bef, self.transform)
		return int(point_aft[0, 0, 0]), int(point_aft[0, 0, 1])

	def pixel_to_tile(self, x: int, y: int) -> Tuple[int, int]:
		point_bef = np.float32([[[x, y]]])
		point_aft = cv2.perspectiveTransform(point_bef, self.untransform)
		col = max(0, min(15, int((point_aft[0, 0, 0] - 0.5 * self.qw * self.scale) / (3 * self.qw * self.scale))))
		yy = point_aft[0, 0, 1]
		if col & 1 == 1:
			yy -= self.hh * self.scale
		row = max(0, min(15, int(yy / (2 * self.hh * self.scale))))
		return col, row

	@staticmethod
	def adjacent(spot: Tuple[int, int]) -> List[Tuple[int, int]]:
		x, y = spot
		hood: List[Tuple[int, int]] = []
		if spot[0] > 0:
			hood.append((x - 1, y))
		if x + 1 < Terrain.w:
			hood.append((x + 1, y))
		if y > 0:
			hood.append((x, y - 1))
		if y + 1 < Terrain.h:
			hood.append((x, y + 1))
		if x & 1 == 0:
			if x > 0 and y > 0:
				hood.append((x - 1, y - 1))
			if x + 1 < Terrain.w and y > 0:
				hood.append((x + 1, y - 1))
		else:
			if x > 0 and y + 1 < Terrain.h:
				hood.append((x - 1, y + 1))
			if x + 1 < Terrain.w and y + 1 < Terrain.h:
				hood.append((x + 1, y + 1))
		return hood

	def get_tile_spots(self, acceptable_types: List[int]) -> List[Tuple[int, int]]:
		candidates: List[Tuple[int, int]] = []
		for y in range(self.h):
			for x in range(self.w):
				if self.tile((x, y)) in acceptable_types:
					candidates.append((x, y))
		return candidates

	def random_tile(self, acceptable_types: List[int]) -> Optional[Tuple[int, int]]:
		candidates = self.get_tile_spots(acceptable_types)
		if len(candidates) < 1:
			return None
		return candidates[random.randrange(len(candidates))]
