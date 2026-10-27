const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const pageInfo = {
  dashboard:  ["Dashboard", "Real-time overview of your fellowship"],
  board:      ["Sprint Board", "Agile Kanban · Priority-sorted"],
  team:       ["Team", "Manage members, roles & access"],
  ai:         ["AI Pairing", "Smart suggestions for engineers"],
  safety:     ["Psychological Safety", "Anonymous feedback channel"],
  governance: ["Governance", "Immutable audit + reversible actions"],
  metrics:    ["Metrics", "Boy Scout Rule · Codebase health"],
};

let me = null;
let allUsers = [];
let allTasks = [];

// ============= Helpers =============
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (res.status === 401) { window.location.href = "/login"; return; }
  if (res.status === 204) return {};
  return res.json();
}

function toast(title, text = "", type = "") {
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.innerHTML = `<div class="t-title">${title}</div><div class="t-text">${text}</div>`;
  $("#toast-wrap").appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function confirmAction(title, text, onYes) {
  $("#modal-title").textContent = title;
  $("#modal-text").textContent = text;
  $("#modal-bg").classList.add("open");
  const yes = $("#modal-confirm");
  const cancel = $("#modal-cancel");
  const cleanup = () => {
    $("#modal-bg").classList.remove("open");
    yes.onclick = null;
    cancel.onclick = null;
  };
  yes.onclick = () => { cleanup(); onYes(); };
  cancel.onclick = cleanup;
}

function initials(name) {
  return (name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
}

// ============= Auth =============
async function loadMe() {
  me = await api("/api/me");
  if (!me) return;
  $("#user-name").textContent = me.full_name;
  $("#user-role").textContent = me.role;
  $("#avatar").textContent = initials(me.full_name);
  $("#dd-name").textContent = me.full_name;
  $("#dd-email").textContent = me.email || me.username;
  if (me.role !== "Admin") {
    $("#add-user-card").style.display = "none";
  }
}

$("#profile-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("#profile-dropdown").classList.toggle("open");
});
document.addEventListener("click", () => $("#profile-dropdown").classList.remove("open"));

$("#logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

// ============= Navigation =============
$$(".nav-item").forEach(btn => btn.addEventListener("click", () => {
  $$(".nav-item").forEach(b => b.classList.remove("active"));
  $$(".tab-panel").forEach(p => p.classList.remove("active"));
  btn.classList.add("active");
  const tab = btn.dataset.tab;
  $("#" + tab).classList.add("active");
  $("#page-title").textContent = pageInfo[tab][0];
  $("#page-sub").textContent = pageInfo[tab][1];
}));

$("#goto-team").addEventListener("click", () => {
  document.querySelector('[data-tab="team"]').click();
});

// ============= Users / Team =============
async function loadUsers() {
  allUsers = await api("/api/users");
  $("#stat-fellows").textContent = allUsers.length;
  $("#team-pill").textContent = allUsers.length;
  $("#team-count-pill").textContent = allUsers.length;

  // Quick team on dashboard
  $("#quick-team").innerHTML = allUsers.slice(0, 4).map(u =>
    `<li><div><strong>${u.full_name}</strong><div class="muted" style="font-size:11.5px;margin:0;">${u.role}</div></div></li>`
  ).join("") || `<li class="muted">No members yet.</li>`;

  // Full team
  $("#team-list").innerHTML = allUsers.map(u => `
    <li>
      <div class="team-member">
        <div class="team-avatar">${initials(u.full_name)}</div>
        <div class="team-info">
          <strong>${u.full_name} ${u.id === me.id ? '<span class="pill" style="font-size:10px;">You</span>' : ""}</strong>
          <span>@${u.username} · ${u.role}</span>
        </div>
      </div>
      <div class="team-actions">
        ${me.role === "Admin" && u.id !== me.id ? `
          <button class="icon-action danger" title="Remove" data-del-user="${u.id}">🗑</button>
        ` : ""}
      </div>
    </li>
  `).join("") || `<li class="muted">No members yet.</li>`;

  // delete handlers
  $$("[data-del-user]").forEach(b => b.addEventListener("click", () => {
    const uid = b.dataset.delUser;
    const u = allUsers.find(x => x.id === uid);
    confirmAction(
      `Remove ${u.full_name}?`,
      "Their tasks will be unassigned. You can undo this from Governance.",
      async () => {
        await api("/api/users/" + uid, { method: "DELETE" });
        toast("Member removed", u.full_name, "error");
        refreshAll();
      });
  }));
}

$("#user-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.fromEntries(fd)),
  });
  const data = await res.json();
  if (!res.ok) return toast("Failed", data.error || "Error", "error");
  toast("Member added", data.full_name, "success");
  e.target.reset();
  refreshAll();
});

// ============= Tasks =============
async function loadBoard() {
  const priority = $("#filter-priority").value;
  const qs = priority ? "?priority=" + priority : "";
  const board = await api("/api/tasks" + qs);
  const flat = Object.values(board).flat();
  allTasks = flat;
  $("#stat-tasks").textContent = flat.length;

  $("#board").innerHTML = Object.entries(board).map(([col, tasks]) => `
    <div class="col">
      <h3 data-count="${tasks.length}">${col}</h3>
      ${tasks.length ? tasks.map(t => `
        <div class="task ${t.priority.toLowerCase()}" data-task="${t.id}">
          <div class="task-actions">
            <button title="Delete" data-del-task="${t.id}">🗑</button>
          </div>
          <div class="title">${t.title}</div>
          <div class="meta"><span>${t.assignee}</span><span class="score">${t.score}</span></div>
          <div class="meta"><span>SP ${t.sp}</span><span>${t.priority}</span></div>
        </div>
      `).join("") : '<p class="muted" style="font-size:12px;">Empty</p>'}
    </div>
  `).join("");

  // click on task → open drawer
  $$(".task").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".task-actions")) return;
      openTaskDrawer(el.dataset.task);
    });
  });

  // delete
  $$("[data-del-task]").forEach(b => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = b.dataset.delTask;
    const t = allTasks.find(x => x.id === id);
    confirmAction(`Delete "${t.title}"?`,
      "You can undo this from Governance tab.", async () => {
        await api("/api/tasks/" + id, { method: "DELETE" });
        toast("Task deleted", t.title, "error");
        refreshAll();
      });
  }));
}

$("#filter-priority").addEventListener("change", loadBoard);
$("#global-search").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  $$(".task").forEach(el => {
    const txt = el.querySelector(".title").textContent.toLowerCase();
    el.style.display = txt.includes(q) ? "" : "none";
  });
});

$("#task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/api/tasks", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: fd.get("title"), description: fd.get("description"),
      priority: fd.get("priority"), story_points: fd.get("story_points"),
    }),
  });
  toast("Task created", fd.get("title"), "success");
  e.target.reset();
  refreshAll();
});

// ============= Task Drawer =============
async function openTaskDrawer(id) {
  const t = await api("/api/tasks/" + id);
  $("#drawer-title").textContent = t.title;
  $("#drawer-body").innerHTML = `
    <div class="drawer-field">
      <label>Description</label>
      <div class="val">${t.description || '<span class="muted">No description</span>'}</div>
    </div>
    <div class="drawer-field">
      <label>Priority</label>
      <div class="val">${t.priority}</div>
    </div>
    <div class="drawer-field">
      <label>Status</label>
      <select id="drawer-status">
        ${["Backlog", "In Progress", "Review", "Done"].map(s =>
          `<option ${s === t.status ? "selected" : ""}>${s}</option>`).join("")}
      </select>
    </div>
    <div class="drawer-field">
      <label>Assignee</label>
      <select id="drawer-assignee">
        <option value="">Unassigned</option>
        ${allUsers.map(u =>
          `<option value="${u.id}" ${u.id === t.assignee_id ? "selected" : ""}>${u.full_name}</option>`).join("")}
      </select>
    </div>
    <div class="drawer-field">
      <label>Comments (${t.comments.length})</label>
      <div id="comments-list">
        ${t.comments.length ? t.comments.map(c =>
          `<div class="comment"><div class="who">${c.author}<span class="when">${c.at.replace("T", " ")}</span></div><div class="what">${c.text}</div></div>`
        ).join("") : '<p class="muted">No comments yet.</p>'}
      </div>
      <form class="comment-form" id="comment-form">
        <input name="text" placeholder="Write a comment..." required style="flex:1;" />
        <button class="btn-primary">Post</button>
      </form>
    </div>
    <button class="btn-danger" id="drawer-delete" style="width:100%;margin-top:20px;">Delete Task</button>
  `;

  $("#drawer-status").addEventListener("change", async (e) => {
    await api(`/api/tasks/${id}/move`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: e.target.value }),
    });
    toast("Status updated", e.target.value, "success");
    loadBoard(); loadEvents();
  });

  $("#drawer-assignee").addEventListener("change", async (e) => {
    await api(`/api/tasks/${id}/assign`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: e.target.value }),
    });
    toast("Assignee updated", "", "success");
    loadBoard(); loadEvents();
  });

  $("#comment-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    await api(`/api/tasks/${id}/comment`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: fd.get("text") }),
    });
    toast("Comment posted", "", "success");
    openTaskDrawer(id);
    loadBoard();
  });

  $("#drawer-delete").addEventListener("click", () => {
    confirmAction(`Delete "${t.title}"?`, "You can undo this from Governance.", async () => {
      await api("/api/tasks/" + id, { method: "DELETE" });
      closeDrawer();
      toast("Task deleted", t.title, "error");
      refreshAll();
    });
  });

  $("#drawer-bg").classList.add("open");
  $("#task-drawer").classList.add("open");
}

function closeDrawer() {
  $("#drawer-bg").classList.remove("open");
  $("#task-drawer").classList.remove("open");
}
$("#drawer-close").addEventListener("click", closeDrawer);
$("#drawer-bg").addEventListener("click", closeDrawer);

// ============= AI =============
async function loadAIList() {
  const board = await api("/api/tasks");
  const all = Object.values(board).flat();
  $("#ai-task-select").innerHTML = all.length
    ? all.map(t => `<option value="${t.id}">${t.title}</option>`).join("")
    : `<option value="">No tasks yet</option>`;
}

$("#ai-task-select").addEventListener("change", async (e) => {
  const id = e.target.value;
  if (!id) return;
  const d = await api("/api/tasks/" + id + "/ai");
  $("#ai-output").innerHTML = `
    <div class="label">AI Product Suggestion</div>
    <div class="value">${d.suggestion}</div>
    <div class="label">Suggested Pair Engineer</div>
    <div class="value">${d.pair_with}</div>`;
});

// ============= Feedback =============
async function loadFeedback() {
  const data = await api("/api/feedback");
  const mood = { great: "😀", ok: "🙂", concerned: "😟" };
  $("#feedback-list").innerHTML = data.length
    ? data.map(f => `
        <li>
          <span class="fb-text">${mood[f.mood] || "🙂"} &nbsp; ${f.message}</span>
          ${me.role === "Admin" ? `<button class="icon-action danger" data-del-fb="${f.id}">🗑</button>` : ""}
        </li>
      `).join("")
    : `<li class="muted">No feedback yet.</li>`;

  $$("[data-del-fb]").forEach(b => b.addEventListener("click", () => {
    const id = b.dataset.delFb;
    confirmAction("Delete feedback?", "This action can be undone.", async () => {
      await api("/api/feedback/" + id, { method: "DELETE" });
      toast("Feedback deleted", "", "error");
      loadFeedback();
    });
  }));
}

$("#feedback-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/api/feedback", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: fd.get("message"), mood: fd.get("mood") }),
  });
  toast("Feedback shared", "Thank you for speaking up", "success");
  e.target.reset();
  loadFeedback(); loadEvents(); loadAudit();
});

// ============= Governance =============
async function loadGovernance() {
  const data = await api("/api/governance");
  $("#stat-events").textContent = data.total_events;
  $("#audit-list").innerHTML = data.recent.length
    ? data.recent.map(e => {
        const { _undo, ...clean } = e;
        return `<li>${clean.at} · <strong>${clean.type}</strong> · ${JSON.stringify(clean.payload)}</li>`;
      }).join("")
    : `<li class="muted">No events yet.</li>`;
}

async function loadEvents() {
  const data = await api("/api/events");
  $("#event-list").innerHTML = data.length
    ? data.map(e => `
        <li class="${e.undone ? "undone" : ""}">
          <span>${e.at} · <strong>${e.type}</strong> · ${JSON.stringify(e.payload)}</span>
          ${e.undoable ? `<button class="undo-btn" data-undo="${e.id}" ${e.undone ? "disabled" : ""}>↩ Undo</button>` : ""}
        </li>
      `).join("")
    : `<li class="muted">No events.</li>`;

  $$("[data-undo]").forEach(b => b.addEventListener("click", async () => {
    const id = b.dataset.undo;
    const res = await api("/api/undo/" + id, { method: "POST" });
    if (res.ok) {
      toast("Action reversed", "State restored", "success");
      refreshAll();
    } else {
      toast("Cannot undo", "Already reversed", "error");
    }
  }));
}

async function loadAudit() { await loadGovernance(); }

// ============= Boy Scout =============
async function loadBoyScout() {
  const d = await api("/api/boy-scout");
  $("#stat-coverage").textContent = d.after.coverage + "%";
  $("#boy-scout").innerHTML = Object.keys(d.before).map(k => `
    <div class="metric">
      <div class="muted">${k}</div>
      <div><span class="before">${d.before[k]}</span><span class="arrow">→</span><span class="after">${d.after[k]}</span></div>
    </div>`).join("");
}

// ============= Constitution =============
async function loadConstitution() {
  const data = await api("/api/constitution");
  $("#constitution").innerHTML = data.map(p =>
    `<li><strong>${p.name}</strong> — ${p.description} <span class="muted" style="font-size:11px;">(w=${p.weight})</span></li>`
  ).join("");
}

// ============= Refresh =============
function refreshAll() {
  loadUsers(); loadBoard(); loadConstitution();
  loadAIList(); loadFeedback(); loadGovernance(); loadEvents(); loadBoyScout();
}

// Init
(async () => {
  await loadMe();
  refreshAll();
  setInterval(() => { loadEvents(); loadGovernance(); }, 4000);
})();