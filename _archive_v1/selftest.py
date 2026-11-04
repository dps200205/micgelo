"""离线自检：不调用 Jev，用随机合成答案跑完路由→展开→判定→报告全流程，检查代码路径是否正常。

用法：python selftest.py C001
输出写到系统临时目录，合成答案不代表任何真实评审结果。
"""
import json
import random
import sys
import tempfile
from pathlib import Path

import run_review as rr
from bank import ROOT, all_conditions, load_bank, load_config, load_standards, load_yaml


def main(case_id: str) -> None:
    random.seed(7)
    cfg = load_config()
    obs, clauses = load_bank(cfg)
    std = load_standards(cfg)
    cdir = ROOT / "cases" / case_id
    brief = load_yaml(cdir / "brief.yaml")
    scene = json.loads((cdir / "scene.json").read_text(encoding="utf-8"))
    ctx = {"brief": brief, "scene": scene}
    dims = set(brief.get("dimensions") or cfg["standards"].keys())
    needed = {ch["obs"] for cid, c in clauses.items()
              if cid[0] in dims and all_conditions(c.get("applies_if"), ctx)
              for ch in c["checks"] if all_conditions(ch.get("applies_if"), ctx)}
    refs = {k: f"x-{k}" for k in ("scene", "thumb", "left", "right")}
    questions, qmeta, gates = rr.build_questions(needed, obs, scene, refs)
    rr.QUESTIONS_SENT.update(questions)

    answers = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            answers[qid] = {"type": "noul", "noul": 0.95 if qid.startswith("present__") else round(random.random(), 2)}
        else:
            ws = [random.random() for _ in q["criteria"]]
            probs = {k: round(w / sum(ws), 2) for k, w in zip(q["criteria"], ws)}
            answers[qid] = {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs, "confidence": 0.5}
    # 让一个元素核对失败，验证“无法判断”路径
    if gates:
        answers[next(iter(gates.values()))]["noul"] = 0.1

    results = rr.judge(clauses, obs, answers, qmeta, gates, ctx, cfg, dims)
    summ = rr.dimension_summary(results)
    out = Path(tempfile.mkdtemp(prefix="review_selftest_"))
    rr.write_report(out, case_id + "（合成数据自检）", results, summ, std, cfg,
                    {"input_tokens": 0, "output_tokens": 0}, "synthetic", brief, scene, "n/a")

    verdicts = [r["verdict"] for r in results.values()]
    assert len(results) == len([c for c in clauses if c[0] in dims]), "条款数量不符"
    assert all(v in ("合格", "需优化", "存疑", "不合格", "不适用", "无法判断", "描述") for v in verdicts)
    assert (out / "report.md").exists() and (out / "llm_handoff.md").exists()
    print(f"问题 {len(questions) - len(gates)} + 核对 {len(gates)}；条款 {len(results)}")
    print("判定分布：", {v: verdicts.count(v) for v in set(verdicts)})
    print("维度汇总：", summ)
    print(f"自检通过，临时输出：{out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "C001")
