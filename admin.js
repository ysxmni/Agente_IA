// ════════════════════════════════════════════════════════════════════════════
//  OPERSAN — admin.js  (permissões por usuário E por setor)
// ════════════════════════════════════════════════════════════════════════════

const API   = "https://agente-ia-62sa.onrender.com";
const token = localStorage.getItem("userToken") || localStorage.getItem("token") || "";

// ─── ESTADO ──────────────────────────────────────────────────────────────────

let allUsers            = [];
let allRoles            = [];
let selectedSectorIds   = [];
let editSectorIds       = [];
let itemToDelete        = { id: null, type: null };

// Estado da aba de permissões de visibilidade
let permViewerSelecionado    = null;
let permTargetsSelecionados  = [];   // IDs de usuários com acesso individual
let permSetoresSelecionados  = [];   // slugs de setores liberados por setor inteiro

// Cache das permissões vindas do backend
let _permCache = { permissoes: [], users: [] };

// Mapa de slug de setor → nome exibível
const SETOR_NOMES = {
    juridico:        "Jurídico",
    suprimentos:     "Suprimentos",
    gestaocontratos: "Gestão de Contratos",
};

// Metadados de setor: slug normalizado → ícone, cor de borda, classe CSS
const SETOR_META = {
    juridico:        { emoji: "⚖️", classe: "juridico" },
    jurídico:        { emoji: "⚖️", classe: "juridico" },
    suprimentos:     { emoji: "📦", classe: "suprimentos" },
    gestaocontratos: { emoji: "📁", classe: "gestaocontratos" },
    "gestão de contratos": { emoji: "📁", classe: "gestaocontratos" },
};

/** Normaliza nome de setor para chave do SETOR_META */
function _slugSetor(nome) {
    return nome.toLowerCase().replace(/\s+/g, "").replace("ã", "a").replace("ç", "c").replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("ú", "u");
}

function _metaSetor(nomeRole) {
    const chave = nomeRole.toLowerCase();
    const chaveSlug = _slugSetor(nomeRole);
    return SETOR_META[chave] || SETOR_META[chaveSlug] || { emoji: "🏢", classe: "" };
}

// ─── BOOT ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
    if (!token) {
        window.location.href = "login.html";
        return;
    }

    try {
        const res = await fetch(`${API}/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(8000)
        });
        if (res.status === 401) {
            localStorage.removeItem("userToken");
            localStorage.removeItem("token");
            window.location.href = "login.html";
            return;
        }
        if (!res.ok) throw new Error(`Erro ${res.status} ao verificar permissão`);

        const me      = await res.json();
        const isAdmin =
            (me.role || "").toLowerCase() === "admin" ||
            (me.roles || []).some(r => r.name?.toLowerCase() === "admin");

        if (!isAdmin) {
            sessionStorage.setItem("accessDenied", "true");
            window.location.href = "index.html";
            return;
        }

        configurarPerfilAdmin(me);

    } catch (err) {
        console.error("❌ Verificação de permissão:", err.message);
        mostrarErroPermissao(err.message);
        return;
    }

    await carregarDados();
    configurarFormularios();
    configurarTeclado();
    configurarBuscas();
});

// ─── ERRO DE PERMISSÃO ────────────────────────────────────────────────────────

function mostrarErroPermissao(mensagem) {
    document.body.innerHTML = `
        <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;
            justify-content:center;background:#0a0c14;color:#fff;font-family:'Sora',sans-serif;
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

// ─── PERFIL ───────────────────────────────────────────────────────────────────

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

// ─── CARREGAR DADOS ───────────────────────────────────────────────────────────

async function carregarDados() {
    try {
        let resUsers, resRoles;
        try {
            resUsers = await fetch(`${API}/admin/users`, {
                headers: { Authorization: `Bearer ${token}` },
                signal: AbortSignal.timeout(8000)
            });
        } catch (e) {
            throw new Error("Servidor indisponível. Verifique se o backend está rodando na porta 8000.");
        }
        try {
            resRoles = await fetch(`${API}/admin/roles`, {
                headers: { Authorization: `Bearer ${token}` },
                signal: AbortSignal.timeout(8000)
            });
        } catch (e) {
            throw new Error("Não foi possível carregar setores do servidor.");
        }

        if (resUsers.status === 401 || resRoles.status === 401) {
            localStorage.removeItem("userToken");
            localStorage.removeItem("token");
            window.location.href = "login.html";
            return;
        }
        if (!resUsers.ok) throw new Error(`Erro ao carregar usuários (${resUsers.status})`);
        if (!resRoles.ok) throw new Error(`Erro ao carregar setores (${resRoles.status})`);

        allUsers = await resUsers.json();
        allRoles = await resRoles.json();

        renderizarStats();
        renderizarTabelaUsuarios();
        renderizarTabelaSetores();
        renderizarBadgesSetores();
        renderizarPreviewUsuarios();
        renderizarPreviewSetores();

        if (!document.getElementById("section-permissoes")?.classList.contains("hidden")) {
            await renderizarAbaPermissoes();
        }

        lucide.createIcons();

    } catch (err) {
        console.error("❌ carregarDados:", err);
        renderizarBadgesSetores();
        renderizarPreviewUsuarios();
        renderizarPreviewSetores();
        lucide.createIcons();
        showToast("⚠️ " + err.message, "error");
    }
}

// ─── STATS ────────────────────────────────────────────────────────────────────

function renderizarStats() {
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    const admins  = allUsers.filter(u => u.roles.some(r => r.name.toLowerCase() === "admin"));
    document.getElementById("total-users").textContent   = allUsers.length;
    document.getElementById("total-sectors").textContent = setores.length;
    document.getElementById("total-admins").textContent  = admins.length;
}

// ─── BADGES DE SELEÇÃO DE SETOR ───────────────────────────────────────────────

function renderizarBadgesSetores() {
    const container = document.getElementById("sectors-list-badges");
    if (!container) return;
    container.innerHTML = "";

    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    if (setores.length === 0) {
        container.innerHTML = '<span class="badge-loading">Nenhum setor cadastrado ainda. Crie um setor primeiro.</span>';
        return;
    }
    setores.forEach(role => {
        const badge = document.createElement("span");
        badge.className   = "badge inactive";
        badge.textContent = role.name;
        badge.dataset.id  = role.id;
        badge.dataset.setorNome = role.name;
        if (selectedSectorIds.includes(role.id)) {
            badge.classList.replace("inactive", "active");
        }
        badge.addEventListener("click", () => toggleBadge(role.id, badge, selectedSectorIds));
        container.appendChild(badge);
    });
}

function toggleBadge(id, element, lista) {
    const idx = lista.indexOf(id);
    if (idx > -1) {
        lista.splice(idx, 1);
        element.classList.replace("active", "inactive");
    } else {
        lista.push(id);
        element.classList.replace("inactive", "active");
    }
}

// ─── PREVIEW LATERAL — USUÁRIOS ───────────────────────────────────────────────

function renderizarPreviewUsuarios() {
    const container = document.getElementById("preview-users-list");
    const counter   = document.getElementById("preview-users-count");
    if (!container) return;

    const naoAdmin = allUsers.filter(u => !u.roles.some(r => r.name.toLowerCase() === "admin"));
    if (counter) counter.textContent = naoAdmin.length;

    if (naoAdmin.length === 0) {
        container.innerHTML = '<p class="preview-empty">Nenhum usuário cadastrado ainda.</p>';
        return;
    }

    container.innerHTML = naoAdmin.map(u => {
        const inicial    = (u.username.split("@")[0] || "U").charAt(0).toUpperCase();
        const nome       = formatarNome(u.username);
        const setores    = u.roles.filter(r => r.name.toLowerCase() !== "admin");

        const badgesHtml = setores.length
            ? setores.map(r => {
                const slug = _slugSetor(r.name);
                return `<span class="preview-role-badge" data-setor="${slug}">${r.name}</span>`;
              }).join("")
            : `<span class="preview-role-badge sem-setor">sem setor</span>`;

        return `
        <div class="preview-user-card">
            <div class="preview-avatar">${inicial}</div>
            <div class="preview-user-info">
                <span class="preview-user-name">${nome}</span>
                <div class="preview-roles">${badgesHtml}</div>
            </div>
        </div>`;
    }).join("");
}

// ─── PREVIEW LATERAL — SETORES ────────────────────────────────────────────────

function renderizarPreviewSetores() {
    const container = document.getElementById("preview-sectors-list");
    const counter   = document.getElementById("preview-sectors-count");
    if (!container) return;

    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    if (counter) counter.textContent = setores.length;

    if (setores.length === 0) {
        container.innerHTML = '<p class="preview-empty">Nenhum setor cadastrado ainda.</p>';
        return;
    }

    container.innerHTML = setores.map(role => {
        const meta     = _metaSetor(role.name);
        const qtdUsers = allUsers.filter(u => u.roles.some(r => r.id === role.id)).length;

        return `
        <div class="preview-sector-card" data-classe="${meta.classe}">
            <div class="preview-sector-icon" data-classe="${meta.classe}">${meta.emoji}</div>
            <div class="preview-sector-info">
                <span class="preview-sector-name" data-classe="${meta.classe}">${role.name}</span>
                <span class="preview-sector-count">${qtdUsers} usuário${qtdUsers !== 1 ? "s" : ""}</span>
            </div>
        </div>`;
    }).join("");
}

// ─── TABELA DE USUÁRIOS ───────────────────────────────────────────────────────

function renderizarTabelaUsuarios(filtro = "") {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    let lista = [...allUsers];
    if (filtro) {
        const t = filtro.toLowerCase();
        lista   = lista.filter(u =>
            u.username.toLowerCase().includes(t) ||
            formatarNome(u.username).toLowerCase().includes(t) ||
            u.roles.some(r => r.name.toLowerCase().includes(t))
        );
    }

    if (lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="preview-empty">${filtro ? "Nenhum resultado encontrado." : "Nenhum usuário cadastrado."}</td></tr>`;
        return;
    }

    lista.forEach(user => {
        const tr = document.createElement("tr");
        const badgesRole = user.roles.map(r => {
            const nome = r.name.toLowerCase();
            let classe = "role-badge ";
            if (nome === "admin") {
                classe += "role-admin";
            } else if (nome === "jurídico" || nome === "juridico") {
                classe += "role-user setor-juridico";
            } else if (nome === "suprimentos") {
                classe += "role-user setor-suprimentos";
            } else if (nome.includes("gest")) {
                classe += "role-user setor-gestao";
            } else {
                classe += "role-user";
            }
            // ── Nome do papel: primeira letra maiúscula, sem forçar lowercase ──
            return `<span class="${classe}">${r.name}</span>`;
        }).join(" ");
        tr.innerHTML = `
            <td>${user.username}</td>
            <td>${formatarNome(user.username)}</td>
            <td>${badgesRole}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn-edit" onclick="abrirEditarUsuario(${user.id})">
                        <i data-lucide="edit-3"></i> Editar
                    </button>
                    <button class="btn-delete" onclick="confirmarExclusao(${user.id}, 'user')">
                        <i data-lucide="trash-2"></i> Excluir
                    </button>
                </div>
            </td>`;
        tbody.appendChild(tr);
    });

    lucide.createIcons();
}

// ─── TABELA DE SETORES ────────────────────────────────────────────────────────

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

    if (setores.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="preview-empty">${filtro ? "Nenhum resultado encontrado." : "Nenhum setor cadastrado."}</td></tr>`;
        return;
    }

    setores.forEach(role => {
        const tr     = document.createElement("tr");
        const criado = role.created_at
            ? new Date(role.created_at).toLocaleDateString("pt-BR")
            : "—";
        // ── CORRIGIDO: removido .toLowerCase() — nome exibido como vem do backend ──
        tr.innerHTML = `
            <td>${role.name}</td>
            <td>${role.description || "—"}</td>
            <td>${criado}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn-edit" onclick="abrirEditarSetor(${role.id})">
                        <i data-lucide="edit-3"></i> Editar
                    </button>
                    <button class="btn-delete" onclick="confirmarExclusao(${role.id}, 'sector')">
                        <i data-lucide="trash-2"></i> Excluir
                    </button>
                </div>
            </td>`;
        tbody.appendChild(tr);
    });

    lucide.createIcons();
}

// ─── BUSCAS ───────────────────────────────────────────────────────────────────

function configurarBuscas() {
    document.getElementById("search-users")?.addEventListener("input", e => {
        renderizarTabelaUsuarios(e.target.value.trim());
        lucide.createIcons();
    });
    document.getElementById("search-sectors")?.addEventListener("input", e => {
        renderizarTabelaSetores(e.target.value.trim());
        lucide.createIcons();
    });
    document.getElementById("search-perm-viewer")?.addEventListener("input", e => {
        renderizarListaViewers(e.target.value.trim());
    });
    document.getElementById("search-perm-target")?.addEventListener("input", e => {
        filtrarTargets(e.target.value.trim());
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  ABA: PERMISSÕES DE VISIBILIDADE
// ════════════════════════════════════════════════════════════════════════════

async function renderizarAbaPermissoes() {
    const listaEl = document.getElementById("perm-viewers-list");
    if (listaEl) listaEl.innerHTML = `<p class="preview-empty">Carregando...</p>`;

    try {
        const res = await fetch(`${API}/admin/visibility`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(8000)
        });
        if (res.status === 401) { redirecionarLogin(); return; }
        if (!res.ok) throw new Error(`Erro ${res.status}`);

        _permCache = await res.json();
        renderizarListaViewers("", _permCache);
        lucide.createIcons();

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

    let usuarios = allUsers.filter(u => !u.roles.some(r => r.name.toLowerCase() === "admin"));
    if (filtro) {
        const t = filtro.toLowerCase();
        usuarios = usuarios.filter(u =>
            u.username.toLowerCase().includes(t) ||
            formatarNome(u.username).toLowerCase().includes(t)
        );
    }

    if (usuarios.length === 0) {
        container.innerHTML = `<p class="preview-empty">Nenhum usuário encontrado.</p>`;
        return;
    }

    container.innerHTML = usuarios.map(u => {
        const nome       = formatarNome(u.username);
        const inicial    = nome.charAt(0).toUpperCase();
        const cor        = avatarColor(u.id);
        const selecionado = permViewerSelecionado === u.id;

        const entrada    = (_permCache.permissoes || []).find(p => p.viewer_id === u.id);
        const qtdTargets = entrada ? (entrada.can_see || []).length : 0;
        const qtdSetores = entrada ? (entrada.sectors || []).length : 0;
        const temPerm    = qtdTargets > 0 || qtdSetores > 0;

        let labelPerm = "";
        if (temPerm) {
            const partes = [];
            if (qtdSetores > 0) partes.push(`${qtdSetores} setor${qtdSetores > 1 ? "es" : ""}`);
            if (qtdTargets > 0) partes.push(`${qtdTargets} colega${qtdTargets > 1 ? "s" : ""}`);
            labelPerm = partes.join(" + ");
        }

        return `
        <div class="perm-viewer-card ${selecionado ? "selecionado" : ""}"
             onclick="selecionarViewer(${u.id})"
             data-viewer-id="${u.id}">
            <div class="perm-avatar" style="background:${cor}22;color:${cor}">${inicial}</div>
            <div class="perm-viewer-info">
                <span class="perm-viewer-nome">${nome}</span>
                <span class="perm-viewer-email">${u.username}</span>
            </div>
            <div class="perm-viewer-badge ${temPerm ? "com-perm" : "sem-perm"}" title="${labelPerm}">
                ${temPerm
                    ? `<i data-lucide="eye"></i>`
                    : `<i data-lucide="eye-off"></i>`}
            </div>
        </div>`;
    }).join("");

    lucide.createIcons();

    if (permViewerSelecionado !== null) {
        renderizarPainelDireito(permViewerSelecionado);
    }
}

async function selecionarViewer(viewerId) {
    permViewerSelecionado = viewerId;

    document.querySelectorAll(".perm-viewer-card").forEach(el => {
        el.classList.toggle("selecionado", parseInt(el.dataset.viewerId) === viewerId);
    });

    const painel = document.getElementById("perm-targets-painel");
    const vazio  = document.getElementById("perm-painel-vazio");
    if (painel) painel.classList.remove("hidden");
    if (vazio)  vazio.classList.add("hidden");

    const entradaCache = (_permCache.permissoes || []).find(p => p.viewer_id === viewerId);
    permTargetsSelecionados = entradaCache
        ? (entradaCache.can_see || []).map(t => t.target_id || t.id)
        : [];
    permSetoresSelecionados = entradaCache
        ? (entradaCache.sectors || [])
        : [];

    renderizarPainelDireito(viewerId);

    try {
        const res = await fetch(`${API}/admin/visibility/${viewerId}`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(8000)
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
                    <i data-lucide="x-circle"></i> Revogar tudo
                </button>
                <button class="btn-submit" id="btn-salvar-permissoes" onclick="salvarPermissoes()" type="button">
                    <i data-lucide="save"></i> Salvar
                </button>
            </div>`;
        lucide.createIcons();
    }

    renderizarSetoresGrid();
    renderizarListaTargets();
    atualizarResumoPerm();
}

function renderizarSetoresGrid() {
    const grid = document.getElementById("perm-setores-grid");
    if (!grid) return;

    const setoresSistema = [
        { slug: "juridico",        nome: "Jurídico",            icon: "⚖️",  cor: "#3b82f6" },
        { slug: "suprimentos",     nome: "Suprimentos",         icon: "📦",  cor: "#10b981" },
        { slug: "gestaocontratos", nome: "Gestão de Contratos", icon: "📁",  cor: "#f59e0b" },
    ];

    if (setoresSistema.length === 0) {
        grid.innerHTML = `<p class="perm-section-desc" style="grid-column:1/-1">Nenhum setor disponível.</p>`;
        return;
    }

    grid.innerHTML = setoresSistema.map(s => {
        const ativo = permSetoresSelecionados.includes(s.slug);
        return `
        <div class="perm-setor-item ${ativo ? "ativo" : ""}" id="setor-item-${s.slug}">
            <div class="perm-setor-header">
                <span class="perm-setor-icon">${s.icon}</span>
                <div class="perm-setor-info-wrap">
                    <span class="perm-setor-nome">${s.nome}</span>
                    <span class="perm-setor-desc">Ver todos os contratos do setor + analista</span>
                </div>
            </div>
            <label class="toggle-switch" title="Liberar acesso ao setor ${s.nome}">
                <input type="checkbox" ${ativo ? "checked" : ""}
                    onchange="toggleSetor('${s.slug}', this)">
                <div class="toggle-track">
                    <div class="toggle-thumb"></div>
                </div>
            </label>
        </div>`;
    }).join("");
}

function renderizarListaTargets(filtro = "") {
    const container = document.getElementById("perm-targets-lista");
    if (!container) return;

    let possiveis = allUsers.filter(u =>
        u.id !== permViewerSelecionado &&
        !u.roles.some(r => r.name.toLowerCase() === "admin")
    );

    if (filtro) {
        const t = filtro.toLowerCase();
        possiveis = possiveis.filter(u =>
            formatarNome(u.username).toLowerCase().includes(t) ||
            u.username.toLowerCase().includes(t)
        );
    }

    if (possiveis.length === 0) {
        container.innerHTML = `<p class="preview-empty" style="padding:.75rem 0">Nenhum usuário disponível.</p>`;
        return;
    }

    container.innerHTML = possiveis.map(u => {
        const nome      = formatarNome(u.username);
        const cor       = avatarColor(u.id);
        const iniciais  = nome.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
        const marcado   = permTargetsSelecionados.includes(u.id);
        const setorNome = u.roles.filter(r => r.name.toLowerCase() !== "admin")
                               .map(r => r.name).join(", ") || "Sem setor";

        return `
        <div class="perm-target-item ${marcado ? "marcado" : ""}"
             data-target-id="${u.id}"
             onclick="toggleTarget(${u.id})">
            <div class="perm-radio">
                <div class="perm-radio-dot"></div>
            </div>
            <div class="perm-avatar" style="background:${cor}22;color:${cor};width:32px;height:32px;font-size:.7rem">
                ${iniciais}
            </div>
            <div class="perm-target-info">
                <span class="perm-target-nome">${nome}</span>
                <span class="perm-target-setor">${setorNome}</span>
            </div>
            <span class="perm-target-status ${marcado ? "liberado" : ""}">
                ${marcado ? "Liberado" : "Bloqueado"}
            </span>
        </div>`;
    }).join("");
}

function filtrarTargets(filtro) {
    renderizarListaTargets(filtro);
}

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
        const status = item?.querySelector(".perm-target-status");
        if (status) { status.className = "perm-target-status"; status.textContent = "Bloqueado"; }
    } else {
        permTargetsSelecionados.push(targetId);
        item?.classList.add("marcado");
        const status = item?.querySelector(".perm-target-status");
        if (status) { status.className = "perm-target-status liberado"; status.textContent = "Liberado"; }
    }

    atualizarResumoPerm();
}

function atualizarResumoPerm() {
    const resumo = document.getElementById("perm-resumo");
    if (!resumo) return;

    const nU = permTargetsSelecionados.length;
    const nS = permSetoresSelecionados.length;

    if (nU === 0 && nS === 0) {
        resumo.innerHTML = '<span style="color:var(--text-3)">Sem permissões — usuário vê apenas os próprios contratos</span>';
        return;
    }

    const partes = [];
    if (nS > 0) {
        const nomesSetores = permSetoresSelecionados.map(s => SETOR_NOMES[s] || s).join(", ");
        partes.push(`<strong style="color:var(--amber)">${nS} setor${nS > 1 ? "es" : ""}</strong> (${nomesSetores})`);
    }
    if (nU > 0) {
        partes.push(`<strong style="color:var(--blue)">${nU} colega${nU > 1 ? "s" : ""}</strong>`);
    }
    resumo.innerHTML = `Acesso liberado: ${partes.join(" e ")}`;
}

async function salvarPermissoes() {
    if (permViewerSelecionado === null) {
        showToast("Selecione um usuário primeiro.", "error");
        return;
    }

    const btnSalvar = document.getElementById("btn-salvar-permissoes");
    if (btnSalvar) btnSalvar.disabled = true;

    try {
        const res = await fetch(`${API}/admin/visibility/${permViewerSelecionado}`, {
            method:  "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({
                target_ids:   permTargetsSelecionados,
                sector_slugs: permSetoresSelecionados,
            }),
            signal: AbortSignal.timeout(8000)
        });

        if (res.status === 401) { redirecionarLogin(); return; }
        if (res.status === 403) { showToast("Permissão negada.", "error"); return; }
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Erro ${res.status}`);
        }

        showToast("Permissões salvas com sucesso!", "success");

        const total = permTargetsSelecionados.length + permSetoresSelecionados.length;
        _atualizarBadgeViewer(permViewerSelecionado, total);

        const entryIdx = (_permCache.permissoes || []).findIndex(p => p.viewer_id === permViewerSelecionado);
        const entry = {
            viewer_id: permViewerSelecionado,
            can_see:   permTargetsSelecionados.map(id => ({ id, target_id: id })),
            sectors:   [...permSetoresSelecionados],
        };
        if (entryIdx > -1) {
            _permCache.permissoes[entryIdx] = entry;
        } else {
            if (!_permCache.permissoes) _permCache.permissoes = [];
            _permCache.permissoes.push(entry);
        }

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
    const viewerCard = document.querySelector(`.perm-viewer-card[data-viewer-id="${viewerId}"]`);
    const badge = viewerCard?.querySelector(".perm-viewer-badge");
    if (!badge) return;
    badge.className = `perm-viewer-badge ${qtd > 0 ? "com-perm" : "sem-perm"}`;
    badge.innerHTML = qtd > 0
        ? `<i data-lucide="eye"></i>`
        : `<i data-lucide="eye-off"></i>`;
    lucide.createIcons();
}

// ─── FORMULÁRIOS ─────────────────────────────────────────────────────────────

function configurarFormularios() {

    document.getElementById("user-form")?.addEventListener("submit", async e => {
        e.preventDefault();

        // ✅ CORREÇÃO: o botão "Criar Usuário" fica no .preview-create-aside,
        // FORA do <form>, por isso e.target.querySelector(".btn-submit") retornava
        // null e causava crash silencioso antes do fetch ser chamado.
        // Solução: buscar o botão no documento pelo atributo form="user-form".
        const btn = document.querySelector('[form="user-form"].btn-submit')
                 || e.target.querySelector(".btn-submit");
        if (btn) btn.disabled = true;

        const payload = {
            username: document.getElementById("user-email").value.trim(),
            password: document.getElementById("user-password").value,
            role_ids: [...selectedSectorIds]
        };
        const papel = document.getElementById("user-role").value;
        if (papel === "admin") {
            const adminRole = allRoles.find(r => r.name.toLowerCase() === "admin");
            if (adminRole && !payload.role_ids.includes(adminRole.id)) {
                payload.role_ids.push(adminRole.id);
            }
        }
        try {
            const res = await fetch(`${API}/admin/users`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body:    JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            e.target.reset();
            selectedSectorIds = [];
            document.querySelectorAll("#sectors-list-badges .badge").forEach(b => b.classList.replace("active", "inactive"));
            await carregarDados();
            showToast("Usuário criado com sucesso!", "success");
        } catch (err) {
            console.error("❌", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("sector-form")?.addEventListener("submit", async e => {
        e.preventDefault();

        // ✅ CORREÇÃO: mesmo problema do formulário de usuário — o botão
        // "Criar Setor" está no .preview-create-aside, FORA do <form>.
        // e.target.querySelector(".btn-submit") retornava null → crash silencioso
        // → fetch nunca era executado → setor nunca era criado.
        // Solução: buscar o botão no documento pelo atributo form="sector-form".
        const btn = document.querySelector('[form="sector-form"].btn-submit')
                 || e.target.querySelector(".btn-submit");
        if (btn) btn.disabled = true;

        const payload = {
            name:        document.getElementById("sector-name").value.trim(),
            description: document.getElementById("sector-description").value.trim()
        };
        try {
            const res = await fetch(`${API}/admin/roles`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body:    JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            e.target.reset();
            await carregarDados();
            showToast("Setor criado com sucesso!", "success");
        } catch (err) {
            console.error("❌", err);
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    });

    document.getElementById("edit-user-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn    = e.target.querySelector(".btn-submit");
        btn.disabled = true;
        const userId  = document.getElementById("edit-user-id").value;
        const payload = {
            username: document.getElementById("edit-user-email").value.trim(),
            role_ids: [...editSectorIds]
        };
        const senha = document.getElementById("edit-user-password").value;
        if (senha) payload.password = senha;
        try {
            const res = await fetch(`${API}/admin/users/${userId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body:    JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            closeEditUserModal();
            await carregarDados();
            showToast("Usuário atualizado!", "success");
        } catch (err) {
            console.error("❌", err);
            showToast(err.message, "error");
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById("edit-sector-form")?.addEventListener("submit", async e => {
        e.preventDefault();
        const btn      = e.target.querySelector(".btn-submit");
        btn.disabled   = true;
        const sectorId = document.getElementById("edit-sector-id").value;
        const payload  = {
            name:        document.getElementById("edit-sector-name").value.trim(),
            description: document.getElementById("edit-sector-description").value.trim()
        };
        try {
            const res = await fetch(`${API}/admin/roles/${sectorId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body:    JSON.stringify(payload)
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Erro ${res.status}`);
            }
            closeEditSectorModal();
            await carregarDados();
            showToast("Setor atualizado!", "success");
        } catch (err) {
            console.error("❌", err);
            showToast(err.message, "error");
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById("confirm-delete-btn")?.addEventListener("click", async () => {
        const { id, type } = itemToDelete;
        if (!id) return;
        const endpoint = type === "user" ? `${API}/admin/users/${id}` : `${API}/admin/roles/${id}`;
        const btnConfirm = document.getElementById("confirm-delete-btn");
        if (btnConfirm) btnConfirm.disabled = true;
        try {
            const res = await fetch(endpoint, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.status === 401) { redirecionarLogin(); return; }
            if (!res.ok) throw new Error(`Erro ${res.status}`);
            closeDeleteModal();
            await carregarDados();
            showToast("Item excluído com sucesso!", "success");
        } catch (err) {
            console.error("❌", err);
            showToast(err.message, "error");
        } finally {
            if (btnConfirm) btnConfirm.disabled = false;
        }
    });
}

// ─── MODAIS ───────────────────────────────────────────────────────────────────

function abrirEditarUsuario(userId) {
    const user = allUsers.find(u => u.id === userId);
    if (!user) return;
    editSectorIds = user.roles.map(r => r.id);
    document.getElementById("edit-user-id").value       = user.id;
    document.getElementById("edit-user-email").value    = user.username;
    document.getElementById("edit-user-name").value     = formatarNome(user.username);
    document.getElementById("edit-user-password").value = "";
    const container = document.getElementById("edit-sectors-list");
    container.innerHTML = "";
    const setores = allRoles.filter(r => r.name.toLowerCase() !== "admin");
    if (setores.length === 0) {
        container.innerHTML = '<span class="badge-loading">Nenhum setor cadastrado.</span>';
    } else {
        setores.forEach(role => {
            const badge         = document.createElement("span");
            const isActive      = editSectorIds.includes(role.id);
            badge.className     = isActive ? "badge active" : "badge inactive";
            badge.textContent   = role.name;
            badge.dataset.id    = role.id;
            badge.dataset.setorNome = role.name;
            badge.addEventListener("click", () => toggleBadge(role.id, badge, editSectorIds));
            container.appendChild(badge);
        });
    }
    document.getElementById("edit-user-modal").classList.remove("hidden");
    lucide.createIcons();
}

function closeEditUserModal() {
    document.getElementById("edit-user-modal").classList.add("hidden");
    editSectorIds = [];
}

function abrirEditarSetor(sectorId) {
    const role = allRoles.find(r => r.id === sectorId);
    if (!role) return;
    document.getElementById("edit-sector-id").value          = role.id;
    document.getElementById("edit-sector-name").value        = role.name;
    document.getElementById("edit-sector-description").value = role.description || "";
    document.getElementById("edit-sector-modal").classList.remove("hidden");
    lucide.createIcons();
}

function closeEditSectorModal() {
    document.getElementById("edit-sector-modal").classList.add("hidden");
}

function confirmarExclusao(id, type) {
    itemToDelete = { id, type };
    document.getElementById("delete-modal").classList.remove("hidden");
    lucide.createIcons();
}

function closeDeleteModal() {
    document.getElementById("delete-modal").classList.add("hidden");
    itemToDelete = { id: null, type: null };
}

// ─── ABAS ─────────────────────────────────────────────────────────────────────

function switchTab(aba) {
    ["users", "sectors", "permissoes"].forEach(s => {
        document.getElementById(`section-${s}`)?.classList.toggle("hidden", s !== aba);
        document.getElementById(`tab-${s}-btn`)?.classList.toggle("active",  s === aba);
    });
    if (aba === "permissoes") renderizarAbaPermissoes();
    lucide.createIcons();
}

// ─── TECLADO ──────────────────────────────────────────────────────────────────

function configurarTeclado() {
    document.addEventListener("keydown", e => {
        if (e.key !== "Escape") return;
        closeEditUserModal();
        closeEditSectorModal();
        closeDeleteModal();
    });
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function formatarNome(username) {
    const raw = username.includes("@") ? username.split("@")[0] : username;
    return raw.split(/[._\-]/).map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");
}

function avatarColor(userId) {
    const palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#14b8a6"];
    return palette[userId % palette.length];
}

function redirecionarLogin() {
    localStorage.removeItem("userToken");
    localStorage.removeItem("token");
    window.location.href = "login.html";
}

// ─── TOAST ───────────────────────────────────────────────────────────────────

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
            toast.style.opacity    = "";
            toast.style.transform  = "";
            toast.style.transition = "";
        }, 320);
    }, 3500);
}