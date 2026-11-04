"""离线自检：不调用 Jev。

1. 检查正式知识库与测试知识库（lint）
2. 用随机答案跑通 C002：路由 → 展开 → 判定 → 报告 → 自动填写复核 → finalize
3. 验证阈值覆盖、soft 不判不合格、一票否决、待复核、finalize 校验
用法：python selftest.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from kb import ROOT, load_config
from run_review import block_summary

PY = sys.executable


def run(*args, ok=True):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"失败：{' '.join(args)}")
    return r


def main():
    cfg = load_config()
    run("lint_kb.py")
    run("lint_kb.py", "--kb", "tests/fixture_kb")
    print("✓ 知识库检查通过（正式 + 测试）")

    tmp = Path(tempfile.mkdtemp(prefix="selftest_"))
    try:
        run("route.py", "check", "C002")
        run("run_review.py", "C002", "--synthetic", "11", "--out", str(tmp))
        v = json.loads((tmp / "verdicts.json").read_text(encoding="utf-8"))
        cl = v["blocks"]["dlm"]["clauses"]
        assert cl["D14"]["verdict"] == "未选中", "路由未选中的条目应为“未选中”"
        assert cl["D02"]["verdict"] == "描述", "未指定主导形式时 D02 只描述"
        for cid, c in cl.items():
            for ch in c["checks"]:
                if ch["soft"]:
                    assert ch["verdict"] != "不合格", f"{cid} soft 检查不应判不合格"
        print("✓ 路由、描述、soft 规则正确")

        # 判定规则单元测试
        th = dict(cfg["judging"]["default"])
        mk = lambda vs, ps: {f"X{i:02d}": {"verdict": v_, "p_min": p} for i, (v_, p) in enumerate(zip(vs, ps))}
        assert block_summary(mk(["合格"] * 9 + ["不合格"], [0.9] * 9 + [0.35]), th)["verdict"] == "合格"      # 90% > 80%
        assert block_summary(mk(["合格"] * 8 + ["不合格"] * 2, [0.9] * 8 + [0.3] * 2), th)["verdict"] == "不合格"  # 80% 不大于 80%
        assert block_summary(mk(["合格"] * 9 + ["不合格"], [0.9] * 9 + [0.1]), th)["verdict"] == "不合格"    # 一票否决
        assert block_summary(mk(["合格"] * 7 + ["存疑"] * 3, [0.9] * 7 + [0.5] * 3), th)["verdict"] == "待复核"
        th2 = {**th, "block_pass_rate": 0.6}
        assert block_summary(mk(["合格"] * 7 + ["不合格"] * 3, [0.9] * 7 + [0.3] * 3), th2)["verdict"] == "合格"
        print("✓ 知识块规则正确（>80%、一票否决、待复核、阈值覆盖）")

        # finalize：先缺项应报错，再自动补全应成功
        tmpl = yaml.safe_load((tmp / "llm_review_template.yaml").read_text(encoding="utf-8"))
        (tmp / "llm_review.yaml").write_text(yaml.safe_dump(tmpl, allow_unicode=True), encoding="utf-8")
        r = run("finalize.py", "C002", "--out", str(tmp), ok=False)
        assert r.returncode != 0, "未填写的复核应被拒绝"
        for k in tmpl["resolutions"]:
            tmpl["resolutions"][k] = {"verdict": "合格", "reason": "自检"}
        bad = [f"dlm.{cid}" for cid, c in cl.items() if c["verdict"] == "不合格"]
        if bad:
            tmpl["overrides"] = {bad[0]: {"verdict": "合格", "reason": "自检推翻"}}
        tmpl["issues"] = [{"priority": 1, "clauses": bad[:1], "kb": "basic", "target": "t", "location": "l",
                           "problem": "p", "action": "a", "expected": "e"}]
        (tmp / "llm_review.yaml").write_text(yaml.safe_dump(tmpl, allow_unicode=True), encoding="utf-8")
        run("finalize.py", "C002", "--out", str(tmp))
        f = json.loads((tmp / "final.json").read_text(encoding="utf-8"))
        assert f["blocks"]["dlm"]["final"] in ("合格", "不合格")
        assert (tmp / "final_report.md").exists()
        print(f"✓ finalize 校验与重算正确（Jev 初判 {f['blocks']['dlm']['jev']} → 最终 {f['blocks']['dlm']['final']}）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("自检全部通过")


if __name__ == "__main__":
    main()
