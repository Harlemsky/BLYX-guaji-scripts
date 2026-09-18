import json
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

import pyautogui
from vision import get_game_rect, template_available, wait_for, wait_screen_stable, wait_until_gone

# 校准文件：由校准工具生成；只要文件在就用里面的绝对像素坐标，窗口尺寸仅作记录
CALIBRATION_PATH = Path(__file__).resolve().parent.parent / "config" / "calibration.json"

# 鼠标上下左右偏移量
DEFAULT_SHIFT = 45
# 拖动鼠标的时间
DEFAULT_DRAG_TIME = 2
# 停留打怪时间
DEFAULT_PAUSE_TIME = 2.3
# 拖拽/点击鼠标移动动画时长（0.15 秒，保留移动优化）
DEFAULT_DURATION = 0.15
# 移动方向
MOVE_UP = 0
MOVE_DOWN = 1
MOVE_LEFT = 2
MOVE_RIGHT = 3
MOVE_LEFT_UP = 4
MOVE_LEFT_DOWN =5
MOVE_RIGHT_UP = 6
MOVE_RIGHT_DOWN = 7
# 默认的鼠标坐标
DEFAULT_CENTER_X = 300
DEFAULT_CENTER_Y = 600
# 回城按钮坐标
DEFAULT_GO_HOME_X = 550
DEFAULT_GO_HOME_Y = 1000
#
DEFAULT_WIDTH = 14
DEFAULT_HEIGHT = 25
DEFAULT_TRANSPORT_X = 350
DEFAULT_TRANSPORT_Y = 500
TRANSPORT_Y_LOSS = 60

DEFAULT_MAP_X = 160
DEFAULT_MAP_Y = 350
DEFAULT_MAP_SHIFT = 60
DEFAULT_LEVEL_X = 380
DEFAULT_LEVEL_Y = 360
DEFAULT_LEVEL_SHIFT = 100
DEFAULT_CONFIRM_YES_X = 380
DEFAULT_CONFIRM_YES_Y = 700


def get_map_pos(num: int):
    x = DEFAULT_MAP_X
    y = DEFAULT_MAP_Y + (num - 1) * DEFAULT_MAP_SHIFT
    return x, y


def get_level_pos(num: int):
    x = DEFAULT_LEVEL_X
    y = DEFAULT_LEVEL_Y + (num - 1) * DEFAULT_LEVEL_SHIFT
    return x, y


def load_calibration():
    """读取校准文件；不存在或内容不合法时返回 None。"""
    if not CALIBRATION_PATH.exists():
        return None
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("points"), dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def calibration_size(calib):
    """校准记录里的窗口尺寸 (宽, 高)。

    优先用 calibrated_width_cm / calibrated_height_cm（只有“保存校准”会写，
    记录的是捕获坐标那一刻的窗口尺寸）；老校准文件没有这两个字段时，退回
    window_width_cm / window_height_cm。读不到返回 None。
    """
    if not calib:
        return None
    w = calib.get("calibrated_width_cm")
    h = calib.get("calibrated_height_cm")
    if w is None or h is None:
        w = calib.get("window_width_cm")
        h = calib.get("window_height_cm")
    if w is None or h is None:
        return None
    try:
        return float(w), float(h)
    except (TypeError, ValueError):
        return None


class AutoPlay(ABC):
    """自动操作执行器"""
    def __init__(self, width: float=DEFAULT_WIDTH, height: float=DEFAULT_HEIGHT, all_auto: bool=True):
        print("all auto", all_auto)
        self.__scale_x = width / DEFAULT_WIDTH
        self.__scale_y = height / DEFAULT_HEIGHT
        calib = load_calibration()
        # 有校准就直接用校准坐标：窗口尺寸只是记录，不参与点击位置的计算，
        # 所以填多少、含不含标题栏都不影响点位。窗口真的改过大小才需要重新校准。
        self.__calib_points = calib.get("points", {}) if calib else {}
        center = self.__calib_points.get("center") if self.__calib_points else None
        if center and center.get("x") is not None and center.get("y") is not None:
            self.__center_x = int(float(center["x"]))
            self.__center_y = int(float(center["y"]))
        else:
            self.__center_x = int(DEFAULT_CENTER_X * self.__scale_x)
            self.__center_y = int(DEFAULT_CENTER_Y * self.__scale_y)
        # 窗口相对定位：记录校准时的窗口原点，运行时按当前窗口位置自动偏移
        calib_origin = None
        if calib and isinstance(calib.get("window_origin"), list) and len(calib["window_origin"]) == 2:
            try:
                calib_origin = (float(calib["window_origin"][0]), float(calib["window_origin"][1]))
            except (TypeError, ValueError):
                calib_origin = None
        cur_rect = get_game_rect()
        if cur_rect:
            cur_origin = (float(cur_rect[0]), float(cur_rect[1]))
            if calib_origin is None:
                calib_origin = cur_origin  # 旧校准无窗口原点记录：不偏移
            self.__win_offset_x = cur_origin[0] - calib_origin[0]
            self.__win_offset_y = cur_origin[1] - calib_origin[1]
        else:
            self.__win_offset_x = 0.0
            self.__win_offset_y = 0.0
        self.__all_auto = all_auto
        self.__is_running = True
        self.__is_first_transport = True
        self.__use_first_transport = True
        self.__transport_wait = None

    # 移动基础函数
    def move(self, direction: int, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        if not self.__is_running:
            return
        x = self.__center_x
        y = self.__center_y
        if direction == MOVE_UP:
            y -= DEFAULT_SHIFT
        elif direction == MOVE_DOWN:
            y += DEFAULT_SHIFT
        elif direction == MOVE_LEFT:
            x -= DEFAULT_SHIFT
        elif direction == MOVE_RIGHT:
            x += DEFAULT_SHIFT
        elif direction == MOVE_LEFT_UP:
            x -= DEFAULT_SHIFT
            y -= DEFAULT_SHIFT
        elif direction == MOVE_LEFT_DOWN:
            x -= DEFAULT_SHIFT
            y += DEFAULT_SHIFT
        elif direction == MOVE_RIGHT_UP:
            x += DEFAULT_SHIFT
            y -= DEFAULT_SHIFT
        elif direction == MOVE_RIGHT_DOWN:
            x += DEFAULT_SHIFT
            y += DEFAULT_SHIFT
        else:
            print("未知方向!")
            return

        pyautogui.mouseDown(
            x=self.__center_x + self.__win_offset_x,
            y=self.__center_y + self.__win_offset_y,
            button='left',
        )
        pyautogui.moveTo(x + self.__win_offset_x, y + self.__win_offset_y, duration=DEFAULT_DURATION)
        time.sleep(drag_time)
        pyautogui.mouseUp()
        time.sleep(pause_time)

    # 向上移动
    def move_up(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_UP,drag_time=drag_time, pause_time=pause_time)

    # 向下移动
    def move_down(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_DOWN, drag_time=drag_time, pause_time=pause_time)

    # 向左移动
    def move_left(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_LEFT, drag_time=drag_time, pause_time=pause_time)

    # 向右移动
    def move_right(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_RIGHT, drag_time=drag_time, pause_time=pause_time)

    # 向左上角移动
    def move_left_up(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_LEFT_UP, drag_time=drag_time, pause_time=pause_time)

    # 向左下角移动
    def move_left_down(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_LEFT_DOWN, drag_time=drag_time, pause_time=pause_time)

    # 向右上角移动
    def move_right_up(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_RIGHT_UP, drag_time=drag_time, pause_time=pause_time)

    # 向右下角移动
    def move_right_down(self, drag_time: float=DEFAULT_DRAG_TIME, pause_time: float=DEFAULT_PAUSE_TIME):
        self.move(MOVE_RIGHT_DOWN, drag_time=drag_time, pause_time=pause_time)

    # 移动到程序位置
    def move_to_program(self):
        if self.__is_running:
            pyautogui.moveTo(
                self.__center_x + self.__win_offset_x,
                self.__center_y + self.__win_offset_y,
                duration=DEFAULT_DURATION,
            )
            pyautogui.click()

    # 点击按钮
    def click_button(self, x, y):
        if self.__is_running:
            pyautogui.moveTo(
                x=x*self.__scale_x + self.__win_offset_x,
                y=y*self.__scale_y + self.__win_offset_y,
                duration=DEFAULT_DURATION,
            )
            pyautogui.click()

    # 点击绝对像素坐标
    def _click_pixel(self, x, y):
        if self.__is_running:
            pyautogui.moveTo(
                x=x + self.__win_offset_x,
                y=y + self.__win_offset_y,
                duration=DEFAULT_DURATION,
            )
            pyautogui.click()

    # 取校准坐标（绝对像素）；没有则回退到 基准坐标×缩放
    def _calibrated(self, key, base_x, base_y):
        point = self.__calib_points.get(key) if self.__calib_points else None
        if point and point.get("x") is not None and point.get("y") is not None:
            return float(point["x"]), float(point["y"])
        return base_x * self.__scale_x, base_y * self.__scale_y

    # 地图列表第 m 项位置：优先使用每张地图的实测坐标，其次第1项+间距推算，最后基准坐标
    def _map_pos(self, m):
        if self.__calib_points:
            positions = self.__calib_points.get("map_positions")
            if positions and str(m) in positions:
                x, y = positions[str(m)]
                return float(x), float(y)
            point = self.__calib_points.get("map")
            if point and point.get("x") is not None and point.get("y") is not None:
                x = float(point["x"])
                shift = float(point.get("shift", DEFAULT_MAP_SHIFT * self.__scale_y))
                y = float(point["y"]) + (m - 1) * shift
                return x, y
        bx, by = get_map_pos(m)
        return bx * self.__scale_x, by * self.__scale_y

    # 层数列表第 l 项位置：优先每层实测坐标，其次第1项+间距推算，最后基准坐标
    def _level_pos(self, l):
        if self.__calib_points:
            positions = self.__calib_points.get("level_positions")
            if positions and str(l) in positions:
                x, y = positions[str(l)]
                return float(x), float(y)
            point = self.__calib_points.get("level")
            if point and point.get("x") is not None and point.get("y") is not None:
                x = float(point["x"])
                shift = float(point.get("shift", DEFAULT_LEVEL_SHIFT * self.__scale_y))
                y = float(point["y"]) + (l - 1) * shift
                return x, y
        bx, by = get_level_pos(l)
        return bx * self.__scale_x, by * self.__scale_y

    # 回城
    def go_home(self):
        self._click_pixel(*self._calibrated("go_home", DEFAULT_GO_HOME_X, DEFAULT_GO_HOME_Y))

    def go_home_with_confirm(self):
        self.go_home()
        time.sleep(0.2)
        self._click_pixel(*self._calibrated("confirm_yes", DEFAULT_CONFIRM_YES_X, DEFAULT_CONFIRM_YES_Y))

    # 传送按钮
    def click_transport(self):
        if self.__use_first_transport and self.__is_first_transport:
            px, py = self._calibrated(
                "transport_first", DEFAULT_TRANSPORT_X, DEFAULT_TRANSPORT_Y - TRANSPORT_Y_LOSS
            )
            self.__is_first_transport = False
        else:
            px, py = self._calibrated("transport", DEFAULT_TRANSPORT_X, DEFAULT_TRANSPORT_Y)
        self._click_pixel(px, py)

    # 用户选项：是否在首次打开传送时使用“首次传送”坐标
    def set_use_first_transport(self, use_first_transport: bool):
        self.__use_first_transport = use_first_transport

    # 传送
    def transport(self, m, l):
        self.move_to_program()
        self.click_transport()
        map_x, map_y = self._map_pos(m)
        self._click_pixel(map_x, map_y)
        time.sleep(0.2)
        level_x, level_y = self._level_pos(l)
        self._click_pixel(level_x, level_y)
        started = time.time()
        if template_available("transport_menu"):
            if not wait_until_gone("transport_menu", timeout=5):
                # 菜单没关，说明层数没点中，重试一次
                self._click_pixel(level_x, level_y)
                wait_until_gone("transport_menu", timeout=5)
            rect = get_game_rect() or (0, 0, 500, 800)
            wait_screen_stable(rect, timeout=15, stable_seconds=1.0)
        else:
            time.sleep(8)
        elapsed = time.time() - started
        floor = self.__transport_wait if self.__transport_wait is not None else 6
        self.__transport_wait = None  # 一次性覆盖，用完即恢复默认 6 秒
        # 传送后角色有 1-2 秒僵直，且每次进图还有初始加载，保底 floor 秒（默认6，实测可调）
        if elapsed < floor:
            time.sleep(floor - elapsed)
        self.move_to_program()

    # 设置下一次传送的一次性保底等待（秒）；用完自动恢复默认
    def set_transport_wait(self, seconds):
        self.__transport_wait = float(seconds)

    #
    @abstractmethod
    def start_transport(self):
        pass

    #
    @abstractmethod
    def move_to_pos(self):
        pass

    #
    @abstractmethod
    def walk_loop(self):
        pass

    def stop(self):
        if self.__is_running:
            self.__is_running = False

    # 先传送，后移动到指定位置，最后执行挂机
    def start(self, stop_event):
        try:
            def start_task():
                self.move_to_program()
                if self.__is_running and self.__all_auto:
                    self.start_transport()
                    self.move_to_pos()
                while self.__is_running:
                    self.walk_loop()
            thread = threading.Thread(target=start_task)
            thread.start()
            while not stop_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("键盘打断")
        finally:
            self.stop()
            print(self.__is_running)
            print("工作线程正在退出...")

