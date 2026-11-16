# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261116T163412Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `b551f7eeae0a`
- 最终 tip `40c56a831460`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（133.37 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 2.359 |  |
| version | 0 | 0.412 | lwt 0.3.0 |
| check | 0 | 0.351 | Check passed: 3 source file(s). |
| blackbox | 0 | 127.876 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.51 |  |
| integrity | 0 | 0.778 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
