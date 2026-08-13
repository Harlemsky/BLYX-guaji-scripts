"""百炼英雄 - 坐标校准工具

用法：
  1. 先把游戏小程序窗口摆到屏幕左上角，调好大小（和平时挂机一致）
  2. 填窗口宽高(cm)，点“计算预期坐标”
  3. 在列表里选中一项，把鼠标悬停在游戏里对应的按钮上，点“捕获鼠标位置”或按 F2
  4. 全部校准完点“保存校准”，之后挂机脚本会自动优先使用这些真实坐标

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

# key, 显示名, 基准x, 基准y, 基准间距(仅地图/层数有)
POINTS = [
    ("center", "角色中心", 300, 600, None),
    ("transport", "传送按钮", 350, 500, None),
    ("transport_first", "传送按钮(首次)", 350, 440, None),
    ("go_home", "回城按钮", 550, 1000, None),
    ("confirm_yes", "回城确认框", 380, 700, None),
    ("map", "地图列表第1项", 160, 350, 60),
    ("level", "层数列表第1项", 380, 360, 100),
]


class CalibrationApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("百炼英雄 - 坐标校准工具")
        root.geometry("760x560")

        self.width_var = tk.StringVar(value="14")
        self.height_var = tk.StringVar(value="25")
        self.mouse_var = tk.StringVar(value="鼠标位置: (?, ?)")

        self.points = {
            key: {
                "label": label,
                "base_x": base_x,
                "base_y": base_y,
                "base_shift": base_shift,
                "exp_x": None,
                "exp_y": None,
                "exp_shift": None,
                "cal_x": None,
                "cal_y": None,
                "cal_shift": None,
            }
            for key, label, base_x, base_y, base_shift in POINTS
        }
        self.selected_key = None
        self.map_positions = {}

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

        table_frame = ttk.Frame(self.root, padding=8)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("label", "expected", "calibrated"),
            show="headings",
            height=8,
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
        self.shift_label = ttk.Label(detail, text="间距:")
        self.shift_var = tk.StringVar()
        self.shift_entry = ttk.Entry(detail, textvariable=self.shift_var, width=8)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="捕获鼠标位置到当前项 (F2)", command=self._capture).pack(side="left", padx=4)
        ttk.Button(bottom, text="应用编辑值", command=self._apply_edit).pack(side="left", padx=4)
        ttk.Button(bottom, text="保存校准", command=self._save).pack(side="right", padx=4)

        self.root.bind("<F2>", lambda e: self._capture())

    # ---------- 逻辑 ----------

    def _load_existing(self):
        if not CALIBRATION_PATH.exists():
            return
        try:
            with open(CALIBRATION_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        self.width_var.set(str(data.get("window_width_cm", 14)))
        self.height_var.set(str(data.get("window_height_cm", 25)))
        saved = data.get("points", {})
        positions = data.get("map_positions", {})
        self.map_positions = positions if isinstance(positions, dict) else {}
        for key, point in saved.items():
            if key in self.points:
                self.points[key]["cal_x"] = point.get("x")
                self.points[key]["cal_y"] = point.get("y")
                self.points[key]["cal_shift"] = point.get("shift")
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

    def _update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for key, p in self.points.items():
            exp_x = p.get("exp_x")
            exp_y = p.get("exp_y")
            exp = f"({exp_x:.1f}, {exp_y:.1f})" if exp_x is not None else "-"
            if p["cal_x"] is not None and p["cal_y"] is not None:
                cal = f"({p['cal_x']:.1f}, {p['cal_y']:.1f})"
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
            self.shift_entry.pack(side="left", padx=2)
            self.shift_var.set("" if p["cal_shift"] is None else str(p["cal_shift"]))
        else:
            self.shift_label.pack_forget()
            self.shift_entry.pack_forget()

    def _capture(self):
        if self.selected_key is None:
            messagebox.showwarning("提示", "先在列表里选择要校准的项")
            return
        x, y = pyautogui.position()
        p = self.points[self.selected_key]
        p["cal_x"] = float(x)
        p["cal_y"] = float(y)
        if p["base_shift"] is not None and p["cal_shift"] is None:
            p["cal_shift"] = p.get("exp_shift")
        self.x_var.set(str(x))
        self.y_var.set(str(y))
        if p["base_shift"] is not None:
            self.shift_var.set(str(p["cal_shift"]))
        self._update_table()

    def _apply_edit(self):
        if self.selected_key is None:
            return
        p = self.points[self.selected_key]
        try:
            if self.x_var.get().strip():
                p["cal_x"] = float(self.x_var.get())
            if self.y_var.get().strip():
                p["cal_y"] = float(self.y_var.get())
            if p["base_shift"] is not None and self.shift_var.get().strip():
                p["cal_shift"] = float(self.shift_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入数字")
            return
        self._update_table()

    def _save(self):
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
        except ValueError:
            messagebox.showerror("错误", "宽高必须是数字")
            return
        points = {}
        for key, p in self.points.items():
            if p["cal_x"] is None or p["cal_y"] is None:
                continue
            point = {"x": p["cal_x"], "y": p["cal_y"]}
            if p["base_shift"] is not None:
                fallback_shift = p["base_shift"] * (h / 25.0)
                point["shift"] = p.get("cal_shift") if p.get("cal_shift") is not None else fallback_shift
            points[key] = point
        if not points:
            messagebox.showwarning("提示", "还没有任何校准数据")
            return
        data = {"window_width_cm": w, "window_height_cm": h, "points": points}
        if self.map_positions:
            data["map_positions"] = self.map_positions
        rect = get_game_rect()
        if rect:
            data["window_origin"] = [rect[0], rect[1]]
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("完成", f"已保存 {len(points)} 个校准点到:\n{CALIBRATION_PATH}")

    def _reset(self):
        if not messagebox.askyesno("确认", "清除所有校准数据，恢复默认坐标？"):
            return
        if CALIBRATION_PATH.exists():
            CALIBRATION_PATH.unlink()
        for p in self.points.values():
            p["cal_x"] = None
            p["cal_y"] = None
            p["cal_shift"] = None
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
