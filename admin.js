// ════════════════════════════════════════════════════════════════════════════
//  OPERSAN — admin.js  v2.1  (toggle admin + setores dinâmicos)
//
//  MUDANÇAS v2.1:
//  - Coluna "Admin" na tabela de usuários com toggle inline
//  - Modal de edição: toggle admin com aviso de segurança
//  - toggleAdmin() — chama PUT /admin/users/:id com { role: "admin"|"user" }
//  - Proteções: último admin, conta própria, confirmação antes de promover
// ════════════════════════════════════════════════════════════════════════════

const API   = "https://agente-ia-62sa.onrender.com";
const token = localStorage.getItem("userToken") || localStorage.getItem("token") || "";

// ─── ÍCONES SVG INLINE ────────────────────────────────────────────────────────
const SVG = {
    edit:     `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
    trash:    `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
    save:     `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
    xCircle:  `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    x:        `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    eye:      `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    eyeOff:   `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
    warning:  `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    check:    `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    chevDown: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`,
    shield:   `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    shieldOff:`<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.69 14a6.9 6.9 0 0 0 .31-2V5l-8-3-3.16 1.18"/><path d="M4.73 4.73L4 5v7c0 6 8 10 8 10a20.29 20.29 0 0 0 5.62-4.38"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
};

// ─── ESTADO ──────────────────────────────────────────────────────────────────
let allUsers            = [];
let allRoles            = [];
let selectedSectorIds   = [];
let editSectorIds       = [];
let itemToDelete        = { id: null, type: null };
let _meuUserId          = null; // id do admin logado

let permViewerSelecionado   = null;
let permTargetsSelecionados = [];
let permSetoresSelecionados = [];
let _permCache = { permissoes: [], users: [] };

// ════════════════════════════════════════════════════════════════════════════
//  HELPERS DE SETOR — DINÂMICOS
// ════════════════════════════════════════════════════════════════════════════

function _slugSetor(nome) {
    return (nome || "")
        .toLowerCase()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, "")
        .replace(/[^a-z0-9]/g, "");
}

function _nomePorSlug(slug) {
    const role = allRoles.find(r => _slugSetor(r.name) === slug);
    return role ? role.name : slug;
}

const _SETOR_CORES = [
    "#3b82f6", "#10b981", "#f59e0b",
    "#8b5cf6", "#06b6d4", "#ec4899", "#f97316", "#14b8a6"
];

function _emojiSetor(nome) {
    const s = _slugSetor(nome);
    if (s.includes("jurid") || s.includes("legal") || s.includes("lei") || s.includes("direito")) return "⚖️";
    if (s.includes("suprim") || s.includes("compra") || s.includes("estoque") || s.includes("logist")) return "📦";
    if (s.includes("gestao") || s.includes("contrat") || s.includes("kanban")) return "📁";
    if (s.includes("financ") || s.includes("contab") || s.includes("fiscal")) return "💼";
    if (s.includes("ti") || s.includes("tech") || s.includes("inform") || s.includes("sistema")) return "⚙️";
    if (s.includes("rh") || s.includes("recurs") || s.includes("human") || s.includes("pessoal")) return "👥";
    return "🏢";
}

function _corSetor(nomeSetor) {
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    const idx = setores.findIndex(r => _slugSetor(r.name) === _slugSetor(nomeSetor));
    return _SETOR_CORES[(idx >= 0 ? idx : 0) % _SETOR_CORES.length];
}

function _classeCorSetor(nome) {
    const slug = _slugSetor(nome);
    if (slug.includes("juridic"))                              return "juridico";
    if (slug.includes("suprimento"))                           return "suprimentos";
    if (slug.includes("gestao") || slug.includes("contrato")) return "gestaocontratos";
    return "default";
}

// ════════════════════════════════════════════════════════════════════════════
//  TOGGLE ADMIN — lógica principal
// ════════════════════════════════════════════════════════════════════════════

/**
 * Alterna o status de admin de um usuário.
 * @param {number} userId  - ID do usuário
 * @param {boolean} tornarAdmin - true = promover, false = rebaixar
 * @param {number} totalAdmins - total atual de admins (proteção último admin)
 */
async function toggleAdmin(userId, tornarAdmin, totalAdmins) {
    const user = allUsers.find(u => u.id === userId);
    if (!user) return;

    const nome = formatarNome(user.username);

    // Proteção: não pode rebaixar o último admin
    if (!tornarAdmin && totalAdmins <= 1) {
        showToast("Não é possível remover o último administrador.", "error");
        return;
    }

    // Proteção: não pode se auto-rebaixar
    if (!tornarAdmin && userId === _meuUserId) {
        showToast("Você não pode remover sua própria permissão de administrador.", "error");
        return;
    }

    // Confirmação antes de alterar
    const acao   = tornarAdmin ? `promover "${nome}" a Administrador` : `rebaixar "${nome}" para Usuário comum`;
    const aviso  = tornarAdmin
        ? `${nome} terá acesso completo ao painel de administração.`
        : `${nome} perderá o acesso ao painel de administração.`;

    if (!confirm(`Deseja ${acao}?\n\n${aviso}`)) return;

    try {
        const res = await fetch(`${API}/admin/users/${userId}`, {
            method:  "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body:    JSON.stringify({ role: tornarAdmin ? "admin" : "user" }),
            signal:  AbortSignal.timeout(10000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ${res.status}`);
        }
        await carregarDados();
        showToast(
            tornarAdmin
                ? `✅ ${nome} agora é Administrador.`
                : `✅ ${nome} agora é Usuário comum.`,
            "success"
        );
    } catch (err) {
        console.error("❌ toggleAdmin:", err);
        showToast(err.message || "Erro ao alterar permissão.", "error");
    }
}

// ════════════════════════════════════════════════════════════════════════════
//  DROPDOWN BASE
// ════════════════════════════════════════════════════════════════════════════

function _criarBaseDropdown(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    container.innerHTML = "";

    const painelAnterior = document.getElementById(`panel-${containerId}`);
    if (painelAnterior) painelAnterior.remove();

    const trigger = document.createElement("button");
    trigger.type      = "button";
    trigger.className = "badges-dropdown-trigger";

    const triggerLeft = document.createElement("div");
    triggerLeft.className = "badges-dropdown-trigger-left";

    const triggerArrow = document.createElement("span");
    triggerArrow.className = "badges-dropdown-trigger-arrow";
    triggerArrow.innerHTML = SVG.chevDown;

    trigger.appendChild(triggerLeft);
    trigger.appendChild(triggerArrow);

    const panel = document.createElement("div");
    panel.className = "badges-dropdown-panel";
    panel.id        = `panel-${containerId}`;
    document.body.appendChild(panel);

    function posicionarPainel() {
        const rect        = trigger.getBoundingClientRect();
        const alturaPanel = panel.offsetHeight || 200;
        const espacoAbaixo = window.innerHeight - rect.bottom;
        panel.style.left  = `${rect.left + window.scrollX}px`;
        panel.style.width = `${rect.width}px`;
        if (espacoAbaixo < alturaPanel && rect.top > alturaPanel) {
            panel.style.top = `${rect.top + window.scrollY - alturaPanel - 4}px`;
        } else {
            panel.style.top = `${rect.bottom + window.scrollY + 4}px`;
        }
    }

    let isOpen = false;

    function abrirDropdown() {
        document.querySelectorAll(".badges-dropdown-panel.open").forEach(p => {
            if (p.id !== panel.id) p.classList.remove("open");
        });
        document.querySelectorAll(".badges-dropdown-trigger.open").forEach(t => {
            if (t !== trigger) t.classList.remove("open");
        });
        isOpen = true;
        panel.classList.add("open");
        trigger.classList.add("open");
        posicionarPainel();
    }

    function fecharDropdown() {
        isOpen = false;
        panel.classList.remove("open");
        trigger.classList.remove("open");
    }

    trigger.addEventListener("click", e => {
        e.stopPropagation();
        isOpen ? fecharDropdown() : abrirDropdown();
    });

    window.addEventListener("scroll",  () => { if (isOpen) posicionarPainel(); }, true);
    window.addEventListener("resize",  () => { if (isOpen) posicionarPainel(); });
    document.addEventListener("click", e => {
        if (!container.contains(e.target) && !panel.contains(e.target)) fecharDropdown();
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") fecharDropdown(); });

    container.appendChild(trigger);
    return { container, trigger, triggerLeft, panel, fecharDropdown };
}

// ════════════════════════════════════════════════════════════════════════════
//  DROPDOWN SETORES — multi-select
// ════════════════════════════════════════════════════════════════════════════

function criarDropdownSetores(containerId, setores, selectedIds, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!setores.length) {
        container.innerHTML = '<span class="badge-loading">Nenhum setor cadastrado ainda.</span>';
        return;
    }

    const base = _criarBaseDropdown(containerId);
    if (!base) return;
    const { triggerLeft, panel, fecharDropdown } = base;

    function atualizarTrigger() {
        triggerLeft.innerHTML = "";
        const selecionados = setores.filter(r => selectedIds.includes(r.id));
        if (!selecionados.length) {
            const ph = document.createElement("span");
            ph.className   = "badges-dropdown-trigger-placeholder";
            ph.textContent = "Selecionar setores...";
            triggerLeft.appendChild(ph);
        } else {
            selecionados.forEach(r => {
                const mini = document.createElement("span");
                mini.className   = `badge-mini ${_classeCorSetor(r.name)}`;
                mini.textContent = r.name;
                triggerLeft.appendChild(mini);
            });
        }
    }

    function renderizarItens() {
        panel.innerHTML = "";
        setores.forEach(role => {
            const ativo       = selectedIds.includes(role.id);
            const classeSetor = _classeCorSetor(role.name);
            const item = document.createElement("div");
            item.className  = `badge ${ativo ? "active" : "inactive"}`;
            item.dataset.id = role.id;
            item.innerHTML  = `
                <div class="badge-label-wrap">
                    <span class="badge-dot ${classeSetor}"></span>
                    <span>${role.name}</span>
                </div>
                <span class="badge-check" style="opacity:${ativo ? 1 : 0}">${SVG.check}</span>`;
            item.addEventListener("click", () => {
                const idx   = selectedIds.indexOf(role.id);
                const check = item.querySelector(".badge-check");
                if (idx > -1) {
                    selectedIds.splice(idx, 1);
                    item.classList.replace("active", "inactive");
                    check.style.opacity = "0";
                } else {
                    selectedIds.push(role.id);
                    item.classList.replace("inactive", "active");
                    check.style.opacity = "1";
                }
                atualizarTrigger();
                if (onChange) onChange(selectedIds);
            });
            panel.appendChild(item);
        });
    }

    atualizarTrigger();
    renderizarItens();

    base.container._refresh = () => { renderizarItens(); atualizarTrigger(); };
    base.container._reset   = () => { selectedIds.length = 0; atualizarTrigger(); renderizarItens(); };
    base.container._destroy = () => { fecharDropdown(); panel.remove(); };
}

// ════════════════════════════════════════════════════════════════════════════
//  DROPDOWN ROLE — seleção única
// ════════════════════════════════════════════════════════════════════════════

function criarDropdownRole(containerId, opcoes, valorInicial, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let valorAtual = valorInicial;
    const base = _criarBaseDropdown(containerId);
    if (!base) return;
    const { triggerLeft, panel, fecharDropdown } = base;

    function atualizarTrigger() {
        triggerLeft.innerHTML = "";
        const opcao = opcoes.find(o => o.value === valorAtual);
        if (opcao) {
            const mini = document.createElement("span");
            mini.className   = `badge-mini ${opcao.classe}`;
            mini.textContent = opcao.label;
            triggerLeft.appendChild(mini);
        }
    }

    function renderizarItens() {
        panel.innerHTML = "";
        opcoes.forEach(opcao => {
            const ativo = valorAtual === opcao.value;
            const item  = document.createElement("div");
            item.className = `badge ${ativo ? "active" : "inactive"}`;
            item.innerHTML = `
                <div class="badge-label-wrap">
                    <span class="badge-dot ${opcao.classe}"></span>
                    <span>${opcao.label}</span>
                </div>
                <span class="badge-check" style="opacity:${ativo ? 1 : 0}">${SVG.check}</span>`;
            item.addEventListener("click", () => {
                valorAtual = opcao.value;
                if (onChange) onChange(valorAtual);
                renderizarItens();
                atualizarTrigger();
                fecharDropdown();
            });
            panel.appendChild(item);
        });
    }

    atualizarTrigger();
    renderizarItens();

    base.container._getValue = () => valorAtual;
    base.container._reset    = () => { valorAtual = valorInicial; atualizarTrigger(); renderizarItens(); };
    base.container._destroy  = () => { fecharDropdown(); panel.remove(); };
}

function renderizarRoleDropdown() {
    criarDropdownRole(
        "user-role-dropdown",
        [
            { value: "user",  label: "Usuário",       classe: "juridico"        },
            { value: "admin", label: "Administrador", classe: "gestaocontratos" },
        ],
        "user"
    );
}

// ════════════════════════════════════════════════════════════════════════════
//  BOOT
// ════════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", async () => {
    if (!token) { window.location.href = "login.html"; return; }

    try {
        const res = await fetch(`${API}/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(10000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (!res.ok) throw new Error(`Erro ${res.status}`);

        const me        = await res.json();
        const roleLocal = (localStorage.getItem("userRole") || "").toLowerCase();
        const isAdmin   =
            (me.role || "").toLowerCase() === "admin" ||
            (me.roles || []).some(r => r.name?.toLowerCase() === "admin") ||
            roleLocal === "admin";

        if (!isAdmin) { window.location.href = "index.html"; return; }

        _meuUserId = me.id; // guarda para proteções de auto-rebaixamento
        localStorage.setItem("userRole", "admin");
        configurarPerfilAdmin(me);

    } catch (err) {
        console.error("❌ Verificação:", err.message);
        mostrarErroPermissao(err.message);
        return;
    }

    await carregarDados();
    configurarFormularios();
    configurarTeclado();
    configurarBuscas();
});

function mostrarErroPermissao(mensagem) {
    document.body.innerHTML = `
        <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;
            justify-content:center;background:#0a0c14;color:#fff;font-family:'Inter',sans-serif;
            gap:1rem;text-align:center;padding:2rem;">
            <div style="font-size:3rem">🔒</div>
            <h2 style="font-size:1.4rem;font-weight:700">Acesso Bloqueado</h2>
            <p style="color:#94a3b8;font-size:0.9rem;max-width:360px">
                Não foi possível verificar suas permissões.<br>
                <em style="font-size:0.8rem">${mensagem}</em>
            </p>
            <a href="index.html" style="margin-top:1rem;padding:0.65rem 1.5rem;background:#3b82f6;
                color:#fff;border-radius:8px;text-decoration:none;font-size:0.875rem;font-weight:600;">
                Voltar ao Sistema</a>
        </div>`;
}

function configurarPerfilAdmin(me) {
    const rawName = me.name || me.username || "Admin";
    const nome    = rawName.includes("@")
        ? rawName.split("@")[0].split(/[._-]/)
            .map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ")
        : rawName;
    const elNome   = document.getElementById("admin-user-name");
    const elAvatar = document.querySelector(".admin-user-avatar");
    if (elNome)   elNome.textContent   = nome;
    if (elAvatar) elAvatar.textContent = nome.charAt(0).toUpperCase();
}

// ════════════════════════════════════════════════════════════════════════════
//  CARREGAR DADOS
// ════════════════════════════════════════════════════════════════════════════

async function carregarDados() {
    try {
        const [resUsers, resRoles] = await Promise.all([
            fetch(`${API}/admin/users`, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(10000) }),
            fetch(`${API}/admin/roles`, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(10000) }),
        ]);

        if (resUsers.status === 401 || resRoles.status === 401) { redirecionarLogin(); return; }
        if (!resUsers.ok) throw new Error(`Erro ao carregar usuários (${resUsers.status})`);
        if (!resRoles.ok) throw new Error(`Erro ao carregar setores (${resRoles.status})`);

        allUsers = await resUsers.json();
        allRoles = await resRoles.json();

        renderizarStats();
        renderizarTabelaUsuarios();
        renderizarTabelaSetores();
        renderizarBadgesSetores();
        renderizarRoleDropdown();
        renderizarPreviewUsuarios();
        renderizarPreviewSetores();

        if (!document.getElementById("section-permissoes")?.classList.contains("hidden")) {
            await renderizarAbaPermissoes();
        }

    } catch (err) {
        console.error("❌ carregarDados:", err);
        renderizarBadgesSetores();
        renderizarRoleDropdown();
        showToast("⚠️ " + err.message, "error");
    }
}

function renderizarStats() {
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    const admins  = allUsers.filter(u =>
        u.role === "admin" || u.roles.some(r => r.name.toLowerCase() === "admin")
    );
    const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
    el("total-users",   allUsers.length);
    el("total-sectors", setores.length);
    el("total-admins",  admins.length);
}

function renderizarBadgesSetores() {
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    selectedSectorIds = selectedSectorIds.filter(id => setores.some(r => r.id === id));
    criarDropdownSetores("sectors-list-badges", setores, selectedSectorIds);
}

function renderizarPreviewUsuarios() {
    const container = document.getElementById("preview-users-list");
    const counter   = document.getElementById("preview-users-count");
    if (!container) return;
    const naoAdmin = allUsers.filter(u =>
        u.role !== "admin" && !u.roles.some(r => r.name.toLowerCase() === "admin")
    );
    if (counter) counter.textContent = naoAdmin.length;
    if (!naoAdmin.length) { container.innerHTML = '<p class="preview-empty">Nenhum usuário cadastrado ainda.</p>'; return; }
    container.innerHTML = naoAdmin.map(u => {
        const nome       = formatarNome(u.username);
        const inicial    = nome.charAt(0).toUpperCase();
        const setores    = u.roles.filter(r => r.name.toLowerCase() !== "admin");
        const badgesHtml = setores.length
            ? setores.map(r => `<span class="preview-role-badge" data-setor="${_slugSetor(r.name)}">${r.name}</span>`).join("")
            : `<span class="preview-role-badge sem-setor">sem setor</span>`;
        return `<div class="preview-user-card"><div class="preview-avatar">${inicial}</div><div class="preview-user-info"><span class="preview-user-name">${nome}</span><div class="preview-roles">${badgesHtml}</div></div></div>`;
    }).join("");
}

function renderizarPreviewSetores() {
    const container = document.getElementById("preview-sectors-list");
    const counter   = document.getElementById("preview-sectors-count");
    if (!container) return;
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    if (counter) counter.textContent = setores.length;
    if (!setores.length) { container.innerHTML = '<p class="preview-empty">Nenhum setor cadastrado ainda.</p>'; return; }
    container.innerHTML = setores.map(role => {
        const emoji    = _emojiSetor(role.name);
        const qtdUsers = allUsers.filter(u => u.roles.some(r => r.id === role.id)).length;
        return `<div class="preview-sector-card"><div class="preview-sector-icon">${emoji}</div><div class="preview-sector-info"><span class="preview-sector-name">${role.name}</span><span class="preview-sector-count">${qtdUsers} usuário${qtdUsers !== 1 ? "s" : ""}</span></div></div>`;
    }).join("");
}

// ════════════════════════════════════════════════════════════════════════════
//  TABELAS
// ════════════════════════════════════════════════════════════════════════════

function renderizarTabelaUsuarios(filtro = "") {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    let lista = [...allUsers];
    if (filtro) {
        const t = filtro.toLowerCase();
        lista = lista.filter(u =>
            u.username.toLowerCase().includes(t) ||
            formatarNome(u.username).toLowerCase().includes(t) ||
            u.roles.some(r => r.name.toLowerCase().includes(t))
        );
    }

    if (!lista.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="preview-empty">${filtro ? "Nenhum resultado." : "Nenhum usuário."}</td></tr>`;
        return;
    }

    // Total de admins para proteção do último admin
    const totalAdmins = allUsers.filter(u =>
        u.role === "admin" || u.roles.some(r => r.name.toLowerCase() === "admin")
    ).length;

    lista.forEach(user => {
        const tr     = document.createElement("tr");
        const eAdmin = user.role === "admin" || user.roles.some(r => r.name.toLowerCase() === "admin");

        // Badges de setor (exclui role "admin" da exibição)
        const badgesSetor = user.roles
            .filter(r => r.name.toLowerCase() !== "admin")
            .map(r => {
                const n = r.name.toLowerCase();
                let cls = "role-badge ";
                if (n === "jurídico" || n === "juridico") cls += "role-user setor-juridico";
                else if (n === "suprimentos")              cls += "role-user setor-suprimentos";
                else if (n.includes("gest"))               cls += "role-user setor-gestao";
                else                                       cls += "role-user";
                return `<span class="${cls}">${r.name}</span>`;
            }).join(" ") || `<span style="color:var(--text-secondary);font-size:.78rem">—</span>`;

        // Regras de proteção para o toggle
        const ehContaPropria  = user.id === _meuUserId;
        const ultimoAdmin     = eAdmin && totalAdmins <= 1;
        const podeRebaixar    = eAdmin && !ehContaPropria && !ultimoAdmin;
        const podePromover    = !eAdmin;
        const togglePermitido = podeRebaixar || podePromover;

        const tooltip = ehContaPropria
            ? "Você não pode alterar sua própria conta aqui"
            : ultimoAdmin
            ? "Último admin — não é possível remover"
            : eAdmin ? "Clique para remover permissão de Admin" : "Clique para tornar Admin";

        tr.innerHTML = `
            <td>${user.username}</td>
            <td>${formatarNome(user.username)}</td>
            <td>${badgesSetor}</td>
            <td>
                <label class="toggle-admin-label"
                       title="${tooltip}"
                       style="display:inline-flex;align-items:center;gap:.5rem;
                              cursor:${togglePermitido ? "pointer" : "not-allowed"};
                              opacity:${ehContaPropria || ultimoAdmin ? ".5" : "1"};
                              user-select:none">
                    <div class="toggle-switch" style="pointer-events:none">
                        <input type="checkbox" ${eAdmin ? "checked" : ""} disabled>
                        <div class="toggle-track admin-track"><div class="toggle-thumb"></div></div>
                    </div>
                    <span style="font-size:.78rem;font-weight:600;
                                 color:${eAdmin ? "var(--purple)" : "var(--text-secondary)"}">
                        ${eAdmin ? "Admin" : "Usuário"}
                    </span>
                </label>
            </td>
            <td><div class="actions-cell">
                <button class="btn-edit"   onclick="abrirEditarUsuario(${user.id})">${SVG.edit} Editar</button>
                <button class="btn-delete" onclick="confirmarExclusao(${user.id}, 'user')">${SVG.trash} Excluir</button>
            </div></td>`;

        if (togglePermitido) {
            tr.querySelector(".toggle-admin-label").addEventListener("click", () => {
                toggleAdmin(user.id, !eAdmin, totalAdmins);
            });
        }

        tbody.appendChild(tr);
    });
}

function renderizarTabelaSetores(filtro = "") {
    const tbody = document.getElementById("sectors-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    let setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    if (filtro) {
        const t = filtro.toLowerCase();
        setores = setores.filter(r =>
            r.name.toLowerCase().includes(t) ||
            (r.description || "").toLowerCase().includes(t)
        );
    }

    if (!setores.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="preview-empty">${filtro ? "Nenhum resultado." : "Nenhum setor."}</td></tr>`;
        return;
    }

    setores.forEach(role => {
        const tr     = document.createElement("tr");
        const criado = role.created_at ? new Date(role.created_at).toLocaleDateString("pt-BR") : "—";
        tr.innerHTML = `
            <td>${role.name}</td>
            <td>${role.description || "—"}</td>
            <td>${criado}</td>
            <td><div class="actions-cell">
                <button class="btn-edit"   onclick="abrirEditarSetor(${role.id})">${SVG.edit} Editar</button>
                <button class="btn-delete" onclick="confirmarExclusao(${role.id}, 'sector')">${SVG.trash} Excluir</button>
            </div></td>`;
        tbody.appendChild(tr);
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  BUSCAS
// ════════════════════════════════════════════════════════════════════════════

function configurarBuscas() {
    document.getElementById("search-users")?.addEventListener("input", e => renderizarTabelaUsuarios(e.target.value.trim()));
    document.getElementById("search-sectors")?.addEventListener("input", e => renderizarTabelaSetores(e.target.value.trim()));
    document.getElementById("search-perm-viewer")?.addEventListener("input", e => renderizarListaViewers(e.target.value.trim()));
    document.getElementById("search-perm-target")?.addEventListener("input", e => filtrarTargets(e.target.value.trim()));
}

// ════════════════════════════════════════════════════════════════════════════
//  ABAS
// ════════════════════════════════════════════════════════════════════════════

function switchTab(aba) {
    ["users", "sectors", "permissoes"].forEach(s => {
        document.getElementById(`section-${s}`)?.classList.toggle("hidden",  s !== aba);
        document.getElementById(`tab-${s}-btn`)?.classList.toggle("active",  s === aba);
    });
    if (aba === "permissoes") renderizarAbaPermissoes();
}

// ════════════════════════════════════════════════════════════════════════════
//  ABA PERMISSÕES
// ════════════════════════════════════════════════════════════════════════════

async function renderizarAbaPermissoes() {
    const listaEl = document.getElementById("perm-viewers-list");
    if (listaEl) listaEl.innerHTML = `<p class="preview-empty">Carregando...</p>`;

    try {
        const res = await fetch(`${API}/admin/visibility`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(10000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (!res.ok) throw new Error(`Erro ${res.status}`);

        _permCache = await res.json();
        renderizarListaViewers("", _permCache);

    } catch (err) {
        console.error("❌ renderizarAbaPermissoes:", err);
        if (listaEl) listaEl.innerHTML = `<p class="preview-empty" style="color:var(--red)">Erro ao carregar permissões.</p>`;
        showToast("Erro ao carregar permissões de visibilidade.", "error");
    }
}

function renderizarListaViewers(filtro = "", data = null) {
    const container = document.getElementById("perm-viewers-list");
    if (!container) return;
    if (data) _permCache = data;

    let usuarios = allUsers.filter(u =>
        u.role !== "admin" && !u.roles.some(r => r.name.toLowerCase() === "admin")
    );
    if (filtro) {
        const t = filtro.toLowerCase();
        usuarios = usuarios.filter(u =>
            u.username.toLowerCase().includes(t) ||
            formatarNome(u.username).toLowerCase().includes(t)
        );
    }

    if (!usuarios.length) { container.innerHTML = `<p class="preview-empty">Nenhum usuário encontrado.</p>`; return; }

    container.innerHTML = usuarios.map(u => {
        const nome        = formatarNome(u.username);
        const cor         = avatarColor(u.id);
        const selecionado = permViewerSelecionado === u.id;
        const entrada     = (_permCache.permissoes || []).find(p => p.viewer_id === u.id);
        const qtdTargets  = entrada ? (entrada.can_see || []).length : 0;
        const qtdSetores  = entrada ? (entrada.sectors || []).length : 0;
        const temPerm     = qtdTargets > 0 || qtdSetores > 0;
        return `
        <div class="perm-viewer-card ${selecionado ? "selecionado" : ""}" onclick="selecionarViewer(${u.id})" data-viewer-id="${u.id}">
            <div class="perm-avatar" style="background:${cor}22;color:${cor}">${nome.charAt(0).toUpperCase()}</div>
            <div class="perm-viewer-info">
                <span class="perm-viewer-nome">${nome}</span>
                <span class="perm-viewer-email">${u.username}</span>
            </div>
            <div class="perm-viewer-badge ${temPerm ? "com-perm" : "sem-perm"}">
                ${temPerm ? SVG.eye : SVG.eyeOff}
            </div>
        </div>`;
    }).join("");

    if (permViewerSelecionado !== null) renderizarPainelDireito(permViewerSelecionado);
}

async function selecionarViewer(viewerId) {
    permViewerSelecionado = viewerId;
    document.querySelectorAll(".perm-viewer-card").forEach(el => {
        el.classList.toggle("selecionado", parseInt(el.dataset.viewerId) === viewerId);
    });
    document.getElementById("perm-targets-painel")?.classList.remove("hidden");
    document.getElementById("perm-painel-vazio")?.classList.add("hidden");

    const entradaCache = (_permCache.permissoes || []).find(p => p.viewer_id === viewerId);
    permTargetsSelecionados = entradaCache ? (entradaCache.can_see || []).map(t => t.target_id || t.id) : [];
    permSetoresSelecionados = entradaCache ? (entradaCache.sectors || []) : [];
    renderizarPainelDireito(viewerId);

    try {
        const res = await fetch(`${API}/admin/visibility/${viewerId}`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(10000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        const data = await res.json();
        permTargetsSelecionados = (data.can_see || []).map(t => t.id);
        permSetoresSelecionados = data.sectors || [];
        renderizarPainelDireito(viewerId);
    } catch (err) {
        console.error("❌ selecionarViewer:", err);
        showToast("Erro ao carregar permissões deste usuário.", "error");
    }
}

function renderizarPainelDireito(viewerId) {
    const viewer   = allUsers.find(u => u.id === viewerId);
    const nome     = viewer ? formatarNome(viewer.username) : "Usuário";
    const cor      = avatarColor(viewerId);
    const iniciais = nome.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();

    const header = document.getElementById("perm-painel-header");
    if (header) {
        header.innerHTML = `
            <div class="perm-painel-header-info">
                <div class="perm-painel-avatar" style="background:${cor}22;color:${cor}">${iniciais}</div>
                <div class="perm-painel-nome-wrap">
                    <span class="perm-painel-nome">${nome}</span>
                    <span class="perm-painel-subtitulo">pode visualizar contratos de:</span>
                </div>
            </div>
            <div class="perm-painel-acoes">
                <button class="btn-revogar-tudo" onclick="revogarTodasPermissoes()" type="button">
                    ${SVG.xCircle} Revogar tudo
                </button>
                <button class="btn-submit" id="btn-salvar-permissoes" onclick="salvarPermissoes()" type="button">
                    ${SVG.save} Salvar
                </button>
            </div>`;
    }

    renderizarSetoresGrid();
    renderizarListaTargets();
    atualizarResumoPerm();
}

function renderizarSetoresGrid() {
    const grid = document.getElementById("perm-setores-grid");
    if (!grid) return;

    const setores = allRoles
        .filter(r => r.name.toLowerCase() !== "admin")
        .map((r, i) => ({
            slug:  _slugSetor(r.name),
            nome:  r.name,
            emoji: _emojiSetor(r.name),
            cor:   _SETOR_CORES[i % _SETOR_CORES.length],
        }));

    if (!setores.length) {
        grid.innerHTML = `<p style="color:var(--text-secondary);font-size:.82rem;padding:.5rem">Nenhum setor cadastrado.</p>`;
        return;
    }

    grid.innerHTML = setores.map(s => {
        const ativo = permSetoresSelecionados.includes(s.slug);
        return `
        <div class="perm-setor-item ${ativo ? "ativo" : ""}" id="setor-item-${s.slug}">
            <div class="perm-setor-header">
                <span class="perm-setor-icon">${s.emoji}</span>
                <div class="perm-setor-info-wrap">
                    <span class="perm-setor-nome">${s.nome}</span>
                    <span class="perm-setor-desc">Ver todos os contratos do setor</span>
                </div>
            </div>
            <label class="toggle-switch" title="Liberar acesso ao setor ${s.nome}">
                <input type="checkbox" ${ativo ? "checked" : ""} onchange="toggleSetor('${s.slug}', this)">
                <div class="toggle-track"><div class="toggle-thumb"></div></div>
            </label>
        </div>`;
    }).join("");
}

function renderizarListaTargets(filtro = "") {
    const container = document.getElementById("perm-targets-lista");
    if (!container) return;

    let possiveis = allUsers.filter(u =>
        u.id !== permViewerSelecionado &&
        u.role !== "admin" &&
        !u.roles.some(r => r.name.toLowerCase() === "admin")
    );

    if (filtro) {
        const t = filtro.toLowerCase();
        possiveis = possiveis.filter(u =>
            formatarNome(u.username).toLowerCase().includes(t) ||
            u.username.toLowerCase().includes(t)
        );
    }

    if (!possiveis.length) { container.innerHTML = `<p class="preview-empty" style="padding:.75rem 0">Nenhum usuário disponível.</p>`; return; }

    container.innerHTML = possiveis.map(u => {
        const nome      = formatarNome(u.username);
        const cor       = avatarColor(u.id);
        const iniciais  = nome.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
        const marcado   = permTargetsSelecionados.includes(u.id);
        const setorNome = u.roles.filter(r => r.name.toLowerCase() !== "admin").map(r => r.name).join(", ") || "Sem setor";
        return `
        <div class="perm-target-item ${marcado ? "marcado" : ""}" data-target-id="${u.id}" onclick="toggleTarget(${u.id})">
            <div class="perm-radio"><div class="perm-radio-dot"></div></div>
            <div class="perm-avatar" style="background:${cor}22;color:${cor};width:32px;height:32px;font-size:.7rem;flex-shrink:0">${iniciais}</div>
            <div class="perm-target-info">
                <span class="perm-target-nome">${nome}</span>
                <span class="perm-target-setor">${setorNome}</span>
            </div>
            <span class="perm-target-status ${marcado ? "liberado" : ""}">${marcado ? "Liberado" : "Bloqueado"}</span>
        </div>`;
    }).join("");
}

function filtrarTargets(filtro) { renderizarListaTargets(filtro); }

function toggleSetor(slug, checkbox) {
    const item = document.getElementById(`setor-item-${slug}`);
    const idx  = permSetoresSelecionados.indexOf(slug);
    if (checkbox.checked) {
        if (idx === -1) permSetoresSelecionados.push(slug);
        item?.classList.add("ativo");
    } else {
        if (idx > -1) permSetoresSelecionados.splice(idx, 1);
        item?.classList.remove("ativo");
    }
    atualizarResumoPerm();
}

function toggleTarget(targetId) {
    const item = document.querySelector(`.perm-target-item[data-target-id="${targetId}"]`);
    const idx  = permTargetsSelecionados.indexOf(targetId);
    if (idx > -1) {
        permTargetsSelecionados.splice(idx, 1);
        item?.classList.remove("marcado");
        const s = item?.querySelector(".perm-target-status");
        if (s) { s.className = "perm-target-status"; s.textContent = "Bloqueado"; }
    } else {
        permTargetsSelecionados.push(targetId);
        item?.classList.add("marcado");
        const s = item?.querySelector(".perm-target-status");
        if (s) { s.className = "perm-target-status liberado"; s.textContent = "Liberado"; }
    }
    atualizarResumoPerm();
}

function atualizarResumoPerm() {
    const resumo = document.getElementById("perm-resumo");
    if (!resumo) return;
    const nU = permTargetsSelecionados.length;
    const nS = permSetoresSelecionados.length;
    if (nU === 0 && nS === 0) {
        resumo.innerHTML = '<span style="color:var(--text-secondary,#94a3b8)">Sem permissões — usuário vê apenas os próprios contratos.</span>';
        return;
    }
    const partes = [];
    if (nS > 0) {
        const nomesSetores = permSetoresSelecionados.map(s => _nomePorSlug(s)).join(", ");
        partes.push(`<strong style="color:var(--amber)">${nS} setor${nS > 1 ? "es" : ""}</strong> (${nomesSetores})`);
    }
    if (nU > 0) partes.push(`<strong style="color:var(--accent-blue)">${nU} colega${nU > 1 ? "s" : ""}</strong>`);
    resumo.innerHTML = `Acesso liberado para: ${partes.join(" e ")}`;
}

async function salvarPermissoes() {
    if (permViewerSelecionado === null) { showToast("Selecione um usuário primeiro.", "error"); return; }
    const btnSalvar = document.getElementById("btn-salvar-permissoes");
    if (btnSalvar) btnSalvar.disabled = true;
    try {
        const res = await fetch(`${API}/admin/visibility/${permViewerSelecionado}`, {
            method:  "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body:    JSON.stringify({ target_ids: permTargetsSelecionados, sector_slugs: permSetoresSelecionados }),
            signal:  AbortSignal.timeout(10000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (res.status === 403) { showToast("Permissão negada.", "error"); return; }
        if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Erro ${res.status}`); }

        showToast("Permissões salvas com sucesso!", "success");
        const total = permTargetsSelecionados.length + permSetoresSelecionados.length;
        _atualizarBadgeViewer(permViewerSelecionado, total);

        const entryIdx = (_permCache.permissoes || []).findIndex(p => p.viewer_id === permViewerSelecionado);
        const entry = {
            viewer_id: permViewerSelecionado,
            can_see:   permTargetsSelecionados.map(id => ({ id, target_id: id })),
            sectors:   [...permSetoresSelecionados]
        };
        if (entryIdx > -1) _permCache.permissoes[entryIdx] = entry;
        else { if (!_permCache.permissoes) _permCache.permissoes = []; _permCache.permissoes.push(entry); }

    } catch (err) {
        console.error("❌ salvarPermissoes:", err);
        showToast(err.message || "Erro ao salvar permissões.", "error");
    } finally {
        if (btnSalvar) btnSalvar.disabled = false;
    }
}

function revogarTodasPermissoes() {
    if (permViewerSelecionado === null) return;
    permTargetsSelecionados = [];
    permSetoresSelecionados = [];
    renderizarPainelDireito(permViewerSelecionado);
    showToast("Permissões removidas — clique em Salvar para confirmar.", "success");
}

function _atualizarBadgeViewer(viewerId, qtd) {
    const badge = document.querySelector(`.perm-viewer-card[data-viewer-id="${viewerId}"] .perm-viewer-badge`);
    if (!badge) return;
    badge.className = `perm-viewer-badge ${qtd > 0 ? "com-perm" : "sem-perm"}`;
    badge.innerHTML = qtd > 0 ? SVG.eye : SVG.eyeOff;
}

// ════════════════════════════════════════════════════════════════════════════
//  FORMULÁRIOS
// ════════════════════════════════════════════════════════════════════════════

function configurarFormularios() {

    document.getElementById("user-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn = document.querySelector('[form="user-form"].btn-submit');
        if (btn) btn.disabled = true;
        const roleDropdown = document.getElementById("user-role-dropdown");
        const papel = roleDropdown?._getValue ? roleDropdown._getValue() : "user";
        const payload = {
            username: document.getElementById("user-email").value.trim(),
            password: document.getElementById("user-password").value,
            role:     papel,
            role_ids: [...selectedSectorIds]
        };
        if (papel === "admin") {
            const adminRole = allRoles.find(r => r.name.toLowerCase() === "admin");
            if (adminRole && !payload.role_ids.includes(adminRole.id)) payload.role_ids.push(adminRole.id);
        }
        try {
            const res = await fetch(`${API}/admin/users`, {
                method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Erro ${res.status}`); }
            e.target.reset();
            selectedSectorIds = [];
            document.getElementById("sectors-list-badges")?._reset?.();
            document.getElementById("user-role-dropdown")?._reset?.();
            await carregarDados();
            showToast("Usuário criado com sucesso!", "success");
        } catch (err) {
            console.error("❌ criar usuário:", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("sector-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn = document.querySelector('[form="sector-form"].btn-submit');
        if (btn) btn.disabled = true;
        const payload = {
            name:        document.getElementById("sector-name").value.trim(),
            description: document.getElementById("sector-description").value.trim()
        };
        try {
            const res = await fetch(`${API}/admin/roles`, {
                method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Erro ${res.status}`); }
            e.target.reset();
            await carregarDados();
            showToast("Setor criado com sucesso!", "success");
        } catch (err) {
            console.error("❌ criar setor:", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("edit-user-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn = e.target.querySelector(".btn-submit");
        if (btn) btn.disabled = true;
        const userId  = document.getElementById("edit-user-id").value;
        const payload = {
            username: document.getElementById("edit-user-email").value.trim(),
            role_ids: [...editSectorIds]
        };
        const senha = document.getElementById("edit-user-password").value;
        if (senha) payload.password = senha;

        // Se o toggle de admin do modal estiver presente, inclui o role
        const adminToggleEl = document.getElementById("edit-admin-toggle");
        if (adminToggleEl) {
            payload.role = adminToggleEl.checked ? "admin" : "user";
        }

        try {
            const res = await fetch(`${API}/admin/users/${userId}`, {
                method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Erro ${res.status}`); }
            closeEditUserModal();
            await carregarDados();
            showToast("Usuário atualizado!", "success");
        } catch (err) {
            console.error("❌ editar usuário:", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("edit-sector-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn = e.target.querySelector(".btn-submit");
        if (btn) btn.disabled = true;
        const sectorId = document.getElementById("edit-sector-id").value;
        const payload  = {
            name:        document.getElementById("edit-sector-name").value.trim(),
            description: document.getElementById("edit-sector-description").value.trim()
        };
        try {
            const res = await fetch(`${API}/admin/roles/${sectorId}`, {
                method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Erro ${res.status}`); }
            closeEditSectorModal();
            await carregarDados();
            showToast("Setor atualizado!", "success");
        } catch (err) {
            console.error("❌ editar setor:", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("confirm-delete-btn")?.addEventListener("click", async () => {
        const { id, type } = itemToDelete;
        if (!id) return;
        const endpoint   = type === "user" ? `${API}/admin/users/${id}` : `${API}/admin/roles/${id}`;
        const btnConfirm = document.getElementById("confirm-delete-btn");
        if (btnConfirm) btnConfirm.disabled = true;
        try {
            const res = await fetch(endpoint, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) throw new Error(`Erro ${res.status}`);
            closeDeleteModal();
            await carregarDados();
            showToast("Item excluído com sucesso!", "success");
        } catch (err) {
            console.error("❌ excluir:", err);
            showToast(err.message, "error");
        } finally {
            if (btnConfirm) btnConfirm.disabled = false;
        }
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  MODAIS
// ════════════════════════════════════════════════════════════════════════════

function abrirEditarUsuario(userId) {
    const user = allUsers.find(u => u.id === userId);
    if (!user) return;

    const eAdmin = user.role === "admin" || user.roles.some(r => r.name.toLowerCase() === "admin");
    editSectorIds = user.roles.filter(r => r.name.toLowerCase() !== "admin").map(r => r.id);

    document.getElementById("edit-user-id").value       = user.id;
    document.getElementById("edit-user-email").value    = user.username;
    document.getElementById("edit-user-name").value     = formatarNome(user.username);
    document.getElementById("edit-user-password").value = "";

    // ── Proteções ────────────────────────────────────────────────────────────
    const totalAdmins    = allUsers.filter(u =>
        u.role === "admin" || u.roles.some(r => r.name.toLowerCase() === "admin")
    ).length;
    const ehContaPropria = userId === _meuUserId;
    const ultimoAdmin    = eAdmin && totalAdmins <= 1;
    const desabilitado   = ehContaPropria || ultimoAdmin;
    const avisoTexto     = ehContaPropria
        ? "Você não pode alterar sua própria conta."
        : ultimoAdmin
        ? "Não é possível remover o único administrador."
        : "";

    // ── Injeta bloco de admin no modal se não existir (compatível com HTML antigo) ──
    if (!document.getElementById("edit-admin-wrap")) {
        // Insere estilos necessários se ainda não existirem
        if (!document.getElementById("admin-toggle-styles")) {
            const style = document.createElement("style");
            style.id = "admin-toggle-styles";
            style.textContent = `
                .edit-admin-row {
                    display:flex; align-items:center; justify-content:space-between;
                    padding:.65rem .85rem;
                    background:var(--input-bg,#1a253d);
                    border:1px solid rgba(255,255,255,0.08);
                    border-radius:8px;
                }
                .edit-admin-row-left  { display:flex; flex-direction:column; gap:.15rem; }
                .edit-admin-row-title { font-size:.85rem; font-weight:600; color:#fff; }
                .edit-admin-row-desc  { font-size:.73rem; color:#94a3b8; }
                .edit-admin-aviso {
                    display:none; font-size:.75rem; color:#f59e0b;
                    margin-top:.35rem; padding:.35rem .65rem;
                    background:rgba(245,158,11,0.08);
                    border-radius:6px; border:1px solid rgba(245,158,11,0.2);
                }
                #edit-admin-toggle:checked ~ .toggle-track {
                    background-color:rgba(139,92,246,0.15)!important;
                    border-color:#8b5cf6!important;
                }
                #edit-admin-toggle:checked ~ .toggle-track .toggle-thumb {
                    background-color:#8b5cf6!important;
                }
            `;
            document.head.appendChild(style);
        }

        // Encontra o campo de setores de acesso e injeta o bloco depois dele
        const setoresField = document.getElementById("edit-sectors-list")?.closest(".field-group");
        const modalActions = document.querySelector("#edit-user-form .modal-actions");
        const insertBefore = modalActions || null;
        const form         = document.getElementById("edit-user-form");

        if (form) {
            const wrap = document.createElement("div");
            wrap.className = "field-group";
            wrap.id        = "edit-admin-wrap";
            wrap.innerHTML = `
                <label>Permissão de Administrador</label>
                <div class="edit-admin-row">
                    <div class="edit-admin-row-left">
                        <span class="edit-admin-row-title" id="edit-admin-label">Usuário comum</span>
                        <span class="edit-admin-row-desc">Acesso ao painel de administração</span>
                    </div>
                    <label class="toggle-switch" style="cursor:pointer;flex-shrink:0">
                        <input type="checkbox" id="edit-admin-toggle">
                        <div class="toggle-track"><div class="toggle-thumb"></div></div>
                    </label>
                </div>
                <span class="edit-admin-aviso" id="edit-admin-aviso"></span>`;

            if (insertBefore) {
                form.insertBefore(wrap, insertBefore);
            } else {
                form.appendChild(wrap);
            }
        }
    }

    // ── Configura o toggle ────────────────────────────────────────────────────
    const adminToggle = document.getElementById("edit-admin-toggle");
    const adminLabel  = document.getElementById("edit-admin-label");
    const adminWrap   = document.getElementById("edit-admin-wrap");
    const adminAviso  = document.getElementById("edit-admin-aviso");

    if (adminToggle) {
        adminToggle.checked  = eAdmin;
        adminToggle.disabled = desabilitado;

        if (adminLabel) adminLabel.textContent = eAdmin ? "Administrador" : "Usuário comum";
        if (adminWrap)  adminWrap.style.opacity = desabilitado ? "0.5" : "1";
        if (adminAviso) {
            adminAviso.textContent = avisoTexto;
            adminAviso.style.display = desabilitado ? "block" : "none";
        }

        adminToggle.onchange = () => {
            if (adminLabel) adminLabel.textContent = adminToggle.checked ? "Administrador" : "Usuário comum";
        };
    }

    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    criarDropdownSetores("edit-sectors-list", setores, editSectorIds);
    document.getElementById("edit-user-modal").classList.remove("hidden");
}

function closeEditUserModal() {
    document.getElementById("edit-user-modal").classList.add("hidden");
    document.getElementById("edit-sectors-list")?._destroy?.();
    // Remove o bloco injetado para que seja recriado limpo na próxima abertura
    document.getElementById("edit-admin-wrap")?.remove();
    editSectorIds = [];
}

function abrirEditarSetor(sectorId) {
    const role = allRoles.find(r => r.id === sectorId);
    if (!role) return;
    document.getElementById("edit-sector-id").value          = role.id;
    document.getElementById("edit-sector-name").value        = role.name;
    document.getElementById("edit-sector-description").value = role.description || "";
    document.getElementById("edit-sector-modal").classList.remove("hidden");
}

function closeEditSectorModal() { document.getElementById("edit-sector-modal").classList.add("hidden"); }

function confirmarExclusao(id, type) {
    itemToDelete = { id, type };
    document.getElementById("delete-modal").classList.remove("hidden");
}

function closeDeleteModal() {
    document.getElementById("delete-modal").classList.add("hidden");
    itemToDelete = { id: null, type: null };
}

// ════════════════════════════════════════════════════════════════════════════
//  TECLADO
// ════════════════════════════════════════════════════════════════════════════

function configurarTeclado() {
    document.addEventListener("keydown", e => {
        if (e.key !== "Escape") return;
        closeEditUserModal();
        closeEditSectorModal();
        closeDeleteModal();
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════════════════════

function formatarNome(username) {
    const raw = username.includes("@") ? username.split("@")[0] : username;
    return raw.split(/[._\-]/).map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");
}

function avatarColor(userId) {
    const palette = ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#14b8a6"];
    return palette[userId % palette.length];
}

function redirecionarLogin() {
    localStorage.removeItem("userToken");
    localStorage.removeItem("token");
    window.location.href = "login.html";
}

// ════════════════════════════════════════════════════════════════════════════
//  TOAST
// ════════════════════════════════════════════════════════════════════════════

function showToast(msg, tipo = "success") {
    const toast = document.getElementById("toast");
    const icon  = document.getElementById("toast-icon");
    const text  = document.getElementById("toast-message");
    if (!toast) return;
    icon.textContent = tipo === "success" ? "✅" : "❌";
    text.textContent = msg;
    toast.className  = `toast ${tipo}`;
    toast.classList.remove("hidden");
    void toast.offsetWidth;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.style.opacity    = "0";
        toast.style.transform  = "translateY(12px)";
        toast.style.transition = "opacity 0.3s, transform 0.3s";
        setTimeout(() => {
            toast.classList.add("hidden");
            toast.style.opacity = toast.style.transform = toast.style.transition = "";
        }, 320);
    }, 3500);
}