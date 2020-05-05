from typing import Optional, Tuple, List, Dict, Mapping, Any, Callable
from abc import abstractmethod
import pygame
import terrain
import image
import enum

def noop() -> None:
	pass

btn_gnome = 'gnome (-2 food)'
btn_dwarf = 'dwarf (-3 food)'
btn_trebuchet = 'trebuchet (-3 gold)'
btn_elf = 'elf (-2 gold)'
btn_dragon = 'dragon (-13 gold)'
btn_farm = 'farm (-2 wood)'
btn_plant = 'plant trees'
btn_hut = 'hut (-1 wood)'
btn_fort = 'fort (-5 wood)'
btn_castle = 'castle (-8 wood)'
btn_wood = 'chop wood'
btn_mine = 'mine (-3 wood)'

class Animation(enum.Enum):
	done = 0
	move = 1
	strike = 2
	kill = 3

class Sprite():
	def __init__(self) -> None:
		self.image: Optional[pygame.image] = None
		self.tile = (0, 0)
		self.pos = (-1000, 0)
		self.exhausted = False
		self.animation: Animation = Animation.done
		self.anim_target: Tuple[int, int] = self.pos
		self.anim_on_finish: Callable[[], None] = noop
		self.life = 1
		self.civ = -1

	def marshall(self) -> Mapping[str, Any]:
		raise NotImplementedError('called an abstract method')

	def marshall_base(self, name: str) -> Dict[str, Any]:
		return {
			'type': name,
			'tile': [self.tile[0], self.tile[1]],
			'pos': [self.pos[0], self.pos[1]],
			'exh': self.exhausted,
			'life': self.life,
		}

	def unmarshall_base(self, ob: Mapping[str, Any]) -> None:
		self.tile = (ob['tile'][0], ob['tile'][1])
		self.pos = (ob['pos'][0], ob['pos'][1])
		self.exhausted = ob['exh']
		self.life = ob['life']

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Sprite':
		if ob['type'] == 'Building': return Building.unmarshall(ob)
		elif ob['type'] == 'Farm': return Farm.unmarshall(ob)
		elif ob['type'] == 'Mine': return Mine.unmarshall(ob)
		elif ob['type'] == 'Gnome': return Gnome.unmarshall(ob)
		elif ob['type'] == 'Dwarf': return Dwarf.unmarshall(ob)
		elif ob['type'] == 'Trebuchet': return Trebuchet.unmarshall(ob)
		elif ob['type'] == 'Elf': return Elf.unmarshall(ob)
		elif ob['type'] == 'Dragon': return Dragon.unmarshall(ob)
		else: raise ValueError('Unrecognized sprite type: ' + str(ob['type']))


	def rect(self) -> Tuple[int, int, int, int]:
		assert self.image
		rect_in = self.image.get_rect()
		w = rect_in[2] - rect_in[0]
		h = rect_in[3] - rect_in[1]
		return (self.pos[0] - w // 2, self.pos[1] - h + 5, self.pos[0] - w // 2 + w, self.pos[1] + 5)

	def set_tile_and_pos(self, tile: Tuple[int, int], terr: terrain.Terrain) -> None:
		self.tile = tile
		p = terr.tile_to_pixel(tile[0], tile[1])
		self.pos = (p[0], p[1] + 147)

	def get_attack_strength(self) -> int:
		return 0

	def strike_opponent(self, target: 'Sprite', tile: Tuple[int, int], terr: terrain.Terrain) -> None:
		target.life -= self.get_attack_strength()
		self.set_tile_and_pos(tile, terr)

	def draw(self, screen: pygame.Surface) -> None:
		if not self.image:
			return
		screen.blit(self.image, self.rect())

	def visibility(self) -> int:
		return 2

	def is_button(self) -> bool:
		return False

	def is_move_target(self) -> bool:
		return False

	def is_attack_target(self) -> bool:
		return False

	def is_building(self) -> bool:
		return False

	def is_farm(self) -> bool:
		return False

	def is_mine(self) -> bool:
		return False

	def is_creature(self) -> bool:
		return False

	def menu_options(self, land_type: int) -> List[str]:
		return []

	def move_range(self) -> int:
		return 0

	def can_fly(self) -> bool:
		return False

	def can_shoot(self) -> bool:
		return False

	def attack_range(self) -> int:
		return 0

	def on_mouse_down(self) -> None:
		pass

	def on_mouse_up(self) -> None:
		pass

	def on_water(self, b: bool) -> None:
		pass

	def start_animation(self, dest: Tuple[int, int], anim: Animation, on_finish: Callable[[], None], victim: Optional['Sprite'] = None) -> None:
		self.animation = anim
		self.anim_on_finish = on_finish
		self.anim_target = dest
		self.anim_origin = self.pos
		self.anim_state = 0
		self.anim_victim = victim

	def stop_animation(self) -> None:
		self.anim_on_finish()

	def animate(self) -> bool:
		if self.animation == Animation.move:
			# Move the selected sprite closer to the destination
			x = (3 * self.pos[0] + self.anim_target[0]) // 4
			y = (3 * self.pos[1] + self.anim_target[1]) // 4
			if x == self.pos[0] and y == self.pos[1]:
				self.pos = self.anim_target
				self.anim_on_finish()
				return True # animation done
			else:
				self.pos = (x, y)
				return False # not done
		elif self.animation == Animation.strike:
			if self.anim_state == 0:
				# Lunge in toward the opponent
				x = (3 * self.pos[0] + self.anim_target[0]) // 4
				y = (3 * self.pos[1] + self.anim_target[1]) // 4
				if 8 * ((x - self.pos[0]) ** 2 + (y - self.pos[1]) ** 2) < (x - self.anim_origin[0]) ** 2 + (y - self.anim_origin[1]) ** 2:
					self.anim_state = 1
				self.pos = (x, y)
				return False # not done
			else:
				# Retreat back to origin
				x = (3 * self.pos[0] + self.anim_origin[0]) // 4
				y = (3 * self.pos[1] + self.anim_origin[1]) // 4
				if (x - self.pos[0]) ** 2 + (y - self.pos[1]) ** 2 < (x - self.anim_origin[0]) ** 2 + (y - self.anim_origin[1]) ** 2:
					self.anim_state = 1
				if x == self.pos[0] and y == self.pos[1]:
					self.pos = self.anim_origin
					self.anim_on_finish()
					return True # animation done
				else:
					self.pos = (x, y)
					return False # not done
		elif self.animation == Animation.kill:
			# Move the selected sprite closer to the destination
			x = (3 * self.pos[0] + self.anim_target[0]) // 4
			y = (3 * self.pos[1] + self.anim_target[1]) // 4
			if 6 * (x - self.pos[0]) ** 2 + (y - self.pos[1]) ** 2 < (x - self.anim_origin[0]) ** 2 + (y - self.anim_origin[1]) ** 2:
				if self.anim_victim is not None:
					px = self.anim_victim.pos[0] + (x - self.pos[0])
					py = self.anim_victim.pos[1] + (y - self.pos[1])
					self.anim_victim.pos = (px, py)
			if x == self.pos[0] and y == self.pos[1]:
				self.pos = self.anim_target
				self.anim_on_finish()
				return True # animation done
			else:
				self.pos = (x, y)
				return False # not done
		else:
			raise ValueError('Unsupported animation: ' + str(self.animation))
		return False

class Button(Sprite):
	im_up = pygame.image.load("pics/game/button_up.png")
	im_down = pygame.image.load("pics/game/button_down.png")
	font = pygame.font.Font('freesansbold.ttf', 24)

	def __init__(self, pos: Tuple[int, int], text: str) -> None:
		super().__init__()
		self.pos = pos
		self.text = text
		self.image = Button.im_up
		self.text_image = Button.font.render(self.text, True, (0, 0, 0))
		rb = self.rect()
		rt = self.text_image.get_rect()
		l = rb[0] + (rb[2] - rb[0] - rt[2]) // 2
		t = rb[1] + (rb[3] - rb[1] - rt[3]) // 2
		self.text_rect_up = (l, t, l + rt[2], t + rt[3])
		self.text_rect_down = (l, t + 3, l + rt[2], t + rt[3] + 3)

	def draw(self, screen: pygame.Surface) -> None:
		screen.blit(self.image, self.rect())
		screen.blit(self.text_image, self.text_rect_down if self.image is Button.im_down else self.text_rect_up)

	def is_button(self) -> bool:
		return True

	def on_mouse_down(self) -> None:
		self.image = Button.im_down

	def on_mouse_up(self) -> None:
		self.image = Button.im_up

class Pointer(Sprite):
	im_back = pygame.image.load("pics/game/ring_back.png")
	im_front = pygame.image.load("pics/game/ring_front.png")

	def __init__(self) -> None:
		super().__init__()
		self.image = Pointer.im_front

	def draw_back(self, screen: pygame.Surface) -> None:
		if not self.image:
			return
		screen.blit(Pointer.im_back, self.rect())

class TargetMove(Sprite):
	im_arrow = image.scale_pg_image(pygame.image.load("pics/game/blue_arrow.png"), 0.3)

	def __init__(self) -> None:
		super().__init__()
		self.image = TargetMove.im_arrow

	def is_move_target(self) -> bool:
		return True

class TargetAttack(Sprite):
	im_arrow = image.scale_pg_image(pygame.image.load("pics/game/red_arrow.png"), 0.3)

	def __init__(self) -> None:
		super().__init__()
		self.image = TargetAttack.im_arrow

	def is_attack_target(self) -> bool:
		return True

class Building(Sprite):
	im_hut = image.scale_pg_image(pygame.image.load("pics/game/hut.png"), 0.15)
	im_fortress = image.scale_pg_image(pygame.image.load("pics/game/fort.png"), 0.17)
	im_castle = image.scale_pg_image(pygame.image.load("pics/game/castle.png"), 0.15)

	def __init__(self) -> None:
		super().__init__()
		self.image = Building.im_hut

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Building')
		if self.image == Building.im_hut: ob['state'] = 0
		elif self.image == Building.im_fortress: ob['state'] = 1
		else: ob['state'] = 2
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Building':
		s = Building()
		s.unmarshall_base(ob)
		if ob['state'] == 0: s.image = Building.im_hut
		elif ob['state'] == 1: s.image = Building.im_fortress
		else: s.image = Building.im_castle
		return s

	def is_building(self) -> bool:
		return True

	def upgrade(self) -> None:
		if self.image == Building.im_hut:
			self.image = Building.im_fortress
		elif self.image == Building.im_fortress:
			self.image = Building.im_castle
		self.exhausted = True

	def menu_options(self, land_type: int) -> List[str]:
		if self.image == Building.im_hut:
			return [
				btn_gnome,
				btn_fort,
			]
		elif self.image == Building.im_fortress:
			return [
				btn_gnome,
				btn_dwarf,
				btn_castle,
			]
		elif self.image == Building.im_castle:
			return [
				btn_gnome,
				btn_dwarf,
				btn_elf,
				btn_dragon,
			]
		else:
			raise ValueError('unrecognized state')

class Farm(Sprite):
	im_farm = image.scale_pg_image(pygame.image.load("pics/game/farm.png"), 0.4)

	def __init__(self) -> None:
		super().__init__()
		self.image = Farm.im_farm

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Farm')
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Farm':
		s = Farm()
		s.unmarshall_base(ob)
		return s

	def is_farm(self) -> bool:
		return True

class Mine(Sprite):
	im_mine = image.scale_pg_image(pygame.image.load("pics/game/mine.png"), 0.10)

	def __init__(self) -> None:
		super().__init__()
		self.image = Mine.im_mine

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Mine')
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Mine':
		s = Mine()
		s.unmarshall_base(ob)
		return s

	def is_mine(self) -> bool:
		return True

class Creature(Sprite):
	im_heart = pygame.image.load("pics/game/heart.png")

	def __init__(self) -> None:
		super().__init__()

	def is_creature(self) -> bool:
		return True

	def draw_life(self, screen: pygame.Surface) -> None:
		x = 900
		y = 10
		im_rect = Creature.im_heart.get_rect()
		for i in range(min(self.life, 34)):
			screen.blit(Creature.im_heart, (x, y, x + im_rect.w, y + im_rect.h))
			x += 30
			if x > 1150:
				x = 900
				y += 28
				if (y // 28) % 2 == 1:
					x += 15

class Gnome(Creature):
	im_gnome = [
		image.scale_pg_image(pygame.image.load("pics/civ0/gnome.png"), 0.07),
		image.scale_pg_image(pygame.image.load("pics/civ1/gnome.png"), 0.12),
		image.scale_pg_image(pygame.image.load("pics/civ2/gnome.png"), 0.07),
		image.scale_pg_image(pygame.image.load("pics/civ3/gnome.png"), 0.15),
	]
	im_gnome_on_raft = [
		image.scale_pg_image(pygame.image.load("pics/civ0/gnome_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/gnome_on_raft.png"), 0.11),
		image.scale_pg_image(pygame.image.load("pics/civ2/gnome_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ3/gnome_on_raft.png"), 0.15),
	]

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Gnome')
		ob['raft'] = self.raft
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Gnome':
		s = Gnome()
		s.unmarshall_base(ob)
		s.raft = ob['raft']
		return s

	def __init__(self) -> None:
		super().__init__()
		self.image = Gnome.im_gnome
		self.life = 3
		self.raft = False

	def draw(self, screen: pygame.Surface) -> None:
		if self.raft:
			self.image = Gnome.im_gnome_on_raft[self.civ]
		else:
			self.image = Gnome.im_gnome[self.civ]
		screen.blit(self.image, self.rect())

	def get_attack_strength(self) -> int:
		return 1

	def menu_options(self, land_type: int) -> List[str]:
		opts: List[str] = []
		if land_type == 2:
			opts.append(btn_wood)
		if land_type == 3:
			opts.append(btn_plant)
			opts.append(btn_farm)
		opts.append(btn_hut)
		return opts

	def visibility(self) -> int:
		return 2

	def move_range(self) -> int:
		return 2

	def attack_range(self) -> int:
		return 2

	def on_water(self, b: bool) -> None:
		self.raft = b

	def can_shoot(self) -> bool:
		return self.raft

class Dwarf(Creature):
	im_dwarf = [
		image.scale_pg_image(pygame.image.load("pics/civ0/dwarf.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/dwarf.png"), 0.12),
		image.scale_pg_image(pygame.image.load("pics/civ2/dwarf.png"), 0.10),
		image.scale_pg_image(pygame.image.load("pics/civ3/dwarf.png"), 0.25),
	]
	im_dwarf_on_raft = [
		image.scale_pg_image(pygame.image.load("pics/civ0/dwarf_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/dwarf_on_raft.png"), 0.10),
		image.scale_pg_image(pygame.image.load("pics/civ2/dwarf_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ3/dwarf_on_raft.png"), 0.15),
	]

	def __init__(self) -> None:
		super().__init__()
		self.image = Dwarf.im_dwarf
		self.life = 5
		self.raft = False

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Dwarf')
		ob['raft'] = self.raft
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Dwarf':
		s = Dwarf()
		s.unmarshall_base(ob)
		s.raft = ob['raft']
		return s

	def draw(self, screen: pygame.Surface) -> None:
		if self.raft:
			self.image = Dwarf.im_dwarf_on_raft[self.civ]
		else:
			self.image = Dwarf.im_dwarf[self.civ]
		screen.blit(self.image, self.rect())

	def visibility(self) -> int:
		return 3

	def move_range(self) -> int:
		return 2

	def attack_range(self) -> int:
		if self.image == Dwarf.im_dwarf: return 3
		else: return 2

	def get_attack_strength(self) -> int:
		return 2

	def menu_options(self, land_type: int) -> List[str]:
		opts: List[str] = [
			btn_trebuchet,
		]
		if land_type == 5: # mountain
			opts.append(btn_mine)
		return opts

	def on_water(self, b: bool) -> None:
		self.raft = b

	def can_shoot(self) -> bool:
		return self.raft

class Trebuchet(Creature):
	im_trebuchet = [
		image.scale_pg_image(pygame.image.load("pics/civ0/trebuchet.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/trebuchet.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ2/trebuchet.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ3/trebuchet.png"), 0.15),
	]
	im_trebuchet_on_raft = [
		image.scale_pg_image(pygame.image.load("pics/civ0/trebuchet_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/trebuchet_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ2/trebuchet_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ3/trebuchet_on_raft.png"), 0.15),
	]

	def __init__(self) -> None:
		super().__init__()
		self.image = Trebuchet.im_trebuchet
		self.life = 1
		self.raft = False

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Trebuchet')
		ob['raft'] = self.raft
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Trebuchet':
		s = Trebuchet()
		s.unmarshall_base(ob)
		s.raft = ob['raft']
		return s

	def draw(self, screen: pygame.Surface) -> None:
		if self.raft:
			self.image = Trebuchet.im_trebuchet_on_raft[self.civ]
		else:
			self.image = Trebuchet.im_trebuchet[self.civ]
		screen.blit(self.image, self.rect())

	def visibility(self) -> int:
		return 5

	def move_range(self) -> int:
		return 1

	def attack_range(self) -> int:
		return 5

	def get_attack_strength(self) -> int:
		return 5

	def can_shoot(self) -> bool:
		return True

	def on_water(self, b: bool) -> None:
		self.raft = b


class Elf(Creature):
	im_elf = [
		image.scale_pg_image(pygame.image.load("pics/civ0/elf.png"), 0.10),
		image.scale_pg_image(pygame.image.load("pics/civ1/elf.png"), 0.18),
		image.scale_pg_image(pygame.image.load("pics/civ2/elf.png"), 0.10),
		image.scale_pg_image(pygame.image.load("pics/civ3/elf.png"), 0.10),
	]
	im_elf_on_raft = [
		image.scale_pg_image(pygame.image.load("pics/civ0/elf_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ1/elf_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ2/elf_on_raft.png"), 0.15),
		image.scale_pg_image(pygame.image.load("pics/civ3/elf_on_raft.png"), 0.15),
	]

	def __init__(self) -> None:
		super().__init__()
		self.image = Elf.im_elf
		self.life = 5
		self.raft = False

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Elf')
		ob['raft'] = self.raft
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Elf':
		s = Elf()
		s.unmarshall_base(ob)
		s.raft = ob['raft']
		return s

	def draw(self, screen: pygame.Surface) -> None:
		if self.raft:
			self.image = Elf.im_elf_on_raft[self.civ]
		else:
			self.image = Elf.im_elf[self.civ]
		screen.blit(self.image, self.rect())

	def visibility(self) -> int:
		return 4

	def move_range(self) -> int:
		if self.image == Elf.im_elf: return 3 # on land
		else: return 2 # on water

	def attack_range(self) -> int:
		return 4

	def get_attack_strength(self) -> int:
		return 2

	def can_shoot(self) -> bool:
		return True

	def on_water(self, b: bool) -> None:
		self.raft = b


class Dragon(Creature):
	im_dragon = [
		image.scale_pg_image(pygame.image.load("pics/civ0/dragon.png"), 0.2),
		image.scale_pg_image(pygame.image.load("pics/civ1/dragon.png"), 0.2),
		image.scale_pg_image(pygame.image.load("pics/civ2/dragon.png"), 0.2),
		image.scale_pg_image(pygame.image.load("pics/civ3/dragon.png"), 0.2),
	]

	def __init__(self) -> None:
		super().__init__()
		self.image = Dragon.im_dragon
		self.life = 9

	def marshall(self) -> Mapping[str, Any]:
		ob = super().marshall_base('Dragon')
		return ob

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Dragon':
		s = Dragon()
		s.unmarshall_base(ob)
		return s

	def draw(self, screen: pygame.Surface) -> None:
		self.image = Dragon.im_dragon[self.civ]
		screen.blit(self.image, self.rect())

	def can_fly(self) -> bool:
		return True

	def visibility(self) -> int:
		return 5

	def move_range(self) -> int:
		return 4

	def attack_range(self) -> int:
		return 4

	def get_attack_strength(self) -> int:
		return 4

	def can_shoot(self) -> bool:
		return True
