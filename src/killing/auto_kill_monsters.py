from base import AutoPlay


# 冰封禁区自动打怪
class Killing53(AutoPlay):

    def __init__(self, width: float, height: float, all_auto: bool):
        print("killing 53")
        super().__init__(width=width, height=height, all_auto=all_auto)
        self.__map = 5
        self.__level = 3

    def start_transport(self):
        self.transport(self.__map, self.__level)

    def move_to_pos(self):
        self.move_left_up(drag_time=1.5, pause_time=0)
        self.move_right_up(drag_time=8.5, pause_time=0)
        self.move_right_down(drag_time=18, pause_time=0)
        self.move_left_down(drag_time=7.4, pause_time=0)
        self.move_left_up(drag_time=5.6, pause_time=0)

    def walk_loop(self):
        print("start walk loop")
        self.move_right_up(drag_time=1.8, pause_time=0)
        self.move_left_up(drag_time=1.8)
        self.move_left_up(drag_time=2.6, pause_time=1)
        self.move_left_down(drag_time=2.2)
        self.move_left_down(drag_time=2.2, pause_time=1)
        self.move_right_down(drag_time=2)
        self.move_right_down(drag_time=2.2, pause_time=1)
        self.move_right_up(drag_time=2.5)
        self.move_right_down(drag_time=2)
        self.move_right_down(drag_time=2)
        self.move_left_up(drag_time=2)
        self.move_left_up(drag_time=1.8)

# 冰封王座自动打怪
class Killing54(AutoPlay):

    def __init__(self, width: float, height: float, all_auto: bool):
        super().__init__(width=width, height=height, all_auto=all_auto)
        self.__map = 5
        self.__level = 4

    def start_transport(self):
        self.transport(self.__map, self.__level)

    def move_to_pos(self):
        self.move_up(drag_time=2.4, pause_time=1)
        self.move_right_up(drag_time=2.6, pause_time=2)

    def walk_loop(self):
        self.move_right_down(drag_time=1.8)
        self.move_right_up(drag_time=2.8)
        self.move_right_up(drag_time=2, pause_time=1.5)
        self.move_left_up(drag_time=1.5, pause_time=1)
        self.move_left_up(drag_time=2, pause_time=2)
        self.move_left_down(drag_time=1.5)
        self.move_left_down(drag_time=2)
        self.move_right_down(drag_time=2)
        self.move_left_down(drag_time=2.5)
        self.move_left_up(drag_time=2)
        self.move_right_down(drag_time=1.8)
        self.move_right_up(drag_time=2)



