# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T055440Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `eee659f2125d`
- 最终 tip `8f960c3ce4d9`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（170.08 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.997 |  |
| version | 0 | 0.414 | lwt 0.3.0 |
| check | 0 | 0.37 | Check passed: 3 source file(s). |
| blackbox | 0 | 164.212 | passed=400 failed=0 total=400 |
| compileall | 0 | 1.713 |  |
| integrity | 0 | 1.252 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
