# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T184915Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `d997bc6ad1ad`
- 最终 tip `15ff9a6fc2b3`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（110.05 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 1.853 |  |
| version | 0 | 0.303 | lwt 0.3.0 |
| check | 0 | 0.264 | Check passed: 3 source file(s). |
| blackbox | 0 | 104.844 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.716 |  |
| integrity | 0 | 0.972 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
