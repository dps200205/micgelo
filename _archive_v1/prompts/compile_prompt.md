# 标准编译提示词（md 标准 → 问题库）

> 用途：把一份新的评审标准 md 编译进 `question_bank/`。交给 WorkBuddy 或任意大模型执行，产出后必须运行 `lint_bank.py` 并人工审核改动。

## 输入

1. 新标准 md 全文，条款格式为 `### X01｜标题`，正文后接 `**不合格时：……**`。
2. 现有 `question_bank/observations.yaml` 与 `question_bank/clauses.yaml`。
3. `config.yaml` 中的槽位列表 `slots`。

## 任务

为每条条款写一个 `clauses.yaml` 条目，并只在确有必要时向 `observations.yaml` 新增观察问题。

## 规则

**拆分**
- 把条款拆成三类信息：适用性（何时评）、意图（作者想要什么）、观察（图上能看到什么）。
- 适用性写进 `applies_if`；意图从项目说明 `brief` 读取，不能让 Jev 猜；只有观察才写成 Jev 问题。
- 条款里每个“或/且”连接的独立判断拆成独立问题。仅为列举同一现象的几种形态时可保留，并在 `lint_ok` 写明理由。
- 无法写成可观察问题的部分，写进条款 `note`，交由大模型补判。

**复用优先**
- 先在现有观察问题中查找同义问题，能复用就引用，不新建。
- 与其他维度条款问的是同一件事时，引用同一个观察问题，并用 `same_as` 互相标注。

**观察问题写法**（遵循 typesafe-ai skill）
- 英文；一次只问一个判断；“是”为真时含义明确，不用双重否定。
- 问具体、看得见的东西，避免抽象术语。术语转写示例：静区 → "an area with little detail where the eye can rest"；面感 → "reads as one filled area"。
- 不问决策（不要写 "Is this composition good?"、"Should …"），决策写在条款的判定规则里。
- noul 必须写 `criteria.true` 和 `criteria.false`，且都描述具体情形，例如 false 不能只写 "not X"。
- choice 选项名用描述内容的 snake_case，不用 A/B/option_1/left。
- 图中具体元素一律使用槽位：`{subject}`、`{item}`（配合 `over`）；不得写入某张图的具体内容。槽位值自带冠词，模板中不写 "the {"。
- 左右比较、计数、比例等交给代码（例如 `image: halves`），不让 Jev 算。

**判定**
- noul 用 `good: true/false`；choice 用 `good_option_slot` / `good_options` / `match_brief` / `match_item`。
- 多元素展开时选择 `aggregate: worst` 或 `best`，并在 `note` 说明理由。
- 标准明确写有“可以合格”的例外（留白、刻意孤立、均匀纹样等）时，用 `soft: true` 或 `applies_if` 处理，不判硬性不合格。

## 产出后

1. 运行 `python lint_bank.py`，错误必须清零，警告逐条确认。
2. 人工审核改动。
3. 用 `cases/` 中的标注案例运行 `eval_cases.py`，一致率低的问题改写或转为大模型判定。
