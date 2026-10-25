/* RE Launcher para Android.
   O catálogo vem de data.json (gerado por tools/mobile_data.py a partir de games/).
   No app, o fetch passa pelo CapacitorHttp (sem bloqueio de CORS): notícias do REVIL e lives da Twitch e do YouTube. */
"use strict";

const ICONS = {
  timeline: '<path d="M3 12h18M6 12V8m6 4v6m6-6V8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="6" cy="7" r="2" fill="currentColor"/><circle cx="12" cy="19" r="2" fill="currentColor"/><circle cx="18" cy="7" r="2" fill="currentColor"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="13" y="4" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="4" y="13" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="13" y="13" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/>',
  phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M11 18h2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  doc: '<path d="M7 3h7l4 4v14H7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/><path d="M10 12h5M10 16h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  live: '<circle cx="12" cy="12" r="2.5" fill="currentColor"/><path d="M7.5 7.5a6.4 6.4 0 0 0 0 9M16.5 7.5a6.4 6.4 0 0 1 0 9M4.6 4.6a10.5 10.5 0 0 0 0 14.8M19.4 4.6a10.5 10.5 0 0 1 0 14.8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  down: '<path d="M12 4v11m-5-5 5 5 5-5M5 20h14" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  link: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="12" r="3" fill="currentColor"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
};
const svg = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const SECTIONS = [
  { id: "canon", nome: "Linha do tempo", icon: "timeline" },
  { id: "spinoff", nome: "Não canônicos", icon: "grid" },
  { id: "celular", nome: "No celular", icon: "phone" },
  { id: "noticias", nome: "Notícias", icon: "doc" },
  { id: "aovivo", nome: "Ao vivo", icon: "live" },
];
const KIND = {
  android: ["Joga-se no Android", "var(--green)"], ios: ["Joga-se no iPhone, iPad ou Mac", "var(--blue)"],
  andamento: ["Em andamento", "#e0a23b"], pc: ["Só no PC (RE Launcher)", "var(--muted)"],
};
const TWITCH_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko";   // identificador público que o site da Twitch usa

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sem armazenamento: tudo bem */ } },
};

let DATA = null;
const state = { section: store.get("secao", "canon"), sel: store.get("sel", {}), ver: store.get("ver", {}) };

function openUrl(url) {
  if (!url) return;
  const b = window.Capacitor?.Plugins?.Browser;
  if (b) b.open({ url, toolbarColor: "#0b0a09" });
  else window.open(url, "_blank");
}

function setBg(url) {
  $("#bg").style.backgroundImage = url ? `url("${url}")` : "none";
}

/* ---------- barra de baixo ---------- */
function renderNav() {
  $("#nav").innerHTML = SECTIONS.map((s) =>
    `<button class="nav-btn${s.id === state.section ? " on" : ""}" data-sec="${s.id}" aria-label="${s.nome}">${svg(s.icon)}<span>${s.nome}</span></button>`).join("");
  $("#nav").querySelectorAll(".nav-btn").forEach((b) => b.onclick = () => go(b.dataset.sec));
}

function go(sec) {
  state.section = sec;
  store.set("secao", sec);
  renderNav();
  $("#view").scrollTop = 0;
  ({ canon: timeline, spinoff: timeline, celular: mobile, noticias: news, aovivo: lives })[sec]();
}

/* ---------- linha do tempo e não canônicos ---------- */
function coverHtml(item, title) {
  return item.capa
    ? `<img src="${esc(item.capa)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'poster',textContent:${esc(JSON.stringify(title))}}))">`
    : `<div class="poster">${esc(title)}</div>`;
}

function timeline() {
  const sec = DATA.secoes.find((s) => s.id === state.section);
  const chs = sec.capitulos;
  const i = Math.min(state.sel[sec.id] ?? 0, chs.length - 1);
  $("#view").innerHTML = `
    <div class="carousel">${chs.map((c, k) => `
      <button class="tile${k === i ? " on" : ""}" data-k="${k}">
        <div class="cover">${coverHtml(c, c.titulo)}</div><div class="year">${esc(c.ano)}</div>
      </button>`).join("")}</div>
    <div class="details" id="details"></div>`;
  const car = $(".carousel");
  car.querySelectorAll(".tile").forEach((t) => t.onclick = () => pick(+t.dataset.k));
  requestAnimationFrame(() => car.children[i]?.scrollIntoView({ inline: "center", block: "nearest" }));
  showChapter(chs[i]);

  function pick(k) {
    state.sel[sec.id] = k;
    store.set("sel", state.sel);
    car.querySelectorAll(".tile").forEach((t, n) => t.classList.toggle("on", n === k));
    car.children[k].scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    showChapter(chs[k]);
  }
}

function showChapter(ch) {
  const vi = Math.min(state.ver[ch.id] ?? 0, ch.versoes.length - 1);
  const v = ch.versoes[vi];
  setBg(v.fundo || ch.fundo || v.capa || ch.capa);
  const [kind, color] = KIND[v.jogar.tipo] || KIND.pc;
  const icon = v.jogar.tipo === "android" ? "down" : v.jogar.tipo === "andamento" ? "eye" : "link";
  $("#details").innerHTML = `
    <h1>${esc(ch.titulo)}</h1>
    <div class="meta">${[ch.quando, ch.onde].filter(Boolean).map(esc).join("  ·  ")}${ch.ano ? `  ·  lançado em <b>${esc(ch.ano)}</b>` : ""}</div>
    <p class="synopsis">${esc(ch.sinopse)}</p>
    ${ch.versoes.length > 1 ? `<div class="pills">${ch.versoes.map((x, k) =>
      `<button class="pill${k === vi ? " on" : ""}" data-k="${k}">${esc(x.versao)}</button>`).join("")}</div>` : ""}
    <div class="card">
      <div class="kind" style="color:${color}">${kind}</div>
      <p>${esc(v.status || v.dica || v.nome)}</p>
      ${v.jogar.url ? `<button class="btn${v.jogar.tipo === "pc" ? " ghost" : ""}" id="act">${svg(icon)}${esc(v.jogar.rotulo)}</button>` : ""}
    </div>`;
  $("#details").querySelectorAll(".pill").forEach((p) => p.onclick = () => {
    state.ver[ch.id] = +p.dataset.k;
    store.set("ver", state.ver);
    showChapter(ch);
  });
  const act = $("#act");
  if (act) act.onclick = () => openUrl(v.jogar.url);
}

/* ---------- no celular: tudo que roda (ou vai rodar) no Android e no iPhone ---------- */
function mobile() {
  setBg(null);
  const all = DATA.secoes.flatMap((s) => s.capitulos.flatMap((c) => c.versoes.map((v) => ({ ...v, cap: c }))));
  const groups = [
    ["Android", all.filter((v) => v.jogar.tipo === "android")],
    ["iPhone, iPad e Mac", all.filter((v) => v.jogar.tipo === "ios")],
    ["Ports para Android em andamento", all.filter((v) => v.jogar.tipo === "andamento" && /android|mobile/i.test(v.versao + v.nome))],
  ];
  $("#view").innerHTML = groups.filter(([, items]) => items.length).map(([title, items]) => `
    <div class="section-title">${esc(title)}</div>
    <div class="list">${items.map((v) => {
      const [kind, color] = KIND[v.jogar.tipo];
      return `<button class="row" data-url="${esc(v.jogar.url)}">
        <div class="thumb">${coverHtml(v.capa ? v : v.cap, v.cap.titulo)}</div>
        <div class="txt"><div class="t">${esc(v.nome)}</div><div class="s">${esc(v.status || v.dica)}</div>
          <div class="tag" style="color:${color}">${esc(v.jogar.rotulo)}  ·  ${kind}</div></div></button>`;
    }).join("")}</div>`).join("") + `<p class="note">Os jogos para PC e os de emulador ficam no RE Launcher do computador.</p>`;
  $("#view").querySelectorAll(".row").forEach((r) => r.onclick = () => openUrl(r.dataset.url));
}

/* ---------- notícias (feed do REVIL) ---------- */
async function news() {
  setBg(null);
  const fonte = DATA.noticias.fonte || "notícias";
  $("#view").innerHTML = `<div class="toolbar"><span class="count">${esc(fonte)}</span></div><div class="spin"></div>`;
  try {
    const xml = new DOMParser().parseFromString(await (await fetch(DATA.noticias.feed)).text(), "text/xml");
    const items = [...xml.getElementsByTagName("item")].slice(0, 20).map((it) => {
      const get = (t) => it.getElementsByTagName(t)[0]?.textContent || "";
      const html = it.getElementsByTagNameNS("http://purl.org/rss/1.0/modules/content/", "encoded")[0]?.textContent || get("description");
      const img = (html.match(/<img[^>]+src="([^"]+)"/) || [])[1] || "";
      const d = new Date(get("pubDate"));
      return { t: get("title"), link: get("link"), img, when: isNaN(d) ? "" : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) };
    });
    if (state.section !== "noticias") return;
    $("#view").innerHTML = `<div class="toolbar"><span class="count">${esc(fonte)}  ·  ${items.length} notícias</span></div>
      <div class="list">${items.map((n) => `<button class="row" data-url="${esc(n.link)}">
        <div class="thumb wide">${n.img ? `<img src="${esc(n.img)}" alt="" loading="lazy">` : ""}</div>
        <div class="txt"><div class="t">${esc(n.t)}</div><div class="s">${esc(n.when)}</div></div></button>`).join("")}</div>`;
    $("#view").querySelectorAll(".row").forEach((r) => r.onclick = () => openUrl(r.dataset.url));
  } catch {
    if (state.section === "noticias") $("#view").innerHTML = `<p class="note">Não deu para carregar as notícias agora. Confira a internet.</p>`;
  }
}

/* ---------- ao vivo: todas as lives de Resident Evil agora ---------- */
async function gql(query) {
  const r = await fetch("https://gql.twitch.tv/gql", {
    method: "POST", headers: { "Client-ID": TWITCH_ID, "Content-Type": "application/json" }, body: JSON.stringify({ query }),
  });
  return (await r.json()).data || {};
}

async function twitchLives() {
  const found = await gql('query { searchCategories(query: "Resident Evil", first: 40) { edges { node { id name viewersCount } } } }');
  const cats = (found.searchCategories?.edges || []).map((e) => e.node).filter((n) => n.viewersCount)
    .sort((a, b) => b.viewersCount - a.viewersCount).slice(0, 10);
  const fields = "edges { node { title viewersCount broadcaster { login displayName } previewImageURL(width: 640, height: 360) } }";
  const parts = await Promise.all(cats.map((c) => gql(`query {
    p: game(id: "${c.id}") { name streams(first: 4, options: {languages: ["pt"]}) { ${fields} } }
    a: game(id: "${c.id}") { name streams(first: 3) { ${fields} } } }`).catch(() => ({}))));
  const out = [], seen = new Set();
  for (const part of parts) {
    for (const [key, game] of Object.entries(part).sort(([a]) => (a === "p" ? -1 : 1))) {
      for (const { node: n } of game?.streams?.edges || []) {
        const login = n.broadcaster?.login;
        if (!login || seen.has(login)) continue;
        seen.add(login);
        out.push({ plat: "Twitch", pt: key === "p", n: n.viewersCount || 0, canal: n.broadcaster.displayName || login,
          titulo: n.title || "Ao vivo", img: n.previewImageURL, cat: game.name, url: `https://www.twitch.tv/${login}` });
      }
    }
  }
  return out;
}

async function youtubeLives() {
  const page = await (await fetch("https://www.youtube.com/results?search_query=resident+evil&sp=EgJAAQ%253D%253D")).text();
  const m = page.match(/var ytInitialData = (\{.*?\});<\/script>/);
  if (!m) return [];
  const found = [];
  (function walk(o) {
    if (Array.isArray(o)) o.forEach(walk);
    else if (o && typeof o === "object") {
      if (o.videoRenderer?.videoId) found.push(o.videoRenderer);
      Object.values(o).forEach(walk);
    }
  })(JSON.parse(m[1]));
  return found.map((v) => {
    const views = (v.viewCountText?.runs || []).map((r) => r.text).join("");
    if (!/assistindo|watching/.test(views)) return null;
    return { plat: "YouTube", pt: false, n: +views.replace(/\D/g, "") || 0, canal: v.ownerText?.runs?.[0]?.text || "",
      titulo: (v.title?.runs || []).map((r) => r.text).join(""), img: `https://i.ytimg.com/vi/${v.videoId}/hqdefault_live.jpg`,
      cat: "", url: `https://www.youtube.com/watch?v=${v.videoId}` };
  }).filter(Boolean);
}

async function lives(force) {
  setBg(null);
  const cached = store.get("lives", null);
  const fresh = cached && Date.now() - cached.quando < 3 * 60 * 1000;
  if (fresh && !force) return showLives(cached.lista);
  $("#view").innerHTML = `<div class="spin"></div>`;
  const res = await Promise.allSettled([twitchLives(), youtubeLives()]);
  const all = res.flatMap((r) => (r.status === "fulfilled" ? r.value : []));
  const pt = all.filter((l) => l.pt).sort((a, b) => b.n - a.n).slice(0, 12);
  const rest = all.filter((l) => !l.pt).sort((a, b) => b.n - a.n);
  const lista = [...pt, ...rest].slice(0, 30);
  if (lista.length) store.set("lives", { quando: Date.now(), lista });
  if (state.section === "aovivo") showLives(lista.length ? lista : cached?.lista || []);
}

function showLives(lista) {
  $("#view").innerHTML = `<div class="toolbar"><span class="count">${lista.length} lives agora</span>
      <button class="small-btn" id="reload">Atualizar</button></div>
    ${lista.length ? `<div class="list">${lista.map((l) => `<button class="row" data-url="${esc(l.url)}">
      <div class="thumb wide"><img src="${esc(l.img)}" alt="" loading="lazy"><span class="live-dot">AO VIVO</span></div>
      <div class="txt"><div class="t">${esc(l.titulo)}</div>
        <div class="s">${esc(l.canal)}${l.cat ? "  ·  " + esc(l.cat) : ""}</div>
        <div class="tag" style="color:${l.plat === "Twitch" ? "#b18cff" : "#ff6b6b"}">${l.plat}  ·  ${l.n.toLocaleString("pt-BR")} assistindo${l.pt ? "  ·  PT" : ""}</div>
      </div></button>`).join("")}</div>`
      : `<p class="note">Nenhuma live encontrada agora (ou sem internet).</p>`}`;
  $("#reload").onclick = () => lives(true);
  $("#view").querySelectorAll(".row").forEach((r) => r.onclick = () => openUrl(r.dataset.url));
}

/* ---------- início ---------- */
function tick() {
  $("#clock").textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

async function start() {
  DATA = await (await fetch("data.json")).json();
  $("#intro").addEventListener("click", () => {
    $("#intro").classList.add("out");
    $("#app").hidden = false;
    renderNav();
    go(SECTIONS.some((s) => s.id === state.section) ? state.section : "canon");
    tick();
    setInterval(tick, 15000);
  }, { once: true });
  window.Capacitor?.Plugins?.App?.addListener?.("backButton", () => {
    if (state.section !== "canon") go("canon");
  });
}

start();
