// ════════════════════════════════════════════════════════════════════════════
//  OPERSAN — dissenso.js  v1.1  (corrigido: acesso ao objeto usuario)
//  Módulo de Dissenso Automático (exclusivo para Suprimentos e Admin)
// ════════════════════════════════════════════════════════════════════════════

// ─── PROMPT ESPECIALIZADO PARA DISSENSO ──────────────────────────────────────
const PROMPT_DISSENSO = `Você é um especialista em análise de dissenso de propostas comerciais para o setor de suprimentos da empresa Opersan.

TAREFA: Com base no contrato/proposta analisado, gere um DISSENSO FORMAL com o fornecedor.

REGRAS:
1. Extraia SOMENTE informações que estejam no contrato. Cite [Cláusula X] ou [Item Y.Z].
2. O dissenso deve ser formal, objetivo e em português.
3. Identifique pontos de divergência, preços acima do mercado, condições desfavoráveis, prazos inadequados.
4. Proponha contrapropostas concretas com valores/percentuais sempre que possível.
5. Use linguagem comercial e negocial.
6. NUNCA invente dados que não estejam no contrato.

ESTRUTURA OBRIGATÓRIA:

DISSENSO COMERCIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DADOS DA PROPOSTA
Fornecedor: [nome conforme contrato]
Objeto: [objeto conforme contrato]
Valor Proposto: [valor conforme contrato, ou "Não consta"]
Data de Referência: [data conforme contrato, ou "Não consta"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PONTOS DE DISSENSO

1. [TÍTULO DO PONTO — ex: VALOR TOTAL DA PROPOSTA]
   Posição do Fornecedor: [o que o contrato diz + cite cláusula]
   Posição da Opersan: [contraproposta objetiva]
   Justificativa: [motivo técnico/comercial]

2. [TÍTULO DO PONTO]
   Posição do Fornecedor: [...]
   Posição da Opersan: [...]
   Justificativa: [...]

[repita para cada ponto identificado, mínimo 3 pontos]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESUMO DAS CONTRAPROPOSTAS

| Item | Proposto pelo Fornecedor | Contraproposta Opersan |
|------|--------------------------|------------------------|
| [item 1] | [valor/condição] | [contraproposta] |
| [item 2] | [valor/condição] | [contraproposta] |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDICIONANTES PARA ACEITE
- [condição 1 para que a Opersan aceite a proposta]
- [condição 2]
- [condição 3]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTRATO ANALISADO:
{texto}`;

// ─── ESTADO DO MÓDULO ─────────────────────────────────────────────────────────

const DissensoState = {
    gerado: false,
    texto: "",
    editando: false,
    textoEditado: "",
};

// ─── HELPERS DE ACESSO AO USUÁRIO ────────────────────────────────────────────
// CORREÇÃO v1.1: script.js usa `const usuario` (escopo de módulo/arquivo).
// Tentamos acessar via window.usuario (se exposto) e, como fallback,
// lemos role/setores do localStorage e dos roles já renderizados no DOM.

function _getUsuario() {
    // Prioridade 1: window.usuario exposto pelo script.js
    if (window.usuario && (window.usuario.token || window.usuario.nome)) {
        return window.usuario;
    }
    // Prioridade 2: monta objeto a partir do localStorage
    const role     = (localStorage.getItem("userRole") || "").toLowerCase();
    const nome     = localStorage.getItem("userName") || "";
    const token    = localStorage.getItem("userToken") || localStorage.getItem("token") || "";
    const isAdmin  = role === "admin";
    return {
        nome,
        role,
        token,
        isAdmin,
        roles:            [],
        setoresPermitidos: [],
    };
}

function _getToken() {
    if (window.usuario && window.usuario.token) return window.usuario.token;
    return localStorage.getItem("userToken") || localStorage.getItem("token") || "";
}

// ─── VERIFICAÇÃO DE ACESSO ────────────────────────────────────────────────────

function _usuarioPodeVerDissenso() {
    const u = _getUsuario();
    if (!u) return false;

    // Admin tem acesso a tudo
    if (u.isAdmin || u.role === "admin") return true;

    // Verifica setoresPermitidos (se disponível via window.usuario)
    const setoresPermitidos = u.setoresPermitidos || [];
    const roles             = u.roles || [];

    const temSuprimentosSetor = setoresPermitidos.some(s =>
        s.includes("suprim") || s.includes("compra") || s.includes("estoque")
    );

    const temSuprimentosRole = roles.some(r =>
        (r.name || "").toLowerCase().includes("suprim") ||
        (r.name || "").toLowerCase().includes("compra")
    );

    // Fallback: verifica o role string diretamente (localStorage)
    const roleStr = (u.role || "").toLowerCase();
    const temSuprimentosRoleStr = roleStr.includes("suprim") || roleStr.includes("compra");

    return temSuprimentosSetor || temSuprimentosRole || temSuprimentosRoleStr;
}

// ─── RENDER DO TOGGLE CHAT/DISSENSO ──────────────────────────────────────────

function renderizarToggleModo() {
    const chatCard = document.querySelector(".chat-card");
    if (!chatCard) return;

    // Remove toggle existente se houver
    const existente = document.getElementById("modoToggleWrap");
    if (existente) existente.remove();

    // Só renderiza para suprimentos e admin
    if (!_usuarioPodeVerDissenso()) return;

    const wrap = document.createElement("div");
    wrap.id = "modoToggleWrap";
    wrap.className = "modo-toggle-wrap";
    wrap.innerHTML = `
        <div class="modo-toggle-inner">
            <button 
                type="button" 
                id="btnModoChat" 
                class="modo-toggle-btn ativo" 
                onclick="alternarModo('chat')"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                Chat
            </button>
            <button 
                type="button" 
                id="btnModoDissenso" 
                class="modo-toggle-btn inativo" 
                onclick="alternarModo('dissenso')"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Dissenso Automático
                <span class="modo-badge-ia">IA</span>
            </button>
        </div>
    `;

    // Insere antes do chat-header
    const chatHeader = chatCard.querySelector(".chat-header");
    if (chatHeader) {
        chatCard.insertBefore(wrap, chatHeader);
    }
}

// ─── ALTERNAR MODO ────────────────────────────────────────────────────────────

let _modoAtual = "chat";

function alternarModo(modo) {
    _modoAtual = modo;

    const btnChat     = document.getElementById("btnModoChat");
    const btnDissenso = document.getElementById("btnModoDissenso");
    const chatHeader  = document.querySelector(".chat-card .chat-header");
    const chatMsgs    = document.getElementById("chatBox");
    const chatInput   = document.querySelector(".chat-card .chat-input-area");
    const dissensoEl  = document.getElementById("dissensoPanel");

    if (modo === "chat") {
        btnChat?.classList.replace("inativo", "ativo");
        btnDissenso?.classList.replace("ativo", "inativo");
        if (chatHeader) chatHeader.style.display = "";
        if (chatMsgs)   chatMsgs.style.display   = "";
        if (chatInput)  chatInput.style.display  = "";
        if (dissensoEl) dissensoEl.style.display = "none";
    } else {
        btnChat?.classList.replace("ativo", "inativo");
        btnDissenso?.classList.replace("inativo", "ativo");
        if (chatHeader) chatHeader.style.display = "none";
        if (chatMsgs)   chatMsgs.style.display   = "none";
        if (chatInput)  chatInput.style.display  = "none";

        // Cria painel de dissenso se não existir
        if (!dissensoEl) {
            criarPainelDissenso();
        } else {
            dissensoEl.style.display = "flex";
            // Reavalia estado toda vez que a aba é aberta
            _atualizarEstadoDissenso();
        }
    }
}

// ─── CRIAR PAINEL DE DISSENSO ─────────────────────────────────────────────────

function criarPainelDissenso() {
    const chatCard = document.querySelector(".chat-card");
    if (!chatCard) return;

    const panel = document.createElement("div");
    panel.id        = "dissensoPanel";
    panel.className = "dissenso-panel";

    panel.innerHTML = `
        <!-- Toolbar -->
        <div class="dissenso-toolbar">
            <div class="dissenso-toolbar-left">
                <span class="dissenso-toolbar-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                    Dissenso Automático
                </span>
            </div>
            <div class="dissenso-toolbar-right" id="dissensoToolbarAcoes" style="display:none">
                <button type="button" class="dissenso-btn dissenso-btn-secondary" id="btnDissensoEditar" onclick="toggleEditarDissenso()">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    Editar
                </button>
                <button type="button" class="dissenso-btn dissenso-btn-secondary" onclick="copiarDissenso()">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    Copiar
                </button>
                <button type="button" class="dissenso-btn dissenso-btn-primary" onclick="imprimirDissenso()">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                    Imprimir
                </button>
                <button type="button" class="dissenso-btn dissenso-btn-danger" onclick="regerarDissenso()" title="Regenerar">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Regenerar
                </button>
            </div>
        </div>

        <!-- Corpo do dissenso -->
        <div class="dissenso-body" id="dissensoBody">
            <!-- Estado inicial: sem contrato -->
            <div class="dissenso-empty-state" id="dissensoEmptyState">
                <div class="dissenso-empty-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                </div>
                <p class="dissenso-empty-title">Nenhum contrato carregado</p>
                <p class="dissenso-empty-desc">Importe uma proposta comercial na aba "Nova Análise" para gerar o dissenso automático.</p>
            </div>
        </div>

        <!-- Footer: botão gerar -->
        <div class="dissenso-footer" id="dissensoFooter" style="display:none">
            <button type="button" class="dissenso-btn-gerar" id="btnGerarDissenso" onclick="gerarDissenso()">
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Gerar Dissenso com IA
            </button>
        </div>
    `;

    chatCard.appendChild(panel);

    // Verifica se tem contrato carregado
    _atualizarEstadoDissenso();
}

// ─── ATUALIZAR ESTADO DO PAINEL ───────────────────────────────────────────────

function _getState() {
    // Prioridade 1: window.state exposto pelo script.js
    if (window.state && window.state.contratoCarregado !== undefined) return window.state;
    // Prioridade 2: variável state no escopo global (mesmo arquivo carregado antes)
    if (typeof state !== "undefined" && state && state.contratoCarregado !== undefined) return state;
    // Prioridade 3: localStorage (sempre disponível)
    try {
        const s = localStorage.getItem("contratoState");
        if (s) return JSON.parse(s);
    } catch (_) {}
    return null;
}

function _atualizarEstadoDissenso() {
    const emptyState   = document.getElementById("dissensoEmptyState");
    const footer       = document.getElementById("dissensoFooter");
    const toolbarAcoes = document.getElementById("dissensoToolbarAcoes");

    const stateObj    = _getState();
    const temContrato = stateObj && stateObj.contratoCarregado && stateObj.resumo;

    if (!temContrato) {
        if (emptyState)   emptyState.style.display   = "flex";
        if (footer)       footer.style.display        = "none";
        if (toolbarAcoes) toolbarAcoes.style.display  = "none";
        return;
    }

    if (emptyState) emptyState.style.display = "none";

    if (DissensoState.gerado) {
        if (footer)       footer.style.display        = "none";
        if (toolbarAcoes) toolbarAcoes.style.display  = "flex";
    } else {
        if (footer)       footer.style.display        = "flex";
        if (toolbarAcoes) toolbarAcoes.style.display  = "none";
    }
}

// ─── GERAR DISSENSO ───────────────────────────────────────────────────────────

async function gerarDissenso() {
    const stateObj = _getState();
    if (!stateObj?.contratoCarregado) {
        alert("Carregue um contrato primeiro.");
        return;
    }

    const btn    = document.getElementById("btnGerarDissenso");
    const body   = document.getElementById("dissensoBody");
    const footer = document.getElementById("dissensoFooter");

    if (btn) {
        btn.disabled   = true;
        btn.innerHTML  = `
            <span class="dissenso-spinner"></span>
            Gerando dissenso...
        `;
    }

    // Exibe loading no corpo
    if (body) {
        body.innerHTML = `
            <div class="dissenso-loading">
                <div class="dissenso-loading-dots">
                    <span></span><span></span><span></span>
                </div>
                <p class="dissenso-loading-text">Analisando proposta e elaborando dissenso...</p>
            </div>
        `;
    }

    try {
        const texto      = stateObj.resumo || "";
        const contratoId = stateObj.idAtivo || localStorage.getItem("idAtivo");
        const token      = _getToken();

        const prompt = PROMPT_DISSENSO.replace("{texto}", texto);

        const API_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
            ? "http://localhost:1500"
            : "https://agente-ia-62sa.onrender.com";

        const f = new FormData();
        f.append("pergunta",    prompt);
        f.append("setor",       "suprimentos");
        f.append("contrato_id", contratoId || "");

        const res = await fetch(`${API_URL}/perguntar`, {
            method:  "POST",
            headers: { Authorization: `Bearer ${token}` },
            body:    f,
            signal:  AbortSignal.timeout(180_000)
        });

        let textoDissenso = "";

        if (res.ok) {
            const data = await res.json();
            textoDissenso = data.resposta || data.texto || "";
        }

        // Fallback: usa o resumo para gerar localmente
        if (!textoDissenso) {
            textoDissenso = _gerarDissensoFallback(texto);
        }

        DissensoState.gerado       = true;
        DissensoState.texto        = textoDissenso;
        DissensoState.textoEditado = textoDissenso;

        _renderizarTextoDissenso(textoDissenso);
        _atualizarEstadoDissenso();

        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Gerar Dissenso com IA
            `;
        }

    } catch (err) {
        console.error("❌ gerarDissenso:", err);
        if (body) {
            body.innerHTML = `
                <div class="dissenso-empty-state">
                    <div class="dissenso-empty-icon" style="color:var(--red)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    </div>
                    <p class="dissenso-empty-title" style="color:var(--red)">Erro ao gerar dissenso</p>
                    <p class="dissenso-empty-desc">${err.message || "Tente novamente."}</p>
                </div>`;
        }
        if (footer) footer.style.display = "flex";
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Tentar Novamente
            `;
        }
    }
}

// ─── FALLBACK LOCAL ───────────────────────────────────────────────────────────

function _gerarDissensoFallback(resumo) {
    return `DISSENSO COMERCIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DADOS DA PROPOSTA
(Extraído do resumo da análise)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PONTOS DE DISSENSO

Com base no conteúdo analisado:

${resumo.substring(0, 1500)}...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Nota: Este dissenso foi gerado a partir do resumo disponível. 
Edite manualmente para adicionar as contrapropostas específicas.`;
}

// ─── RENDERIZAR TEXTO DO DISSENSO ─────────────────────────────────────────────

function _renderizarTextoDissenso(texto, editavel = false) {
    const body = document.getElementById("dissensoBody");
    if (!body) return;

    if (editavel) {
        body.innerHTML = `
            <div class="dissenso-edit-wrap">
                <div class="dissenso-edit-hint">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                    Modo edição ativo — edite o texto abaixo e clique em Salvar
                </div>
                <textarea 
                    id="dissensoTextarea" 
                    class="dissenso-textarea"
                    spellcheck="false"
                >${texto}</textarea>
                <div class="dissenso-edit-actions">
                    <button type="button" class="dissenso-btn dissenso-btn-secondary" onclick="cancelarEdicaoDissenso()">
                        Cancelar
                    </button>
                    <button type="button" class="dissenso-btn dissenso-btn-primary" onclick="salvarEdicaoDissenso()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                        Salvar Alterações
                    </button>
                </div>
            </div>`;
    } else {
        const linhas = texto.split("\n").map(linha => {
            if (linha.startsWith("DISSENSO COMERCIAL")) {
                return `<div class="dissenso-titulo-principal">${linha}</div>`;
            }
            if (linha.startsWith("━")) {
                return `<div class="dissenso-separador"></div>`;
            }
            if (/^[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ\s]{4,}$/.test(linha.trim()) && linha.trim().length > 3 && !linha.includes("|")) {
                return `<div class="dissenso-secao">${linha}</div>`;
            }
            if (linha.includes("|")) {
                return `<div class="dissenso-tabela-linha">${linha}</div>`;
            }
            if (/^\d+\./.test(linha.trim())) {
                return `<div class="dissenso-item-numerado">${linha}</div>`;
            }
            if (linha.includes(":") && !linha.trim().startsWith("-") && linha.trim().length < 120) {
                const idx   = linha.indexOf(":");
                const chave = linha.substring(0, idx);
                const valor = linha.substring(idx + 1);
                if (chave.trim().length < 40) {
                    return `<div class="dissenso-campo"><span class="dissenso-campo-chave">${chave}:</span><span class="dissenso-campo-valor">${valor}</span></div>`;
                }
            }
            if (linha.trim().startsWith("-")) {
                return `<div class="dissenso-bullet">${linha.replace(/^(\s*)-\s*/, "$1• ")}</div>`;
            }
            if (!linha.trim()) {
                return `<div class="dissenso-espaco"></div>`;
            }
            return `<div class="dissenso-linha">${linha}</div>`;
        }).join("");

        body.innerHTML = `<div class="dissenso-conteudo">${linhas}</div>`;
    }
}

// ─── AÇÕES DO DISSENSO ────────────────────────────────────────────────────────

function toggleEditarDissenso() {
    const btn = document.getElementById("btnDissensoEditar");
    if (DissensoState.editando) {
        cancelarEdicaoDissenso();
    } else {
        DissensoState.editando = true;
        _renderizarTextoDissenso(DissensoState.textoEditado, true);
        if (btn) btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Cancelar`;
    }
}

function cancelarEdicaoDissenso() {
    DissensoState.editando = false;
    const btn = document.getElementById("btnDissensoEditar");
    _renderizarTextoDissenso(DissensoState.textoEditado, false);
    if (btn) btn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        Editar`;
}

function salvarEdicaoDissenso() {
    const textarea = document.getElementById("dissensoTextarea");
    if (!textarea) return;
    DissensoState.textoEditado = textarea.value;
    DissensoState.editando     = false;
    const btn = document.getElementById("btnDissensoEditar");
    _renderizarTextoDissenso(DissensoState.textoEditado, false);
    if (btn) btn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        Editar`;
}

function regerarDissenso() {
    DissensoState.gerado       = false;
    DissensoState.texto        = "";
    DissensoState.textoEditado = "";
    DissensoState.editando     = false;

    const body = document.getElementById("dissensoBody");
    if (body) body.innerHTML = "";

    const toolbarAcoes = document.getElementById("dissensoToolbarAcoes");
    if (toolbarAcoes) toolbarAcoes.style.display = "none";

    const footer = document.getElementById("dissensoFooter");
    if (footer) footer.style.display = "flex";

    _atualizarEstadoDissenso();
}

function copiarDissenso() {
    const texto = DissensoState.textoEditado || DissensoState.texto;
    if (!texto) return;

    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(texto).then(() => {
            _flashBotao("copiar", "✓ Copiado!");
        });
    } else {
        const ta = document.createElement("textarea");
        ta.value = texto;
        ta.style.cssText = "position:fixed;opacity:0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        _flashBotao("copiar", "✓ Copiado!");
    }
}

function _flashBotao(tipo, msg) {
    const btns = document.querySelectorAll("#dissensoToolbarAcoes .dissenso-btn");
    btns.forEach(btn => {
        if (btn.textContent.trim().includes("Copiar")) {
            const original = btn.innerHTML;
            btn.innerHTML = msg;
            setTimeout(() => { btn.innerHTML = original; }, 1800);
        }
    });
}

function imprimirDissenso() {
    const texto = DissensoState.textoEditado || DissensoState.texto;
    if (!texto) return;

    const stateObj     = _getState();
    const nomeContrato = stateObj?.nomeContrato || "Proposta";
    const data         = new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });

    // ── Reutiliza o modal de impressão do script.js (printModal + printFrame) ──
    // Cria o modal se ainda não existir (mesma estrutura do abrirModalImpressao do script.js)
    let overlay = document.getElementById("printModal");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id        = "printModal";
        overlay.className = "modal-overlay hidden";

        // SVGs inline para não depender de lucide já inicializado
        const svgPrinter = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>`;
        const svgX       = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;

        overlay.innerHTML = `
            <div class="modal-card large print-modal-card">
                <div class="modal-header">
                    <div class="header-title">
                        ${svgPrinter}
                        <h3>Imprimir Dissenso</h3>
                    </div>
                    <button type="button" onclick="fecharModal('printModal')" class="btn-close">${svgX}</button>
                </div>
                <div class="print-preview-body">
                    <iframe id="printFrame" class="print-frame"></iframe>
                </div>
                <div class="modal-footer">
                    <button type="button" onclick="fecharModal('printModal')" class="btn-modal-footer btn-cancelar">${svgX} Fechar</button>
                    <button type="button" onclick="document.getElementById('printFrame').contentWindow.focus(); document.getElementById('printFrame').contentWindow.print();" class="btn-modal-footer btn-imprimir">${svgPrinter} Confirmar Impressão</button>
                </div>
            </div>`;
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) {
                if (typeof fecharModal === "function") fecharModal("printModal");
                else overlay.classList.add("hidden");
            }
        });
        document.body.appendChild(overlay);
    }

    // Monta o HTML de impressão do dissenso
    const htmlImpressao = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Dissenso — ${nomeContrato}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Georgia', serif;
    color: #1a1a2e;
    font-size: 11pt;
    line-height: 1.75;
    padding: 2.5cm 2.8cm;
    background: #fff;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 3px solid #1a1a2e;
    padding-bottom: 14px;
    margin-bottom: 20px;
  }
  .header-left h1 {
    font-size: 17pt;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.3px;
  }
  .header-left p {
    font-size: 9pt;
    color: #475569;
    margin-top: 3px;
    font-family: Arial, sans-serif;
  }
  .header-right {
    text-align: right;
    font-family: Arial, sans-serif;
    font-size: 8.5pt;
    color: #64748b;
    line-height: 1.6;
  }
  .badge {
    display: inline-block;
    background: #f0fdf4;
    border: 1px solid #86efac;
    color: #166534;
    font-size: 8pt;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: Arial, sans-serif;
    margin-bottom: 8px;
    letter-spacing: 0.04em;
  }
  .content {
    white-space: pre-wrap;
    font-size: 10.5pt;
    word-break: break-word;
  }
  .footer {
    margin-top: 48px;
    border-top: 1px solid #e2e8f0;
    padding-top: 12px;
    font-family: Arial, sans-serif;
    font-size: 8pt;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }
  @media print {
    body { padding: 1.8cm 2cm; }
    .footer { position: fixed; bottom: 1cm; left: 2cm; right: 2cm; }
  }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <div class="badge">⚖ DISSENSO COMERCIAL</div>
      <h1>${nomeContrato}</h1>
      <p>Gerado automaticamente pelo Sistema Opersan — Setor de Suprimentos</p>
    </div>
    <div class="header-right">
      <strong>Data:</strong> ${data}<br>
      <strong>Sistema:</strong> Opersan v4.9<br>
      <strong>Setor:</strong> Suprimentos
    </div>
  </div>
  <div class="content">${texto.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
  <div class="footer">
    <span>Opersan — Sistema de Gestão de Contratos</span>
    <span>Documento gerado em ${data}</span>
  </div>
</body>
</html>`;

    // Injeta no iframe e abre o modal
    const frame = document.getElementById("printFrame");
    if (frame) frame.srcdoc = htmlImpressao;

    if (typeof abrirModal === "function") {
        abrirModal("printModal");
    } else {
        overlay.classList.remove("hidden");
    }
}

// ─── EXPORTAR FUNÇÕES GLOBAIS ─────────────────────────────────────────────────

window.renderizarToggleModo     = renderizarToggleModo;
window.alternarModo             = alternarModo;
window.gerarDissenso            = gerarDissenso;
window.toggleEditarDissenso     = toggleEditarDissenso;
window.cancelarEdicaoDissenso   = cancelarEdicaoDissenso;
window.salvarEdicaoDissenso     = salvarEdicaoDissenso;
window.regerarDissenso          = regerarDissenso;
window.copiarDissenso           = copiarDissenso;
window.imprimirDissenso         = imprimirDissenso;
window._usuarioPodeVerDissenso  = _usuarioPodeVerDissenso;
window._atualizarEstadoDissenso = _atualizarEstadoDissenso;
window.DissensoState            = DissensoState;

// ─── AUTO-INIT ROBUSTO ────────────────────────────────────────────────────────
// CORREÇÃO v1.1: não depende mais de window.usuario.token para inicializar.
// Verifica apenas se o chat-card existe e se há um token no localStorage.
// A verificação de permissão (suprimentos/admin) já acontece dentro de
// renderizarToggleModo() → _usuarioPodeVerDissenso().

function _dissensoAutoInit() {
    if (!document.querySelector(".chat-card")) return false;

    // Aguarda token no localStorage (populado pelo script.js após login)
    const token = localStorage.getItem("userToken") || localStorage.getItem("token") || "";
    if (!token) return false;

    if (document.getElementById("modoToggleWrap")) return true; // já existe

    renderizarToggleModo();
    return true;
}

(function _bootDissenso() {
    // Tentativa imediata
    if (_dissensoAutoInit()) return;

    // MutationObserver: monitora o DOM até o chat-card aparecer
    const observer = new MutationObserver(() => {
        if (_dissensoAutoInit()) observer.disconnect();
    });
    observer.observe(document.body || document.documentElement, {
        childList: true, subtree: true
    });

    // Polling de segurança por até 20s
    let n = 0;
    const poll = setInterval(() => {
        n++;
        if (_dissensoAutoInit() || n > 40) {
            clearInterval(poll);
            observer.disconnect();
        }
    }, 500);
})();