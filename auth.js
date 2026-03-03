// ════════════════════════════════════════════════════════════
//  AUTH.JS — Opersan (versão limpa)
// ════════════════════════════════════════════════════════════

const API_URL = "https://agente-ia-62sa.onrender.com";

async function verificarAutenticacaoUsuario() {
    const userToken = localStorage.getItem('userToken');
    if (!userToken || userToken === 'null' || userToken === 'undefined') {
        window.location.href = 'login.html';
        return null;
    }
    try {
        const response = await fetch(`${API_URL}/users/me`, {
            headers: { 'Authorization': `Bearer ${userToken}` }
        });
        if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('userToken');
            window.location.href = 'login.html';
            return null;
        }
        if (!response.ok) return null;
        const userData = await response.json();
        if (userData.role)     localStorage.setItem('userRole', userData.role);
        if (userData.username) localStorage.setItem('userName', userData.username);
        return userData;
    } catch (error) {
        console.error('auth.js: Erro de rede:', error.message);
        return null;
    }
}