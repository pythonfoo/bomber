import asyncio
import msgpack
import pygameui as ui
import traceback


class ClientStub:

    def __init__(self, reader, writer, level):
        self.reader = reader
        self.writer = writer
        self.peername = None
        self.on_message = ui.callback.Signal()
        self.state = "pending"
        self.level = level

    def inform(self, msg_type, args):
        self.writer.write(msgpack.packb((msg_type, args)))

    def handle_msg(self, msg):
        if self.state == "pending" and msg["type"] == "connect":
            # print(repr(msg))
            self.position = self.level.player_register(self, **msg)
            self.state = "connected"
        else:
            self.on_message(msg)

    def bye(self):
        try:
            self.level.player_unregister(self.level)
        except:
            pass


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
        new_client = ClientStub(reader, writer, self.level)
        # position = self.level.player_register(new_client)
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
                traceback.print_exc()
                new_client.bye()
                del self.clients[peername]
                # self.level.player_unregister(position)
                return
            except Exception as e:
                error = 'ERROR: {}'.format(e)
                print(error)
                traceback.print_exc()
                self.send_to_client(peername, ("ERR", error))
                new_client.writer.write_eof()
                new_client.bye()
                del self.clients[peername]
                # self.level.player_unregister(position)
                return

    def close(self):
        self.send_to_all_clients("bye\n")
        self.close_clients()
