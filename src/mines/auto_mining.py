from base import AutoPlay

# 自动打矿
class Mines(AutoPlay):

    def __init__(self, width: float, height: float, all_auto: bool):
        super().__init__(width=width, height=height, all_auto=all_auto)
        self.__map = 4
        self.__level = 2

    def start_transport(self):
        self.transport(self.__map, self.__level)

    def move_to_pos(self):
        self.move_left(drag_time=1, pause_time=0)
        self.move_down(drag_time=0.8, pause_time=0)

    def walk_loop(self):
        self.move_left_down(drag_time=2.3)
        self.move_left_up(drag_time=3)
        self.move_left_down(drag_time=2.5)
        self.move_right_down(drag_time=1.8)
        self.move_left_up(drag_time=5.5)
        self.move_up(drag_time=3.5)
        self.move_left_down(drag_time=5)
        self.move_right_down(drag_time=1.5)
        self.move_right_up(drag_time=4)
        self.move_right_down(drag_time=3)
        self.move_right_up(drag_time=2)
        self.move_right_down(drag_time=3)
        self.move_right_up(drag_time=1.2)
