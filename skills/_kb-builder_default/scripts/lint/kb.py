"""知识库读取：扫描卡片、加载知识块（标准 + 问题库 + 图片登记）、条件求值、阈值解析。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CARD_PREFIX = ("！", "!")
SKIP_DIRS = {"images", "__pycache__"}
LEVELS = {"root", "folder", "block"}
STATUSES = {"可用", "草稿", "待建设"}
CARD_SECTIONS = {
    "root": ["一句话定位", "什么时候评", "什么时候不评"],
    "folder": ["一句话定位", "什么时候评", "什么时候不评"],
    "block": ["一句话定位", "什么时候评", "什么时候不评", "需要的信息", "与其他知识块的关系", "条目索引"],
}
STD_REQUIRED = ["适用条件", "判断说明", "观察要点", "合格表现", "不合格表现", "不合格时"]


# ============================== 基础 ==============================
def load_yaml(path: Path | str):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path: Path | str | None = None) -> dict:
    return load_yaml(path or ROOT / "config.yaml")


def kb_root(cfg: dict, override: str | None = None) -> Path:
    p = Path(override or cfg["kb_root"])
    return (p if p.is_absolute() else ROOT / p).resolve()


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return (yaml.safe_load(parts[1]) or {}), parts[2]
    return {}, text


def norm_criteria(crit):
    """YAML 会把 true/false 键解析成布尔值，这里统一成字符串。"""
    if not isinstance(crit, dict):
        return crit
    out = {}
    for k, v in crit.items():
        out["true" if k is True else "false" if k is False else str(k)] = v
    return out


def slug(text: str, limit: int = 48) -> str:
    """名称 -> 选项/问题 ID：去冠词，按词截断，不截断半个单词（选项名会发给 Jev）。"""
    s = re.sub(r"^(the|a|an)\s+", "", text.strip().lower())
    out = ""
    for w in [w for w in re.split(r"[^a-z0-9]+", s) if w]:
        nxt = f"{out}_{w}" if out else w
        if len(nxt) > limit:
            break
        out = nxt
    return out or "item"


# ============================== 卡片 ==============================
@dataclass
class Node:
    path: Path                      # 文件夹绝对路径
    rel: str                        # 相对知识库根的路径
    name: str
    meta: dict
    sections: dict
    card_file: Path | None
    children: list = field(default_factory=list)

    @property
    def level(self): return self.meta.get("level", "folder")
    @property
    def status(self): return self.meta.get("status", "待建设")
    @property
    def kb(self): return self.meta.get("kb")
    @property
    def id(self): return self.meta.get("id")


def find_card(folder: Path) -> Path | None:
    cards = [p for p in folder.iterdir() if p.is_file() and p.name.startswith(CARD_PREFIX) and p.suffix == ".md"]
    return cards[0] if len(cards) == 1 else (sorted(cards)[0] if cards else None)


def parse_sections(body: str) -> dict:
    out, cur, buf = {}, None, []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return out


def scan(root: Path) -> Node:
    """递归扫描知识库，返回根节点。kb 字段向下继承。"""
    def walk(folder: Path, parent_kb: str | None) -> Node:
        card = find_card(folder)
        meta, sections = {}, {}
        if card:
            meta, body = split_frontmatter(card.read_text(encoding="utf-8"))
            sections = parse_sections(body)
        meta.setdefault("kb", parent_kb)
        node = Node(folder, folder.relative_to(root).as_posix() if folder != root else ".",
                    folder.name, meta, sections, card)
        for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
            if sub.name.startswith("_") or sub.name in SKIP_DIRS:
                continue
            node.children.append(walk(sub, meta.get("kb")))
        return node
    return walk(root, None)


def iter_nodes(node: Node):
    yield node
    for c in node.children:
        yield from iter_nodes(c)


# ============================== 评审标准 ==============================
CLAUSE_RE = re.compile(r"^### ([A-Z]\d{2})｜(.+?)\s*$", re.M)
FIELD_RE = re.compile(r"^- \*\*(.+?)\*\*[：:]\s*(.*)$")
SUBITEM_RE = re.compile(r"^\s+- (.+)$")


def parse_standard(path: Path) -> tuple[dict, dict]:
    """返回 (头信息, {条目: {title, fields, raw}})。fields 中列表型字段为 list。"""
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    heads = list(CLAUSE_RE.finditer(body))
    clauses = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        chunk = body[m.end():end]
        stop = re.search(r"^## ", chunk, re.M)
        if stop:
            chunk = chunk[:stop.start()]
        fields, cur = {}, None
        for line in chunk.splitlines():
            fm = FIELD_RE.match(line)
            if fm:
                cur = fm.group(1)
                fields[cur] = fm.group(2).strip()
                continue
            sm = SUBITEM_RE.match(line)
            if sm and cur:
                if not isinstance(fields[cur], list):
                    fields[cur] = [fields[cur]] if fields[cur] else []
                fields[cur].append(sm.group(1).strip())
        if not fields:  # 兼容旧格式：一段正文 + **不合格时：**
            text = chunk.strip()
            fix = ""
            if "**不合格时：" in text:
                text, fix = text.split("**不合格时：", 1)
                fix = fix.strip().rstrip("*").strip()
            fields = {"判断说明": text.strip(), "不合格时": fix}
        clauses[m.group(1)] = {"title": m.group(2).strip(), "fields": fields, "raw": chunk.strip()}
    return meta, clauses


def parse_index_table(text: str) -> list[str]:
    return re.findall(r"^\|\s*([A-Z]\d{2})\s*\|", text or "", re.M)


# ============================== 知识块 ==============================
@dataclass
class Block:
    id: str
    kb: str
    node: Node
    status: str
    std_meta: dict = field(default_factory=dict)
    std: dict = field(default_factory=dict)
    q: dict = field(default_factory=dict)          # questions.yaml 全文
    images: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def observations(self): return self.q.get("observations") or {}
    @property
    def clauses(self): return self.q.get("clauses") or {}
    @property
    def refs(self): return self.q.get("refs") or {}
    @property
    def usable(self): return self.status == "可用" and not self.errors and bool(self.clauses)
    @property
    def name(self): return re.sub(r"^\d+_", "", self.node.name).replace("场景概念设计中的", "")

    def ref_path(self, name: str) -> Path:
        return (self.node.path / self.refs[name]["file"]).resolve()

    def examples_for(self, cid: str) -> list[dict]:
        return [im for im in self.images if im.get("role") == "example" and cid in (im.get("clauses") or [])]


def load_block(node: Node) -> Block:
    b = Block(node.id, node.kb, node, node.status)
    if node.status == "待建设":
        return b
    std_name, q_name = node.meta.get("standard"), node.meta.get("questions", "questions.yaml")
    if std_name and (node.path / std_name).exists():
        b.std_meta, b.std = parse_standard(node.path / std_name)
    else:
        b.errors.append(f"缺少评审标准文件 {std_name}")
    qf = node.path / q_name
    if qf.exists():
        b.q = load_yaml(qf)
        for o in b.observations.values():
            if "criteria" in o:
                o["criteria"] = norm_criteria(o["criteria"])
    else:
        b.errors.append(f"缺少问题库 {q_name}")
    cf = node.path / "cases.yaml"
    if cf.exists():
        b.images = load_yaml(cf).get("images") or []
    return b


def load_blocks(root: Path) -> dict[str, Block]:
    tree = scan(root)
    out = {}
    for n in iter_nodes(tree):
        if n.level == "block" and n.id:
            out[n.id] = load_block(n)
    return out


def block_from_dict(bid: str, kb: str, q: dict, base: Path) -> Block:
    """由路由文件中的“用户补充问题”构造临时知识块。"""
    node = Node(base, f"(用户补充:{bid})", bid, {"level": "block", "kb": kb, "id": bid, "status": "可用"}, {}, None)
    b = Block(bid, kb, node, "可用", q={"block": bid, **q})
    for o in b.observations.values():
        if "criteria" in o:
            o["criteria"] = norm_criteria(o["criteria"])
    b.std = {cid: {"title": c.get("title", ""), "fields": {"判断说明": c.get("note", "用户在本次评审中提出的要求")}}
             for cid, c in b.clauses.items()}
    return b


# ============================== 条件 ==============================
COND_RE = re.compile(r"^\s*([\w.]+)\s*(==|!=|not in|in)\s*(.+?)\s*$")


def _lookup(path: str, ctx: dict):
    cur = ctx
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def eval_condition(cond: str, ctx: dict) -> bool:
    m = COND_RE.match(cond)
    if not m:
        return bool(_lookup(cond.strip(), ctx))
    path, op, raw = m.groups()
    val = _lookup(path, ctx)
    val = "" if val is None else (str(val).lower() if isinstance(val, bool) else str(val))
    raw = raw.strip()
    target = [x.strip() for x in raw[1:-1].split(",") if x.strip()] if raw.startswith("[") else raw
    return {"==": val == target, "!=": val != target, "in": val in target, "not in": val not in target}[op]


def all_conditions(conds, ctx: dict) -> bool:
    return all(eval_condition(c, ctx) for c in (conds or []))


def condition_path(cond: str) -> str:
    m = COND_RE.match(cond)
    return (m.group(1) if m else cond).strip()


# ============================== 阈值 ==============================
def thresholds(cfg: dict, block_id: str, clause_id: str | None = None) -> dict:
    j = cfg["judging"]
    th = dict(j["default"])
    th.update((j.get("blocks") or {}).get(block_id) or {})
    if clause_id:
        th.update((j.get("clauses") or {}).get(f"{block_id}.{clause_id}") or {})
    return th


def stable_hash(obj) -> str:
    import hashlib
    return hashlib.sha1(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]
