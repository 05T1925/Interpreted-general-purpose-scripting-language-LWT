# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T164926Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `12b26810b3b0`
- 最终 tip `c52675f2c491`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（103.71 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.79 |  |
| version | 0 | 0.309 | lwt 0.3.0 |
| check | 0 | 0.345 | Check passed: 3 source file(s). |
| blackbox | 0 | 99.048 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.277 |  |
| integrity | 0 | 0.858 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
