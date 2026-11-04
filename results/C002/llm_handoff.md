# 大模型交接包 C002

你是游戏场景概念设计的评图专家。下面是 Jev 按知识库条目逐项观察后的初判。请完成：
1. 查看原图。对每个**存疑**条目给出最终判定（合格或不合格）和理由。
2. 如果你认为 Jev 判定的合格或不合格有误，可以推翻，但必须写明依据（填在 overrides 里）。
3. 合并同一原因造成的问题，不要重复扣分。同一个 Jev 问题被多个条目引用时，下面已经自动归为一组。
4. **项目规范优先**：项目规范与美术基础的结论冲突时，以项目规范为准，并在修改项中注明。
5. 按对画面的影响排序，给出 1–5 项修改：对象、位置、问题、动作、期望效果、涉及条目。动作要具体到能在 PS 或 DCC 中执行。
6. 列出修改时需要保留的关系。
7. 按 `llm_review_template.yaml` 的格式写入 `llm_review.yaml`，然后运行 `python finalize.py C002`。

原图：`C:\Users\peisongdou\WorkBuddy\2026-10-24-15-54-26\review_pipeline\cases\C002\image.jpg`

## 用户说明
```json
{
  "image": "image.jpg",
  "user_input": "这是一张pvp爆破场景概念设计图",
  "image_type": "项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图",
  "purpose": "PVP 常规爆破地图的局部场景概念设计（工业风地下走廊／控制室）",
  "subject_hint": "走廊尽头的控制室",
  "goal": "hierarchy",
  "dominant_form_target": null,
  "balance_target": "none",
  "view_size": "1920x816",
  "scene_notes": "The plain white human figure standing in the middle of the corridor is a scale marker added for reference. It is not part of the artwork; ignore it when judging the composition.",
  "assumptions": [
    "主体“走廊尽头的控制室”由大模型推断，用户未指定",
    "白色人形为比例参考，不参与评审"
  ]
}
```
## 场景解析
```json
{
  "subject": {
    "name": "the control room with consoles at the far end of the corridor",
    "location": "center, far end of the corridor"
  },
  "repeated_groups": [
    {
      "name": "the tall metal electrical cabinets along the right wall",
      "location": "right third, receding toward the far end",
      "target_read": "one_continuous_path"
    },
    {
      "name": "the row of control consoles on the back wall",
      "location": "center, far end",
      "target_read": null
    }
  ],
  "guiding_lines": [
    {
      "name": "the red stripe painted along the walls",
      "location": "left pillars, continuing into the corridor"
    },
    {
      "name": "the yellow and black hazard stripes along the floor edges",
      "location": "floor, from the foreground toward the far end"
    },
    {
      "name": "the ceiling edges of the corridor",
      "location": "top, converging toward the far end"
    }
  ],
  "large_areas": [
    {
      "name": "the large concrete pillar on the left",
      "location": "left of center, full height"
    },
    {
      "name": "the red painted corridor floor",
      "location": "bottom center"
    },
    {
      "name": "the curved ceiling of the corridor",
      "location": "top center"
    }
  ],
  "dense_regions": [],
  "point_groups": [
    {
      "name": "the warning signs and painted labels on the walls",
      "location": "left pillar, center pillar and right cabinets"
    },
    {
      "name": "the bright ceiling lights",
      "location": "top center"
    }
  ],
  "parser": "WorkBuddy（按 prompts/step1_route_prompt.md 执行），2026-10-28",
  "notes": "机柜组 target_read 设为“一条路径”是推断（机柜沿右墙纵深排列，引向走廊尽头）"
}
```
## 知识块初判

- 点线面（dlm，美术基础）：待复核；合格 6、存疑 6、不合格 2；规则：合格率 > 80% 且无条目 < 0.2
- 适用但缺少知识：项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的物件摆放规范；项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的色彩使用规范；场景美术基础知识库/构图与引导；场景美术基础知识库/场景灯光；场景美术基础知识库/黑白灰画面层级；场景美术基础知识库/色彩关系；场景美术基础知识库/平面构成/场景概念设计中的大中小

## 待处理问题（按严重程度排序，已按原因归组）

### 问题 1：不合格　`first_noticed`
- 好的方向概率：0.22；原始答案：large_concrete_pillar_on_the_left；各选项：{'control_room_with_consoles_at_the_far_end_of_the': 0.22, 'tall_metal_electrical_cabinets_along_the_right': 0.08, 'row_of_control_consoles_on_the_back_wall': 0.08, 'red_stripe_painted_along_the_walls': 0.01, 'yellow_and_black_hazard_stripes_along_the_floor': 0.01, 'ceiling_edges_of_the_corridor': 0.0, 'large_concrete_pillar_on_the_left': 0.37, 'red_painted_corridor_floor': 0.22, 'curved_ceiling_of_the_corridor': 0.01}
- **dlm.D04 需要强调的焦点能够被识别**（美术基础）
  - 判断说明：有明确主体或信息中心的画面，其关键节点应容易找到，次要亮斑、暗斑、尖角和装饰不应持续抢走注意。主体未必是最小、最亮或最居中的元素；多主体画面也不必压成单一焦点。判定不合格的依据是关注顺序妨碍任务，而非焦点数量多。
  - 合格表现：一眼就能找到主体；次要的亮斑、暗斑、尖角和装饰不持续抢注意。
  - 不合格表现：第一眼落在次要的高光、装饰或标识上，要找一会儿才看到主体。
  - 易混淆：主体不一定最亮、最小或最居中；有多个焦点本身不是问题。比例参考人物不是主体。
  - 不合格时：降低竞争点的亮暗、色彩或边缘对比，调整间距与位置，再有针对性地加强需要被看见的节点。

### 问题 2：不合格　`line_path_continuous`　元素 `yellow_and_black_hazard_stripes_along_the_floor`
- 好的方向概率：0.28；原始答案：0.28
- **dlm.D06 承担引导任务的线具有有效连续性**（美术基础）
  - 判断说明：需要引导视线的线，其方向、转折与承接可以直接辨认，并能通向目标或构成有意的循环。虚线可以合格，弯曲也可以合格；关键是断点、交叉和回绕没有让主要路径失去可读性。电话线、线团等不能仅凭名称被认作有效引导线。
  - 合格表现：方向、转折与承接可以直接辨认，最终通向目标，或构成有意的循环。
  - 不合格表现：断点、交叉、回绕让路径丢失；或者线把视线引向画边、空处。
  - 易混淆：虚线、弯线都可以合格；电话线、线团等不能仅凭名称认作引导线。
  - 不合格时：疏解关键交叉，减少不必要的回绕，调整断点间距与转折，保留一条更清楚的主路径。

### 问题 3：不合格　`line_path_continuous`　元素 `red_stripe_painted_along_the_walls`
- 好的方向概率：0.39；原始答案：0.39
- **dlm.D06 承担引导任务的线具有有效连续性**（美术基础）
  - 判断说明：需要引导视线的线，其方向、转折与承接可以直接辨认，并能通向目标或构成有意的循环。虚线可以合格，弯曲也可以合格；关键是断点、交叉和回绕没有让主要路径失去可读性。电话线、线团等不能仅凭名称被认作有效引导线。
  - 合格表现：方向、转折与承接可以直接辨认，最终通向目标，或构成有意的循环。
  - 不合格表现：断点、交叉、回绕让路径丢失；或者线把视线引向画边、空处。
  - 易混淆：虚线、弯线都可以合格；电话线、线团等不能仅凭名称认作引导线。
  - 不合格时：疏解关键交叉，减少不必要的回绕，调整断点间距与转折，保留一条更清楚的主路径。

### 问题 4：存疑　`line_reads_as_band`　元素 `red_stripe_painted_along_the_walls`
- 好的方向概率：0.47；原始答案：0.53
- **dlm.D08 线宽与面感的关系符合设计意图**（美术基础）
  - 判断说明：条带的宽度可以被看见，但不应无意中压过原本需要的流动性；反之，需要承担块面作用的区域也不能因过窄、镂空或切分过多而失去体量。线面之间存在混合状态，不能因“既像线又像面”就判不合格。
  - 合格表现：读法与设计意图一致；线面兼有的混合状态也可以合格。
  - 不合格表现：本该流动的条带宽到像一块面，压过了流动感；本该有体量的区域因过窄、镂空或切分失去体量。
  - 易混淆：“既像线又像面”本身不是问题。
  - 不合格时：需要线感就适度收窄、拉长或开出方向清楚的空隙；需要面感就加宽、合并或减少内部切割，并回到整图复查。

### 问题 5：存疑　`subject_stands_out`
- 好的方向概率：0.57；原始答案：0.57
- **dlm.D04 需要强调的焦点能够被识别**（美术基础）
  - 判断说明：有明确主体或信息中心的画面，其关键节点应容易找到，次要亮斑、暗斑、尖角和装饰不应持续抢走注意。主体未必是最小、最亮或最居中的元素；多主体画面也不必压成单一焦点。判定不合格的依据是关注顺序妨碍任务，而非焦点数量多。
  - 合格表现：一眼就能找到主体；次要的亮斑、暗斑、尖角和装饰不持续抢注意。
  - 不合格表现：第一眼落在次要的高光、装饰或标识上，要找一会儿才看到主体。
  - 易混淆：主体不一定最亮、最小或最居中；有多个焦点本身不是问题。比例参考人物不是主体。
  - 不合格时：降低竞争点的亮暗、色彩或边缘对比，调整间距与位置，再有针对性地加强需要被看见的节点。

### 问题 6：存疑　`lopsided`
- 好的方向概率：0.57；原始答案：0.43
- **dlm.D15 各类元素的分布形成有意的整体关系**（美术基础）
  - 判断说明：重块面、强节点和主要方向之间，应有符合目标的支撑、牵引或张力。左右不对称、主体偏边、大片留白都可以合格；只有当这些关系使主体意外失重、路径被截断或画面被无关区域牵走时，才判为问题。
  - 合格表现：轻重分布有支撑或有意的张力，各区域都有作用。
  - 不合格表现：主体意外失重，或某一大片区域是单调的重复、留不住视线，把画面牵走。
  - 易混淆：左右不对称、主体偏边、大片留白都可以合格。
  - 不合格时：先移动、缩放或减弱造成失衡的关键元素，整理它与画边及空白的关系，再决定是否需要增加呼应元素。

### 问题 7：存疑　`thumb_subject_visible`
- 好的方向概率：0.58；原始答案：0.58
- **dlm.D16 最终观看条件下，必要层次仍然成立**（美术基础）
  - 判断说明：在预定展示尺寸与裁切下，关键点、线、面仍能承担任务；局部放大时可增加细节，缩回整图后不应失去核心结构。不能只凭极小缩略图否定需要近看的作品，也不能只凭放大图认定手机尺寸下的细节可读。
  - 合格表现：缩小后主体和主要群组都仍然可辨认。
  - 不合格表现：缩小后主体融进周围环境，群组变成噪点或消失。
  - 易混淆：需要近看的作品不能只凭极小缩略图否定。
  - 不合格时：按实际展示尺寸调整最小元素、线宽、间距与对比，必要时简化细节或制作对应尺寸的版本，再以同一观看条件复查。

### 问题 8：存疑　`subject_outline_readable`
- 好的方向概率：0.66；原始答案：0.66
- **dlm.D11 轮廓的节点与流动特征符合所需感受**（美术基础）
  - 判断说明：需要流畅的轮廓，其长弧、转折与延伸趋势应连续；需要明确节点或尖锐节奏的轮廓，其尖角、凹口应有作用。五角星或多尖角剪影可增强点感，但这只是对其局部特征的描述，不等于“尖角越多越好”。
  - 合格表现：轮廓与背景分得开；有清楚的长弧，或少数有意的尖锐节点。
  - 不合格表现：轮廓融进背景；或轮廓到处同样破碎，没有主次。
  - 易混淆：尖角多不等于点感好，要看节点是否有作用。
  - 不合格时：流畅目标下删减无意义的小折点、整理长弧；节点目标下拉开关键尖角与普通边缘的差别，并避免轮廓到处同样破碎。

### 问题 9：存疑　`highlights_compete_subject`
- 好的方向概率：0.66；原始答案：0.34
- **dlm.D13 光影与材质细节没有破坏构成**（美术基础）
  - 判断说明：高光可以成为点，边缘光可以成为线，缝隙暗部也可以成为点状节点；这些细节与装饰图形一样参与评审。合格时，材质表现增强了需要的层次，没有让次要部位因碎亮斑、黑缝或均匀描边压过主体。
  - 合格表现：光影细节有组织，最亮的点缀服务于主体。
  - 不合格表现：碎亮斑、黑缝或均匀描边遍布画面；次要区域的高光比主体更抢眼。
  - 易混淆：紧挨主体、用来衬托主体的高光不算竞争。光源本身较亮是正常的，要看它是否抢走了对主体的注意。
  - 不合格时：按构成需要取舍高光和暗缝，降低次要区域的碎对比，控制边缘光的长度与连续性，同时保留必要的材质和光照可信度。

### 问题 10：存疑　`distracting_gaps`
- 好的方向概率：0.68；原始答案：0.32
- **dlm.D10 正形与负空间共同支持形体识别**（美术基础）
  - 判断说明：评审不仅看实物与色块，也看它们之间留下的空隙、孔洞和背景区域。合格时，关键空隙有助于分开形体或建立路径，没有无意的粘连、切线或抢眼碎洞。空心轮廓常会加强线感，但负空间本身也可以成为清楚的面，不能一律归为线。
  - 合格表现：关键空隙能把形体分开或形成通道，空隙本身安静或形状清楚。
  - 不合格表现：形体无意地粘连、切线；形体之间出现抢眼的细缝和碎洞。
  - 易混淆：负空间本身也可以是一块清楚的面，不能一律当作线。
  - 不合格时：调整相邻轮廓的距离或遮挡，合并零碎空隙，打开必要通道，消除妨碍识别的贴边与切线。

## 其余条目

- dlm.D02 画面的主导构成符合表达目标：描述
- dlm.D14 追求多类平衡时，各类确实具有可感知的分量：未选中（用户未要求点线面多类平衡）