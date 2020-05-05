from typing import Tuple, List, Optional, Mapping, Any
import pygame
import pygame.locals as pg
import terrain
import mvc
import civ
import image
import sprite
import targeter
import sys
import json
import random

# random.seed(1234)

class Action:
	def __init__(self, descr: str, doer: int, target: Optional[Tuple[int, int]]) -> None:
		self.descr = descr
		self.doer = doer
		self.target = target

	def marshall(self) -> Mapping[str, Any]:
		if self.descr == 'End':
			return { 'a': self.descr }
		elif self.descr == 'move' or self.descr == 'attack':
			assert self.target
			return {
				'a': self.descr,
				'd': self.doer,
				't': [ self.target[0], self.target[1] ],
			}
		else:
			return {
				'a': self.descr,
				'd': self.doer,
			}

	@staticmethod
	def unmarshall(ob: Mapping[str, Any]) -> 'Action':
		descr = ob['a']
		doer = ob['d'] if 'd' in ob else -1
		target = None
		if descr == 'move' or descr == 'attack':
			targ = ob['t']
			target = ( targ[0], targ[1] )
		return Action(descr, doer, target)


class Model(mvc.Model):
	def __init__(self) -> None:
		self.terr = terrain.Terrain()
		self.civs: List[civ.Civ] = []
		self.active_civ = 0
		self.perspective_civ = 0
		self.pointer = sprite.Pointer()
		self.selected_sprite: Optional[sprite.Sprite] = None
		self.selected_index: int
		self.targets: List[sprite.Sprite] = []
		self.menu: List[sprite.Sprite] = []
		self.control: List[sprite.Sprite] = [ sprite.Button((400, 75), 'End turn') ]
		self.pushed_button: Optional[sprite.Button] = None
		self.animating_sprite: Optional[sprite.Sprite] = None
		self.message = ''
		self.history: List[Action] = []
		self.history_pos = 0
		self.display_mode = True
		self.replay = False

	def start_game(self, num_civs: int) -> None:
		if num_civs > 4:
			raise ValueError('Sorry, only up to 4 players are currently supported')
		self.terr.generate_terrain()
		self.terr.update_canvas([], [[ False for x in range(16) ] for y in range(16)])
		self.civs = []
		for i in range(num_civs):
			self.civs.append(civ.Civ(self.terr))
		for c in self.civs:
			c.place_starter_hut(self.civs)
		self.active_civ = 0
		self.perspective_civ = 0
		if len(self.civs) > 1:
			self.message = 'Player 1, get ready!'

	def marshall(self) -> Mapping[str, Any]:
		return {
			'terr': self.terr.marshall(),
			'civs': [ civ.marshall() for civ in self.civs ],
			'ac': self.active_civ,
		}

	def unmarshall(self, ob: Mapping[str, Any]) -> None:
		self.terr.unmarshall(ob['terr'])
		old_civs = self.civs
		self.civs = []
		for i, serialized in enumerate(ob['civs']):
			c = civ.Civ(self.terr)
			c.unmarshall(serialized, old_civs[i] if i < len(old_civs) else None)
			self.civs.append(c)
		self.active_civ = ob['ac']

	def save_game(self) -> None:
        # Save game state
		ob = self.marshall()
		b = bytes(json.dumps(ob), 'utf8')
		with open('game.json', mode='wb+') as file:
			file.write(b)

        # Save the history
		hist = [ act.marshall() for act in self.history ]
		b = bytes(json.dumps(hist), 'utf8')
		with open('history.json', mode='wb+') as file:
			file.write(b)

	def load_game(self) -> None:
		filecontents = None
		with open('game.json', mode='rb') as file:
			filecontents = file.read()
		ob = json.loads(filecontents)
		self.unmarshall(ob)
		self.update_canvas()

	def update_canvas(self) -> None:
		self.visibility = self.civs[self.perspective_civ].make_visibility_map()
		self.terr.update_canvas(self.owned_spots(), self.visibility)
		self.canvas = image.to_pygame_surface(self.terr.canvas)

	# Returns a list of all the sprites on the screen, sorted from back to front for display purposes
	def sorted_visible_sprites(self) -> List[sprite.Sprite]:
		# Gather all the sprites
		assert self.visibility
		sprites: List[sprite.Sprite] = []
		for i, civ in enumerate(self.civs):
			for s in civ.population:
				s.civ = i
				if self.visibility[s.tile[1]][s.tile[0]]:
					sprites.append(s)

		# Sort from back to front
		sprites.sort(key = lambda spr: spr.tile[1])
		return sprites

	def find_opponent(self, tile: Tuple[int, int]) -> Optional[sprite.Sprite]:
		for i in range(len(self.civs)):
			if i == self.active_civ:
				continue
			civ = self.civs[i]
			for s in civ.population:
				if s.tile == tile:
					return s
		return None

	# Returns the sprite on the specified tile, or None if there is none.
	# Also, returns its index if it is in the current civilization, or -1
	def find_sprite(self, pos: Tuple[int, int]) -> Tuple[Optional[sprite.Sprite], int]:
		for s in self.menu + self.control:
			r = s.rect()
			if pos[0] >= r[0] and pos[1] >= r[1] and pos[0] < r[2] and pos[1] < r[3]:
				return s, -1
		tile = self.terr.pixel_to_tile(pos[0], pos[1] - 149)
		for s in self.targets:
			if s.tile == tile:
				return s, -1
		for i, s in enumerate(self.civs[self.active_civ].population):
			if s.tile == tile:
				return s, i
		for civ in self.civs:
			if civ is self.civs[self.active_civ]:
				continue
			for s in civ.population:
				if s.tile == tile:
					return s, -1
		return None, -1

	# Get a list of all the spots owned by each civilization. (This is used to update the canvas.)
	def owned_spots(self) -> List[List[Tuple[int, int, bool]]]:
		owned: List[List[Tuple[int, int, bool]]] = []
		for civ in self.civs:
			spots: List[Tuple[int, int, bool]] = []
			for s in civ.population:
				spots.append(s.tile + (s.exhausted,))
				# print(str(s.tile) + ' -> ' + str(s))
			owned.append(spots)
		return owned

	def update(self) -> bool:
		if len(self.message) > 0:
			return False
		elif self.animating_sprite is None:
			if self.history_pos < len(self.history):
				self.do_action(self.history[self.history_pos])
				self.history_pos += 1
			else:
				self.replay = False
		else:
			if self.animating_sprite.animate():
				self.animating_sprite = None # animation done
				self.update_canvas()
			return True # invalidate the view
		return False # don't invalidate the view

	def spawn_sprite(self, origin: sprite.Sprite, spr: sprite.Sprite) -> None:
		if origin.is_building():
			sm = targeter.Targeter(self.terr, self.civs)
			spot = sm.nearest_open_spot(origin.tile, self.terr, allow_water=False)
			if spot[0] < 0:
				spot = sm.nearest_open_spot(origin.tile, self.terr, allow_water=True)
				if spot[0] < 0:
					print('no room')
					return
			origin.exhausted = True
		else:
			spot = origin.tile
			spr.exhausted = True
		assert spot is not None
		self.civs[self.active_civ].population.append(spr)
		if origin.is_building():
			# animate
			spr.set_tile_and_pos(origin.tile, self.terr)
			dest_x, dest_y = self.terr.tile_to_pixel(spot[0], spot[1])
			self.animating_sprite = spr
			self.animating_sprite.start_animation((dest_x, dest_y + 149), sprite.Animation.move, lambda: self.animating_sprite.set_tile_and_pos(spot, self.terr)) # type: ignore
			self.animating_sprite.exhausted = True
		else:
			# just appear
			spr.set_tile_and_pos(spot, self.terr)
			self.update_canvas()

	def change_perspective(self) -> None:
		self.update_canvas()
		self.save_game()
		if len(self.civs) > 1:
			self.message = 'Player ' + str(self.active_civ + 1) + ', get ready!'
			civ = self.civs[self.active_civ]
			if civ.human and 'civs' in civ.last_state:
				self.history_pos = civ.last_history_pos - 1 # the -1 is because 'update' is about to increment it
				state = civ.last_state
				civ.last_state = {}
				self.unmarshall(state)
				self.replay = True
			else:
				print('no replay for civ ' + str(self.active_civ) + '. human? ' + str(civ.human) + ', backup? ' + str('civs' in civ.last_state))

	def do_action(self, act: Action) -> None:
		civ = self.civs[self.active_civ]
		doer: sprite.Sprite = civ.population[act.doer]
		# if self.replay:
		# 	print('    ', end='')
		# print('Civ ' + str(self.active_civ) + ' tile ' + str(doer.tile) + ' action ' + str(act.descr) + ', history_pos=' + str(self.history_pos))
		if act.descr == 'End':
			for spr in civ.population:
				spr.exhausted = False
			prev_civ = self.active_civ
			while True:
				self.active_civ += 1
				if self.active_civ >= len(self.civs):
					self.active_civ = 0
				civ.start_turn(self.civs, self.active_civ)
				if civ.alive:
					break
			self.perspective_civ = self.active_civ
			if len(self.civs) > 1 and not self.replay:
				state = self.marshall()
				self.civs[prev_civ].set_last_state(state, len(self.history))
			if self.display_mode and not self.replay:
				self.change_perspective()
		elif act.descr == 'move':
			assert act.target
			tx, ty = self.terr.tile_to_pixel(act.target[0], act.target[1])
			self.targets.clear()
			self.menu.clear()
			self.animating_sprite = doer
			self.animating_sprite.on_water(self.terr.tile(act.target) == 1)
			if self.terr.tile(self.animating_sprite.tile) != 1 and self.terr.tile(act.target) == 1:
				civ.wood -= 1
			self.animating_sprite.start_animation((tx, ty + 149), sprite.Animation.move, lambda: self.animating_sprite.set_tile_and_pos(act.target, self.terr)) # type: ignore
			self.animating_sprite.exhausted = True
		elif act.descr == 'attack':
			assert act.target
			opponent = self.find_opponent(act.target)
			assert opponent is not None
			tx, ty = self.terr.tile_to_pixel(act.target[0], act.target[1])
			self.targets.clear()
			self.menu.clear()
			self.animating_sprite = doer
			if opponent.is_creature():
				if self.animating_sprite.get_attack_strength() >= opponent.life:
					self.animating_sprite.start_animation((tx, ty + 149), sprite.Animation.kill, lambda: self.kill_opponent(self.animating_sprite, opponent), opponent) # type: ignore
				else:
					self.animating_sprite.start_animation((tx, ty + 149), sprite.Animation.strike, lambda: self.animating_sprite.strike_opponent(opponent, self.animating_sprite.tile, self.terr)) # type: ignore
			else:
				self.animating_sprite.start_animation((tx, ty + 149), sprite.Animation.strike, lambda: self.capture_opponent(self.animating_sprite, opponent), opponent) # type: ignore
			self.animating_sprite.exhausted = True
		elif act.descr == 'gnome':
			if civ.food >= 2:
				civ.food -= 2
				self.spawn_sprite(doer, sprite.Gnome())
		elif act.descr == 'dwarf':
			if civ.food >= 3:
				civ.food -= 3
				self.spawn_sprite(doer, sprite.Dwarf())
		elif act.descr == 'elf':
			if civ.gold >= 2:
				civ.gold -= 2
				self.spawn_sprite(doer, sprite.Elf())
		elif act.descr == 'dragon':
			if civ.gold >= 13:
				civ.gold -= 13
				self.spawn_sprite(doer, sprite.Dragon())
		elif act.descr == 'fort':
			if civ.wood >= 5:
				civ.wood -= 5
				doer.upgrade() # type: ignore
				self.update_canvas()
		elif act.descr == 'castle':
			if civ.wood >= 8:
				civ.wood -= 8
				doer.upgrade() # type: ignore
				self.update_canvas()
		elif act.descr == 'hut':
			if civ.wood >= 1:
				civ.wood -= 1
				assert doer is not None
				self.spawn_sprite(doer, sprite.Building())
				civ.population.remove(doer)
				self.update_canvas()
		elif act.descr == 'chop':
			land_tile = self.terr.random_tile([3])
			if land_tile is not None:
				self.terr.set_tile(land_tile, 2) # grow new forest on random land tile
			assert doer is not None
			doer.exhausted = True
			self.terr.set_tile(doer.tile, 3) # change this forest tile to land
			civ.wood += 3
			self.update_canvas()
		elif act.descr == 'plant':
			assert doer is not None
			doer.exhausted = True
			self.terr.set_tile(doer.tile, 2) # change this land tile to forest
			self.update_canvas()
		elif act.descr == 'farm':
			if civ.wood >= 2:
				civ.wood -= 2
				assert doer is not None
				self.spawn_sprite(doer, sprite.Farm())
				civ.population.remove(doer)
				self.update_canvas()
		elif act.descr == 'trebuchet':
			if civ.gold >= 3:
				civ.gold -= 3
				assert doer is not None
				self.spawn_sprite(doer, sprite.Trebuchet())
				civ.population.remove(doer)
		elif act.descr == 'mine':
			if civ.wood >= 3:
				civ.wood -= 3
				assert doer is not None
				self.spawn_sprite(doer, sprite.Mine())
				civ.population.remove(doer)
		else:
			raise ValueError('Unrecognized action: ' + act.descr)

	def clear_selection(self) -> None:
		self.targets.clear()
		self.menu.clear()
		self.selected_sprite = None
		self.selected_index = -1

	def move_pointer(self, pos: Tuple[int, int]) -> None:
		tx, ty = self.terr.pixel_to_tile(pos[0], pos[1] - 149)
		px, py = self.terr.tile_to_pixel(tx, ty)
		self.pointer.tile = (tx, ty)
		self.pointer.pos = (px, py + 149 + 10)
		self.clear_selection()

	def kill_opponent(self, attacker: sprite.Sprite, victim: sprite.Sprite) -> None:
		attacker.set_tile_and_pos(victim.tile, self.terr)
		attacker.life += 1
		victim.life = 0
		for civ in self.civs:
			if victim in civ.population:
				civ.population.remove(victim)

	def capture_opponent(self, attacker: sprite.Sprite, victim: sprite.Sprite) -> None:
		attacker.set_tile_and_pos(attacker.tile, self.terr)
		for civ in self.civs:
			if victim in civ.population:
				civ.population.remove(victim)
		self.civs[self.active_civ].population.append(victim)
		self.update_canvas()

	def select_sprite(self, s: sprite.Sprite, index: int) -> None:
		self.move_pointer(s.pos)
		self.selected_sprite = s
		self.selected_index = index
		if index >= 0 and not s.exhausted:
			# Make target sprites
			self.targets.clear()
			tt = targeter.Targeter(self.terr, self.civs)
			move_targets = tt.get_move_targets(
				s.tile,
				self.terr,
				s.move_range(),
				s.can_fly() or self.civs[self.active_civ].wood >= 1,
				s.can_fly(),
				)
			for targ in move_targets:
				t: sprite.Sprite = sprite.TargetMove()
				t.set_tile_and_pos(targ.tile, self.terr)
				self.targets.append(t)
			attack_targets = tt.get_attack_targets(
				s.tile,
				self.terr,
				s.attack_range(),
				self.active_civ,
				s.can_shoot(),
				)
			for targ in attack_targets:
				t = sprite.TargetAttack()
				t.set_tile_and_pos(targ.tile, self.terr)
				self.targets.append(t)

			# Make menu buttons
			self.menu.clear()
			y = 75
			for opt in s.menu_options(self.terr.tile(s.tile)):
				self.menu.append(sprite.Button((125, y), opt))
				y += 75

	def on_mouse_down(self, pos: Tuple[int, int]) -> None:
		if len(self.message) > 0:
			return
		if self.animating_sprite is not None:
			self.animating_sprite.stop_animation()
		s, index = self.find_sprite(pos)
		if s is None:
			self.selected_sprite = None
			self.selected_index = -1
			self.targets.clear()
			self.menu.clear()
			self.move_pointer(pos)
		else:
			s.on_mouse_down()
			if s is not self.selected_sprite:
				if s.is_button():
					self.pushed_button = s # type: ignore
				elif s.is_move_target():
					self.history.append(Action('move', self.selected_index, s.tile))
				elif s.is_attack_target():
					self.history.append(Action('attack', self.selected_index, s.tile))
				else:
					self.select_sprite(s, index)

	def on_mouse_up(self, pos: Tuple[int, int]) -> None:
		if len(self.message) > 0:
			self.message = ''
			return
		s, index = self.find_sprite(pos)
		if s is not None:
			if s is self.pushed_button:
				n = s.text.find(' ') # type: ignore
				descr = s.text if n < 0 else s.text[:n] # type: ignore
				prev_player = self.active_civ
				self.history.append(Action(descr, self.selected_index, None))
				self.pushed_button.on_mouse_up()
				self.pushed_button = None
				self.clear_selection()

		# Ensure that any other buttons are released
		if self.pushed_button is not None:
			self.pushed_button.on_mouse_up()
			self.pushed_button = None
			self.clear_selection()

	def on_mouse_move(self, pos: Tuple[int, int]) -> None:
		if self.selected_sprite is None:
			self.move_pointer(pos)

	def on_key_press(self, dx: int, dy: int) -> None:
		tx, ty = self.pointer.tile
		tx = max(0, min(15, tx + dx))
		ty += max(0, min(15, ty + dy))
		px, py = self.terr.tile_to_pixel(tx, ty)
		self.pointer.tile = (tx, ty)
		self.pointer.pos = (px, py + 149 + 10)
		self.clear_selection()


class View(mvc.View):
	font = pygame.font.Font('freesansbold.ttf', 24)

	def __init__(self, model: Model) -> None:
		super().__init__(model)
		self.dirty = True
		self.model = model
		self.model.update_canvas()

	def update(self) -> None:
		if not self.dirty:
			return
		elif len(self.model.message) > 0:
			# Display message
			self.screen.fill([64, 200, 128])
			text_image = View.font.render(self.model.message, True, (0, 0, 0))
			tr = text_image.get_rect()
			l = 776 - (tr[2] - tr[0]) // 2
			t = 400
			r = (l, t, l + tr[2] - tr[0], t + tr[3] - tr[1])
			self.screen.blit(text_image, r)
		else:
			# Game play
			self.screen.fill([0, 0, 0])
			self.screen.blit(self.model.canvas, (0, 149, 1552, 873))
			sprites = self.model.sorted_visible_sprites()
			self.model.pointer.draw_back(self.screen)
			for s in sprites:
				s.draw(self.screen)
			for s in self.model.targets:
				s.draw(self.screen)
			for s in self.model.menu:
				s.draw(self.screen)
			for s in self.model.control:
				s.draw(self.screen)
			self.model.civs[self.model.perspective_civ].draw_resources(self.screen)
			if self.model.selected_sprite is not None and self.model.selected_sprite.is_creature():
				self.model.selected_sprite.draw_life(self.screen) # type: ignore
			self.model.pointer.draw(self.screen)
		pygame.display.flip()
		self.dirty = False

class Controller(mvc.Controller):
	def __init__(self, num_civs: int) -> None:
		self.model = Model()
		if num_civs == 0:
			self.model.load_game()
		else:
			self.model.start_game(num_civs)
		self.view = View(self.model)
		super().__init__(self.view)

	def update(self) -> None:
		for event in pygame.event.get():
			if event.type == pg.QUIT:
				self.keep_going = False
			elif event.type == pg.KEYDOWN:
				if event.key == pg.K_ESCAPE:
					self.keep_going = False
			elif event.type == pygame.MOUSEBUTTONDOWN:
				self.view.dirty = True
				self.model.on_mouse_down(pygame.mouse.get_pos())
			elif event.type == pygame.MOUSEBUTTONUP:
				self.view.dirty = True
				self.model.on_mouse_up(pygame.mouse.get_pos())
			elif event.type == pygame.MOUSEMOTION:
				mx, my = pygame.mouse.get_pos()
				self.view.dirty = True
				self.model.on_mouse_move(pygame.mouse.get_pos())
		keys = pygame.key.get_pressed()
		dx = (1 if keys[pg.K_RIGHT] else 0) - (1 if keys[pg.K_LEFT] else 0)
		dy = (1 if keys[pg.K_DOWN] else 0) - (1 if keys[pg.K_UP] else 0)
		if dx != 0 or dy != 0:
			self.view.dirty = True
			self.model.on_key_press(dx, dy)
