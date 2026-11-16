id: <identifier>
unit: "1"
level: <照抄单元里那一级>   # freeze｜pave｜take the number｜scale；空着或抄错，上层判不了这一轮的产物进没进下一级
leaf: <leaf id>           # and loop_state.json 的接线；写错叶子，这一轮的进度就记到别人头上
status: DONE            # 七种之一，见 03-executor.md §2：DONE | BLOCKED(depends|criterion-unreachable|no-signal|result-not-established|write scope) | OVER-BUDGET(<step>)
ratio: 1                # 这一项自己完成到几成；DONE ⟺ ratio: 1
gap: <还差什么才算 done，一句>
est_min: <还差多少分钟，给区间>
---

# unit #1 return

## what I read
- `<path>:<line>` —— one line of explanation

## what I did（each with its command）
- `<command>` → `<reading>`

## acceptance line逐条
| criterion | reading | pass/fail |
|---|---|---|

## where it is stuck（`BLOCKED(...)` write only when）
- what is missing、who must supply it、what was tried
