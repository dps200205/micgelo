"""把各步骤串成完整流程：第 1 步（大模型检索与解析）→ 第 2、3 步（Jev + 判定）→ 第 4 步（大模型复核）。
同时提供知识块生成（读取 skills/kb-builder 作为上下文）。供 Web 工具调用。
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

from finalize import apply_review, validate_review
from kb import (CARD_SECTIONS, ROOT, iter_nodes, kb_root, load_block, load_blocks, load_config, load_yaml, parse_index_table,
                scan, slug)
from lint_kb import lint_block
from llm import LLM, LLMError
from route import check_routing, short
from run_review import ReviewError, run_case

PROMPTS = ROOT / "prompts"
SKILL_DIR = ROOT / "skills" / "kb-builder"
STD_LIST_SLOTS = ("repeated_groups", "guiding_lines", "large_areas", "dense_regions", "point_groups")
TARGET_READ = {"separate_items", "one_continuous_path", "one_filled_area"}
TEXT_EXT = {".md", ".yaml", ".yml", ".txt", ".json", ".py"}


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


# ============================== 第 1 步 ==============================
def kb_outline(root: Path) -> str:
    """知识库目录摘要：可用节点带卡片摘要，待建设节点只有路径。"""
    lines = []
    for n in iter_nodes(scan(root)):
        if n.rel == ".":
            continue
        head = f"- {n.rel} [{n.level}|{n.kb}|{n.status}" + (f"|id={n.id}" if n.id else "") + "]"
        lines.append(head)
        if n.status != "待建设":
            for s in ("一句话定位", "什么时候评", "什么时候不评"):
                if n.sections.get(s):
                    lines.append(f"    {s}：{short(n.sections[s], 220)}")
    return "\n".join(lines)


def _extra_slots(blocks: dict, ids: list) -> list[str]:
    out = []
    for bid in ids:
        out += (blocks[bid].q.get("slots") or {}).get("lists") or []
    return sorted(set(out))


def normalize_scene(scene: dict, slots: list[str]) -> dict:
    def fix_name(name: str) -> str:
        name = (name or "").strip()
        return name if re.match(r"^(the|a|an)\s", name, re.I) else f"the {name}"

    out = {}
    subj = scene.get("subject")
    out["subject"] = {**subj, "name": fix_name(subj["name"])} if isinstance(subj, dict) and subj.get("name") else None
    for s in slots:
        items = []
        for it in scene.get(s) or []:
            if isinstance(it, dict) and it.get("name"):
                it = {**it, "name": fix_name(it["name"])}
                if s == "repeated_groups" and it.get("target_read") not in TARGET_READ:
                    it["target_read"] = None
                items.append(it)
        out[s] = items
    return out


def scene_errors(scene: dict) -> list[str]:
    errs, seen = [], {}
    all_items = ([scene["subject"]] if scene.get("subject") else []) + [i for k, v in scene.items() if isinstance(v, list) for i in v]
    for it in all_items:
        k = slug(it["name"])
        if k in seen and seen[k] != it["name"]:
            errs.append(f"场景元素名称过于相似，请改得更有区别：'{seen[k]}' / '{it['name']}'")
        seen[k] = it["name"]
    return errs


def _dedupe_paths(items: list) -> list:
    """去掉被子路径覆盖的上级文件夹，只保留最具体的节点。"""
    paths = [m["path"] for m in items]
    return [m for m in items if not any(p != m["path"] and p.startswith(m["path"] + "/") for p in paths)]


def step1(run_dir: Path, user_input: str, hints: dict, llm: LLM, cfg: dict, log) -> dict:
    root = kb_root(cfg)
    image = run_dir / "image.jpg"
    blocks = load_blocks(root)
    usable = {b.id for b in blocks.values() if b.usable}
    if not usable:
        raise ReviewError("知识库中没有状态为“可用”的知识块，请先建设知识库")
    tree_paths = {n.rel for n in iter_nodes(scan(root))}

    # ---------- 1a：理解图片、选知识块 ----------
    def check_a(o):
        errs = []
        if not isinstance(o.get("brief"), dict):
            errs.append("缺少 brief")
        for b in o.get("blocks") or []:
            if b.get("id") not in usable:
                errs.append(f"blocks 中的 {b.get('id')} 不是可用知识块，可用的有 {sorted(usable)}；待建设的请写进 missing_knowledge")
        if not o.get("blocks"):
            errs.append("blocks 为空：请至少选择一个适用的可用知识块")
        return errs

    labels = {"subject": "主体或焦点", "view_size": "最终观看尺寸", "dominant_form_target": "预期主导形式", "balance_target": "多类平衡目标"}
    hint_text = "".join(f"\n{labels.get(k, k)}：{v}" for k, v in hints.items() if v)
    log("读取知识库目录，判断图类型和适用的知识块")
    a = llm.chat_json(prompt("tool_step1a_select_blocks.md"),
                      f"用户说明：{user_input or '（未填写）'}{hint_text}\n\n知识库目录：\n{kb_outline(root)}",
                      images=[image], validate=check_a, log=log)
    ids = [b["id"] for b in a["blocks"]]
    log(f"图类型：{a.get('image_type') or '未匹配到项目节点'}；选中知识块：{', '.join(ids)}")

    # ---------- 1b：选条目、场景解析 ----------
    slots = list(STD_LIST_SLOTS) + _extra_slots(blocks, ids)
    detail = []
    for bid in ids:
        b = blocks[bid]
        detail.append(f"### 知识块 {bid}（{b.name}，{b.kb}）\n\n" + "\n\n".join(
            f"#### {s}\n{b.node.sections.get(s, '（无）')}" for s in ("需要的信息", "与其他知识块的关系", "条目索引")))
    extra_txt = _extra_slots(blocks, ids)

    def check_b(o):
        errs = []
        got = {it.get("id"): it for it in o.get("blocks") or []}
        for bid in ids:
            if bid not in got:
                errs.append(f"blocks 缺少知识块 {bid}")
                continue
            idx = set(parse_index_table(blocks[bid].node.sections.get("条目索引")))
            miss = idx - set(got[bid].get("clauses") or []) - set(got[bid].get("skipped") or {})
            if miss:
                errs.append(f"{bid} 的条目 {sorted(miss)} 既没有选中也没有说明跳过原因")
            bad = set(got[bid].get("clauses") or []) - set(blocks[bid].clauses)
            if bad:
                errs.append(f"{bid} 中不存在条目 {sorted(bad)}")
        if not isinstance(o.get("scene"), dict):
            errs.append("缺少 scene")
        else:
            errs += scene_errors(normalize_scene(o["scene"], slots))
        return errs

    log("读取条目索引，选择条目并解析画面元素")
    b_out = llm.chat_json(prompt("tool_step1b_clauses_scene.md"),
                          f"用户说明：{user_input or '（未填写）'}{hint_text}\n\n项目说明：\n{json.dumps(a['brief'], ensure_ascii=False)}\n\n"
                          f"额外槽位：{extra_txt or '无'}\n\n" + "\n\n".join(detail),
                          images=[image], validate=check_b, log=log)

    scene = normalize_scene(b_out["scene"], slots)
    reasons = {b["id"]: b.get("reason") for b in a["blocks"]}
    routing = {
        "image_type": a.get("image_type"),
        "blocks": [{"id": it["id"], "path": blocks[it["id"]].node.rel,
                    "reason": it.get("reason") or reasons.get(it["id"]),
                    "clauses": it.get("clauses") or [], "skipped": it.get("skipped") or {}}
                   for it in b_out["blocks"] if it.get("id") in usable],
        "skipped_blocks": [m for m in a.get("skipped_blocks") or [] if m.get("path")],
        "missing_knowledge": _dedupe_paths([m for m in a.get("missing_knowledge") or [] if m.get("path") in tree_paths]),
        "extra": b_out.get("extra") or None,
    }
    errs, warns = check_routing(cfg, root, routing, run_dir)
    if errs:
        if routing["extra"]:   # 用户补充问题不合规时丢弃它，不让整次评审失败
            log("用户补充问题未通过检查，已忽略：" + errs[0])
            routing["extra"] = None
            errs, warns = check_routing(cfg, root, routing, run_dir)
        if errs:
            raise ReviewError("检索结果未通过检查：" + "；".join(errs[:5]))
    for w in warns:
        log("提示：" + w)

    brief = {"image": "image.jpg", "user_input": user_input, "image_understanding": a.get("image_understanding"),
             "image_type": a.get("image_type"), **a["brief"]}
    brief["assumptions"] = list(brief.get("assumptions") or [])
    # 意图字段只接受用户给出的值：大模型的推测不进入判定，只记录为推断
    for key, empty, label in (("dominant_form_target", None, "预期主导形式"), ("balance_target", "none", "多类平衡目标")):
        guess = brief.get(key)
        brief[key] = hints.get(key) or empty
        if guess not in (None, "", "null", empty) and guess != brief[key]:
            brief["assumptions"].append(f"大模型推测{label}为 {guess}，用户未指定，未用于判定")
    if hints.get("subject"):
        brief["subject_hint"] = hints["subject"]
    elif scene.get("subject"):
        brief["assumptions"].append(f"主体（{scene['subject']['name']}）由大模型推断。焦点相关条目受它影响较大，同一张图换一个主体可能得出不同结论；建议在“主体或焦点”中指定")
    if hints.get("view_size"):
        brief["view_size"] = hints["view_size"]
    (run_dir / "brief.yaml").write_text(yaml.safe_dump(brief, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (run_dir / "routing.yaml").write_text(yaml.safe_dump(routing, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (run_dir / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    n = sum(len(b["clauses"]) for b in routing["blocks"])
    log(f"选中 {n} 条条目；缺少知识 {len(routing['missing_knowledge'])} 处")
    return {"brief": brief, "routing": routing, "scene": scene}


# ============================== 第 4 步 ==============================
def step4(run_dir: Path, llm: LLM, cfg: dict, log) -> dict:
    v = json.loads((run_dir / "verdicts.json").read_text(encoding="utf-8"))
    pending = [f"{bid}.{cid}" for bid, b in v["blocks"].items() for cid, c in b["clauses"].items() if c["verdict"] == "存疑"]
    bad = [f"{bid}.{cid}" for bid, b in v["blocks"].items() for cid, c in b["clauses"].items() if c["verdict"] == "不合格"]
    handoff = (run_dir / "llm_handoff.md").read_text(encoding="utf-8")
    examples = re.findall(r"案例图（.+?）：`(.+?)`", handoff)[:6]

    def check(o):
        return validate_review(v, o)

    log(f"大模型复核：存疑 {len(pending)} 条，不合格 {len(bad)} 条")
    text = (f"待复核条目（resolutions 必须覆盖）：{pending or '无'}\n初判不合格条目：{bad or '无'}\n\n"
            f"以下是交接包。其中提到的文件和命令可以忽略，直接输出 JSON。\n\n{handoff}")
    if examples:
        text = f"图片顺序：第 1 张为待评原图，其后为知识库中的案例图（见交接包说明）。\n\n{text}"
    rv = llm.chat_json(prompt("tool_step4_review.md"), text, images=[run_dir / "image.jpg", *examples],
                       thinking=True, validate=check, log=log)
    rv["reviewer"] = llm.label
    (run_dir / "llm_review.yaml").write_text(yaml.safe_dump(rv, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return apply_review(run_dir, rv, cfg)


# ============================== 知识块生成 ==============================
def skill_context(limit: int = 150_000) -> str:
    """读取 skill 的 SKILL.md 和 references/ 下全部文本，作为生成时的上下文。替换 skill 后自动生效。"""
    if not (SKILL_DIR / "SKILL.md").exists():
        raise ReviewError("未找到知识库生成 skill：请在“知识库生成”页面上传")
    parts = [("SKILL.md", (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))]
    ref = SKILL_DIR / "references"
    if ref.exists():
        for p in sorted(ref.rglob("*")):
            if p.is_file() and p.suffix.lower() in TEXT_EXT:
                parts.append((p.relative_to(SKILL_DIR).as_posix(), p.read_text(encoding="utf-8")))
    out, total = [], 0
    for name, txt in parts:
        if total + len(txt) > limit:
            out.append(f"（{name} 及之后的文件因长度限制未载入）")
            break
        out.append(f"===== {name} =====\n{txt}")
        total += len(txt)
    return "\n\n".join(out)


GEN_CONTRACT = """
你现在由评审工具调用，无法运行脚本或读写文件。请直接输出下面的 JSON（只输出 JSON），由工具写入文件并运行检查：
{
  "block_id": "小写英文ID，全库唯一",
  "folder_name": "知识块文件夹名，如 场景概念设计中的大中小",
  "card_filename": "！什么时候评审<名称>.md",
  "standard_filename": "01<名称>的评审标准.md",
  "card": "知识块卡片全文（含 YAML 头信息，status 写 草稿）",
  "standard": "评审标准全文（含 YAML 头信息）",
  "questions": "questions.yaml 全文",
  "cases": "cases.yaml 全文，没有图片时写 images: []",
  "review_notes": ["需要人工确认的内容，例如推断、依据不足、资料矛盾之处"]
}
系统内置的场景元素槽位只有这些：单值 subject；列表 repeated_groups（成组重复元素）、guiding_lines（引导线）、large_areas（大块面）、dense_regions（密区）、point_groups（点状元素群）。
over、needs、options_from 优先使用它们，例如“需要成组的元素”用 repeated_groups。只有确实需要新元素类型（如包点）时，才在 questions 的 slots.lists 中声明新槽位。
条件和判定可用的 brief 字段及取值只有这些，不要自创：
goal：hierarchy（有主次）、uniform_pattern（均匀纹样）、minimal（极简）、equal_display（均等展示）、balanced_groups（多组平衡）
dominant_form_target：point、line、area、mixed
balance_target：none、point_line、point_area、line_area、all_three
要求：卡片头信息的 standard 字段与 standard_filename 一致；questions 的 source_version 与评审标准 version 一致；观察问题和 criteria 只能用英文，且不能写某一张图的具体内容。
资料中没有依据的内容不要编造，写进 review_notes。
""".strip()


def existing_questions(blocks: dict) -> str:
    rows = []
    for b in blocks.values():
        for oid, o in b.observations.items():
            rows.append(f"- {b.id}.{oid}: {o.get('q')}")
    return "\n".join(rows)


def _write_block(folder: Path, g: dict, images: list[tuple[str, bytes]]):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "images").mkdir(exist_ok=True)
    for p in folder.iterdir():   # 修复重写时清掉上一轮的文件
        if p.is_file():
            p.unlink()
    card = re.sub(r"(?m)^status:.*$", "status: 草稿", g["card"], count=1)
    (folder / g["card_filename"]).write_text(card, encoding="utf-8")
    (folder / g["standard_filename"]).write_text(g["standard"], encoding="utf-8")
    (folder / "questions.yaml").write_text(g["questions"], encoding="utf-8")
    (folder / "cases.yaml").write_text(g.get("cases") or "images: []\n", encoding="utf-8")
    for name, data in images:
        (folder / "images" / name).write_bytes(data)


def generate_block(parent_rel: str, name: str, materials: str, images: list[tuple[str, bytes]], llm: LLM, cfg: dict, log) -> dict:
    root = kb_root(cfg)
    parent = (root / parent_rel).resolve()
    if not str(parent).startswith(str(root)) or not parent.is_dir():
        raise ReviewError("目标文件夹不存在")
    tree = scan(root)
    pnode = next((n for n in iter_nodes(tree) if n.path == parent), None)
    if pnode is None:
        raise ReviewError("目标文件夹不在知识库中")
    kb_type = pnode.kb or "basic"
    blocks = load_blocks(root)
    used_ids = sorted(blocks)
    image_names = [n for n, _ in images]

    text = (f"目标位置：{parent_rel}（所属库 kb: {kb_type}）\n知识块名称：{name or '由你根据资料决定'}\n"
            f"已占用的知识块 ID：{used_ids}\n\n已有观察问题（有同义问题时原样复用文本）：\n{existing_questions(blocks)}\n\n"
            f"随资料提供的图片文件（已按此顺序附在消息中，保存在 images/ 下）：{image_names or '无'}\n\n资料正文：\n{materials}")

    tmp_holder = {}

    def check(o):
        for k in ("block_id", "folder_name", "card_filename", "standard_filename", "card", "standard", "questions"):
            if not o.get(k):
                return [f"缺少字段 {k}"]
        if o["block_id"] in used_ids:
            return [f"block_id {o['block_id']} 已被占用"]
        if not re.fullmatch(r"[^\\/:*?\"<>|]+", o["folder_name"]) or o["folder_name"].startswith((".", "_")):
            return ["folder_name 不合法"]
        if not o["card_filename"].startswith(("！", "!")):
            return ["card_filename 必须以 ！ 开头"]
        folder = parent / o["folder_name"]
        if folder.exists() and tmp_holder.get("folder") != folder:
            return [f"文件夹 {o['folder_name']} 已存在，请换一个名称"]
        try:
            yaml.safe_load(o["questions"])
            yaml.safe_load(o.get("cases") or "")
        except yaml.YAMLError as e:
            return [f"YAML 无法解析：{e}"]
        old = tmp_holder.get("folder")
        if old and old != folder:   # 修复时模型改了文件夹名：清掉上一轮自己生成的草稿
            shutil.rmtree(old, ignore_errors=True)
        _write_block(folder, o, images)
        tmp_holder["folder"] = folder
        node = next((n for n in iter_nodes(scan(root)) if n.path == folder), None)
        if node is None or node.level != "block":
            return ["卡片头信息应写 level: block"]
        b = load_block(node)
        # 状态被强制为草稿；为了让检查覆盖全部内容，这里按“可用”的严格程度检查
        errs, warns = lint_block(b, cfg)
        for sec in CARD_SECTIONS["block"]:
            if not node.sections.get(sec):
                errs.append(f"卡片缺少小节“{sec}”")
        tmp_holder.update(warnings=warns)
        return errs

    log("读取 skill 与样板，开始生成知识块")
    try:
        g = llm.chat_json(skill_context() + "\n\n" + GEN_CONTRACT, text, images=[_img_tmp(images, i) for i in range(len(images))] or None,
                          thinking=True, validate=check, repairs=3, log=log)
    except LLMError:
        if tmp_holder.get("folder"):
            log("生成结果未通过检查，草稿已保留，可在知识库页面查看和修改")
        raise
    finally:
        _clean_img_tmp()
    folder = tmp_holder["folder"]
    (folder / "_生成说明.md").write_text("# 生成说明（需人工审核）\n\n" + "\n".join(f"- {x}" for x in g.get("review_notes") or ["无"]) + "\n", encoding="utf-8")
    log(f"已生成草稿：{folder.relative_to(root).as_posix()}")
    return {"path": folder.relative_to(root).as_posix(), "block_id": g["block_id"], "review_notes": g.get("review_notes") or [],
            "warnings": tmp_holder.get("warnings") or []}


_IMG_TMP = ROOT / "data" / "_gen_tmp"


def _img_tmp(images, i) -> Path:
    _IMG_TMP.mkdir(parents=True, exist_ok=True)
    p = _IMG_TMP / f"{i}{Path(images[i][0]).suffix}"
    p.write_bytes(images[i][1])
    return p


def _clean_img_tmp():
    shutil.rmtree(_IMG_TMP, ignore_errors=True)
