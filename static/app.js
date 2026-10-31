const $ = (s) => document.querySelector(s);
const state = { info: null, video: null, analysis: null, passed: false, posting: false, blocked: null };

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `요청 실패 (${r.status})`);
  return data;
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDate = (iso) => new Date(iso).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
const fmtViews = (n) => (n >= 10000 ? (n / 10000).toFixed(1) + "만" : n.toLocaleString()) + "회";

// ── 아이콘 (선 아이콘 SVG, Lucide 모양 참고) ──
const ICONS = {
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  play: '<rect x="2" y="4" width="20" height="16" rx="4"/><path d="m10 9 5 3-5 3z"/>',
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  refresh: '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/>',
  trending: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  rotate: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
};
const icon = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
const tile = (name, size = "sm") => `<span class="tile ${size}">${icon(name)}</span>`;
document.querySelectorAll("i[data-icon]").forEach((el) => (el.outerHTML = icon(el.dataset.icon)));

// ── 상단 상태 ──
async function refreshInfo() {
  state.info = await api("/api/info");
  const i = state.info;
  $("#pillToday").textContent = `오늘 게시 ${i.today_count}/${i.daily_max}`;
  $("#pillTodayWrap").classList.toggle("full", i.today_count >= i.daily_max);
  $("#logMax").textContent = i.daily_max;
  updateAssignHint();
}

// ── ① 영상 목록 ──
function renderList(videos, title) {
  $("#listTitle").textContent = title;
  const list = $("#list");
  if (!videos.length) { list.innerHTML = '<p class="empty">조건에 맞는 영상이 없습니다.</p>'; return; }
  list.innerHTML = videos.map((v) => `
    <div class="item${v.already_commented ? " done" : ""}" data-id="${v.id}">
      <img src="${esc(v.thumbnail)}" alt="">
      <div><div class="t">${esc(v.title)}</div>
        <div class="m">${esc(v.channel)} · ${fmtDate(v.published_at)}</div>
        <div class="m">조회 ${fmtViews(v.views)} · 시간당 ${Math.round(v.views_per_hour).toLocaleString()}회
          ${v.already_commented ? '<span class="tag">댓글 단 영상</span>' : ""}</div></div>
    </div>`).join("");
  list.querySelectorAll(".item").forEach((el) => (el.onclick = () => selectVideo(el.dataset.id, el)));
}

async function loadList(btn, path, title, label) {
  const lbl = btn.querySelector(".lbl");
  btn.disabled = true; lbl.textContent = "불러오는 중…";
  try { renderList(await api(path), title); }
  catch (e) { $("#list").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  finally { btn.disabled = false; lbl.textContent = label; }
}

$("#btnLoad").onclick = () => loadList($("#btnLoad"), "/api/videos", "최신 영상", "영상 불러오기");
$("#btnRising").onclick = () => loadList($("#btnRising"), "/api/rising", "뜨기 직전 영상 (시간당 조회수 순) · 자동 게시하지 않습니다", "뜨기 직전 영상 찾기");
$("#btnLink").onclick = () => { const v = $("#link").value.trim(); if (v) selectVideo(v, null); };
$("#link").onkeydown = (e) => { if (e.key === "Enter") $("#btnLink").click(); };

function selectVideo(idOrLink, el) {
  document.querySelectorAll(".item.on").forEach((x) => x.classList.remove("on"));
  if (el) el.classList.add("on");
  state.analysis = null;
  makeDraft(idOrLink);
}

// ── ② 분석 + 초안 ──
let draftSeq = 0;   // 분석 중에 다른 영상을 고르면 늦게 도착한 이전 결과는 버린다
async function makeDraft(idOrLink, keepAnalysis = false) {
  const seq = ++draftSeq;
  $("#draftEmpty").hidden = true; $("#draftBox").hidden = true; $("#loading2").hidden = false;
  const analysis = keepAnalysis ? state.analysis : null;
  state.video = null; state.passed = false; updatePostBtn();
  try {
    const body = { video: idOrLink, analysis };
    const d = await api("/api/draft", { method: "POST", body: JSON.stringify(body) });
    if (seq !== draftSeq) return;
    state.video = d.video; state.analysis = d.analysis;
    renderDraft(d);
    checkCanPost();
  } catch (e) {
    if (seq !== draftSeq) return;
    $("#draftEmpty").hidden = false;
    $("#draftEmpty").innerHTML = `<span class="err">${esc(e.message)}</span>`;
  } finally { if (seq === draftSeq) $("#loading2").hidden = true; }
}

function renderDraft(d) {
  const v = d.video;
  $("#selVideo").innerHTML = `<img src="${esc(v.thumbnail)}" alt=""><div><b>${esc(v.title)}</b>
    <div class="hint">${esc(v.channel)}${d.transcript_source ? " · 자막: " + esc(d.transcript_source) : ""}</div></div>`;
  $("#worry").textContent = d.analysis.worry;
  $("#moments").innerHTML = d.analysis.key_moments.map((m) => `<li>${esc(m)}</li>`).join("");
  $("#comment").value = d.comment;
  $("#attempts").innerHTML = d.attempts.map((a) =>
    `<li>${esc(a.text)}${a.fails.length
      ? `<div class="att bad">${icon("x")}${esc(a.fails.join(", "))}</div>`
      : `<div class="att">${icon("check")}통과</div>`}</li>`).join("");
  showChecks(d.attempts.at(-1).fails, d.attempts.length);
  $("#draftBox").hidden = false;
}

function showChecks(fails, tries) {
  const n = $("#comment").value.trim().length, c = state.info.comment;
  $("#count").textContent = `${n}자 / ${c.min_chars}~${c.max_chars}자`;
  $("#checks").innerHTML = fails.length
    ? `${tile("x")}<span class="bad">규칙 위반: ${esc(fails.join(" · "))}${tries > 1 ? ` (${tries}회 시도 후)` : ""}</span>`
    : `${tile("check")}<span>규칙 검사 통과</span>`;
  state.passed = !fails.length;
  updatePostBtn();
}

let checkTimer;
$("#comment").oninput = () => {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(async () => {
    try {
      const { fails } = await api("/api/check", { method: "POST", body: JSON.stringify({ text: $("#comment").value }) });
      showChecks(fails, 0);
    } catch (e) { showChecks([`검사 실패: ${e.message}`], 0); }
  }, 300);
};

$("#btnRegen").onclick = () => state.video && makeDraft(state.video.id, true);
$("#btnReanalyze").onclick = () => state.video && makeDraft(state.video.id, false);

// ── ③ 게시 ──
const selectedProfile = () => ($("#autoAssign").checked ? null : $("#profile").value);

function updateAssignHint() {
  const auto = $("#autoAssign").checked;
  $("#profile").disabled = auto;
  $("#assignHint").textContent = auto ? `다음 차례: ${state.assigned || state.info?.next_profile || "-"}` : "선택한 계정으로 게시합니다.";
}

async function checkCanPost() {
  if (!state.video) return;
  try {
    const q = new URLSearchParams({ video_id: state.video.id });
    if (selectedProfile()) q.set("profile", selectedProfile());
    const r = await api(`/api/can_post?${q}`);
    state.blocked = r.reason; state.assigned = r.profile;
  } catch (e) { state.blocked = e.message; }
  updateAssignHint(); updatePostBtn();
}

function updatePostBtn() {
  let why = "";
  if (state.posting) why = "게시 진행 중입니다…";
  else if (!state.video) why = "2단계에서 초안을 먼저 만들어 주세요.";
  else if (!state.passed) why = "초안이 규칙 검사를 통과해야 게시할 수 있습니다.";
  else if (state.blocked) why = state.blocked;
  $("#btnPost").disabled = !!why;
  $("#postWhy").textContent = why;
  $("#postWhy").classList.toggle("err", !!state.blocked && !state.posting && state.passed);
}

$("#autoAssign").onchange = () => { updateAssignHint(); checkCanPost(); };
$("#profile").onchange = checkCanPost;

function renderSteps(job) {
  $("#steps").hidden = false;
  $("#steps").innerHTML = job.steps.map((s, i) => {
    let cls = i < job.step_index ? "done" : i === job.step_index ? "now" : "";
    if (job.status === "failed" && i === job.step_index) cls = "fail";
    if (job.status === "success") cls = "done";
    const extra = s === "입력 중" && i <= job.step_index ? ` (${job.typed}/${job.total}자)` : "";
    const mark = cls === "done" ? tile("check") : cls === "fail" ? tile("x") : '<span class="tile sm"><i class="dot"></i></span>';
    return `<li class="${cls}">${mark}<span>${esc(s)}${extra}</span></li>`;
  }).join("");
}

$("#btnPost").onclick = async () => {
  state.posting = true; updatePostBtn(); $("#postResult").innerHTML = "";
  try {
    const { job_id, profile } = await api("/api/post", { method: "POST",
      body: JSON.stringify({ video_id: state.video.id, text: $("#comment").value, profile: selectedProfile() }) });
    $("#assignHint").textContent = `게시 계정: ${profile}`;
    await new Promise((resolve, reject) => {
      const tick = async () => {
        let job;
        try { job = await api(`/api/post/${job_id}`); } catch (e) { return reject(e); }
        renderSteps(job);
        if (job.status === "running") return setTimeout(tick, 1000);
        if (job.status === "success") {
          $("#postResult").innerHTML = `<div class="result">${tile("check", "")}<div><b>게시 완료</b>${esc(job.profile)} 계정
            ${job.comment_url ? ` · <a href="${esc(job.comment_url)}" target="_blank" rel="noopener">댓글 보기${icon("external")}</a>` : ""}</div></div>`;
        } else {
          $("#postResult").innerHTML = `<div class="result bad">${tile("x", "")}<div><b>게시 실패</b><span class="msg">${esc(job.reason)}</span>
            ${job.screenshot ? `<a href="/shots/${esc(job.screenshot)}" target="_blank"><img src="/shots/${esc(job.screenshot)}" alt="실패 화면"></a>` : ""}</div></div>`;
        }
        resolve();
      };
      tick();
    });
  } catch (e) {
    $("#postResult").innerHTML = `<div class="result bad">${tile("x", "")}<div><b>게시 실패</b><span class="msg">${esc(e.message)}</span></div></div>`;
  } finally {
    state.posting = false;
    await Promise.all([refreshInfo(), loadLog()]);
    await checkCanPost();
  }
};

// ── 기록 ──
async function loadLog() {
  const rows = await api("/api/log");
  $("#logBody").innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td class="nowrap">${esc(r.created_at.slice(5, 16).replace("T", " "))}</td>
      <td class="title" title="${esc(r.title)}">${esc(r.title)}</td>
      <td class="nowrap">${esc(r.profile)}</td>
      <td class="cmt">${esc(r.comment)}</td>
      <td><span class="st ${r.status === "성공" ? "ok" : "bad"}">${tile(r.status === "성공" ? "check" : "x")}${esc(r.status)}</span></td>
      <td>${r.comment_url ? `<a href="${esc(r.comment_url)}" target="_blank" rel="noopener">댓글 보기${icon("external")}</a>` : ""}
          ${r.reason ? `<span class="bad">${esc(r.reason)}</span>` : ""}
          ${r.screenshot ? `<a href="/shots/${esc(r.screenshot)}" target="_blank"><img class="shot" src="/shots/${esc(r.screenshot)}" alt=""></a>` : ""}</td>
    </tr>`).join("") : '<tr><td colspan="6" class="empty">아직 기록이 없습니다.</td></tr>';
}

// ── 시작 ──
(async () => {
  await refreshInfo();
  const i = state.info;
  $("#q").textContent = i.search.query;
  $("#pillModel").textContent = `AI: ${i.model}`;
  $("#profile").innerHTML = i.profiles.map((p) => `<option>${esc(p)}</option>`).join("");
  $("#autoAssign").checked = i.assignment === "round_robin";
  const r = i.rising;
  $("#risingHint").textContent = `뜨기 직전 = 최근 ${r.hours}시간 업로드 · 조회 ${r.min_views.toLocaleString()}~${r.max_views.toLocaleString()}회 · 시간당 ${r.min_views_per_hour}회 이상 (초안까지만, 자동 게시 없음)`;
  updateAssignHint();
  const missing = Object.entries(i.keys).filter(([, ok]) => !ok).map(([k]) => k);
  if (missing.length) {
    $("#keyWarn").hidden = false;
    $("#keyWarn").textContent = `.env 에 ${missing.join(", ")} 값이 없습니다. 키를 넣고 서버를 다시 실행하세요.`;
  }
  loadLog();
})();
