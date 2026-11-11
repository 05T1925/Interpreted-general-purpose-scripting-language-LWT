# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T142435Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `429b78fcc232`
- 最终 tip `cca58887f4d3`；lag 白名单 通过：docs/platform-submission.json, docs/platform-submission.md, reports/s48-defense/package-index.json
- Result: **PASS**（149.83 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 2.351 |  |
| version | 0 | 0.449 | lwt 0.3.0 |
| check | 0 | 0.351 | Check passed: 3 source file(s). |
| blackbox | 0 | 139.807 | passed=400 failed=0 total=400 |
| compileall | 0 | 2.578 |  |
| integrity | 0 | 4.055 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
