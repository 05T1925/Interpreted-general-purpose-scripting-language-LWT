# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T104022Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `9d48a9ec125e`
- 最终 tip `b39a91e3ab9d`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（133.24 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 5.094 |  |
| version | 0 | 0.557 | lwt 0.3.0 |
| check | 0 | 0.402 | Check passed: 3 source file(s). |
| blackbox | 0 | 124.08 | passed=400 failed=0 total=400 |
| compileall | 0 | 1.758 |  |
| integrity | 0 | 1.156 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
