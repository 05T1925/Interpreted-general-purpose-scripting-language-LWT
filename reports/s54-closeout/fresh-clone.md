# S48 fresh-clone verification

- Bundle: `C:\Users\28641\Desktop\大三上\程序设计实践\大作业\dist\lwt-submission-20261111T171232Z\lwt-history.bundle`
- Branch: `main`；bundle HEAD `ad366e09db9d`
- 最终 tip `f3dc36c4d782`；lag 白名单 通过：reports/s48-defense/package-index.json
- Result: **PASS**（116.54 s）

| step | exit | seconds | key output |
|---|---:|---:|---|
| git clone | 0 | 2.149 |  |
| version | 0 | 0.387 | lwt 0.3.0 |
| check | 0 | 0.336 | Check passed: 3 source file(s). |
| blackbox | 0 | 111.293 | passed=401 failed=0 total=401 |
| compileall | 0 | 1.404 |  |
| integrity | 0 | 0.863 | Project integrity: OK; cases=401; matrix_links=498; referenced_cases=401; unreferenced=0; exempt=0 |
