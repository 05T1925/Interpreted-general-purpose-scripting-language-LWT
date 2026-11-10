# GUI A–E 一页纸速查（现场用）

> 配套长文档：[`gui-acceptance-kit.md`](gui-acceptance-kit.md)。本页只放“3 步启动 + 3 个必看 + 异常怎么办 + CLI 降级”。
> **状态口径**：当前 `REGISTERED 0/5`，A–E 全部 `NOT_RUN`；只有你本人在无遮挡桌面执行并把截图/录屏放进 `evidence/gui/` 后，才由 `python tools/register_gui_evidence.py` 登记。登记 ≠ 通过。
> **停止规则（S21）**：窗口被遮挡、或无法判断输入属于谁，立即停止该项并记 `BLOCKED`，不绕过、不补拍、不换机重来冒充。

## 0. 十秒准备

```bash
python -m lwt --version                      # 期望 lwt 0.3.0
python -c "import tkinter; print(tkinter.TkVersion)"   # 期望 8.6
python tools/register_gui_evidence.py         # 结束前跑一次，登记证据
```

## A. 语义实验室（约 6 分钟）

```bash
python -m app.language_lab
```
1. 选 `examples/language_lab/division_by_zero.lwt`，点**预测**（说出预期：除零、带行列、退出 3）。
2. 点**运行**，对照实际输出与退出码；点**解释**看逐步说明。
3. **重置**后缩放窗口，再用中文输入法在注释里打一行字，切走再切回焦点。

必看：① 预测与实际一致；② 错误定位到行列；③ 缩放后布局不破、输入法不吞字。
异常：窗口被遮挡或焦点抢不回 → 停，记 `BLOCKED`。
CLI 降级：`python -m lwt examples/language_lab/division_by_zero.lwt`（退出 3、定位到行列）。

## B. 日志工作台（约 5 分钟）

```bash
python -m app.log_detective -- app/fixtures/sample.log
```
1. 过滤 `WARN`；2. 关键字 `retry` + `top=2`；3. 打开一个坏文件再切回正常文件。

必看：① WARN 计数与行列表一致；② top=2 只留两条；③ 坏文件后能恢复，不崩。
异常：读不到 fixture → 检查是否在仓库根执行；仍失败记 `BLOCKED`。
CLI 降级：`python -m lwt app/log_report.lwt -- app/fixtures/sample.log --level WARN --keyword retry --top 2`

## C. LWT Snake（约 6 分钟）

```bash
python -m app.lwt_snake
```
1. 方向键移动 + 吃食物；2. 开**提示/自动驾驶**看它自己走；3. 切走窗口（失焦）再回来，试**录制→回放→接管**。

必看：① 按键即时响应且不反向自杀；② 自动驾驶不撞墙；③ 失焦暂停、回放与录制一致。
异常：按键无响应或无法判断焦点归属 → 停，记 `BLOCKED`。
CLI 降级（规则层，无 GUI）：
```bash
diff <(tr -d '\r' < app/lwt_snake/demo.expected) \
     <(python -m lwt app/lwt_snake/game.lwt < app/lwt_snake/demo.commands | tr -d '\r')
```
自动 GUI 测试（**不等于**人工验收）：`python -m unittest tests.test_lwt_snake_gui -q`

## D. S41 只读 Tk 查看器（约 3 分钟）

```bash
python -m app.lwt_snake.counterfactual_ui
```
1. 载入 `reports/s41-found/witness.json`；2. 点**重新验真**；3. 切换见证后关闭窗口。

必看：① 载入后显示观察前缀与分支；② 重新验真给出同一结论；③ 关闭不报错、不留进程。
异常：文件选择框被遮挡 → 停，记 `BLOCKED`。
CLI 降级：直接读 `reports/s41-found/witness.json` 与 `reports/s41-found/report.md`；单测 `python -m unittest tests.test_lwt_snake_counterfactual -q`。

## E. PPT 逐页播放 + 桌面无遮挡（约 4 分钟）

1. 全屏播放 `slides/LWT介绍.pptx`（21 页）；2. 翻到第 10 页，确认原生图表 **12 个数值点**；3. 退出全屏，确认桌面无遮挡、输入归属清楚。

必看：① 21 页顺序正确；② 第 10 页图表可读、数值点 12 个；③ 投屏/录屏里没有遮挡物。
异常：投屏分辨率导致图表被裁 → 改用窗口模式并记录，不裁图充数。
CLI 降级：`python tools/run_defense_probe.py --claim ppt`

## 登记

```bash
# 文件名：<A-E>-<步骤>-<UTC时间戳>.<png|jpg|mp4>，例如 A-2-predict-20261110T120501.png
python tools/register_gui_evidence.py            # 写 reports/s48-defense/gui-acceptance.json
python tools/register_gui_evidence.py --require-all   # 五项齐全才退出 0
```

`REGISTERED n/5` 只表示材料已登记；PASS 必须你本人现场确认。缺项保持 `NOT_RUN`。
