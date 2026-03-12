// ════════════════════════════════════════════════════════════════════════════
//  OPERSAN — script.js  v4.5  (setores dinâmicos via API)
//
//  MUDANÇAS v4.5:
//  1. setoresDisponiveis agora é carregado da API (/admin/roles) no boot
//  2. Metadados de ícone/cor/slug gerados automaticamente para qualquer setor
//  3. MAPA_SETORES construído dinamicamente (não mais hardcoded)
//  4. Mantida toda a lógica de polling, keep-alive e permissões v4.4
// ════════════════════════════════════════════════════════════════════════════

const API = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:1500"
    : "https://agente-ia-62sa.onrender.com";

// ── PATCH: adiciona variáveis CSS faltantes ao :root ───────────────────────
(function _patchCSSVars() {
    const s = document.createElement("style");
    s.id = "opersan-css-patch";
    s.textContent = `
        :root {
            --text-secondary:  #94a3b8;
            --text-primary:    #ffffff;
            --blue-dim:        rgba(59,130,246,0.08);
            --accent-blue:     #60a5fa;
            --border-focus:    rgba(59,130,246,0.4);
            --input-bg:        #1a253d;
        }
        .setores-visiveis-wrap {
            display: flex;
            flex-direction: column;
            gap: .35rem;
            padding-top: .5rem;
            border-top: 1px solid rgba(255,255,255,.06);
        }
        .setor-visivel-badge {
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            padding: .22rem .65rem;
            border-radius: 7px;
            font-size: .74rem;
            font-weight: 600;
        }
        .setor-visivel-badge svg { width:13px; height:13px; }
    `;
    document.head.appendChild(s);
})();

// ─── BIBLIOTECA DE ÍCONES SVG INLINE ─────────────────────────────────────────
const IC = {
    scale:          `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/><path d="M7 21h10"/><line x1="12" y1="3" x2="12" y2="21"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>`,
    package:        `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
    "folder-kanban":`<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2z"/><line x1="8" y1="12" x2="8" y2="16"/><line x1="12" y1="10" x2="12" y2="16"/><line x1="16" y1="14" x2="16" y2="16"/></svg>`,
    briefcase:      `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`,
    settings:       `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
    tag:            `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`,
    list:           `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
    eye:            `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    user:           `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
    users:          `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    "alert-triangle":`<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    "alert-circle": `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    info:           `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    "check-circle-2":`<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
    printer:        `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>`,
    x:              `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    copy:           `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
    check:          `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    calendar:       `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
    "trash-2":      `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
    "file-text":    `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
    "refresh-cw":   `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`,
    "log-out":      `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`,
    "book-open":    `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
};

function ic(name) { return IC[name] || IC["tag"]; }

// ════════════════════════════════════════════════════════════════════════════
//  GERAÇÃO DINÂMICA DE METADADOS DE SETORES
//  Converte qualquer nome de setor vindo da API em slug, ícone e cor
// ════════════════════════════════════════════════════════════════════════════

// Paleta de cores para setores dinâmicos (índice circular)
const SETOR_CORES = [
    "#3b82f6", // azul
    "#10b981", // verde
    "#f59e0b", // âmbar
    "#8b5cf6", // roxo
    "#06b6d4", // ciano
    "#ec4899", // rosa
    "#f97316", // laranja
    "#14b8a6", // teal
];

// Mapeamento de palavras-chave → ícone
const SETOR_ICON_KEYWORDS = [
    { palavras: ["jurid", "legal", "lei", "direito", "advog"],     icon: "scale"          },
    { palavras: ["suprim", "compra", "estoque", "logist", "sto"],  icon: "package"        },
    { palavras: ["gestao", "gestão", "contrat", "kanban"],         icon: "folder-kanban"  },
    { palavras: ["financ", "contab", "fiscal"],                    icon: "briefcase"      },
    { palavras: ["ti", "tech", "inform", "sistema", "software"],   icon: "settings"       },
];

/**
 * Normaliza o nome do setor para um slug simples (sem acentos, sem espaços).
 * Ex: "Gestão de Contratos" → "gestaocontratos"
 */
function _slugSetor(nome) {
    return (nome || "")
        .toLowerCase()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")  // remove acentos
        .replace(/\s+/g, "")
        .replace(/[^a-z0-9]/g, "");
}

/**
 * Dado um nome de setor, retorna o ícone mais adequado.
 */
function _iconSetor(nome) {
    const slug = _slugSetor(nome);
    for (const regra of SETOR_ICON_KEYWORDS) {
        if (regra.palavras.some(p => slug.includes(p))) return regra.icon;
    }
    return "tag"; // ícone padrão para setores desconhecidos
}

/**
 * Dado um índice, retorna uma cor da paleta (circular).
 */
function _corSetor(indice) {
    return SETOR_CORES[indice % SETOR_CORES.length];
}

/**
 * Converte um role vindo da API em objeto de setor padronizado.
 * { id: "juridico", nome: "Jurídico", icon: "scale", cor: "#3b82f6" }
 */
function _roleParaSetor(role, indice) {
    return {
        id:   _slugSetor(role.name),
        nome: role.name,
        icon: _iconSetor(role.name),
        cor:  _corSetor(indice),
        // guarda o id numérico da API para referência futura
        apiId: role.id,
    };
}

// ─── ESTADO GLOBAL ───────────────────────────────────────────────────────────

// Inicializado vazio — preenchido pela API no boot
let setoresDisponiveis    = [];

// MAPA_SETORES construído dinamicamente após carregarSetores()
// Formato: { "slug": ["slug"], "nome original": ["slug"] }
let MAPA_SETORES = { "admin": [] };

let setorSelecionado      = null;
let setorChatAtivo        = null;
let setorFiltroAtivo      = "todos";
let todosContratos        = [];
let contratoParaExcluirId = null;
let _enviandoPergunta     = false;

let perspectiva = { analystId: null, escopo: "meus" };
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

    _renderSkeletonSidebar();

    try {
        await autenticarUsuario();
    } catch (err) {
        console.error("❌ Autenticação falhou:", err.message);
        localStorage.removeItem("userToken");
        localStorage.removeItem("token");
        window.location.href = "login.html";
        return;
    }

    // ── NOVO: carrega setores da API antes de tudo ──
    await carregarSetores();

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
});

// ─── SKELETON SIDEBAR ────────────────────────────────────────────────────────

function _renderSkeletonSidebar() {
    const container = document.getElementById('sidebar-container');
    if (!container) return;
    container.innerHTML = `
        <div class="logo">
            <div class="logo-icon">${ic('file-text')}</div>
            <h1>Opersan</h1>
        </div>
        <nav class="nav-menu">
            <div class="skeleton-nav-item"></div>
            <div class="skeleton-nav-item"></div>
        </nav>
        <div class="sidebar-footer">
            <div class="skeleton-user">
                <div class="skeleton-avatar"></div>
                <div class="skeleton-user-info">
                    <div class="skeleton-line w70"></div>
                    <div class="skeleton-line w40"></div>
                </div>
            </div>
        </div>
    `;
}

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

// ════════════════════════════════════════════════════════════════════════════
//  CARREGAMENTO DINÂMICO DE SETORES DA API  ← NOVO em v4.5
// ════════════════════════════════════════════════════════════════════════════

/**
 * Busca /admin/roles, filtra o role "admin" e monta setoresDisponiveis + MAPA_SETORES.
 * Se a API falhar, mantém um fallback com os 3 setores originais para não quebrar.
 */
async function carregarSetores() {
    try {
        const res = await fetch(`${API}/admin/roles`, {
            headers: { Authorization: `Bearer ${usuario.token}` },
            signal: AbortSignal.timeout(10000)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const roles = await res.json();

        // Filtra o role especial "admin" — não é um setor de trabalho
        const setoresAPI = roles.filter(r => r.name.toLowerCase() !== "admin");

        if (!setoresAPI.length) {
            console.warn("⚠️ Nenhum setor retornado pela API — usando fallback.");
            _usarSetoresFallback();
            return;
        }

        // Constrói setoresDisponiveis com metadados gerados automaticamente
        setoresDisponiveis = setoresAPI.map((role, i) => _roleParaSetor(role, i));

        // Constrói MAPA_SETORES para configurarSetores() usar
        MAPA_SETORES = { "admin": setoresDisponiveis.map(s => s.id) };
        setoresDisponiveis.forEach(s => {
            // mapeia pelo slug
            MAPA_SETORES[s.id] = [s.id];
            // mapeia também pelo nome original em lowercase (com e sem acento)
            const nomeLower = s.nome.toLowerCase();
            MAPA_SETORES[nomeLower] = [s.id];
            // mapeia pelo slug sem acento (compatibilidade com roles antigos)
            const nomeSlugNFD = s.nome.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, "");
            if (nomeSlugNFD !== s.id) MAPA_SETORES[nomeSlugNFD] = [s.id];
        });

        console.log(`✅ ${setoresDisponiveis.length} setor(es) carregado(s):`, setoresDisponiveis.map(s => s.nome).join(", "));

    } catch (err) {
        console.warn("⚠️ Erro ao carregar setores da API:", err.message, "— usando fallback.");
        _usarSetoresFallback();
    }
}

/**
 * Fallback com os 3 setores originais caso a API não responda.
 */
function _usarSetoresFallback() {
    setoresDisponiveis = [
        { id: "juridico",        nome: "Jurídico",            icon: "scale",          cor: "#3b82f6", apiId: null },
        { id: "suprimentos",     nome: "Suprimentos",         icon: "package",        cor: "#10b981", apiId: null },
        { id: "gestaocontratos", nome: "Gestão de Contratos", icon: "folder-kanban",  cor: "#f59e0b", apiId: null },
    ];
    MAPA_SETORES = {
        "admin":               ["juridico", "suprimentos", "gestaocontratos"],
        "jurídico":            ["juridico"],
        "juridico":            ["juridico"],
        "suprimentos":         ["suprimentos"],
        "gestão de contratos": ["gestaocontratos"],
        "gestaocontratos":     ["gestaocontratos"],
    };
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
        // Admin vê todos os setores que existem
        setoresVisiveis = setoresDisponiveis.map(s => s.id);
        return;
    }

    try {
        const res = await fetch(`${API}/my/visibility`, {
            headers: { Authorization: `Bearer ${usuario.token}` }
        });
        if (res.ok) {
            const data       = await res.json();
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

function configurarSetores() {
    if (usuario.isAdmin) {
        // Admin tem acesso a todos os setores carregados
        usuario.setoresPermitidos = setoresDisponiveis.map(s => s.id);
    } else {
        // Constrói a lista de setores do usuário a partir de seus roles
        let p = [];

        // Tenta pelo role principal (string exata e slug)
        const rolePrincipal = usuario.role.toLowerCase();
        if (MAPA_SETORES[rolePrincipal]) {
            p = [...MAPA_SETORES[rolePrincipal]];
        }
        // Tenta também pelo slug do rolePrincipal (ex: "t.i." → "ti")
        if (!p.length) {
            const slugPrincipal = _slugSetor(usuario.role);
            if (MAPA_SETORES[slugPrincipal]) {
                p = [...MAPA_SETORES[slugPrincipal]];
            }
            // Ou diretamente como setor (ex: role "T.I." → setor.id "ti")
            if (!p.length) {
                const setorDireto = setoresDisponiveis.find(s => s.id === slugPrincipal);
                if (setorDireto) p.push(setorDireto.id);
            }
        }

        // Complementa com todos os roles do usuário
        usuario.roles.forEach(r => {
            const slugs = MAPA_SETORES[r.name.toLowerCase()] ||
                          MAPA_SETORES[_slugSetor(r.name)] ||
                          [];
            slugs.forEach(x => { if (!p.includes(x)) p.push(x); });
        });

        // Garante que slugs de roles que batem diretamente com um setor funcionem
        usuario.roles.forEach(r => {
            if (r.name.toLowerCase() === "admin") return;
            const slugRole = _slugSetor(r.name);
            const setorDireto = setoresDisponiveis.find(s => s.id === slugRole);
            if (setorDireto && !p.includes(setorDireto.id)) {
                p.push(setorDireto.id);
            }
        });

        usuario.setoresPermitidos = p.length ? p : (setoresDisponiveis[0] ? [setoresDisponiveis[0].id] : []);
    }

    setorSelecionado = setorChatAtivo = usuario.setoresPermitidos[0] || null;
}

function renderizarSetoresChat() {
    const container = document.getElementById("chatSetorButtons");
    if (!container) return;
    const setores = setoresDisponiveis.filter(s => usuario.setoresPermitidos.includes(s.id));
    if (!setores.length) { container.innerHTML = ""; return; }

    if (setores.length === 1) {
        setorChatAtivo = setores[0].id;
        container.innerHTML = `<div class="chat-setor-badge-unico">${ic(setores[0].icon)} ${setores[0].nome}</div>`;
        return;
    }

    container.innerHTML = setores.map(s =>
        `<button type="button" class="chat-setor-btn ${s.id === setorChatAtivo ? "ativo" : "inativo"}"
            data-setor="${s.id}" onclick="selecionarSetorChat('${s.id}')">
            ${ic(s.icon)} ${s.nome}
        </button>`
    ).join("");
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
            onclick="aplicarFiltroSetor('todos')">${ic('list')} Todos</button>`;
    }
    html += setores.map(s =>
        `<button type="button" class="filter-btn ${setorFiltroAtivo === s.id ? "ativo" : "inativo"}"
            data-setor="${s.id}" onclick="aplicarFiltroSetor('${s.id}')">
            ${ic(s.icon)} ${s.nome}
        </button>`
    ).join("");
    container.innerHTML = html;
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
    if (btn && input) btn.disabled = !input.value.trim() || _enviandoPergunta;
}

function configurarEventos() {
    const inputPergunta = document.getElementById("perguntaUser");
    const btnEnviar     = document.getElementById("btnEnviar");

    btnEnviar?.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        if (!_enviandoPergunta && inputPergunta?.value.trim()) enviarPergunta();
    });

    inputPergunta?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault(); e.stopPropagation();
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
            ["deleteModal","novaAnaliseModal","resumoModal","logoutModal","printModal","avisoModal"].forEach(fecharModal);
        }
    });
}

// ════════════════════════════════════════════════════════════════════════════
// UPLOAD COM POLLING — mantido de v4.4
// ════════════════════════════════════════════════════════════════════════════

const ETAPAS_UPLOAD = [
    { texto: "📄 Lendo o PDF...",              duracao: 800  },
    { texto: "🔍 Extraindo texto...",           duracao: 1200 },
    { texto: "🤖 IA analisando o contrato...", duracao: null },
    { texto: "💾 Salvando análise...",          duracao: 600  },
];

const UPLOAD_TIMEOUT_MS        = 90_000;
const POLLING_INTERVALO        = 6_000;
const POLLING_MAX              = 150;
const POLLING_TIMEOUT_POR_TENT = 30_000;
const MAX_RETRY_404            = 3;
const ESPERA_COLD_START_MS     = 45_000;
const PING_INTERVALO_MS        = 55_000;
let   _pingTimer               = null;
let   _pollingInicioMs         = 0;

function _iniciarPing() {
    _pararPing();
    _pingTimer = setInterval(async () => {
        try {
            await fetch(`${API}/ping`, {
                headers: { Authorization: `Bearer ${usuario.token}` },
                signal:  AbortSignal.timeout(10_000)
            });
        } catch (e) {
            console.warn("⚠️ Ping falhou:", e.message);
        }
    }, PING_INTERVALO_MS);
}

function _pararPing() {
    if (_pingTimer !== null) { clearInterval(_pingTimer); _pingTimer = null; }
}

async function enviarContrato() {
    const input   = document.getElementById("inputArquivo");
    const arquivo = input?.files?.[0];
    if (!arquivo) return;

    const setorParaEnvio = setorSelecionado || usuario.setoresPermitidos?.[0] || setoresDisponiveis[0]?.id || "juridico";
    const setorInfo      = setoresDisponiveis.find(s => s.id === setorParaEnvio);
    const nomeSetor      = setorInfo?.nome || setorParaEnvio;

    _iniciarProgresso();
    await _avancarEtapa(0);
    await _avancarEtapa(1);
    _avancarEtapaSemEspera(2);

    const fd = new FormData();
    fd.append("file",  arquivo);
    fd.append("setor", setorParaEnvio);

    try {
        const resUpload = await fetch(`${API}/upload`, {
            method:  "POST",
            headers: { Authorization: `Bearer ${usuario.token}` },
            body:    fd,
            signal:  AbortSignal.timeout(UPLOAD_TIMEOUT_MS)
        });

        if (!resUpload.ok) {
            let detalhe = `Erro ${resUpload.status}`;
            try { const e = await resUpload.json(); detalhe = e.detail || detalhe; } catch (_) {}
            throw new Error(detalhe);
        }

        const jobData = await resUpload.json();
        const jobId   = jobData.job_id;
        if (!jobId) throw new Error("Servidor não retornou job_id. Tente novamente.");

        _iniciarPing();
        _pollingInicioMs = Date.now();
        const data = await _aguardarJob(jobId);

        await _avancarEtapa(3);
        _finalizarProgresso("✅ ANÁLISE CONCLUÍDA!");

        state.contratoCarregado = true;
        state.resumo            = data.resumo;
        state.nomeContrato      = data.nome || arquivo.name;
        state.idAtivo           = data.id;
        state.mensagens         = [];
        localStorage.setItem("idAtivo", data.id);
        salvarEstado();

        renderResumo(data.resumo);

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
        _pararPing();
        let msg;
        if (err.name === "TimeoutError" || err.message?.includes("timeout")) {
            msg = "O servidor demorou para responder. Aguarde 30 segundos e tente novamente.";
        } else if (err.message?.includes("Failed to fetch") || err.message?.includes("NetworkError")) {
            msg = "Erro de conexão com o servidor. Verifique sua internet e tente novamente.";
        } else {
            msg = `Erro no processamento: ${err.message}`;
        }
        _finalizarProgresso(`❌ ${msg}`, "error");
        mostrarAviso(msg, "error");
    }
}

async function _aguardarJob(jobId) {
    const TEMPO_TOTAL_ESPERADO_MS = 600_000;
    let contador404 = 0;

    for (let tentativa = 0; tentativa < POLLING_MAX; tentativa++) {
        await new Promise(r => setTimeout(r, POLLING_INTERVALO));

        const decorrido_ms  = Date.now() - _pollingInicioMs;
        const decorrido_min = Math.floor(decorrido_ms / 60_000);
        const decorrido_seg = Math.floor((decorrido_ms % 60_000) / 1000);
        const tempoStr      = decorrido_min > 0 ? `${decorrido_min} min ${decorrido_seg}s` : `${decorrido_seg}s`;

        let etapaStr;
        if (decorrido_ms < 5_000)       etapaStr = "📄 Extraindo texto do PDF...";
        else if (decorrido_ms < 15_000) etapaStr = "🔍 Preparando análise...";
        else if (contador404 > 0)       etapaStr = `🔄 Reconectando ao servidor... (tentativa ${contador404}/${MAX_RETRY_404})`;
        else                            etapaStr = `🤖 IA analisando o contrato${".".repeat((tentativa % 3) + 1)}`;

        const textoEl = document.querySelector(".progress-texto");
        if (textoEl) textoEl.textContent = `${etapaStr} (${tempoStr})`;

        const pct   = Math.min(20 + Math.floor((decorrido_ms / TEMPO_TOTAL_ESPERADO_MS) * 72), 92);
        const barra = document.getElementById("progressBarFill");
        if (barra) barra.style.width = pct + "%";

        let erroFatal = null;

        try {
            const res = await fetch(`${API}/job/${jobId}`, {
                headers: { Authorization: `Bearer ${usuario.token}` },
                signal:  AbortSignal.timeout(POLLING_TIMEOUT_POR_TENT)
            });

            if (res.status === 404) {
                contador404++;
                if (contador404 >= MAX_RETRY_404) {
                    erroFatal = new Error("O servidor reiniciou durante a análise. Aguarde 30s e envie novamente.");
                } else {
                    const textoEl2 = document.querySelector(".progress-texto");
                    if (textoEl2) textoEl2.textContent = `🔄 Servidor reiniciando, aguardando ${ESPERA_COLD_START_MS / 1000}s... (tentativa ${contador404}/${MAX_RETRY_404})`;
                    await new Promise(r => setTimeout(r, ESPERA_COLD_START_MS));
                }
            } else if (!res.ok) {
                contador404 = 0;
            } else {
                contador404 = 0;
                const job = await res.json();
                if (job.status === "done")  { _pararPing(); return job.result; }
                if (job.status === "error") { erroFatal = new Error(job.error || "Erro interno durante a análise."); }
            }
        } catch (err) {
            contador404 = 0;
            console.warn(`⚠️ Polling tentativa ${tentativa + 1}: ${err.message}`);
        }

        if (erroFatal !== null) { _pararPing(); throw erroFatal; }
    }

    _pararPing();
    throw new Error(`Tempo esgotado após ${Math.floor((POLLING_MAX * POLLING_INTERVALO) / 60_000)} minutos. Tente novamente.`);
}

let _etapaAtual = 0;

function _iniciarProgresso() {
    _etapaAtual = 0;
    const statusEl = document.getElementById("status");
    if (!statusEl) return;
    statusEl.className = "status-badge processing";
    statusEl.classList.remove("hidden");
    statusEl.innerHTML = `
        <div class="progress-wrap">
            <span class="progress-texto">⏳ Iniciando...</span>
            <div class="progress-bar-track">
                <div class="progress-bar-fill" id="progressBarFill" style="width:5%"></div>
            </div>
        </div>`;
}

function _avancarEtapa(indice) {
    return new Promise(resolve => {
        const etapa   = ETAPAS_UPLOAD[indice];
        const pct     = Math.round(((indice + 1) / ETAPAS_UPLOAD.length) * 18);
        const textoEl = document.querySelector(".progress-texto");
        const barraEl = document.getElementById("progressBarFill");
        if (textoEl) textoEl.textContent = etapa.texto;
        if (barraEl) barraEl.style.width = pct + "%";
        setTimeout(resolve, etapa.duracao || 0);
    });
}

function _avancarEtapaSemEspera(indice) {
    const etapa   = ETAPAS_UPLOAD[indice];
    const textoEl = document.querySelector(".progress-texto");
    const barraEl = document.getElementById("progressBarFill");
    if (textoEl) textoEl.textContent = etapa.texto;
    if (barraEl) barraEl.style.width = "20%";
}

function _finalizarProgresso(mensagem, tipo = "success") {
    const statusEl = document.getElementById("status");
    if (!statusEl) return;
    const barraEl = document.getElementById("progressBarFill");
    if (barraEl) barraEl.style.width = "100%";
    setTimeout(() => {
        statusEl.className   = `status-badge ${tipo}`;
        statusEl.textContent = mensagem;
    }, 400);
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
    loading.innerHTML = '<div class="message-content typing-indicator"><span></span><span></span><span></span></div>';
    chatBox?.appendChild(loading);
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

    const fd = new FormData();
    fd.append("pergunta",    pergunta);
    fd.append("setor",       setorChatAtivo || setoresDisponiveis[0]?.id || "juridico");
    fd.append("contrato_id", contratoId);

    try {
        const res = await fetch(`${API}/perguntar`, {
            method:  "POST",
            headers: { Authorization: `Bearer ${usuario.token}` },
            body:    fd,
            signal:  AbortSignal.timeout(360_000)
        });

        document.getElementById("chatLoading")?.remove();

        if (!res.ok) {
            let detalhe = `Erro ${res.status}`;
            try { const e = await res.json(); detalhe = e.detail || detalhe; } catch (_) {}
            throw new Error(detalhe);
        }

        const data = await res.json();
        adicionarMensagem("ai", data.resposta || "Sem resposta.");

    } catch (err) {
        document.getElementById("chatLoading")?.remove();
        if (err.name === "TimeoutError") {
            adicionarMensagem("ai", "⏱️ A IA demorou muito. Tente novamente com uma pergunta mais específica.");
        } else if (err.message?.includes("Failed to fetch")) {
            adicionarMensagem("ai", "❌ Erro de conexão. Verifique sua internet e tente novamente.");
        } else {
            adicionarMensagem("ai", `❌ Erro: ${err.message}`);
        }
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
    msg.style.opacity   = "0";
    msg.style.transform = "translateY(6px)";
    chat.appendChild(msg);
    requestAnimationFrame(() => {
        msg.style.transition = "opacity 0.2s ease, transform 0.2s ease";
        msg.style.opacity    = "1";
        msg.style.transform  = "translateY(0)";
    });
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
    _renderSkeletonBiblioteca(lista);
    renderizarSeletorPerspectiva();
    renderizarFiltroSetores();
    await _buscarEExibirContratos();
}

function _renderSkeletonBiblioteca(container) {
    const skeletons = Array.from({ length: 6 }, () => `
        <div class="skeleton-card">
            <div class="skeleton-card-header"><div class="skeleton-line w80"></div></div>
            <div class="skeleton-card-body">
                <div class="skeleton-badge"></div>
                <div class="skeleton-line w40" style="margin-top:.5rem"></div>
                <div class="skeleton-line w90" style="margin-top:.75rem"></div>
                <div class="skeleton-line w70"></div>
                <div class="skeleton-line w80"></div>
                <div class="skeleton-actions"></div>
            </div>
        </div>`).join("");
    container.innerHTML = `<div class="history-grid skeleton-grid">${skeletons}</div>`;
}

async function _buscarEExibirContratos() {
    const lista = document.getElementById("listaContratos");
    if (!lista) return;

    const params = new URLSearchParams();
    if (perspectiva.analystId !== null) {
        params.append("analyst_id", perspectiva.analystId);
    } else {
        if (perspectiva.escopo === "meus") params.append("analyst_id", usuario.id);
    }
    if (setorFiltroAtivo !== "todos") params.append("sector_id", setorFiltroAtivo);

    try {
        const res = await fetch(`${API}/contratos/listar?${params.toString()}`, {
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

    const temColegas    = usuariosVisiveis.length > 0;
    const temSetores    = setoresVisiveis.length > 0;
    const euSelecionado = perspectiva.analystId === null;

    if (!temColegas && !temSetores && !usuario.isAdmin) { container.innerHTML = ""; return; }

    let indicadorHtml = "";
    if (!euSelecionado) {
        const analista = usuariosVisiveis.find(u => u.id === perspectiva.analystId);
        if (analista) {
            indicadorHtml = `
            <div class="perspectiva-info-row">
                <span class="perspectiva-info-text">
                    ${ic('eye')} Visualizando análises de <strong>${analista.nome}</strong>
                </span>
                <button class="btn-voltar-minhas" onclick="voltarMinhasPerspectiva()">← Voltar às minhas</button>
            </div>`;
        }
    }

    let escopoHtml = "";
    if (usuario.isAdmin && perspectiva.analystId === null) {
        escopoHtml = `
        <div class="perspectiva-escopo">
            <span class="perspectiva-escopo-label">Escopo:</span>
            <button class="escopo-btn ${perspectiva.escopo === "meus" ? "ativo" : ""}" onclick="definirEscopo('meus')">
                ${ic('user')} Meus contratos
            </button>
            <button class="escopo-btn ${perspectiva.escopo === "todos" ? "ativo" : ""}" onclick="definirEscopo('todos')">
                ${ic('users')} Todos do setor
            </button>
        </div>`;
    }

    let setoresBadgesHtml = "";
    if (temSetores && !usuario.isAdmin) {
        const setoresInfo = setoresVisiveis.map(slug => {
            const s = setoresDisponiveis.find(x => x.id === slug);
            return s ? `<span class="setor-visivel-badge" style="color:${s.cor};background:${s.cor}15;border:1px solid ${s.cor}30">
                ${ic(s.icon)} ${s.nome}
            </span>` : "";
        }).filter(Boolean).join("");
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
            <span class="perspectiva-label">${ic('eye')} Perspectiva</span>
            <div class="perspectiva-selector">
                <button class="perspectiva-btn meu ${euSelecionado ? "ativo" : ""}" onclick="selecionarPerspectiva(null)">
                    <span class="pav-avatar" style="background:#3b82f620;color:#3b82f6">${usuario.nome.charAt(0).toUpperCase()}</span>
                    Meus contratos
                </button>
                ${usuariosVisiveis.map(u => `
                <button class="perspectiva-btn outro ${perspectiva.analystId === u.id ? "ativo" : ""}" onclick="selecionarPerspectiva(${u.id})">
                    <span class="pav-avatar" style="background:${u.cor}20;color:${u.cor}">${(u.iniciais || u.nome.charAt(0)).toUpperCase()}</span>
                    ${u.nome}
                </button>`).join("")}
            </div>` : ""}
            ${setoresBadgesHtml}
            ${escopoHtml}
            ${indicadorHtml}
        </div>`;
}

async function selecionarPerspectiva(analystId) {
    perspectiva.analystId = analystId;
    perspectiva.escopo = "meus";
    renderizarSeletorPerspectiva();
    const lista = document.getElementById("listaContratos");
    if (lista) _renderSkeletonBiblioteca(lista);
    await _buscarEExibirContratos();
}

async function definirEscopo(escopo) {
    if (!usuario.isAdmin) return;
    perspectiva.escopo = escopo;
    renderizarSeletorPerspectiva();
    const lista = document.getElementById("listaContratos");
    if (lista) _renderSkeletonBiblioteca(lista);
    await _buscarEExibirContratos();
}

async function voltarMinhasPerspectiva() {
    perspectiva.analystId = null;
    perspectiva.escopo    = "meus";
    renderizarSeletorPerspectiva();
    const lista = document.getElementById("listaContratos");
    if (lista) _renderSkeletonBiblioteca(lista);
    await _buscarEExibirContratos();
}

// ─── RENDERIZAR CONTRATOS ─────────────────────────────────────────────────────

/**
 * Tenta encontrar um setor em setoresDisponiveis pelo slug do contrato.
 * Aceita tanto match exato quanto match parcial (para slugs antigos/novos).
 */
function _encontrarSetorContrato(setorSlug) {
    if (!setorSlug) return setoresDisponiveis[0] || null;
    const slug = _slugSetor(setorSlug);
    // 1. match exato por id
    let s = setoresDisponiveis.find(x => x.id === slug);
    if (s) return s;
    // 2. match por nome normalizado
    s = setoresDisponiveis.find(x => _slugSetor(x.nome) === slug);
    if (s) return s;
    // 3. match parcial (para slugs antigos como "gestaocontratos" vs "gestao")
    s = setoresDisponiveis.find(x => slug.includes(x.id) || x.id.includes(slug));
    return s || null;
}

function renderizarContratos(lista) {
    const el = document.getElementById("listaContratos");
    if (!el) return;

    let filtrados = lista.filter(c => {
        const setorContrato = _slugSetor(c.setor || "");
        const setorObj = _encontrarSetorContrato(setorContrato);
        const setorId  = setorObj?.id || setorContrato;

        if (setorFiltroAtivo === "todos") {
            return usuario.setoresPermitidos.includes(setorId) ||
                   usuario.isAdmin ||
                   setoresDisponiveis.some(s => s.id === setorId);
        }
        return setorId === setorFiltroAtivo;
    });

    if (!filtrados.length) {
        const msg = perspectiva.analystId !== null
            ? "Este usuário não possui contratos neste setor."
            : "Nenhum contrato encontrado.";
        el.innerHTML = `<p class='preview-empty'>${msg}</p>`;
        atualizarContadorResultados(0, lista.length);
        return;
    }

    el.innerHTML = "";
    filtrados.forEach((c, i) => {
        const setorObj = _encontrarSetorContrato(c.setor);
        const badge = setorObj
            ? `<span class="setor-badge-card" style="background:${setorObj.cor}18;border-color:${setorObj.cor}40;color:${setorObj.cor}">${ic(setorObj.icon)}${setorObj.nome}</span>`
            : "";

        const mostrarAnalista = c.show_analyst && c.analista && c.analista.id;
        const analistaBadge   = mostrarAnalista
            ? `<span class="analista-badge">${ic('user')}${c.analista.nome}</span>`
            : "";

        const card = document.createElement("div");
        card.className       = "history-card";
        card.style.opacity   = "0";
        card.style.transform = "translateY(10px)";
        card.innerHTML = `
            <div class="card-header"><h3>${c.nome}</h3></div>
            <div class="card-body">
                <div class="setor-badge-wrap">${badge}</div>
                <div class="date-tag">
                    <span class="date-tag-left">${ic('calendar')}${new Date(c.data).toLocaleDateString("pt-BR")}</span>
                    ${analistaBadge}
                </div>
                <p class="preview-text">${c.preview || ""}</p>
                <div class="card-actions">
                    <button type="button" onclick="abrirDoHistorico(${c.id})" class="btn-open">Abrir Análise</button>
                    ${c.is_mine || usuario.isAdmin
                        ? `<button type="button" onclick="solicitarExclusao(${c.id})" class="btn-delete-icon">${ic('trash-2')}</button>`
                        : ""}
                </div>
            </div>`;
        el.appendChild(card);

        setTimeout(() => {
            card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
            card.style.opacity    = "1";
            card.style.transform  = "translateY(0)";
        }, i * 50);
    });

    atualizarContadorResultados(filtrados.length, lista.length);
}

function filtrarContratos() {
    const input = document.getElementById("searchInput");
    const clear = document.getElementById("clearSearch");
    const termo = input?.value.toLowerCase().trim() || "";
    if (clear) clear.classList.toggle("hidden", !termo);

    let filtrados = todosContratos.filter(c => {
        const setorContrato = _slugSetor(c.setor || "");
        const setorObj      = _encontrarSetorContrato(setorContrato);
        const setorId       = setorObj?.id || setorContrato;

        if (setorFiltroAtivo === "todos") {
            return usuario.setoresPermitidos.includes(setorId) || usuario.isAdmin;
        }
        return setorId === setorFiltroAtivo;
    });

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

// ─── MODAL DE AVISO ──────────────────────────────────────────────────────────

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
                <p id="avisoTexto"></p>
                <div class="modal-actions">
                    <button type="button" onclick="fecharModal('avisoModal')" class="btn-primary">OK</button>
                </div>
            </div>`;
        overlay.addEventListener("click", (e) => { if (e.target === overlay) fecharModal("avisoModal"); });
        document.body.appendChild(overlay);
    }

    const icones  = { info: "info", warning: "alert-triangle", error: "alert-circle", success: "check-circle-2" };
    const classes = { info: "info", warning: "warning", error: "warning", success: "info" };
    const titulos = { info: "Atenção", warning: "Atenção", error: "Ocorreu um erro", success: "Concluído" };

    document.getElementById("avisoIcon").className = `modal-icon ${classes[tipo] || "info"}`;
    document.getElementById("avisoIcon").innerHTML  = ic(icones[tipo] || "info");
    document.getElementById("avisoTitulo").textContent = titulos[tipo] || "Aviso";
    document.getElementById("avisoTexto").textContent  = mensagem;

    abrirModal("avisoModal");
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
}

function abrirModalResumo() {
    if (!state.resumo) {
        mostrarAviso("Nenhum documento carregado. Importe um contrato para ver a análise.", "warning");
        return;
    }
    const textoFull = document.getElementById("textoFull");
    if (textoFull) textoFull.innerHTML = state.resumo.replace(/\n/g, "<br>");
    const footer = document.querySelector("#resumoModal .modal-footer");
    if (footer) {
        footer.innerHTML = `
            <button type="button" onclick="fecharModal('resumoModal')" class="btn-modal-footer btn-cancelar">${ic('x')} Fechar</button>
            <button type="button" onclick="abrirModalImpressao()" class="btn-modal-footer btn-imprimir">${ic('printer')} Imprimir</button>
            <button type="button" id="btnCopiarResumo" onclick="copiarResumo()" class="btn-modal-footer btn-copiar">${ic('copy')} Copiar Texto</button>`;
    }
    abrirModal("resumoModal");
}

// ─── IMPRESSÃO ────────────────────────────────────────────────────────────────

function abrirModalImpressao() {
    fecharModal("resumoModal");
    let overlay = document.getElementById("printModal");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id        = "printModal";
        overlay.className = "modal-overlay hidden";
        overlay.innerHTML = `
            <div class="modal-card large print-modal-card">
                <div class="modal-header">
                    <div class="header-title">
                        ${ic('printer')}
                        <h3>Imprimir Análise</h3>
                    </div>
                    <button type="button" onclick="fecharModalImpressao()" class="btn-close">${ic('x')}</button>
                </div>
                <div class="print-preview-body">
                    <iframe id="printFrame" class="print-frame"></iframe>
                </div>
                <div class="modal-footer">
                    <button type="button" onclick="fecharModalImpressao()" class="btn-modal-footer btn-cancelar">${ic('x')} Fechar</button>
                    <button type="button" onclick="executarImpressao()" class="btn-modal-footer btn-imprimir">${ic('printer')} Confirmar Impressão</button>
                </div>
            </div>`;
        overlay.addEventListener("click", (e) => { if (e.target === overlay) fecharModalImpressao(); });
        document.body.appendChild(overlay);
    }

    document.getElementById("printFrame").srcdoc = _gerarHtmlImpressao();
    abrirModal("printModal");
}

function fecharModalImpressao() { fecharModal("printModal"); abrirModal("resumoModal"); }

function executarImpressao() {
    const frame = document.getElementById("printFrame");
    if (frame?.contentWindow) { frame.contentWindow.focus(); frame.contentWindow.print(); }
}

function _gerarHtmlImpressao() {
    return `<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Análise — ${state.nomeContrato}</title>
<style>
    * { margin:0;padding:0;box-sizing:border-box; }
    body { font-family:'Georgia',serif;color:#1a1a1a;font-size:11pt;line-height:1.7;padding:2cm;background:#fff; }
    h1 { font-size:18pt;color:#1e40af;border-bottom:3px solid #3b82f6;padding-bottom:10px;margin-bottom:8px; }
    .meta { color:#64748b;font-size:9.5pt;margin-bottom:24px;font-family:Arial,sans-serif; }
    hr { border:none;border-top:1px solid #e2e8f0;margin:20px 0; }
    .content { white-space:pre-wrap;text-align:justify;font-size:10.5pt; }
    .footer { margin-top:40px;font-size:8.5pt;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:10px;font-family:Arial,sans-serif;text-align:center; }
    @media print { body { padding:1.5cm; } }
</style></head><body>
    <h1>Análise Completa do Contrato</h1>
    <div class="meta">${state.nomeContrato} — ${new Date().toLocaleDateString("pt-BR",{day:"2-digit",month:"long",year:"numeric"})}</div>
    <hr>
    <div class="content">${state.resumo}</div>
    <div class="footer">Gerado pelo Sistema Opersan</div>
</body></html>`;
}

// ─── CÓPIA ────────────────────────────────────────────────────────────────────

function copiarResumo() {
    if (!state.resumo) return;
    const btn = document.getElementById("btnCopiarResumo");
    const ok = () => {
        if (btn) {
            btn.innerHTML = `${ic('check')} Copiado!`;
            btn.classList.add("btn-copiar--ok");
            setTimeout(() => {
                btn.innerHTML = `${ic('copy')} Copiar Texto`;
                btn.classList.remove("btn-copiar--ok");
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
    if (partes.length >= 2) return (partes[0][0] + partes[partes.length-1][0]).toUpperCase();
    return nome.slice(0, 2).toUpperCase();
}

function _avatarColor(id) {
    const palette = ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#14b8a6"];
    return palette[id % palette.length];
}