"""问题库自动检查：python lint_bank.py

错误（必须清零）：结构缺失、引用不存在、槽位用错、与标准 md 不一致、问题含中文。
警告（逐条确认）：问题里有 or/and、出现决策类措辞、问题过长、观察问题未被引用。
"""
import re
import sys

from bank import condition_paths, load_bank, load_config, load_standards

POSITIONAL = re.compile(r"^(a|b|c|d|e|option_?\d+|choice_?\d+|left|right|top|bottom|first|second|\d+)$", re.I)
CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
DECISION = re.compile(r"\b(should|good|bad|better|worse|well[- ]composed|quality|correct)\b", re.I)
CHOICE_RULES = ("good_option_slot", "good_options", "match_brief", "match_item")


def main() -> int:
    cfg = load_config()
    obs, clauses = load_bank(cfg)
    std = load_standards(cfg)
    single, lists = set(cfg["slots"]["single"]), set(cfg["slots"]["lists"])
    errors, warnings = [], []
    E = lambda m: errors.append(m)
    W = lambda m: warnings.append(m)

    # ---------- 观察问题 ----------
    for oid, o in obs.items():
        t = o.get("type")
        if t not in ("noul", "choice"):
            E(f"[{oid}] type 必须是 noul 或 choice")
            continue
        q = o.get("q", "")
        if not q:
            E(f"[{oid}] 缺少 q")
        crit = o.get("criteria") or {}
        texts = [q] + [str(v) for v in crit.values()]
        image = o.get("image", "scene")
        over, needs = o.get("over"), set(o.get("needs", []))

        if t == "noul" and set(crit) != {"true", "false"}:
            E(f"[{oid}] noul 必须且只能有 criteria.true / criteria.false")
        if t == "choice":
            if bool(crit) == bool(o.get("options_from")):
                E(f"[{oid}] choice 需要 criteria 或 options_from 二选一")
            for name in crit:
                if POSITIONAL.match(name):
                    E(f"[{oid}] 选项名 '{name}' 是位置型名称，应描述内容")
            for s in o.get("options_from", []):
                if s not in single | lists:
                    E(f"[{oid}] options_from 含未知槽位 {s}")
            if len(crit) == 1:
                E(f"[{oid}] choice 至少需要 2 个选项")
        if over and over not in lists:
            E(f"[{oid}] over={over} 不是列表槽位")
        if needs - single:
            E(f"[{oid}] needs 含未知槽位 {needs - single}")
        if image not in ("scene", "thumb", "halves"):
            E(f"[{oid}] image 只能是 scene/thumb/halves")

        allowed = {"item"} if over else set()
        allowed |= needs
        if image == "thumb":
            allowed.add("thumb_img")
        if image == "halves":
            allowed.add("half_img")
        used = set()
        for tx in texts:
            used |= set(PLACEHOLDER.findall(tx))
            if CJK.search(tx):
                E(f"[{oid}] 问题或选项描述含中文，Jev 应使用英文")
            if re.search(r"\b(the|a|an) \{", tx, re.I):
                E(f"[{oid}] 槽位值自带冠词，模板不要写 'the {{'")
        for p in used - allowed:
            E(f"[{oid}] 使用了未声明的占位符 {{{p}}}")
        if over and "item" not in used:
            E(f"[{oid}] 声明了 over 但模板未使用 {{item}}")
        if image == "thumb" and "thumb_img" not in PLACEHOLDER.findall(q):
            E(f"[{oid}] image=thumb 时 q 必须包含 {{thumb_img}}")
        if image == "halves" and "half_img" not in PLACEHOLDER.findall(q):
            E(f"[{oid}] image=halves 时 q 必须包含 {{half_img}}")
        if image == "scene" and "`scene`" not in q:
            E(f"[{oid}] q 没有引用 `scene`")

        # or/and 只查问题本身：criteria 描述情形时列举几种形态是正常的
        waived = set((o.get("lint_ok") or {}).keys())
        for word in ("or", "and"):
            if word not in waived and re.search(rf"\b{word}\b", q):
                W(f"[{oid}] 问题含 '{word}'，确认是否两个判断：{q[:90]}")
        if DECISION.search(q):
            W(f"[{oid}] 问题含决策/评价措辞：{DECISION.search(q).group(0)}")
        if len(q) > 200:
            W(f"[{oid}] 问题过长（{len(q)} 字符）")

    # ---------- 条款 ----------
    used_obs = set()
    for cid, c in clauses.items():
        if cid not in std:
            E(f"[{cid}] 标准 md 中不存在该条款")
        elif c.get("title") != std[cid]["title"]:
            E(f"[{cid}] 标题与 md 不一致：'{c.get('title')}' vs '{std[cid]['title']}'")
        conds = list(c.get("applies_if") or [])
        checks = c.get("checks") or []
        if not checks:
            E(f"[{cid}] 没有 checks")
        for ch in checks:
            oid = ch.get("obs")
            conds += ch.get("applies_if") or []
            if oid not in obs:
                E(f"[{cid}] 引用了不存在的观察问题 {oid}")
                continue
            used_obs.add(oid)
            o = obs[oid]
            if o["type"] == "noul" and not isinstance(ch.get("good"), bool):
                E(f"[{cid}/{oid}] noul 检查必须写 good: true/false")
            if o["type"] == "choice":
                rules = [k for k in CHOICE_RULES if k in ch]
                if len(rules) != 1:
                    E(f"[{cid}/{oid}] choice 检查需且仅需一种判定方式 {CHOICE_RULES}")
                opts = set(o.get("criteria") or {})
                for g in ch.get("good_options", []):
                    if g not in opts:
                        E(f"[{cid}/{oid}] good_options 含不存在的选项 {g}")
            if "aggregate" in ch:
                if ch["aggregate"] not in ("worst", "best"):
                    E(f"[{cid}/{oid}] aggregate 只能是 worst/best")
                if not o.get("over") and o.get("image") != "halves":
                    E(f"[{cid}/{oid}] 该问题不展开，aggregate 无意义")
        for cond in conds:
            p = condition_paths(cond)
            if not (p.startswith("scene.") or p.startswith("brief.")):
                E(f"[{cid}] 条件 '{cond}' 必须以 scene. 或 brief. 开头")
        sa = c.get("same_as")
        if sa and (sa not in clauses or clauses[sa].get("same_as") != cid):
            E(f"[{cid}] same_as={sa} 未互相标注")

    for cid in std:
        if cid not in clauses:
            E(f"[{cid}] 标准 md 中的条款未编译：{std[cid]['title']}")
    for oid in obs:
        if oid not in used_obs:
            W(f"[{oid}] 未被任何条款引用")

    n_checks = sum(len(c.get("checks") or []) for c in clauses.values())
    print(f"标准条款 {len(std)} 条 | 已编译 {len(clauses)} 条 | 观察问题 {len(obs)} 个 | 检查引用 {n_checks} 处")
    print(f"\n错误 {len(errors)} 条")
    for m in errors:
        print("  ✗", m)
    print(f"\n警告 {len(warnings)} 条")
    for m in warnings:
        print("  !", m)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
