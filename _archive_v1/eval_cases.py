"""一致率评测：对比人工标注（cases/cases.yaml 的 labels）与管线判定（results/<id>/verdicts.json）。

用法：
    python eval_cases.py                 # 全部已标注案例
    python eval_cases.py --split test    # 只看 test 集（最终测准确率用）

输出：每条条款的一致率、“合格/不合格”方向一致率、存疑率，以及每个观察问题在人工合格与不合格两组上的平均概率（区分度）。
结果同时写入 results/eval_report.md。
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from bank import ROOT, load_yaml

PASS, NONPASS = {"合格"}, {"需优化", "不合格"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["tune", "test", "all"], default="all")
    ap.add_argument("--cases", default=str(ROOT / "cases" / "cases.yaml"))
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--min-n", type=int, default=5, help="样本数达到多少才给出改写建议")
    args = ap.parse_args()

    cases = load_yaml(args.cases)["cases"]
    res_dir = Path(args.results)
    per_clause = defaultdict(lambda: {"n": 0, "exact": 0, "direction": 0, "direction_n": 0, "uncertain": 0, "pairs": []})
    obs_sep = defaultdict(lambda: {"pass": [], "fail": []})
    used, skipped = [], []

    for c in cases:
        labels = c.get("labels") or {}
        if not labels or (args.split != "all" and c.get("split") != args.split):
            continue
        vf = res_dir / c["id"] / "verdicts.json"
        if not vf.exists():
            skipped.append(f"{c['id']}（未运行 run_review）")
            continue
        machine = json.loads(vf.read_text(encoding="utf-8"))["clauses"]
        used.append(c["id"])
        for cid, human in labels.items():
            if cid not in machine:
                continue
            m = machine[cid]["verdict"]
            s = per_clause[cid]
            s["n"] += 1
            s["pairs"].append((c["id"], human, m))
            if m == "存疑":
                s["uncertain"] += 1
            if m == human:
                s["exact"] += 1
            if human in PASS | NONPASS and m in PASS | NONPASS:
                s["direction_n"] += 1
                s["direction"] += (human in PASS) == (m in PASS)
            if human in PASS | NONPASS:
                for ch in machine[cid]["checks"]:
                    if ch.get("p_good") is not None:
                        obs_sep[(cid, ch["obs"])]["pass" if human in PASS else "fail"].append(ch["p_good"])

    L = [f"# 一致率评测（split={args.split}）", "",
         f"- 参与案例：{len(used)} 个 {used}",
         f"- 跳过：{skipped or '无'}", ""]
    if not used:
        L.append("没有可评测的案例：请在 cases/cases.yaml 中填写 labels，并先对这些案例运行 run_review.py。")
    else:
        L += ["## 条款一致率", "",
              "| 条款 | 样本 | 完全一致 | 方向一致（合格 vs 非合格） | 存疑率 | 建议 |", "|---|---|---|---|---|---|"]
        for cid in sorted(per_clause):
            s = per_clause[cid]
            exact = s["exact"] / s["n"]
            direc = s["direction"] / s["direction_n"] if s["direction_n"] else None
            unc = s["uncertain"] / s["n"]
            tip = "样本不足"
            if s["n"] >= args.min_n:
                tip = "改写问题或转大模型判定" if (direc is not None and direc < 0.7) else "存疑过多，检查问题措辞" if unc > 0.3 else "可用"
            L.append(f"| {cid} | {s['n']} | {exact:.0%} | {'—' if direc is None else f'{direc:.0%}'} | {unc:.0%} | {tip} |")
        L += ["", "## 观察问题区分度", "",
              "人工判合格的案例上，该问题“好的方向”平均概率应明显高于人工判不合格的案例；两者接近说明这个问题没有区分力。", "",
              "| 条款 / 观察问题 | 人工合格：均值(n) | 人工非合格：均值(n) | 差值 |", "|---|---|---|---|"]
        for (cid, oid), v in sorted(obs_sep.items()):
            mp = sum(v["pass"]) / len(v["pass"]) if v["pass"] else None
            mf = sum(v["fail"]) / len(v["fail"]) if v["fail"] else None
            diff = f"{mp - mf:+.2f}" if mp is not None and mf is not None else "—"
            fmt = lambda m, n: "—" if m is None else f"{m:.2f}({n})"
            L.append(f"| {cid} / {oid} | {fmt(mp, len(v['pass']))} | {fmt(mf, len(v['fail']))} | {diff} |")
        L += ["", "## 不一致明细", ""]
        for cid in sorted(per_clause):
            for case_id, h, m in per_clause[cid]["pairs"]:
                if h != m:
                    L.append(f"- {cid} @ {case_id}：人工 {h} / 管线 {m}")

    text = "\n".join(L)
    print(text)
    out = res_dir / "eval_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
