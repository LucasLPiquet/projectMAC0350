async function entrar() {
    const dados = {
        nome: document.getElementById('nome').value,
        senha: document.getElementById('senha').value
    };

    const resposta = await fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({nome: dados.nome, senha: dados.senha})
    });

    if (resposta.ok) {
        const resultado = await resposta.json();
        window.location.href = "/profile";
    } else {
        alert("Nome de usuário ou senha incorretos!");
    }
}