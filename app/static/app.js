"use strict";
// ============================== 工具函数 ==============================
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const main = () => $("#main");
const state = { job: null, jobTimer: null, reviewImg: null, kb: { sel: "", file: null, open: new Set([""]), tree: null }, settings: null };

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  let d;
  try { d = await r.json(); } catch { d = { error: `HTTP ${r.status}` }; }
  if (!r.ok || d.error) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}
function toast(msg, ms = 2600) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), ms);
}
function fileB64(file) {
  return new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(",")[1]); fr.onerror = rej; fr.readAsDataURL(file); });
}
function pickFiles(accept, multiple = false) {
  return new Promise((res) => { const i = document.createElement("input"); i.type = "file"; i.accept = accept; i.multiple = multiple; i.onchange = () => res([...i.files]); i.click(); });
}
function vBadge(v) {
  const cls = { 合格: "b-ok", 不合格: "b-bad", 存疑: "b-warn", 待复核: "b-warn" }[v] || "b-gray";
  return `<span class="badge ${cls}">${esc(v || "—")}</span>`;
}
const KBN = { basic: "美术基础", project: "项目规范" };
function kbBadge(k) { return `<span class="badge ${k === "project" ? "b-blue" : "b-gray"}">${esc(KBN[k] || k || "")}</span>`; }
function fmtP(p) { return p === null || p === undefined ? "—" : Number(p).toFixed(2); }
function msgBox(el, text, kind = "err") { el.innerHTML = text ? `<div class="msg ${kind}">${esc(text)}</div>` : ""; }
function modal(html) {
  const bg = document.createElement("div"); bg.className = "modal-bg"; bg.innerHTML = `<div class="modal">${html}</div>`;
  bg.addEventListener("click", (e) => { if (e.target === bg) bg.remove(); });
  document.body.appendChild(bg); return bg;
}

// 简易 Markdown 渲染（足够显示知识库和报告）
function md(src) {
  let text = String(src || "").replace(/\r/g, "");
  let fm = "";
  if (text.startsWith("---\n")) { const e = text.indexOf("\n---", 4); if (e > 0) { fm = text.slice(4, e); text = text.slice(e + 4); } }
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  const lines = text.split("\n"); const out = []; let i = 0;
  if (fm) out.push(`<pre>${esc(fm)}</pre>`);
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) { const buf = []; i++; while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]); i++; out.push(`<pre>${esc(buf.join("\n"))}</pre>`); continue; }
    let m;
    if ((m = l.match(/^(#{1,4})\s+(.*)/))) { out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); i++; continue; }
    if (/^\|/.test(l)) {
      const rows = []; while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      let h = `<table><tr>${cells(rows[0]).map((c) => `<th>${inline(c)}</th>`).join("")}</tr>`;
      rows.slice(rows[1] && /^[\s|:-]+$/.test(rows[1]) ? 2 : 1).forEach((r) => { h += `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`; });
      out.push(h + "</table>"); continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const buf = []; while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || /^\s{2,}\S/.test(lines[i]))) {
        const s = lines[i++]; const ind = s.match(/^\s*/)[0].length;
        buf.push(`<li style="margin-left:${ind * 8}px">${inline(s.replace(/^\s*([-*]|\d+\.)\s+/, ""))}</li>`);
      }
      out.push(`<ul>${buf.join("")}</ul>`); continue;
    }
    if (/^>\s?/.test(l)) { const buf = []; while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, "")); out.push(`<blockquote>${inline(buf.join(" "))}</blockquote>`); continue; }
    if (!l.trim()) { i++; continue; }
    const buf = []; while (i < lines.length && lines[i].trim() && !/^(#|\||```|>|\s*([-*]|\d+\.)\s)/.test(lines[i])) buf.push(lines[i++]);
    out.push(`<p>${inline(buf.join(" "))}</p>`);
  }
  return `<div class="md">${out.join("")}</div>`;
}

// ============================== 路由 ==============================
const pages = { review: renderReview, history: renderHistory, run: renderRun, kb: renderKB, generate: renderGenerate, judging: renderJudging, settings: renderSettings };
function route() {
  const [p, arg] = (location.hash.slice(1) || "review").split("/");
  const name = pages[p] ? p : "review";
  $$(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.page === (name === "run" ? "history" : name)));
  main().scrollTop = 0;
  pages[name](arg ? decodeURIComponent(arg) : undefined);
}
window.addEventListener("hashchange", route);

async function refreshNav() {
  try {
    const s = await api("/api/settings"); state.settings = s;
    const p = s.llm.providers[s.llm.active];
    $("#navStatus").innerHTML = `<div><span class="dot ${s.jev_key_mask || s.jev_env_fallback ? "ok" : "bad"}"></span>Jev ${s.jev_key_mask || s.jev_env_fallback ? "已配置" : "未配置"}</div>
      <div><span class="dot ${p && p.api_key_mask ? "ok" : "bad"}"></span>${esc(p ? p.model : "大模型未配置")}</div>`;
  } catch (e) { $("#navStatus").textContent = "无法连接服务"; }
}

// ============================== 新建评审 ==============================
const STEP_NAMES = ["理解图片与检索知识库", "Jev 逐项观察", "代码判定", "大模型复核", "生成报告"];
function stepsHtml(job) {
  return `<div class="steps">${STEP_NAMES.map((n, i) => {
    let c = "";
    if (job) {
      if (job.status === "error" && i === job.step) c = "err";
      else if (i < job.step || job.status === "done") c = "done";
      else if (i === job.step && job.status === "running") c = "on";
    }
    return `<div class="step ${c}"><div class="n">${c === "on" ? '<span class="spin"></span>' : ""}第 ${i + 1} 步</div>${n}</div>`;
  }).join("")}</div>`;
}
function renderReview() {
  main().innerHTML = `
  <div class="page-h"><div><h1>新建评审</h1><div class="sub">上传场景概念设计图，写清图的类型，系统会自动检索知识库、调用 Jev 观察并由大模型复核。</div></div></div>
  <div class="grid2">
    <div class="card">
      <div class="drop" id="drop"><div class="ph">点击或拖入图片<br><span class="hint">PNG / JPG，短边不少于 280 像素</span></div></div>
      <label class="f">图片说明 <span class="hint">写清图的类型，例如“这是一张 PVP 爆破地图的场景概念设计图”</span></label>
      <textarea class="i" id="userInput" rows="3" placeholder="这是一张 PVP 爆破地图的场景概念设计图"></textarea>
      <label class="f">主体或焦点 <span class="hint">建议填写。不填时由大模型推断，同一张图的结论可能不一样</span></label><input class="i" id="subject" placeholder="例如：走廊尽头的控制室">
      <details style="margin-top:10px"><summary>更多选项</summary>
        <label class="f">最终观看尺寸（可选）</label><input class="i" id="viewSize" placeholder="例如：1920x1080，或“手机横屏”">
        <div class="grid2" style="gap:10px">
          <div><label class="f">预期主导形式</label><select class="i" id="dft"><option value="">未指定（只描述，不判定）</option><option value="point">点</option><option value="line">线</option><option value="area">面</option><option value="mixed">点线面混合</option></select></div>
          <div><label class="f">多类平衡目标</label><select class="i" id="bal"><option value="">未要求</option><option value="point_line">点线平衡</option><option value="point_area">点面平衡</option><option value="line_area">线面平衡</option><option value="all_three">点线面三类平衡</option></select></div>
        </div>
        <div class="hint">作者意图只由你指定，系统不会替你猜。未指定时，相关条目只描述或不评。</div>
        <label class="row" style="margin-top:12px;font-size:13px"><input type="checkbox" id="skipReview"> 只要 Jev 初判，跳过大模型复核</label>
      </details>
      <div id="reviewMsg"></div>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="startBtn">开始评审</button><span class="hint" id="costHint">一次评审约需 3–6 分钟</span></div>
    </div>
    <div class="card" id="progressCard"></div>
  </div>`;
  const drop = $("#drop");
  const show = (f) => {
    if (!f || !/image\/(png|jpe?g)/.test(f.type)) return toast("请选择 PNG 或 JPG 图片");
    state.reviewImg = f; const url = URL.createObjectURL(f); drop.innerHTML = `<img src="${url}">`;
  };
  if (state.reviewImg) show(state.reviewImg);
  drop.onclick = async () => show((await pickFiles("image/png,image/jpeg"))[0]);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); show(e.dataTransfer.files[0]); };
  document.onpaste = (e) => { if (location.hash.startsWith("#review") || !location.hash) { const f = [...(e.clipboardData?.files || [])][0]; if (f) show(f); } };
  $("#startBtn").onclick = startReview;
  paintProgress();
}
function paintProgress() {
  const el = $("#progressCard"); if (!el) return;
  const job = state.job && state.job.kind === "review" ? state.job : null;
  if (!job) {
    el.innerHTML = `<h2>评审流程</h2>${stepsHtml(null)}
      <div class="sub">1. 大模型看图，逐层读取知识库卡片，选出适用的知识块和条目，并列出画面元素。<br>
      2. 系统把条目对应的问题填入画面元素，发给 Jev 逐项回答，得到概率。<br>
      3. 代码按“判定标准”给出每条条目和每个知识块的初判。<br>
      4. 大模型复核存疑项、合并同因问题，给出修改建议。项目规范优先。<br>
      5. 生成报告，保存在“评审记录”中。</div>`;
    return;
  }
  el.innerHTML = `<div class="row" style="justify-content:space-between"><h2 style="margin:0">${job.status === "running" ? '<span class="spin"></span>评审进行中' : job.status === "done" ? "评审完成" : "评审失败"}</h2>
    ${job.status !== "running" ? `<a class="btn sm" href="#run/${job.run_id}">查看结果</a>` : ""}</div>
    <div style="height:10px"></div>${stepsHtml(job)}
    ${job.error ? `<div class="msg err">${esc(job.error)}</div>` : ""}
    <div class="logs" id="jobLogs">${job.logs.map((l) => `${l.t}  ${esc(l.msg)}`).join("\n")}</div>`;
  const lg = $("#jobLogs"); if (lg) lg.scrollTop = lg.scrollHeight;
}
async function startReview() {
  const box = $("#reviewMsg"); msgBox(box, "");
  if (!state.reviewImg) return msgBox(box, "请先选择图片");
  if (state.job && state.job.status === "running") return msgBox(box, "已有评审正在进行，请等待完成");
  const btn = $("#startBtn"); btn.disabled = true;
  try {
    const r = await api("/api/review", {
      image_b64: await fileB64(state.reviewImg), filename: state.reviewImg.name, user_input: $("#userInput").value,
      subject: $("#subject").value, view_size: $("#viewSize").value, skip_review: $("#skipReview").checked,
      dominant_form_target: $("#dft").value || null, balance_target: $("#bal").value || null,
    });
    state.job = { id: r.job_id, run_id: r.run_id, kind: "review", status: "running", step: 0, logs: [] };
    pollJob(() => { paintProgress(); }, (job) => { if (job.status === "done") { toast("评审完成"); location.hash = "#run/" + job.run_id; } });
    paintProgress();
  } catch (e) { msgBox(box, e.message); } finally { btn.disabled = false; }
}
function pollJob(onTick, onEnd) {
  clearInterval(state.jobTimer);
  state.jobTimer = setInterval(async () => {
    try {
      const j = await api("/api/jobs/" + state.job.id);
      state.job = { ...state.job, ...j }; onTick(state.job);
      if (j.status !== "running") { clearInterval(state.jobTimer); onEnd && onEnd(state.job); }
    } catch (e) { clearInterval(state.jobTimer); state.job.status = "error"; state.job.error = e.message; onTick(state.job); }
  }, 1500);
}

// ============================== 评审记录 ==============================
async function renderHistory() {
  main().innerHTML = `<div class="page-h"><h1>评审记录</h1></div><div id="hist" class="hist"><div class="empty">加载中…</div></div>`;
  const { runs } = await api("/api/runs");
  if (!runs.length) { $("#hist").innerHTML = `<div class="empty" style="grid-column:1/-1">还没有评审记录。<a href="#review">新建评审</a></div>`; return; }
  $("#hist").innerHTML = runs.map((r) => `
    <div class="hc" onclick="location.hash='#run/${r.id}'">
      <img src="/api/runs/${r.id}/image" loading="lazy">
      <div class="b"><div class="d">${esc(r.created)}${r.reviewed === false ? " · 仅初判" : ""}</div>
        <div style="margin:4px 0 6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.user_input || r.filename || "（无说明）")}</div>
        <div class="chips">${r.status === "running" ? '<span class="badge b-blue">进行中</span>' : r.status === "error" ? '<span class="badge b-bad">失败</span>' :
          Object.entries(r.verdict || {}).map(([k, v]) => `<span class="badge ${v === "合格" ? "b-ok" : v === "不合格" ? "b-bad" : "b-warn"}">${esc(k)}：${esc(v)}</span>`).join("")}</div>
      </div></div>`).join("");
}

async function renderRun(id) {
  main().innerHTML = `<div class="empty">加载中…</div>`;
  let d;
  try { d = await api("/api/runs/" + encodeURIComponent(id)); } catch (e) { main().innerHTML = `<div class="msg err">${esc(e.message)}</div>`; return; }
  const m = d.meta || {}, v = d.verdicts, f = d.final, b = d.brief || {}, rt = d.routing || {};
  const running = m.status === "running";
  const jev = m.jev || {}, llm = m.llm || {};
  const tok = Object.values(jev.usage || {}).reduce((a, u) => a + (u.input_tokens || 0), 0);
  const reportName = f ? "final_report.md" : "report.md";
  main().innerHTML = `
  <div class="page-h"><div><h1>评审结果</h1><div class="sub">${esc(m.created || "")} · ${esc(id)}</div></div>
    <div class="row">${v ? `<a class="btn" href="/api/runs/${id}/file?name=${reportName}&dl=1">下载报告</a><a class="btn" href="/api/runs/${id}/file?name=final.json&dl=1" ${f ? "" : "hidden"}>下载 final.json</a>` : ""}
    <button class="btn danger" id="delRun">删除</button></div></div>
  ${running ? `<div class="card" id="progressCard"></div>` : ""}
  ${m.status === "error" ? `<div class="msg err">评审失败：${esc(m.error)}</div>` : ""}
  <div class="grid2" style="grid-template-columns:minmax(0,1fr) minmax(0,1.6fr)">
    <div class="card"><img class="thumb" src="/api/runs/${id}/image">
      <div class="kv" style="margin-top:12px">
        <div>图片说明</div><div>${esc(m.user_input || "（未填写）")}</div>
        <div>大模型理解</div><div>${esc(b.image_understanding || "—")}</div>
        <div>图类型</div><div>${esc(rt.image_type || "未匹配项目节点")}</div>
        <div>主体</div><div>${esc(b.subject_hint || "—")}</div>
        <div>用量</div><div>Jev ${tok} token（约 $${(jev.cost || 0).toFixed(4)}）<br>${esc(llm.model || "大模型")} ${llm.calls || 0} 次调用，${(llm.prompt || 0) + (llm.completion || 0)} token</div>
      </div>
      ${(b.assumptions || []).length ? `<h3>推断（需确认）</h3><ul class="sub" style="padding-left:18px;margin:0">${b.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
    </div>
    <div>
      <div class="card"><h2>知识块结论</h2><div class="blocks">${v ? Object.entries(v.blocks).map(([bid, bk]) => blockCard(bid, bk, f)).join("") : '<div class="empty">暂无结果</div>'}</div>
        ${(rt.missing_knowledge || []).length ? `<div class="msg warn" style="margin-bottom:0"><b>适用但知识库尚未建设：</b>${rt.missing_knowledge.map((x) => esc(x.path.split("/").pop())).join("、")}</div>` : ""}
      </div>
      ${f ? issuesCard(f) : v ? `<div class="msg info">这次评审跳过了大模型复核，只有 Jev 初判。</div>` : ""}
    </div>
  </div>
  ${v ? clausesCard(v) : ""}
  ${rt.blocks ? routingCard(rt, d.scene) : ""}
  <details class="card"><summary>运行日志</summary><div class="logs" style="margin-top:10px">${(m.logs || []).map((l) => `${l.t}  ${esc(l.msg)}`).join("\n")}</div></details>`;
  $("#delRun").onclick = async () => { if (!confirm("删除这条评审记录？（会移到 data/trash，可以手动恢复）")) return; await api(`/api/runs/${id}/delete`, {}); toast("已删除"); location.hash = "#history"; };
  $$("tr.click").forEach((tr) => tr.onclick = () => { const n = tr.nextElementSibling; n.hidden = !n.hidden; });
  $$(".ctab").forEach((bt) => bt.onclick = () => { $$(".ctab").forEach((x) => x.classList.toggle("on", x === bt)); $$(".cpane").forEach((p) => p.hidden = p.dataset.b !== bt.dataset.b); });
  if (running && state.job && state.job.run_id === id) { paintProgress(); pollJob(paintProgress, () => renderRun(id)); }
  else if (running) { $("#progressCard").innerHTML = `<div class="msg info">这次评审仍在进行或服务已重启，请稍后刷新。</div>`; }
}
function blockCard(bid, bk, f) {
  const s = bk.summary, js = bk.jev_summary;
  const n = s.evaluated || 1;
  const pct = (x) => (x / n * 100).toFixed(1) + "%";
  return `<div class="bk"><div class="t"><span>${esc(bk.name)} <span class="sub mono">${esc(bid)}</span></span>${vBadge(s.verdict)}</div>
    <div class="row" style="gap:6px;margin-top:4px">${kbBadge(bk.kb)}${f && js ? `<span class="sub">Jev 初判 ${esc(js.verdict)}</span>` : ""}</div>
    <div class="bar"><i style="width:${pct(s.passed)};background:#22c55e"></i><i style="width:${pct(s.uncertain)};background:#f59e0b"></i><i style="width:${pct(s.failed)};background:#ef4444"></i></div>
    <div class="sub">合格 ${s.passed} · 存疑 ${s.uncertain} · 不合格 ${s.failed}　合格率 ${s.pass_rate === null ? "—" : Math.round(s.pass_rate * 100) + "%"}</div>
    <div class="hint">${esc(s.rule)}${s.vetoes.length ? `；<span style="color:var(--bad)">一票否决：${esc(s.vetoes.join("、"))}</span>` : ""}</div></div>`;
}
function issuesCard(f) {
  const iss = f.issues || [];
  return `<div class="card"><h2>修改建议</h2>
    ${iss.length ? iss.map((it, i) => `<div class="issue"><div class="h"><span class="num">${i + 1}</span><span>${esc(it.target)}</span>${kbBadge(it.kb)}<span class="sub mono" style="font-weight:400">${esc((it.clauses || []).join(" "))}</span></div>
      <dl><dt>位置</dt><dd>${esc(it.location)}</dd><dt>问题</dt><dd>${esc(it.problem)}</dd><dt>动作</dt><dd>${esc(it.action)}</dd><dt>期望</dt><dd>${esc(it.expected)}</dd></dl></div>`).join("") : '<div class="sub">没有需要修改的问题。</div>'}
    ${(f.keep || []).length ? `<h3>修改时保留</h3><ul style="padding-left:18px;margin:0">${f.keep.map((k) => `<li>${esc(k)}</li>`).join("")}</ul>` : ""}
    ${f.notes ? `<h3>需要注意</h3><div class="sub" style="white-space:pre-wrap">${esc(f.notes)}</div>` : ""}</div>`;
}
function clausesCard(v) {
  const ids = Object.keys(v.blocks);
  return `<div class="card"><h2>条目明细 <span class="sub" style="font-weight:400">点击行查看 Jev 的问题和概率</span></h2>
    <div class="tabs">${ids.map((b, i) => `<button class="ctab ${i ? "" : "on"}" data-b="${esc(b)}">${esc(v.blocks[b].name)}</button>`).join("")}</div>
    ${ids.map((bid, i) => {
      const bk = v.blocks[bid];
      return `<div class="cpane" data-b="${esc(bid)}" ${i ? "hidden" : ""}><table class="t"><tr><th>条目</th><th>标题</th><th>Jev 初判</th><th>最终</th><th>最低概率</th><th>说明</th></tr>
      ${Object.entries(bk.clauses).map(([cid, c]) => {
        const jv = c.jev_verdict || c.verdict;
        const changed = c.jev_verdict && c.jev_verdict !== c.verdict;
        return `<tr class="click"><td class="mono">${esc(cid)}</td><td>${esc(c.title)}</td><td>${vBadge(jv)}</td><td>${c.jev_verdict ? vBadge(c.verdict) : "—"}${changed && c.overridden ? ' <span class="hint">推翻</span>' : ""}</td>
          <td class="mono">${fmtP(c.p_min)}</td><td class="sub">${esc(c.llm_reason || c.reason || "")}</td></tr>
          <tr class="detail" hidden><td></td><td colspan="5">${(c.checks || []).map((ch) => `<div style="margin:4px 0"><b class="mono">${esc(ch.obs)}</b> ${vBadge(ch.verdict)} ${ch.soft ? '<span class="hint">soft：最差判存疑</span>' : ""} <span class="hint">${ch.aggregate === "best" ? "取最好" : "取最差"}</span>
            ${ch.items.map((it) => `<div class="q">· ${esc(it.question || it.qid)}<br>&nbsp;&nbsp;<b>${it.gated ? "元素核对未通过：" + esc(it.gated) : it.p_good === null ? "回答：" + esc(it.answer) + "（仅描述）" : "好的方向概率 " + fmtP(it.p_good)}</b></div>`).join("")}</div>`).join("") || '<span class="hint">无检查</span>'}</td></tr>`;
      }).join("")}</table></div>`;
    }).join("")}</div>`;
}
function routingCard(rt, scene) {
  const sc = scene || {};
  const el = (k, label) => (sc[k] || []).length ? `<div><span class="sub">${label}：</span>${sc[k].map((x) => esc(x.name)).join("；")}</div>` : "";
  return `<details class="card"><summary>检索与场景解析（第 1 步结果）</summary>
    <h3>选中的知识块</h3>${rt.blocks.map((b) => `<div style="margin-bottom:6px"><b>${esc(b.id)}</b> <span class="sub">${esc(b.path)}</span><br><span class="sub">${esc(b.reason || "")}</span><br>
      <span class="hint">评 ${b.clauses.length} 条：${esc(b.clauses.join(" "))}${Object.keys(b.skipped || {}).length ? "；跳过：" + Object.entries(b.skipped).map(([k, r]) => esc(k + "（" + r + "）")).join("、") : ""}</span></div>`).join("")}
    ${(rt.skipped_blocks || []).length ? `<h3>判断不适用</h3>${rt.skipped_blocks.map((x) => `<div class="sub">${esc(x.path)}：${esc(x.reason)}</div>`).join("")}` : ""}
    ${(rt.missing_knowledge || []).length ? `<h3>适用但缺少知识</h3>${rt.missing_knowledge.map((x) => `<div class="sub">${esc(x.path)}：${esc(x.reason)}</div>`).join("")}` : ""}
    <h3>画面元素</h3><div style="font-size:13px">${sc.subject ? `<div><span class="sub">主体：</span>${esc(sc.subject.name)}</div>` : ""}
      ${el("repeated_groups", "成组元素")}${el("guiding_lines", "引导线")}${el("large_areas", "大块面")}${el("dense_regions", "密集区")}${el("point_groups", "点状元素")}</div></details>`;
}

// ============================== 知识库 ==============================
async function renderKB() {
  main().innerHTML = `
  <div class="page-h"><div><h1>知识库</h1><div class="sub" id="kbRoot"></div></div>
    <div class="row"><button class="btn" id="lintBtn">检查知识库</button><a class="btn" href="#generate">用 AI 生成知识块</a></div></div>
  <div id="lintOut"></div>
  <div class="kbw">
    <div class="card" style="padding:0"><div class="tree" id="tree"></div></div>
    <div class="card" style="padding:0" id="dirPanel"></div>
    <div class="card" id="filePanel"><div class="empty">在左侧选择文件夹，再选择文件查看或编辑</div></div>
  </div>`;
  $("#lintBtn").onclick = runLint;
  await loadTree();
  await openDir(state.kb.sel);
  if (state.kb.file) openFile(state.kb.file);
}
async function loadTree() {
  const t = await api("/api/kb/tree"); state.kb.tree = t.tree;
  $("#kbRoot").textContent = "位置：" + t.root;
  const node = (n, d) => {
    const has = n.children.length > 0, open = state.kb.open.has(n.path);
    return `<div class="tn ${state.kb.sel === n.path ? "on" : ""}" data-p="${esc(n.path)}" style="padding-left:${6 + d * 14}px" title="${esc(n.summary || n.name)}">
      <span class="tw" data-tw="${esc(n.path)}">${has ? (open ? "▾" : "▸") : ""}</span>
      <span class="nm">${n.level === "block" ? "◆ " : ""}${esc(n.path ? n.name : "知识库根目录")}</span>${n.path ? `<span class="st ${esc(n.status)}">${esc(n.status)}</span>` : ""}</div>
      ${has && open ? n.children.map((c) => node(c, d + 1)).join("") : ""}`;
  };
  $("#tree").innerHTML = node(t.tree, 0);
  $$("#tree .tn").forEach((el) => el.onclick = (e) => {
    const p = el.dataset.p;
    if (e.target.dataset.tw !== undefined) { state.kb.open.has(p) ? state.kb.open.delete(p) : state.kb.open.add(p); loadTree(); return; }
    state.kb.open.add(p); state.kb.sel = p; state.kb.file = null; loadTree(); openDir(p);
    $("#filePanel").innerHTML = `<div class="empty">选择文件查看或编辑</div>`;
  });
}
function findNode(n, p) { if (n.path === p) return n; for (const c of n.children) { const r = findNode(c, p); if (r) return r; } return null; }
async function openDir(p) {
  const node = findNode(state.kb.tree, p) || state.kb.tree;
  const d = await api("/api/kb/dir?path=" + encodeURIComponent(p));
  const isRoot = !p;
  $("#dirPanel").innerHTML = `<div style="padding:12px 12px 4px"><div style="font-weight:600;word-break:break-all">${esc(isRoot ? "知识库根目录" : node.name)}</div>
      <div class="row" style="gap:6px;margin:6px 0">${isRoot ? "" : `<span class="badge b-gray">${node.level === "block" ? "知识块" + (node.id ? " · " + esc(node.id) : "") : "文件夹"}</span>`}${node.kb ? kbBadge(node.kb) : ""}</div>
      ${isRoot ? "" : `<label class="f" style="margin-top:4px">状态</label><select class="i" id="stSel">${["可用", "草稿", "待建设"].map((s) => `<option ${s === node.status ? "selected" : ""}>${s}</option>`).join("")}</select>`}
      <div class="row" style="gap:6px;margin-top:10px">
        ${node.level !== "block" ? `<button class="btn sm" id="mkFolder">新建文件夹</button><button class="btn sm" id="mkBlock">新建知识块</button>` : ""}
        <button class="btn sm" id="upFiles">上传文件</button><button class="btn sm" id="upZip">导入压缩包</button>
        ${isRoot ? "" : `<button class="btn sm danger" id="rmDir">删除</button>`}</div></div>
    <div class="files">${d.files.map((f) => `<div class="fi ${state.kb.file === f.path ? "on" : ""}" data-f="${esc(f.path)}" data-k="${f.kind}"><span>${esc(f.name)}</span><span>${(f.size / 1024).toFixed(1)}K</span></div>`).join("") || '<div class="empty">空文件夹</div>'}</div>`;
  $$("#dirPanel .fi").forEach((el) => el.onclick = () => { state.kb.file = el.dataset.f; $$("#dirPanel .fi").forEach((x) => x.classList.toggle("on", x === el)); openFile(el.dataset.f, el.dataset.k); });
  const reload = async () => { await loadTree(); await openDir(p); };
  if ($("#stSel")) $("#stSel").onchange = async (e) => {
    try { await api("/api/kb/status", { path: p, status: e.target.value }); toast("状态已更新为 " + e.target.value); await reload(); }
    catch (err) { e.target.value = node.status; alert(err.message); }
  };
  const mk = (type) => {
    const md_ = modal(`<h2>${type === "block" ? "新建知识块" : "新建文件夹"}</h2>
      <label class="f">名称</label><input class="i" id="mkName" placeholder="${type === "block" ? "例如：场景概念设计中的聚散" : "例如：构图与引导"}">
      ${type === "block" ? `<label class="f">知识块 ID（小写英文，全库唯一）</label><input class="i" id="mkId" placeholder="例如：jusan">` : ""}
      <div class="hint">会自动生成一张“待建设”状态的卡片，之后可以编辑内容，或用 AI 生成。</div><div id="mkMsg"></div>
      <div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn" id="mkCancel">取消</button><button class="btn primary" id="mkOk">创建</button></div>`);
    $("#mkCancel", md_).onclick = () => md_.remove();
    $("#mkOk", md_).onclick = async () => {
      try { const r = await api("/api/kb/mkdir", { parent: p, name: $("#mkName", md_).value, type, id: $("#mkId", md_)?.value });
        md_.remove(); state.kb.open.add(p); state.kb.sel = r.path; await loadTree(); await openDir(r.path); toast("已创建"); }
      catch (e) { msgBox($("#mkMsg", md_), e.message); }
    };
  };
  if ($("#mkFolder")) { $("#mkFolder").onclick = () => mk("folder"); $("#mkBlock").onclick = () => mk("block"); }
  $("#upFiles").onclick = async () => {
    const fs = await pickFiles(".md,.yaml,.yml,.txt,.json,.png,.jpg,.jpeg", true); if (!fs.length) return;
    try { const r = await api("/api/kb/upload", { dir: p, files: await Promise.all(fs.map(async (f) => ({ name: f.name, b64: await fileB64(f) }))) }); toast(`已上传 ${r.saved.length} 个文件`); reload(); }
    catch (e) { alert(e.message); }
  };
  $("#upZip").onclick = async () => {
    const [f] = await pickFiles(".zip"); if (!f) return;
    if (!confirm(`把 ${f.name} 解压到“${isRoot ? "知识库根目录" : node.name}”？同名文件会被覆盖。`)) return;
    try { const r = await api("/api/kb/import_zip", { dir: p, b64: await fileB64(f) }); toast(`已导入 ${r.count} 个文件`); reload(); } catch (e) { alert(e.message); }
  };
  if ($("#rmDir")) $("#rmDir").onclick = async () => {
    if (!confirm(`删除“${node.name}”及其中全部内容？\n会移到 data/trash，可以手动恢复。`)) return;
    try { await api("/api/kb/delete", { path: p }); state.kb.sel = p.split("/").slice(0, -1).join("/"); state.kb.file = null; await loadTree(); await openDir(state.kb.sel); $("#filePanel").innerHTML = ""; toast("已删除"); }
    catch (e) { alert(e.message); }
  };
}
async function openFile(path, kind) {
  const fp = $("#filePanel"); const name = path.split("/").pop();
  if (!kind) kind = /\.(png|jpe?g)$/i.test(path) ? "image" : /\.(md|ya?ml|txt|json|py)$/i.test(path) ? "text" : "other";
  const head = (extra = "") => `<div class="row" style="justify-content:space-between;margin-bottom:10px"><div style="font-weight:600;word-break:break-all">${esc(name)}</div><div class="row" style="gap:6px">${extra}<button class="btn sm danger" id="rmFile">删除</button></div></div>`;
  if (kind === "image") fp.innerHTML = head() + `<img src="/api/kb/raw?path=${encodeURIComponent(path)}" style="max-width:100%;border-radius:8px;border:1px solid var(--line)">`;
  else if (kind !== "text") fp.innerHTML = head() + `<div class="empty">无法预览此类文件</div>`;
  else {
    const { content } = await api("/api/kb/file?path=" + encodeURIComponent(path));
    const isMd = /\.md$/i.test(path);
    fp.innerHTML = head(`${isMd ? '<button class="btn sm" id="pv">预览</button>' : ""}<button class="btn sm primary" id="sv">保存</button>`) +
      `<textarea class="i code" id="ed" spellcheck="false"></textarea><div id="pvBox" hidden style="max-height:calc(100vh - 230px);overflow:auto"></div><div id="svMsg"></div>`;
    $("#ed").value = content;
    $("#sv").onclick = async () => {
      try { await api("/api/kb/file", { path, content: $("#ed").value }); msgBox($("#svMsg"), "已保存（旧版本备份在 data/trash）", "ok"); loadTree(); }
      catch (e) { msgBox($("#svMsg"), e.message); }
    };
    if (isMd) $("#pv").onclick = () => { const pv = $("#pvBox"), ed = $("#ed"); const on = pv.hidden; pv.hidden = !on; ed.hidden = on; $("#pv").textContent = on ? "编辑" : "预览"; if (on) pv.innerHTML = md(ed.value); };
    $("#ed").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); $("#sv").click(); } });
  }
  $("#rmFile").onclick = async () => {
    if (!confirm(`删除 ${name}？（会移到 data/trash）`)) return;
    try { await api("/api/kb/delete", { path }); state.kb.file = null; fp.innerHTML = `<div class="empty">已删除</div>`; openDir(state.kb.sel); loadTree(); } catch (e) { alert(e.message); }
  };
}
async function runLint() {
  const out = $("#lintOut"); out.innerHTML = `<div class="msg info"><span class="spin"></span>检查中…</div>`;
  try {
    const r = await api("/api/kb/lint"); const s = r.stats;
    out.innerHTML = `<div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">检查结果：${r.errors.length ? `<span style="color:var(--bad)">错误 ${r.errors.length} 条</span>` : '<span style="color:var(--ok)">没有错误</span>'}，警告 ${r.warnings.length} 条</h2><button class="btn sm" onclick="this.closest('.card').remove()">关闭</button></div>
      <div class="sub" style="margin:6px 0">知识块 ${s.block || 0} 个：可用 ${s["可用"]}，草稿 ${s["草稿"]}，待建设 ${s["待建设"]}。只有“可用”的知识块参与评审；草稿和待建设的问题只作提示。</div>
      ${r.errors.map((e) => `<div class="q" style="color:var(--bad)">✗ ${esc(e)}</div>`).join("")}${r.warnings.map((e) => `<div class="q" style="color:var(--warn)">! ${esc(e)}</div>`).join("")}</div>`;
  } catch (e) { msgBox(out, e.message); }
}

// ============================== 知识库生成 ==============================
async function renderGenerate() {
  main().innerHTML = `<div class="page-h"><div><h1>知识库生成</h1><div class="sub">把课程笔记、项目规范、图片交给 AI，按知识库生成 skill 产出知识块草稿；审核后在知识库中设为“可用”。</div></div></div>
  <div class="grid2" style="grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)">
    <div class="card" id="genCard"></div>
    <div class="card" id="skillCard"><div class="empty">加载中…</div></div>
  </div>`;
  paintSkill();
  const t = await api("/api/kb/tree");
  const folders = [];
  const walk = (n, d) => { if (n.level !== "block") { folders.push({ p: n.path, label: "　".repeat(d) + (n.path ? n.name : "知识库根目录") + (n.kb ? `（${KBN[n.kb]}）` : "") }); n.children.forEach((c) => walk(c, d + 1)); } };
  walk(t.tree, 0);
  $("#genCard").innerHTML = `<h2>生成新知识块</h2>
    <label class="f">放在哪个文件夹下</label><select class="i" id="gParent">${folders.map((f) => `<option value="${esc(f.p)}">${esc(f.label)}</option>`).join("")}</select>
    <label class="f">知识块名称（可选）</label><input class="i" id="gName" placeholder="例如：场景概念设计中的聚散">
    <label class="f">资料内容</label><textarea class="i" id="gText" rows="10" placeholder="粘贴课程笔记、讲解文字稿、项目规范原文……越具体越好。资料里没有的标准，AI 不会编造，会列为待确认。"></textarea>
    <div class="row" style="margin-top:8px"><button class="btn sm" id="gFiles">添加文件</button><span class="hint">支持 md、txt 文本和 png、jpg 图片。视频请先转写成文字稿。</span></div>
    <div id="gFileList" class="chips" style="margin-top:8px"></div><div id="gMsg"></div>
    <div class="row" style="margin-top:14px"><button class="btn primary" id="gStart">开始生成</button><span class="hint">通常需要 5–15 分钟，取决于资料长度</span></div>
    <div id="gProgress" style="margin-top:14px"></div>`;
  let files = [];
  const paintFiles = () => { $("#gFileList").innerHTML = files.map((f, i) => `<span class="badge b-gray">${esc(f.name)} <a href="javascript:void 0" data-i="${i}">×</a></span>`).join(""); $$("#gFileList a").forEach((a) => a.onclick = () => { files.splice(+a.dataset.i, 1); paintFiles(); }); };
  $("#gFiles").onclick = async () => { files = files.concat(await pickFiles(".md,.txt,.png,.jpg,.jpeg", true)); paintFiles(); };
  $("#gStart").onclick = async () => {
    msgBox($("#gMsg"), "");
    if (state.job && state.job.status === "running") return msgBox($("#gMsg"), "已有任务正在进行");
    try {
      const r = await api("/api/generate", { parent: $("#gParent").value, name: $("#gName").value, materials: $("#gText").value,
        files: await Promise.all(files.map(async (f) => ({ name: f.name, b64: await fileB64(f) }))) });
      state.job = { id: r.job_id, kind: "generate", status: "running", logs: [] };
      const paint = (j) => {
        const el = $("#gProgress"); if (!el) return;
        el.innerHTML = `<div class="logs">${(j.logs || []).map((l) => `${l.t}  ${esc(l.msg)}`).join("\n") || (j.status === "running" ? "准备中…" : "")}</div>
          ${j.status === "running" ? '<div class="msg info"><span class="spin"></span>生成中，请勿关闭页面</div>' : ""}
          ${j.error ? `<div class="msg err">${esc(j.error)}</div>` : ""}
          ${j.result ? `<div class="msg ok">已生成草稿：${esc(j.result.path)}（ID：${esc(j.result.block_id)}）</div>
            ${j.result.review_notes.length ? `<h3>需要人工确认</h3><ul style="padding-left:18px;margin:0">${j.result.review_notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
            ${j.result.warnings.length ? `<h3>检查警告</h3>${j.result.warnings.map((x) => `<div class="q" style="color:var(--warn)">! ${esc(x)}</div>`).join("")}` : ""}
            <div class="row" style="margin-top:10px"><button class="btn" id="gOpen">在知识库中审核</button></div>` : ""}`;
        if ($("#gOpen")) $("#gOpen").onclick = () => { const p = j.result.path; state.kb.sel = p; p.split("/").reduce((a, s) => { const x = a ? a + "/" + s : s; state.kb.open.add(x); return x; }, ""); state.kb.file = null; location.hash = "#kb"; };
      };
      paint(state.job); pollJob(paint);
    } catch (e) { msgBox($("#gMsg"), e.message); }
  };
}
async function paintSkill() {
  const s = await api("/api/skill"); const el = $("#skillCard");
  el.innerHTML = `<div class="row" style="justify-content:space-between"><h2 style="margin:0">知识库生成 skill</h2>${s.installed ? '<span class="badge b-ok">已安装</span>' : '<span class="badge b-bad">未安装</span>'}</div>
    ${s.installed ? `<div style="margin:10px 0"><b>${esc(s.name)}</b><div class="sub">${esc(s.description)}</div></div>` : ""}
    <div class="row" style="gap:6px"><button class="btn sm" id="skUp">上传替换（zip）</button>${s.installed ? '<a class="btn sm" href="/api/skill/download">下载</a>' : ""}${s.has_default ? '<button class="btn sm" id="skReset">恢复默认</button>' : ""}</div>
    <div class="hint" style="margin-top:6px">生成时会读取 SKILL.md 和 references/ 下的全部文本。替换或编辑后立即生效，旧版本移到 data/trash。</div>
    <h3>文件 <span class="hint" style="font-weight:400">点击查看或编辑</span></h3>
    <div>${(s.files || []).map((f) => `<div class="fi" data-f="${esc(f.path)}" data-k="${f.kind}"><span>${esc(f.path)}</span><span>${(f.size / 1024).toFixed(1)}K</span></div>`).join("")}</div>`;
  $("#skUp").onclick = async () => { const [f] = await pickFiles(".zip"); if (!f) return; try { await api("/api/skill/replace", { b64: await fileB64(f) }); toast("skill 已替换"); paintSkill(); } catch (e) { alert(e.message); } };
  if ($("#skReset")) $("#skReset").onclick = async () => { if (!confirm("恢复为默认版本？当前版本会移到 data/trash")) return; await api("/api/skill/reset", {}); toast("已恢复默认"); paintSkill(); };
  $$("#skillCard .fi").forEach((x) => x.onclick = async () => {
    if (x.dataset.k !== "text") return toast("这个文件不能在这里编辑");
    const { content } = await api("/api/skill/file?path=" + encodeURIComponent(x.dataset.f));
    const m = modal(`<div class="row" style="justify-content:space-between"><b>${esc(x.dataset.f)}</b><div class="row" style="gap:6px"><button class="btn sm" id="skC">关闭</button><button class="btn sm primary" id="skS">保存</button></div></div>
      <textarea class="i code" id="skE" style="margin-top:10px;min-height:60vh" spellcheck="false"></textarea>`);
    m.querySelector(".modal").style.width = "900px";
    $("#skE", m).value = content; $("#skC", m).onclick = () => m.remove();
    $("#skS", m).onclick = async () => { try { await api("/api/skill/file", { path: x.dataset.f, content: $("#skE", m).value }); toast("已保存"); m.remove(); } catch (e) { alert(e.message); } };
  });
}

// ============================== 判定标准 ==============================
const TH = [
  ["pass_at", "条目合格线", "概率 ≥ 此值判合格"],
  ["fail_below", "条目不合格线", "概率 < 此值判不合格，之间为存疑"],
  ["block_pass_rate", "知识块合格率", "合格条目占比需大于此值"],
  ["veto_below", "一票否决线", "任一条目概率低于此值，知识块直接不合格"],
  ["gate", "元素核对线", "Jev 判断元素存在的概率低于此值，相关检查记为无法判断"],
];
async function renderJudging() {
  main().innerHTML = `<div class="empty">加载中…</div>`;
  const d = await api("/api/judging"); const j = d.judging;
  const blocks = d.blocks;
  main().innerHTML = `<div class="page-h"><div><h1>判定标准</h1><div class="sub">概率都先换算为“好的方向”的概率再比较。修改后对新的评审生效。</div></div><button class="btn primary" id="jSave">保存</button></div>
  <div id="jMsg"></div>
  <div class="card"><h2>默认规则</h2><div class="th-grid">${TH.map(([k, n, h]) => `<div><label class="f">${n}</label><input class="i" type="number" step="0.01" min="0" max="1" data-def="${k}" value="${j.default[k]}"><div class="hint">${h}</div></div>`).join("")}</div>
    <div class="scale" id="scale"></div></div>
  <div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">按知识块调整</h2><button class="btn sm" id="addB">添加</button></div>
    <div class="hint" style="margin:4px 0 8px">留空表示沿用默认值。</div><table class="t" id="bTbl"></table></div>
  <div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">按条目调整</h2><button class="btn sm" id="addC">添加</button></div>
    <div class="hint" style="margin:4px 0 8px">优先级：条目 &gt; 知识块 &gt; 默认。</div><table class="t" id="cTbl"></table></div>`;
  const bRows = Object.entries(j.blocks || {}).map(([k, v]) => ({ key: k, v }));
  const cRows = Object.entries(j.clauses || {}).map(([k, v]) => ({ key: k, v }));
  const bOpts = blocks.map((b) => [b.id, `${b.name}（${b.id}）`]);
  const cOpts = blocks.flatMap((b) => b.clauses.map((c) => [`${b.id}.${c.id}`, `${b.id}.${c.id} ${c.title}`]));
  const paintTbl = (sel, rows, opts) => {
    $(sel).innerHTML = rows.length ? `<tr><th style="width:30%">对象</th>${TH.map(([, n]) => `<th>${n}</th>`).join("")}<th></th></tr>` + rows.map((r, i) => `<tr>
      <td><select class="i" data-i="${i}" data-f="key">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === r.key ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></td>
      ${TH.map(([k]) => `<td><input class="i" type="number" step="0.01" min="0" max="1" data-i="${i}" data-f="${k}" value="${r.v[k] ?? ""}" placeholder="默认"></td>`).join("")}
      <td><button class="btn sm danger" data-del="${i}">移除</button></td></tr>`).join("") : '<tr><td class="hint">没有调整</td></tr>';
    $$(`${sel} [data-f]`).forEach((el) => el.oninput = () => { const r = rows[+el.dataset.i]; if (el.dataset.f === "key") r.key = el.value; else r.v[el.dataset.f] = el.value; });
    $$(`${sel} [data-del]`).forEach((el) => el.onclick = () => { rows.splice(+el.dataset.del, 1); paintTbl(sel, rows, opts); });
  };
  paintTbl("#bTbl", bRows, bOpts); paintTbl("#cTbl", cRows, cOpts);
  $("#addB").onclick = () => { if (!bOpts.length) return toast("没有可选的知识块"); bRows.push({ key: bOpts[0][0], v: {} }); paintTbl("#bTbl", bRows, bOpts); };
  $("#addC").onclick = () => { if (!cOpts.length) return toast("没有可选的条目"); cRows.push({ key: cOpts[0][0], v: {} }); paintTbl("#cTbl", cRows, cOpts); };
  const paintScale = () => {
    const pa = +$('[data-def="pass_at"]').value, fb = +$('[data-def="fail_below"]').value;
    $("#scale").innerHTML = `<div style="width:${fb * 100}%;background:#fee2e2;color:#991b1b">不合格 &lt;${fb}</div><div style="width:${Math.max(pa - fb, 0) * 100}%;background:#fef3c7;color:#92400e">存疑</div><div style="flex:1;background:#dcfce7;color:#166534">合格 ≥${pa}</div>`;
  };
  $$("[data-def]").forEach((el) => el.oninput = paintScale); paintScale();
  $("#jSave").onclick = async () => {
    const def = {}; $$("[data-def]").forEach((el) => def[el.dataset.def] = el.value);
    const pack = (rows) => { const o = {}; rows.forEach((r) => { if (o[r.key]) throw new Error(`${r.key} 重复`); o[r.key] = r.v; }); return o; };
    try { await api("/api/judging", { default: def, blocks: pack(bRows), clauses: pack(cRows) }); msgBox($("#jMsg"), "已保存，对新的评审生效", "ok"); }
    catch (e) { msgBox($("#jMsg"), e.message); }
  };
}

// ============================== 设置 ==============================
async function renderSettings() {
  const s = await api("/api/settings"); state.settings = s;
  const act = s.llm.active, provs = s.llm.providers;
  const cur = provs[act] || {};
  main().innerHTML = `<div class="page-h"><h1>设置</h1></div>
  <div class="grid2">
    <div class="card"><h2>Jev（TypeSafe）</h2>
      <div class="sub">用于逐项观察图片。在 console.typesafe.ai 获取 API Key。</div>
      <label class="f">API Key ${s.jev_key_mask ? `<span class="badge b-ok">已填写 ${esc(s.jev_key_mask)}</span>` : s.jev_env_fallback ? '<span class="badge b-blue">使用环境变量 TYPESAFE_API_KEY</span>' : '<span class="badge b-bad">未填写</span>'}</label>
      <input class="i" id="jevKey" type="password" placeholder="${s.jev_key_mask ? "留空则不修改" : "apikey_…"}" autocomplete="off">
      <div class="row" style="margin-top:12px"><button class="btn primary" id="jevSave">保存</button><button class="btn" id="jevTest">测试连接</button>${s.jev_key_mask ? '<button class="btn danger" id="jevClear">清除</button>' : ""}</div>
      <div id="jevMsg"></div>
      <label class="f" style="margin-top:16px">Jev 模型</label><div class="mono">${esc(s.model)}</div>
    </div>
    <div class="card"><h2>大模型</h2>
      <div class="sub">负责理解图片、检索知识库、复核与生成知识库。目前支持 OpenAI 兼容接口。</div>
      <label class="f">当前使用</label>
      <div class="row"><select class="i" id="llmSel" style="flex:1">${Object.entries(provs).map(([id, p]) => `<option value="${esc(id)}" ${id === act ? "selected" : ""}>${esc(p.label || p.model)}</option>`).join("")}<option value="__new">＋ 添加新的大模型</option></select></div>
      <div id="llmForm"></div><div id="llmMsg"></div>
    </div>
  </div>
  <div class="card"><h2>知识库位置</h2><div class="sub">评审和编辑都使用这个文件夹。</div>
    <div class="row" style="margin-top:10px"><input class="i" id="kbRootIn" style="flex:1" value="${esc(s.kb_root)}"><button class="btn" id="kbRootSave">保存</button></div><div id="kbMsg"></div></div>`;
  const form = (id) => {
    const p = id === "__new" ? { label: "", base_url: "", model: "", thinking_param: "" } : provs[id];
    $("#llmForm").innerHTML = `
      <label class="f">显示名称</label><input class="i" id="pLabel" value="${esc(p.label || "")}">
      <label class="f">接口地址（base_url）</label><input class="i" id="pBase" value="${esc(p.base_url || "")}" placeholder="https://…/v1">
      <label class="f">模型名称</label><input class="i" id="pModel" value="${esc(p.model || "")}">
      <label class="f">API Key ${p.api_key_mask ? `<span class="badge b-ok">已填写 ${esc(p.api_key_mask)}</span>` : ""}</label><input class="i" id="pKey" type="password" placeholder="${p.api_key_mask ? "留空则不修改" : ""}" autocomplete="off">
      <label class="f">思考模式参数名（可选）</label><input class="i" id="pThink" value="${esc(p.thinking_param || "")}" placeholder="千问为 enable_thinking；不支持则留空">
      <div class="hint">模型需要支持图片输入。</div>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="pSave">${id === "__new" ? "添加并使用" : "保存并使用"}</button><button class="btn" id="pTest">测试连接</button>${id !== "__new" && Object.keys(provs).length > 1 ? '<button class="btn danger" id="pDel">删除</button>' : ""}</div>`;
    $("#pSave").onclick = async () => {
      try {
        await api("/api/settings", { llm_provider: { id: id === "__new" ? null : id, label: $("#pLabel").value, base_url: $("#pBase").value, model: $("#pModel").value, api_key: $("#pKey").value, thinking_param: $("#pThink").value } });
        toast("已保存"); refreshNav(); renderSettings();
      } catch (e) { msgBox($("#llmMsg"), e.message); }
    };
    $("#pTest").onclick = async () => { msgBox($("#llmMsg"), "测试中…", "info"); try { const r = await api("/api/settings/test", { target: "llm" }); msgBox($("#llmMsg"), `连接正常（${r.seconds} 秒）：${r.detail}`, "ok"); } catch (e) { msgBox($("#llmMsg"), e.message); } };
    if ($("#pDel")) $("#pDel").onclick = async () => { if (!confirm("删除这个大模型配置？")) return; await api("/api/settings", { llm_delete: id }); refreshNav(); renderSettings(); };
  };
  form(act || "__new");
  $("#llmSel").onchange = async (e) => { if (e.target.value !== "__new") { await api("/api/settings", { llm_active: e.target.value }); refreshNav(); toast("已切换"); } form(e.target.value); };
  $("#jevSave").onclick = async () => { try { await api("/api/settings", { jev_api_key: $("#jevKey").value }); toast("已保存"); refreshNav(); renderSettings(); } catch (e) { msgBox($("#jevMsg"), e.message); } };
  $("#jevTest").onclick = async () => { msgBox($("#jevMsg"), "测试中…", "info"); try { const r = await api("/api/settings/test", { target: "jev" }); msgBox($("#jevMsg"), `连接正常（${r.seconds} 秒）。${r.detail}`, "ok"); } catch (e) { msgBox($("#jevMsg"), e.message); } };
  if ($("#jevClear")) $("#jevClear").onclick = async () => { if (!confirm("清除已保存的 Jev API Key？")) return; await api("/api/settings", { jev_clear: true }); refreshNav(); renderSettings(); };
  $("#kbRootSave").onclick = async () => { try { await api("/api/settings", { kb_root: $("#kbRootIn").value }); msgBox($("#kbMsg"), "已保存", "ok"); } catch (e) { msgBox($("#kbMsg"), e.message); } };
}

refreshNav();
route();
