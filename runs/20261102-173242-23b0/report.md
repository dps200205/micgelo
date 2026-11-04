# 评审报告 20261102-173242-23b0（Jev 初判）

- 图片：`C:\Users\peisongdou\WorkBuddy\2026-10-24-15-54-26\review_pipeline\runs\20261102-173242-23b0\image.jpg`
- 图类型：项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图
- 模型：jev-1.14.0；请求：美术基础 11292 token；合计约 $0.00047
- 默认规则：条目 ≥0.7 合格、<0.4 不合格、之间存疑；知识块合格率 >80% 且无条目 <0.2（按知识块覆盖的阈值见各块）

## 知识块结论

| 知识块 | 来源 | 初判 | 合格 / 存疑 / 不合格 | 合格率 | 一票否决 |
|---|---|---|---|---|---|
| 点线面（dlm） | 美术基础 | **不合格** | 7 / 6 / 1 | 50% | D04 |

**适用但知识库尚未建设：** 项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的物件摆放规范（用户明确说明是PVP爆破场景，该节点适用但状态为待建设，无法提供具体的物件摆放规范评审。）；项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的色彩使用规范（用户明确说明是PVP爆破场景，该节点适用但状态为待建设，无法提供具体的色彩规范评审。）；场景美术基础知识库/场景灯光（画面中有明显的顶光和自发光灯管，涉及光影氛围营造，但该知识块待建设。）；场景美术基础知识库/立体构成（场景涉及复杂的透视结构和空间体积感，立体构成知识块待建设。）；场景美术基础知识库/色彩关系（画面有明显的冷暖对比（灰色混凝土与红色地面/标语），色彩关系知识块待建设。）；场景美术基础知识库/黑白灰画面层级（需要评估画面的素描关系和视觉重心，该知识块待建设。）

## 点线面（dlm）

| 条目 | 判定 | 依据（好的方向概率） |
|---|---|---|
| D01 关键元素在实际分析范围内发挥预期作用 | 合格 | line_visible_full[yellow_safety_lines_marking_the_edges_of_the]: 0.93；line_visible_full[horizontal_red_stripe_painted_across_the_left]: 0.95 |
| D02 画面的主导构成符合表达目标 | 描述 | dominant_form: long_directional_lines（仅描述） |
| D03 需要形成对比的视觉层次能够区分 | 合格 | levels_distinct: 0.94 |
| D04 需要强调的焦点能够被识别 | 不合格 | first_noticed: 0.10 / subject_stands_out: 0.52 |
| D05 多点分布形成可读的停顿关系 | 合格 | points_equally_loud[rectangular_ceiling_light_fixtures]: 0.89；points_equally_loud[yellow_triangular_warning_signs_on_the_walls_and]: 0.89 / points_pull_from_subject[rectangular_ceiling_light_fixtures]: 0.74；points_pull_from_subject[yellow_triangular_warning_signs_on_the_walls_and]: 0.78 |
| D06 承担引导任务的线具有有效连续性 | 存疑 | line_path_continuous[yellow_safety_lines_marking_the_edges_of_the]: 0.55；line_path_continuous[horizontal_red_stripe_painted_across_the_left]: 0.58 / line_leads_to_subject[yellow_safety_lines_marking_the_edges_of_the]: 0.82；line_leads_to_subject[horizontal_red_stripe_painted_across_the_left]: 0.58 |
| D07 需要形成强线感时，跨度与显著性足够 | 合格 | （soft）line_spans_far[yellow_safety_lines_marking_the_edges_of_the]: 0.80；line_spans_far[horizontal_red_stripe_painted_across_the_left]: 0.44 / line_contrast[yellow_safety_lines_marking_the_edges_of_the]: 0.88；line_contrast[horizontal_red_stripe_painted_across_the_left]: 0.91 |
| D08 线宽与面感的关系符合设计意图 | 存疑 | （soft）line_reads_as_band[yellow_safety_lines_marking_the_edges_of_the]: 0.76；line_reads_as_band[horizontal_red_stripe_painted_across_the_left]: 0.31 |
| D09 主要块面的形状与归属清楚 | 合格 | area_shape_clear[red_painted_floor_zone_in_the_central_corridor]: 0.87；area_shape_clear[large_concrete_pillar_structure_in_the_left]: 0.91；area_shape_clear[back_wall_surface_behind_the_control_consoles]: 0.71 / area_broken_up[red_painted_floor_zone_in_the_central_corridor]: 0.90；area_broken_up[large_concrete_pillar_structure_in_the_left]: 0.90；area_broken_up[back_wall_surface_behind_the_control_consoles]: 0.79 |
| D10 正形与负空间共同支持形体识别 | 存疑 | shapes_merge: 0.75 / distracting_gaps: 0.66 |
| D11 轮廓的节点与流动特征符合所需感受 | 合格 | subject_outline_readable: 0.75 / （soft）subject_outline_noisy: 0.90 |
| D12 点线聚集后的整体性质没有偏离目标 | 合格 | group_reads_as[row_of_tall_metal_electrical_cabinets_along_the]: 0.75；group_reads_as[series_of_overhead_pipes_and_conduits_running]: 0.75 |
| D13 光影与材质细节没有破坏构成 | 存疑 | glow_clutter: 0.90 / highlights_compete_subject: 0.64 |
| D14 追求多类平衡时，各类确实具有可感知的分量 | 未选中 | 项目说明未要求多类平衡（balance_target 为 null）。 |
| D15 各类元素的分布形成有意的整体关系 | 存疑 | lopsided: 0.52 / （soft）half_holds_eye[left]: 0.75；half_holds_eye[right]: 0.87 |
| D16 最终观看条件下，必要层次仍然成立 | 存疑 | thumb_subject_visible: 0.58 / thumb_group_visible[row_of_tall_metal_electrical_cabinets_along_the]: 0.89；thumb_group_visible[series_of_overhead_pipes_and_conduits_running]: 0.75 |