# S47 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261110T024954Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `76bb4fb1e7dd`
- 最终 tip `dcb0b1e27fd4`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（159.49 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 0.939 |  |
| version | 0 | 0.555 | lwt 0.3.0 |
| check | 0 | 0.41 | Check passed: 3 source file(s). |
| blackbox | 0 | 154.378 | passed=400 failed=0 total=400 |
| compileall | 0 | 2.203 |  |
| integrity | 0 | 0.884 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
