【aware】读到本条即为 aware：先答一行「回执：hook-action → 把这次「创建动作」写进一条 hook 规则：条件、值、回执行」，再开始工作；回执写在回复最开头，不是结尾。

【创建动作·一条 hook 就是条件加值】用户说“创建动作：「xxx」”时，指的是在 `.agent-ide/skills/hook` 里加一条 UserPromptSubmit 规则，不是待办、不是脚本别名、不是文档里的一个词。

规则的形状只有一种：条件加值。条件二选一——`--trigger keyword` 配 `--keywords a,b,c`（任一出现即命中），或 `--trigger fn`（由函数判定，如今只有 `tools` 一条，覆盖已装技能）。值是一份 `data/inject/<id>.md`，命中时原样贴在块头 `【<id>｜matched <命中词>】` 之下，不加判语、不分类、不追加别的块。

值的第一行固定是三件事：写 `【aware】`、给回执行 `回执：<id> → <看到本条后立刻要做的第一个动作>`、说明回执写在回复最开头。第二行起才是这一条要注入的语境正文。值里的动作写在第一行的回执里，不另设 `cmd` 字段。

加一条规则的命令逐字是：`./.agent-tools/hook add --id <id> --trigger keyword --keywords "a,b" --inject @.agent-ide/skills/hook/data/inject/<id>.md`；改一条用 `./.agent-tools/hook set <id> --keywords "…" --inject @<路径>`；删一条用 `./.agent-tools/hook rm <id>`，同时删掉它的值文件，不留同内容的第二份。

规矩三条：一，这个 skill 里不放生成器，值是逐条手写、就地改，不从别的文档切；二，命名跟着归属走——AGENTS 四章的规则用 `agents-` 打头，项目临时入口用 `temp-` 打头，行为规则用 `agent-` 打头；三，加完当场用 `echo '{"prompt":"<触发词>"}' | ./.agent-tools/hook` 验一次，块头、回执行、值首行三处对得上才算加完。
