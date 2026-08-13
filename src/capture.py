"""截图助手：按 F8 保存整屏截图到 templates_src/，按 ESC 退出。"""
import re
from pathlib import Path

import pyautogui
from pynput import keyboard

OUT_DIR = Path(__file__).resolve().parent.parent / "templates_src"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def next_index():
    """从已有截图的编号继续，避免重开工具后覆盖旧图。"""
    max_n = 0
    for p in OUT_DIR.glob("screenshot_*.png"):
        m = re.search(r"screenshot_(\d+)\.png$", p.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


index = next_index()


def take_shot():
    global index
    shot = pyautogui.screenshot()
    path = OUT_DIR / f"screenshot_{index:02d}.png"
    shot.save(path)
    print(f"[{index}] 已保存: {path}")
    index += 1


def on_press(key):
    if key == keyboard.Key.f8:
        take_shot()
    elif key == keyboard.Key.esc:
        return False


def main():
    print(f"截图保存目录: {OUT_DIR}")
    print("按 F8 截图，按 ESC 退出。")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
