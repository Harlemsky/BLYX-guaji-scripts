"""基于 OpenCV 的屏幕识别模块。

模板图片放在项目根目录 templates/ 下（例如 transport_menu.png、game_loaded.png）。
所有识别函数都是可选的：模板缺失或 OpenCV 不可用时返回 None/False，
调用方会回退到原来的固定等待逻辑，不影响现有功能。
"""
import time
from pathlib import Path

import numpy as np
import pyautogui

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    cv2 = None
    _HAS_CV2 = False

try:
    import pygetwindow as gw
    _HAS_PYWINDOW = True
except ImportError:
    gw = None
    _HAS_PYWINDOW = False

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_cache = {}


def template_available(name: str) -> bool:
    """模板文件是否已提供（供调用方决定是否启用识别逻辑）。"""
    return _HAS_CV2 and _load_template(name) is not None


def get_game_rect():
    """定位标题为“百炼英雄”的游戏窗口，返回 (left, top, width, height)；找不到返回 None。"""
    if not _HAS_PYWINDOW:
        return None
    try:
        wins = gw.getWindowsWithTitle("百炼英雄")
    except Exception:
        return None
    # 优先精确匹配“百炼英雄”（排除“百炼英雄挂机系统”等程序自身窗口），
    # 多个同名窗口时选可见且面积最大的（避免选中隐藏/离屏的旧窗口）
    exact = [
        w for w in wins
        if w.title.strip() == "百炼英雄"
        and w.left is not None and w.width > 0 and w.height > 0
    ]
    if exact:
        visible = [w for w in exact if getattr(w, "visible", True)]
        pool = visible or exact
        best = max(pool, key=lambda w: w.width * w.height)
        return best.left, best.top, best.width, best.height
    # 兜底：标题含“百炼英雄”，但排除挂机系统/校准工具/资源管理器
    for w in wins:
        title = w.title
        if any(k in title for k in ("挂机系统", "校准工具", "文件资源管理器")):
            continue
        if w.left is not None and w.width > 0 and w.height > 0:
            return w.left, w.top, w.width, w.height
    return None


def _load_template(name: str):
    """加载灰度模板（带缓存）；不存在返回 None。"""
    if name in _cache:
        return _cache[name]
    path = TEMPLATES_DIR / f"{name}.png"
    if not path.exists():
        _cache[name] = None
        return None
    # cv2.imread 在 Windows 上不支持中文路径，改用 imdecode
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    _cache[name] = img
    return img


def grab_frame():
    """截取当前屏幕并转为灰度图。"""
    try:
        shot = pyautogui.screenshot()
    except Exception:
        return None
    if shot is None:
        return None
    return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2GRAY)


def find_template(name: str, confidence: float = 0.8, frame=None):
    """在屏幕中查找模板，返回 (中心x, 中心y, 置信度)；找不到返回 None。"""
    if not _HAS_CV2:
        return None
    template = _load_template(name)
    if template is None:
        return None
    if frame is None:
        frame = grab_frame()
        if frame is None:
            return None
    h, w = template.shape[:2]
    res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < confidence:
        return None
    return max_loc[0] + w // 2, max_loc[1] + h // 2, float(max_val)


def wait_for(name: str, timeout: float = 10.0, interval: float = 0.5, confidence: float = 0.8):
    """等待模板出现，返回坐标；超时返回 None。"""
    if not _HAS_CV2 or _load_template(name) is None:
        return None
    if grab_frame() is None:
        return None  # 截屏不可用时不等待，交给调用方回退
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = find_template(name, confidence=confidence)
        if result:
            return result
        time.sleep(interval)
    return None


def wait_until_gone(name: str, timeout: float = 10.0, interval: float = 0.5, confidence: float = 0.8):
    """等待模板消失，返回 True；超时返回 False。"""
    if not _HAS_CV2 or _load_template(name) is None:
        return True
    if grab_frame() is None:
        return True  # 截屏不可用时视为无需等待
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_template(name, confidence=confidence) is None:
            return True
        time.sleep(interval)
    return False


def grab_region(rect):
    """截取屏幕指定区域 (left, top, width, height) 的灰度图。"""
    x, y, w, h = rect
    if x < 0:
        w += x
        x = 0
    if y < 0:
        h += y
        y = 0
    if w <= 0 or h <= 0:
        return None
    frame = grab_frame()
    if frame is None:
        return None
    return frame[y:y + h, x:x + w]


def wait_screen_stable(rect, timeout: float = 25.0, stable_seconds: float = 1.5, interval: float = 0.5,
                       diff_threshold: float = 3.0):
    """等待指定屏幕区域连续多帧几乎不变（画面稳定），返回 True；超时返回 False。"""
    if not _HAS_CV2:
        return False
    needed = max(1, int(stable_seconds / interval))
    prev = None
    stable_count = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur = grab_region(rect)
        if cur is None:
            time.sleep(interval)
            continue
        if prev is not None and cur.shape == prev.shape:
            diff = float(np.mean(cv2.absdiff(cur, prev)))
            if diff < diff_threshold:
                stable_count += 1
                if stable_count >= needed:
                    return True
            else:
                stable_count = 0
        prev = cur
        time.sleep(interval)
    return False


def click_template(name: str, confidence: float = 0.8, timeout: float = 5.0):
    """找到模板并点击其中心，返回是否点击成功。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = find_template(name, confidence=confidence)
        if result:
            x, y, _ = result
            pyautogui.click(x, y)
            return True
        time.sleep(0.3)
    return False
