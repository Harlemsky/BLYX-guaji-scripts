"""百炼英雄 - 坐标校准工具

用法：
  1. 先把游戏小程序窗口摆到屏幕左上角，调好大小（和平时挂机一致）
  2. 填窗口宽高(cm)，点“计算预期坐标”
  3. 在列表里选中一项，把鼠标悬停在游戏里对应的按钮上，点“捕获鼠标位置”或按 F2
  4. 全部校准完点“保存校准”，之后挂机脚本会自动优先使用这些真实坐标

地图列表/层数列表只需捕获第 1、2 项：工具会自动算出间距（第2项 y - 第1项 y），
挂机脚本按这个间距推算后面的项。想更准可以顺手把第 3 项往后也捕获，工具会取平均
间距；实测坐标会写进 config/calibration.json 的 map_positions / level_positions。

校准数据保存在 config/calibration.json，脚本只会在窗口尺寸匹配时使用。
"""
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pyautogui
from vision import get_game_rect

BASE_DIR = Path(__file__).resolve().parent.parent
CALIBRATION_PATH = BASE_DIR / "config" / "calibration.json"
UI_SETTINGS_PATH = BASE_DIR / "config" / "gui_settings.json"


def _load_json(path):
    """读取 JSON 文件；不存在或损坏时返回空字典。"""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}

# 地图列表 / 层数列表支持逐项校准的最大序号（第1、2项必填，其余可选）
MAX_ITEM_INDEX = 6
# 动态项的基准，与 src/base.py 的 get_map_pos / get_level_pos 保持一致
MAP_BASE = (160, 350, 60)
LEVEL_BASE = (380, 360, 100)


def build_point_defs():
    """生成所有校准项：固定项 + 地图列表第n项 + 层数列表第n项。

    每项为 (key, 显示名, 基准x, 基准y, 基准间距, kind)；kind 为 None 表示固定项，
    ("map", n) / ("level", n) 表示地图列表 / 层数列表的第 n 项。
    """
    defs = [
        ("center", "角色中心", 300, 600, None, None),
        ("transport", "传送按钮", 350, 500, None, None),
        ("transport_first", "传送按钮(首次)", 350, 440, None, None),
        ("go_home", "回城按钮", 550, 1000, None, None),
        ("confirm_yes", "回城确认框", 380, 700, None, None),
    ]
    for kind, (base_x, base_y, base_shift) in (("map", MAP_BASE), ("level", LEVEL_BASE)):
        for n in range(1, MAX_ITEM_INDEX + 1):
            key = kind if n == 1 else f"{kind}_{n}"
            name = "地图列表" if kind == "map" else "层数列表"
            label = f"{name}第{n}项（必填）" if n <= 2 else f"{name}第{n}项（可选）"
            defs.append((
                key,
                label,
                base_x,
                base_y + (n - 1) * base_shift,
                base_shift if n == 1 else None,
                (kind, n),
            ))
    return defs


# key, 显示名, 基准x, 基准y, 基准间距(仅第1项有), 所属列表
POINTS = build_point_defs()


class CalibrationApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("百炼英雄 - 坐标校准工具")
        root.geometry("880x720")

        self.width_var = tk.StringVar(value="14")
        self.height_var = tk.StringVar(value="25")
        self.mouse_var = tk.StringVar(value="鼠标位置: (?, ?)")

        self.points = {
            key: {
                "label": label,
                "base_x": base_x,
                "base_y": base_y,
                "base_shift": base_shift,
                "kind": kind,
                "exp_x": None,
                "exp_y": None,
                "exp_shift": None,
                "cal_x": None,
                "cal_y": None,
                "cal_shift": None,
            }
            for key, label, base_x, base_y, base_shift, kind in POINTS
        }
        self.selected_key = None
        self.map_positions = {}
        self.level_positions = {}
        self.capture_origin = None
        self.window_var = tk.StringVar(value="游戏窗口: 未检测到")

        self._build_ui()
        self._load_existing()
        self._update_table()
        self._poll_mouse()

    # ---------- 界面 ----------

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="窗口宽度(cm)").pack(side="left")
        ttk.Entry(top, textvariable=self.width_var, width=8).pack(side="left", padx=4)
        ttk.Label(top, text="窗口高度(cm)").pack(side="left")
        ttk.Entry(top, textvariable=self.height_var, width=8).pack(side="left", padx=4)
        ttk.Button(top, text="计算预期坐标", command=self._compute_expected).pack(side="left", padx=8)
        ttk.Button(top, text="恢复默认(清除校准)", command=self._reset).pack(side="right")

        ttk.Label(
            self.root,
            textvariable=self.mouse_var,
            font=("Arial", 12),
            foreground="blue",
        ).pack(pady=4)
        ttk.Label(
            self.root,
            textvariable=self.window_var,
            font=("Arial", 11),
            foreground="green",
        ).pack(pady=2)
        ttk.Label(
            self.root,
            text="地图/层数只需捕获第1、2项：间距会自动算出，后面的项按间距推算；想更准再顺手捕获第3项往后（可选）",
            font=("Arial", 10),
            foreground="gray",
        ).pack(pady=2)

        table_frame = ttk.Frame(self.root, padding=8)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("label", "expected", "calibrated"),
            show="headings",
            height=11,
        )
        self.tree.heading("label", text="校准项")
        self.tree.heading("expected", text="预期位置 (按基准计算)")
        self.tree.heading("calibrated", text="校准位置 (实际)")
        self.tree.column("label", width=170, anchor="w")
        self.tree.column("expected", width=210, anchor="center")
        self.tree.column("calibrated", width=210, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail = ttk.Frame(self.root, padding=8)
        detail.pack(fill="x")

        self.detail_label = ttk.Label(detail, text="当前项: -")
        self.detail_label.pack(side="left", padx=8)

        ttk.Label(detail, text="x:").pack(side="left")
        self.x_var = tk.StringVar()
        ttk.Entry(detail, textvariable=self.x_var, width=8).pack(side="left", padx=2)
        ttk.Label(detail, text="y:").pack(side="left")
        self.y_var = tk.StringVar()
        ttk.Entry(detail, textvariable=self.y_var, width=8).pack(side="left", padx=2)
        # 间距由实测坐标自动算出，这里只显示，不用手填
        self.shift_label = ttk.Label(detail, text="间距(自动):")
        self.shift_var = tk.StringVar()
        self.shift_value = ttk.Label(detail, textvariable=self.shift_var, width=8)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="捕获鼠标位置到当前项 (F2)", command=self._capture).pack(side="left", padx=4)
        ttk.Button(bottom, text="应用编辑值", command=self._apply_edit).pack(side="left", padx=4)
        ttk.Button(bottom, text="保存校准", command=self._save).pack(side="right", padx=4)

        self.root.bind("<F2>", lambda e: self._capture())

    # ---------- 逻辑 ----------

    def _load_existing(self):
        """读取校准文件；没有校准文件时，宽高取自挂机界面的配置，两边始终是同一个值。"""
        data = _load_json(CALIBRATION_PATH)
        w = data.get("window_width_cm")
        h = data.get("window_height_cm")
        if w is None or h is None:
            ui = _load_json(UI_SETTINGS_PATH)
            w = ui.get("width_cm", 14)
            h = ui.get("height_cm", 25)
        self.width_var.set(str(w))
        self.height_var.set(str(h))
        if not data:
            return
        saved = data.get("points", {})
        origin = data.get("window_origin")
        if isinstance(origin, list) and len(origin) == 2:
            self.capture_origin = (float(origin[0]), float(origin[1]))
            self.window_var.set(f"游戏窗口原点(已保存): ({int(origin[0])}, {int(origin[1])})")
        if not isinstance(saved, dict):
            saved = {}
        # 兼容两种位置：统一以 points 内为准，顶层旧格式作为兜底
        positions = saved.get("map_positions") or data.get("map_positions") or {}
        self.map_positions = positions if isinstance(positions, dict) else {}
        levels = saved.get("level_positions") or data.get("level_positions") or {}
        self.level_positions = levels if isinstance(levels, dict) else {}
        for key, point in saved.items():
            if key in self.points:
                self.points[key]["cal_x"] = point.get("x")
                self.points[key]["cal_y"] = point.get("y")
                self.points[key]["cal_shift"] = point.get("shift")
        # 地图/层数逐项实测坐标（map_positions / level_positions）优先级最高，
        # 它们才是挂机脚本真正使用的值，所以放在固定项之后覆盖
        for p in self.points.values():
            kind = p["kind"]
            if kind is None:
                continue
            table = self.map_positions if kind[0] == "map" else self.level_positions
            pos = table.get(str(kind[1]))
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                p["cal_x"] = float(pos[0])
                p["cal_y"] = float(pos[1])
        # 间距永远按实测坐标算，不手填（只有一项时保留文件里已有的值）
        for kind in ("map", "level"):
            self._auto_shift(kind)
        self._compute_expected()

    def _scale(self):
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
            return w / 14.0, h / 25.0
        except ValueError:
            return None, None

    def _compute_expected(self):
        sx, sy = self._scale()
        if sx is None:
            messagebox.showerror("错误", "宽高必须是数字")
            return
        for key, p in self.points.items():
            p["exp_x"] = p["base_x"] * sx
            p["exp_y"] = p["base_y"] * sy
            if p["base_shift"] is not None:
                p["exp_shift"] = p["base_shift"] * sy
        self._update_table()

    def _auto_shift(self, kind):
        """用已捕获的序号自动算间距，写进第1项的间距。

        只填第 1、2 项时，间距 = y2 - y1；如果还多填了几项，就按每跨一项的
        平均 y 差来算，结果更准。挂机脚本用它推算没单独校准的那些项。
        """
        pairs = []
        for n in range(1, MAX_ITEM_INDEX + 1):
            p = self.points[kind if n == 1 else f"{kind}_{n}"]
            if p["cal_y"] is not None:
                pairs.append((n, float(p["cal_y"])))
        if len(pairs) < 2:
            return None
        gaps = [
            (y2 - y1) / (n2 - n1)
            for (n1, y1), (n2, y2) in zip(pairs, pairs[1:])
        ]
        shift = round(sum(gaps) / len(gaps), 2)
        self.points[kind]["cal_shift"] = shift
        return shift

    def _update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for key, p in self.points.items():
            exp_x = p.get("exp_x")
            exp_y = p.get("exp_y")
            exp = f"({exp_x:.1f}, {exp_y:.1f})" if exp_x is not None else "-"
            if p["cal_x"] is not None and p["cal_y"] is not None:
                cal = f"({float(p['cal_x']):.1f}, {float(p['cal_y']):.1f})"
                if p["base_shift"] is not None and p.get("cal_shift") is not None:
                    cal += f"  间距{float(p['cal_shift']):.1f}"
            else:
                cal = "-"
            self.tree.insert("", "end", iid=key, values=(p["label"], exp, cal))

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        self.selected_key = key
        p = self.points[key]
        self.detail_label.config(text=f"当前项: {p['label']}")
        self.x_var.set("" if p["cal_x"] is None else str(p["cal_x"]))
        self.y_var.set("" if p["cal_y"] is None else str(p["cal_y"]))
        if p["base_shift"] is not None:
            self.shift_label.pack(side="left", padx=(12, 2))
            self.shift_value.pack(side="left", padx=2)
            self.shift_var.set("" if p["cal_shift"] is None else str(p["cal_shift"]))
        else:
            self.shift_label.pack_forget()
            self.shift_value.pack_forget()

    def _capture(self):
        if self.selected_key is None:
            messagebox.showwarning("提示", "先在列表里选择要校准的项")
            return
        x, y = pyautogui.position()
        p = self.points[self.selected_key]
        p["cal_x"] = float(x)
        p["cal_y"] = float(y)
        # 捕获时记录窗口原点：保存时用它，保证坐标与原点来自同一窗口位置
        rect = get_game_rect()
        if rect:
            self.capture_origin = (float(rect[0]), float(rect[1]))
            self.window_var.set(
                f"游戏窗口: ({int(rect[0])}, {int(rect[1])}) 尺寸 {rect[2]}x{rect[3]}"
            )
        else:
            self.window_var.set("游戏窗口: 未检测到（请先打开游戏）")
        # 捕获地图/层数后自动算间距；只捕获了一项时先用基准间距兜底
        if p["kind"] is not None:
            first = self.points[p["kind"][0]]
            if self._auto_shift(p["kind"][0]) is None and first["cal_shift"] is None:
                first["cal_shift"] = first.get("exp_shift")
        self.x_var.set(str(x))
        self.y_var.set(str(y))
        if p["base_shift"] is not None:
            self.shift_var.set("" if p["cal_shift"] is None else str(p["cal_shift"]))
        self._update_table()

    def _apply_edit(self):
        if self.selected_key is None:
            return
        p = self.points[self.selected_key]
        y_edited = False
        try:
            if self.x_var.get().strip():
                p["cal_x"] = float(self.x_var.get())
            if self.y_var.get().strip():
                p["cal_y"] = float(self.y_var.get())
                y_edited = True
        except ValueError:
            messagebox.showerror("错误", "请输入数字")
            return
        # 间距跟着实测坐标走，改了 y 就重算
        if y_edited and p["kind"] is not None:
            self._auto_shift(p["kind"][0])
        self._update_table()

    def _save(self):
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
        except ValueError:
            messagebox.showerror("错误", "宽高必须是数字")
            return
        points = {}
        map_positions = {}
        level_positions = {}
        for key, p in self.points.items():
            if p["cal_x"] is None or p["cal_y"] is None:
                continue
            kind = p["kind"]
            if kind is not None:
                # 地图/层数逐项坐标写进 map_positions / level_positions
                target = map_positions if kind[0] == "map" else level_positions
                target[str(kind[1])] = [p["cal_x"], p["cal_y"]]
                if kind[1] != 1:
                    continue  # 第2项往后只走 map_positions / level_positions
            point = {"x": p["cal_x"], "y": p["cal_y"]}
            if p["base_shift"] is not None:
                fallback_shift = p["base_shift"] * (h / 25.0)
                point["shift"] = p.get("cal_shift") if p.get("cal_shift") is not None else fallback_shift
            points[key] = point
        if not points and not map_positions and not level_positions:
            messagebox.showwarning("提示", "还没有任何校准数据")
            return
        if map_positions:
            points["map_positions"] = map_positions
        if level_positions:
            points["level_positions"] = level_positions
        # window_* 是“用户填的窗口尺寸”，挂机界面和这里共用同一个值（互相同步）；
        # calibrated_* 记录“捕获这批坐标时的窗口尺寸”，只在这里写，
        # 之后用户在界面上改尺寸也不会覆盖它，脚本靠它判断校准是否还对得上。
        data = {
            "window_width_cm": w,
            "window_height_cm": h,
            "calibrated_width_cm": w,
            "calibrated_height_cm": h,
            "points": points,
        }
        rect = get_game_rect()
        if self.capture_origin is not None:
            data["window_origin"] = list(self.capture_origin)
            if rect and (abs(rect[0] - self.capture_origin[0]) > 5
                         or abs(rect[1] - self.capture_origin[1]) > 5):
                messagebox.showwarning(
                    "窗口位置已变化",
                    "捕获坐标时的窗口位置与当前不同，将按捕获时的位置保存。\n"
                    "建议把窗口放回捕获时的位置，或重新捕获所有坐标。",
                )
        elif rect:
            data["window_origin"] = [rect[0], rect[1]]
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._sync_ui_settings(w, h)
        messagebox.showinfo("完成", f"已保存 {len(points)} 个校准点到:\n{CALIBRATION_PATH}")

    def _sync_ui_settings(self, w, h):
        """把窗口尺寸写进挂机界面的配置，让两边填的尺寸永远一致。"""
        ui = _load_json(UI_SETTINGS_PATH)
        ui["width_cm"] = w
        ui["height_cm"] = h
        try:
            UI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(UI_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(ui, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _reset(self):
        if not messagebox.askyesno("确认", "清除所有校准数据，恢复默认坐标？"):
            return
        if CALIBRATION_PATH.exists():
            CALIBRATION_PATH.unlink()
        for p in self.points.values():
            p["cal_x"] = None
            p["cal_y"] = None
            p["cal_shift"] = None
        self.map_positions = {}
        self.level_positions = {}
        self.selected_key = None
        self.x_var.set("")
        self.y_var.set("")
        self.shift_var.set("")
        self._update_table()
        messagebox.showinfo("完成", "已恢复默认坐标")

    def _poll_mouse(self):
        try:
            x, y = pyautogui.position()
            self.mouse_var.set(f"鼠标位置: ({x}, {y})")
        except Exception:
            pass
        self.root.after(100, self._poll_mouse)


def main():
    root = tk.Tk()
    CalibrationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
