import json
import time
from pathlib import Path

import numpy as np

from base import AutoPlay
from vision import get_game_rect, grab_region

# 配置文件路径：项目根目录/config/boss_path.json
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "boss_path.json"

# 配置里可用的方向名称 -> 基类移动方法
_DIRECTION_METHODS = {
    "up": "move_up",
    "down": "move_down",
    "left": "move_left",
    "right": "move_right",
    "left_up": "move_left_up",
    "left_down": "move_left_down",
    "right_up": "move_right_up",
    "right_down": "move_right_down",
}

_DEFAULT_ROUTE_NAME = "默认路线"


class KillBoss(AutoPlay):

    def __init__(self, width: float, height: float, all_auto: bool, route: str = None,
                 use_refresh: bool = True):
        super().__init__(width=width, height=height, all_auto=all_auto)
        # 启动时先校验整份配置，有问题尽早报错
        self._all_config = self._load_config()
        self._route_name = route or self._pick_default_route(self._all_config)
        self._config = self._route_config(self._route_name, self._all_config)
        self.__use_refresh = use_refresh

    # ---------- 配置读取与校验 ----------

    @staticmethod
    def get_route_names():
        """返回配置中所有路线名（供界面下拉框使用）。"""
        if not CONFIG_PATH.exists():
            return []
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        routes = config.get("routes")
        if routes is None:
            # 兼容旧格式：整份配置就是单条默认路线
            return [_DEFAULT_ROUTE_NAME]
        return list(routes.keys())

    def _load_config(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"找不到Boss路径配置文件: {CONFIG_PATH}")
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        self._validate_config(config)
        return config

    def _validate_config(self, config):
        routes = config.get("routes")
        if routes is None:
            # 兼容旧格式：整份配置就是单条默认路线
            routes = {_DEFAULT_ROUTE_NAME: config}
        if not isinstance(routes, dict) or not routes:
            raise ValueError("配置文件中必须包含 routes（至少一条路线）")
        for route_name, route in routes.items():
            bosses = route.get("bosses")
            if not isinstance(bosses, list) or not bosses:
                raise ValueError(f"路线 '{route_name}' 的 bosses 必须是非空列表")
            for boss in bosses:
                if not isinstance(boss.get("map"), int) or not isinstance(boss.get("level"), int):
                    raise ValueError(f"路线 '{route_name}' 的 Boss 配置缺少 map/level 整数: {boss}")
                for step in boss.get("steps", []):
                    direction = step.get("direction")
                    if direction not in _DIRECTION_METHODS:
                        raise ValueError(
                            f"路线 '{route_name}' 存在未知移动方向 '{direction}'，"
                            f"可用: {', '.join(_DIRECTION_METHODS)}"
                        )
            refresh = route.get("refresh", {})
            if not isinstance(refresh.get("map"), int) or not isinstance(refresh.get("level"), int):
                raise ValueError(f"路线 '{route_name}' 的 refresh 配置必须包含 map/level 整数")
            refresh_enabled = route.get("refresh_enabled", True)
            if not isinstance(refresh_enabled, bool):
                raise ValueError(f"路线 '{route_name}' 的 refresh_enabled 必须是 true/false")

    @staticmethod
    def _pick_default_route(config):
        """route 参数为空时，选择第一条路线。"""
        routes = config.get("routes")
        if routes is None:
            return _DEFAULT_ROUTE_NAME
        return next(iter(routes))

    @staticmethod
    def _route_config(route_name, config):
        """取出指定路线的配置，找不到时报错。"""
        routes = config.get("routes")
        if routes is None:
            if route_name != _DEFAULT_ROUTE_NAME:
                raise ValueError(f"找不到路线 '{route_name}'，可用: {_DEFAULT_ROUTE_NAME}")
            return config
        if route_name not in routes:
            raise ValueError(f"找不到路线 '{route_name}'，可用: {', '.join(routes)}")
        return routes[route_name]

    # ---------- 移动 ----------

    def _move(self, direction, drag_time=None, pause_time=None):
        """按方向名执行一次拖拽移动；省略的时长参数使用基类默认值。"""
        method_name = _DIRECTION_METHODS[direction]
        kwargs = {}
        if drag_time is not None:
            kwargs["drag_time"] = drag_time
        if pause_time is not None:
            kwargs["pause_time"] = pause_time
        getattr(self, method_name)(**kwargs)

    def _walk_steps(self, steps):
        for step in steps:
            self._move(
                direction=step["direction"],
                drag_time=step.get("drag_time"),
                pause_time=step.get("pause_time"),
            )

    # ---------- 传送 / 打Boss ----------

    def _visit_boss(self, boss):
        self.transport(boss["map"], boss["level"])
        self._walk_steps(boss.get("steps", []))
        # 名字含 xb 的条目不打Boss，跳过战斗结束判定
        if "xb" in boss.get("name", "").lower():
            return
        steps = boss.get("steps") or []
        last_pause = steps[-1].get("pause_time", 2.3) if steps else 2.3
        after_kill = self._config.get("timing", {}).get("after_kill_pause", 1)
        budget = last_pause + after_kill + 30
        self._wait_battle_end(budget=budget)

    def _wait_battle_end(self, budget, grace=1.5):
        """等待战斗结束：先给 grace 秒开战时间，之后画面连续稳定约 1.5 秒视为结束。

        不依赖血条模板（不同 Boss 血条位置不同、倒地后 UI 不消失），
        用“角色停止攻击 → 画面静止”判断，对任何 Boss 通用。
        """
        rect = get_game_rect() or (0, 0, 500, 800)
        if grab_region(rect) is None:
            return False  # 截屏不可用，跳过检测，回退原逻辑
        start = time.time()
        deadline = start + budget
        prev = None
        stable_streak = 0
        while time.time() < deadline:
            if time.time() - start >= grace:
                frame = grab_region(rect)
                if frame is None:
                    time.sleep(0.5)
                    continue
                if prev is not None and frame.shape == prev.shape:
                    diff = float(np.mean(np.abs(frame.astype(np.int16) - prev.astype(np.int16))))
                    stable_streak = stable_streak + 1 if diff < 3.0 else 0
                    if stable_streak >= 3:  # 约 1.5 秒稳定
                        return True
                prev = frame
            time.sleep(0.5)
        return False

    def _refresh_boss(self):
        refresh = self._config["refresh"]
        self.transport(refresh["map"], refresh["level"])
        self.go_home_with_confirm()
        time.sleep(refresh.get("wait_seconds", 10))

    # ---------- AutoPlay 抽象方法 ----------

    def start_transport(self):
        pass

    def move_to_pos(self):
        pass

    def walk_loop(self):
        # 每一轮重新读取配置：修改 JSON 后下一轮自动生效，无需重启
        self._all_config = self._load_config()
        self._config = self._route_config(self._route_name, self._all_config)
        timing = self._config.get("timing", {})
        after_kill = timing.get("after_kill_pause", 1)
        after_go_home = timing.get("after_go_home_pause", 6)

        for boss in self._config["bosses"]:
            self._visit_boss(boss)
            time.sleep(after_kill)
            self.go_home()
            time.sleep(after_go_home)
        # 路线允许刷新 且 界面勾选了刷新时，才执行 5-1 换图回城刷新
        if self._config.get("refresh_enabled", True) and self.__use_refresh:
            self._refresh_boss()
