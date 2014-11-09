""" bomber.py

a little server where you can send commands to paint a specific pixel.

Usage:

    bomber.py
"""
import asyncio
import time
import pygameui as ui
from docopt import docopt
from bomber.scenes import LoadingScene, MapScene
from bomber.network import Server
from bomber.engine import Map

@asyncio.coroutine
def main_loop(loop):
    now = last = time.time()
    time_per_frame = 1 / 5

    while True:
        # 30 frames per second, considering computation/drawing time
        yield from asyncio.sleep(last + time_per_frame - now)
        last, now = now, time.time()
        dt = now - last
        if ui.single_loop_run(dt*1000):
            return


if __name__ == "__main__":
    arguments = docopt(__doc__, version='bomber 0.1')

    loop = asyncio.get_event_loop()
    ui.init("bomber", (900, 700))
    ui.scene.push(LoadingScene())
    map_scene = MapScene(Map(ui.Rect(10, 10, 500, 500)))
    ui.scene.insert(0, map_scene)
    # screen = pygame.display.set_mode((900, 700))
    if not arguments.get('--connect'):
        gameserver = Server(level=map_scene.map)
        asyncio.async(gameserver.run_server())

    # map_scene.map.player_register(ClientStub(None, None))
    ui.scene.pop()
    try:
        loop.run_until_complete(main_loop(loop))
    finally:
        loop.close()
