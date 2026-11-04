# 评审报告 C002（Jev 初判）

- 图片：`C:\Users\peisongdou\WorkBuddy\2026-10-24-15-54-26\review_pipeline\cases\C002\image.jpg`
- 图类型：项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图
- 模型：jev-1.14.0；请求：美术基础 11655 token；合计约 $0.00049
- 默认规则：条目 ≥0.7 合格、<0.4 不合格、之间存疑；知识块合格率 >80% 且无条目 <0.2（按知识块覆盖的阈值见各块）

## 知识块结论

| 知识块 | 来源 | 初判 | 合格 / 存疑 / 不合格 | 合格率 | 一票否决 |
|---|---|---|---|---|---|
| 点线面（dlm） | 美术基础 | **待复核** | 6 / 6 / 2 | 43% | — |

**适用但知识库尚未建设：** 项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的物件摆放规范（爆破地图的项目规范，本图适用）；项目知识库/01_局内场景/01_PVP场景/01_常规爆破地图/场景中的色彩使用规范（图中大量使用红黄警示色，需要按项目色彩规范核对）；场景美术基础知识库/构图与引导（走廊纵深透视与地面箭头承担主要引导）；场景美术基础知识库/场景灯光（顶灯与尽头光源决定空间氛围和焦点）；场景美术基础知识库/黑白灰画面层级（立柱暗面与尽头亮区的明度关系影响焦点）；场景美术基础知识库/色彩关系（红色地面、黄色警示线与灰色墙面的色彩搭配）；场景美术基础知识库/平面构成/场景概念设计中的大中小（立柱、机柜、控制台的尺度层级）

## 点线面（dlm）

| 条目 | 判定 | 依据（好的方向概率） |
|---|---|---|
| D01 关键元素在实际分析范围内发挥预期作用 | 合格 | line_visible_full[red_stripe_painted_along_the_walls]: 0.93；line_visible_full[yellow_and_black_hazard_stripes_along_the_floor]: 0.82；line_visible_full[ceiling_edges_of_the_corridor]: 0.93 |
| D02 画面的主导构成符合表达目标 | 描述 | dominant_form: long_directional_lines（仅描述） |
| D03 需要形成对比的视觉层次能够区分 | 合格 | levels_distinct: 0.94 |
| D04 需要强调的焦点能够被识别 | 不合格 | first_noticed: 0.22 / subject_stands_out: 0.57 |
| D05 多点分布形成可读的停顿关系 | 合格 | points_equally_loud[warning_signs_and_painted_labels_on_the_walls]: 0.94；points_equally_loud[bright_ceiling_lights]: 0.85 / points_pull_from_subject[warning_signs_and_painted_labels_on_the_walls]: 0.71；points_pull_from_subject[bright_ceiling_lights]: 0.70 |
| D06 承担引导任务的线具有有效连续性 | 不合格 | line_path_continuous[red_stripe_painted_along_the_walls]: 0.39；line_path_continuous[yellow_and_black_hazard_stripes_along_the_floor]: 0.28；line_path_continuous[ceiling_edges_of_the_corridor]: 0.75 / line_leads_to_subject[red_stripe_painted_along_the_walls]: 0.62；line_leads_to_subject[yellow_and_black_hazard_stripes_along_the_floor]: 0.81；line_leads_to_subject[ceiling_edges_of_the_corridor]: 0.92 |
| D07 需要形成强线感时，跨度与显著性足够 | 合格 | （soft）line_spans_far[red_stripe_painted_along_the_walls]: 0.78；line_spans_far[yellow_and_black_hazard_stripes_along_the_floor]: 0.57；line_spans_far[ceiling_edges_of_the_corridor]: 0.84 / line_contrast[red_stripe_painted_along_the_walls]: 0.84；line_contrast[yellow_and_black_hazard_stripes_along_the_floor]: 0.87；line_contrast[ceiling_edges_of_the_corridor]: 0.41 |
| D08 线宽与面感的关系符合设计意图 | 存疑 | （soft）line_reads_as_band[red_stripe_painted_along_the_walls]: 0.47；line_reads_as_band[yellow_and_black_hazard_stripes_along_the_floor]: 0.74；line_reads_as_band[ceiling_edges_of_the_corridor]: 0.75 |
| D09 主要块面的形状与归属清楚 | 合格 | area_shape_clear[large_concrete_pillar_on_the_left]: 0.87；area_shape_clear[red_painted_corridor_floor]: 0.86；area_shape_clear[curved_ceiling_of_the_corridor]: 0.84 / area_broken_up[large_concrete_pillar_on_the_left]: 0.92；area_broken_up[red_painted_corridor_floor]: 0.87；area_broken_up[curved_ceiling_of_the_corridor]: 0.78 |
| D10 正形与负空间共同支持形体识别 | 存疑 | shapes_merge: 0.75 / distracting_gaps: 0.68 |
| D11 轮廓的节点与流动特征符合所需感受 | 存疑 | subject_outline_readable: 0.66 / （soft）subject_outline_noisy: 0.92 |
| D12 点线聚集后的整体性质没有偏离目标 | 合格 | group_reads_as[tall_metal_electrical_cabinets_along_the_right]: 0.71；group_reads_as[row_of_control_consoles_on_the_back_wall]: one_continuous_path（仅描述） |
| D13 光影与材质细节没有破坏构成 | 存疑 | glow_clutter: 0.91 / highlights_compete_subject: 0.66 |
| D14 追求多类平衡时，各类确实具有可感知的分量 | 未选中 | 用户未要求点线面多类平衡 |
| D15 各类元素的分布形成有意的整体关系 | 存疑 | lopsided: 0.57 / （soft）half_holds_eye[left]: 0.74；half_holds_eye[right]: 0.86 |
| D16 最终观看条件下，必要层次仍然成立 | 存疑 | thumb_subject_visible: 0.58 / thumb_group_visible[tall_metal_electrical_cabinets_along_the_right]: 0.88；thumb_group_visible[row_of_control_consoles_on_the_back_wall]: 0.76 |