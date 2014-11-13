""" bomber.py

a bomberman clone server.

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
    time_per_frame = 1 / 30

    while True:
        # 30 frames per second, considering computation/drawing time
        yield from asyncio.sleep(last + time_per_frame - now)
        last, now = now, time.time()
        dt = now - last
        if ui.single_loop_run(dt*1000):
            return


def main(arguments):
    # init async and pygame
    loop = asyncio.get_event_loop()
    ui.init("bomber", (900, 700))

    # show loading scene
    ui.scene.push(LoadingScene())
    map_scene = MapScene(Map(ui.Rect(10, 10, 490, 490)))
    ui.scene.insert(0, map_scene)

    gameserver = Server(level=map_scene.map)
    asyncio.async(gameserver.run_server())

    from bomber.network import ClientStub
    loop.call_soon(map_scene.map.player_register, ClientStub(None, None, map_scene.map))

    # show game ui
    ui.scene.pop()
    try:
        loop.run_until_complete(main_loop(loop))
    finally:
        loop.close()


if __name__ == "__main__":
    arguments = docopt(__doc__, version='bomber 0.1')
    main(arguments)
