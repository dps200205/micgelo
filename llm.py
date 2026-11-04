"""大模型接入层：OpenAI 兼容接口，可在设置中切换供应商。不依赖 openai 包。"""
from __future__ import annotations

import base64
import io
import json
import re
import time
from pathlib import Path

import requests
from PIL import Image, ImageOps


class LLMError(Exception):
    pass


def image_data_url(path: Path | str, max_side: int = 1568) -> str:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def user_content(text: str, images: list | None = None) -> list | str:
    if not images:
        return text
    parts = [{"type": "image_url", "image_url": {"url": image_data_url(p)}} for p in images]
    parts.append({"type": "text", "text": text})
    return parts


def extract_json(text: str):
    """从模型回复中取出 JSON：兼容代码块包裹和前后多余文字。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise json.JSONDecodeError("回复中没有 JSON", text[:200], 0)


class LLM:
    def __init__(self, provider: dict, on_usage=None):
        for k in ("base_url", "model", "api_key"):
            if not provider.get(k):
                raise LLMError(f"大模型配置缺少 {k}，请在“设置”中填写")
        self.p = provider
        self.total = {"prompt": 0, "completion": 0, "calls": 0}
        self.on_usage = on_usage

    @property
    def label(self) -> str:
        return self.p["model"]

    def chat(self, messages: list, thinking: bool = False, timeout: int = 180, temperature: float = 0.2) -> str:
        """流式调用：长任务只要还在输出就不会超时；timeout 指两段数据之间的最长等待（秒）。"""
        body = {"model": self.p["model"], "messages": messages, "temperature": temperature,
                "stream": True, "stream_options": {"include_usage": True}}
        param = self.p.get("thinking_param")
        if param:
            body[param] = bool(thinking)
        body.update(self.p.get("extra_body") or {})
        url = self.p["base_url"].rstrip("/") + "/chat/completions"
        last = None
        for attempt in range(3):
            try:
                with requests.post(url, json=body, timeout=(20, timeout), stream=True,
                                   headers={"Authorization": "Bearer " + self.p["api_key"]}) as r:
                    if r.status_code != 200:
                        last = f"大模型请求失败 HTTP {r.status_code}: {r.text[:500]}"
                        if r.status_code in (429, 500, 502, 503, 504):
                            time.sleep(3 * (attempt + 1))
                            continue
                        break
                    return self._read_stream(r)
            except requests.RequestException as e:
                last = f"大模型连接中断：{e}"
                time.sleep(2 * (attempt + 1))
        raise LLMError(last)

    def _read_stream(self, r) -> str:
        parts = []
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            d = json.loads(data)
            if d.get("error"):
                raise LLMError(f"大模型返回错误：{d['error']}")
            u = d.get("usage")
            if u:
                self.total["prompt"] += u.get("prompt_tokens", 0)
                self.total["completion"] += u.get("completion_tokens", 0)
            for c in d.get("choices") or []:
                piece = (c.get("delta") or {}).get("content")
                if piece:
                    parts.append(piece)
        self.total["calls"] += 1
        return "".join(parts)

    def chat_json(self, system: str, text: str, images: list | None = None, thinking: bool = False,
                  validate=None, repairs: int = 2, log=None) -> dict:
        """请求并解析 JSON。validate(obj) 返回错误列表；有错误时把错误发回模型修复。"""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_content(text, images)}]
        for attempt in range(repairs + 1):
            reply = self.chat(messages, thinking=thinking)
            try:
                obj = extract_json(reply)
                errs = validate(obj) if validate else []
            except (json.JSONDecodeError, ValueError) as e:
                obj, errs = None, [f"回复不是合法 JSON：{e}"]
            if not errs:
                return obj
            if log:
                log(f"模型输出未通过检查（第 {attempt + 1} 次）：{errs[0]}" + (f" 等 {len(errs)} 项" if len(errs) > 1 else ""))
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "输出未通过检查，请修正后重新输出完整 JSON，不要输出其他内容：\n- " + "\n- ".join(errs[:30])})
        raise LLMError("模型多次输出都未通过检查：" + "；".join(errs[:5]))
