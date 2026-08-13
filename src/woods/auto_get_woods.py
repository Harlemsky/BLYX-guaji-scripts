
from base import AutoPlay


class Woods(AutoPlay):

    def __init__(self, width: float, height: float, all_auto: bool):
        super().__init__(width=width, height=height, all_auto=all_auto)
        self.__map = 5
        self.__level = 1

    def start_transport(self):
        self.transport(self.__map, self.__level)

    def move_to_pos(self):
        self.move_left_up(drag_time=3, pause_time=1.5)

    def walk_loop(self):
        self.move_left_down(drag_time=2.5)
        self.move_left_down(drag_time=2, pause_time=0)
        self.move_left_up(drag_time=1.5)
        self.move_left_up(drag_time=7.5)
        self.move_down(drag_time=1.5)
        self.move_left_down(drag_time=2)
        self.move_left_down(drag_time=3, pause_time=0.5)
        self.move_left_up(drag_time=2)
        self.move_right_down(drag_time=5)
        self.move_right_down(drag_time=1)
        self.move_right_up(drag_time=3)
        self.move_right(drag_time=2.5, pause_time=0.5)
        self.move_right_up(drag_time=4)
        self.move_right_down(drag_time=2)
        self.move_right_up(drag_time=2.1, pause_time=0)
