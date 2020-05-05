import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from abc import abstractmethod
import time

pygame.init()

class Model():
	@abstractmethod
	def update(self) -> bool:
		raise NotImplementedError('stub')


class View():
	screen_width = 1552
	screen_size = (screen_width, screen_width * 9 // 16)
	icon = pygame.image.load("pics/game/icon.png")
	pygame.display.set_caption('Gaia')
	pygame.display.set_icon(icon)
	screen = pygame.display.set_mode(screen_size, pygame.DOUBLEBUF | pygame.HWSURFACE, 32)

	def __init__(self, model: Model) -> None:
		self._model = model

	@abstractmethod
	def update(self) -> None:
		raise NotImplementedError('stub')


class Controller():
	def __init__(self, view: View) -> None:
		self._model = view._model
		self._view = view
		self.keep_going = True

	@abstractmethod
	def update(self) -> None:
		raise NotImplementedError('stub')

	def run(self) -> None:
		while self.keep_going:
			self.update()
			if self._model.update():
				self._view.dirty = True # type: ignore
			self._view.update()
			time.sleep(0.05)
