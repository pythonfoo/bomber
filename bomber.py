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
        self.on_message = ui.callback.Signal()

    def inform(self, msg_type, args):
        self.writer.write(msgpack.packb((msg_type, args)))

    def handle_msg(self, msg):
        self.on_message(msg)


class Server:

    """
    took the structure from
    https://github.com/Mionar/aiosimplechat
    it was MIT licenced
    """
    clients = {}
    server = None

    def __init__(self, host='*', port=8001, level=None):
        self.host = host
        self.port = port
        self.level = level
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
        print("hallo {}".format(peername))
        new_client = ClientStub(reader, writer)
        position = self.level.player_register(new_client)
        self.clients[peername] = new_client
        # self.send_to_client(peername, 'Welcome {}'.format(peername))
        unpacker = msgpack.Unpacker(encoding='utf-8')
        while not reader.at_eof():
            try:
                pack = yield from reader.read(1024)
                unpacker.feed(pack)
                for msg in unpacker:
                    new_client.handle_msg(msg)
            except ConnectionResetError as e:
                print('ERROR: {}'.format(e))
                del self.clients[peername]
                self.level.player_unregister(position)
                return
            except Exception as e:
                error = 'ERROR: {}'.format(e)
                print(error)
                self.send_to_client(peername, error)
                new_client.writer.write_eof()
                del self.clients[peername]
                self.level.player_unregister(position)
                return

    def close(self):
        self.send_to_all_clients("bye\n")
        self.close_clients()


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


class Player:

    def __init__(self, position, client, name="Hans", color=None, password="", id=None, map=None):
        x, y = position
        # TODO use a real hash
        hashpassword = lambda x: x

        # TODO don't use 10 as a fixed value for map raster
        self.frame = ui.Rect(x * 10, y * 10, 10, 10)
        self._top = float(self.frame.top)
        self._left = float(self.frame.left)
        self.name = name
        self.client = client
        self.color = {
            "1": (0x80, 0, 0),      # red
            "2": (0, 0, 255),       # blue
            "3": (255, 255, 255),   # white
            "4": (0xFF, 0x66, 0),   # orange
            "5": (0, 0x80, 0),      # green
            "6": (0x55, 0x22, 0),   # brown
            "7": (0x80, 0, 0x80),   # purple
            "8": (255, 255, 0),     # yellow
        }[color]
        self.password = hashpassword(password)
        self.speed = 10.
        self.bombamount = 0
        self.explosion_radius = 1
        self.moving = 0
        self.direction = "w"        # North
        self.id = id
        self.map = map
        client.on_message.connect(self.handle_msg)

    def handle_msg(self, msg):
        if msg["type"] == "move":
            self.move(msg["direction"])
        elif msg["type"] == "whoami":
            self.client.inform("OK", [self.color, self.id, self._top, self._left])
        elif msg["type"] == "whoami":
            self.client.inform("OK", self.get_map(),)

    def move(self, direction):
        assert direction in "wasd"
        self.direction = direction
        self.moving = 1.

    def update(self, dt):
        if not self.moving > 0:
            return
        time_to_move = min(dt, self.moving)
        self.moving -= time_to_move
        distance = time_to_move * self.speed

        top, left = {
            "w": (-1, 0),
            "a": (0, -1),
            "s": (1, 0),
            "d": (0, 1),
        }[self.direction]

        self._top += top * distance
        self._left += left * distance

        if self._top < 0.:
            self._top = 0
            self.moving = 0
        if self._left < 0.:
            self._left = 0
            self.moving = 0
        if self._top > 490.:
            self._top = 490
            self.moving = 0
        if self._left > 490.:
            self._left = 490
            self.moving = 0
        self.frame.top = self._top
        self.frame.left = self._left
        if not self.map.frame.contains(self.frame):
            self.moving = 0



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

        spawnpoints = []
        freespawnpoints = []

        self.walls = []
        self.items = []
        self.players = []
        self.spawnpoints = {}

        for y, line in enumerate(lines):
            for x, (attr, block) in enumerate(feedblock(line)):
                # TODO don't use 10 as a fixed value for map raster
                frame = ui.Rect(x * 10, y * 10, 10, 10)
                if block == "W":
                    self.walls.append(DestructableWall(frame))
                elif block == "M":
                    self.walls.append(IndestructableWall(frame))
                elif block == "S":
                    # this is a spawn point
                    # attr is the start position
                    self.spawnpoints[attr] = (x, y)
                    freespawnpoints.append(attr)

        self.freespawnpoints = sorted(freespawnpoints, reverse=True)

        self.on_player_join = ui.callback.Signal()
        self.on_player_leave = ui.callback.Signal()

        # self.on_keydown.register(self.keydown)

    def key_down(self, key, code):
        if not self.players:
            return
        if code.lower() == "w":
            self.players[0].move("w")
        elif code.lower() == "a":
            self.players[0].move("a")
        elif code.lower() == "s":
            self.players[0].move("s")
        elif code.lower() == "d":
            self.players[0].move("d")

    def player_register(self, client):
        try:
            position = self.freespawnpoints.pop()
        except StopIteration as e:
            return False

        # TODO create player View/ convert client to player
        player = Player(
            position=self.spawnpoints[position],
            client=client,
            color=position,
            id=position,
            map=self
        )
        self.players.append(player)
        return position

    def player_unregister(self, position):
        np = [p for p in self.players if p.id != position]
        if len(self.players) > len(np):
            self.players = np
            self.freespawnpoints.append(position)

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

    def update(self, dt):
        for player in self.players:
            player.update(dt)


class MapScene(ui.Scene):

    def __init__(self):
        super().__init__()
        self.map = Map(ui.Rect(10, 10, 500, 500))
        self.add_child(self.map)


def handle_msg(msg):
    user = msg["user"]
    pos = msg["x"], msg["y"]
    color = msg["color"]


if __name__ == "__main__":
    arguments = docopt(__doc__, version='bomber 0.1')

    loop = asyncio.get_event_loop()
    ui.init("bomber", (900, 700))
    ui.scene.push(LoadingScene())
    map_scene = MapScene()
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
