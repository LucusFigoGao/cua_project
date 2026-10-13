# TODO

## 1. grounding 精度（阻塞评估质量）

agent 能正确识别页面（认出 TrelloClone workspaces 和 Project Alpha），但像素坐标不准：
点了 `(308,265)`，目标实际在 `(590,285)`。

**坐标系本身已排除**：手动 `click(590,285)` 能正确导航到 `/board/board-1`；
截图缩放也排除了（`pyautogui.size()`、`ImageGrab`、chromium `--window-size` 全是
1920x1080，无 `force-device-scale-factor`）。这是模型能力问题。

两条路：

- 换模型，如 `gemini-2.5-computer-use-preview-10-2025`
- 加 set-of-mark 辅助 —— 但 SoM 依赖 a11y 树画框，而 a11y 当前不可用（见 README §5），
  要走这条得先重做沙箱模板让 `_gi` 匹配 python 3.12

## 2. M4 批量调度

`src/runner/batch_runner.py`：N 个 worker 线程消费任务队列。
每个 worker 拿实例是秒级的，批跑启动开销基本消失。并发上限 12 个实例（配额所限）。

## 3. 补 `src/smoke_test/test_apps_host.py`

开发机 app 的验证目前没有脚本覆盖，需要测三件事：
31 个 app 在开发机上起得来、沙箱经 `host.docker.internal` 能访问到、
不同 sid 之间状态互不污染。

## 4. 扩展到几百上千个网页

开发机磁盘（build 产物）会先于内存成为瓶颈（31 个 app 的 vite preview 合计才 1.68GB，
磁盘 70GB）。届时考虑按需拉起或反向代理分发。
