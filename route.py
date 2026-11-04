"""第一步：渐进式检索（给大模型用的读取工具 + 路由文件检查）。

大模型按以下顺序调用，每一步只读必要的内容：
    python route.py tree                      # 第 1 层：两个知识库下的文件夹卡片摘要
    python route.py tree --under 项目知识库 --depth 3
    python route.py card <路径或知识块ID>      # 读一张卡片的完整内容
    python route.py clauses dlm               # 第 3 层：知识块的条目索引（不读评审标准全文）
    python route.py check C002                # 检查 cases/C002/routing.yaml 是否有效

`--json` 可输出机器可读格式。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kb import ROOT, iter_nodes, kb_root, load_blocks, load_config, load_yaml, parse_index_table, scan

L1_SECTIONS = ("一句话定位", "什么时候评", "什么时候不评")


def short(text: str, limit: int = 160) -> str:
    t = " ".join(l.strip("- ").strip() for l in (text or "").splitlines() if l.strip())
    return t if len(t) <= limit else t[:limit] + "…"


def find_node(tree, key: str):
    for n in iter_nodes(tree):
        if n.id == key or n.rel == key or n.rel.endswith(key) or n.name == key:
            return n
    return None


def cmd_tree(tree, under: str | None, depth: int, as_json: bool):
    start = find_node(tree, under) if under else tree
    if start is None:
        sys.exit(f"找不到 {under}")
    rows = []

    def walk(n, d):
        if d > depth:
            return
        if n is not start or under:
            rows.append({
                "depth": d, "path": n.rel, "level": n.level, "kb": n.kb, "status": n.status, "id": n.id,
                **{s: short(n.sections.get(s, "")) for s in L1_SECTIONS},
                "children": len(n.children),
            })
        for c in n.children:
            walk(c, d + 1)
    walk(start, 0 if under else 0)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        ind = "  " * r["depth"]
        tag = f"[{r['level']}|{r['kb']}|{r['status']}" + (f"|id={r['id']}" if r["id"] else "") + "]"
        print(f"{ind}{Path(r['path']).name} {tag}")
        if r["status"] != "待建设":
            for s in L1_SECTIONS:
                if r[s]:
                    print(f"{ind}    {s}：{r[s]}")


def cmd_card(tree, key: str):
    n = find_node(tree, key)
    if n is None or n.card_file is None:
        sys.exit(f"找不到 {key} 的卡片")
    print(f"# {n.rel}  ({n.card_file.name})")
    print(n.card_file.read_text(encoding="utf-8"))


def cmd_clauses(tree, bid: str):
    n = find_node(tree, bid)
    if n is None or n.level != "block":
        sys.exit(f"{bid} 不是知识块")
    print(f"# 知识块 {n.id}（{n.rel}，{n.status}）")
    for s in ("需要的信息", "与其他知识块的关系", "条目索引"):
        print(f"\n## {s}\n{n.sections.get(s, '（无）')}")


def check_routing(cfg, root: Path, r: dict, base: Path) -> tuple[list, list]:
    """检查路由结果，返回 (errors, warnings)。"""
    blocks = load_blocks(root)
    errs, warns = [], []
    for item in r.get("blocks") or []:
        bid = item.get("id")
        b = blocks.get(bid)
        if b is None:
            errs.append(f"知识块 {bid} 不存在")
            continue
        if not b.usable:
            errs.append(f"知识块 {bid} 状态为 {b.status}，不能参与评审（应列入 missing_knowledge）")
            continue
        idx = set(parse_index_table(b.node.sections.get("条目索引")))
        chosen = item.get("clauses") or []
        skipped = item.get("skipped") or {}
        for cid in chosen:
            if cid not in b.clauses:
                errs.append(f"{bid}.{cid} 不存在")
        missing = idx - set(chosen) - set(skipped)
        if missing:
            warns.append(f"{bid}：条目 {sorted(missing)} 既未选中也未说明跳过原因")
        if not item.get("reason"):
            warns.append(f"{bid}：缺少选择理由 reason")
    for m in r.get("missing_knowledge") or []:
        if not m.get("reason"):
            warns.append(f"missing_knowledge {m.get('path')} 缺少原因")
    if r.get("extra"):
        from kb import block_from_dict
        from lint_kb import lint_questions
        e, w = lint_questions(block_from_dict("user", "project", r["extra"], base), cfg, check_std=False)
        errs += e
        warns += w
    return errs, warns


def cmd_check(cfg, root: Path, case: str, cases_dir: Path) -> int:
    rf = cases_dir / case / "routing.yaml"
    if not rf.exists():
        sys.exit(f"缺少 {rf}")
    errs, warns = check_routing(cfg, root, load_yaml(rf), cases_dir / case)
    print(f"路由检查 {case}：错误 {len(errs)}，警告 {len(warns)}")
    for m in errs:
        print("  ✗", m)
    for m in warns:
        print("  !", m)
    return 1 if errs else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tree", "card", "clauses", "check"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--under")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--kb")
    ap.add_argument("--cases", default=str(ROOT / "cases"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    root = kb_root(cfg, a.kb)
    tree = scan(root)
    if a.cmd == "tree":
        cmd_tree(tree, a.under, a.depth, a.json)
    elif a.cmd == "card":
        cmd_card(tree, a.arg)
    elif a.cmd == "clauses":
        cmd_clauses(tree, a.arg)
    else:
        return cmd_check(cfg, root, a.arg, Path(a.cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
