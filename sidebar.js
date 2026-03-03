// ════════════════════════════════════════════════════════════
//  SIDEBAR.JS — Opersan (sem DOMContentLoaded próprio)
// ════════════════════════════════════════════════════════════

function renderizarSidebar(userData) {
    const container = document.getElementById('sidebar-container');
    if (!container) return;

    let isAdmin = false;
    if (userData.role?.toLowerCase() === 'admin') isAdmin = true;
    if (userData.roles?.some(r => r.name?.toLowerCase() === 'admin')) isAdmin = true;

    let menuItems = `
        <button id="tabNovaAnalise" class="nav-item active" onclick="trocarAba('nova')">
            <i data-lucide="layout-dashboard"></i> Painel de Análise
        </button>
        <button id="tabHistorico" class="nav-item" onclick="trocarAba('historico')">
            <i data-lucide="library"></i> Biblioteca
        </button>
    `;

    if (isAdmin) {
        menuItems += `
            <button id="tabAdmin" class="nav-item" onclick="window.location.href='admin.html'">
                <i data-lucide="user-star"></i> Admin
            </button>
        `;
    }

    const userName = userData.username || localStorage.getItem('userName') || 'Usuário';
    const userRole = userData.role || localStorage.getItem('userRole') || 'Usuário';

    container.innerHTML = `
        <div class="logo">
            <div class="logo-icon"><i data-lucide="file-text"></i></div>
            <h1>Opersan</h1>
        </div>
        <nav class="nav-menu">
            ${menuItems}
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

    if (typeof lucide !== 'undefined') lucide.createIcons();
}