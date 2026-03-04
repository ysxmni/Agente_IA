// ════════════════════════════════════════════════════════════
//  LOGIN.JS — Opersan (login fluido com feedback visual)
// ════════════════════════════════════════════════════════════

const API = "https://agente-ia-62sa.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();

    // Se já estiver logado com token válido, redireciona direto
    const tokenSalvo = localStorage.getItem("userToken") || localStorage.getItem("token");
    if (tokenSalvo) {
        _verificarTokenERedirecionarSeValido(tokenSalvo);
    }

    const form = document.getElementById("loginform");
    if (!form) {
        console.error("Formulário de login não encontrado.");
        return;
    }

    // Foco automático no campo de email ao carregar
    const emailInput = document.getElementById("email");
    emailInput?.focus();

    // Enter no campo de email pula para senha
    emailInput?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            document.getElementById("password")?.focus();
        }
    });

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        await _fazerLogin();
    });
});

// ─── VERIFICAÇÃO SILENCIOSA DE TOKEN ─────────────────────────────────────────

async function _verificarTokenERedirecionarSeValido(token) {
    try {
        const res = await fetch(`${API}/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(4000)
        });
        if (res.ok) {
            // Token ainda válido — redireciona sem precisar logar de novo
            window.location.href = "index.html";
        }
    } catch {
        // Token expirado ou servidor offline — deixa na tela de login normalmente
        localStorage.removeItem("userToken");
        localStorage.removeItem("token");
    }
}

// ─── LOGIN PRINCIPAL ──────────────────────────────────────────────────────────

async function _fazerLogin() {
    const emailInput  = document.getElementById("email");
    const senhaInput  = document.getElementById("password");
    const btnSubmit   = document.querySelector(".btn-submit");
    const errorEl     = _getOrCreateErrorEl();

    const email = emailInput?.value.trim();
    const senha = senhaInput?.value.trim();

    // Validação leve no frontend antes de bater no servidor
    if (!email || !senha) {
        _mostrarErro(errorEl, "Preencha e-mail e senha para continuar.");
        if (!email) emailInput?.focus();
        else senhaInput?.focus();
        return;
    }

    // Estado de loading no botão
    _setBtnLoading(btnSubmit, true);
    _limparErro(errorEl);

    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", senha);

    try {
        const response = await fetch(`${API}/token`, {
            method: "POST",
            body: formData,
            signal: AbortSignal.timeout(15000)
        });

        if (!response.ok) {
            const erro = await response.json().catch(() => ({ detail: "Erro desconhecido" }));
            // Animação de shake no card ao errar
            _shakeCard();
            _mostrarErro(errorEl, erro.detail || "E-mail ou senha inválidos.");
            senhaInput.value = "";
            senhaInput?.focus();
            return;
        }

        const data = await response.json();

        if (!data.access_token) {
            _mostrarErro(errorEl, "Erro interno: token não recebido.");
            return;
        }

        // Salva token e dados do usuário
        localStorage.setItem("userToken", data.access_token);
        localStorage.setItem("token",     data.access_token); // compatibilidade
        localStorage.setItem("userName",  data.user?.name || data.user?.username || email);
        localStorage.setItem("userRole",  data.user?.role || "user");
        if (data.user?.id) localStorage.setItem("userId", data.user.id);

        // Feedback de sucesso antes de redirecionar
        _setBtnSuccess(btnSubmit);
        setTimeout(() => {
            window.location.href = "index.html";
        }, 400);

    } catch (error) {
        if (error.name === "TimeoutError") {
            _mostrarErro(errorEl, "Servidor demorou para responder. Tente novamente.");
        } else {
            _mostrarErro(errorEl, "Não foi possível conectar ao servidor.");
        }
        console.error("❌ Erro ao conectar:", error);
    } finally {
        // Só restaura o botão se não houve sucesso
        if (btnSubmit && !btnSubmit.classList.contains("btn-success")) {
            _setBtnLoading(btnSubmit, false);
        }
    }
}

// ─── HELPERS DE UI ────────────────────────────────────────────────────────────

function _setBtnLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.innerHTML = loading
        ? `<span class="btn-spinner"></span> Entrando...`
        : `Entrar <i data-lucide="arrow-right"></i>`;
    if (!loading && typeof lucide !== "undefined") lucide.createIcons();
}

function _setBtnSuccess(btn) {
    if (!btn) return;
    btn.disabled = true;
    btn.classList.add("btn-success");
    btn.innerHTML = `<i data-lucide="check"></i> Acesso liberado!`;
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function _getOrCreateErrorEl() {
    let el = document.getElementById("loginError");
    if (!el) {
        el = document.createElement("div");
        el.id        = "loginError";
        el.className = "login-error hidden";
        const form   = document.getElementById("loginform");
        const btnWrap = form?.querySelector(".btn-submit")?.parentElement || form;
        form?.insertBefore(el, form.querySelector(".btn-submit"));
    }
    return el;
}

function _mostrarErro(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    // Pequena animação de entrada
    el.style.opacity   = "0";
    el.style.transform = "translateY(-4px)";
    requestAnimationFrame(() => {
        el.style.transition = "opacity 0.2s ease, transform 0.2s ease";
        el.style.opacity    = "1";
        el.style.transform  = "translateY(0)";
    });
}

function _limparErro(el) {
    if (!el) return;
    el.textContent = "";
    el.classList.add("hidden");
}

function _shakeCard() {
    const card = document.querySelector(".login-card");
    if (!card) return;
    card.classList.add("shake");
    card.addEventListener("animationend", () => card.classList.remove("shake"), { once: true });
}