# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T165426Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `f563866a219d`
- 最终 tip `87e9797f8d21`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（106.42 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.811 |  |
| version | 0 | 0.297 | lwt 0.3.0 |
| check | 0 | 0.258 | Check passed: 3 source file(s). |
| blackbox | 0 | 101.476 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.521 |  |
| integrity | 0 | 0.959 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
