# 下发块模板（组长一轮交 1–5 个）

**每个块照抄下面这块**，只改尖括号处。块内**禁止三反引号**；块外**零散文**；全部块之后**只写报数**。

```PROMPT
id: <identifier>
root：<项目根绝对路径>
entry：<项目根>/.agent-ide/skills/overleaf/src/template/docs/strategy-roleplay/03-executor.md
# unit #<n> <item名>
level：<freeze | pave | take the number | scale>（上一级的放行读数：<一句>）
purpose：<这一项为哪条分句／哪条路；`paves:` 写在这里>
what to do：<一句概要，能让用户判断该不该复制>
which file：<可写路径，不是入口/模板>
acceptance line：<可重算的数：exit=0 / non-finite 0 / ocr_hits≥3/4 …>
depends：#<k>（无则写“none”）
budget：<步数上限 / 耗时上限 / 卡数>
return：indicator/<identifier>/returns/#<n>.md（首行 `# unit #<n>`）
```

**发完的最后一段（只这一段，不许有别的话）**：

> this round dispatches N items：#<a> <一句话目的>；#<b> <一句话目的>……（依赖未 resolve 的项写 `excluded: #k because <depends>`）

**为什么前三行是死的**：执行层拿到的必须和组长拿到的一样——**`id`（哪一轮）＋entry（你是哪一层）＋root（在哪干活）**。missing“root”，它会自己去猜一棵树；missing“entry”，它不会知道自己只做一项。

**自检五条**：①块数＝报数里的 N；②每个块首两行是 `purpose`／`what to do`；③块内三反引号计数＝0；④前三行是 `id:`／`root：`／`entry：`；⑤**开始行是 `\`\`\`PROMPT`，不是裸 `\`\`\``**。

**反例（本轮实测 `9200e4b3`）**：写成 `\`\`\`` 起行、把 `PROMPT` 放进正文首行——**用户按 `\`\`\`PROMPT` 检索时一块都命中不到**，六个围栏全成了“没有标记的代码块”。**`PROMPT` 是围栏的语言标记，不是正文的一行。**
