"""评图管线运行器。

用法：
    python run_review.py C001            # 读取 cases/cases.yaml 中的 C001，调用 Jev，输出到 results/C001/
    python run_review.py C001 --dry-run  # 只生成问题和请求，不调用 Jev

每个案例需要：
    cases/cases.yaml       中登记的图片路径
    cases/C001/brief.yaml  项目说明（意图信息，由人填写）
    cases/C001/scene.json  场景解析结果（按 prompts/scene_parse_prompt.md 由多模态大模型生成）

API Key 读取环境变量 TYPESAFE_API_KEY。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageOps

from bank import ROOT, all_conditions, load_bank, load_config, load_standards, load_yaml, slug

PRICE_PER_MTOK = 0.042
SEVERITY = {"合格": 0, "需优化": 1, "存疑": 2, "不合格": 3}


# =============================== 图片 ===============================
def _fit(im: Image.Image, max_side: int) -> Image.Image:
    w, h = im.size
    s = min(1.0, max_side / max(w, h))
    return im.resize((round(w * s), round(h * s)), Image.LANCZOS) if s < 1 else im


def _jpeg(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92, progressive=False)
    return buf.getvalue()


def prepare_images(path: Path, cfg: dict) -> dict[str, Image.Image]:
    ic = cfg["image"]
    base = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    full = _fit(base, ic["max_side"])
    if min(full.size) < ic["min_side"]:
        sys.exit(f"图片短边 {min(full.size)}px 小于 Jev 下限 {ic['min_side']}px")
    s = ic["thumb_short_side"] / min(base.size)
    thumb = _fit(base.resize((round(base.size[0] * s), round(base.size[1] * s)), Image.LANCZOS), ic["max_side"])
    w, h = full.size
    imgs = {"scene": full, "thumb": thumb}
    left, right = full.crop((0, 0, w // 2, h)), full.crop((w // 2, 0, w, h))
    if min(left.size) >= ic["min_side"]:
        imgs["left"], imgs["right"] = left, right
    return imgs


# =============================== 问题展开 ===============================
def slot_items(scene: dict, slot: str) -> list[dict]:
    v = scene.get(slot)
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def build_questions(obs_needed: set, obs: dict, scene: dict, refs: dict) -> tuple[dict, dict, dict]:
    """返回 (questions, qmeta, gates)。qmeta[qid] = {obs, item_key, item}。"""
    subject = scene.get("subject")
    questions, qmeta, names = {}, {}, {}

    def fill(text: str, item: dict | None, half: str | None) -> str:
        out = text
        if item is not None:
            out = out.replace("{item}", item["name"])
        if subject:
            out = out.replace("{subject}", subject["name"])
        out = out.replace("{thumb_img}", refs.get("thumb", "{thumb_img}"))
        if half:
            out = out.replace("{half_img}", refs[half])
        return out[0].upper() + out[1:] if out else out

    for oid in sorted(obs_needed):
        o = obs[oid]
        if "subject" in o.get("needs", []) and not subject:
            continue
        if o.get("image") == "halves":
            if "left" not in refs:
                continue
            units = [(h, None, h) for h in ("left", "right")]
        elif o.get("over"):
            units = [(slug(it["name"]), it, None) for it in slot_items(scene, o["over"])]
        else:
            units = [(None, None, None)]
        for key, item, half in units:
            qid = f"{oid}__{key}" if key else oid
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
            questions[qid] = q
            qmeta[qid] = {"obs": oid, "item_key": key, "item": item}
            if item is not None:
                names[slug(item["name"])] = item["name"]
            if subject and "subject" in o.get("needs", []):
                names[slug(subject["name"])] = subject["name"]
    if subject and any(questions[q]["type"] == "choice" for q in questions):
        names.setdefault(slug(subject["name"]), subject["name"])

    gates = {}
    for key, name in names.items():
        gid = f"present__{key}"
        questions[gid] = {
            "type": "noul",
            "instructions": f"Does `scene` contain {name}?",
            "criteria": {"true": f"{name[0].upper() + name[1:]} can be found in the image",
                         "false": f"Nothing in the image matches {name}"},
        }
        gates[key] = gid
    return questions, qmeta, gates


# =============================== 判定 ===============================
def verdict_of(p: float, cfg: dict, soft: bool) -> str:
    t = cfg["thresholds"]
    v = "合格" if p >= t["pass_at"] else "不合格" if p <= t["fail_at"] else "存疑"
    if soft and v == "不合格":
        v = "需优化"
    return v


def good_prob(check: dict, o: dict, ans: dict, meta: dict, ctx: dict, cfg: dict):
    """返回好的方向的概率；None 表示只描述、不判定。"""
    if o["type"] == "noul":
        p = ans["noul"]
        return p if check["good"] else 1 - p
    probs = ans["probabilities"]
    if "good_option_slot" in check:
        target = slot_items(ctx["scene"], check["good_option_slot"])
        return probs.get(slug(target[0]["name"]), 0.0) if target else None
    if "good_options" in check:
        return sum(probs.get(k, 0.0) for k in check["good_options"])
    if "match_brief" in check:
        want = ctx["brief"].get(check["match_brief"])
        if not want:
            return None
        return probs.get(cfg["dominant_form_map"].get(want, want), 0.0)
    if "match_item" in check:
        want = (meta["item"] or {}).get(check["match_item"])
        return probs.get(want, 0.0) if want else None
    return None


def judge(clauses, obs, answers, qmeta, gates, ctx, cfg, dims):
    subject = ctx["scene"].get("subject")
    gate_at = cfg["gate"]

    def gated_ok(meta):
        keys = []
        if meta["item"] is not None:
            keys.append(meta["item_key"])
        if subject and "subject" in obs[meta["obs"]].get("needs", []):
            keys.append(slug(subject["name"]))
        for k in keys:
            gid = gates.get(k)
            if gid and answers[gid]["noul"] < gate_at:
                return False, f"{gid}={answers[gid]['noul']:.2f}"
        return True, ""

    results = {}
    for cid, c in clauses.items():
        if cid[0] not in dims:
            continue
        r = {"title": c["title"], "same_as": c.get("same_as"), "note": c.get("note", ""), "checks": []}
        if not all_conditions(c.get("applies_if"), ctx):
            r["verdict"] = "不适用"
            results[cid] = r
            continue
        cvs = []
        for ch in c["checks"]:
            if not all_conditions(ch.get("applies_if"), ctx):
                continue
            o = obs[ch["obs"]]
            items = []
            for qid, meta in qmeta.items():
                if meta["obs"] != ch["obs"]:
                    continue
                ok, why = gated_ok(meta)
                a = answers[qid]
                p = good_prob(ch, o, a, meta, ctx, cfg) if ok else None
                items.append({
                    "qid": qid, "item": meta["item_key"], "question": QUESTIONS_SENT[qid]["instructions"],
                    "answer": a.get("noul", a.get("choice")),
                    "probabilities": a.get("probabilities"),
                    "p_good": None if p is None else round(p, 3),
                    "gated": None if ok else why,
                })
            scored = [it for it in items if it["p_good"] is not None]
            if not items or all(it["gated"] for it in items):
                v, p = "无法判断", None
            elif not scored:
                v, p = "描述", None
            else:
                ps = [it["p_good"] for it in scored]
                p = max(ps) if ch.get("aggregate") == "best" else min(ps)
                v = verdict_of(p, cfg, ch.get("soft", False))
            for it in scored:
                it["verdict"] = verdict_of(it["p_good"], cfg, ch.get("soft", False))
            r["checks"].append({"obs": ch["obs"], "rule": {k: v2 for k, v2 in ch.items() if k not in ("obs", "applies_if")},
                                "verdict": v, "p_good": None if p is None else round(p, 3), "items": items})
            cvs.append(v)
        graded = [v for v in cvs if v in SEVERITY]
        if not cvs:
            r["verdict"] = "不适用"
        elif graded:
            r["verdict"] = max(graded, key=SEVERITY.get)
        elif all(v == "描述" for v in cvs):
            r["verdict"] = "描述"
        else:
            r["verdict"] = "无法判断"
        results[cid] = r
    return results


def dimension_summary(results: dict) -> dict:
    out = {}
    for cid, r in results.items():
        out.setdefault(cid[0], []).append(r["verdict"])
    summ = {}
    for d, vs in out.items():
        counts = {k: vs.count(k) for k in ("合格", "需优化", "存疑", "不合格", "不适用", "无法判断", "描述") if vs.count(k)}
        if "不合格" in vs:
            overall = "不合格"
        elif "需优化" in vs or "存疑" in vs:
            overall = "需优化" + (f"（{vs.count('存疑')} 项存疑待复核）" if "存疑" in vs else "")
        else:
            overall = "合格"
        summ[d] = {"overall": overall, "counts": counts}
    return summ


# =============================== 输出 ===============================
def fmt_evidence(ch: dict) -> str:
    parts = []
    for it in ch["items"]:
        tag = f"{ch['obs']}" + (f"[{it['item']}]" if it["item"] else "")
        if it["gated"]:
            parts.append(f"{tag}: 元素核对未通过({it['gated']})")
        elif it["p_good"] is None:
            parts.append(f"{tag}: {it['answer']}（仅描述）")
        else:
            parts.append(f"{tag}: 好的方向 {it['p_good']:.2f}")
    return "；".join(parts)


def write_report(out: Path, case_id, results, summ, std, cfg, usage, model, brief, scene, image_path):
    cost = usage["input_tokens"] * PRICE_PER_MTOK / 1e6
    L = [f"# 评审报告 {case_id}", "",
         f"- 图片：`{image_path}`",
         f"- 模型：{model}；输入 {usage['input_tokens']} token，约 ${cost:.5f}",
         f"- 判定阈值：好的方向 ≥ {cfg['thresholds']['pass_at']} 合格，≤ {cfg['thresholds']['fail_at']} 不合格，中间为存疑；soft 检查最差判“需优化”",
         ""]
    for d, s in summ.items():
        L.append(f"**{cfg['standards'][d]['name']}：{s['overall']}**　" + "，".join(f"{k} {v}" for k, v in s["counts"].items()))
    L.append("")
    for d in summ:
        L += [f"## {cfg['standards'][d]['name']}", "", "| 条款 | 判定 | 依据（Jev 概率） |", "|---|---|---|"]
        for cid, r in results.items():
            if cid[0] != d:
                continue
            ev = " / ".join(fmt_evidence(ch) for ch in r["checks"]) or "—"
            same = f"（与 {r['same_as']} 同源）" if r.get("same_as") else ""
            L.append(f"| {cid} {r['title']}{same} | {r['verdict']} | {ev} |")
        L.append("")
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")

    # ---------- 大模型交接包 ----------
    issues = {}
    for cid, r in results.items():
        for ch in r["checks"]:
            if ch["verdict"] not in ("不合格", "需优化", "存疑"):
                continue
            scored = [it for it in ch["items"] if it.get("p_good") is not None]
            if ch["rule"].get("aggregate") == "best" and scored:
                # “至少一个好即可”：问题在于最好的那个也不够好，只报告它
                bad_items = [max(scored, key=lambda it: it["p_good"])]
            else:
                bad_items = [it for it in ch["items"] if it.get("verdict") in ("不合格", "需优化", "存疑")] or ch["items"]
            for it in bad_items:
                key = (ch["obs"], it["item"])
                v = ch["verdict"] if ch["rule"].get("aggregate") == "best" else it.get("verdict", ch["verdict"])
                g = issues.setdefault(key, {"clauses": [], "item": it, "verdict": v})
                if cid not in g["clauses"]:
                    g["clauses"].append(cid)
    order = sorted(issues.items(), key=lambda kv: -SEVERITY.get(kv[1]["verdict"], 0))

    H = [f"# 大模型交接包 {case_id}", "",
         "你是评图专家。下面是 Jev 按评审标准逐项观察的结果。请完成：",
         "1. 查看原图，对“存疑”项给出你的判断，并说明理由。",
         "2. 把同一原因造成的问题合并（同一观察问题被多条条款引用时已自动归组），不要重复扣分。",
         "3. 对“不适用/无法判断/描述”项和条款备注中“需大模型补判”的部分，结合项目说明补充判断。",
         "4. 按对表达的影响排序，列出最重要的 1—3 项修改：对象、动作、期望效果，参照各条款的“不合格时”。",
         "5. 如果你认为 Jev 的某个结论有误，明确指出并说明依据，不要静默推翻。",
         "",
         f"原图：`{image_path}`", "",
         "## 项目说明", "```json", json.dumps(brief, ensure_ascii=False, indent=2), "```",
         "## 场景解析", "```json", json.dumps(scene, ensure_ascii=False, indent=2), "```",
         "## 各维度结论", ""]
    for d, s in summ.items():
        H.append(f"- {cfg['standards'][d]['name']}：{s['overall']}（{'，'.join(f'{k} {v}' for k, v in s['counts'].items())}）")
    H += ["", "## 待处理问题（按严重程度，已按原因归组）", ""]
    for i, ((oid, item), g) in enumerate(order, 1):
        it = g["item"]
        H.append(f"### 问题 {i}：{g['verdict']}　观察 `{oid}`" + (f"　元素 `{item}`" if item else ""))
        H.append(f"- Jev 问题：{it['question']}")
        if it.get("p_good") is not None:
            H.append(f"- 好的方向概率：{it['p_good']:.2f}；原始答案：{it['answer']}" +
                     (f"；各选项：{it['probabilities']}" if it.get("probabilities") else ""))
        for cid in g["clauses"]:
            s = std.get(cid, {})
            H.append(f"- 涉及条款 **{cid} {s.get('title', '')}**")
            H.append(f"  - 标准：{s.get('criterion', '')}")
            H.append(f"  - 不合格时：{s.get('fix', '')}")
        H.append("")
    H += ["## 其余条款状态", ""]
    for cid, r in results.items():
        if r["verdict"] in ("不适用", "无法判断", "描述") or r.get("note"):
            H.append(f"- {cid} {r['title']}：{r['verdict']}" + (f"。编译备注：{r['note']}" if r.get("note") else ""))
    (out / "llm_handoff.md").write_text("\n".join(H), encoding="utf-8")


# =============================== 主流程 ===============================
QUESTIONS_SENT: dict = {}


def read_user_env(name: str) -> str | None:
    """Windows 下进程未继承新写入的用户环境变量时，直接从注册表读取。"""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    obs, clauses = load_bank(cfg)
    std = load_standards(cfg)
    cases = {c["id"]: c for c in load_yaml(ROOT / "cases" / "cases.yaml")["cases"]}
    case = cases.get(args.case_id) or sys.exit(f"cases.yaml 中没有 {args.case_id}")
    cdir = ROOT / "cases" / args.case_id
    brief = load_yaml(cdir / "brief.yaml")
    scene = json.loads((cdir / "scene.json").read_text(encoding="utf-8"))
    ctx = {"brief": brief, "scene": scene}
    seen = {}
    for s in cfg["slots"]["single"] + cfg["slots"]["lists"]:
        for it in slot_items(scene, s):
            k = slug(it["name"])
            if k in seen and seen[k] != it["name"]:
                sys.exit(f"scene.json 中两个元素名称过于相似（ID 冲突 {k}）：'{seen[k]}' / '{it['name']}'")
            seen[k] = it["name"]
    dims = set(brief.get("dimensions") or cfg["standards"].keys())
    image_path = (ROOT / "cases" / case["file"]).resolve()

    # 路由：适用条款 -> 需要的观察问题
    needed = set()
    for cid, c in clauses.items():
        if cid[0] in dims and all_conditions(c.get("applies_if"), ctx):
            for ch in c["checks"]:
                if all_conditions(ch.get("applies_if"), ctx):
                    needed.add(ch["obs"])

    imgs = prepare_images(image_path, cfg)
    tag = uuid.uuid4().hex[:8]
    refs = {k: f"{tag}-{k}" for k in imgs}
    questions, qmeta, gates = build_questions(needed, obs, scene, refs)
    QUESTIONS_SENT.update(questions)

    used = {"scene"} | {k for k in ("thumb", "left", "right") if any(refs[k] in q["instructions"] for q in questions.values())}
    request = {
        "model": cfg["model"],
        "state": {"scene": refs["scene"]},
        "assets": {refs[k]: {"type": "image", "part": f"img-{k}"} for k in used},
        "questions": questions,
    }
    out = ROOT / "results" / args.case_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "request.json").write_text(json.dumps(
        {"request": request, "images": {k: list(imgs[k].size) for k in used}}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"适用条款覆盖观察问题 {len(needed)} 个 → 展开后 {len(questions) - len(gates)} 个问题 + {len(gates)} 个元素核对；图片 {sorted(used)}")
    if args.dry_run:
        print(f"[dry-run] 请求已写入 {out / 'request.json'}")
        return

    key = os.environ.get("TYPESAFE_API_KEY") or read_user_env("TYPESAFE_API_KEY") or sys.exit("缺少环境变量 TYPESAFE_API_KEY")
    files = {"request": (None, json.dumps(request), "application/json")}
    for k in used:
        files[f"img-{k}"] = (f"{k}.jpg", _jpeg(imgs[k]), "image/jpeg")
    resp = requests.post(cfg["api"], files=files, timeout=300,
                         headers={"Authorization": f"Bearer {key}", "TypeSafe-Danger-Zone-Images": "true"})
    if resp.status_code != 200:
        sys.exit(f"Jev 请求失败 HTTP {resp.status_code}: {resp.text[:2000]}")
    data = resp.json()
    (out / "response.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    results = judge(clauses, obs, data["answers"], qmeta, gates, ctx, cfg, dims)
    summ = dimension_summary(results)
    (out / "verdicts.json").write_text(json.dumps(
        {"case": args.case_id, "model": data["model"], "usage": data["usage"], "summary": summ, "clauses": results},
        ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, args.case_id, results, summ, std, cfg, data["usage"], data["model"], brief, scene, image_path)

    print(f"模型 {data['model']}，输入 {data['usage']['input_tokens']} token")
    for gk, gid in gates.items():
        print(f"  元素核对 {gk}: {data['answers'][gid]['noul']:.2f}")
    for d, s in summ.items():
        print(f"{cfg['standards'][d]['name']}：{s['overall']}  {s['counts']}")
    for cid, r in results.items():
        print(f"  {cid} {r['verdict']:<4} {r['title']}")
    print(f"输出：{out}")


if __name__ == "__main__":
    main()
