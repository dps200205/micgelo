"""一致率评测：对比人工标注与管线判定，用于校准问题和阈值。

    python eval_cases.py                    # 对比 Jev 初判（校准 Jev 用）
    python eval_cases.py --stage final      # 对比大模型复核后的最终结论
    python eval_cases.py --split test       # 只看 test 集（最终测准确率用，调参时不要看）

标注写在 cases/cases.yaml：labels 的键为 知识块ID.条目编号，值为 合格 / 不合格 / 不适用。
结果写入 results/eval_report.md。
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from kb import ROOT, load_yaml

GRADED = {"合格", "不合格"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["tune", "test", "all"], default="all")
    ap.add_argument("--stage", choices=["jev", "final"], default="jev")
    ap.add_argument("--cases", default=str(ROOT / "cases" / "cases.yaml"))
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--min-n", type=int, default=5)
    a = ap.parse_args()
    reg = load_yaml(a.cases).get("cases") or []
    per = defaultdict(lambda: {"n": 0, "agree": 0, "unsure": 0, "pairs": []})
    sep = defaultdict(lambda: {"合格": [], "不合格": []})
    used, skipped = [], []
    fname = "verdicts.json" if a.stage == "jev" else "verdicts_final.json"
    for c in reg:
        labels = c.get("labels") or {}
        if not labels or (a.split != "all" and c.get("split") != a.split):
            continue
        vf = Path(a.results) / c["id"] / fname
        if not vf.exists():
            skipped.append(f"{c['id']}（缺 {fname}）")
            continue
        blocks = json.loads(vf.read_text(encoding="utf-8"))["blocks"]
        used.append(c["id"])
        for key, human in labels.items():
            bid, _, cid = key.partition(".")
            m = (blocks.get(bid) or {}).get("clauses", {}).get(cid)
            if not m:
                continue
            s = per[key]
            s["n"] += 1
            s["pairs"].append((c["id"], human, m["verdict"]))
            s["unsure"] += m["verdict"] == "存疑"
            s["agree"] += m["verdict"] == human
            if human in GRADED:
                for ch in m.get("checks", []):
                    if ch.get("p_good") is not None:
                        sep[(key, ch["obs"])][human].append(ch["p_good"])
    L = [f"# 一致率评测（stage={a.stage}，split={a.split}）", "", f"- 参与案例：{len(used)} 个 {used}", f"- 跳过：{skipped or '无'}", ""]
    if not used:
        L.append("没有可评测的案例：请在 cases/cases.yaml 中填写 labels，并先对这些案例运行 run_review.py。")
    else:
        L += ["## 条目一致率", "", "| 条目 | 样本 | 一致率 | 存疑率 | 建议 |", "|---|---|---|---|---|"]
        for key in sorted(per):
            s = per[key]
            agree, unsure = s["agree"] / s["n"], s["unsure"] / s["n"]
            tip = "样本不足"
            if s["n"] >= a.min_n:
                tip = "改写问题或改由大模型判定" if agree < 0.7 else "存疑过多，检查措辞或阈值" if unsure > 0.3 else "可用"
            L.append(f"| {key} | {s['n']} | {agree:.0%} | {unsure:.0%} | {tip} |")
        L += ["", "## 观察问题区分度", "", "人工判合格的图上“好的方向”平均概率应明显高于人工判不合格的图；两者接近说明这个问题没有区分力，阈值也无从调起。", "",
              "| 条目 / 观察问题 | 人工合格：均值(n) | 人工不合格：均值(n) | 差值 |", "|---|---|---|---|"]
        for (key, oid), v in sorted(sep.items()):
            mp = sum(v["合格"]) / len(v["合格"]) if v["合格"] else None
            mf = sum(v["不合格"]) / len(v["不合格"]) if v["不合格"] else None
            fmt = lambda m, n: "—" if m is None else f"{m:.2f}({n})"
            diff = f"{mp - mf:+.2f}" if mp is not None and mf is not None else "—"
            L.append(f"| {key} / {oid} | {fmt(mp, len(v['合格']))} | {fmt(mf, len(v['不合格']))} | {diff} |")
        L += ["", "## 不一致明细", ""]
        for key in sorted(per):
            for cid, h, m in per[key]["pairs"]:
                if h != m:
                    L.append(f"- {key} @ {cid}：人工 {h} / 管线 {m}")
    text = "\n".join(L)
    print(text)
    out = Path(a.results) / "eval_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
