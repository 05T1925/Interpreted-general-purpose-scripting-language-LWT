# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T183305Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `72da29e09759`
- 最终 tip `8a37965ac733`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（148.6 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 4.529 |  |
| version | 0 | 0.445 | lwt 0.3.0 |
| check | 0 | 0.332 | Check passed: 3 source file(s). |
| blackbox | 0 | 139.945 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.954 |  |
| integrity | 0 | 1.232 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
