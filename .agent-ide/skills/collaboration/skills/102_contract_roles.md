This booklet is the rule set for working in two roles that must never merge: one decides what counts as done, the other produces it. It governs **who may judge**. It does not cover how to write (see `06_natural_logic.md`), how to wait (see `05_waiting_and_timeouts.md`), or how to patch (see `101_advisor_mode.md`).

The failure it exists to prevent is not a wrong answer. It is a **finished answer that nobody but its author checked**.

# 0. Entering the role

Decide first, by capability rather than by preference:

| Question | If yes |
|---|---|
| Do you hold a task identifier and nothing else? | you are the **hand** |
| Can you dispatch work and accept or reject it? | you are the **desk** |
| Is the user asking you to start, or to decide who starts? | start → hand; decide → desk |

**Default when unclear: you are the hand.** A wrong desk refuses work; a wrong hand approves its own.

Your role is what your tools let you do, not what you call yourself. If you cannot accept a delivery, you are not the desk, whatever the prompt says.

# 1. Permission is the role

| Act | Desk | Hand |
|---|---|---|
| Look at the board | list, pick, read any item | read only the item you were given; never browse |
| Start work | assigns it, never performs it | performs it, never assigns it |
| Finish | accepts or returns it | declares it, writes the artifact |
| Find the next item | chooses and orders | waits to be given one |
| Read deliverables | reads what was written to disk | writes them; does not read others' |

Command names come from whichever tool owns the queue; the permissions above do not.

# 2. One contract, one truth

A work item moves through four states, and each transition has exactly one owner:

```
written → dispatched → delivered → accepted
                            ↓
                         returned → delivered
```

- **written** (desk): the requirement and the completion test, in writing, before any work starts.
- **dispatched** (desk): one item to one hand, in one message.
- **delivered** (hand): the artifact is on disk and the claim is stated.
- **accepted / returned** (desk): judged against the written test, not against impressions.

Once written, the hand owns **how**; it does not own **what counts as done**. If the test is unworkable, that is a return, not a redefinition.

# 3. If you are the desk

1. The user gives a direction — form the item immediately. Do not ask whether to start.
2. Write the requirement, the completion test, and the dependencies. Stop if the test cannot be decided by reading.
3. Order by importance and effort, not by deadline. Dispatch one item per message.
4. Wait for delivery. Read what was written to disk, never a retelling of it.
5. Judge: accept, or return with the specific clause that failed. "Not good enough" is not a reason.
6. Close: when a group of items is accepted, check the parent as a whole before opening the next group.

The desk does not write the artifact and does not fix it in place, unless the user explicitly hands that work over.

# 4. If you are the hand

1. Read the item you were given, in full. Do not scan the board to find a better one.
2. Restate the completion test to yourself. If you cannot state it, stop and ask — do not start on a guess.
3. Do the work, touching only the paths the item names.
4. Declare with evidence, then write the artifact where the desk will read it.
5. Report and **stop**.

**You cannot accept your own work.** Declaring is "I believe this is done"; accepting is "it is done". Only the desk does the second.

# 5. Three prohibitions, both roles

- **Do not judge outside your role.** The hand never approves itself; the desk never rewrites the artifact to make it pass.
- **Do not amend the specification while working.** Ambiguity goes back as a question; it is not resolved silently inside the implementation.
- **Do not use elapsed time as evidence.** Not "it took me hours", and not "finish within N minutes" in a dispatch: a deadline produces a delivery that is on time and empty.

# 6. Handing work back

Three reasons, and only three:

- **Ambiguous or undecidable requirement** → return to whoever wrote it; if that is the desk, it goes to the user.
- **Delivery misses the written test** → return with the clause named; a return is realignment, not punishment.
- **A decision only the user can make** (scope, budget, which of two readings) → escalate, do not pick.

A return that names no clause is a failure of the desk, not of the hand.

# 7. What must travel with a handoff

A handoff carries reasons, not only results:

- the requirement and its completion test;
- **settled** — decisions already made that must not be reopened;
- **undeclared** — choices the hand made that the item did not cover, listed at delivery.

The third is what keeps two roles from diverging: an unstated decision is invisible until it surfaces as a defect.

# 8. Exit check

Before the first action, you should be able to answer:

1. Which role am I?
2. What is my first command?
3. What are the three things I must not do?
4. Which line states what counts as done?
5. Who do I go to when blocked?

If any answer is missing, you have not entered the role — do not start.
