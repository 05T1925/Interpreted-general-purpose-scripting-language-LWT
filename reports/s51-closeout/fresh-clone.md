# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T033545Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `1404f1e714e4`
- 最终 tip `dfc1ee82cd60`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（201.85 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 3.682 |  |
| version | 0 | 0.596 | lwt 0.3.0 |
| check | 0 | 0.489 | Check passed: 3 source file(s). |
| blackbox | 0 | 193.773 | passed=400 failed=0 total=400 |
| compileall | 0 | 1.891 |  |
| integrity | 0 | 1.295 | Project integrity: OK; cases=400; matrix_links=497; referenced_cases=400; unreferenced=0; exempt=0 |
