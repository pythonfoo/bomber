import re
import random
import pygameui as ui


TILE_WIDTH = 10
TILE_HEIGHT = 10

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
        self.frame = ui.Rect(x * TILE_WIDTH, y * TILE_HEIGHT, TILE_WIDTH, TILE_HEIGHT)
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
        elif msg["type"] == "map":
            self.client.inform("OK", self.get_map(),)

    def move(self, direction):
        assert direction in "wasd"
        self.direction = direction
        self.moving = 1.

    def update(self, dt):
        # print (self.moving)
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

        # print("dt:{}, t:{}, l:{}, d:{}, m:{}".format(dt, self._top, self._left, distance, self.moving))
        self._top += top * distance
        self._left += left * distance

        if self._top < 0.:
            self._top = 0
            self.moving = 0
        if self._left < 0.:
            self._left = 0
            self.moving = 0
        if self._top > 480.:
            self._top = 480
            self.moving = 0
        if self._left > 480.:
            self._left = 480
            self.moving = 0
        # print("dt:{}, t:{}, l:{}, d:{}, m:{}".format(dt, self._top, self._left, distance, self.moving))
        self.frame.top = self._top
        self.frame.left = self._left
        # if not self.map.frame.contains(self.frame):
        #     self.moving = 0



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


