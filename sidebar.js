// ════════════════════════════════════════════════════════════
//  SIDEBAR.JS — Opersan  (SVGs inline — zero flash/delay)
// ════════════════════════════════════════════════════════════

const SIDEBAR_ICONS = {
    "file-text":        `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10,9 9,9 8,9"/></svg>`,
    "layout-dashboard": `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
    "library":          `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
    "user-star":        `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
    "log-out":          `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`,
};

function sidebarIcon(name) {
    return SIDEBAR_ICONS[name] || `<svg width="18" height="18"/>`;
}

function renderizarSidebar(userData) {
    const container = document.getElementById("sidebar-container");
    if (!container) return;

    let isAdmin = false;
    if (userData.role?.toLowerCase() === "admin") isAdmin = true;
    if (userData.roles?.some(r => r.name?.toLowerCase() === "admin")) isAdmin = true;

    const adminItem = isAdmin ? `
        <button id="tabAdmin" class="nav-item" onclick="window.location.href='admin.html'">
            ${sidebarIcon("user-star")} Admin
        </button>` : "";

    const userName = userData.username || localStorage.getItem("userName") || "Usuário";
    const userRole = isAdmin ? "Administrador" : (userData.role || localStorage.getItem("userRole") || "Usuário");

    container.innerHTML = `
        <div class="logo">
            <div class="logo-icon">${sidebarIcon("file-text")}</div>
            <h1>Opersan</h1>
        </div>
        <nav class="nav-menu">
            <button id="tabNovaAnalise" class="nav-item active" onclick="trocarAba('nova')">
                ${sidebarIcon("layout-dashboard")} Painel de Análise
            </button>
            <button id="tabHistorico" class="nav-item" onclick="trocarAba('historico')">
                ${sidebarIcon("library")} Biblioteca
            </button>
            ${adminItem}
        </nav>
        <div class="sidebar-footer">
            <div class="user-profile">
                <div class="avatar">${userName.charAt(0).toUpperCase()}</div>
                <div class="user-info">
                    <span class="user-name">${userName}</span>
                    <span class="user-role">${userRole}</span>
                </div>
            </div>
            <button type="button" onclick="fazerLogout()" class="btn-logout">
                ${sidebarIcon("log-out")} Sair
            </button>
        </div>`;
    // Zero lucide.createIcons() — SVGs já prontos
}