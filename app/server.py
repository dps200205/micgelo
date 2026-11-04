"""CFM 场景概念设计评审工具：本地 Web 服务（只监听 127.0.0.1）。

    python app/server.py [--port 8765] [--no-browser]

依赖：requests、pillow、pyyaml。界面在 app/static/。
API Key 保存在 data/settings.json，不会通过接口返回明文。
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import mimetypes
import re
import shutil
import sys
import threading
import time
import traceback
import uuid
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
import yaml
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import pipeline  # noqa: E402
from kb import (ROOT, iter_nodes, kb_root, load_block, load_blocks, load_config, load_yaml, scan,  # noqa: E402
                split_frontmatter)
from lint_kb import lint_all, lint_block  # noqa: E402
from llm import LLM, LLMError  # noqa: E402
from run_review import ReviewError, jev_key_default, run_case  # noqa: E402
from finalize import apply_review  # noqa: E402,F401

STATIC = Path(__file__).resolve().parent / "static"
DATA = BASE / "data"
RUNS = BASE / "runs"
TRASH = DATA / "trash"
SETTINGS = DATA / "settings.json"
SKILL = BASE / "skills" / "kb-builder"
SKILL_DEFAULT = BASE / "skills" / "_kb-builder_default"
MAX_BODY = 300 * 1024 * 1024
TEXT_EXT = {".md", ".yaml", ".yml", ".txt", ".json", ".py"}
UPLOAD_EXT = {".md", ".yaml", ".yml", ".txt", ".json", ".png", ".jpg", ".jpeg"}
IMG_EXT = {".png", ".jpg", ".jpeg"}
RUN_FILES = {"final_report.md", "report.md", "final.json", "verdicts.json", "llm_handoff.md", "brief.yaml", "routing.yaml", "scene.json"}
STEPS = ["理解图片与检索知识库", "Jev 逐项观察", "代码判定", "大模型复核", "生成报告"]
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ============================== 设置 ==============================
def load_settings() -> dict:
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    return {"jev_api_key": "", "llm": {"active": None, "providers": {}}}


def save_settings(s: dict):
    DATA.mkdir(exist_ok=True)
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def mask(k: str | None) -> str:
    if not k:
        return ""
    return k[:6] + "…" + k[-4:] if len(k) > 12 else "已填写"


def settings_public() -> dict:
    s = load_settings()
    cfg = load_config()
    providers = {pid: {**{k: v for k, v in p.items() if k != "api_key"}, "api_key_mask": mask(p.get("api_key"))}
                 for pid, p in s["llm"]["providers"].items()}
    env_key = bool(jev_key_default())
    return {"jev_key_mask": mask(s.get("jev_api_key")), "jev_env_fallback": env_key and not s.get("jev_api_key"),
            "llm": {"active": s["llm"].get("active"), "providers": providers},
            "kb_root": str(kb_root(cfg)), "model": cfg.get("model")}


def active_llm() -> LLM:
    s = load_settings()
    p = s["llm"]["providers"].get(s["llm"].get("active") or "")
    if not p:
        raise ApiError("未配置大模型：请在“设置”中填写")
    return LLM(p)


def jev_key() -> str | None:
    return load_settings().get("jev_api_key") or jev_key_default()


def update_settings(b: dict):
    s = load_settings()
    if "jev_api_key" in b and b["jev_api_key"].strip():
        s["jev_api_key"] = b["jev_api_key"].strip()
    if b.get("jev_clear"):
        s["jev_api_key"] = ""
    if b.get("llm_provider"):
        p = b["llm_provider"]
        pid = p.get("id") or re.sub(r"[^a-z0-9_]+", "_", (p.get("model") or "provider").lower())
        cur = s["llm"]["providers"].setdefault(pid, {})
        for k in ("label", "base_url", "model", "thinking_param"):
            if k in p:
                cur[k] = (p[k] or "").strip()
        if (p.get("api_key") or "").strip():
            cur["api_key"] = p["api_key"].strip()
        if b.get("activate", True):
            s["llm"]["active"] = pid
    if b.get("llm_active"):
        if b["llm_active"] not in s["llm"]["providers"]:
            raise ApiError("没有这个大模型配置")
        s["llm"]["active"] = b["llm_active"]
    if b.get("llm_delete"):
        s["llm"]["providers"].pop(b["llm_delete"], None)
        if s["llm"].get("active") == b["llm_delete"]:
            s["llm"]["active"] = next(iter(s["llm"]["providers"]), None)
    if b.get("kb_root"):
        p = Path(b["kb_root"]).expanduser()
        if not p.is_dir():
            raise ApiError(f"文件夹不存在：{p}")
        cfg = load_config()
        cfg["kb_root"] = str(p.resolve())
        save_config(cfg)
    save_settings(s)


def test_key(target: str) -> dict:
    t = time.time()
    if target == "jev":
        k = jev_key()
        if not k:
            raise ApiError("还没有填写 Jev API Key")
        cfg = load_config()
        api = cfg["api"].rsplit("/", 1)[0] + "/models"
        r = requests.get(api, headers={"Authorization": "Bearer " + k}, timeout=30)
        if r.status_code != 200:
            raise ApiError(f"Jev 验证失败 HTTP {r.status_code}" + ("（Key 无效或已失效）" if r.status_code == 401 else ""))
        return {"ok": True, "detail": "可用模型：" + "、".join(m["name"] for m in r.json().get("models", [])), "seconds": round(time.time() - t, 1)}
    llm = active_llm()
    reply = llm.chat([{"role": "user", "content": "只回复两个字：正常"}], timeout=60)
    return {"ok": True, "detail": f"{llm.label} 回复：{reply[:20]}", "seconds": round(time.time() - t, 1)}


# ============================== 判定标准 ==============================
HEADER = "# 评审工具配置。可在界面“判定标准”“设置”中修改，也可直接编辑。\n"
TH_KEYS = {"pass_at", "fail_below", "block_pass_rate", "veto_below", "gate"}


def save_config(cfg: dict):
    (BASE / "config.yaml").write_text(HEADER + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def judging_view() -> dict:
    cfg = load_config()
    blocks = load_blocks(kb_root(cfg))
    return {"judging": cfg["judging"], "blocks": [
        {"id": b.id, "name": b.name, "kb": b.kb, "status": b.status,
         "clauses": [{"id": c, "title": v.get("title")} for c, v in b.clauses.items()]}
        for b in blocks.values() if b.status != "待建设"]}


def _check_th(d: dict, where: str, full: bool = False) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if k not in TH_KEYS:
            raise ApiError(f"{where}：未知字段 {k}")
        if v in (None, ""):
            continue
        try:
            v = float(v)
        except (TypeError, ValueError) as e:
            raise ApiError(f"{where}：{k} 必须是数字") from e
        if not 0 <= v <= 1:
            raise ApiError(f"{where}：{k} 必须在 0 到 1 之间")
        out[k] = round(v, 4)
    if full and set(out) != TH_KEYS:
        raise ApiError(f"{where}：默认规则必须填写全部字段")
    return out


def save_judging(b: dict):
    default = _check_th(b.get("default"), "默认规则", full=True)
    blocks = {k: t for k, v in (b.get("blocks") or {}).items() if (t := _check_th(v, f"知识块 {k}"))}
    clauses = {k: t for k, v in (b.get("clauses") or {}).items() if (t := _check_th(v, f"条目 {k}"))}

    def ok(th, where):
        if th["fail_below"] > th["pass_at"]:
            raise ApiError(f"{where}：不合格线不能高于合格线")
    ok(default, "默认规则")
    for k, v in blocks.items():
        ok({**default, **v}, f"知识块 {k}")
    for k, v in clauses.items():
        bid = k.split(".")[0]
        ok({**default, **blocks.get(bid, {}), **v}, f"条目 {k}")
    cfg = load_config()
    cfg["judging"] = {"default": default, "blocks": blocks, "clauses": clauses}
    save_config(cfg)


# ============================== 知识库文件 ==============================
def kb_path(rel: str, must_exist: bool = True) -> Path:
    root = kb_root(load_config())
    p = (root / (rel or "")).resolve()
    if not p.is_relative_to(root):
        raise ApiError("路径超出知识库范围")
    if must_exist and not p.exists():
        raise ApiError("文件不存在", 404)
    return p


def safe_name(name: str) -> str:
    name = Path(name or "").name.strip()
    if not name or name.startswith(".") or re.search(r'[\\/:*?"<>|]', name):
        raise ApiError(f"名称不合法：{name}")
    return name


def to_trash(p: Path, root: Path):
    dst = TRASH / datetime.now().strftime("%Y%m%d-%H%M%S-%f") / p.relative_to(root)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dst))


def backup_copy(p: Path, root: Path):
    dst = TRASH / datetime.now().strftime("%Y%m%d-%H%M%S-%f") / p.relative_to(root)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst)


def kb_tree() -> dict:
    cfg = load_config()
    root = kb_root(cfg)

    def conv(n):
        return {"name": n.name, "path": "" if n.rel == "." else n.rel, "level": n.level, "kb": n.kb, "status": n.status,
                "id": n.id, "summary": n.sections.get("一句话定位", ""), "children": [conv(c) for c in n.children]}
    return {"root": str(root), "tree": conv(scan(root))}


def kb_dir(rel: str) -> dict:
    p = kb_path(rel)
    if not p.is_dir():
        raise ApiError("不是文件夹")
    files = []
    for f in sorted(p.iterdir(), key=lambda x: (not x.name.startswith(("！", "!")), x.name)):
        if f.is_file():
            files.append({"name": f.name, "path": f.relative_to(kb_root(load_config())).as_posix(), "size": f.stat().st_size,
                          "kind": "image" if f.suffix.lower() in IMG_EXT else "text" if f.suffix.lower() in TEXT_EXT else "other"})
    img = p / "images"
    if img.is_dir():
        for f in sorted(img.iterdir()):
            if f.is_file():
                files.append({"name": "images/" + f.name, "path": f.relative_to(kb_root(load_config())).as_posix(), "size": f.stat().st_size,
                              "kind": "image" if f.suffix.lower() in IMG_EXT else "other"})
    return {"path": rel, "files": files}


def kb_save(b: dict):
    p = kb_path(b["path"], must_exist=False)
    if p.suffix.lower() not in TEXT_EXT:
        raise ApiError("只能编辑文本文件")
    content = b.get("content", "")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ApiError(f"YAML 格式错误：{e}") from e
    if p.exists():
        backup_copy(p, kb_root(load_config()))
    p.write_text(content, encoding="utf-8")


def kb_upload(b: dict) -> dict:
    d = kb_path(b.get("dir", ""))
    saved = []
    for f in b.get("files") or []:
        name = safe_name(f["name"])
        if Path(name).suffix.lower() not in UPLOAD_EXT:
            raise ApiError(f"不支持的文件类型：{name}")
        target_dir = d / "images" if Path(name).suffix.lower() in IMG_EXT and d.joinpath("images").is_dir() else d
        (target_dir / name).write_bytes(base64.b64decode(f["b64"]))
        saved.append(name)
    return {"saved": saved}


def extract_zip(data: bytes, target: Path, allowed: set | None = None) -> int:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        # 编码修正：Windows 压缩工具常用 GBK 写中文文件名
        count = 0
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not info.flag_bits & 0x800:
                try:
                    name = name.encode("cp437").decode("gbk")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass
            dst = (target / name).resolve()
            if not dst.is_relative_to(target.resolve()):
                raise ApiError("压缩包包含非法路径")
            if allowed and dst.suffix.lower() not in allowed:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(z.read(info))
            count += 1
    return count


def kb_mkdir(b: dict) -> dict:
    parent = kb_path(b.get("parent", ""))
    name = safe_name(b.get("name"))
    if name.startswith("_"):
        raise ApiError("以 _ 开头的文件夹不参与检索")
    p = parent / name
    if p.exists():
        raise ApiError("已存在同名文件夹")
    kind = b.get("type", "folder")
    root = kb_root(load_config())
    pnode = next((n for n in iter_nodes(scan(root)) if n.path == parent.resolve()), None)
    kbt = (pnode.kb if pnode else None) or b.get("kb") or "basic"
    title = re.sub(r"^\d+_", "", name).replace("场景概念设计中的", "")
    head = ["---", f"level: {'block' if kind == 'block' else 'folder'}", f"kb: {kbt}"]
    if kind == "block":
        bid = (b.get("id") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", bid):
            raise ApiError("知识块 ID 必须是小写英文、数字或下划线，且以字母开头")
        if bid in load_blocks(root):
            raise ApiError(f"知识块 ID {bid} 已被占用")
        head.append(f"id: {bid}")
    head += ["status: 待建设", "version: 1.0", f"updated: {datetime.now():%Y-%m-%d}"]
    if kind == "block":
        head += ["standard: 待编写", "questions: questions.yaml"]
    head.append("---")
    body = [f"# 什么时候评审{title}", "", "## 一句话定位", "（待补充）", "", "## 什么时候评", "- （待补充）", "", "## 什么时候不评", "- （待补充）", ""]
    if kind == "block":
        body += ["## 需要的信息", "- （待补充）", "", "## 与其他知识块的关系", "- （待补充）", "", "## 条目索引",
                 "| 条目 | 标题 | 何时适用 | 看什么 |", "|---|---|---|---|", ""]
    p.mkdir(parents=True)
    (p / f"！什么时候评审{title}.md").write_text("\n".join(head + body), encoding="utf-8")
    if kind == "block":
        (p / "images").mkdir()
        (p / "cases.yaml").write_text("images: []\n", encoding="utf-8")
    return {"path": p.relative_to(root).as_posix()}


def kb_set_status(b: dict) -> dict:
    p = kb_path(b["path"])
    status = b.get("status")
    if status not in ("可用", "草稿", "待建设"):
        raise ApiError("状态无效")
    cfg = load_config()
    root = kb_root(cfg)
    node = next((n for n in iter_nodes(scan(root)) if n.path == p), None)
    if node is None or node.card_file is None:
        raise ApiError("该文件夹没有卡片文件")
    if status == "可用" and node.level == "block":
        errs, _ = lint_block(load_block(node), cfg)
        for s in ("一句话定位", "什么时候评", "什么时候不评", "需要的信息", "与其他知识块的关系", "条目索引"):
            txt = node.sections.get(s, "")
            if not txt or "待补充" in txt:
                errs.append(f"卡片小节“{s}”未填写")
        if not (p / str(node.meta.get("standard", "待编写"))).is_file():
            errs.append("评审标准文件不存在")
        if errs:
            raise ApiError("未通过检查，不能设为可用：\n" + "\n".join(errs[:15]))
    text = node.card_file.read_text(encoding="utf-8")
    backup_copy(node.card_file, root)
    if re.search(r"(?m)^status:.*$", text):
        text = re.sub(r"(?m)^status:.*$", f"status: {status}", text, count=1)
    else:
        text = text.replace("---\n", f"---\nstatus: {status}\n", 1)
    node.card_file.write_text(text, encoding="utf-8")
    return {"status": status}


# ============================== Skill ==============================
def skill_info() -> dict:
    if not (SKILL / "SKILL.md").exists():
        return {"installed": False, "files": []}
    meta, body = split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
    files = [{"path": p.relative_to(SKILL).as_posix(), "size": p.stat().st_size, "kind": "text" if p.suffix.lower() in TEXT_EXT else "other"}
             for p in sorted(SKILL.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    return {"installed": True, "name": meta.get("name"), "description": meta.get("description"), "files": files,
            "dir": str(SKILL), "has_default": SKILL_DEFAULT.exists()}


def skill_path(rel: str) -> Path:
    p = (SKILL / rel).resolve()
    if not p.is_relative_to(SKILL.resolve()):
        raise ApiError("路径超出 skill 范围")
    return p


def skill_replace(data: bytes):
    tmp = DATA / f"_skill_{uuid.uuid4().hex[:6]}"
    tmp.mkdir(parents=True)
    try:
        extract_zip(data, tmp)
        cands = [p.parent for p in tmp.rglob("SKILL.md")]
        if not cands:
            raise ApiError("压缩包中没有 SKILL.md")
        src = min(cands, key=lambda p: len(p.parts))
        if SKILL.exists():
            dst = TRASH / datetime.now().strftime("skill-%Y%m%d-%H%M%S")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(SKILL), str(dst))
        shutil.copytree(src, SKILL)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def skill_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in SKILL.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, Path("kb-builder") / p.relative_to(SKILL))
    return buf.getvalue()


# ============================== 任务 ==============================
def new_job(kind: str, **extra) -> dict:
    job = {"id": uuid.uuid4().hex[:12], "kind": kind, "status": "running", "step": 0, "logs": [], "error": None, "result": None, **extra}
    with LOCK:
        JOBS[job["id"]] = job
    return job


def job_log(job: dict):
    def log(msg):
        job["logs"].append({"t": datetime.now().strftime("%H:%M:%S"), "msg": str(msg)})
    return log


def write_meta(run_dir: Path, **kw):
    f = run_dir / "meta.json"
    meta = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    meta.update(kw)
    f.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def review_worker(job: dict, run_dir: Path, user_input: str, hints: dict, skip_review: bool):
    log = job_log(job)
    llm = None
    try:
        key = jev_key()
        if not key:
            raise ReviewError("还没有填写 Jev API Key，请先到“设置”中填写")
        llm = active_llm()
        cfg = load_config()
        job["step"] = 0
        pipeline.step1(run_dir, user_input, hints, llm, cfg, log)
        job["step"] = 1
        log("发送给 Jev")
        r = run_case(run_dir, run_dir, jev_key=key, cfg=cfg, log=log)
        job["step"] = 2
        write_meta(run_dir, jev={"model": r["model"], "usage": r["usage"], "cost": r["cost"]},
                   initial={bid: s["verdict"] for bid, s in r["summaries"].items()})
        final = None
        if not skip_review:
            job["step"] = 3
            final = pipeline.step4(run_dir, llm, cfg, log)
        job["step"] = 4
        verdict = {bid: b["final"] for bid, b in final["blocks"].items()} if final else {bid: s["verdict"] for bid, s in r["summaries"].items()}
        write_meta(run_dir, status="done", verdict=verdict, llm={"model": llm.label, **llm.total}, logs=job["logs"], reviewed=bool(final))
        log("评审完成")
        job["status"] = "done"
        job["step"] = len(STEPS)
    except (ReviewError, LLMError, ApiError) as e:
        job["error"] = str(e)
        job["status"] = "error"
        log("失败：" + str(e))
        write_meta(run_dir, status="error", error=str(e), logs=job["logs"], llm={"model": llm.label, **llm.total} if llm else None)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        job["error"] = f"内部错误：{e}"
        job["status"] = "error"
        log("失败：" + job["error"])
        write_meta(run_dir, status="error", error=job["error"], logs=job["logs"])


def start_review(b: dict) -> dict:
    if not b.get("image_b64"):
        raise ApiError("请先选择图片")
    try:
        raw = base64.b64decode(b["image_b64"].split(",")[-1])
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception as e:  # noqa: BLE001
        raise ApiError("无法读取图片，请使用 PNG 或 JPG") from e
    cfg = load_config()
    if min(im.size) < cfg["image"]["min_side"]:
        raise ApiError(f"图片太小：短边 {min(im.size)} 像素，至少需要 {cfg['image']['min_side']} 像素")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True)
    im.save(run_dir / "image.jpg", quality=95)
    user_input = (b.get("user_input") or "").strip()
    write_meta(run_dir, id=run_id, created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename=b.get("filename"),
               user_input=user_input, status="running")
    job = new_job("review", run_id=run_id, steps=STEPS)
    dft, bal = b.get("dominant_form_target") or None, b.get("balance_target") or None
    if dft not in (None, "point", "line", "area", "mixed") or bal not in (None, "none", "point_line", "point_area", "line_area", "all_three"):
        raise ApiError("评审目标参数无效")
    hints = {"subject": (b.get("subject") or "").strip(), "view_size": (b.get("view_size") or "").strip(),
             "dominant_form_target": dft, "balance_target": bal}
    threading.Thread(target=review_worker, args=(job, run_dir, user_input, hints, bool(b.get("skip_review"))), daemon=True).start()
    return {"job_id": job["id"], "run_id": run_id}


def generate_worker(job: dict, parent: str, name: str, materials: str, images: list):
    log = job_log(job)
    try:
        cfg = load_config()
        llm = active_llm()
        job["result"] = pipeline.generate_block(parent, name, materials, images, llm, cfg, log)
        job["result"]["llm"] = {"model": llm.label, **llm.total}
        job["status"] = "done"
    except (ReviewError, LLMError, ApiError) as e:
        job["error"], job["status"] = str(e), "error"
        log("失败：" + str(e))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        job["error"], job["status"] = f"内部错误：{e}", "error"
        log("失败：" + job["error"])


def start_generate(b: dict) -> dict:
    materials = (b.get("materials") or "").strip()
    images = []
    for f in b.get("files") or []:
        name = safe_name(f["name"])
        data = base64.b64decode(f["b64"])
        ext = Path(name).suffix.lower()
        if ext in IMG_EXT:
            images.append((name, data))
        elif ext in (".md", ".txt"):
            materials += f"\n\n===== 文件 {name} =====\n" + data.decode("utf-8", errors="replace")
        else:
            raise ApiError(f"目前只支持 md、txt 文本和 png、jpg 图片：{name}。视频请先转写成文字；Word、PDF 请先转成文本。")
    if not materials and not images:
        raise ApiError("请提供资料：粘贴文字或上传文件")
    job = new_job("generate")
    threading.Thread(target=generate_worker, args=(job, b.get("parent") or "", (b.get("name") or "").strip(), materials, images), daemon=True).start()
    return {"job_id": job["id"]}


# ============================== 评审记录 ==============================
def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_dir_of(run_id: str) -> Path:
    if not re.fullmatch(r"[\w-]+", run_id or ""):
        raise ApiError("记录不存在", 404)
    d = RUNS / run_id
    if not d.is_dir():
        raise ApiError("记录不存在", 404)
    return d


def list_runs() -> list:
    out = []
    if RUNS.exists():
        for d in sorted(RUNS.iterdir(), reverse=True):
            m = read_json(d / "meta.json")
            if m:
                out.append({k: m.get(k) for k in ("id", "created", "user_input", "status", "verdict", "error", "reviewed", "filename")})
    return out


def run_detail(run_id: str) -> dict:
    d = run_dir_of(run_id)
    verdicts = read_json(d / "verdicts_final.json") or read_json(d / "verdicts.json")
    qtext = {}
    for req in ("basic", "project"):
        r = read_json(d / f"request_{req}.json")
        if r:
            for qid, q in r["request"]["questions"].items():
                qtext[qid] = q["instructions"]
    if verdicts:
        for b in verdicts["blocks"].values():
            for c in b["clauses"].values():
                for ch in c.get("checks", []):
                    for it in ch["items"]:
                        it["question"] = qtext.get(it["qid"], "")
    def yml(n):
        return load_yaml(d / n) if (d / n).exists() else None
    return {"meta": read_json(d / "meta.json"), "brief": yml("brief.yaml"), "routing": yml("routing.yaml"), "scene": read_json(d / "scene.json"),
            "verdicts": verdicts, "final": read_json(d / "final.json")}


# ============================== HTTP ==============================
class Handler(BaseHTTPRequestHandler):
    server_version = "CFMReview/1.0"

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", code)

    def _file(self, p: Path, download: str | None = None):
        if not p.is_file():
            raise ApiError("文件不存在", 404)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix.lower() in (".md", ".yaml", ".yml", ".txt"):
            ctype = "text/plain; charset=utf-8"
        hd = {"Content-Disposition": f"attachment; filename*=UTF-8''{requests.utils.quote(download)}"} if download else None
        self._send(p.read_bytes(), ctype, headers=hd)

    def _guard(self) -> bool:
        """只接受本机页面发起的请求，防止其他网站跨站调用本地接口。"""
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            self._json({"error": "forbidden"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc not in allowed:
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    def _handle(self, fn):
        try:
            if not self._guard():
                return
            fn()
        except ApiError as e:
            self._json({"error": str(e)}, e.code)
        except (ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"内部错误：{e}"}, 500)

    def do_GET(self):
        self._handle(self._get)

    def do_POST(self):
        self._handle(self._post)

    def _get(self):
        u = urlparse(self.path)
        path, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
        if path == "/" or path.startswith("/static/"):
            name = "index.html" if path == "/" else path[len("/static/"):]
            p = (STATIC / name).resolve()
            if not p.is_relative_to(STATIC):
                raise ApiError("not found", 404)
            return self._file(p)
        routes = {
            "/api/settings": lambda: settings_public(),
            "/api/judging": lambda: judging_view(),
            "/api/kb/tree": lambda: kb_tree(),
            "/api/kb/lint": lambda: lint_all(load_config(), kb_root(load_config())),
            "/api/runs": lambda: {"runs": list_runs()},
            "/api/skill": lambda: skill_info(),
        }
        if path in routes:
            return self._json(routes[path]())
        if path == "/api/kb/dir":
            return self._json(kb_dir(q.get("path", "")))
        if path == "/api/kb/file":
            p = kb_path(q.get("path", ""))
            if p.suffix.lower() in TEXT_EXT:
                return self._json({"path": q["path"], "content": p.read_text(encoding="utf-8")})
            raise ApiError("不是文本文件")
        if path == "/api/kb/raw":
            return self._file(kb_path(q.get("path", "")))
        if path == "/api/skill/file":
            p = skill_path(q.get("path", ""))
            if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
                raise ApiError("不是文本文件")
            return self._json({"path": q["path"], "content": p.read_text(encoding="utf-8")})
        if path == "/api/skill/download":
            return self._send(skill_zip(), "application/zip", headers={"Content-Disposition": "attachment; filename=kb-builder.zip"})
        m = re.fullmatch(r"/api/jobs/(\w+)", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job:
                raise ApiError("任务不存在（服务可能已重启）", 404)
            return self._json(job)
        m = re.fullmatch(r"/api/runs/([\w-]+)", path)
        if m:
            return self._json(run_detail(m.group(1)))
        m = re.fullmatch(r"/api/runs/([\w-]+)/image", path)
        if m:
            return self._file(run_dir_of(m.group(1)) / "image.jpg")
        m = re.fullmatch(r"/api/runs/([\w-]+)/file", path)
        if m:
            name = q.get("name", "")
            if name not in RUN_FILES:
                raise ApiError("文件不存在", 404)
            return self._file(run_dir_of(m.group(1)) / name, download=q.get("dl") and f"{m.group(1)}_{name}")
        raise ApiError("not found", 404)

    def _post(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ApiError("上传内容过大", 413)
        b = json.loads(self.rfile.read(n) or b"{}")
        path = urlparse(self.path).path
        if path == "/api/settings":
            update_settings(b)
            return self._json(settings_public())
        if path == "/api/settings/test":
            try:
                return self._json(test_key(b.get("target")))
            except (LLMError, requests.RequestException) as e:
                raise ApiError(str(e)) from e
        if path == "/api/judging":
            save_judging(b)
            return self._json(judging_view())
        if path == "/api/review":
            return self._json(start_review(b))
        if path == "/api/generate":
            return self._json(start_generate(b))
        if path == "/api/kb/file":
            kb_save(b)
            return self._json({"ok": True})
        if path == "/api/kb/upload":
            return self._json(kb_upload(b))
        if path == "/api/kb/import_zip":
            n = extract_zip(base64.b64decode(b["b64"]), kb_path(b.get("dir", "")), UPLOAD_EXT)
            return self._json({"count": n})
        if path == "/api/kb/delete":
            root = kb_root(load_config())
            p = kb_path(b["path"])
            if p == root:
                raise ApiError("不能删除知识库根目录")
            to_trash(p, root)
            return self._json({"ok": True})
        if path == "/api/kb/mkdir":
            return self._json(kb_mkdir(b))
        if path == "/api/kb/status":
            return self._json(kb_set_status(b))
        if path == "/api/skill/file":
            p = skill_path(b["path"])
            if p.suffix.lower() not in TEXT_EXT:
                raise ApiError("只能编辑文本文件")
            p.write_text(b.get("content", ""), encoding="utf-8")
            return self._json({"ok": True})
        if path == "/api/skill/replace":
            skill_replace(base64.b64decode(b["b64"]))
            return self._json(skill_info())
        if path == "/api/skill/reset":
            if not SKILL_DEFAULT.exists():
                raise ApiError("没有默认版本")
            if SKILL.exists():
                dst = TRASH / datetime.now().strftime("skill-%Y%m%d-%H%M%S")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(SKILL), str(dst))
            shutil.copytree(SKILL_DEFAULT, SKILL)
            return self._json(skill_info())
        m = re.fullmatch(r"/api/runs/([\w-]+)/delete", path)
        if m:
            d = run_dir_of(m.group(1))
            dst = TRASH / ("run-" + m.group(1))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(dst))
            return self._json({"ok": True})
        raise ApiError("not found", 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    RUNS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    for d in RUNS.iterdir():   # 上次未结束的任务不会再继续，标记为中断
        m = read_json(d / "meta.json") if d.is_dir() else None
        if m and m.get("status") == "running":
            write_meta(d, status="error", error="服务重启，这次评审已中断，请重新发起")
    srv = None
    for port in range(a.port, a.port + 10):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("端口都被占用")
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"评审工具已启动：{url}\n关闭这个窗口即可退出。", flush=True)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
