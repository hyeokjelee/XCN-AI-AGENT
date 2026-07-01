/* 엑큐(XCU): 로그인 사용자 환영 배너를 왼쪽 사이드바 최상단에 삽입 */
(function () {
  let user = undefined;          // undefined=미조회, null=비로그인, {}=로그인
  let lastFetch = 0;

  async function fetchUser() {
    const now = Date.now();
    if (user) return user;                       // 이미 확보
    if (now - lastFetch < 2000) return user;     // 과도한 호출 방지
    lastFetch = now;
    try {
      const r = await fetch("/api/whoami", { credentials: "same-origin" });
      if (r.ok) { user = await r.json(); }
      else { user = null; }
    } catch (e) { user = null; }
    return user;
  }

  function makeBanner(name) {
    const b = document.createElement("div");
    b.id = "xcu-welcome-banner";
    b.textContent = name + " 님 환영합니다!";
    b.style.cssText =
      "margin:8px;padding:11px 14px;border-radius:10px;font-weight:600;font-size:14px;" +
      "text-align:center;color:#fff;background:linear-gradient(135deg,#6d5cf0,#9b5cf0);" +
      "box-shadow:0 4px 14px rgba(124,92,255,.35);";
    return b;
  }

  async function inject() {
    if (document.getElementById("xcu-welcome-banner")) return;
    // 왼쪽 사이드바(shadcn): data-sidebar="header" 우선, 없으면 sidebar 컨테이너
    const header = document.querySelector('[data-sidebar="header"]');
    const sidebar = document.querySelector('[data-sidebar="sidebar"]');
    const target = header || sidebar;
    if (!target) return;
    const u = await fetchUser();
    if (!u) return;  // 비로그인(로그인 화면)에서는 표시하지 않음
    if (document.getElementById("xcu-welcome-banner")) return;
    const name = u.display_name || u.identifier || "사용자";
    target.insertBefore(makeBanner(name), target.firstChild);
  }

  const obs = new MutationObserver(function () { inject(); });
  obs.observe(document.body, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", inject);
  inject();
})();

/* 엑큐(XCU): 선택한 에이전트를 설정(⚙️) 아이콘 옆에 칩으로 표시.
   값은 백엔드(/api/selected_agents)를 폴링 → 저장 즉시 반영(새로고침 불필요). */
(function () {
  let agents = [];

  async function fetchAgents() {
    try {
      const r = await fetch("/api/selected_agents", { credentials: "same-origin" });
      if (r.ok) {
        const d = await r.json();
        agents = Array.isArray(d.agents) ? d.agents : [];
      }
    } catch (e) { /* 무시 */ }
  }

  function findSettingsButton() {
    const sels = [
      "#chat-settings-open", "#chat-settings", "#settings-button",
      'button[aria-label*="setting" i]', 'button[title*="setting" i]',
      'button[aria-label*="설정"]', 'button[title*="설정"]',
    ];
    for (const s of sels) { const el = document.querySelector(s); if (el) return el; }
    return null;
  }

  function chip(label) {
    return '<span style="background:hsl(252 90% 96%);border:1px solid hsl(252 80% 85%);' +
           'color:hsl(255 60% 52%);border-radius:999px;padding:1px 8px;white-space:nowrap;">' +
           label + "</span>";
  }

  const BASE_STYLE =
    "display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;" +
    "max-width:460px;margin:0 8px;font-size:12px;font-weight:600;vertical-align:middle;";
  // 입력 박스 바로 위에 한 줄로 (컴포저의 형제로 삽입)
  const BAR_STYLE =
    "display:flex;align-items:center;gap:6px;flex-wrap:wrap;" +
    "margin:0 0 6px 2px;font-size:12px;font-weight:600;";
  const FIXED_STYLE =
    "position:fixed;bottom:96px;left:50%;transform:translateX(-50%);z-index:9999;" +
    "display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;max-width:70vw;" +
    "padding:6px 10px;border-radius:12px;background:hsl(0 0% 100% / .92);" +
    "box-shadow:0 4px 16px rgba(80,60,200,.18);font-size:12px;font-weight:600;";

  // 멱등 렌더: 위치/내용이 바뀔 때만 DOM을 건드린다.
  function render() {
    const html = agents.length
      ? agents.map(chip).join("")
      : '<span style="opacity:.5;font-weight:500;">에이전트 자동</span>';
    const anchor = findSettingsButton();

    let badge = document.getElementById("xcu-agent-badge");
    if (!badge) {
      badge = document.createElement("div");
      badge.id = "xcu-agent-badge";
    }
    // 앵커는 '실제로 화면에 보이는' 버튼일 때만 사용(숨은 버튼 오탐 방지).
    const anchorVisible = anchor && anchor.parentElement && anchor.offsetParent !== null;
    const composer = document.querySelector("#message-composer");
    let mode;
    if (anchorVisible) {
      // 1순위: 설정 버튼 옆
      if (badge.previousElementSibling !== anchor) {
        badge.style.cssText = BASE_STYLE;
        anchor.parentElement.insertBefore(badge, anchor.nextSibling);
      }
      mode = "anchor";
    } else if (composer && composer.parentElement) {
      // 2순위: 입력 박스 바로 위(컴포저의 형제로 삽입)
      if (badge.nextElementSibling !== composer) {
        badge.style.cssText = BAR_STYLE;
        composer.parentElement.insertBefore(badge, composer);
      }
      mode = "bar";
    } else {
      // 3순위: 화면 고정(무조건 보이게)
      if (badge.parentElement !== document.body || badge.style.position !== "fixed") {
        badge.style.cssText = FIXED_STYLE;
        document.body.appendChild(badge);
      }
      mode = "fixed";
    }
    const sig = mode + "|" + html;
    if (badge.getAttribute("data-sig") !== sig) {
      badge.innerHTML = html;
      badge.setAttribute("data-sig", sig);
    }
  }

  async function tick() {
    if (document.hidden) return;           // 탭이 안 보이면 폴링 중단(서버 부하 절감)
    await fetchAgents();
    render();
  }

  document.addEventListener("DOMContentLoaded", tick);
  setInterval(tick, 2500);  // 2.5초 폴링(탭 활성 시에만) → 설정 저장 후 수초 내 반영
  tick();
})();
