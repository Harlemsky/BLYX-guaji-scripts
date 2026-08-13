
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, Button

from pynput import keyboard

from base import load_calibration
from golds.auto_kill_boss import KillBoss
from killing.auto_kill_monsters import Killing53, Killing54
from mines.auto_mining import Mines
from woods.auto_get_woods import Woods

WINDOW_TITLE = "百炼英雄挂机系统"
WINDOW_SIZE = "500x580"
SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "gui_settings.json"
AUTO_GET_WOODS = "自动收集木材"
AUTO_MINING = "自动采矿"
AUTO_KILL_BOSS = "自动打BOSS刷金币"
AUTO_KILL_MONSTERS_BFJQ = "冰封禁区自动挂机打怪"
AUTO_KILL_MONSTERS_BFWZ = "冰封王座自动挂机打怪"

global_win = None
current_task = None
stop_event = threading.Event()


def load_settings():
    """读取上次保存的界面配置；不存在或损坏时返回空字典。"""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(width_cm, height_cm, mode, route, all_auto, first_transport, boss_refresh):
    """保存界面配置，下次启动自动恢复。"""
    data = {
        "width_cm": width_cm,
        "height_cm": height_cm,
        "mode": mode,
        "route": route,
        "all_auto": all_auto,
        "first_transport": first_transport,
        "boss_refresh": boss_refresh,
    }
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class TaskManager:
    def __init__(self):
        global stop_event
        self.thread = None
        self.stop_event = stop_event
        self.task_instance = None

    def start_task(self, width: float, height: float, selected_mode: str, all_auto: bool, route: str = None,
                   use_first_transport: bool = True, use_refresh: bool = True):
        self.stop_task()

        print(f"挂机模式: {selected_mode}")
        if selected_mode == AUTO_KILL_MONSTERS_BFJQ:
            task_class = Killing53
        elif selected_mode == AUTO_GET_WOODS:
            task_class = Woods
        elif selected_mode == AUTO_MINING:
            task_class = Mines
        elif selected_mode == AUTO_KILL_MONSTERS_BFWZ:
            task_class = Killing54
        elif selected_mode == AUTO_KILL_BOSS:
            task_class = KillBoss
        else:
            task_class = Killing53
        if selected_mode == AUTO_KILL_BOSS:
            self.task_instance = KillBoss(
                width=width, height=height, all_auto=all_auto,
                route=route, use_refresh=use_refresh,
            )
        else:
            self.task_instance = task_class(width=width, height=height, all_auto=all_auto)
        self.task_instance.set_use_first_transport(use_first_transport)
        self.stop_event.clear()

        self.thread = threading.Thread(target=self._run_task, daemon=True)
        self.thread.start()

    def _run_task(self):
        try:
            self.task_instance.start(stop_event=self.stop_event)
        except Exception as e:
            print(f"任务执行出错: {e}")

    def stop_task(self):
        """停止当前任务"""
        if self.is_running():
            self.stop_event.set()
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                print("警告：任务线程未及时退出")

        # 重置状态
        self.thread = None
        self.task_instance = None

    def is_running(self):
        """检查任务是否在运行"""
        return self.thread and self.thread.is_alive()

def on_press(key):
    global stop_event, global_win
    if key == keyboard.Key.esc:
        print("ESC 键被按下，停止挂机")

        # 设置停止事件
        stop_event.set()

        return False


def key_listener():
    """键盘监听函数"""
    print("按 ESC 键退出程序...")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


def create_window():
    """创建主窗口界面"""
    global global_win

    win = tk.Tk()
    global_win = win
    # 设置标题
    win.title(WINDOW_TITLE)
    win.geometry(WINDOW_SIZE)

    # 配置网格布局权重，使内容居中
    win.grid_columnconfigure(0, weight=1)
    win.grid_columnconfigure(1, weight=1)
    win.grid_columnconfigure(2, weight=1)
    win.grid_columnconfigure(3, weight=1)

    # 标题标签
    title_label = tk.Label(win, text="请设置小程序宽高", font=('Arial', 12))
    title_label.grid(row=0, column=1, columnspan=2, pady=10)

    # 恢复上次配置：尺寸优先用校准文件（校准坐标只在尺寸匹配时生效），其余用上次保存的设置
    settings = load_settings()
    calib = load_calibration()
    default_w = str(calib["window_width_cm"]) if calib and calib.get("window_width_cm") is not None \
        else str(settings.get("width_cm", 14))
    default_h = str(calib["window_height_cm"]) if calib and calib.get("window_height_cm") is not None \
        else str(settings.get("height_cm", 25))

    # X坐标输入
    tk.Label(win, text="宽度(cm)", font=('Arial', 12)).grid(row=1, column=1, sticky='e', padx=5)
    center_x = tk.StringVar(value=default_w)
    x_entry = tk.Entry(win, bg='white', font=('Arial', 12), fg='red', textvariable=center_x)
    x_entry.grid(row=1, column=2, sticky='w', padx=5, pady=5)

    # Y坐标输入
    tk.Label(win, text="高度(cm)", font=('Arial', 12)).grid(row=2, column=1, sticky='e', padx=5)
    center_y = tk.StringVar(value=default_h)
    y_entry = tk.Entry(win, bg='white', font=('Arial', 12), fg='red', textvariable=center_y)
    y_entry.grid(row=2, column=2, sticky='w', padx=5, pady=5)

    # 模式选择
    mode_label = tk.Label(win, text='请选择挂机项目', font=('Arial', 12))
    mode_label.grid(row=3, column=1, columnspan=2, pady=10)

    selects = ttk.Combobox(win, state="readonly", font=('Arial', 11))
    selects.grid(row=4, column=1, columnspan=2, padx=10, pady=5, sticky='ew')
    mode_values = (
        AUTO_KILL_MONSTERS_BFJQ,
        AUTO_GET_WOODS,
        AUTO_MINING,
        AUTO_KILL_MONSTERS_BFWZ,
        AUTO_KILL_BOSS
    )
    selects["values"] = mode_values
    saved_mode = settings.get("mode")
    selects.current(mode_values.index(saved_mode) if saved_mode in mode_values else 0)

    # Boss路线选择（仅打Boss刷金币模式可用）
    route_label = tk.Label(win, text='Boss路线', font=('Arial', 12))
    route_label.grid(row=5, column=1, columnspan=2, pady=5)
    route_select = ttk.Combobox(win, state="readonly", font=('Arial', 11))
    route_select.grid(row=6, column=1, columnspan=2, padx=10, pady=5, sticky='ew')
    route_names = KillBoss.get_route_names()
    route_select["values"] = route_names
    saved_route = settings.get("route")
    if saved_route in route_names:
        route_select.current(route_names.index(saved_route))
    elif route_names:
        route_select.current(0)
    route_select.config(state=tk.DISABLED)

    def on_mode_change(event=None):
        """切换挂机模式时，只有打Boss模式允许选路线。"""
        if selects.get() == AUTO_KILL_BOSS:
            route_select.config(state="readonly")
            refresh_check.config(state="normal")
        else:
            route_select.config(state=tk.DISABLED)
            refresh_check.config(state=tk.DISABLED)

    selects.bind("<<ComboboxSelected>>", on_mode_change)

    # 首次传送选项：勾选=首次打开传送用“首次”坐标；不勾选=永远用普通传送坐标
    first_transport_var = tk.BooleanVar(value=bool(settings.get("first_transport", True)))
    first_transport_check = tk.Checkbutton(
        win,
        text="首次传送使用首次坐标(勾选=是)",
        variable=first_transport_var,
        font=('Arial', 11),
    )
    first_transport_check.grid(row=7, column=1, columnspan=2, pady=5)

    # Boss刷新选项：勾选=打完一轮后传送到5-1换图回城刷新Boss；不勾选=只循环
    boss_refresh_var = tk.BooleanVar(value=bool(settings.get("boss_refresh", True)))
    refresh_check = tk.Checkbutton(
        win,
        text="Boss刷新(打完传5-1换图回城)",
        variable=boss_refresh_var,
        font=('Arial', 11),
    )
    refresh_check.grid(row=8, column=1, columnspan=2, pady=5)

    # 自动化选择
    auto_select = tk.Label(win, text='是否全自动(是则不需要移动到指定位置)', font=('Arial', 12))
    auto_select.grid(row=9, column=1, columnspan=2, pady=10)

    # 共享变量
    selected_option = tk.BooleanVar()
    selected_option.set(bool(settings.get("all_auto", True)))  # 恢复上次选择

    def on_select():
        print(selected_option.get())

    # 单选框控件
    radio1 = tk.Radiobutton(
        win,
        text="是",
        variable=selected_option,
        value=True,
        command=on_select  # 选中时触发函数
    )
    radio1.select()
    radio2 = tk.Radiobutton(
        win,
        text="否",
        variable=selected_option,
        value=False,
        command=on_select
    )
    radio1.grid(row=10, column=1, columnspan=1)
    radio2.grid(row=10, column=2, columnspan=1)

    # 设置完所有控件后，按恢复的模式刷新路线下拉框可用状态
    on_mode_change()

    def current_settings():
        """收集当前界面配置（宽高允许小数，非法时保留原输入）。"""
        try:
            w = float(center_x.get())
        except ValueError:
            w = center_x.get()
        try:
            h = float(center_y.get())
        except ValueError:
            h = center_y.get()
        return {
            "width_cm": w,
            "height_cm": h,
            "mode": selects.get(),
            "route": route_select.get() if route_select["values"] else "",
            "all_auto": bool(selected_option.get()),
            "first_transport": bool(first_transport_var.get()),
            "boss_refresh": bool(boss_refresh_var.get()),
        }

    # 状态标签
    if calib:
        status_var = tk.StringVar(
            value=f"状态: 已加载校准({default_w} × {default_h})，请保持窗口尺寸一致"
        )
    else:
        status_var = tk.StringVar(value="状态: 准备就绪")
    status_label = tk.Label(win, textvariable=status_var, font=('Arial', 11), fg="blue")
    status_label.grid(row=11, column=1, columnspan=2, pady=5)

    # 按钮框架
    btn_frame = tk.Frame(win)
    btn_frame.grid(row=12, column=1, columnspan=2, pady=10)

    # 开始按钮
    def start_task():
        """启动任务函数"""
        global current_task
        try:
            width = float(center_x.get())
            height = float(center_y.get())
            mode = selects.get()
            all_auto = selected_option.get()
            route = route_select.get() if mode == AUTO_KILL_BOSS else None
            print("all_auto", all_auto)
            if mode == AUTO_KILL_BOSS and not route:
                status_var.set("错误: 请选择Boss路线")
                return

            # 保存本次配置，下次启动自动恢复
            save_settings(**current_settings())

            # 初始化任务管理器
            if current_task is None:
                current_task = TaskManager()

            current_task.start_task(
                width, height, mode, all_auto,
                route=route,
                use_first_transport=first_transport_var.get(),
                use_refresh=boss_refresh_var.get(),
            )
            status_var.set("状态: 运行中 - " + mode)
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
        except ValueError:
            status_var.set("错误: 请输入有效的坐标值")
        except Exception as e:
            status_var.set(f"错误: {str(e)}")

    start_btn = Button(btn_frame, text='开始挂机',
                       command=start_task,
                       font=('Arial', 12, 'bold'),
                       bg='#4CAF50',
                       fg='black',
                       width=10)
    start_btn.pack(side=tk.LEFT, padx=5)

    # 停止按钮
    def stop_task():
        """停止任务函数"""
        global current_task
        if current_task:
            current_task.stop_task()
            status_var.set("状态: 已停止")
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)

    stop_btn = Button(btn_frame, text='停止挂机',
                      command=stop_task,
                      font=('Arial', 12, 'bold'),
                      bg='#F44336',
                      fg='black',
                      width=10,
                      state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT, padx=5)

    # 提示信息
    tip_label = tk.Label(win, text="提示: 按ESC键可停止挂机", font=('Arial', 10), fg="gray")
    tip_label.grid(row=13, column=1, columnspan=2, pady=5)

    # 窗口关闭事件处理
    def on_closing():
        """窗口关闭时的处理"""
        global current_task
        # 停止当前任务
        if current_task:
            current_task.stop_task()

        # 保存当前界面配置
        save_settings(**current_settings())

        # 销毁窗口
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_closing)

    win.mainloop()

            
def main():
    """主函数"""
    global current_task

    # 创建并启动键盘监听线程
    key_thread = threading.Thread(target=key_listener, daemon=True)
    key_thread.start()

    # 在主线程中创建窗口
    create_window()

    # 窗口关闭后，确保停止所有任务
    if current_task:
        current_task.stop_task()

    print("程序已退出")


if __name__ == '__main__':
    main()
