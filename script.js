// ════════════════════════════════════════════════════════════════════════════
//  OPERSAN — script.js  (visibilidade por usuário e por setor com badge analista)
// ════════════════════════════════════════════════════════════════════════════

const API = "https://agente-ia-62sa.onrender.com";

// ─── ESTADO GLOBAL ───────────────────────────────────────────────────────────

let setoresDisponiveis = [
    { id: "juridico",        nome: "Jurídico",            icon: "scale",         cor: "#3b82f6" },
    { id: "suprimentos",     nome: "Suprimentos",         icon: "package",       cor: "#10b981" },
    { id: "gestaocontratos", nome: "Gestão de Contratos", icon: "folder-kanban", cor: "#f59e0b" }
];

let setorSelecionado      = "juridico";
let setorChatAtivo        = "juridico";
let setorFiltroAtivo      = "todos";
let todosContratos        = [];
let contratoParaExcluirId = null;
let _enviandoPergunta     = false;

// ─── ESTADO DE PERSPECTIVA ────────────────────────────────────────────────────
let perspectiva = {
    analystId: null,
    escopo:    "meus"
};

let usuariosVisiveis = [];
let setoresVisiveis  = [];

const usuario = {
    nome: "", role: "", roles: [], isAdmin: false, setoresPermitidos: [],
    id: null,
    get token() {
        return localStorage.getItem("userToken") || localStorage.getItem("token") || "";
    }
};

let state = (() => {
    try {
        const s = localStorage.getItem("contratoState");
        return s ? JSON.parse(s) : _estadoInicial();
    } catch { return _estadoInicial(); }
})();

function _estadoInicial() {
    return { contratoCarregado: false, resumo: "", mensagens: [], nomeContrato: "", idAtivo: null };
}
function salvarEstado() { localStorage.setItem("contratoState", JSON.stringify(state)); }
function limparEstado() {
    state = _estadoInicial();
    localStorage.removeItem("contratoState");
    localStorage.removeItem("idAtivo");
}

// ─── BOOT ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
    if (!localStorage.getItem("userToken") && localStorage.getItem("token")) {
        localStorage.setItem("userToken", localStorage.getItem("token"));
    }

    if (!usuario.token) {
        window.location.href = "login.html";
        return;
    }

    try {
        await autenticarUsuario();
    } catch (err) {
        console.error("❌ Autenticação falhou:", err.message);
        localStorage.removeItem("userToken");
        window.location.href = "login.html";
        return;
    }

    await carregarVisibilidade();

    if (typeof renderizarSidebar === "function") {
        renderizarSidebar({ username: usuario.nome, role: usuario.role, roles: usuario.roles });
    }

    configurarSetores();
    configurarPerfil();
    renderizarSetoresChat();
    configurarEventos();

    if (state.contratoCarregado && state.resumo) {
        renderResumo(state.resumo);
        state.mensagens.forEach(m => adicionarMensagem(m.autor, m.texto, false));
        habilitarChat(true);
        atualizarStatus("✅ SISTEMA PRONTO", "success");
    } else {
        renderTelaInicial();
        habilitarChat(false);
    }

    if (typeof lucide !== "undefined") lucide.createIcons();
});

// ─── AUTENTICAÇÃO ─────────────────────────────────────────────────────────────

async function autenticarUsuario() {
    if (!usuario.token) throw new Error("Token não encontrado.");
    const res = await fetch(`${API}/users/me`, {
        headers: { Authorization: `Bearer ${usuario.token}` }
    });
    if (!res.ok) throw new Error(`Token inválido (${res.status})`);
    const data = await res.json();

    const raw = data.username || "";
    usuario.nome = raw.includes("@")
        ? raw.split("@")[0].split(/[._-]/).map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ")
        : raw;
    usuario.id      = data.id;
    usuario.role    = data.role || (data.roles?.[0]?.name) || "user";
    usuario.roles   = data.roles || [];
    usuario.isAdmin = usuario.role.toLowerCase() === "admin" ||
                      usuario.roles.some(r => r.name?.toLowerCase() === "admin");

    localStorage.setItem("userName", usuario.nome);
    localStorage.setItem("userRole", usuario.role.toLowerCase());
    if (data.id) localStorage.setItem("userId", data.id);
}

// ─── VISIBILIDADE ─────────────────────────────────────────────────────────────

async function carregarVisibilidade() {
    if (usuario.isAdmin) {
        try {
            const res = await fetch(`${API}/admin/users`, {
                headers: { Authorization: `Bearer ${usuario.token}` }
            });
            if (res.ok) {
                const todos = await res.json();
                usuariosVisiveis = todos
                    .filter(u => !u.roles.some(r => r.name?.toLowerCase() === "admin"))
                    .map(u => ({
                        id:       u.id,
                        username: u.username,
                        nome:     _formatarNome(u.username),
                        iniciais: _getIniciais(_formatarNome(u.username)),
                        cor:      _avatarColor(u.id)
                    }));
            }
        } catch (e) {
            console.warn("⚠️ Admin: lista de usuários não carregada:", e.message);
        }
        setoresVisiveis = Object.keys({ juridico: 1, suprimentos: 1, gestaocontratos: 1 });
        return;
    }

    try {
        const res = await fetch(`${API}/my/visibility`, {
            headers: { Authorization: `Bearer ${usuario.token}` }
        });
        if (res.ok) {
            const data    = await res.json();
            usuariosVisiveis = data.can_see || [];
            setoresVisiveis  = data.sectors  || [];
        }
    } catch (e) {
        console.warn("⚠️ Visibilidade não carregada:", e.message);
        usuariosVisiveis = [];
        setoresVisiveis  = [];
    }
}

// ─── SETORES ─────────────────────────────────────────────────────────────────

const MAPA_SETORES = {
    "admin":                  ["juridico", "suprimentos", "gestaocontratos"],
    "jurídico":               ["juridico"],
    "juridico":               ["juridico"],
    "suprimentos":            ["suprimentos"],
    "gestão de contratos":    ["gestaocontratos"],
    "gestaocontratos":        ["gestaocontratos"],
};

function configurarSetores() {
    if (usuario.isAdmin) {
        usuario.setoresPermitidos = ["juridico", "suprimentos", "gestaocontratos"];
    } else {
        let p = MAPA_SETORES[usuario.role.toLowerCase()];
        if (!p) {
            p = [];
            usuario.roles.forEach(r => {
                const s = MAPA_SETORES[r.name.toLowerCase()];
                if (s) s.forEach(x => { if (!p.includes(x)) p.push(x); });
            });
        }
        usuario.setoresPermitidos = (p && p.length) ? p : ["juridico"];
    }
    setorSelecionado = setorChatAtivo = usuario.setoresPermitidos[0];
}

function renderizarSetoresChat() {
    const container = document.getElementById("chatSetorButtons");
    if (!container) return;
    const setores = setoresDisponiveis.filter(s => usuario.setoresPermitidos.includes(s.id));
    if (!setores.length) { container.innerHTML = ""; return; }

    if (setores.length === 1) {
        setorChatAtivo = setores[0].id;
        container.innerHTML = `<div class="chat-setor-badge-unico"><i data-lucide="${setores[0].icon}"></i> ${setores[0].nome}</div>`;
        if (typeof lucide !== "undefined") lucide.createIcons();
        return;
    }

    container.innerHTML = setores.map(s =>
        `<button type="button" class="chat-setor-btn ${s.id === setorChatAtivo ? "ativo" : "inativo"}"
            data-setor="${s.id}" onclick="selecionarSetorChat('${s.id}')">
            <i data-lucide="${s.icon}"></i> ${s.nome}
        </button>`
    ).join("");
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function selecionarSetorChat(id) {
    if (!usuario.setoresPermitidos.includes(id)) return;
    setorChatAtivo = setorSelecionado = id;
    renderizarSetoresChat();
    const s = setoresDisponiveis.find(x => x.id === id);
    if (s) adicionarMensagem("ai", `Agora conversando com a IA de <strong>${s.nome}</strong>.`, true);
}

function renderizarFiltroSetores() {
    const container = document.getElementById("filtroSetores");
    if (!container) return;
    const setores = setoresDisponiveis.filter(s => usuario.setoresPermitidos.includes(s.id));
    if (!setores.length) { container.innerHTML = ""; return; }

    let html = "";
    if (setores.length > 1) {
        html += `<button type="button" class="filter-btn ${setorFiltroAtivo === "todos" ? "ativo" : "inativo"}"
            onclick="aplicarFiltroSetor('todos')"><i data-lucide="list"></i> Todos</button>`;
    }
    html += setores.map(s =>
        `<button type="button" class="filter-btn ${setorFiltroAtivo === s.id ? "ativo" : "inativo"}"
            onclick="aplicarFiltroSetor('${s.id}')"><i data-lucide="${s.icon}"></i> ${s.nome}</button>`
    ).join("");
    container.innerHTML = html;
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function aplicarFiltroSetor(id) {
    setorFiltroAtivo = id;
    renderizarFiltroSetores();
    filtrarContratos();
}

// ─── PERFIL ───────────────────────────────────────────────────────────────────

function configurarPerfil() {
    let nome = localStorage.getItem("userName") || usuario.nome || "Usuário";
    if (nome.includes("@")) {
        nome = nome.split("@")[0].split(/[._-]/)
            .map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");
    }
    const elNome   = document.querySelector(".user-name");
    const elAvatar = document.querySelector(".avatar");
    const elRole   = document.querySelector(".user-role");
    if (elNome)   elNome.textContent   = nome;
    if (elAvatar) elAvatar.textContent = nome.charAt(0).toUpperCase();
    if (elRole)   elRole.textContent   = usuario.isAdmin ? "Administrador" : (usuario.role || "Usuário");
}

// ─── EVENTOS ─────────────────────────────────────────────────────────────────

function validarBotao() {
    const input = document.getElementById("perguntaUser");
    const btn   = document.getElementById("btnEnviar");
    if (btn && input) {
        btn.disabled = !input.value.trim() || _enviandoPergunta;
    }
}

function configurarEventos() {
    const inputPergunta = document.getElementById("perguntaUser");
    const btnEnviar     = document.getElementById("btnEnviar");

    btnEnviar?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!_enviandoPergunta && inputPergunta?.value.trim()) enviarPergunta();
    });

    inputPergunta?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.stopPropagation();
            if (!_enviandoPergunta && inputPergunta.value.trim()) enviarPergunta();
        }
    });

    inputPergunta?.addEventListener("input", validarBotao);

    const formChat = document.getElementById("formChat");
    formChat?.addEventListener("submit", (e) => { e.preventDefault(); e.stopPropagation(); return false; });

    document.getElementById("inputArquivo")?.addEventListener("change", enviarContrato);
    document.getElementById("confirmDeleteBtn")?.addEventListener("click", executarExclusao);
    document.getElementById("searchInput")?.addEventListener("input", filtrarContratos);
    document.getElementById("clearSearch")?.addEventListener("click", limparPesquisa);

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            ["deleteModal", "novaAnaliseModal", "resumoModal", "logoutModal", "printModal", "avisoModal"].forEach(fecharModal);
        }
    });
}

// ─── UPLOAD ───────────────────────────────────────────────────────────────────

async function enviarContrato() {
    const input   = document.getElementById("inputArquivo");
    const arquivo = input?.files?.[0];
    if (!arquivo) return;

    const setorInfo = setoresDisponiveis.find(s => s.id === setorSelecionado);
    const nomeSetor = setorInfo?.nome || "Jurídico";
    atualizarStatus(`⏳ ANALISANDO PARA ${nomeSetor.toUpperCase()}...`, "processing");

    const fd = new FormData();
    fd.append("file",  arquivo);
    fd.append("setor", setorSelecionado);

    try {
        const res = await fetch(`${API}/upload`, {
            method:  "POST",
            headers: { Authorization: `Bearer ${usuario.token}` },
            body:    fd,
            signal:  AbortSignal.timeout(120000)
        });

        if (!res.ok) {
            const e = await res.json().catch(() => ({}));
            throw new Error(e.detail || `Erro ${res.status}`);
        }

        const data = await res.json();

        state.contratoCarregado = true;
        state.resumo            = data.resumo;
        state.nomeContrato      = data.nome || arquivo.name;
        state.idAtivo           = data.id;
        state.mensagens         = [];
        localStorage.setItem("idAtivo", data.id);
        salvarEstado();

        renderResumo(data.resumo);
        atualizarStatus("✅ ANÁLISE CONCLUÍDA!", "success");

        const chatBox = document.getElementById("chatBox");
        if (chatBox) {
            chatBox.innerHTML = "";
            adicionarMensagem("ai",
                `Documento <strong>${data.nome}</strong> analisado pelo setor <strong>${data.setor_nome || nomeSetor}</strong>. Faça suas perguntas!`,
                false
            );
        }

        habilitarChat(true);
        if (input) input.value = "";

    } catch (err) {
        console.error("❌ Upload:", err);
        atualizarStatus(`❌ Erro: ${err.message}`, "error");
        mostrarAviso("Erro no processamento: " + err.message, "error");
    }
}

// ─── CHAT ─────────────────────────────────────────────────────────────────────

async function enviarPergunta() {
    if (_enviandoPergunta) return;

    const input      = document.getElementById("perguntaUser");
    const pergunta   = input?.value.trim();
    const contratoId = state.idAtivo || localStorage.getItem("idAtivo");

    if (!pergunta) return;

    if (!contratoId) {
        adicionarMensagem("ai", "⚠️ Nenhum contrato carregado. Por favor, importe um contrato primeiro.", false);
        return;
    }

    _enviandoPergunta = true;
    validarBotao();

    adicionarMensagem("user", pergunta);
    input.value = "";

    const chatBox = document.getElementById("chatBox");
    const loading = document.createElement("div");
    loading.id        = "chatLoading";
    loading.className = "message system";
    loading.innerHTML = '<div class="message-content">⏳ Analisando...</div>';
    chatBox?.appendChild(loading);
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

    const fd = new FormData();
    fd.append("pergunta",    pergunta);
    fd.append("setor",       setorChatAtivo || "juridico");
    fd.append("contrato_id", contratoId);

    try {
        const res = await fetch(`${API}/perguntar`, {
            method:  "POST",
            headers: { Authorization: `Bearer ${usuario.token}` },
            body:    fd,
            signal:  AbortSignal.timeout(120000)
        });

        document.getElementById("chatLoading")?.remove();

        if (!res.ok) throw new Error(`Erro ${res.status} na resposta do servidor`);

        const data = await res.json();
        adicionarMensagem("ai", data.resposta || "Sem resposta.");

    } catch (err) {
        document.getElementById("chatLoading")?.remove();
        if (err.name === "TimeoutError") {
            adicionarMensagem("ai", "⏱️ A IA demorou muito para responder. Tente novamente.");
        } else {
            adicionarMensagem("ai", `❌ Erro: ${err.message}`);
        }
        console.error("❌ Pergunta:", err);
    } finally {
        _enviandoPergunta = false;
        const inp = document.getElementById("perguntaUser");
        if (inp) inp.disabled = false;
        validarBotao();
    }
}

function adicionarMensagem(autor, texto, salvar = true) {
    const chat = document.getElementById("chatBox");
    if (!chat) return;
    const msg = document.createElement("div");
    msg.className = `message ${autor === "ai" ? "system" : "user"}`;
    msg.innerHTML = `<div class="message-content">${texto.replace(/\n/g, "<br>")}</div>`;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
    if (salvar) { state.mensagens.push({ autor, texto }); salvarEstado(); }
}

function habilitarChat(ativo) {
    const btn   = document.getElementById("btnEnviar");
    const input = document.getElementById("perguntaUser");
    if (input) input.disabled = !ativo;
    if (btn) {
        if (ativo) {
            btn.removeAttribute("data-desabilitado");
            btn.disabled = !document.getElementById("perguntaUser")?.value.trim();
        } else {
            btn.setAttribute("data-desabilitado", "true");
            btn.disabled = true;
        }
    }
}

function limparChatVisual() {
    const chat = document.getElementById("chatBox");
    if (!chat) return;
    chat.innerHTML = '<div class="message system"><div class="message-content">Chat limpo. Continue fazendo perguntas.</div></div>';
    state.mensagens = [];
    salvarEstado();
}

// ─── BIBLIOTECA ───────────────────────────────────────────────────────────────

async function carregarHistorico() {
    const lista = document.getElementById("listaContratos");
    if (!lista) return;
    lista.innerHTML = "<p class='preview-empty'>Carregando biblioteca...</p>";

    renderizarSeletorPerspectiva();
    renderizarFiltroSetores();

    await _buscarEExibirContratos();
}

async function _buscarEExibirContratos() {
    const lista = document.getElementById("listaContratos");
    if (!lista) return;

    const params = new URLSearchParams();

    if (perspectiva.analystId !== null) {
        params.append("analyst_id", perspectiva.analystId);
    }
    if (setorFiltroAtivo !== "todos") {
        params.append("sector_id", setorFiltroAtivo);
    }

    const url = `${API}/contratos/listar?${params.toString()}`;

    try {
        const res = await fetch(url, {
            headers: { Authorization: `Bearer ${usuario.token}` }
        });
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        todosContratos = await res.json();
        renderizarContratos(todosContratos);
    } catch (err) {
        console.error("❌ Histórico:", err);
        lista.innerHTML = "<p class='preview-empty' style='color:#ef4444'>Erro ao conectar com a base de dados.</p>";
    }
}

// ─── SELETOR DE PERSPECTIVA ───────────────────────────────────────────────────

function renderizarSeletorPerspectiva() {
    const container = document.getElementById("seletorPerspectiva");
    if (!container) return;

    const temColegas = usuariosVisiveis.length > 0;
    const temSetores = setoresVisiveis.length > 0;

    if (!temColegas && !temSetores && !usuario.isAdmin) {
        container.innerHTML = "";
        return;
    }

    const euSelecionado = perspectiva.analystId === null;

    let indicadorHtml = "";
    if (!euSelecionado && perspectiva.analystId !== null) {
        const analista = usuariosVisiveis.find(u => u.id === perspectiva.analystId);
        if (analista) {
            indicadorHtml = `
            <div class="perspectiva-indicador">
                <i data-lucide="eye"></i>
                Visualizando análises de <strong>${analista.nome}</strong>
                <button class="btn-voltar-minha" onclick="voltarMinhasPerspectiva()">
                    ← Voltar às minhas
                </button>
            </div>`;
        }
    }

    let escopoHtml = "";
    if (usuario.isAdmin && perspectiva.analystId === null) {
        escopoHtml = `
        <div class="escopo-wrap">
            <span class="escopo-label">Escopo:</span>
            <button class="escopo-btn ${perspectiva.escopo === "meus" ? "ativo" : ""}"
                onclick="definirEscopo('meus')">
                <i data-lucide="user"></i> Meus contratos
            </button>
            <button class="escopo-btn ${perspectiva.escopo === "todos" ? "ativo" : ""}"
                onclick="definirEscopo('todos')">
                <i data-lucide="users"></i> Todos do setor
            </button>
        </div>`;
    }

    let setoresBadgesHtml = "";
    if (temSetores && !usuario.isAdmin) {
        const setoresInfo = setoresVisiveis.map(slug => {
            const s = setoresDisponiveis.find(x => x.id === slug);
            return s ? `<span class="setor-visivel-badge" style="color:${s.cor};background:${s.cor}15;border:1px solid ${s.cor}30">
                <i data-lucide="${s.icon}" style="width:11px;height:11px;display:inline;vertical-align:middle;margin-right:.25rem"></i>
                ${s.nome}
            </span>` : "";
        }).join("");
        if (setoresInfo) {
            setoresBadgesHtml = `
            <div class="setores-visiveis-wrap">
                <span class="perspectiva-label" style="font-size:.6rem">SETORES VISÍVEIS</span>
                <div style="display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.3rem">${setoresInfo}</div>
            </div>`;
        }
    }

    container.innerHTML = `
        <div class="perspectiva-wrap">
            ${temColegas || usuario.isAdmin ? `
            <span class="perspectiva-label">
                <i data-lucide="eye" style="display:inline;width:11px;height:11px;vertical-align:middle"></i>
                Perspectiva
            </span>
            <div class="perspectiva-selector">
                <button class="perspectiva-btn meu ${euSelecionado ? "ativo" : ""}"
                    onclick="selecionarPerspectiva(null)">
                    <span class="pav-avatar" style="background:#3b82f620;color:#3b82f6">
                        ${usuario.nome.charAt(0).toUpperCase()}
                    </span>
                    Meus contratos
                </button>
                ${usuariosVisiveis.map(u => `
                <button class="perspectiva-btn outro ${perspectiva.analystId === u.id ? "ativo" : ""}"
                    onclick="selecionarPerspectiva(${u.id})">
                    <span class="pav-avatar" style="background:${u.cor}20;color:${u.cor}">
                        ${(u.iniciais || u.nome.charAt(0)).toUpperCase()}
                    </span>
                    ${u.nome}
                </button>`).join("")}
            </div>` : ""}
            ${setoresBadgesHtml}
            ${escopoHtml}
            ${indicadorHtml}
        </div>`;

    if (typeof lucide !== "undefined") lucide.createIcons();
}

async function selecionarPerspectiva(analystId) {
    perspectiva.analystId = analystId;
    if (analystId !== null) perspectiva.escopo = "meus";
    renderizarSeletorPerspectiva();
    await _buscarEExibirContratos();
    if (typeof lucide !== "undefined") lucide.createIcons();
}

async function definirEscopo(escopo) {
    if (!usuario.isAdmin) return;
    perspectiva.escopo = escopo;
    renderizarSeletorPerspectiva();
    await _buscarEExibirContratos();
    if (typeof lucide !== "undefined") lucide.createIcons();
}

async function voltarMinhasPerspectiva() {
    perspectiva.analystId = null;
    perspectiva.escopo    = "meus";
    renderizarSeletorPerspectiva();
    await _buscarEExibirContratos();
    if (typeof lucide !== "undefined") lucide.createIcons();
}

// ─── RENDERIZAR CONTRATOS ─────────────────────────────────────────────────────

function renderizarContratos(lista) {
    const el = document.getElementById("listaContratos");
    if (!el) return;

    let filtrados = lista.filter(c =>
        setorFiltroAtivo === "todos"
            ? usuario.setoresPermitidos.includes((c.setor || "juridico").toLowerCase())
            : (c.setor || "juridico").toLowerCase() === setorFiltroAtivo
    );

    if (!filtrados.length) {
        const msg = perspectiva.analystId !== null
            ? "Este usuário não possui contratos neste setor."
            : "Nenhum contrato encontrado.";
        el.innerHTML = `<p class='preview-empty'>${msg}</p>`;
        atualizarContadorResultados(0, lista.length);
        return;
    }

    el.innerHTML = "";
    filtrados.forEach(c => {
        const s     = setoresDisponiveis.find(x => x.id === (c.setor || "juridico").toLowerCase());
        const badge = s
            ? `<span class="setor-badge-card" data-setor="${s.id}"><i data-lucide="${s.icon}"></i>${s.nome}</span>`
            : "";

        const mostrarAnalista = c.show_analyst && c.analista && c.analista.id;
        const analistaBadge   = mostrarAnalista
            ? `<span class="analista-badge">
                <i data-lucide="user"></i>${c.analista.nome}
               </span>`
            : "";

        const card = document.createElement("div");
        card.className = "history-card";
        card.innerHTML = `
            <div class="card-header"><h3>${c.nome}</h3></div>
            <div class="card-body">
                <div class="setor-badge-wrap">
                    ${badge}
                </div>
                <div class="date-tag">
                    <span class="date-tag-left">
                        <i data-lucide="calendar"></i>${new Date(c.data).toLocaleDateString("pt-BR")}
                    </span>
                    ${analistaBadge}
                </div>
                <p class="preview-text">${c.preview || ""}</p>
                <div class="card-actions">
                    <button type="button" onclick="abrirDoHistorico(${c.id})" class="btn-open">Abrir Análise</button>
                    ${c.is_mine || usuario.isAdmin
                        ? `<button type="button" onclick="solicitarExclusao(${c.id})" class="btn-delete-icon"><i data-lucide="trash-2"></i></button>`
                        : ""}
                </div>
            </div>`;
        el.appendChild(card);
    });

    if (typeof lucide !== "undefined") lucide.createIcons();
    atualizarContadorResultados(filtrados.length, lista.length);
}

function filtrarContratos() {
    const input = document.getElementById("searchInput");
    const clear = document.getElementById("clearSearch");
    const termo = input?.value.toLowerCase().trim() || "";
    if (clear) clear.classList.toggle("hidden", !termo);

    let filtrados = todosContratos.filter(c =>
        setorFiltroAtivo === "todos"
            ? usuario.setoresPermitidos.includes((c.setor || "juridico").toLowerCase())
            : (c.setor || "juridico").toLowerCase() === setorFiltroAtivo
    );

    if (termo) filtrados = filtrados.filter(c =>
        c.nome.toLowerCase().includes(termo) ||
        (c.preview || "").toLowerCase().includes(termo) ||
        new Date(c.data).toLocaleDateString("pt-BR").includes(termo) ||
        (c.analista?.nome || "").toLowerCase().includes(termo)
    );

    renderizarContratos(filtrados);
}

function limparPesquisa() {
    const i = document.getElementById("searchInput");
    if (i) { i.value = ""; filtrarContratos(); }
}

function atualizarContadorResultados(encontrados, total) {
    const el    = document.getElementById("searchResultCount");
    const input = document.getElementById("searchInput");
    if (!el) return;
    const temFiltro = input?.value.trim() || setorFiltroAtivo !== "todos";
    if (temFiltro && encontrados !== total) {
        el.textContent = `${encontrados} de ${total} contratos encontrados`;
        el.classList.remove("hidden");
    } else {
        el.classList.add("hidden");
    }
}

async function abrirDoHistorico(id) {
    try {
        const res = await fetch(`${API}/contratos/${id}`, {
            headers: { Authorization: `Bearer ${usuario.token}` }
        });
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        const data = await res.json();

        state.contratoCarregado = true;
        state.resumo            = data.resumo;
        state.nomeContrato      = data.nome;
        state.idAtivo           = id;
        state.mensagens         = data.mensagens || [];
        localStorage.setItem("idAtivo", id);
        salvarEstado();

        trocarAba("nova");
        renderResumo(data.resumo);
        atualizarStatus("✅ Contrato carregado", "success");

        const chat = document.getElementById("chatBox");
        if (chat) {
            chat.innerHTML = "";
            (data.mensagens || []).forEach(m => adicionarMensagem(m.autor, m.texto, false));
            if (!data.mensagens?.length) {
                let msg = `Contrato <strong>${data.nome}</strong> carregado.`;
                if (data.analista && data.analista.id !== usuario.id) {
                    msg += ` Analisado por <strong>${data.analista.nome}</strong>.`;
                }
                msg += " Faça suas perguntas!";
                adicionarMensagem("ai", msg, false);
            }
        }
        habilitarChat(true);
    } catch (err) {
        console.error("❌ Abrir:", err);
        mostrarAviso("Erro ao abrir contrato: " + err.message, "error");
    }
}

function solicitarExclusao(id) { contratoParaExcluirId = id; abrirModal("deleteModal"); }

async function executarExclusao() {
    try {
        const res = await fetch(`${API}/contratos/${contratoParaExcluirId}`, {
            method:  "DELETE",
            headers: { Authorization: `Bearer ${usuario.token}` }
        });
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        if (state.idAtivo == contratoParaExcluirId) limparEstado();
        fecharModal("deleteModal");
        carregarHistorico();
    } catch (err) {
        console.error("❌ Excluir:", err);
        mostrarAviso("Erro ao excluir: " + err.message, "error");
    }
}

// ─── ABAS ─────────────────────────────────────────────────────────────────────

function trocarAba(aba) {
    const isNova = aba === "nova";
    document.getElementById("abaNovaAnalise")?.classList.toggle("hidden", !isNova);
    document.getElementById("abaHistorico")?.classList.toggle("hidden", isNova);
    document.getElementById("tabNovaAnalise")?.classList.toggle("active", isNova);
    document.getElementById("tabHistorico")?.classList.toggle("active", !isNova);
    if (!isNova) carregarHistorico();
}

// ─── UI ───────────────────────────────────────────────────────────────────────

function renderResumo(texto) {
    const el = document.getElementById("resumoTexto");
    if (!el) return;
    el.innerHTML = texto.length > 350 ? texto.substring(0, 350) + "..." : texto;
    el.classList.remove("italic");
}

function renderTelaInicial() {
    const el = document.getElementById("resumoTexto");
    if (el) { el.innerHTML = "Nenhum documento processado."; el.classList.add("italic"); }
}

function atualizarStatus(texto, tipo) {
    const el = document.getElementById("status");
    if (!el) return;
    el.textContent = texto;
    el.className   = `status-badge ${tipo}`;
    el.classList.remove("hidden");
}

// ─── MODAL DE AVISO — substitui alert() nativo ───────────────────────────────

/**
 * Exibe um aviso padronizado no estilo do sistema, sem usar alert() nativo.
 * @param {string} mensagem  - Texto do aviso
 * @param {string} tipo      - "info" | "warning" | "error" | "success"
 */
function mostrarAviso(mensagem, tipo = "info") {
    let overlay = document.getElementById("avisoModal");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id        = "avisoModal";
        overlay.className = "modal-overlay hidden";
        overlay.innerHTML = `
            <div class="modal-card">
                <div class="modal-icon" id="avisoIcon"></div>
                <h3 id="avisoTitulo"></h3>
                <p  id="avisoTexto"></p>
                <div class="modal-actions">
                    <button type="button" onclick="fecharModal('avisoModal')" class="btn-primary">OK</button>
                </div>
            </div>`;
        overlay.addEventListener("click", (e) => { if (e.target === overlay) fecharModal("avisoModal"); });
        document.body.appendChild(overlay);
    }

    const icones = {
        info:    { svg: "info",           cls: "info"    },
        warning: { svg: "alert-triangle", cls: "warning" },
        error:   { svg: "alert-circle",   cls: "warning" },
        success: { svg: "check-circle-2", cls: "info"    },
    };
    const titulos = {
        info:    "Atenção",
        warning: "Atenção",
        error:   "Ocorreu um erro",
        success: "Concluído",
    };

    const cfg = icones[tipo] || icones.info;
    document.getElementById("avisoIcon").className = `modal-icon ${cfg.cls}`;
    document.getElementById("avisoIcon").innerHTML  = `<i data-lucide="${cfg.svg}"></i>`;
    document.getElementById("avisoTitulo").textContent = titulos[tipo] || "Aviso";
    document.getElementById("avisoTexto").textContent  = mensagem;

    abrirModal("avisoModal");
    if (typeof lucide !== "undefined") lucide.createIcons();
}

// ─── MODAIS ───────────────────────────────────────────────────────────────────

function abrirModal(id)  { document.getElementById(id)?.classList.remove("hidden"); }
function fecharModal(id) { document.getElementById(id)?.classList.add("hidden"); }

function novaAnalise()       { abrirModal("novaAnaliseModal"); }
function fazerLogout()       { abrirModal("logoutModal"); }
function fecharModalLogout() { fecharModal("logoutModal"); }
function fecharModalResumo() { fecharModal("resumoModal"); }

function confirmarLogout() {
    localStorage.clear();
    window.location.href = "login.html";
}

function executarResete() {
    limparEstado();
    renderTelaInicial();
    habilitarChat(false);
    const chat = document.getElementById("chatBox");
    if (chat) chat.innerHTML = '<div class="message system"><div class="message-content">Sistema pronto. Por favor, importe o contrato.</div></div>';
    const status = document.getElementById("status");
    if (status) status.classList.add("hidden");
    const inp = document.getElementById("inputArquivo");
    if (inp) inp.value = "";
    fecharModal("novaAnaliseModal");
    trocarAba("nova");
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function abrirModalResumo() {
    // Sem contrato: aviso padronizado no estilo do sistema — sem alert() nativo
    if (!state.resumo) {
        mostrarAviso("Nenhum documento carregado. Importe um contrato para ver a análise.", "warning");
        return;
    }
    const textoFull = document.getElementById("textoFull");
    if (textoFull) textoFull.innerHTML = state.resumo.replace(/\n/g, "<br>");
    const footer = document.querySelector("#resumoModal .modal-footer");
    if (footer) {
        footer.innerHTML = `
            <button type="button" onclick="fecharModal('resumoModal')" class="btn-modal-footer btn-cancelar"><i data-lucide="x"></i> Fechar</button>
            <button type="button" onclick="abrirModalImpressao()" class="btn-modal-footer btn-imprimir"><i data-lucide="printer"></i> Imprimir</button>
            <button type="button" id="btnCopiarResumo" onclick="copiarResumo()" class="btn-modal-footer btn-copiar"><i data-lucide="copy"></i> Copiar Texto</button>`;
        if (typeof lucide !== "undefined") lucide.createIcons();
    }
    abrirModal("resumoModal");
}

// ─── IMPRESSÃO VIA MODAL INTERNO ─────────────────────────────────────────────

/**
 * Abre a pré-visualização de impressão dentro de um modal do sistema,
 * usando um <iframe srcdoc> para evitar abertura de nova aba.
 */
function abrirModalImpressao() {
    fecharModal("resumoModal");

    // Cria o modal de impressão dinamicamente se ainda não existir
    let overlay = document.getElementById("printModal");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id        = "printModal";
        overlay.className = "modal-overlay hidden";
        overlay.innerHTML = `
            <div class="modal-card large print-modal-card">
                <div class="modal-header">
                    <div class="header-title">
                        <i data-lucide="printer"></i>
                        <h3>Imprimir Análise</h3>
                    </div>
                    <button type="button" onclick="fecharModalImpressao()" class="btn-close">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="print-preview-body">
                    <iframe id="printFrame" class="print-frame"></iframe>
                </div>
                <div class="modal-footer">
                    <button type="button" onclick="fecharModalImpressao()" class="btn-modal-footer btn-cancelar">
                        <i data-lucide="x"></i> Fechar
                    </button>
                    <button type="button" onclick="executarImpressao()" class="btn-modal-footer btn-imprimir">
                        <i data-lucide="printer"></i> Confirmar Impressão
                    </button>
                </div>
            </div>`;
        overlay.addEventListener("click", (e) => { if (e.target === overlay) fecharModalImpressao(); });
        document.body.appendChild(overlay);
    }

    // Injeta o HTML de impressão no iframe via srcdoc (sem nova aba)
    const frame = document.getElementById("printFrame");
    frame.srcdoc = _gerarHtmlImpressao();

    abrirModal("printModal");
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function fecharModalImpressao() {
    fecharModal("printModal");
    // Reabre o resumo ao fechar o modal de impressão
    abrirModal("resumoModal");
}

function executarImpressao() {
    const frame = document.getElementById("printFrame");
    if (frame?.contentWindow) {
        frame.contentWindow.focus();
        frame.contentWindow.print();
    }
}

function _gerarHtmlImpressao() {
    return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Análise — ${state.nomeContrato}</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Georgia', serif;
        color: #1a1a1a;
        font-size: 11pt;
        line-height: 1.7;
        padding: 2cm;
        background: #fff;
    }
    h1 {
        font-size: 18pt;
        color: #1e40af;
        border-bottom: 3px solid #3b82f6;
        padding-bottom: 10px;
        margin-bottom: 8px;
    }
    .meta {
        color: #64748b;
        font-size: 9.5pt;
        margin-bottom: 24px;
        font-family: Arial, sans-serif;
    }
    hr { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }
    .content {
        white-space: pre-wrap;
        text-align: justify;
        font-size: 10.5pt;
    }
    .footer {
        margin-top: 40px;
        font-size: 8.5pt;
        color: #94a3b8;
        border-top: 1px solid #e2e8f0;
        padding-top: 10px;
        font-family: Arial, sans-serif;
        text-align: center;
    }
    @media print { body { padding: 1.5cm; } }
</style>
</head>
<body>
    <h1>Análise Completa do Contrato</h1>
    <div class="meta">${state.nomeContrato} — ${new Date().toLocaleDateString("pt-BR", { day:"2-digit", month:"long", year:"numeric" })}</div>
    <hr>
    <div class="content">${state.resumo}</div>
    <div class="footer">Gerado pelo Sistema Opersan</div>
</body>
</html>`;
}

// ─── CÓPIA ────────────────────────────────────────────────────────────────────

function copiarResumo() {
    if (!state.resumo) return;
    const btn = document.getElementById("btnCopiarResumo");
    const ok = () => {
        if (btn) {
            btn.innerHTML = '<i data-lucide="check"></i> Copiado!';
            btn.classList.add("btn-copiar--ok");
            setTimeout(() => {
                btn.innerHTML = '<i data-lucide="copy"></i> Copiar Texto';
                btn.classList.remove("btn-copiar--ok");
                if (typeof lucide !== "undefined") lucide.createIcons();
            }, 2000);
        }
    };
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(state.resumo).then(ok).catch(() => copiarFallback(ok));
    } else {
        copiarFallback(ok);
    }
}

function copiarFallback(cb) {
    const ta = document.createElement("textarea");
    ta.value = state.resumo;
    ta.style.cssText = "position:fixed;opacity:0;top:0;left:0;";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); cb(); }
    catch { mostrarAviso("Não foi possível copiar o texto.", "error"); }
    finally { document.body.removeChild(ta); }
}

// ─── HELPERS PRIVADOS ─────────────────────────────────────────────────────────

function _formatarNome(username) {
    const raw = username.includes("@") ? username.split("@")[0] : username;
    return raw.split(/[._\-]/).map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");
}

function _getIniciais(nome) {
    const partes = nome.trim().split(" ");
    if (partes.length >= 2) return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
    return nome.slice(0, 2).toUpperCase();
}

function _avatarColor(id) {
    const palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#14b8a6"];
    return palette[id % palette.length];
}