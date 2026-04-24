/* =========================================================
 * IBTicket · Operations Console
 * Frontend client for the ticket triage workspace.
 * Plain JS, no framework. Designed to feel like a product.
 * ========================================================= */

"use strict";

/* ----------------------------- State ----------------------------- */

const DEFAULTS = Object.freeze({
  page: 1,
  perPage: 25,
  q: "",
  type: "",
  user: "",
  statuses: [],
  responded: "",
  dateFrom: "",
  dateTo: "",
  sort: "created_at",
  order: "desc",
});

const state = {
  ...DEFAULTS,
  statuses: [],
  total: 0,
  totalPages: 1,
  ticketsById: new Map(),
  facets: { statuses: [], types: [] },
  capabilities: { has_customer: true, has_priority: false, has_answer: false, has_type: false },
  isLoading: false,
  lastRequestedAt: 0,
  lastLoadMs: null,
};

/* ----------------------------- DOM ----------------------------- */

const $ = (id) => document.getElementById(id);

const dom = {
  // Topbar
  qInput: $("qInput"),
  refreshBtn: $("refreshBtn"),
  newTicketBtn: $("newTicketBtn"),

  // KPI
  kpiTotal: $("kpiTotal"),
  kpiTotalHint: $("kpiTotalHint"),
  kpiPending: $("kpiPending"),
  kpiResolved: $("kpiResolved"),
  kpiUpdated: $("kpiUpdated"),
  kpiLatency: $("kpiLatency"),

  // Filters
  toggleFiltersBtn: $("toggleFiltersBtn"),
  clearFiltersBtn: $("clearFiltersBtn"),
  filters: $("filters"),
  typeSelect: $("typeSelect"),
  userInput: $("userInput"),
  statusChips: $("statusChips"),
  respondedSegs: document.querySelectorAll(".segmented [data-responded]"),
  dateFromInput: $("dateFromInput"),
  dateToInput: $("dateToInput"),
  sortSelect: $("sortSelect"),
  orderBtn: $("orderBtn"),
  orderLabel: $("orderLabel"),
  perPageSelect: $("perPageSelect"),
  activeChips: $("activeChips"),

  // Table
  tableWrap: $("tableWrap"),
  ticketsBody: $("ticketsBody"),
  emptyState: $("emptyState"),
  emptyClearBtn: $("emptyClearBtn"),
  errorState: $("errorState"),
  errorStateMsg: $("errorStateMsg"),
  errorRetryBtn: $("errorRetryBtn"),
  tableHead: document.querySelector(".tickets-table thead"),

  // Pager
  pageInfo: $("pageInfo"),
  pagerPages: $("pagerPages"),
  firstBtn: $("firstBtn"),
  prevBtn: $("prevBtn"),
  nextBtn: $("nextBtn"),
  lastBtn: $("lastBtn"),

  // Health
  healthDot: $("healthDot"),
  healthText: $("healthText"),

  // Drawer
  drawer: $("newDrawer"),
  form: $("newTicketForm"),
  emailInput: $("emailInput"),
  messageInput: $("messageInput"),
  createBtn: $("createBtn"),
  formFeedback: $("formFeedback"),

  // Ticket modal
  ticketModal: $("ticketModal"),
  modalTicketId: $("modalTicketId"),
  modalTicketSubject: $("modalTicketSubject"),
  modalTicketBody: $("modalTicketBody"),

  // Toasts
  toastStack: $("toastStack"),
};

/* ----------------------------- Helpers ----------------------------- */

function debounce(fn, ms = 300) {
  let t;
  return function debounced(...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value ?? "");
  return div.innerHTML;
}

function isResolved(status) {
  const v = String(status || "").toLowerCase();
  return v === "resolved" || v === "closed";
}

function initialsFor(name, email) {
  const src = (name || email || "?").trim();
  if (!src) return "?";
  const parts = src.replace(/@.*/, "").split(/[\s._-]+/).filter(Boolean);
  if (!parts.length) return src.slice(0, 2).toUpperCase();
  const a = parts[0][0] || "";
  const b = parts.length > 1 ? parts[parts.length - 1][0] : (parts[0][1] || "");
  return (a + b).toUpperCase();
}

function avatarHue(seed) {
  const s = String(seed || "");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
}

function formatDate(epoch) {
  if (!epoch) return { abs: "—", rel: "" };
  const date = new Date(Number(epoch) * 1000);
  if (Number.isNaN(date.getTime())) return { abs: "—", rel: "" };
  const abs = date.toLocaleString("es-ES", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
  const diffMs = Date.now() - date.getTime();
  const rel = relativeTime(diffMs);
  return { abs, rel };
}

function relativeTime(diffMs) {
  const past = diffMs >= 0;
  const abs = Math.abs(diffMs);
  const min = Math.round(abs / 60000);
  if (min < 1) return past ? "justo ahora" : "en instantes";
  if (min < 60) return past ? `hace ${min} min` : `en ${min} min`;
  const hr = Math.round(min / 60);
  if (hr < 24) return past ? `hace ${hr} h` : `en ${hr} h`;
  const day = Math.round(hr / 24);
  if (day < 30) return past ? `hace ${day} d` : `en ${day} d`;
  const mo = Math.round(day / 30);
  if (mo < 12) return past ? `hace ${mo} mes${mo === 1 ? "" : "es"}` : `en ${mo} m`;
  const yr = Math.round(mo / 12);
  return past ? `hace ${yr} a` : `en ${yr} a`;
}

function statusTone(status) {
  const s = String(status || "").toLowerCase();
  if (s === "resolved" || s === "closed") return "ok";
  if (s === "open" || s === "new") return "info";
  if (s === "pending" || s === "waiting") return "warn";
  if (s === "escalated" || s === "blocked") return "danger";
  return "";
}

function formatStatusLabel(s) {
  if (!s) return "—";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatTypeLabel(s) {
  if (!s) return "—";
  return String(s)
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function bodyTextForModal(ticket) {
  const text = String(ticket?.body || "").trim();
  return text || "Este ticket no tiene body disponible.";
}

/* ----------------------------- HTTP ----------------------------- */

async function requestJSON(url, options = {}) {
  const opts = { ...options };
  opts.headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(options.headers || {}),
  };
  const response = await fetch(url, opts);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function buildListUrl() {
  const params = new URLSearchParams();
  params.set("page", String(state.page));
  params.set("per_page", String(state.perPage));
  if (state.q) params.set("q", state.q);
  if (state.type) params.set("type", state.type);
  if (state.user) params.set("user", state.user);
  if (state.statuses.length) params.set("status", state.statuses.join(","));
  if (state.responded) params.set("responded", state.responded);
  if (state.dateFrom) params.set("date_from", state.dateFrom);
  if (state.dateTo) params.set("date_to", state.dateTo);
  if (state.sort && state.sort !== DEFAULTS.sort) params.set("sort", state.sort);
  if (state.order && state.order !== DEFAULTS.order) params.set("order", state.order);
  return `/api/tickets?${params.toString()}`;
}

/* ----------------------------- URL sync ----------------------------- */

function readStateFromURL() {
  const p = new URLSearchParams(window.location.search);
  state.page = Math.max(1, Number(p.get("page") || DEFAULTS.page) || 1);
  const perPage = Number(p.get("per_page") || DEFAULTS.perPage) || DEFAULTS.perPage;
  state.perPage = [10, 25, 50, 100].includes(perPage) ? perPage : DEFAULTS.perPage;
  state.q = p.get("q") || "";
  state.type = (p.get("type") || p.get("subject") || "").trim().toLowerCase();
  state.user = p.get("user") || "";
  state.statuses = (p.get("status") || "").split(",").map((s) => s.trim()).filter(Boolean);
  state.responded = ["yes", "no"].includes(p.get("responded") || "") ? p.get("responded") : "";
  state.dateFrom = p.get("date_from") || "";
  state.dateTo = p.get("date_to") || "";
  state.sort = p.get("sort") || DEFAULTS.sort;
  state.order = p.get("order") === "asc" ? "asc" : "desc";
}

function writeStateToURL() {
  const p = new URLSearchParams();
  if (state.page !== 1) p.set("page", state.page);
  if (state.perPage !== DEFAULTS.perPage) p.set("per_page", state.perPage);
  if (state.q) p.set("q", state.q);
  if (state.type) p.set("type", state.type);
  if (state.user) p.set("user", state.user);
  if (state.statuses.length) p.set("status", state.statuses.join(","));
  if (state.responded) p.set("responded", state.responded);
  if (state.dateFrom) p.set("date_from", state.dateFrom);
  if (state.dateTo) p.set("date_to", state.dateTo);
  if (state.sort !== DEFAULTS.sort) p.set("sort", state.sort);
  if (state.order !== DEFAULTS.order) p.set("order", state.order);
  const qs = p.toString();
  const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.replaceState(null, "", nextUrl);
}

/* ----------------------------- Rendering ----------------------------- */

function showSkeleton() {
  const skeletons = Math.min(6, Math.max(3, Math.floor(state.perPage / 5) + 3));
  const rows = Array.from({ length: skeletons })
    .map(() => '<tr class="row-skeleton"><td colspan="8"><div class="skeleton-row"></div></td></tr>')
    .join("");
  dom.ticketsBody.innerHTML = rows;
  dom.emptyState.classList.add("hidden");
  dom.errorState.classList.add("hidden");
}

function showEmpty() {
  state.ticketsById = new Map();
  dom.ticketsBody.innerHTML = "";
  dom.errorState.classList.add("hidden");
  dom.emptyState.classList.remove("hidden");
}

function showError(message) {
  state.ticketsById = new Map();
  dom.ticketsBody.innerHTML = "";
  dom.emptyState.classList.add("hidden");
  dom.errorState.classList.remove("hidden");
  dom.errorStateMsg.textContent = message || "Error desconocido.";
}

function renderTickets(tickets) {
  state.ticketsById = new Map(
    (tickets || [])
      .filter((t) => Number(t?.ticket_id))
      .map((t) => [Number(t.ticket_id), t])
  );

  if (!tickets.length) {
    showEmpty();
    return;
  }
  dom.emptyState.classList.add("hidden");
  dom.errorState.classList.add("hidden");

  dom.ticketsBody.innerHTML = tickets
    .map((t) => renderRow(t))
    .join("");
}

function renderRow(t) {
  const resolved = isResolved(t.status);
  const subject = t.subject && t.subject.trim() ? t.subject : "(sin asunto)";
  const email = t.email || "";
  const customer = t.customer_name || (email ? email.split("@")[0] : "");
  const displayName = customer || "Anónimo";
  const { abs: dateAbs, rel: dateRel } = formatDate(t.created_at);
  const respondedBadge = t.responded
    ? '<span class="badge ok"><span class="dot"></span>Sí</span>'
    : '<span class="badge warn"><span class="dot"></span>No</span>';
  const tone = statusTone(t.status);
  const statusBadge = `<span class="badge ${tone}"><span class="dot"></span>${escapeHtml(formatStatusLabel(t.status))}</span>`;
  const hue = avatarHue(email || customer || t.ticket_id);
  const avatarStyle = `background: linear-gradient(135deg, hsl(${hue} 70% 58%), hsl(${(hue + 40) % 360} 70% 50%));`;
  const actionCell = resolved
    ? '<span class="badge ok"><span class="dot"></span>Resuelto</span>'
    : `<button class="btn btn-ghost" data-action="resolve" data-id="${t.ticket_id}" title="Marcar como resuelto">
        <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="m5 12 4 4 10-10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Marcar resuelto
      </button>`;

  return `
    <tr data-id="${t.ticket_id}">
      <td class="col-id"><span class="id-cell">${escapeHtml(t.ticket_id)}</span></td>
      <td class="col-subject">
        <div class="subject-cell">
          <span class="subject-title">${escapeHtml(subject)}</span>
          <span class="subject-meta">${escapeHtml(t.priority ? `prioridad ${t.priority} · ` : "")}${escapeHtml(t.response_name || "")}</span>
        </div>
      </td>
      <td class="col-user">
        <div class="user-cell">
          <span class="avatar" style="${avatarStyle}">${escapeHtml(initialsFor(customer, email))}</span>
          <div class="user-meta">
            <span class="user-name">${escapeHtml(displayName)}</span>
            <span class="user-email">${escapeHtml(email || "sin email")}</span>
          </div>
        </div>
      </td>
      <td class="col-status">${statusBadge}</td>
      <td class="col-responded">${respondedBadge}</td>
      <td class="col-response">
        <span class="response-cell" title="${escapeHtml(t.response_name || "")}">${escapeHtml(t.response_name || "—")}</span>
      </td>
      <td class="col-date">
        <span class="date-cell">${escapeHtml(dateAbs)}<span class="rel">${escapeHtml(dateRel)}</span></span>
      </td>
      <td class="col-action"><div class="action-cell">${actionCell}</div></td>
    </tr>
  `;
}

function renderStatusChips() {
  const facets = state.facets.statuses || [];
  const active = new Set(state.statuses);
  if (!facets.length) {
    dom.statusChips.innerHTML = '<span class="chip empty">Aún sin estados conocidos</span>';
    return;
  }
  dom.statusChips.innerHTML = facets
    .map((s) => {
      const activeCls = active.has(s) ? " active" : "";
      return `<button type="button" class="chip${activeCls}" data-status="${escapeHtml(s)}">${escapeHtml(formatStatusLabel(s))}</button>`;
    })
    .join("");
}

function renderTypeSelect() {
  const facetTypes = Array.isArray(state.facets.types) ? state.facets.types : [];
  const values = new Set(
    facetTypes
      .map((t) => String(t || "").trim().toLowerCase())
      .filter(Boolean)
  );
  if (state.type) values.add(state.type.toLowerCase());

  const sorted = [...values].sort((a, b) => a.localeCompare(b, "es", { sensitivity: "base" }));
  dom.typeSelect.innerHTML = [
    '<option value="">Todos los tipos</option>',
    ...sorted.map((typeName) => `<option value="${escapeHtml(typeName)}">${escapeHtml(formatTypeLabel(typeName))}</option>`),
  ].join("");
  dom.typeSelect.value = state.type || "";
}

function renderRespondedSegs() {
  dom.respondedSegs.forEach((btn) => {
    const val = btn.dataset.responded || "";
    btn.classList.toggle("active", val === state.responded);
  });
}

function renderActiveChips() {
  const chips = [];
  const push = (label, value, onClear) => chips.push({ label, value, onClear });

  if (state.q) push("Búsqueda", state.q, () => { state.q = ""; dom.qInput.value = ""; });
  if (state.type) push("Tipo", formatTypeLabel(state.type), () => { state.type = ""; dom.typeSelect.value = ""; });
  if (state.user) push("Usuario", state.user, () => { state.user = ""; dom.userInput.value = ""; });
  if (state.statuses.length) {
    state.statuses.forEach((s) => {
      push("Estado", formatStatusLabel(s), () => {
        state.statuses = state.statuses.filter((x) => x !== s);
        renderStatusChips();
      });
    });
  }
  if (state.responded) {
    push("Respondido", state.responded === "yes" ? "Sí" : "No", () => {
      state.responded = ""; renderRespondedSegs();
    });
  }
  if (state.dateFrom) push("Desde", state.dateFrom, () => { state.dateFrom = ""; dom.dateFromInput.value = ""; });
  if (state.dateTo) push("Hasta", state.dateTo, () => { state.dateTo = ""; dom.dateToInput.value = ""; });
  if (state.sort !== DEFAULTS.sort || state.order !== DEFAULTS.order) {
    const sortLabel = dom.sortSelect.querySelector(`option[value="${state.sort}"]`)?.textContent || state.sort;
    push("Orden", `${sortLabel} · ${state.order === "asc" ? "Asc" : "Desc"}`, () => {
      state.sort = DEFAULTS.sort; state.order = DEFAULTS.order;
      dom.sortSelect.value = state.sort;
      dom.orderBtn.dataset.order = state.order;
      dom.orderLabel.textContent = "Desc";
    });
  }

  if (!chips.length) {
    dom.activeChips.innerHTML = "";
    return;
  }

  dom.activeChips.innerHTML = chips
    .map((c, i) => `
      <span class="active-chip" data-chip="${i}">
        <b>${escapeHtml(c.label)}</b>
        <span>${escapeHtml(c.value)}</span>
        <button type="button" aria-label="Eliminar filtro ${escapeHtml(c.label)}" data-chip-clear="${i}">
          <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        </button>
      </span>
    `).join("");

  dom.activeChips.querySelectorAll("[data-chip-clear]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = Number(btn.dataset.chipClear);
      chips[i]?.onClear?.();
      state.page = 1;
      writeStateToURL();
      renderActiveChips();
      loadTickets();
    });
  });
}

function renderPager() {
  const { page, totalPages, total, perPage } = state;
  const start = total === 0 ? 0 : (page - 1) * perPage + 1;
  const end = Math.min(page * perPage, total);
  dom.pageInfo.textContent = total
    ? `${start.toLocaleString("es-ES")}–${end.toLocaleString("es-ES")} de ${total.toLocaleString("es-ES")} tickets`
    : "Sin resultados";

  dom.firstBtn.disabled = page <= 1;
  dom.prevBtn.disabled = page <= 1;
  dom.nextBtn.disabled = page >= totalPages;
  dom.lastBtn.disabled = page >= totalPages;

  dom.pagerPages.innerHTML = buildPageButtons(page, totalPages)
    .map((entry) => {
      if (entry === "…") {
        return '<span class="pager-page gap">…</span>';
      }
      const active = entry === page ? " active" : "";
      return `<button type="button" class="pager-page${active}" data-page="${entry}">${entry}</button>`;
    })
    .join("");

  dom.pagerPages.querySelectorAll("[data-page]").forEach((el) => {
    el.addEventListener("click", () => goToPage(Number(el.dataset.page)));
  });
}

function buildPageButtons(page, total) {
  if (total <= 7) return range(1, total);
  const pages = new Set([1, total, page, page - 1, page + 1]);
  if (page <= 3) [2, 3, 4].forEach((n) => pages.add(n));
  if (page >= total - 2) [total - 1, total - 2, total - 3].forEach((n) => pages.add(n));
  const sorted = [...pages].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
  const withGaps = [];
  for (let i = 0; i < sorted.length; i++) {
    withGaps.push(sorted[i]);
    if (i < sorted.length - 1 && sorted[i + 1] - sorted[i] > 1) withGaps.push("…");
  }
  return withGaps;
}

function range(a, b) { return Array.from({ length: b - a + 1 }, (_, i) => a + i); }

function renderKPIs() {
  dom.kpiTotal.textContent = state.total.toLocaleString("es-ES");
  const filtersActive = hasActiveFilters();
  dom.kpiTotalHint.textContent = filtersActive ? "coinciden con los filtros" : "tickets totales";

  const pageTickets = dom.ticketsBody.querySelectorAll("tr[data-id]");
  let pending = 0, resolved = 0;
  pageTickets.forEach((tr) => {
    const hasResolveBtn = tr.querySelector('[data-action="resolve"]');
    if (hasResolveBtn) pending += 1; else resolved += 1;
  });
  dom.kpiPending.textContent = pending.toLocaleString("es-ES");
  dom.kpiResolved.textContent = resolved.toLocaleString("es-ES");

  const now = new Date();
  dom.kpiUpdated.textContent = now.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  dom.kpiLatency.textContent = state.lastLoadMs != null ? `respuesta en ${state.lastLoadMs} ms` : "—";
}

function hasActiveFilters() {
  return !!(
    state.q || state.type || state.user ||
    state.statuses.length || state.responded ||
    state.dateFrom || state.dateTo
  );
}

function renderSortIndicators() {
  dom.tableHead.querySelectorAll("th[data-sort]").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === state.sort) {
      th.classList.add(state.order === "asc" ? "sorted-asc" : "sorted-desc");
    }
  });
}

function setHealth(kind, text) {
  dom.healthDot.classList.remove("ok", "warn", "danger");
  if (kind !== "neutral") dom.healthDot.classList.add(kind);
  dom.healthText.textContent = text;
}

/* ----------------------------- Loading ----------------------------- */

async function loadTickets({ preserveScroll = true } = {}) {
  state.isLoading = true;
  dom.tableWrap.classList.add("is-loading");
  showSkeleton();

  const url = buildListUrl();
  const ticket = ++state.lastRequestedAt;
  const scrollY = preserveScroll ? window.scrollY : 0;
  const t0 = performance.now();

  try {
    const payload = await requestJSON(url);
    if (ticket !== state.lastRequestedAt) return; // outdated response
    state.total = payload.total || 0;
    state.totalPages = Math.max(1, payload.total_pages || 1);
    state.page = payload.page || state.page;
    state.facets = {
      statuses: payload.facets?.statuses || [],
      types: payload.facets?.types || [],
    };
    state.capabilities = payload.capabilities || state.capabilities;
    state.lastLoadMs = Math.round(performance.now() - t0);

    renderTypeSelect();
    renderStatusChips();
    renderTickets(payload.tickets || []);
    renderPager();
    renderKPIs();
    renderSortIndicators();
    renderActiveChips();
    setHealth("ok", "Ingest operativo");
    writeStateToURL();
  } catch (error) {
    if (ticket !== state.lastRequestedAt) return;
    showError(error.message || "No se pudo cargar el listado.");
    state.lastLoadMs = Math.round(performance.now() - t0);
    renderKPIs();
    setHealth("danger", "Ingest no responde");
  } finally {
    state.isLoading = false;
    dom.tableWrap.classList.remove("is-loading");
    if (preserveScroll) window.scrollTo({ top: scrollY });
  }
}

function goToPage(page) {
  if (state.isLoading) return;
  const next = Math.min(Math.max(1, Number(page) || 1), state.totalPages);
  if (next === state.page) return;
  state.page = next;
  loadTickets();
}

/* ----------------------------- Actions ----------------------------- */

async function resolveTicket(ticketId) {
  try {
    await requestJSON(`/api/tickets/${ticketId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    });
    toast({ title: `Ticket #${ticketId} resuelto`, kind: "ok" });
    await loadTickets();
  } catch (error) {
    toast({ title: "No se pudo resolver", message: error.message, kind: "error" });
  }
}

async function createTicket(email, message) {
  dom.createBtn.classList.add("is-loading");
  dom.createBtn.disabled = true;
  dom.createBtn.querySelector(".btn-label").textContent = "Clasificando…";
  setFormFeedback("Los modelos ML están clasificando el ticket y escribiendo la base de datos…", "working");

  try {
    const payload = await requestJSON("/api/tickets", {
      method: "POST",
      body: JSON.stringify({ email, message }),
    });
    const ids = (payload.ticket_ids || []).join(", ") || "ok";
    setFormFeedback(`Ticket creado. IDs: ${ids}`, "ok");
    toast({ title: "Ticket creado", message: `ID ${ids}`, kind: "ok" });
    dom.form.reset();
    closeDrawer();
    state.page = 1;
    await loadTickets({ preserveScroll: false });
  } catch (error) {
    setFormFeedback(error.message, "error");
    toast({ title: "No se pudo crear el ticket", message: error.message, kind: "error" });
  } finally {
    dom.createBtn.classList.remove("is-loading");
    dom.createBtn.disabled = false;
    dom.createBtn.querySelector(".btn-label").textContent = "Crear ticket";
  }
}

function setFormFeedback(text, kind = "info") {
  dom.formFeedback.textContent = text;
  dom.formFeedback.className = `feedback ${kind}`;
}

function clearAllFilters() {
  state.q = "";
  state.type = "";
  state.user = "";
  state.statuses = [];
  state.responded = "";
  state.dateFrom = "";
  state.dateTo = "";
  state.sort = DEFAULTS.sort;
  state.order = DEFAULTS.order;
  state.page = 1;

  dom.qInput.value = "";
  dom.typeSelect.value = "";
  dom.userInput.value = "";
  dom.dateFromInput.value = "";
  dom.dateToInput.value = "";
  dom.sortSelect.value = DEFAULTS.sort;
  dom.orderBtn.dataset.order = DEFAULTS.order;
  dom.orderLabel.textContent = "Desc";
  renderTypeSelect();
  renderRespondedSegs();
  renderStatusChips();
  writeStateToURL();
  loadTickets();
}

/* ----------------------------- Drawer ----------------------------- */

function openDrawer() {
  dom.drawer.classList.add("is-open");
  dom.drawer.setAttribute("aria-hidden", "false");
  setTimeout(() => dom.emailInput.focus(), 50);
}
function closeDrawer() {
  dom.drawer.classList.remove("is-open");
  dom.drawer.setAttribute("aria-hidden", "true");
  setFormFeedback("", "info");
}

/* ----------------------------- Ticket modal ----------------------------- */

function openTicketModal(ticket) {
  if (!dom.ticketModal) return;

  const id = Number(ticket?.ticket_id) || "—";
  const subject = String(ticket?.subject || "").trim() || "(sin asunto)";

  dom.modalTicketId.textContent = `Ticket #${id}`;
  dom.modalTicketSubject.textContent = subject;
  dom.modalTicketBody.textContent = bodyTextForModal(ticket);

  dom.ticketModal.classList.add("is-open");
  dom.ticketModal.setAttribute("aria-hidden", "false");
}

function closeTicketModal() {
  if (!dom.ticketModal) return;
  dom.ticketModal.classList.remove("is-open");
  dom.ticketModal.setAttribute("aria-hidden", "true");
}

/* ----------------------------- Toasts ----------------------------- */

function toast({ title = "", message = "", kind = "info", duration = 4000 } = {}) {
  const icons = {
    ok: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="m5 12 4 4 10-10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 8v5M12 16.5v.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 11v6M12 7.5v.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    warn: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 9v5M12 17.5v.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="m12 3 10 18H2L12 3z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  };
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.innerHTML = `
    <span class="toast-icon">${icons[kind] || icons.info}</span>
    <div>
      ${title ? `<p class="toast-title">${escapeHtml(title)}</p>` : ""}
      ${message ? `<p class="toast-msg">${escapeHtml(message)}</p>` : ""}
    </div>
  `;
  dom.toastStack.appendChild(node);
  setTimeout(() => {
    node.style.transition = "opacity .2s, transform .2s";
    node.style.opacity = "0";
    node.style.transform = "translateY(6px)";
    setTimeout(() => node.remove(), 220);
  }, duration);
}

/* ----------------------------- Event wiring ----------------------------- */

function writeFiltersToDOM() {
  dom.qInput.value = state.q;
  dom.typeSelect.value = state.type;
  dom.userInput.value = state.user;
  dom.dateFromInput.value = state.dateFrom;
  dom.dateToInput.value = state.dateTo;
  dom.sortSelect.value = state.sort;
  dom.orderBtn.dataset.order = state.order;
  dom.orderLabel.textContent = state.order === "asc" ? "Asc" : "Desc";
  dom.perPageSelect.value = String(state.perPage);
  renderRespondedSegs();
}

const triggerSearch = debounce(() => {
  state.page = 1;
  writeStateToURL();
  renderActiveChips();
  loadTickets();
}, 280);

function wireEvents() {
  dom.qInput.addEventListener("input", (e) => {
    state.q = e.target.value.trim();
    triggerSearch();
  });
  dom.typeSelect.addEventListener("change", (e) => {
    state.type = e.target.value.trim().toLowerCase();
    state.page = 1;
    writeStateToURL();
    renderActiveChips();
    loadTickets();
  });
  dom.userInput.addEventListener("input", (e) => {
    state.user = e.target.value.trim();
    triggerSearch();
  });
  dom.dateFromInput.addEventListener("change", (e) => {
    state.dateFrom = e.target.value;
    state.page = 1;
    writeStateToURL(); renderActiveChips(); loadTickets();
  });
  dom.dateToInput.addEventListener("change", (e) => {
    state.dateTo = e.target.value;
    state.page = 1;
    writeStateToURL(); renderActiveChips(); loadTickets();
  });

  dom.statusChips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip[data-status]");
    if (!chip) return;
    const s = chip.dataset.status;
    if (state.statuses.includes(s)) {
      state.statuses = state.statuses.filter((x) => x !== s);
    } else {
      state.statuses = [...state.statuses, s];
    }
    state.page = 1;
    renderStatusChips();
    writeStateToURL();
    renderActiveChips();
    loadTickets();
  });

  dom.respondedSegs.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.responded = btn.dataset.responded || "";
      state.page = 1;
      renderRespondedSegs();
      writeStateToURL();
      renderActiveChips();
      loadTickets();
    });
  });

  dom.sortSelect.addEventListener("change", (e) => {
    state.sort = e.target.value;
    state.page = 1;
    renderSortIndicators();
    writeStateToURL();
    renderActiveChips();
    loadTickets();
  });
  dom.orderBtn.addEventListener("click", () => {
    state.order = state.order === "asc" ? "desc" : "asc";
    dom.orderBtn.dataset.order = state.order;
    dom.orderLabel.textContent = state.order === "asc" ? "Asc" : "Desc";
    state.page = 1;
    renderSortIndicators();
    writeStateToURL();
    renderActiveChips();
    loadTickets();
  });

  dom.perPageSelect.addEventListener("change", (e) => {
    state.perPage = Number(e.target.value) || DEFAULTS.perPage;
    state.page = 1;
    writeStateToURL();
    loadTickets();
  });

  dom.toggleFiltersBtn.addEventListener("click", () => {
    const hidden = dom.filters.classList.toggle("is-hidden");
    dom.toggleFiltersBtn.setAttribute("aria-expanded", String(!hidden));
  });

  dom.clearFiltersBtn.addEventListener("click", clearAllFilters);
  dom.emptyClearBtn.addEventListener("click", clearAllFilters);
  dom.errorRetryBtn.addEventListener("click", () => loadTickets());

  dom.refreshBtn.addEventListener("click", () => loadTickets());
  dom.firstBtn.addEventListener("click", () => goToPage(1));
  dom.prevBtn.addEventListener("click", () => goToPage(state.page - 1));
  dom.nextBtn.addEventListener("click", () => goToPage(state.page + 1));
  dom.lastBtn.addEventListener("click", () => goToPage(state.totalPages));

  dom.tableHead.addEventListener("click", (event) => {
    const th = event.target.closest("th[data-sort]");
    if (!th) return;
    const col = th.dataset.sort;
    if (state.sort === col) {
      state.order = state.order === "asc" ? "desc" : "asc";
    } else {
      state.sort = col;
      state.order = col === "created_at" || col === "ticket_id" ? "desc" : "asc";
    }
    dom.sortSelect.value = state.sort;
    dom.orderBtn.dataset.order = state.order;
    dom.orderLabel.textContent = state.order === "asc" ? "Asc" : "Desc";
    state.page = 1;
    renderSortIndicators();
    writeStateToURL();
    renderActiveChips();
    loadTickets();
  });

  dom.ticketsBody.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-action='resolve']");
    if (btn) {
      const id = Number(btn.dataset.id);
      if (!id) return;
      btn.disabled = true;
      resolveTicket(id);
      return;
    }

    const row = event.target.closest("tr[data-id]");
    if (!row) return;
    const ticketId = Number(row.dataset.id);
    if (!ticketId) return;
    const ticket = state.ticketsById.get(ticketId);
    if (!ticket) return;
    openTicketModal(ticket);
  });

  dom.ticketModal?.querySelectorAll("[data-modal-close]").forEach((el) => {
    el.addEventListener("click", closeTicketModal);
  });

  // Drawer
  dom.newTicketBtn.addEventListener("click", openDrawer);
  dom.drawer.querySelectorAll("[data-drawer-close]").forEach((el) => {
    el.addEventListener("click", closeDrawer);
  });
  dom.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = dom.emailInput.value.trim();
    const message = dom.messageInput.value.trim();
    if (!email || !message) {
      setFormFeedback("Email y mensaje son obligatorios.", "error");
      return;
    }
    createTicket(email, message);
  });

  // Global shortcuts
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && dom.ticketModal?.classList.contains("is-open")) {
      closeTicketModal();
      return;
    }
    if (event.key === "Escape" && dom.drawer.classList.contains("is-open")) {
      closeDrawer();
    }
    const tag = (event.target && event.target.tagName) || "";
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if (!typing && event.key === "/") {
      event.preventDefault();
      dom.qInput.focus();
      dom.qInput.select();
    }
    if (!typing && event.key.toLowerCase() === "n" && !event.metaKey && !event.ctrlKey) {
      openDrawer();
    }
  });

  window.addEventListener("popstate", () => {
    readStateFromURL();
    writeFiltersToDOM();
    loadTickets();
  });
}

/* ----------------------------- Boot ----------------------------- */

function boot() {
  readStateFromURL();
  writeFiltersToDOM();
  renderTypeSelect();
  renderStatusChips();
  renderSortIndicators();
  renderActiveChips();
  wireEvents();
  setHealth("neutral", "Conectando…");
  loadTickets({ preserveScroll: false });
}

document.addEventListener("DOMContentLoaded", boot);
