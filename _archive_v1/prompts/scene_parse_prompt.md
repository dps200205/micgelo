# 场景解析提示词（每张图一次）

> 用途：由多模态大模型看图，输出 `scene.json`，供 `run_review.py` 填充问题模板。只描述看得见的元素，不评价好坏。

## 输出格式（严格 JSON）

```json
{
  "subject": {"name": "the golden statue of soldiers", "location": "left of center, on a pedestal"},
  "repeated_groups": [
    {"name": "the tall glowing vertical panels", "location": "behind the statue, spreading right", "target_read": "one_filled_area"}
  ],
  "guiding_lines": [{"name": "the diagonal spotlight beams", "location": "rising from the stage front"}],
  "large_areas": [{"name": "the tiled stage floor", "location": "bottom third"}],
  "dense_regions": [{"name": "the soldier statue group", "location": "left of center"}],
  "point_groups": [{"name": "the small stage lamps", "location": "along the stage front"}],
  "parser": "解析者与日期"
}
```

## 规则

- `name` 用英文名词短语并**带冠词**（the …），复数组用复数。名称要让没看过图的人也能找到它，例如写成 "the row of dark human silhouettes on the back wall"，不要写 "group 2"。
- `subject`：项目说明指定了主体时，以项目说明为准；没有明确主体时填 `null`。
- `repeated_groups`：多个相似元素组成的组。每张图最多 5 组，选最影响构图的。
- `target_read`：该组按设计应读成 `separate_items` / `one_continuous_path` / `one_filled_area` 中的哪一种。只有意图明显时才填，不确定填 `null`，由项目说明或人工补充。
- `guiding_lines`：承担方向或引导作用的线，最多 4 条。
- `large_areas`：主要块面，最多 4 个。
- `dense_regions`：需要看清内部内容的密区，不包括只作纹理的区域。
- `point_groups`：分散的小亮点、小物件等点状元素群。
- 不存在的类别填空列表 `[]`，不要硬凑。
- 运行器会先让 Jev 核对每个元素是否存在，解析错误的元素会被标为“无法判断”。
