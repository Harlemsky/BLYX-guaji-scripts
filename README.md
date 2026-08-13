# 百炼英雄挂机脚本

基于 OpenCV 图像识别 + 鼠标模拟的微信小程序《百炼英雄》挂机脚本（Windows 版）。
仅供个人娱乐学习，请勿商用；挂机存在账号风险，请谨慎使用。

## 功能与模式

| 模式 | 说明 |
|---|---|
| 冰封禁区自动挂机打怪 | 冰冠堡垒 3 层-冰冠禁区，绕圈引怪打怪 |
| 自动收集木材 | 冰冠堡垒 1 层-王座大厅，自动打怪收木头 |
| 自动采矿 | 严寒地带-北风营地，自动采矿 |
| 冰封王座自动挂机打怪 | 冰冠堡垒 4 层-冰封王座 |
| 自动打BOSS刷金币 | 按配置路线传送、打 Boss、回城循环，路线可自定义 |

## 环境要求

- Windows + Python 3.13
- 依赖：`pyautogui`、`pynput`、`pillow`、`opencv-python`、`numpy`（见 `requirements.txt`）
- 项目自带 `.venv` 虚拟环境，可直接使用

## 快速开始

1. 打开微信和百炼英雄小程序，把小程序窗口调整到固定尺寸（建议约 7.5 × 13.5 cm），放到任意位置（建议固定一个位置）
2. **首次使用先校准**：双击 `校准工具.bat`，按列表捕获 角色中心 / 传送按钮 / 回城按钮 / 地图列表 / 层数列表 的真实坐标，点“保存校准”（会自动记录窗口位置，之后窗口随便移动都能准确定位）
3. 双击 `启动挂机脚本.bat` 打开挂机界面
4. 在界面里填小程序实际宽高（须与校准时一致）、选择挂机模式、选择 Boss 路线
5. 点“开始挂机”；停止时点“停止挂机”或按键盘 **ESC**

注意：窗口位置可以随意移动，但**窗口尺寸改变后需要重新校准**。

## 自动打BOSS刷金币：自定义路线

打 Boss 模式支持自定义传送路线，只需编辑 `config/boss_path.json`，无需改代码。

- `routes`：路线集合，界面下拉框可切换；每轮循环自动重新读取，改完无需重启
- 每个 Boss 条目：
  - `name`：名称（随意；名字含 `xb` 表示不打 Boss，只过图）
  - `map` / `level`：传送到第几张地图第几层（按传送菜单里的顺序）
  - `steps`：传送到位后的走位序列，每步包含：
    - `direction`：方向，可选 `up` / `down` / `left` / `right` / `left_up` / `left_down` / `right_up` / `right_down`
    - `drag_time`：拖拽秒数，越久走得越远
    - `pause_time`：停留/战斗秒数（可省略）
- `refresh_enabled`：打完一轮后是否执行 5-1 换图回城刷新（`false` 则只循环）
- `refresh`：刷新目标地图/层数/等待秒数
- `timing`：`after_kill_pause`（打完到回城的间隔）、`after_go_home_pause`（回城后等待）

示例（自定义一条两个 Boss 的路线）：

```json
"我的路线": {
  "bosses": [
    { "name": "2-1", "map": 2, "level": 1,
      "steps": [ { "direction": "right", "drag_time": 1.0, "pause_time": 3.0 } ] },
    { "name": "3-1", "map": 3, "level": 1,
      "steps": [ { "direction": "down", "drag_time": 6.0, "pause_time": 3.0 } ] }
  ],
  "refresh_enabled": true,
  "refresh": { "map": 5, "level": 1, "wait_seconds": 10 },
  "timing": { "after_kill_pause": 1, "after_go_home_pause": 6 }
}
```

## 内置路线

- **默认路线**：后期刷钱路线，依次打 2-1 → 3-1 → 3-2 → 3-3 → 4-1，打完一轮刷新 Boss 再循环，适合战力较高时持续刷金币
- **1-2路线**：7 万战力前的开荒路线（1-2 → 2-1 → 2-2 → 3-1，含 xb 过图条目）。如果你的游戏里还没有某些地图/层数，**直接删除对应条目即可**

## 目录结构

```
src/main.py                  挂机主程序（界面）
src/base.py                  鼠标操作与坐标体系
src/golds/auto_kill_boss.py  Boss 路线执行与战斗判定
src/vision.py                图像识别：模板匹配、窗口定位、画面稳定
src/calibrate.py             坐标校准工具
src/capture.py               截图工具（F8 截图）
config/boss_path.json        Boss 路线配置
templates/                   识别模板
```

## 免责声明

本项目仅供学习交流，请勿用于商业用途；挂机脚本存在违反游戏条款与账号封禁的风险，使用后果自负。
