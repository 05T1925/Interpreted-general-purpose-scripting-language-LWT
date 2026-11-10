# 现场 GUI 证据目录（S48）

把本人现场验收的截图/录屏放在本目录，命名：`<A-E>-<步骤>-<UTC时间戳>.<png|jpg|mp4>`。

例如：`A-2-predict-20261110T120501.png`、`C5-replay-20261110T121530.mp4`。

- 只放**本人执行**的证据；不要放自动 GUI 测试的截图冒充人工验收。
- 放好后运行 `python tools/register_gui_evidence.py`，生成 `reports/s48-defense/gui-acceptance.{json,md}`。
- 缺项保持 `NOT_RUN`；登记不等于 PASS，最终结论由本人确认。
