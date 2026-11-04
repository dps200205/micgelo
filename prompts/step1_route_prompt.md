# 第一步提示词：理解图片 → 渐进式检索 → 场景解析

> 交给多模态大模型执行（目前由 WorkBuddy 执行）。产出 `cases/<id>/` 下的三个文件：`brief.yaml`、`routing.yaml`、`scene.json`。完成后运行 `python route.py check <id>`。

## 输入
- 图片，以及用户的文字说明，例如“这是一张 PVP 爆破场景概念设计图”。
- 读取知识库的工具 `route.py`。只按下面的顺序读，**不要读评审标准全文**。

## 步骤

### 1. 整理用户说明 → `brief.yaml`
- `image_type`：在项目知识库中能对应到的最具体的图类型节点路径。
- 只记录用户说的，以及能从图上确定的信息；推断出来的内容写进 `assumptions`。
- 图中有比例参考人物、标注、水印等非美术内容时，用英文写进 `scene_notes`，说明它们不参与评审。
- 意图类字段没有依据时一律留 `null`：`goal`、`dominant_form_target`、`balance_target`。

### 2. 渐进式检索 → `routing.yaml`
1. `python route.py tree --depth 1`：读两个知识库的卡片。
2. 项目知识库：`python route.py tree --under 项目知识库 --depth 4`，按 `image_type` 逐层进入，只看这条路径下的知识块。
3. 美术基础知识库：根据画面里实际存在的元素和问题选择文件夹，用 `route.py tree --under <文件夹>` 查看其中的知识块。
4. 对状态为“可用”的知识块运行 `python route.py clauses <id>`，按“条目索引”的“何时适用”逐条决定：
   - 适用的条目写进 `clauses`；
   - 不适用的写进 `skipped` 并说明原因。
5. 适用、但状态为“待建设”的写进 `missing_knowledge`；读过卡片后判断不适用的写进 `skipped_blocks`。
6. 用户在说明里提出、知识库中没有的额外要求，按 questions.yaml 的格式写进 `extra`（观察问题用英文，判定方式同知识块）。没有就写 `null`。

### 3. 场景解析 → `scene.json`
只描述看得见的元素，不评价好坏。元素名称用英文名词短语并**带冠词**，要让没看过图的人也能凭名称找到它。

| 槽位 | 内容 | 上限 |
|---|---|---|
| `subject` | 主体或焦点区，`{name, location}`；不明确时填 null | 1 |
| `repeated_groups` | 成组的重复相似元素，附 `target_read`：`separate_items` / `one_continuous_path` / `one_filled_area` / null | 5 |
| `guiding_lines` | 承担方向或引导作用的线 | 4 |
| `large_areas` | 主要块面 | 4 |
| `dense_regions` | 需要看清内部内容的密区，只作纹理的区域不算 | 3 |
| `point_groups` | 分散的点状元素群 | 3 |
| 知识块声明的额外槽位 | 例如 `bombsites`，见各知识块 questions.yaml 的 `slots` | — |

- 比例参考人物等非美术内容**不要**列为任何元素。
- 不存在的类别填 `[]`，不要硬凑。运行时 Jev 会先核对每个元素是否存在，不存在的元素相关检查会记为“无法判断”。
