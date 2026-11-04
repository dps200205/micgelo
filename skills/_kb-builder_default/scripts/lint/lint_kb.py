"""知识库自动检查：python lint_kb.py [--kb 路径]

错误（必须清零）：结构缺失、引用不存在、槽位用错、与评审标准不一致、问题含中文、参考图不可用。
警告（逐条确认）：问题里有 or/and、出现决策类措辞、观察要点与检查数不一致、未被引用的问题或参考图。
"""
from __future__ import annotations

import argparse
import re
import sys

from PIL import Image

from kb import (CARD_SECTIONS, COND_RE, LEVELS, STATUSES, STD_REQUIRED, Block, condition_path, iter_nodes, kb_root,
                load_block, load_config, parse_index_table, scan)

POSITIONAL = re.compile(r"^(a|b|c|d|e|option_?\d+|choice_?\d+|left|right|top|bottom|first|second|\d+)$", re.I)
CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
REF_PH = re.compile(r"\{ref:([A-Za-z0-9_]+)\}")
DECISION = re.compile(r"\b(should|good|bad|better|worse|well[- ]composed|quality|correct)\b", re.I)
CHOICE_RULES = ("good_option_slot", "good_options", "match_brief", "match_item")
# 用户说明中可用于判定的字段及取值
BRIEF_VALUES = {
    "goal": {"hierarchy", "uniform_pattern", "minimal", "equal_display", "balanced_groups"},
    "dominant_form_target": {"point", "line", "area", "mixed"},
    "balance_target": {"none", "point_line", "point_area", "line_area", "all_three"},
}


def lint_questions(b: Block, cfg: dict, check_std: bool = True) -> tuple[list, list]:
    """检查一个知识块的问题库。返回 (errors, warnings)。"""
    errors, warnings = [], []
    E = lambda m: errors.append(f"[{b.id}] {m}")
    W = lambda m: warnings.append(f"[{b.id}] {m}")
    obs, clauses, refs = b.observations, b.clauses, b.refs
    bslots = b.q.get("slots") or {}
    single = set(cfg["slots"]["single"]) | set(bslots.get("single") or [])
    lists = set(cfg["slots"]["lists"]) | set(bslots.get("lists") or [])
    imin = cfg["image"]["min_side"]

    # ---------- 参考图 ----------
    used_refs = set()
    for name, r in refs.items():
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            E(f"参考图名称 '{name}' 只能用英文、数字、下划线")
        f = r.get("file") if isinstance(r, dict) else None
        if not f:
            E(f"参考图 {name} 缺少 file")
            continue
        p = b.ref_path(name)
        if not p.exists():
            E(f"参考图 {name} 文件不存在：{f}")
            continue
        try:
            with Image.open(p) as im:
                if im.format not in ("PNG", "JPEG"):
                    E(f"参考图 {name} 格式 {im.format}，只支持 PNG/JPEG")
                if min(im.size) < imin:
                    E(f"参考图 {name} 短边 {min(im.size)}px，小于 {imin}px")
        except Exception as e:  # noqa: BLE001
            E(f"参考图 {name} 无法读取：{e}")

    # ---------- 观察问题 ----------
    for oid, o in obs.items():
        t = o.get("type")
        if t not in ("noul", "choice"):
            E(f"{oid}: type 必须是 noul 或 choice")
            continue
        q = o.get("q", "")
        crit = o.get("criteria") or {}
        texts = [q] + [str(v) for v in crit.values()]
        image = o.get("image", "scene")
        over, needs = o.get("over"), set(o.get("needs", []))
        if not q:
            E(f"{oid}: 缺少 q")
        if t == "noul" and set(crit) != {"true", "false"}:
            E(f"{oid}: noul 必须且只能有 criteria.true / criteria.false")
        if t == "choice":
            if bool(crit) == bool(o.get("options_from")):
                E(f"{oid}: choice 需要 criteria 或 options_from 二选一")
            for name in crit:
                if POSITIONAL.match(name):
                    E(f"{oid}: 选项名 '{name}' 是位置型名称，应描述内容")
            if crit and len(crit) < 2:
                E(f"{oid}: choice 至少需要 2 个选项")
            for s in o.get("options_from", []):
                if s not in single | lists:
                    E(f"{oid}: options_from 含未知槽位 {s}")
        if over and over not in lists:
            E(f"{oid}: over={over} 不是列表槽位（可在 questions.yaml 的 slots.lists 中声明）")
        if needs - single:
            E(f"{oid}: needs 含未知槽位 {needs - single}")
        if image not in ("scene", "thumb", "halves"):
            E(f"{oid}: image 只能是 scene/thumb/halves")

        allowed = ({"item"} if over else set()) | needs
        allowed |= {"thumb_img"} if image == "thumb" else set()
        allowed |= {"half_img"} if image == "halves" else set()
        used = set()
        for tx in texts:
            used |= set(PLACEHOLDER.findall(tx))
            for rn in REF_PH.findall(tx):
                used_refs.add(rn)
                if rn not in refs:
                    E(f"{oid}: 引用了未声明的参考图 {{ref:{rn}}}")
            if CJK.search(tx):
                E(f"{oid}: 问题或选项描述含中文，Jev 应使用英文")
            if re.search(r"\b(the|a|an) \{(?!ref:)", tx, re.I):
                E(f"{oid}: 槽位值自带冠词，模板不要写 'the {{'")
        for p in used - allowed:
            E(f"{oid}: 使用了未声明的占位符 {{{p}}}")
        if over and "item" not in used:
            E(f"{oid}: 声明了 over 但模板未使用 {{item}}")
        if image == "thumb" and "{thumb_img}" not in q:
            E(f"{oid}: image=thumb 时 q 必须包含 {{thumb_img}}")
        if image == "halves" and "{half_img}" not in q:
            E(f"{oid}: image=halves 时 q 必须包含 {{half_img}}")
        if image == "scene" and "`scene`" not in q:
            E(f"{oid}: q 没有引用 `scene`")
        waived = set((o.get("lint_ok") or {}).keys())
        for word in ("or", "and"):
            if word not in waived and re.search(rf"\b{word}\b", REF_PH.sub("", q)):
                W(f"{oid}: 问题含 '{word}'，确认是否两个判断：{q[:90]}")
        if DECISION.search(q):
            W(f"{oid}: 问题含决策/评价措辞：{DECISION.search(q).group(0)}")
        if len(q) > 220:
            W(f"{oid}: 问题过长（{len(q)} 字符）")
    for name in set(refs) - used_refs:
        W(f"参考图 {name} 未被任何问题引用")

    # ---------- 条目 ----------
    used_obs = set()
    for cid, c in clauses.items():
        if not re.fullmatch(r"[A-Z]\d{2}", cid):
            E(f"{cid}: 条目编号应为 大写字母+两位数字")
        if check_std:
            if cid not in b.std:
                E(f"{cid}: 评审标准中不存在该条目")
            elif c.get("title") != b.std[cid]["title"]:
                E(f"{cid}: 标题与评审标准不一致：'{c.get('title')}' vs '{b.std[cid]['title']}'")
        checks = c.get("checks") or []
        if not checks:
            E(f"{cid}: 没有 checks")
        conds = list(c.get("applies_if") or [])
        for ch in checks:
            oid = ch.get("obs")
            conds += ch.get("applies_if") or []
            if oid not in obs:
                E(f"{cid}: 引用了不存在的观察问题 {oid}")
                continue
            used_obs.add(oid)
            o = obs[oid]
            if o["type"] == "noul" and not isinstance(ch.get("good"), bool):
                E(f"{cid}/{oid}: noul 检查必须写 good: true/false")
            if o["type"] == "choice":
                if len([k for k in CHOICE_RULES if k in ch]) != 1:
                    E(f"{cid}/{oid}: choice 检查需且仅需一种判定方式 {CHOICE_RULES}")
                for g in ch.get("good_options", []):
                    if g not in (o.get("criteria") or {}):
                        E(f"{cid}/{oid}: good_options 含不存在的选项 {g}")
            if "aggregate" in ch:
                if ch["aggregate"] not in ("worst", "best"):
                    E(f"{cid}/{oid}: aggregate 只能是 worst/best")
                if not o.get("over") and o.get("image") != "halves":
                    E(f"{cid}/{oid}: 该问题不展开，aggregate 无意义")
        for cond in conds:
            p = condition_path(cond)
            if not (p.startswith("scene.") or p.startswith("brief.")):
                E(f"{cid}: 条件 '{cond}' 必须以 scene. 或 brief. 开头")
            elif p.startswith("brief."):
                field = p[len("brief."):]
                if field not in BRIEF_VALUES:
                    E(f"{cid}: 条件 '{cond}' 用了系统不支持的字段，只能用 {sorted(BRIEF_VALUES)}")
                else:
                    m = COND_RE.match(cond)
                    raw = m.group(3).strip() if m else ""
                    vals = [x.strip() for x in raw[1:-1].split(",")] if raw.startswith("[") else ([raw] if raw else [])
                    bad = [x for x in vals if x not in BRIEF_VALUES[field]]
                    if bad:
                        E(f"{cid}: 条件 '{cond}' 的取值 {bad} 不存在，这一条永远不会被正确评审。可用值：{sorted(BRIEF_VALUES[field])}")
        for ch in checks:
            if ch.get("match_brief") and ch["match_brief"] not in BRIEF_VALUES:
                E(f"{cid}/{ch.get('obs')}: match_brief 用了系统不支持的字段 {ch['match_brief']}")
        if check_std and cid in b.std:
            pts = b.std[cid]["fields"].get("观察要点")
            n_pts = len(pts) if isinstance(pts, list) else (1 if pts else 0)
            if n_pts and n_pts != len(checks):
                W(f"{cid}: 评审标准有 {n_pts} 条观察要点，问题库有 {len(checks)} 个检查")
            for ch in checks:
                if ch.get("point") and not (1 <= ch["point"] <= max(n_pts, 1)):
                    E(f"{cid}/{ch.get('obs')}: point={ch['point']} 超出观察要点数量 {n_pts}")
    for oid in set(obs) - used_obs:
        W(f"观察问题 {oid} 未被任何条目引用")
    return errors, warnings


def lint_block(b: Block, cfg: dict) -> tuple[list, list]:
    errors, warnings = [f"[{b.id}] {m}" for m in b.errors], []
    E = lambda m: errors.append(f"[{b.id}] {m}")
    W = lambda m: warnings.append(f"[{b.id}] {m}")
    if b.status == "待建设":
        return errors, warnings
    if b.errors:
        return errors, warnings
    # 评审标准
    for cid, c in b.std.items():
        miss = [f for f in STD_REQUIRED if not c["fields"].get(f)]
        if miss:
            E(f"评审标准 {cid} 缺少字段：{'、'.join(miss)}")
    if str(b.q.get("source_version")) != str(b.std_meta.get("version")):
        E(f"问题库 source_version={b.q.get('source_version')} 与评审标准 version={b.std_meta.get('version')} 不一致，需重新编译")
    if b.q.get("block") != b.id:
        E(f"questions.yaml 的 block={b.q.get('block')} 与卡片 id={b.id} 不一致")
    for cid in b.std:
        if cid not in b.clauses:
            E(f"评审标准中的条目 {cid} 未编译进问题库")
    idx = parse_index_table(b.node.sections.get("条目索引"))
    if set(idx) != set(b.std):
        E(f"卡片“条目索引”与评审标准条目不一致：索引 {sorted(set(idx) ^ set(b.std))}")
    # 图片登记
    for im in b.images:
        if im.get("role") not in ("reference", "example"):
            E(f"cases.yaml 图片 {im.get('id')} 的 role 只能是 reference/example")
        if not (b.node.path / str(im.get("file", ""))).exists():
            E(f"cases.yaml 图片文件不存在：{im.get('file')}")
        for cid in im.get("clauses") or []:
            if cid not in b.std:
                E(f"cases.yaml 图片 {im.get('id')} 关联了不存在的条目 {cid}")
    e2, w2 = lint_questions(b, cfg)
    return errors + e2, warnings + w2


def lint_all(cfg: dict, root) -> dict:
    """检查整个知识库，返回 {root, errors, warnings, stats, blocks}。"""
    tree = scan(root)
    errors, warnings, ids = [], [], {}
    stats = {"folder": 0, "block": 0, "可用": 0, "待建设": 0, "草稿": 0}
    for n in iter_nodes(tree):
        where = n.rel
        if n.card_file is None:
            errors.append(f"[{where}] 缺少 ！卡片文件")
            continue
        if n.level not in LEVELS:
            errors.append(f"[{where}] level={n.level} 无效")
            continue
        if n.status not in STATUSES and n.level != "root":
            errors.append(f"[{where}] status={n.status} 无效，应为 {STATUSES}")
        if n.level != "root" and n.kb not in ("basic", "project"):
            errors.append(f"[{where}] kb 应为 basic 或 project（可从上级继承）")
        stats[n.level] = stats.get(n.level, 0) + 1
        if n.level != "root":
            stats[n.status] = stats.get(n.status, 0) + 1
        if n.status != "待建设":
            for s in CARD_SECTIONS[n.level]:
                txt = n.sections.get(s, "")
                if not txt or "待补充" in txt:
                    (errors if n.status == "可用" else warnings).append(f"[{where}] 卡片缺少或未填写小节“{s}”")
            if "特殊情况" in n.sections.get("什么时候不评", ""):
                warnings.append(f"[{where}] “什么时候不评”含“特殊情况”，请写成具体反例")
        if n.level == "block":
            if not n.id:
                errors.append(f"[{where}] 知识块缺少 id")
                continue
            if n.id in ids:
                errors.append(f"[{where}] 知识块 id {n.id} 与 {ids[n.id]} 重复")
            ids[n.id] = where
            e, w = lint_block(load_block(n), cfg)
            (errors if n.status == "可用" else warnings).extend(e)
            warnings.extend(w)
    return {"root": str(root), "errors": errors, "warnings": warnings, "stats": stats, "blocks": ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb")
    args = ap.parse_args()
    cfg = load_config()
    r = lint_all(cfg, kb_root(cfg, args.kb))
    stats, errors, warnings = r["stats"], r["errors"], r["warnings"]
    print(f"知识库：{r['root']}")
    print(f"文件夹 {stats.get('folder', 0)} | 知识块 {stats.get('block', 0)} | 可用 {stats['可用']} | 草稿 {stats['草稿']} | 待建设 {stats['待建设']}")
    for bid, where in r["blocks"].items():
        print(f"  知识块 {bid}: {where}")
    print(f"\n错误 {len(errors)} 条")
    for m in errors:
        print("  ✗", m)
    print(f"\n警告 {len(warnings)} 条")
    for m in warnings:
        print("  !", m)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
