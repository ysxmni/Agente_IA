const API = "https://agente-ia-62sa.onrender.com";

// Aguarda o DOM carregar
document.addEventListener("DOMContentLoaded", () => {

    lucide.createIcons();

    const form = document.getElementById("loginform");

    if (!form) {
        console.error("Formulário de login não encontrado.");
        return;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const emailInput = document.getElementById("email");
        const senhaInput = document.getElementById("password");
        const btnSubmit = document.querySelector(".btn-submit");

        const email = emailInput.value.trim();
        const senha = senhaInput.value.trim();

        if (!email || !senha) {
            alert("Preencha email e senha.");
            return;
        }

        // Feedback visual no botão
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = "Entrando...";
        }

        // ✅ FastAPI OAuth2 exige FormData com 'username' e 'password'
        const formData = new FormData();
        formData.append("username", email);
        formData.append("password", senha);

        try {
            // ✅ CORRIGIDO: endpoint correto é /token, não /login
            const response = await fetch(`${API}/token`, {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const erro = await response.json().catch(() => ({ detail: "Erro desconhecido" }));
                console.error("Erro no login:", erro);
                alert(erro.detail || "Email ou senha inválidos.");
                return;
            }

            const data = await response.json();
            console.log("✅ Login bem-sucedido:", data);

            if (!data.access_token) {
                alert("Token não recebido do servidor.");
                return;
            }

            // ✅ CORRIGIDO: salva como 'userToken' — chave usada pelo script.js
            localStorage.setItem("userToken", data.access_token);
            localStorage.setItem("userName", data.user?.name || data.user?.username || email);

            console.log("💾 Token salvo como 'userToken':", data.access_token);

            window.location.href = "index.html";

        } catch (error) {
            console.error("❌ Erro ao conectar com servidor:", error);
            alert("Erro ao conectar com o servidor. Verifique se o backend está rodando.");
        } finally {
            // Restaura botão
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = 'Entrar <i data-lucide="arrow-right"></i>';
                lucide.createIcons();
            }
        }
    });

});