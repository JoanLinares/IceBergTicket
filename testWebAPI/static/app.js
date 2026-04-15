const state = {
  page: 1,
  perPage: 10,
  totalPages: 1,
};

const ticketsBody = document.getElementById("ticketsBody");
const pageInfo = document.getElementById("pageInfo");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const lastBtn = document.getElementById("lastBtn");
const refreshBtn = document.getElementById("refreshBtn");
const form = document.getElementById("newTicketForm");
const createBtn = document.getElementById("createBtn");
const formFeedback = document.getElementById("formFeedback");

function setFeedback(message, type = "ok") {
  formFeedback.textContent = message;
  formFeedback.className = `feedback ${type}`;
}

async function requestJSON(url, options = {}) {
  const opts = { ...options };
  opts.headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(url, opts);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function isResolved(status) {
  const value = String(status || "").toLowerCase();
  return value === "resolved" || value === "closed";
}

function renderTickets(tickets) {
  if (!tickets.length) {
    ticketsBody.innerHTML = "<tr><td colspan=\"6\" class=\"empty\">No hay tickets todavia</td></tr>";
    return;
  }

  ticketsBody.innerHTML = tickets
    .map((ticket) => {
      const resolved = isResolved(ticket.status);
      const responded = ticket.responded ? "Si" : "No";
      const responseName = ticket.response_name || "Sin respuesta";
      const actionButton = resolved
        ? "<span class=\"badge ok\">Resuelto</span>"
        : `<button class=\"inline-btn\" data-action=\"resolve\" data-id=\"${ticket.ticket_id}\">Marcar resuelto</button>`;

      return `
        <tr>
          <td>${ticket.ticket_id}</td>
          <td>${escapeHtml(ticket.subject || "(sin asunto)")}</td>
          <td>${escapeHtml(responseName)}</td>
          <td><span class=\"badge ${ticket.responded ? "ok" : "warn"}\">${responded}</span></td>
          <td>${escapeHtml(ticket.status || "open")}</td>
          <td>${actionButton}</td>
        </tr>
      `;
    })
    .join("");
}

function updatePager(meta) {
  state.page = meta.page;
  state.totalPages = meta.total_pages;
  pageInfo.textContent = `Pagina ${meta.page} de ${meta.total_pages} (${meta.total} tickets)`;
  prevBtn.disabled = meta.page <= 1;
  nextBtn.disabled = meta.page >= meta.total_pages;
  lastBtn.disabled = meta.page >= meta.total_pages;
}

async function loadTickets(page = state.page) {
  ticketsBody.innerHTML = "<tr><td colspan=\"6\" class=\"empty\">Cargando tickets...</td></tr>";
  try {
    const payload = await requestJSON(`/api/tickets?page=${page}&per_page=${state.perPage}`);
    renderTickets(payload.tickets || []);
    updatePager(payload);
  } catch (error) {
    ticketsBody.innerHTML = `<tr><td colspan=\"6\" class=\"empty\">${escapeHtml(error.message)}</td></tr>`;
  }
}

async function createTicket(email, message) {
  createBtn.disabled = true;
  createBtn.textContent = "Clasificando y creando...";
  setFeedback("La API está clasificando el ticket con los modelos ML y guardándolo en la base de datos...", "ok");

  try {
    const payload = await requestJSON("/api/tickets", {
      method: "POST",
      body: JSON.stringify({ email, message }),
    });
    setFeedback(`Ticket creado. IDs: ${(payload.ticket_ids || []).join(", ") || "ok"}`, "ok");
    form.reset();
    await loadTickets(1);
  } catch (error) {
    setFeedback(error.message, "error");
  } finally {
    createBtn.disabled = false;
    createBtn.textContent = "Crear ticket";
  }
}

async function resolveTicket(ticketId) {
  try {
    await requestJSON(`/api/tickets/${ticketId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    });
    await loadTickets(state.page);
  } catch (error) {
    setFeedback(error.message, "error");
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("emailInput").value.trim();
  const message = document.getElementById("messageInput").value.trim();

  if (!email || !message) {
    setFeedback("Email y mensaje son obligatorios", "error");
    return;
  }

  await createTicket(email, message);
});

prevBtn.addEventListener("click", () => {
  if (state.page > 1) {
    loadTickets(state.page - 1);
  }
});

nextBtn.addEventListener("click", () => {
  if (state.page < state.totalPages) {
    loadTickets(state.page + 1);
  }
});

lastBtn.addEventListener("click", () => {
  if (state.page < state.totalPages) {
    loadTickets(state.totalPages);
  }
});

refreshBtn.addEventListener("click", () => loadTickets(state.page));

ticketsBody.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action='resolve']");
  if (!button) {
    return;
  }

  const ticketId = Number(button.dataset.id);
  if (!ticketId) {
    return;
  }

  resolveTicket(ticketId);
});

loadTickets(1);
