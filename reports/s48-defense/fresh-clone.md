# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261110T074855Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `bfda042c5026`
- 最终 tip `e8d64b56ce7c`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（173.12 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.669 |  |
| version | 0 | 0.583 | lwt 0.3.0 |
| check | 0 | 0.439 | Check passed: 3 source file(s). |
| blackbox | 0 | 167.907 | passed=400 failed=0 total=400 |
| compileall | 0 | 1.583 |  |
| integrity | 0 | 0.782 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
