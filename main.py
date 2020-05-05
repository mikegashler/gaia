from typing import Tuple, List, Optional
import mvc
import pygame
import pygame.locals as pg
import time
import terrain
import civ
import cv2
import numpy as np
import image
import sprite
import gaia

class Model(mvc.Model):
	def __init__(self) -> None:
		self.sprites: List[sprite.Sprite] = []
		self.sprites.append(sprite.Button((200, 100), 'Load'))
		self.sprites.append(sprite.Button((800, 300), '1 Player'))
		self.sprites.append(sprite.Button((800, 400), '2 Players Hot Seat'))
		self.sprites.append(sprite.Button((800, 500), '3 Players Hot Seat'))
		self.sprites.append(sprite.Button((800, 600), '4 Players Hot Seat'))

	def update(self) -> bool:
		return False

	def find_sprite(self, pos: Tuple[int, int]) -> Optional[sprite.Sprite]:
		d = 100000000
		s: Optional[sprite.Sprite] = None
		for spr in self.sprites:
			r = spr.rect()
			if pos[0] >= r[0] and pos[1] >= r[1] and pos[0] < r[2] and pos[1] < r[3]:
				dd = (spr.pos[0] - pos[0]) ** 2 + (spr.pos[1] - pos[1]) ** 2
				if dd < d:
					d = dd
					s = spr
		return s

	def do_action(self, action: str) -> None:
		if action == 'Load':
			c = gaia.Controller(0)
			c.run()
		elif action == '1 Player':
			c = gaia.Controller(1)
			c.run()
		elif action == '2 Players Hot Seat':
			c = gaia.Controller(2)
			c.run()
		elif action == '3 Players Hot Seat':
			c = gaia.Controller(3)
			c.run()
		elif action == '4 Players Hot Seat':
			c = gaia.Controller(4)
			c.run()
		else:
			raise ValueError('Unrecognized action: ' + action)

class View(mvc.View):
	def __init__(self, model: Model) -> None:
		self.model = model
		super().__init__(model)

	def update(self) -> None:
		self.screen.fill([130, 180, 200])
		for s in self.model.sprites:
			s.draw(self.screen)
		pygame.display.flip()

class Controller(mvc.Controller):
	def __init__(self) -> None:
		self.model = Model()
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
				mpos = pygame.mouse.get_pos()
				s = self.model.find_sprite(mpos)
				if s:
					s.on_mouse_down()
			elif event.type == pygame.MOUSEBUTTONUP:
				mpos = pygame.mouse.get_pos()
				s = self.model.find_sprite(mpos)
				if s:
					s.on_mouse_up()
					if s.is_button():
						self.model.do_action(s.text) # type: ignore
			elif event.type == pygame.MOUSEMOTION:
				pass
		keys = pygame.key.get_pressed()

c = Controller()
c.run()
