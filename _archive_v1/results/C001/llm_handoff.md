# 大模型交接包 C001

你是评图专家。下面是 Jev 按评审标准逐项观察的结果。请完成：
1. 查看原图，对“存疑”项给出你的判断，并说明理由。
2. 把同一原因造成的问题合并（同一观察问题被多条条款引用时已自动归组），不要重复扣分。
3. 对“不适用/无法判断/描述”项和条款备注中“需大模型补判”的部分，结合项目说明补充判断。
4. 按对表达的影响排序，列出最重要的 1—3 项修改：对象、动作、期望效果，参照各条款的“不合格时”。
5. 如果你认为 Jev 的某个结论有误，明确指出并说明依据，不要静默推翻。

原图：`C:\Users\peisongdou\WorkBuddy\2026-10-24-15-54-26\review_pipeline\cases\images\C001.jpg`

## 项目说明
```json
{
  "purpose": "场景概念图／活动舞台视觉（假设，待确认）",
  "subject_hint": "左中部的金色士兵雕像",
  "goal": "hierarchy",
  "dominant_form_target": null,
  "balance_target": "none",
  "view_size": "1920x740",
  "dimensions": [
    "D",
    "J"
  ],
  "assumptions": [
    "用途与主体由 WorkBuddy 根据画面推断，未经作者确认",
    "未给出标题、按钮等功能区要求"
  ]
}
```
## 场景解析
```json
{
  "subject": {
    "name": "the golden statue of soldiers on the pedestal",
    "location": "left of center"
  },
  "repeated_groups": [
    {
      "name": "the tall glowing vertical panels behind the statue",
      "location": "back wall; tallest behind the statue, shorter toward both sides",
      "target_read": null
    },
    {
      "name": "the row of dark human silhouettes along the back wall",
      "location": "back wall, at the far left and across the right two-thirds",
      "target_read": "one_continuous_path"
    },
    {
      "name": "the large glowing pink letters on the back wall",
      "location": "back wall, left panels and right half",
      "target_read": null
    }
  ],
  "guiding_lines": [
    {
      "name": "the diagonal spotlight beams",
      "location": "rising from the stage front toward the top edge"
    },
    {
      "name": "the curved bright edge of the stage floor",
      "location": "sweeping from below the statue toward the right edge"
    }
  ],
  "large_areas": [
    {
      "name": "the dark blue back wall",
      "location": "upper half"
    },
    {
      "name": "the tiled stage floor",
      "location": "lower third"
    },
    {
      "name": "the reflective blue area on the right side of the floor",
      "location": "lower right"
    }
  ],
  "dense_regions": [
    {
      "name": "the cluster of soldier figures in the statue",
      "location": "left of center"
    }
  ],
  "point_groups": [
    {
      "name": "the small stage lamps along the front edge of the stage",
      "location": "a row at the base of the back wall"
    }
  ],
  "parser": "WorkBuddy（按 prompts/scene_parse_prompt.md 人工执行），2026-10-27"
}
```
## 各维度结论

- 点线面：不合格（合格 5，存疑 8，不合格 1，不适用 1，描述 1）
- 聚散：需优化（7 项存疑待复核）（合格 5，存疑 7）

## 待处理问题（按严重程度，已按原因归组）

### 问题 1：不合格　观察 `highlights_compete_subject`
- Jev 问题：Do highlights or glows away from the golden statue of soldiers on the pedestal pull the eye away from it in `scene`?
- 好的方向概率：0.25；原始答案：0.75
- 涉及条款 **D13 光影与材质细节没有破坏构成**
  - 标准：高光可以成为点，边缘光可以成为线，缝隙暗部也可以成为点状节点；这些细节与装饰图形一样参与评审。合格时，材质表现增强了需要的层次，没有让次要部位因碎亮斑、黑缝或均匀描边压过主体。
  - 不合格时：按构成需要取舍高光和暗缝，降低次要区域的碎对比，控制边缘光的长度与连续性，同时保留必要的材质和光照可信度。

### 问题 2：存疑　观察 `points_equally_loud`　元素 `small_stage_lamps_along_the_front_edge_of_the`
- Jev 问题：Are all of the small stage lamps along the front edge of the stage in `scene` about equally eye-catching?
- 好的方向概率：0.35；原始答案：0.65
- 涉及条款 **D05 多点分布形成可读的停顿关系**
  - 标准：多个点可以形成疏密、节奏、分组或有意的均匀重复；它们的停顿作用应服务整体，而非让视线在无关位置反复跳转。若处处同样醒目、又没有图案化或均等展示的目标，以致主体难找，则不合格。
  - 不合格时：删减无作用的点，将部分点并为组，或拉开大小、强弱与间距；需要均匀纹样时则修正重复节奏和边界接续。

### 问题 3：存疑　观察 `line_path_continuous`　元素 `diagonal_spotlight_beams`
- Jev 问题：Can the eye follow the diagonal spotlight beams in `scene` as one continuous path?
- 好的方向概率：0.41；原始答案：0.41
- 涉及条款 **D06 承担引导任务的线具有有效连续性**
  - 标准：需要引导视线的线，其方向、转折与承接可以直接辨认，并能通向目标或构成有意的循环。虚线可以合格，弯曲也可以合格；关键是断点、交叉和回绕没有让主要路径失去可读性。电话线、线团等不能仅凭名称被认作有效引导线。
  - 不合格时：疏解关键交叉，减少不必要的回绕，调整断点间距与转折，保留一条更清楚的主路径。

### 问题 4：存疑　观察 `line_reads_as_band`　元素 `curved_bright_edge_of_the_stage_floor`
- Jev 问题：Is the curved bright edge of the stage floor in `scene` so wide that it looks more like a flat area than a line?
- 好的方向概率：0.43；原始答案：0.57
- 涉及条款 **D08 线宽与面感的关系符合设计意图**
  - 标准：条带的宽度可以被看见，但不应无意中压过原本需要的流动性；反之，需要承担块面作用的区域也不能因过窄、镂空或切分过多而失去体量。线面之间存在混合状态，不能因“既像线又像面”就判不合格。
  - 不合格时：需要线感就适度收窄、拉长或开出方向清楚的空隙；需要面感就加宽、合并或减少内部切割，并回到整图复查。

### 问题 5：存疑　观察 `area_shape_clear`　元素 `dark_blue_back_wall`
- Jev 问题：In `scene`, is the overall shape of the dark blue back wall easy to see?
- 好的方向概率：0.37；原始答案：0.37
- 涉及条款 **D09 主要块面的形状与归属清楚**
  - 标准：需要承担主体、背景分区或整体支撑的面，其轮廓、范围和相互关系应可辨认；明暗、纹理和小装饰没有把必要的大形拆成难以组织的碎片。边缘可以虚化，块面可以重叠，但不能因此使关键形体误读。
  - 不合格时：先合并同属一个区域的碎明暗，减少内部高对比切割，再在关键轮廓处恢复必要的分离或遮挡关系。

### 问题 6：存疑　观察 `area_shape_clear`　元素 `reflective_blue_area_on_the_right_side_of_the`
- Jev 问题：In `scene`, is the overall shape of the reflective blue area on the right side of the floor easy to see?
- 好的方向概率：0.66；原始答案：0.66
- 涉及条款 **D09 主要块面的形状与归属清楚**
  - 标准：需要承担主体、背景分区或整体支撑的面，其轮廓、范围和相互关系应可辨认；明暗、纹理和小装饰没有把必要的大形拆成难以组织的碎片。边缘可以虚化，块面可以重叠，但不能因此使关键形体误读。
  - 不合格时：先合并同属一个区域的碎明暗，减少内部高对比切割，再在关键轮廓处恢复必要的分离或遮挡关系。

### 问题 7：存疑　观察 `area_broken_up`　元素 `tiled_stage_floor`
- Jev 问题：Is the tiled stage floor in `scene` broken into many small fragments by highlights, shadows or texture?
- 好的方向概率：0.56；原始答案：0.44
- 涉及条款 **D09 主要块面的形状与归属清楚**
  - 标准：需要承担主体、背景分区或整体支撑的面，其轮廓、范围和相互关系应可辨认；明暗、纹理和小装饰没有把必要的大形拆成难以组织的碎片。边缘可以虚化，块面可以重叠，但不能因此使关键形体误读。
  - 不合格时：先合并同属一个区域的碎明暗，减少内部高对比切割，再在关键轮廓处恢复必要的分离或遮挡关系。

### 问题 8：存疑　观察 `area_broken_up`　元素 `reflective_blue_area_on_the_right_side_of_the`
- Jev 问题：Is the reflective blue area on the right side of the floor in `scene` broken into many small fragments by highlights, shadows or texture?
- 好的方向概率：0.52；原始答案：0.48
- 涉及条款 **D09 主要块面的形状与归属清楚**
  - 标准：需要承担主体、背景分区或整体支撑的面，其轮廓、范围和相互关系应可辨认；明暗、纹理和小装饰没有把必要的大形拆成难以组织的碎片。边缘可以虚化，块面可以重叠，但不能因此使关键形体误读。
  - 不合格时：先合并同属一个区域的碎明暗，减少内部高对比切割，再在关键轮廓处恢复必要的分离或遮挡关系。

### 问题 9：存疑　观察 `shapes_merge`
- Jev 问题：In `scene`, do neighboring shapes touch or overlap so that it is hard to tell them apart?
- 好的方向概率：0.50；原始答案：0.5
- 涉及条款 **D10 正形与负空间共同支持形体识别**
  - 标准：评审不仅看实物与色块，也看它们之间留下的空隙、孔洞和背景区域。合格时，关键空隙有助于分开形体或建立路径，没有无意的粘连、切线或抢眼碎洞。空心轮廓常会加强线感，但负空间本身也可以成为清楚的面，不能一律归为线。
  - 不合格时：调整相邻轮廓的距离或遮挡，合并零碎空隙，打开必要通道，消除妨碍识别的贴边与切线。

### 问题 10：存疑　观察 `distracting_gaps`
- Jev 问题：Are there small eye-catching gaps or slivers of background between shapes in `scene`?
- 好的方向概率：0.60；原始答案：0.4
- 涉及条款 **D10 正形与负空间共同支持形体识别**
  - 标准：评审不仅看实物与色块，也看它们之间留下的空隙、孔洞和背景区域。合格时，关键空隙有助于分开形体或建立路径，没有无意的粘连、切线或抢眼碎洞。空心轮廓常会加强线感，但负空间本身也可以成为清楚的面，不能一律归为线。
  - 不合格时：调整相邻轮廓的距离或遮挡，合并零碎空隙，打开必要通道，消除妨碍识别的贴边与切线。
- 涉及条款 **J11 组间空白和静区具有明确作用**
  - 标准：群组之间的空间应有助于分隔、引导、衬托或提供停顿，没有妨碍识别的狭缝和抢眼碎洞。大片空白可以合格，满版也可以合格，不能要求固定留白比例；有标题、按钮或人物放置要求时，应按已给定的功能区核对。
  - 不合格时：通过移动、缩放或合并群组整理空白形状，打开必要通道，并优先清理已明确的功能区附近的高对比细节。

### 问题 11：存疑　观察 `group_reads_as`　元素 `row_of_dark_human_silhouettes_along_the_back`
- Jev 问题：As a whole, how do the row of dark human silhouettes along the back wall in `scene` read?
- 好的方向概率：0.57；原始答案：one_continuous_path；各选项：{'separate_items': 0.43, 'one_continuous_path': 0.57, 'one_filled_area': 0.0}
- 涉及条款 **D12 点线聚集后的整体性质没有偏离目标**
  - 标准：点群、排线和交织纹理在实际观看尺寸下，应保留所需的独立性、方向性或整体面感。需要逐个辨认的点不能糊成一块，需要连成路径的点不能散成无关碎片，需要统一成面的排线不能割裂成竞争条纹。
  - 不合格时：优先调整间距、数量、线宽、覆盖范围或对比度，使整体重新呈现目标感受；具体检查参见《聚散与疏密评测标准》。
- 涉及条款 **J09 聚集程度没有造成非预期的点线面转换**
  - 标准：需要独立点感时，点群不能在实际尺寸下合成一整片；需要线感时，沿线间距和方向应足以建立路径；需要面感时，内部空洞和断裂不应把整体拆散。应同时记录“由什么组成”和“整体主要像什么”。
  - 不合格时：按目标调整间隔、数量、方向、粗细或覆盖范围；每次改变后重新判断主导感受，不以“已经加密”或“已经减少”代替复查。

### 问题 12：存疑　观察 `lopsided`
- Jev 问题：Does `scene` feel lopsided, as if one side is much heavier than the other?
- 好的方向概率：0.39；原始答案：0.61
- 涉及条款 **D15 各类元素的分布形成有意的整体关系**
  - 标准：重块面、强节点和主要方向之间，应有符合目标的支撑、牵引或张力。左右不对称、主体偏边、大片留白都可以合格；只有当这些关系使主体意外失重、路径被截断或画面被无关区域牵走时，才判为问题。
  - 不合格时：先移动、缩放或减弱造成失衡的关键元素，整理它与画边及空白的关系，再决定是否需要增加呼应元素。
- 涉及条款 **J10 群组之间的视觉分量符合主次或平衡目标**
  - 标准：有主次的设计可以一聚区强、其他区域弱；要求多组平衡时，各组则应达到可感知的分量。不能仅用元素数量比较强弱：少量大而强的元素，可能压过大量小而弱的元素。
  - 不合格时：调整群组的面积、对比度、密度或位置，必要时削弱强组；增加小元素前，先判断它们是否会合成新的块面而改变原定关系。

### 问题 13：存疑　观察 `half_holds_eye`　元素 `right`
- Jev 问题：Does this part of an image, 8dba464f-right, contain something that holds the viewer's attention?
- 好的方向概率：0.60；原始答案：0.6
- 涉及条款 **D15 各类元素的分布形成有意的整体关系**
  - 标准：重块面、强节点和主要方向之间，应有符合目标的支撑、牵引或张力。左右不对称、主体偏边、大片留白都可以合格；只有当这些关系使主体意外失重、路径被截断或画面被无关区域牵走时，才判为问题。
  - 不合格时：先移动、缩放或减弱造成失衡的关键元素，整理它与画边及空白的关系，再决定是否需要增加呼应元素。

### 问题 14：存疑　观察 `thumb_group_visible`　元素 `large_glowing_pink_letters_on_the_back_wall`
- Jev 问题：In this small version of the image, 8dba464f-thumb, can the large glowing pink letters on the back wall still be seen as a group?
- 好的方向概率：0.69；原始答案：0.69
- 涉及条款 **D16 最终观看条件下，必要层次仍然成立**
  - 标准：在预定展示尺寸与裁切下，关键点、线、面仍能承担任务；局部放大时可增加细节，缩回整图后不应失去核心结构。不能只凭极小缩略图否定需要近看的作品，也不能只凭放大图认定手机尺寸下的细节可读。
  - 不合格时：按实际展示尺寸调整最小元素、线宽、间距与对比，必要时简化细节或制作对应尺寸的版本，再以同一观看条件复查。
- 涉及条款 **J12 聚散关系在实际观看尺度下仍有效**
  - 标准：在最终展示尺寸下，必要的群组、间隔和疏密差异应能被辨认。缩小时细节合成为面是正常现象，只有这种合并破坏目标时才算问题；放大后出现更多局部信息也不等于整体变乱。
  - 不合格时：用目标尺寸重新调整最小间距、元素大小与线宽，减少缩放后形成噪声或粘连的细节，并在整图和必要局部两种尺度下复查。

### 问题 15：存疑　观察 `group_merges_neighbor`　元素 `tall_glowing_vertical_panels_behind_the_statue`
- Jev 问题：Do the tall glowing vertical panels behind the statue in `scene` blend into nearby elements so that it is unclear where the group ends?
- 好的方向概率：0.65；原始答案：0.35
- 涉及条款 **J02 组内联系与组间分隔能够区分**
  - 标准：需要区分的群组，应有可见的边界或分隔依据。通常组内联系强于组间联系，但不要求每个内部间距都小于外部间距；颜色、连接和方向也可能决定分组。若组间缝隙与组内缝隙混同，以致元素归属不清，则不合格。
  - 不合格时：拉开关键组间距离，收紧关键组内距离，或用对比和方向区分；不要机械地把所有元素等距排开。

### 问题 16：存疑　观察 `group_merges_neighbor`　元素 `row_of_dark_human_silhouettes_along_the_back`
- Jev 问题：Do the row of dark human silhouettes along the back wall in `scene` blend into nearby elements so that it is unclear where the group ends?
- 好的方向概率：0.60；原始答案：0.4
- 涉及条款 **J02 组内联系与组间分隔能够区分**
  - 标准：需要区分的群组，应有可见的边界或分隔依据。通常组内联系强于组间联系，但不要求每个内部间距都小于外部间距；颜色、连接和方向也可能决定分组。若组间缝隙与组内缝隙混同，以致元素归属不清，则不合格。
  - 不合格时：拉开关键组间距离，收紧关键组内距离，或用对比和方向区分；不要机械地把所有元素等距排开。

### 问题 17：存疑　观察 `group_merges_neighbor`　元素 `large_glowing_pink_letters_on_the_back_wall`
- Jev 问题：Do the large glowing pink letters on the back wall in `scene` blend into nearby elements so that it is unclear where the group ends?
- 好的方向概率：0.45；原始答案：0.55
- 涉及条款 **J02 组内联系与组间分隔能够区分**
  - 标准：需要区分的群组，应有可见的边界或分隔依据。通常组内联系强于组间联系，但不要求每个内部间距都小于外部间距；颜色、连接和方向也可能决定分组。若组间缝隙与组内缝隙混同，以致元素归属不清，则不合格。
  - 不合格时：拉开关键组间距离，收紧关键组内距离，或用对比和方向区分；不要机械地把所有元素等距排开。

### 问题 18：存疑　观察 `stray_pull_from_subject`
- Jev 问题：Do small isolated elements in `scene` pull the eye away from the golden statue of soldiers on the pedestal?
- 好的方向概率：0.61；原始答案：0.39
- 涉及条款 **J06 散开的元素具有可解释的组织作用**
  - 标准：组外的点或小形，可以承担引导、呼应、平衡、延伸或有意孤立的作用。若若干散点既不参与这些关系，又造成注意分散、意外粘边或视觉噪声，则不合格；不能仅因一个元素远离群组就要求移回。
  - 不合格时：删除无作用的散点，或调整其位置、方向、大小与强度，使它与主组或表达目标建立可见联系。

### 问题 19：存疑　观察 `group_shape_clear`　元素 `tall_glowing_vertical_panels_behind_the_statue`
- Jev 问题：Taken as a whole, do the tall glowing vertical panels behind the statue in `scene` form an overall shape that is easy to see?
- 好的方向概率：0.68；原始答案：0.68
- 涉及条款 **J08 群组作为整体时具有可辨认的形状或方向**
  - 标准：当一群元素承担整体块面或方向组织时，应能看出其大致范围、主要延伸方向或形状特征。群组边缘可以不规则，但不能因少数无关突刺、飞点和碎凹口让整体范围难以辨认。
  - 不合格时：先把群组概括成简单轮廓或方向带，再移动边缘元素、删减孤立突刺，保留有助于表达的变化。

### 问题 20：存疑　观察 `group_outliers`　元素 `tall_glowing_vertical_panels_behind_the_statue`
- Jev 问题：Do a few of the tall glowing vertical panels behind the statue in `scene` stick out from the rest so that the group's outline looks messy?
- 好的方向概率：0.39；原始答案：0.61
- 涉及条款 **J08 群组作为整体时具有可辨认的形状或方向**
  - 标准：当一群元素承担整体块面或方向组织时，应能看出其大致范围、主要延伸方向或形状特征。群组边缘可以不规则，但不能因少数无关突刺、飞点和碎凹口让整体范围难以辨认。
  - 不合格时：先把群组概括成简单轮廓或方向带，再移动边缘元素、删减孤立突刺，保留有助于表达的变化。

### 问题 21：存疑　观察 `group_outliers`　元素 `row_of_dark_human_silhouettes_along_the_back`
- Jev 问题：Do a few of the row of dark human silhouettes along the back wall in `scene` stick out from the rest so that the group's outline looks messy?
- 好的方向概率：0.52；原始答案：0.48
- 涉及条款 **J08 群组作为整体时具有可辨认的形状或方向**
  - 标准：当一群元素承担整体块面或方向组织时，应能看出其大致范围、主要延伸方向或形状特征。群组边缘可以不规则，但不能因少数无关突刺、飞点和碎凹口让整体范围难以辨认。
  - 不合格时：先把群组概括成简单轮廓或方向带，再移动边缘元素、删减孤立突刺，保留有助于表达的变化。

### 问题 22：存疑　观察 `group_outliers`　元素 `large_glowing_pink_letters_on_the_back_wall`
- Jev 问题：Do a few of the large glowing pink letters on the back wall in `scene` stick out from the rest so that the group's outline looks messy?
- 好的方向概率：0.47；原始答案：0.53
- 涉及条款 **J08 群组作为整体时具有可辨认的形状或方向**
  - 标准：当一群元素承担整体块面或方向组织时，应能看出其大致范围、主要延伸方向或形状特征。群组边缘可以不规则，但不能因少数无关突刺、飞点和碎凹口让整体范围难以辨认。
  - 不合格时：先把群组概括成简单轮廓或方向带，再移动边缘元素、删减孤立突刺，保留有助于表达的变化。

## 其余条款状态

- D01 关键元素在实际分析范围内发挥预期作用：合格。编译备注：仅检查“引导线在全图中仍可见”；分析范围与裁切是否合适需大模型结合项目说明判断。
- D02 画面的主导构成符合表达目标：描述。编译备注：项目说明未给 dominant_form_target 时只做描述，不判定。
- D04 需要强调的焦点能够被识别：合格。编译备注：多主体画面需在项目说明中指定主体，目前只支持单一主体。
- D06 承担引导任务的线具有有效连续性：存疑。编译备注：“构成有意循环”的引导方式未覆盖，需大模型补判。
- D07 需要形成强线感时，跨度与显著性足够：合格。编译备注：“约一半跨度”是课堂经验提示而非阈值，因此设为 soft。
- D08 线宽与面感的关系符合设计意图：存疑。编译备注：若设计本意就是条带面，应在项目说明中注明，由大模型复核。
- D11 轮廓的节点与流动特征符合所需感受：合格。编译备注：只检查主体轮廓；“流畅 vs 尖锐节点”的目标需在项目说明中给出后再细化。
- D14 追求多类平衡时，各类确实具有可感知的分量：不适用
- D15 各类元素的分布形成有意的整体关系：存疑。编译备注：大片留白可以合格，所以左右半图检查设为 soft；左右比较由代码切图完成。
- D16 最终观看条件下，必要层次仍然成立：存疑。编译备注：缩略图短边 280 像素（Jev 下限），代表手机信息流尺寸；其他展示尺寸需另配。
- J05 密区形成整体时仍保留必要信息：合格。编译备注：只需形成纹理的密区不必可数，场景解析时不要把这类区域列入 dense_regions。
- J06 散开的元素具有可解释的组织作用：存疑。编译备注：散点本身可能是有意孤立，只有“抢走主体注意力”才判硬性不合格。
- J11 组间空白和静区具有明确作用：存疑。编译备注：满版设计也可合格，所以“有无静区”设为 soft；标题、按钮等功能区核对需在项目说明中给出。