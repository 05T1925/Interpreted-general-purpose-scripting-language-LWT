# S46 bounded schedule exploration

- Generated: `2026-11-09T03:21:00Z`
- Tool: `tools/model_check_concurrency.py`
- Mutant: `duplicate-delivery`
- Budget: max_runs=200 per program, max_decisions=30, time_budget=60.0s total

> This is bounded systematic exploration, **not** a formal proof. `BUDGET_EXHAUSTED` is not `PASS`.

| program | status | runs | outcomes | violations | min prefix | replay |
|---|---|---:|---:|---:|---|---|
| channel-blocked-then-queued | COMPLETE | 1 | 1 | 1 | [] | ok |
| channel-close-drain | COMPLETE | 1 | 1 | 1 | [] | ok |
| channel-exactly-once | COMPLETE | 1 | 1 | 1 | [] | ok |
| channel-fifo-three | COMPLETE | 1 | 1 | 1 | [] | ok |
| deadlock-two-receivers | COMPLETE | 3 | 1 | 0 | - | ok |
| join-error-origin | COMPLETE | 1 | 1 | 0 | - | ok |
| lost-update | COMPLETE | 19 | 2 | 0 | - | ok |
| nested-spawn-drain | COMPLETE | 5 | 1 | 0 | - | ok |

- Programs: 8
- Runs: 32
- Violations: 4
- Budget exhausted: 0
- Invalid prefixes (skipped): 0
- Thread leaks: 0
- Replay failures: 0

## Outcome classes

### channel-blocked-then-queued
- exit=0 stdout=`1,1,2\n` count=1 first_prefix=[]
- VIOLATION exit=0 minimized_prefix=[]

### channel-close-drain
- exit=0 stdout=`1\n1\n2\n` count=1 first_prefix=[]
- VIOLATION exit=0 minimized_prefix=[]

### channel-exactly-once
- exit=0 stdout=`7\n7\n` count=1 first_prefix=[]
- VIOLATION exit=0 minimized_prefix=[]

### channel-fifo-three
- exit=0 stdout=`1123\n` count=1 first_prefix=[]
- VIOLATION exit=0 minimized_prefix=[]

### deadlock-two-receivers
- exit=3 stdout=`` count=3 first_prefix=[]

### join-error-origin
- exit=0 stdout=`Boom\noriginal message\n` count=1 first_prefix=[]

### lost-update
- exit=0 stdout=`1\n` count=13 first_prefix=[]
- exit=0 stdout=`2\n` count=6 first_prefix=[1, 1]

### nested-spawn-drain
- exit=0 stdout=`done\n` count=5 first_prefix=[]
