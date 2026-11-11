# 教学云平台提交清单（S53）

> 平台：教学云平台 <https://ucloud.bupt.edu.cn/>；大作业 70%：代码审查、文档检查、功能演示、答辩（平时 30%）。
> **状态：未上传。** 上传必须由本人操作；本文件只证明“待上传的包与清单一致”，不代表已提交。

## 1. 待上传文件

| 项 | 路径 | 存在 | SHA-256 | 校验 | 说明 |
|---|---|---|---|---|---|
| 提交包 zip | `dist/lwt-submission-20261111T171232Z/lwt-submission.zip` | 是 | `e930d8b6d74d…` | 一致 | 解压后即为完整仓库；--verify-blackbox 会实跑 401 黑盒 |
| Git 历史 bundle | `dist/lwt-submission-20261111T171232Z/lwt-history.bundle` | 是 | `6f8d2d0749df…` | 一致 | 截止 SHA ad366e09db9d；git fetch <bundle> main 可复核 |
| PPT | `slides/LWT介绍.pptx` | 是 | `809320b2aee6…` | 一致 | 21 页；内容本阶段未改动 |
| README.md | `README.md` | 是 | `1cc415582a8f…` | 一致 | 教师入口：三分钟验收路径 + 当前状态 |
| SUBMISSION.md | `SUBMISSION.md` | 是 | `df50c1307ce4…` | 一致 | 8 项提交内容 + 第 8 章任务对照 |
| docs/language-spec.md | `docs/language-spec.md` | 是 | `f7d8a9649ea0…` | 一致 | §1–§11 正式语言规范 |
| docs/test-matrix.md | `docs/test-matrix.md` | 是 | `70b37b201d9c…` | 一致 | 覆盖矩阵（§8 逐项打勾） |
| docs/defense-qa-card.md | `docs/defense-qa-card.md` | 是 | `91319542a354…` | 一致 | 答辩问答卡 |
| docs/agent-friendly-interface.md | `docs/agent-friendly-interface.md` | 是 | `409621c1bffd…` | 一致 | 课件 4.4/4.5 接口对照 |
| docs/s53-mutation-interface.md | `docs/s53-mutation-interface.md` | 是 | `5c0593ffd3a0…` | 一致 | S53 报告 |
| reports/s53-mutation/mutation-report.json | `reports/s53-mutation/mutation-report.json` | 是 | `594a4eb4bd9d…` | 一致 | 变异探针证据 |
| reports/s52-course-align/performance-space.json | `reports/s52-course-align/performance-space.json` | 是 | `bfa147edf48c…` | 一致 | 空间/分位数性能证据 |

## 2. 大作业 70% 四项 → 仓库证据

| 评分项 | 证据 | 复算命令 |
|---|---|---|
| 代码审查 | `lwt/`、`tools/`、`tests/`；每阶段提交信息含改动理由 | `python -m compileall -q lwt app tools tests` |
| 文档检查 | `README.md`、`SUBMISSION.md`、`docs/language-spec.md`、`docs/test-matrix.md`、`docs/agent-friendly-interface.md` | `python -m unittest tests.test_doc_consistency -q` |
| 功能演示 | `docs/onsite-runbook.md` 的 5 条必跑命令 + `docs/demo-script.md` | `python -m lwt examples/guide/hello.lwt` |
| 答辩 | `docs/defense-qa-card.md`（含 S53 新增 3 问） | 见该文件 |

## 3. 校验结果

- 必需文件 SHA 全部一致：**True**
- 解压后 401 黑盒：**401/401**（checked=True，exit=0）
- 总判定 `all_pass`：**True**
- 包索引：`reports/s48-defense/package-index.json`（tip `ad366e09db9d`）

## 4. 复现

```bash
python tools/check_platform_bundle.py --verify-blackbox
```
