import re
import random
import pygameui as ui
from itertools import chain


TILE_WIDTH = 10
TILE_HEIGHT = 10


def feedblock(line):
    while line:
        attr, block, line = line[0], line[1], line[2:]
        yield attr, block


def first(iterator):
    for elem in iterator:
        return elem


class MapObject:

    hidden = False
    color = (100, 100, 100)

    def __init__(self, frame):
        self.frame = frame

    @property
    def position_int(self):
        return (round(self.frame.left / TILE_WIDTH), round(self.frame.top / TILE_HEIGHT))

    @property
    def position_float(self):
        return (round(self.frame.left / TILE_WIDTH, 1), round(self.frame.top / TILE_HEIGHT, 1))


class Bomb(MapObject):

    def __init__(self, player, fuse_time, position):

        x, y = position
        frame = ui.Rect(
            x * TILE_WIDTH,
            y * TILE_HEIGHT,
            TILE_WIDTH,
            TILE_HEIGHT
        )
        super().__init__(frame)
        self.player = player
        self.fuse_time = fuse_time
        self.burn_time = 1.
        self._state = "ticking"
        self.color = (10, 10, 10)
        self.explosion_radius = player.explosion_radius
        self.hidden = False

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        state_transitions = {
            "ticking": ["exploding", "burning"],
            "exploding": ["burning"],
            "burning": [],
        }

        assert value in state_transitions[self._state]

        if self._state != value:
            self._state = value
            self.on_new_state(value)

    def on_new_state(self, state):
        if state == "burning" or state == "exploding":
            self.color = (255, 255, 230)

    def update(self, dt):
        if self.state == "ticking":
            time_to_tick = min(dt, self.fuse_time)
            dt -= time_to_tick
            self.fuse_time -= time_to_tick
            if self.fuse_time <= 0:
                self.state = "exploding"

        if self.state == "exploding":
            time_to_burn = min(dt, self.burn_time)
            self.burn_time -= time_to_burn
            if self.burn_time <= 0:
                self.hidden = True


class Wall(MapObject):
    pass


class DestructableWall(Wall):

    color = (200, 100, 100)
    destructable = True


class IndestructableWall(Wall):

    color = (100, 100, 100)
    destructable = False


COLLIDING_OBJECTS = (IndestructableWall, Bomb)


class Player:

    # TODO change orientation,
    # ui.Rect uses left, top
    # this uses top, left

    directions = {
        "w": (-1, 0),
        "a": (0, -1),
        "s": (1, 0),
        "d": (0, 1),
    }

    def __init__(self, position, client, name="Hans", color=None, password="", id=None, map=None):
        x, y = position
        # TODO use a real hash
        hashpassword = lambda x: x

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
        self.bombamount = 1
        self.explosion_radius = 1
        self.moving = 0             # unit pixel
        self.direction = "w"        # North
        self.id = id
        self.map = map
        client.on_message.connect(self.handle_msg)

    @property
    def position_int(self):
        return (round(self.frame.left / TILE_WIDTH), round(self.frame.top / TILE_HEIGHT))

    @property
    def next_position_int(self):
        top, left = self.directions[self.direction]
        x, y = self.position_int
        return x + left, y + top

    @property
    def position_float(self):
        return (round(self.frame.left / TILE_WIDTH, 1), round(self.frame.top / TILE_HEIGHT, 1))

    @property
    def delta_position_distance(self):
        x, y = self.position_int
        x *= TILE_WIDTH
        y *= TILE_HEIGHT
        return abs(x - self._left) + abs(y - self._top)

    def get_direction_to_int_position(self):
        xi, yi = self.position_int
        xf, yf = self.position_float

        if xf > xi:
            return "a"
        elif xf < xi:
            return "d"
        elif yf > yi:
            return "w"
        elif yf < yi:
            return "s"

    def handle_msg(self, msg):
        if msg["type"] == "move":
            self.move(msg["direction"])
        elif msg["type"] == "whoami":
            self.client.inform("OK", [self.color, self.id, self._top, self._left])
        elif msg["type"] == "map":
            self.client.inform("OK", self.get_map(),)
        elif msg["type"] == "bomb":
            self.bomb()

    def move(self, direction, distance=10.):
        assert direction in "wasd"
        self.direction = direction
        self.moving = distance

    def bomb(self):
        self.map.plant_bomb(self)

    def update(self, dt):
        if not self.moving > 0:
            return

        distance = min(dt * self.speed, self.moving)
        self.moving -= distance

        top, left = self.directions[self.direction]

        _top = self._top + (top * distance)
        _left = self._left + (left * distance)

        # collision detection with map border
        if _top < 0:
            _top = 0
            self.moving = 0
        if _left < 0:
            _left = 0
            self.moving = 0
        if _top > (self.map.frame.height - TILE_HEIGHT):
            _top = (self.map.frame.height - TILE_HEIGHT)
            self.moving = 0
        if _left > (self.map.frame.width - TILE_WIDTH):
            _left = (self.map.frame.width - TILE_WIDTH)
            self.moving = 0

        # collision detection with walls
        frame = ui.Rect(_left, _top, TILE_WIDTH, TILE_HEIGHT)   # possible new position
        collision_frame = ui.Rect(
            min(self.frame.left, frame.left),
            min(self.frame.top, frame.top),
            abs(self.frame.left - frame.left) + TILE_WIDTH,
            abs(self.frame.top - frame.top) + TILE_HEIGHT,
        )

        # TODO it is the jurisdiction of Map to tell the Player about colliding walls
        # Now it is even more complicated to move this to the Map object
        # because it cannot inlcude objects that are placed on

        collisions = [wall for wall in chain(self.map.walls, self.map.items)
            if isinstance(wall, COLLIDING_OBJECTS) and collision_frame.colliderect(wall.frame)
                and not self.frame.colliderect(wall.frame)]
        if collisions:
            # TODO send info to client

            collision = True
            if self.direction == "w":
                # get the lowest box
                collisions = sorted(collisions, key=lambda x: x.frame.top, reverse=True)
                collider = [c for c in collisions if c.position_int == self.next_position_int]
                if collider:
                    frame.top = collisions[0].frame.bottom
                    _top = frame.top
                else:
                    # no valid collision
                    collision = False

            elif self.direction == "a":
                # get the box farest right
                collisions = sorted(collisions, key=lambda x: x.frame.left, reverse=True)
                collider = [c for c in collisions if c.position_int == self.next_position_int]
                if collider:
                    frame.left = collisions[0].frame.right
                    _left = frame.left
                else:
                    # no valid collision
                    collision = False

            elif self.direction == "s":
                # get the highest box
                collisions = sorted(collisions, key=lambda x: x.frame.top)
                collider = [c for c in collisions if c.position_int == self.next_position_int]
                if collider:
                    frame.bottom = collisions[0].frame.top
                    _top = frame.top
                else:
                    # no valid collision
                    collision = False

            elif self.direction == "d":
                # get the box farest left
                collisions = sorted(collisions, key=lambda x: x.frame.left)
                collider = [c for c in collisions if c.position_int == self.next_position_int]
                if collider:
                    frame.right = collisions[0].frame.left
                    _left = frame.left
                else:
                    # no valid collision
                    collision = False

            if collision:
                self.moving = 0
            else:
                offset_distance = min(self.delta_position_distance, distance)
                distance -= offset_distance
                new_direction = self.get_direction_to_int_position()
                if new_direction:
                    top_offset, left_offset = self.directions[new_direction]
                    _top = self._top + (top_offset * offset_distance)
                    _left = self._left + (left_offset * offset_distance)
                    if distance > 0:
                        _top += top * distance
                        _left += left * distance

        self.frame.top = self._top = _top
        self.frame.left = self._left = _left


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
            self.players[0].move("w", 1)
        elif code.lower() == "a":
            self.players[0].move("a", 1)
        elif code.lower() == "s":
            self.players[0].move("s", 1)
        elif code.lower() == "d":
            self.players[0].move("d", 1)
        elif code.lower() == "b":
            self.players[0].bomb()

    def player_register(self, client):
        try:
            position = self.freespawnpoints.pop()
        except StopIteration as e:
            return False

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

    def plant_bomb(self, player):
        bombs = [b for b in self.items if isinstance(b, Bomb) and b.player is player]
        if len(bombs) >= player.bombamount:
            return False
        self.items.append(Bomb(
            player=player,
            fuse_time=5,
            position=player.position_int,
        ))

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

        for item in self.items:
            item.update(dt)
        self.items = [i for i in self.items if not i.hidden]
