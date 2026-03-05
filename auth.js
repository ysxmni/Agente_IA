// ════════════════════════════════════════════════════════════
//  AUTH.JS — Opersan  (executado antes de script.js)
//  Verifica token e redireciona para login se inválido.
//  Não usa Lucide nem qualquer CDN externo.
// ════════════════════════════════════════════════════════════

(function () {
    // Normaliza chaves: garante que "token" e "userToken" sejam equivalentes
    const t1 = localStorage.getItem("userToken");
    const t2 = localStorage.getItem("token");

    if (!t1 && t2)  localStorage.setItem("userToken", t2);
    if (!t2 && t1)  localStorage.setItem("token", t1);

    const token = localStorage.getItem("userToken") || localStorage.getItem("token");

    // Se não há token algum, vai direto para login sem fazer fetch
    if (!token) {
        window.location.replace("login.html");
        // Interrompe o restante da execução desta página
        throw new Error("AUTH: sem token — redirecionando");
    }

    // Token existe — a validação completa acontece no script.js via /users/me
    // auth.js só garante que existe algo antes de montar o DOM
})();