import pygameui as ui


class LoadingScene(ui.Scene):

    def __init__(self):
        super().__init__()

        label = ui.label.Label(self.frame, "Loading ...")
        self.add_child(label)


class MapScene(ui.Scene):

    def __init__(self, map):
        super().__init__()
        self.map = map
        self.add_child(self.map)
