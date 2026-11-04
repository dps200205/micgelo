"""公共工具：加载配置与问题库、解析标准 md、计算条件。"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path | str):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    return load_yaml(ROOT / "config.yaml")


def _norm_criteria(crit):
    """YAML 会把 true/false 键解析成布尔值，这里统一成字符串。"""
    if not isinstance(crit, dict):
        return crit
    out = {}
    for k, v in crit.items():
        if k is True:
            k = "true"
        elif k is False:
            k = "false"
        out[str(k)] = v
    return out


def load_bank(cfg: dict) -> tuple[dict, dict]:
    obs = load_yaml(ROOT / cfg["bank"]["observations"])["observations"]
    for o in obs.values():
        if "criteria" in o:
            o["criteria"] = _norm_criteria(o["criteria"])
    clauses = load_yaml(ROOT / cfg["bank"]["clauses"])["clauses"]
    return obs, clauses


CLAUSE_RE = re.compile(r"^### ([A-Z]\d{2})｜(.+?)\n\n(.+?)(?=\n### |\n## |\Z)", re.S | re.M)


def parse_standard(path: str) -> dict:
    """从标准 md 中提取 {条款ID: {title, criterion, fix}}。"""
    text = Path(path).read_text(encoding="utf-8")
    out = {}
    for cid, title, body in CLAUSE_RE.findall(text):
        body = body.strip()
        fix = ""
        if "**不合格时：" in body:
            body, fix = body.split("**不合格时：", 1)
            fix = fix.strip().rstrip("*").strip()
        out[cid] = {"title": title.strip(), "criterion": body.strip(), "fix": fix}
    return out


def load_standards(cfg: dict) -> dict:
    allc = {}
    for prefix, s in cfg["standards"].items():
        for cid, c in parse_standard(s["file"]).items():
            c["dimension"] = s["name"]
            allc[cid] = c
    return allc


# ---------------- 条件 ----------------
COND_RE = re.compile(r"^\s*([\w.]+)\s*(==|!=|not in|in)\s*(.+?)\s*$")


def _lookup(path: str, ctx: dict):
    cur = ctx
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [x.strip() for x in raw[1:-1].split(",") if x.strip()]
    return raw


def eval_condition(cond: str, ctx: dict) -> bool:
    m = COND_RE.match(cond)
    if not m:
        val = _lookup(cond.strip(), ctx)
        return bool(val)
    path, op, raw = m.groups()
    val = _lookup(path, ctx)
    val = "" if val is None else str(val).lower() if isinstance(val, bool) else str(val)
    target = _parse_value(raw)
    if op == "==":
        return val == target
    if op == "!=":
        return val != target
    if op == "in":
        return val in target
    return val not in target


def all_conditions(conds, ctx: dict) -> bool:
    return all(eval_condition(c, ctx) for c in (conds or []))


def condition_paths(cond: str) -> str:
    m = COND_RE.match(cond)
    return (m.group(1) if m else cond).strip()


def slug(text: str, limit: int = 48) -> str:
    """名称 -> 选项/问题 ID：去冠词，按词截断，不截断半个单词（选项名会发给 Jev）。"""
    s = re.sub(r"^(the|a|an)\s+", "", text.strip().lower())
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w]
    out = ""
    for w in words:
        nxt = f"{out}_{w}" if out else w
        if len(nxt) > limit:
            break
        out = nxt
    return out or "item"
