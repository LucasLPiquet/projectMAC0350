from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi import Depends, HTTPException, status, Cookie, Response
from typing import Annotated
from typing import List, Optional
from sqlmodel import Session, select, SQLModel, create_engine
from models import Usuario, Conquista, UsuarioConquista, Amizade

arquivo_sqlite = "data.db"
url_sqlite = f"sqlite:///{arquivo_sqlite}"

engine = create_engine(url_sqlite)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def criar_conquistas():
    conquistas = [
        Conquista(nome="Primeiro login", descricao="Fez login pela primeira vez"),
        Conquista(nome="Primeiro amigo", descricao="Adicionou um amigo"),
        Conquista(nome="Vereador", descricao="Conseguiu 20 amigos"),
        Conquista(nome="Preguiçoso", descricao="Conseguiu 100 pontos"),
        Conquista(nome="Dedicado", descricao="Conseguiu 500 pontos"),
        Conquista(nome="Disciplinado", descricao="Conseguiu 1000 pontos"),
        Conquista(nome="Cheio de cocôs", descricao="Conseguiu 5000 pontos"),
        Conquista(nome="UMA MÁQUINA", descricao="Estudou por 5 horas seguidas"),
    ]

    with Session(engine) as session:
        for c in conquistas:
            query = select(Conquista).where(Conquista.nome == c.nome)
            existe = session.exec(query).first()

            if not existe:
                session.add(c)

        session.commit()

def dar_conquista(usuario_id: int, conquista_id: int):
    with Session(engine) as session:

        conquista = UsuarioConquista(
            usuario_id=usuario_id,
            conquista_id=conquista_id
        )

        session.add(conquista)
        session.commit()

def buscar_amigos(busca, user: Usuario):
    with Session(engine) as session:
        query = (select(Usuario)
                .join(Amizade, Amizade.amigo_id == Usuario.id)
                .where(
                    Amizade.usuario_id == user.id,
                    Usuario.nome.contains(busca)
                )
                .order_by(Usuario.nome)
        )
        return session.exec(query).all()
    
def buscar_users(busca, user: Usuario):
    with Session(engine) as session:
        query = (select(Usuario)
                .where(
                    Usuario.nome.contains(busca),
                    Usuario.id != user.id,
                    Usuario.id.not_in(select(Amizade.amigo_id).where(Amizade.usuario_id == user.id))
                )
                .order_by(Usuario.nome)
        )
        return session.exec(query).all()


def adicionar_amigo(user: Usuario, amigo_id: int):
    novo_valor = user.numero_amigos + 1
    with Session(engine) as session:
        ja_amigo = session.exec(
            select(Amizade).where(
                Amizade.usuario_id == user.id,
                Amizade.amigo_id == amigo_id
            )
        ).first()
        if ja_amigo:
            return 

        amizade = Amizade(usuario_id=user.id, amigo_id=amigo_id)
        session.add(amizade)
        db_user = session.get(Usuario, user.id)
        db_user.numero_amigos += 1
        session.add(db_user)
        session.commit()

    with Session(engine) as session:
        ids_conquistas = {uc.conquista_id for uc in session.exec(
            select(UsuarioConquista).where(UsuarioConquista.usuario_id == user.id)
        ).all()}

    if novo_valor == 1 and 2 not in ids_conquistas:
        dar_conquista(user.id, 2)
    if novo_valor == 20 and 3 not in ids_conquistas:
        dar_conquista(user.id, 3)
    

def remover_amigo(user: Usuario, amigo_id: int):
    with Session(engine) as session:
        query = select(Amizade).where(
            Amizade.usuario_id == user.id,
            Amizade.amigo_id == amigo_id
        )
        db_user = session.get(Usuario, user.id)
        db_user.numero_amigos -= 1
        session.add(db_user)
        amizade = session.exec(query).first()
        if amizade:
            session.delete(amizade)
        session.commit()

app = FastAPI()

@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    criar_conquistas()

class UsuarioCreate(BaseModel):
    nome: str
    senha: str
    bio: Optional[str] = None

class BioUpdate(BaseModel):
    id: int
    bio: str

# Monta a pasta "static" na rota "/static"
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")  


@app.post("/usuarios")
def criar_usuario(user: UsuarioCreate):
    with Session(engine) as session:
        novo_usuario = Usuario(nome=user.nome, senha=user.senha, bio=user.bio)
        session.add(novo_usuario)
        session.commit()
        session.refresh(novo_usuario)
    return {"nome": user.nome}

@app.get("/cadastro", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("cadastro.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("inicial.html", {"request": request})


@app.post("/login")
def login(user: UsuarioCreate, response: Response):
    with Session(engine) as session:
        query = (
            select(Usuario)
            .where(Usuario.nome == user.nome)
            .where(Usuario.senha == user.senha)
        )
        usuario = session.exec(query).first()
    
    if usuario == None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if usuario.primeiro_login:
        dar_conquista(usuario.id, 1)  # Conquista "Primeiro login"
        with Session(engine) as session:
            db_user = session.get(Usuario, usuario.id)
            db_user.primeiro_login = False
            session.add(db_user)
            session.commit()
    response.set_cookie(key="session_user", value=usuario.nome)
    return {"message": "Logado com sucesso", "nome": usuario.nome}

def get_active_user(session_user: Annotated[str | None, Cookie()] = None):
    if not session_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso negado: você não está logado."
        )

    with Session(engine) as session:

        query = select(Usuario).where(Usuario.nome == session_user)
        user = session.exec(query).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão inválida"
            )

        return user

@app.patch("/atualizar_bio")
def atualizar_descricao(
    request: Request,
    bio: str = Form(...),
    user: Usuario = Depends(get_active_user)
):
    with Session(engine) as session:
        db_user = session.get(Usuario, user.id)

        db_user.bio = bio
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        response = Response()
        response.headers["HX-Redirect"] = "/profile/perfil"
        return response

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user: Usuario = Depends(get_active_user)):
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "pagina": "/profile/perfil"
        }
    )

@app.get("/profile/perfil", response_class=HTMLResponse)
async def perfil_page(request: Request, user: dict = Depends(get_active_user)):
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse("profile.html", {"user": user, "pagina": "/profile/perfil", "request": request})
    return templates.TemplateResponse("perfil.html", {"user": user, "request": request})

@app.get("/profile/estudar", response_class=HTMLResponse)
async def estudar_page(request: Request, user: dict = Depends(get_active_user), perdeu: bool = False):
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse("profile.html", {"user": user, "pagina": "/profile/estudar", "request": request})
    return templates.TemplateResponse("estudar.html", {"user": user, "request": request})

@app.get("/profile/conquistas", response_class=HTMLResponse)
async def conquistas_page(request: Request, user: dict = Depends(get_active_user)):
    with Session(engine) as session:
        conquistas = session.exec(select(Conquista)).all()
        db_user = session.get(Usuario, user.id)
        ids_conquistas = {uc.conquista_id for uc in session.exec(
            select(UsuarioConquista).where(UsuarioConquista.usuario_id == user.id)
        ).all()}

    if not "HX-Request" in request.headers:
        return templates.TemplateResponse("profile.html", {"user": user, "pagina": "/profile/conquistas", "request": request})
    return templates.TemplateResponse("conquistas.html", {"user": user, "request": request, "conquistas": conquistas, "ids_conquistas": ids_conquistas})

@app.get("/profile/social", response_class=HTMLResponse)
async def social_page(request: Request, user: dict = Depends(get_active_user)):
    amigos = buscar_amigos("", user)
    users = buscar_users("", user)
    if (not "HX-Request" in request.headers):
        return templates.TemplateResponse("profile.html", {"user": user, "pagina": "/profile/social", "request": request})
    return templates.TemplateResponse("social.html", {"user": user, "request": request, "amigos": amigos, "users": users})

@app.get("/profile/social/listar_amigos", response_class=HTMLResponse)
def lista_amizade(request: Request, busca_amigos: str = "", user: Usuario = Depends(get_active_user)):
    amigos = buscar_amigos(busca_amigos, user)
    return templates.TemplateResponse("social.html", {"request": request, "amigos": amigos, "users": []})
    
@app.get("/profile/social/listar_users", response_class=HTMLResponse)
def lista_users(request: Request, busca_users: str = "", user: Usuario = Depends(get_active_user)):
    users = buscar_users(busca_users, user)
    return templates.TemplateResponse("social.html", {"request": request, "users": users, "amigos": []})


@app.post("/profile/social/adicionar_amigo")
def adicionar_amigo_endpoint(user_id: int = Form(...), user: Usuario = Depends(get_active_user)):
    adicionar_amigo(user, user_id)
    response = Response()
    response.headers["HX-Redirect"] = "/profile/social"
    return response

@app.post("/profile/social/remover_amigo")
def remover_amigo_endpoint(request: Request, amigo_id: int = Form(...), user: Usuario = Depends(get_active_user)):
    remover_amigo(user, amigo_id)
    response = Response()
    response.headers["HX-Redirect"] = "/profile/social"
    return response


@app.get("/profile/estudando", response_class=HTMLResponse)
async def estudando_page(request: Request, tempo: int, user: dict = Depends(get_active_user)):
    return templates.TemplateResponse("estudando.html", {"user": user, "request": request, "tempo": tempo})

@app.post("/profile/estudando/venceu", response_class=HTMLResponse)
async def finalizar_estudo(request: Request, tempo: int = Form(...), pontos: int = Form(...), user: dict = Depends(get_active_user)):
    if tempo >= 5*60*60:
        dar_conquista(user.id, 8)  # Conquista "UMA MÁQUINA"
    if user.pontuacao + pontos >= 100 and not any(c.conquista_id == 4 for c in user.conquistas):
        dar_conquista(user.id, 4)  # Conquista "Preguiçoso"
    if user.pontuacao + pontos >= 500 and not any(c.conquista_id == 5 for c in user.conquistas):
        dar_conquista(user.id, 5)  # Conquista "Dedicado"
    if user.pontuacao + pontos >= 1000 and not any(c.conquista_id == 6 for c in user.conquistas):
        dar_conquista(user.id, 6)  # Conquista "Disciplinado"
    if user.pontuacao + pontos >= 5000 and not any(c.conquista_id == 7 for c in user.conquistas):
        dar_conquista(user.id, 7)  # Conquista "Cheio de cocôs"
    with Session(engine) as session:
        db_user = session.get(Usuario, user.id)
        db_user.pontuacao += pontos
        db_user.temp_pontuacao = pontos
        session.add(db_user)
        session.commit()
    response = Response()
    response.headers["HX-Redirect"] = "/profile/vencedor"
    return response

@app.post("/profile/estudando/perdeu", response_class=HTMLResponse)
async def perder_estudo(request: Request, pontos: int = Form(...), user: dict = Depends(get_active_user)):
    with Session(engine) as session:
        db_user = session.get(Usuario, user.id)
        db_user.temp_pontuacao = pontos
        session.add(db_user)
        session.commit()
    response = Response()
    response.headers["HX-Redirect"] = "/profile/perdedor"
    return response

@app.get("/profile/perdedor", response_class=HTMLResponse)
async def perdedor_page(request: Request, user: dict = Depends(get_active_user)):
    return templates.TemplateResponse("perdedor.html", {"user": user, "request": request, "pontuacao": user.temp_pontuacao})

@app.get("/profile/vencedor", response_class=HTMLResponse)
async def vencedor_page(request: Request, user: dict = Depends(get_active_user)):
    return templates.TemplateResponse("vencedor.html", {"user": user, "request": request, "pontuacao": user.temp_pontuacao})

@app.post("/profile/vencedor/salvar_pontuacao", response_class=HTMLResponse)
async def salvar_pontuacao(request: Request, user: dict = Depends(get_active_user)):
    with Session(engine) as session:
        db_user = session.get(Usuario, user.id)
        db_user.temp_pontuacao = 0
        session.add(db_user)
        session.commit()
    response = Response()
    response.headers["HX-Redirect"] = "/profile/estudar"
    return response

@app.post("/profile/perdedor/sair", response_class=HTMLResponse)
async def sair_perdedor(request: Request, user: dict = Depends(get_active_user)):
    with Session(engine) as session:
        db_user = session.get(Usuario, user.id)
        db_user.temp_pontuacao = 0
        session.add(db_user)
        session.commit()
    response = Response()
    response.headers["HX-Redirect"] = "/profile/estudar"
    return response