"""第二、三步：按路由结果展开问题 → 分“美术基础 / 项目规范”两次请求 Jev → 代码判定 → 生成报告与大模型交接包。

用法：
    python run_review.py C002                 # 读取 cases/C002/{brief.yaml, scene.json, routing.yaml}
    python run_review.py C002 --dry-run       # 只生成请求，不调用 Jev
    python run_review.py C002 --synthetic 7   # 用随机答案代替 Jev（自检用，结果无意义）
    可选：--kb 知识库路径  --cases 案例目录  --out 输出目录

输出 results/<案例>/：request_*.json  response_*.json  verdicts.json  report.md  llm_handoff.md  llm_review_template.yaml
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import sys
import uuid
from pathlib import Path

import requests
import yaml
from PIL import Image, ImageOps

from kb import (ROOT, all_conditions, block_from_dict, kb_root, load_blocks, load_config, load_yaml, slug,
                stable_hash, thresholds)

ORDER = {"合格": 0, "存疑": 1, "不合格": 2}
KB_NAME = {"basic": "美术基础", "project": "项目规范"}


# ============================== 图片 ==============================
def _fit(im: Image.Image, max_side: int) -> Image.Image:
    w, h = im.size
    s = min(1.0, max_side / max(w, h))
    return im.resize((round(w * s), round(h * s)), Image.LANCZOS) if s < 1 else im


def to_jpeg(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=92, progressive=False)
    return buf.getvalue()


def prepare_scene(path: Path, cfg: dict) -> dict[str, Image.Image]:
    ic = cfg["image"]
    base = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    full = _fit(base, ic["max_side"])
    if min(full.size) < ic["min_side"]:
        raise ValueError(f"图片短边 {min(full.size)}px 小于 Jev 下限 {ic['min_side']}px")
    s = ic["thumb_short_side"] / min(base.size)
    imgs = {"scene": full,
            "thumb": _fit(base.resize((round(base.size[0] * s), round(base.size[1] * s)), Image.LANCZOS), ic["max_side"])}
    w, h = full.size
    left, right = full.crop((0, 0, w // 2, h)), full.crop((w // 2, 0, w, h))
    if min(left.size) >= ic["min_side"]:
        imgs["left"], imgs["right"] = left, right
    return imgs


def load_ref(path: Path, cfg: dict) -> Image.Image:
    return _fit(ImageOps.exif_transpose(Image.open(path)).convert("RGB"), cfg["image"]["max_side"])


# ============================== 展开问题 ==============================
def slot_items(scene: dict, slot: str) -> list[dict]:
    v = scene.get(slot)
    return [] if v is None else (v if isinstance(v, list) else [v])


def expand(b, oid: str, scene: dict) -> list[dict]:
    """把一个观察问题展开成若干问题单元。图片位置先用符号占位，组装请求时再替换为资源 ID。"""
    o = b.observations[oid]
    subject = scene.get("subject")
    if "subject" in o.get("needs", []) and not subject:
        return []
    for s in o.get("needs", []):
        if s != "subject" and not scene.get(s):
            return []

    def fill(text: str, item, half):
        out = text
        if item is not None:
            out = out.replace("{item}", item["name"])
        if subject:
            out = out.replace("{subject}", subject["name"])
        for s in o.get("needs", []):
            if s != "subject" and isinstance(scene.get(s), dict):
                out = out.replace("{" + s + "}", scene[s]["name"])
        out = out.replace("{thumb_img}", "<<thumb>>")
        if half:
            out = out.replace("{half_img}", f"<<{half}>>")
        for name in b.refs:
            out = out.replace("{ref:" + name + "}", f"<<ref:{b.ref_path(name).as_posix()}>>")
        return out[0].upper() + out[1:] if out else out

    if o.get("image") == "halves":
        units = [(h, None, h) for h in ("left", "right")]
    elif o.get("over"):
        units = [(slug(it["name"]), it, None) for it in slot_items(scene, o["over"])]
    else:
        units = [(None, None, None)]
    out = []
    for key, item, half in units:
        q = {"type": o["type"], "instructions": fill(o["q"], item, half)}
        if o["type"] == "choice" and o.get("options_from"):
            opts = {}
            for s in o["options_from"]:
                for it in slot_items(scene, s):
                    opts.setdefault(slug(it["name"]), it["name"])
            if len(opts) < 2:
                continue
            q["criteria"] = opts
        else:
            q["criteria"] = {k: fill(v, item, half) for k, v in o["criteria"].items()}
        names = []
        if item is not None:
            names.append(item["name"])
        if subject and ("subject" in o.get("needs", []) or o.get("options_from")):
            names.append(subject["name"])
        out.append({"block": b.id, "kb": b.kb, "obs": oid, "item_key": key, "item": item,
                    "q": q, "gate_names": sorted(set(names))})
    return out


def selected_checks(sel: dict, blocks: dict, ctx: dict):
    """遍历被选中、且机器条件成立的 (知识块, 条目, 检查)。"""
    for bid, cids in sel.items():
        b = blocks[bid]
        for cid in cids:
            c = b.clauses[cid]
            if not all_conditions(c.get("applies_if"), ctx):
                continue
            for ch in c["checks"]:
                if all_conditions(ch.get("applies_if"), ctx):
                    yield b, cid, ch


def build(sel: dict, blocks: dict, ctx: dict):
    """返回 qmeta, questions[req], gates[req]（问题文本中仍是符号占位）。"""
    scene = ctx["scene"]
    needed = {}
    for b, cid, ch in selected_checks(sel, blocks, ctx):
        needed.setdefault((b.id, ch["obs"]), b)
    groups = {}
    for (bid, oid), b in needed.items():
        for u in expand(b, oid, scene):
            groups.setdefault(stable_hash(u["q"]), []).append(u)

    qmeta, questions, gates, used_ids = {}, {"basic": {}, "project": {}}, {"basic": {}, "project": {}}, set()
    for h, us in groups.items():
        u0 = us[0]
        qid = f"{u0['block']}__{u0['obs']}" + (f"__{u0['item_key']}" if u0["item_key"] else "")
        if qid in used_ids:
            qid = f"{qid}__{h[:4]}"
        used_ids.add(qid)
        req = "project" if any(u["kb"] == "project" for u in us) else "basic"
        questions[req][qid] = u0["q"]
        qmeta[qid] = {"req": req, "members": [(u["block"], u["obs"], u["item_key"]) for u in us],
                      "item": u0["item"], "gate_names": u0["gate_names"]}
        for name in u0["gate_names"]:
            gid = f"present__{slug(name)}"
            if gid not in gates[req]:
                cap = name[0].upper() + name[1:]
                gates[req][gid] = {"type": "noul", "instructions": f"Does `scene` contain {name}?",
                                   "criteria": {"true": f"{cap} can be found in the image",
                                                "false": f"Nothing in the image matches {name}"}}
    return qmeta, questions, gates


def assemble(req_questions: dict, req_gates: dict, imgs: dict, cfg: dict, tag: str, notes: str | None):
    """把符号占位替换为资源 ID，生成请求体与要上传的图片。"""
    qs = {**req_questions, **req_gates}
    text = json.dumps(qs, ensure_ascii=False)
    assets, files = {f"{tag}-scene": {"type": "image", "part": "img-scene"}}, {"img-scene": imgs["scene"]}
    for k in ("thumb", "left", "right"):
        if f"<<{k}>>" in text:
            text = text.replace(f"<<{k}>>", f"{tag}-{k}")
            assets[f"{tag}-{k}"] = {"type": "image", "part": f"img-{k}"}
            files[f"img-{k}"] = imgs[k]
    refs = sorted(set(seg.split(">>")[0] for seg in text.split("<<ref:")[1:]))
    for i, p in enumerate(refs):
        rid = f"{tag}-ref{i}"
        text = text.replace(f"<<ref:{p}>>", rid)
        assets[rid] = {"type": "image", "part": f"img-ref{i}"}
        files[f"img-ref{i}"] = load_ref(Path(p), cfg)
    state = {"scene": f"{tag}-scene"}
    if notes:
        state["notes"] = notes
    return {"model": cfg["model"], "state": state, "assets": assets, "questions": json.loads(text)}, files, refs


# ============================== 判定 ==============================
def good_prob(ch: dict, o: dict, ans: dict, item, ctx: dict, cfg: dict):
    if o["type"] == "noul":
        return ans["noul"] if ch["good"] else 1 - ans["noul"]
    probs = ans["probabilities"]
    if "good_option_slot" in ch:
        t = slot_items(ctx["scene"], ch["good_option_slot"])
        return probs.get(slug(t[0]["name"]), 0.0) if t else None
    if "good_options" in ch:
        return sum(probs.get(k, 0.0) for k in ch["good_options"])
    if "match_brief" in ch:
        want = ctx["brief"].get(ch["match_brief"])
        return probs.get(cfg["dominant_form_map"].get(want, want), 0.0) if want else None
    if "match_item" in ch:
        want = (item or {}).get(ch["match_item"])
        return probs.get(want, 0.0) if want else None
    return None


def level(p: float, th: dict) -> str:
    return "合格" if p >= th["pass_at"] else "不合格" if p < th["fail_below"] else "存疑"


def judge(sel, blocks, answers, qmeta, ctx, cfg, routing):
    """answers: {req: {qid: answer}}。返回 {bid: {clauses: {...}}}。"""
    idx = {}
    for qid, m in qmeta.items():
        for bid, oid, key in m["members"]:
            idx.setdefault((bid, oid), []).append((qid, key))
    skipped_reason = {it["id"]: (it.get("skipped") or {}) for it in routing.get("blocks") or []}
    out = {}
    for bid, cids in sel.items():
        b = blocks[bid]
        res = {}
        for cid, c in b.clauses.items():
            th = thresholds(cfg, bid, cid)
            r = {"title": c["title"], "kb": b.kb, "thresholds": th, "checks": []}
            if cid not in cids:
                r["verdict"] = "未选中"
                r["reason"] = skipped_reason.get(bid, {}).get(cid, "路由未选择")
                res[cid] = r
                continue
            if not all_conditions(c.get("applies_if"), ctx):
                r["verdict"] = "不适用"
                r["reason"] = f"条件不成立：{c.get('applies_if')}"
                res[cid] = r
                continue
            for ch in c["checks"]:
                if not all_conditions(ch.get("applies_if"), ctx):
                    continue
                o = b.observations[ch["obs"]]
                items = []
                for qid, key in idx.get((bid, ch["obs"]), []):
                    m = qmeta[qid]
                    a = answers[m["req"]][qid]
                    gate_fail = None
                    for name in m["gate_names"]:
                        g = answers[m["req"]].get(f"present__{slug(name)}")
                        if g and g["noul"] < th["gate"]:
                            gate_fail = f"{name} 存在概率 {g['noul']:.2f}"
                            break
                    p = None if gate_fail else good_prob(ch, o, a, m["item"], ctx, cfg)
                    items.append({"qid": qid, "req": m["req"], "item": key, "answer": a.get("noul", a.get("choice")),
                                  "probabilities": a.get("probabilities"), "p_good": None if p is None else round(p, 3),
                                  "gated": gate_fail, "verdict": None if p is None else level(p, th)})
                scored = [it["p_good"] for it in items if it["p_good"] is not None]
                if not items or all(it["gated"] for it in items):
                    v, p = "无法判断", None
                elif not scored:
                    v, p = "描述", None
                else:
                    p = max(scored) if ch.get("aggregate") == "best" else min(scored)
                    v = level(p, th)
                    if ch.get("soft") and v == "不合格":
                        v = "存疑"
                r["checks"].append({"obs": ch["obs"], "soft": bool(ch.get("soft")), "aggregate": ch.get("aggregate", "worst"),
                                    "good": ch.get("good"), "verdict": v, "p_good": None if p is None else round(p, 3),
                                    "items": items})
            graded = [x["verdict"] for x in r["checks"] if x["verdict"] in ORDER]
            hard = [x["p_good"] for x in r["checks"] if x["p_good"] is not None and not x["soft"]]
            r["p_min"] = min(hard) if hard else None
            if graded:
                r["verdict"] = max(graded, key=ORDER.get)
            elif r["checks"] and all(x["verdict"] == "描述" for x in r["checks"]):
                r["verdict"] = "描述"
            elif r["checks"]:
                r["verdict"] = "无法判断"
            else:
                r["verdict"] = "不适用"
                r["reason"] = "所有检查的条件都不成立"
            res[cid] = r
        out[bid] = {"name": b.name, "kb": b.kb, "path": b.node.rel, "clauses": res}
    return out


def block_summary(clauses: dict, th: dict, final: bool = False) -> dict:
    """知识块判定。final=True 时 clauses 中不应再有“存疑”。"""
    graded = {cid: c for cid, c in clauses.items() if c["verdict"] in ORDER}
    n = len(graded)
    ok = sum(1 for c in graded.values() if c["verdict"] == "合格")
    unsure = sum(1 for c in graded.values() if c["verdict"] == "存疑")
    vetoes = [cid for cid, c in graded.items()
              if c.get("p_min") is not None and c["p_min"] < th["veto_below"] and not c.get("veto_lifted")]
    rate = ok / n if n else None
    if n == 0:
        v = "无可评条目"
    elif vetoes:
        v = "不合格"
    elif rate > th["block_pass_rate"]:
        v = "合格"
    elif not final and unsure and (ok + unsure) / n > th["block_pass_rate"]:
        v = "待复核"
    else:
        v = "不合格"
    return {"verdict": v, "evaluated": n, "passed": ok, "uncertain": unsure, "failed": n - ok - unsure,
            "pass_rate": None if rate is None else round(rate, 3), "vetoes": vetoes,
            "rule": f"合格率 > {th['block_pass_rate']:.0%} 且无条目 < {th['veto_below']}"}


# ============================== 输出 ==============================
def evidence(ch: dict) -> str:
    parts = []
    for it in ch["items"]:
        tag = ch["obs"] + (f"[{it['item']}]" if it["item"] else "")
        if it["gated"]:
            parts.append(f"{tag}: 元素核对未通过（{it['gated']}）")
        elif it["p_good"] is None:
            parts.append(f"{tag}: {it['answer']}（仅描述）")
        else:
            parts.append(f"{tag}: {it['p_good']:.2f}")
    soft = "（soft）" if ch["soft"] else ""
    return soft + "；".join(parts)


def write_outputs(out: Path, case_id, results, routing, brief, scene, usage, model, image_path, cfg, blocks):
    tokens = sum(u.get("input_tokens", 0) for u in usage.values())
    cost = tokens * cfg["price_per_mtok"] / 1e6
    summaries = {bid: block_summary(r["clauses"], thresholds(cfg, bid)) for bid, r in results.items()}
    for bid in results:
        results[bid]["summary"] = summaries[bid]
    (out / "verdicts.json").write_text(json.dumps({
        "case": case_id, "model": model, "usage": usage, "image": str(image_path),
        "routing": routing, "blocks": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- report.md ----------
    d = cfg["judging"]["default"]
    L = [f"# 评审报告 {case_id}（Jev 初判）", "",
         f"- 图片：`{image_path}`",
         f"- 图类型：{routing.get('image_type', '未填写')}",
         f"- 模型：{model}；请求：" + "，".join(f"{KB_NAME[k]} {v.get('input_tokens', 0)} token" for k, v in usage.items())
         + f"；合计约 ${cost:.5f}",
         f"- 默认规则：条目 ≥{d['pass_at']} 合格、<{d['fail_below']} 不合格、之间存疑；知识块合格率 >{d['block_pass_rate']:.0%} 且无条目 <{d['veto_below']}（按知识块覆盖的阈值见各块）",
         "", "## 知识块结论", "", "| 知识块 | 来源 | 初判 | 合格 / 存疑 / 不合格 | 合格率 | 一票否决 |", "|---|---|---|---|---|---|"]
    for bid, r in results.items():
        s = r["summary"]
        rate = "—" if s["pass_rate"] is None else f"{s['pass_rate']:.0%}"
        L.append(f"| {r['name']}（{bid}） | {KB_NAME[r['kb']]} | **{s['verdict']}** | {s['passed']} / {s['uncertain']} / {s['failed']} | {rate} | {', '.join(s['vetoes']) or '—'} |")
    miss = routing.get("missing_knowledge") or []
    if miss:
        L += ["", "**适用但知识库尚未建设：** " + "；".join(f"{m['path']}（{m.get('reason', '')}）" for m in miss)]
    for bid, r in results.items():
        L += ["", f"## {r['name']}（{bid}）", "", "| 条目 | 判定 | 依据（好的方向概率） |", "|---|---|---|"]
        for cid, c in r["clauses"].items():
            ev = " / ".join(evidence(ch) for ch in c["checks"]) or c.get("reason", "—")
            L.append(f"| {cid} {c['title']} | {c['verdict']} | {ev} |")
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")

    # ---------- 交接包 ----------
    issues = {}
    for bid, r in results.items():
        for cid, c in r["clauses"].items():
            if c["verdict"] not in ("存疑", "不合格"):
                continue
            for ch in c["checks"]:
                if ch["verdict"] not in ("存疑", "不合格"):
                    continue
                scored = [it for it in ch["items"] if it["p_good"] is not None]
                if ch["aggregate"] == "best" and scored:
                    bad = [max(scored, key=lambda it: it["p_good"])]
                else:
                    bad = [it for it in scored if it["verdict"] in ("存疑", "不合格")] or scored
                for it in bad:
                    g = issues.setdefault(it["qid"], {"item": it, "obs": ch["obs"], "clauses": [], "verdict": it["verdict"]})
                    if ch["soft"] and g["verdict"] == "不合格":
                        g["verdict"] = "存疑"
                    if f"{bid}.{cid}" not in g["clauses"]:
                        g["clauses"].append(f"{bid}.{cid}")
    order = sorted(issues.values(), key=lambda g: (-ORDER.get(g["verdict"], 0), g["item"]["p_good"] or 0))
    H = [f"# 大模型交接包 {case_id}", "",
         "你是游戏场景概念设计的评图专家。下面是 Jev 按知识库条目逐项观察后的初判。请完成：",
         "1. 查看原图。对每个**存疑**条目给出最终判定（合格或不合格）和理由。",
         "2. 如果你认为 Jev 判定的合格或不合格有误，可以推翻，但必须写明依据（填在 overrides 里）。",
         "3. 合并同一原因造成的问题，不要重复扣分。同一个 Jev 问题被多个条目引用时，下面已经自动归为一组。",
         "4. **项目规范优先**：项目规范与美术基础的结论冲突时，以项目规范为准，并在修改项中注明。",
         "5. 按对画面的影响排序，给出 1–5 项修改：对象、位置、问题、动作、期望效果、涉及条目。动作要具体到能在 PS 或 DCC 中执行。",
         "6. 列出修改时需要保留的关系。",
         f"7. 按 `llm_review_template.yaml` 的格式写入 `llm_review.yaml`，然后运行 `python finalize.py {case_id}`。",
         "", f"原图：`{image_path}`", "",
         "## 用户说明", "```json", json.dumps(brief, ensure_ascii=False, indent=2), "```",
         "## 场景解析", "```json", json.dumps(scene, ensure_ascii=False, indent=2), "```",
         "## 知识块初判", ""]
    for bid, r in results.items():
        s = r["summary"]
        H.append(f"- {r['name']}（{bid}，{KB_NAME[r['kb']]}）：{s['verdict']}；合格 {s['passed']}、存疑 {s['uncertain']}、不合格 {s['failed']}；规则：{s['rule']}")
    if miss:
        H.append("- 适用但缺少知识：" + "；".join(m["path"] for m in miss))
    H += ["", "## 待处理问题（按严重程度排序，已按原因归组）", ""]
    for i, g in enumerate(order, 1):
        it = g["item"]
        H.append(f"### 问题 {i}：{g['verdict']}　`{g['obs']}`" + (f"　元素 `{it['item']}`" if it["item"] else ""))
        H.append(f"- 好的方向概率：{it['p_good']:.2f}；原始答案：{it['answer']}" +
                 (f"；各选项：{it['probabilities']}" if it.get("probabilities") else ""))
        for key in g["clauses"]:
            bid, cid = key.split(".")
            f = blocks[bid].std.get(cid, {}).get("fields", {})
            H.append(f"- **{key} {blocks[bid].std.get(cid, {}).get('title', '')}**（{KB_NAME[blocks[bid].kb]}）")
            for fld in ("判断说明", "合格表现", "不合格表现", "易混淆", "不合格时"):
                if f.get(fld):
                    H.append(f"  - {fld}：{f[fld]}")
            for ex in blocks[bid].examples_for(cid):
                H.append(f"  - 案例图（{ex.get('label')}）：`{(blocks[bid].node.path / ex['file']).as_posix()}`　{ex.get('note', '')}")
        H.append("")
    H += ["## 其余条目", ""]
    for bid, r in results.items():
        for cid, c in r["clauses"].items():
            if c["verdict"] in ("不适用", "无法判断", "描述", "未选中"):
                H.append(f"- {bid}.{cid} {c['title']}：{c['verdict']}" + (f"（{c.get('reason')}）" if c.get("reason") else ""))
    (out / "llm_handoff.md").write_text("\n".join(H), encoding="utf-8")

    # ---------- 复核模板 ----------
    tmpl = {"case": case_id, "reviewer": None,
            "resolutions": {f"{bid}.{cid}": {"verdict": None, "reason": None}
                            for bid, r in results.items() for cid, c in r["clauses"].items() if c["verdict"] == "存疑"},
            "overrides": {},
            "issues": [{"priority": 1, "clauses": [], "kb": "basic", "target": None, "location": None,
                        "problem": None, "action": None, "expected": None}],
            "keep": [], "notes": None}
    head = ("# 第四步：大模型复核结果。复制为 llm_review.yaml 后填写。\n"
            "# resolutions：每个“存疑”条目必须给出 verdict（合格/不合格）和 reason\n"
            "# overrides：推翻 Jev 已判合格或不合格的条目，例如 dlm.D13: {verdict: 合格, reason: ...}\n"
            "# issues：合并同因后的修改项，按 priority 从 1 开始排序；kb 填 basic 或 project（冲突时以 project 为准）\n")
    (out / "llm_review_template.yaml").write_text(head + yaml.safe_dump(tmpl, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return summaries, cost


# ============================== 主流程 ==============================
def read_user_env(name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def synthetic_answers(questions: dict, rng: random.Random) -> dict:
    out = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            out[qid] = {"type": "noul", "noul": 0.95 if qid.startswith("present__") else round(rng.random(), 2)}
        else:
            ws = [rng.random() for _ in q["criteria"]]
            probs = {k: round(w / sum(ws), 2) for k, w in zip(q["criteria"], ws)}
            out[qid] = {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs, "confidence": 0.5}
    return out


def load_case(case_dir: Path):
    brief = load_yaml(case_dir / "brief.yaml")
    scene = json.loads((case_dir / "scene.json").read_text(encoding="utf-8"))
    routing = load_yaml(case_dir / "routing.yaml")
    return brief, scene, routing


class ReviewError(Exception):
    """评审流程中可预期的错误（配置、输入、接口），信息可直接展示给用户。"""


def jev_key_default() -> str | None:
    return os.environ.get("TYPESAFE_API_KEY") or read_user_env("TYPESAFE_API_KEY")


def run_case(case_dir: Path, out: Path, *, kb: str | None = None, jev_key: str | None = None,
             dry_run: bool = False, synthetic: int | None = None, cfg: dict | None = None, log=print) -> dict:
    """第二、三步。返回 {summaries, results, usage, model, cost}。出错抛 ReviewError。"""
    cfg = cfg or load_config()
    blocks = load_blocks(kb_root(cfg, kb))
    brief, scene, routing = load_case(case_dir)
    ctx = {"brief": brief, "scene": scene}
    image_path = (case_dir / brief.get("image", "image.jpg")).resolve()
    case_id = case_dir.name

    seen = {}
    for s, v in scene.items():
        for it in (v if isinstance(v, list) else [v] if isinstance(v, dict) else []):
            if isinstance(it, dict) and it.get("name"):
                k = slug(it["name"])
                if k in seen and seen[k] != it["name"]:
                    raise ReviewError(f"场景解析中两个元素名称过于相似（ID 冲突 {k}）：'{seen[k]}' / '{it['name']}'")
                seen[k] = it["name"]

    sel = {}
    for it in routing.get("blocks") or []:
        b = blocks.get(it["id"])
        if b is None or not b.usable:
            raise ReviewError(f"路由中的知识块 {it['id']} 不存在或不可用")
        sel[it["id"]] = [c for c in it.get("clauses") or [] if c in b.clauses]
    if routing.get("extra"):
        from lint_kb import lint_questions
        ub = block_from_dict("user", "project", routing["extra"], case_dir)
        e, _ = lint_questions(ub, cfg, check_std=False)
        if e:
            raise ReviewError("用户补充问题未通过检查：\n" + "\n".join(e))
        blocks["user"] = ub
        sel["user"] = list(ub.clauses)

    qmeta, questions, gates = build(sel, blocks, ctx)
    try:
        imgs = prepare_scene(image_path, cfg)
    except ValueError as e:
        raise ReviewError(str(e)) from e
    tag = uuid.uuid4().hex[:8]
    out.mkdir(parents=True, exist_ok=True)

    reqs = {}
    for req in ("basic", "project"):
        if not questions[req]:
            continue
        body, files, refs = assemble(questions[req], gates[req], imgs, cfg, tag, brief.get("scene_notes"))
        reqs[req] = (body, files)
        (out / f"request_{req}.json").write_text(json.dumps(
            {"request": body, "images": {k: list(v.size) for k, v in files.items()}, "refs": refs},
            ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[{KB_NAME[req]}] 问题 {len(questions[req])} 个 + 元素核对 {len(gates[req])} 个；图片 {len(files)} 张")
    if not reqs:
        raise ReviewError("没有可发送的问题：检查路由选择的条目和场景解析中的元素")
    if dry_run:
        log(f"[dry-run] 请求已写入 {out}")
        return {"dry_run": True}

    answers, usage, model = {}, {}, None
    if synthetic is not None:
        rng = random.Random(synthetic)
        for req, (body, _) in reqs.items():
            answers[req] = synthetic_answers(body["questions"], rng)
            usage[req] = {"input_tokens": 0, "output_tokens": 0}
        model = "synthetic"
    else:
        key = jev_key or jev_key_default()
        if not key:
            raise ReviewError("缺少 Jev API Key：请在“设置”中填写")
        for req, (body, files) in reqs.items():
            mp = {"request": (None, json.dumps(body), "application/json")}
            for part, im in files.items():
                mp[part] = (f"{part}.jpg", to_jpeg(im), "image/jpeg")
            try:
                resp = requests.post(cfg["api"], files=mp, timeout=300,
                                     headers={"Authorization": f"Bearer {key}", "TypeSafe-Danger-Zone-Images": "true"})
            except requests.RequestException as e:
                raise ReviewError(f"[{KB_NAME[req]}] 无法连接 Jev：{e}") from e
            if resp.status_code != 200:
                hint = "（API Key 无效或已失效）" if resp.status_code == 401 else ""
                raise ReviewError(f"[{KB_NAME[req]}] Jev 请求失败 HTTP {resp.status_code}{hint}: {resp.text[:500]}")
            data = resp.json()
            (out / f"response_{req}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            answers[req], usage[req], model = data["answers"], data["usage"], data["model"]

    results = judge(sel, blocks, answers, qmeta, ctx, cfg, routing)
    summaries, cost = write_outputs(out, case_id, results, routing, brief, scene, usage, model, image_path, cfg, blocks)
    log(f"Jev {model}：" + "，".join(f"{KB_NAME[k]} {v['input_tokens']} token" for k, v in usage.items()) + f"，约 ${cost:.5f}")
    for bid, s in summaries.items():
        log(f"{results[bid]['name']}（{bid}）初判：{s['verdict']}，合格 {s['passed']} 存疑 {s['uncertain']} 不合格 {s['failed']}")
    return {"summaries": summaries, "results": results, "usage": usage, "model": model, "cost": cost}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--kb")
    ap.add_argument("--cases", default=str(ROOT / "cases"))
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--synthetic", type=int, metavar="SEED")
    a = ap.parse_args()
    case_dir = Path(a.cases) / a.case_id
    out = Path(a.out) if a.out else ROOT / "results" / a.case_id
    try:
        r = run_case(case_dir, out, kb=a.kb, dry_run=a.dry_run, synthetic=a.synthetic)
    except ReviewError as e:
        sys.exit(str(e))
    if r.get("dry_run"):
        return
    for bid, res in r["results"].items():
        for cid, c in res["clauses"].items():
            print(f"    {cid} {c['verdict']:<4} {c['title']}")
    print(f"输出：{out}")


if __name__ == "__main__":
    main()
