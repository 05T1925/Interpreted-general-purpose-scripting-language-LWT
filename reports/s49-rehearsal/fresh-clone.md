# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261110T152326Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `55229dbc114f`
- 最终 tip `6bd95468c8cc`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（151.01 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.836 |  |
| version | 0 | 0.385 | lwt 0.3.0 |
| check | 0 | 0.334 | Check passed: 3 source file(s). |
| blackbox | 0 | 145.576 | passed=400 failed=0 total=400 |
| compileall | 0 | 1.617 |  |
| integrity | 0 | 1.066 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
