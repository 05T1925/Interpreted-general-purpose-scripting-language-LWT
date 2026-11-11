# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T172812Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `e2f34256a2f5`
- 最终 tip `df7962ae1983`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（114.02 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 2.545 |  |
| version | 0 | 0.352 | lwt 0.3.0 |
| check | 0 | 0.294 | Check passed: 3 source file(s). |
| blackbox | 0 | 108.38 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.424 |  |
| integrity | 0 | 0.933 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
