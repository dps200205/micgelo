"""第四步收尾：读取大模型复核结果 llm_review.yaml，重算知识块结论，生成最终报告。

用法：python finalize.py C002 [--out 结果目录]
输入：results/<案例>/verdicts.json + llm_review.yaml
输出：final.json（结构化，供后续 DCC 修改使用）、final_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kb import ROOT, load_config, load_yaml, thresholds
from run_review import KB_NAME, block_summary

FINAL = {"合格", "不合格"}
ISSUE_FIELDS = ("target", "location", "problem", "action", "expected")


def validate_review(v: dict, rv: dict) -> list[str]:
    """校验大模型复核结果，返回错误列表。"""
    res, ovr = rv.get("resolutions") or {}, rv.get("overrides") or {}
    errs = []
    pending = [f"{bid}.{cid}" for bid, b in v["blocks"].items() for cid, c in b["clauses"].items() if c["verdict"] == "存疑"]
    for key in pending:
        r = res.get(key) or {}
        if r.get("verdict") not in FINAL or not r.get("reason"):
            errs.append(f"存疑条目 {key} 未给出最终判定（合格/不合格）和理由")
    for key in res:
        if key not in pending:
            errs.append(f"resolutions 中的 {key} 不是存疑条目；推翻 Jev 的结论请写在 overrides 中")
    for key, r in ovr.items():
        bid, _, cid = key.partition(".")
        c = v["blocks"].get(bid, {}).get("clauses", {}).get(cid)
        if c is None:
            errs.append(f"overrides 中的 {key} 不存在")
        elif c["verdict"] not in FINAL:
            errs.append(f"overrides 中的 {key} 初判为 {c['verdict']}，只能推翻 合格/不合格")
        elif (r or {}).get("verdict") not in FINAL or not (r or {}).get("reason"):
            errs.append(f"overrides 中的 {key} 需要 verdict 和 reason")
    for i, it in enumerate(rv.get("issues") or [], 1):
        miss = [f for f in ISSUE_FIELDS if not it.get(f)]
        if miss:
            errs.append(f"issues 第 {i} 项缺少 {miss}")
        if it.get("kb") not in ("basic", "project"):
            errs.append(f"issues 第 {i} 项 kb 应为 basic 或 project")
    return errs


def apply_review(out: Path, rv: dict, cfg: dict | None = None) -> dict:
    """应用复核结果并写出最终文件。调用前应先通过 validate_review。"""
    cfg = cfg or load_config()
    v = json.loads((out / "verdicts.json").read_text(encoding="utf-8"))
    res, ovr = rv.get("resolutions") or {}, rv.get("overrides") or {}
    changes = []
    for bid, b in v["blocks"].items():
        for cid, c in b["clauses"].items():
            key = f"{bid}.{cid}"
            c["jev_verdict"] = c["verdict"]
            if key in res:
                c["verdict"], c["llm_reason"] = res[key]["verdict"], res[key]["reason"]
                changes.append(("复核存疑", key, c["jev_verdict"], c["verdict"], res[key]["reason"]))
            elif key in ovr:
                c["verdict"], c["llm_reason"], c["overridden"] = ovr[key]["verdict"], ovr[key]["reason"], True
                if c["verdict"] == "合格":
                    c["veto_lifted"] = True
                changes.append(("推翻 Jev", key, c["jev_verdict"], c["verdict"], ovr[key]["reason"]))
        b["jev_summary"] = b["summary"]
        b["summary"] = block_summary(b["clauses"], thresholds(cfg, bid), final=True)
    issues = sorted(rv.get("issues") or [], key=lambda x: (0 if x.get("kb") == "project" else 1, x.get("priority", 99)))
    final = {"case": v["case"], "image": v["image"], "blocks": {bid: {"name": b["name"], "kb": b["kb"],
             "jev": b["jev_summary"]["verdict"], "final": b["summary"]["verdict"], "summary": b["summary"]}
             for bid, b in v["blocks"].items()},
             "changes": [dict(zip(("type", "clause", "from", "to", "reason"), c)) for c in changes],
             "issues": issues, "keep": rv.get("keep") or [], "reviewer": rv.get("reviewer"), "notes": rv.get("notes"),
             "missing_knowledge": (v.get("routing") or {}).get("missing_knowledge") or []}
    (out / "final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "verdicts_final.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")

    L = [f"# 最终评审 {v['case']}", "", f"- 图片：`{v['image']}`", f"- 复核：{rv.get('reviewer') or '未署名'}", "",
         "## 知识块结论", "", "| 知识块 | 来源 | Jev 初判 | 最终 | 合格率 | 一票否决 |", "|---|---|---|---|---|---|"]
    for bid, b in v["blocks"].items():
        s = b["summary"]
        rate = "—" if s["pass_rate"] is None else f"{s['pass_rate']:.0%}（{s['passed']}/{s['evaluated']}）"
        L.append(f"| {b['name']}（{bid}） | {KB_NAME[b['kb']]} | {b['jev_summary']['verdict']} | **{s['verdict']}** | {rate} | {', '.join(s['vetoes']) or '—'} |")
    if final["missing_knowledge"]:
        L += ["", "**适用但知识库尚未建设：** " + "；".join(m["path"] for m in final["missing_knowledge"])]
    L += ["", "## 修改项（项目规范优先，其次按优先级）", ""]
    for it in issues:
        L += [f"### {it.get('priority')}. {it['target']}（{KB_NAME[it['kb']]}；{', '.join(it.get('clauses') or [])}）",
              f"- 位置：{it['location']}", f"- 问题：{it['problem']}", f"- 动作：{it['action']}", f"- 期望：{it['expected']}", ""]
    if final["keep"]:
        L += ["## 修改时保留", ""] + [f"- {k}" for k in final["keep"]] + [""]
    L += ["## 复核记录", "", "| 类型 | 条目 | Jev | 最终 | 理由 |", "|---|---|---|---|---|"]
    for t, key, f, to, why in changes:
        L.append(f"| {t} | {key} | {f} | {to} | {why} |")
    if rv.get("notes"):
        L += ["", "## 备注", "", str(rv["notes"])]
    (out / "final_report.md").write_text("\n".join(L), encoding="utf-8")
    return final


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config()
    out = Path(a.out) if a.out else ROOT / "results" / a.case_id
    v = json.loads((out / "verdicts.json").read_text(encoding="utf-8"))
    rf = out / "llm_review.yaml"
    if not rf.exists():
        sys.exit(f"缺少 {rf}：请按 llm_review_template.yaml 填写")
    rv = load_yaml(rf)
    errs = validate_review(v, rv)
    if errs:
        print("复核结果未通过检查：")
        for e in errs:
            print("  ✗", e)
        return 1
    final = apply_review(out, rv, cfg)
    for bid, b in final["blocks"].items():
        print(f"{b['name']}（{bid}）：Jev {b['jev']} → 最终 {b['final']}  合格率 {b['summary']['pass_rate']}")
    n_res = sum(1 for c in final["changes"] if c["type"] == "复核存疑")
    print(f"复核 {n_res} 条，推翻 {len(final['changes']) - n_res} 条，修改项 {len(final['issues'])} 项")
    print(f"输出：{out / 'final_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
