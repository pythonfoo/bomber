""" bomber.py

a little server where you can send commands to paint a specific pixel.

Usage:

    bomber.py
"""
import pygame
import asyncio
import time
import msgpack
import pygameui as ui
import re
import random
from docopt import docopt


class ClientStub:

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.peername = None

    def inform(self, msg_type, args):
        self.writer.write(msgpack.packb((msg_type, args)))


class Server:

    """
    took the structure from
    https://github.com/Mionar/aiosimplechat
    it was MIT licenced
    """
    clients = {}
    server = None

    def __init__(self, host='localhost', port=8001):
        self.host = host
        self.port = port
        self.clients = {}

    @asyncio.coroutine
    def run_server(self):
        try:
            self.server = yield from asyncio.start_server(
                self.client_connected,
                self.host, self.port
            )
            print('Running server on {}:{}'.format(self.host, self.port))
        except OSError:
            print('Cannot bind to this port! Is the server already running?')

    def send_to_client(self, peername, msg):
        client = self.clients[peername]
        client.writer.write(msgpack.packb(msg))
        return

    def send_to_all_clients(self, msg):
        for peername in self.clients.keys():
            self.send_to_client(peername, msg)
        return

    def close_clients(self):
        for peername, client in self.clients.items():
            client.writer.write_eof()

    @asyncio.coroutine
    def client_connected(self, reader, writer):
        peername = writer.transport.get_extra_info('peername')
        new_client = ClientStub(reader, writer)
        self.clients[peername] = new_client
        # self.send_to_client(peername, 'Welcome {}'.format(peername))
        unpacker = msgpack.Unpacker(encoding='utf-8')
        while not reader.at_eof():
            try:
                pack = yield from reader.read(1024)
                unpacker.feed(pack)
                for msg in unpacker:
                    handle_msg(msg)
            except ConnectionResetError as e:
                print('ERROR: {}'.format(e))
                del self.clients[peername]
                return
            except Exception as e:
                error = 'ERROR: {}'.format(e)
                print(error)
                self.send_to_client(peername, error)
                new_client.writer.write_eof()
                del self.clients[peername]
                return

    def close(self):
        self.send_to_all_clients("bye\n")
        self.close_clients()


@asyncio.coroutine
def main_loop(loop):
    now = last = time.time()
    time_per_frame = 1 / 30

    while True:
        # 30 frames per second, considering computation/drawing time
        yield from asyncio.sleep(last + time_per_frame - now)
        last, now = now, time.time()
        dt = now - last
        if ui.single_loop_run(dt):
            return


class LoadingScene(ui.Scene):

    def __init__(self):
        super().__init__()

        label = ui.label.Label(self.frame, "Loading ...")
        label.text_color = (0, 250, 0)
        # label.layout()
        self.add_child(label)


def feedblock(line):
    while line:
        attr, block, line = line[0], line[1], line[2:]
        yield attr, block


class Wall:

    hidden = False
    color = (100, 100, 100)

    def __init__(self, frame):
        self.frame = frame


class DestructableWall(Wall):

    color = (200, 100, 100)


class IndestructableWall(Wall):
    pass


class Map(ui.View):

    def __init__(self, frame):
        super().__init__(frame)

        with open("simple.map") as fh:
            mapdata = fh.read()

        def rand_wall(match):
            if random.random() < 0.6:
                return " W"
            return match.group()

        mapdata = re.sub(r" ( )", rand_wall, mapdata)
        lines = mapdata.splitlines()

        self.walls = []
        self.items = []
        self.players = []

        for y, line in enumerate(lines):
            for x, (attr, block) in enumerate(feedblock(line)):
                frame = ui.Rect(x * 10, y * 10, 10, 10)
                if block == "W":
                    self.walls.append(DestructableWall(frame))
                elif block == "M":
                    self.walls.append(IndestructableWall(frame))

    def draw(self):
        if not super().draw():
            return False
        ui.render.fillrect(self.surface,
            [(173, 222, 78), (153, 202, 58)],
            ui.Rect(0, 0, self.frame.w, self.frame.h)
        )

        # draw walls
        for wall in self.walls:
            ui.render.fillrect(self.surface, wall.color, wall.frame)

        # draw items
        for item in self.items:
            ui.render.fillrect(self.surface, item.color, item.frame)

        # draw player
        for player in self.players:
            ui.render.fillrect(self.surface, player.color, player.frame)
        return True


class MapScene(ui.Scene):

    def __init__(self):
        super().__init__()
        self.map = Map(ui.Rect(10, 10, 500, 500))
        self.add_child(self.map)


def handle_msg(msg):
    user = msg["user"]
    pos = msg["x"], msg["y"]
    color = msg["color"]
    pygame.draw.line(screen, color, pos, pos)


if __name__ == "__main__":
    arguments = docopt(__doc__, version='bomber 0.1')

    loop = asyncio.get_event_loop()
    ui.init("bomber", (900, 700))
    ui.scene.push(LoadingScene())
    ui.scene.insert(0, MapScene())
    # screen = pygame.display.set_mode((900, 700))
    if not arguments.get('--connect'):
        gameserver = Server()
        asyncio.async(gameserver.run_server())

    try:
        loop.run_until_complete(main_loop(loop))
    finally:
        loop.close()