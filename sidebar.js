// ════════════════════════════════════════════════════════════
//  SIDEBAR.JS — Opersan
//  Correções:
//  · Recebe isAdmin pré-calculado (sem re-derivar)
//  · username já chega formatado de script.js (usuario.nome)
//  · _criarIcones() via requestAnimationFrame elimina flash
//    de ícones sem SVG no primeiro render
// ════════════════════════════════════════════════════════════

function renderizarSidebar(userData) {
    const container = document.getElementById('sidebar-container');
    if (!container) return;

    // Aceita isAdmin pré-calculado; faz fallback se necessário
    const isAdmin = userData.isAdmin
        ?? (userData.role?.toLowerCase() === 'admin'
            || userData.roles?.some(r => r.name?.toLowerCase() === 'admin')
            || false);

    // username já chega formatado de script.js (usuario.nome)
    const userName = userData.username || 'Usuário';
    const userRole = userData.role     || 'Usuário';

    container.innerHTML = `
        <div class="logo">
            <div class="logo-icon"><i data-lucide="file-text"></i></div>
            <h1>Opersan</h1>
        </div>
        <nav class="nav-menu">
            <button id="tabNovaAnalise" class="nav-item active" onclick="trocarAba('nova')">
                <i data-lucide="layout-dashboard"></i> Painel de Análise
            </button>
            <button id="tabHistorico" class="nav-item" onclick="trocarAba('historico')">
                <i data-lucide="library"></i> Biblioteca
            </button>
            ${isAdmin ? `
            <button id="tabAdmin" class="nav-item" onclick="window.location.href='admin.html'">
                <i data-lucide="user-star"></i> Admin
            </button>` : ''}
        </nav>
        <div class="sidebar-footer">
            <div class="user-profile">
                <div class="avatar">${userName.charAt(0).toUpperCase()}</div>
                <div class="user-info">
                    <span class="user-name">${userName}</span>
                    <span class="user-role">${isAdmin ? 'Administrador' : userRole}</span>
                </div>
            </div>
            <button onclick="fazerLogout()" class="btn-logout">
                <i data-lucide="log-out"></i> Sair
            </button>
        </div>
    `;

    // rAF garante que o browser já inseriu o HTML no layout antes de processar
    // os ícones, eliminando o flash de [data-lucide] sem SVG
    _criarIcones();
}

// ─── helper centralizado ──────────────────────────────────────────────────────
// Definido aqui e também em script.js como fallback.
// Todos os módulos chamam _criarIcones() em vez de lucide.createIcons() direto.
function _criarIcones() {
    if (typeof lucide === 'undefined') return;
    requestAnimationFrame(() => lucide.createIcons());
}