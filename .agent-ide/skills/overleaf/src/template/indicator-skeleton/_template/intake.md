# Intake checklist (after a fence arrives from the supervisor, tick every item before cutting)

- [ ] **1 Store the original**: append a `## ROUND n · <date time>` section + `> source: <key>'s reply (export :start–end)`, with the body pasted as it is — **never overwritten** (overwriting hands the previous round's commission to the next round)
- [ ] **2 Read the state**: `ON-RAMP LEFT` and `## EXCLUDED` in `LOOP_STATE.md`; `task-queue list --id TEMP_<id>`
- [ ] **3 Reconcile**: each item of fence §4 against the queue's existing items — a duplicate does not enter the stack, a newly found gap is pushed onto the top
- [ ] **4 Judge the convention**: for each item ask "is the product a reading or a judgement"; judgements come back to this layer or go up
- [ ] **5 Mark dependencies**: each item writes `depends:#k` (empty when none); two items whose acceptance lines read the same product without a dependency marked = a cutting error
- [ ] **6 Cut**: land `units/#n-<slug>.md` (six lines: purpose · which file · acceptance line · dependency · budget · return)
- [ ] **7 Push to the queue**: `cp units/#n-*.md /tmp/ && task-queue push /tmp/#n-*.md --id TEMP_<id>` (the original stays in `units/`); **the queue is the undispatched pool, dispatch pops out of it**, and the completion credential is `returns/#n-verdict.md`
- [ ] **8 Run the ruler**: `python3 workspace/indicator/check.py <id>` → `PASS 12/12`

**Dispatch with any item unticked** and what was cut surfaces at collection as "the executor failed", when the cause is the intake.
