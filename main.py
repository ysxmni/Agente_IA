import io
import sqlite3
import re
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf import PdfReader
import logging

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, TIMESTAMP, Text, Boolean, and_, or_
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from passlib.context import CryptContext
from pydantic import BaseModel
import datetime
from fastapi import Depends
from typing import List, Annotated
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from google import genai

# ════════════════════════════════════════════════════════════
# VARIÁVEIS DE AMBIENTE
# ════════════════════════════════════════════════════════════
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL", "sqlite:///contratos_v2.db")
HOST           = os.getenv("HOST", "0.0.0.0")
PORT           = int(os.getenv("PORT", 8000))

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE LOGGING
# ════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
# OAUTH2 E AUTENTICAÇÃO
# ════════════════════════════════════════════════════════════
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class UserLogin(BaseModel):
    username: str
    password: str

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO FASTAPI
# ════════════════════════════════════════════════════════════
app = FastAPI(
    title="Analisador de Contratos IA - Sistema Opersan",
    description="Sistema de análise de contratos com IA e gestão multi-setorial",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA IA GEMINI
# ════════════════════════════════════════════════════════════
if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY não encontrada no .env!")

try:
    client = genai.Client(api_key=GEMINI_API_KEY)

    MODELOS_PREFERENCIA = [
        'gemini-2.5-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-2.5-flash',
        'gemini-flash-latest',
        'gemini-2.0-flash',
    ]

    MODELO_ATIVO = None

    for modelo in MODELOS_PREFERENCIA:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents="teste de conectividade"
            )
            MODELO_ATIVO = modelo
            logger.info(f"✅ Modelo Gemini ativo: {modelo}")
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                logger.warning(f"⚠️  {modelo} - Cota excedida")
            elif "404" in error_str:
                logger.warning(f"⚠️  {modelo} - Modelo não disponível")
            else:
                logger.warning(f"⚠️  {modelo} - Erro: {error_str[:100]}")
            continue

    if not MODELO_ATIVO:
        logger.error("❌ Nenhum modelo Gemini disponível")
        raise Exception("Cota da API Gemini excedida.")

except Exception as e:
    logger.error(f"❌ Erro fatal ao configurar Gemini: {e}")
    client = None
    MODELO_ATIVO = None

# ════════════════════════════════════════════════════════════
# PROMPTS ESPECIALIZADOS POR SETOR
# ════════════════════════════════════════════════════════════
PROMPTS_SETORES = {
    "juridico": {
        "nome": "Jurídico",
        "icon": "scale",
        "cor": "#3b82f6",
        "resumo": """Você é um assistente jurídico especializado em análise de contratos.

FOCO PRINCIPAL: Análise legal, riscos jurídicos e conformidade contratual.

ESTRUTURA OBRIGATÓRIA DO RESUMO:

════════════════════════════════════════════════════════════
ANÁLISE JURÍDICA DO CONTRATO
════════════════════════════════════════════════════════════

1. QUALIFICAÇÃO JURÍDICA DO CONTRATO
   - Natureza jurídica: [tipo de contrato sob perspectiva legal]
   - Legislação aplicável: [leis, códigos e normas relevantes]
   - Jurisdição: [competência territorial]

2. PARTES CONTRATANTES
   Qualificação Completa:
   - Contratante: [nome, CNPJ/CPF, endereço, representante legal]
   - Contratado: [nome, CNPJ/CPF, endereço, representante legal]

3. OBJETO CONTRATUAL E CAUSA
   - Descrição legal do objeto
   - Licitude e possibilidade jurídica
   - Determinação ou determinabilidade

4. CLÁUSULAS ESSENCIAIS
   OBRIGAÇÕES PRINCIPAIS:
   - Do Contratante: [listar com fundamentação legal]
   - Do Contratado: [listar com fundamentação legal]

5. RISCOS JURÍDICOS IDENTIFICADOS
   ALTO RISCO:
   - [Listar riscos críticos que podem gerar litígio]
   
   MÉDIO RISCO:
   - [Listar riscos moderados]

6. RECOMENDAÇÕES JURÍDICAS
   - Ajustes contratuais sugeridos
   - Documentação complementar necessária

════════════════════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um assistente jurídico especializado em contratos.

CONTEXTO DO CONTRATO:
{contexto}

PERGUNTA DO USUÁRIO:
{pergunta}

Responda de forma clara, objetiva e fundamentada juridicamente."""
    },

    "suprimentos": {
        "nome": "Suprimentos",
        "icon": "package",
        "cor": "#10b981",
        "resumo": """Você é um especialista em gestão de suprimentos e compras.

FOCO PRINCIPAL: Análise comercial, condições de fornecimento e logística.

ESTRUTURA OBRIGATÓRIA DO RESUMO:

════════════════════════════════════════════════════════════
ANÁLISE DE SUPRIMENTOS E COMPRAS
════════════════════════════════════════════════════════════

1. INFORMAÇÕES DO FORNECEDOR
   - Razão Social: [nome completo]
   - CNPJ: [número]
   - Contato Comercial: [telefone/email]

2. ESPECIFICAÇÃO DO FORNECIMENTO
   PRODUTOS/SERVIÇOS:
   - Descrição detalhada: [especificações técnicas]
   - Quantidade: [unidades/volume]
   - Qualidade/Normas: [padrões, certificações]

3. CONDIÇÕES COMERCIAIS
   VALORES:
   - Preço Unitário: R$ [valor]
   - Valor Total: R$ [total]
   - Frete: [CIF/FOB - R$ valor]
   
   CONDIÇÕES DE PAGAMENTO:
   - Forma: [à vista, parcelado, faturado]
   - Prazo: [30/60/90 dias]

4. LOGÍSTICA E ENTREGA
   - Lead time: [dias úteis]
   - Prazo de entrega: [data específica]
   - Local de entrega: [endereço]

5. GARANTIAS E QUALIDADE
   - Prazo de garantia: [meses]
   - Certificações exigidas: [ISO, INMETRO, etc]

6. RISCOS DE SUPRIMENTOS
   - Riscos de entrega
   - Riscos de qualidade
   - Riscos de preço/reajuste

════════════════════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um especialista em compras e gestão de suprimentos.

CONTEXTO DO CONTRATO:
{contexto}

PERGUNTA DO USUÁRIO:
{pergunta}

Responda focando em aspectos comerciais, logísticos e de qualidade."""
    },

    "gestaocontratos": {
        "nome": "Gestão de Contratos",
        "icon": "folder-kanban",
        "cor": "#f59e0b",
        "resumo": """Você é um especialista em gestão operacional de contratos.
        
FOCO PRINCIPAL: Gestão operacional prática, com foco em evitar glosas e penalidades.

ESTRUTURA OBRIGATÓRIA DO RESUMO:

════════════════════════════════════════════════════════════
ANÁLISE DE GESTÃO OPERACIONAL
════════════════════════════════════════════════════════════

1. RESUMO DO ESCOPO OPERACIONAL
   - Atividades principais: [o que deve ser feito]
   - Local de execução: [onde]
   - Horário de atendimento: [quando]

2. MÃO DE OBRA E EQUIPE
   - Quantitativo exigido: [número de pessoas]
   - Qualificação necessária: [cursos, NR's, etc]
   - Uniformes e EPIs: [exigências]

3. MATERIAIS E EQUIPAMENTOS
   - Lista de equipamentos obrigatórios
   - Insumos/Produtos: [especificações]
   - Responsabilidade por manutenção

4. NÍVEIS DE SERVIÇO (SLA)
   - Tempo de resposta: [horas/minutos]
   - Frequência de execução: [diária/semanal]
   - Indicadores de desempenho: [KPIs]

5. PENALIDADES OPERACIONAIS E GLOSAS
   - Hipóteses de glosa: [o que gera desconto]
   - Valores/Percentuais: [% de multa]
   - Reincidência: [consequências]

6. CRONOGRAMA E PRAZOS
   - Início da execução: [data]
   - Vigência: [meses/anos]
   - Marcos importantes: [datas críticas]

════════════════════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um especialista em gestão operacional de contratos.

CONTEXTO DO CONTRATO:
{contexto}

PERGUNTA DO USUÁRIO:
{pergunta}

Responda focando em aspectos operacionais práticos, SLAs, penalidades e gestão do dia a dia."""
    }
}

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO BANCO DE DADOS
# ════════════════════════════════════════════════════════════
Base          = declarative_base()
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine        = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal  = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ════════════════════════════════════════════════════════════
# TABELAS DO BANCO DE DADOS
# ════════════════════════════════════════════════════════════

user_role_association = Table(
    'user_role_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id',  ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id',  ondelete='CASCADE'), primary_key=True)
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

class User(Base):
    __tablename__ = 'users'
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String,  unique=True, nullable=False, index=True)
    name            = Column(String,  nullable=True)
    hashed_password = Column(String,  nullable=False)
    role            = Column(String,  default='user')
    is_active       = Column(Boolean, default=True)
    created_at      = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    roles           = relationship("Role", secondary=user_role_association, back_populates="users")

    can_see = relationship(
        "UserVisibilityPermission",
        foreign_keys="UserVisibilityPermission.viewer_id",
        back_populates="viewer",
        cascade="all, delete-orphan"
    )

class Role(Base):
    __tablename__ = 'roles'
    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String,  unique=True, nullable=False)
    description = Column(String,  nullable=True, default="")
    created_at  = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    users       = relationship("User", secondary=user_role_association, back_populates="roles")

class Contract(Base):
    __tablename__ = 'contratos'
    id         = Column(Integer, primary_key=True, index=True)
    nome       = Column(String,  nullable=False)
    texto      = Column(Text,    nullable=False)
    resumo     = Column(Text)
    setor      = Column(String,  default='juridico')
    user_id    = Column(Integer, ForeignKey('users.id'))
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)

class Message(Base):
    __tablename__ = 'mensagens'
    id          = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey('contratos.id', ondelete="CASCADE"))
    autor       = Column(String)
    texto       = Column(Text)
    created_at  = Column(TIMESTAMP, default=datetime.datetime.utcnow)

# ════════════════════════════════════════════════════════════
# PERMISSÕES DE VISIBILIDADE
#
# viewer_id  → usuário que RECEBE a permissão (pode ver)
# target_id  → usuário cujos contratos serão VISÍVEIS
#              (quando target_id = -1 e sector_slug definido → acesso ao setor inteiro)
#
# Tipos de permissão:
#   perm_type = "user"   → acesso a contratos de um usuário específico
#   perm_type = "sector" → acesso a todos os contratos de um setor inteiro
# ════════════════════════════════════════════════════════════
class UserVisibilityPermission(Base):
    __tablename__ = 'user_visibility_permissions'
    id          = Column(Integer, primary_key=True, index=True)
    viewer_id   = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    target_id   = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    perm_type   = Column(String,  default='user')   # 'user' | 'sector'
    sector_slug = Column(String,  nullable=True)    # slug do setor quando perm_type='sector'
    created_at  = Column(TIMESTAMP, default=datetime.datetime.utcnow)

    viewer = relationship("User", foreign_keys=[viewer_id], back_populates="can_see")
    target = relationship("User", foreign_keys=[target_id])

# ════════════════════════════════════════════════════════════
# MODELOS PYDANTIC
# ════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    username: str
    password: str
    name:     Optional[str] = None
    role:     str           = 'user'
    role_ids: List[int]     = []

class RoleCreate(BaseModel):
    name:        str
    description: Optional[str] = ""

class RoleOut(BaseModel):
    id:          int
    name:        str
    description: Optional[str] = ""
    created_at:  Optional[datetime.datetime] = None
    class Config:
        from_attributes = True

class UserOut(BaseModel):
    id:       int
    username: str
    name:     Optional[str] = None
    role:     str
    roles:    List[RoleOut]
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str]       = None
    password: Optional[str]       = None
    role_ids: Optional[List[int]] = None

class RoleUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None

class SetUserVisibilityBody(BaseModel):
    """
    Payload para definir as permissões de um viewer.
    target_ids   → lista de IDs de usuários cujos contratos ele pode ver
    sector_slugs → lista de slugs de setor para acesso total ao setor
    """
    target_ids:   List[int] = []
    sector_slugs: List[str] = []

# ════════════════════════════════════════════════════════════
# CRIAÇÃO DO BANCO E MIGRAÇÃO
# ════════════════════════════════════════════════════════════

Base.metadata.create_all(bind=engine)
logger.info("✅ Tabelas do banco de dados criadas/verificadas")

def migrar_banco():
    db_path = DATABASE_URL.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Migração: coluna description em roles
        cursor.execute("PRAGMA table_info(roles)")
        colunas_roles = [row[1] for row in cursor.fetchall()]
        if "description" not in colunas_roles:
            cursor.execute("ALTER TABLE roles ADD COLUMN description TEXT DEFAULT ''")
            conn.commit()
            logger.info("✅ Migração: coluna 'description' adicionada à tabela roles")

        # Garante que a tabela de visibilidade existe com as colunas corretas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_visibility_permissions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                viewer_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                target_id   INTEGER REFERENCES users(id) ON DELETE CASCADE,
                perm_type   TEXT DEFAULT 'user',
                sector_slug TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migração: adicionar colunas novas caso tabela já existia sem elas
        cursor.execute("PRAGMA table_info(user_visibility_permissions)")
        cols_perm = [row[1] for row in cursor.fetchall()]
        if "perm_type" not in cols_perm:
            cursor.execute("ALTER TABLE user_visibility_permissions ADD COLUMN perm_type TEXT DEFAULT 'user'")
            conn.commit()
            logger.info("✅ Migração: coluna 'perm_type' adicionada")
        if "sector_slug" not in cols_perm:
            cursor.execute("ALTER TABLE user_visibility_permissions ADD COLUMN sector_slug TEXT")
            conn.commit()
            logger.info("✅ Migração: coluna 'sector_slug' adicionada")

        logger.info("✅ Migração: tabela user_visibility_permissions garantida")
        conn.close()
    except Exception as e:
        logger.warning(f"⚠️ Migração: {e}")

migrar_banco()

def create_default_roles_and_admin():
    db = SessionLocal()
    try:
        setores_padrao = [
            ("Admin",                 "Acesso administrativo completo"),
            ("Jurídico",              "Análise jurídica de contratos"),
            ("Suprimentos",           "Gestão de compras e fornecedores"),
            ("Gestão de Contratos",   "Gestão operacional de contratos"),
        ]
        for setor_nome, setor_desc in setores_padrao:
            if not db.query(Role).filter(Role.name == setor_nome).first():
                db.add(Role(name=setor_nome, description=setor_desc))
                logger.info(f"  ✅ Setor criado: {setor_nome}")
        db.commit()

        admin_username = "admin@opersan.com.br"
        admin_password = "admin123"

        if not db.query(User).filter(User.username == admin_username).first():
            admin_role = db.query(Role).filter(Role.name == "Admin").first()
            hashed_pwd = hash_password(admin_password)
            admin_user = User(
                username        = admin_username,
                name            = "Administrador",
                hashed_password = hashed_pwd,
                role            = 'admin'
            )
            if admin_role:
                admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            logger.info(f"✅ Usuário admin criado: {admin_username}")
        else:
            logger.info(f"ℹ️  Usuário admin já existe")

    except Exception as e:
        logger.error(f"❌ Erro ao criar dados iniciais: {e}")
        db.rollback()
    finally:
        db.close()

create_default_roles_and_admin()

# ════════════════════════════════════════════════════════════
# DEPENDENCY INJECTION
# ════════════════════════════════════════════════════════════

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ════════════════════════════════════════════════════════════
# FUNÇÕES DE AUTENTICAÇÃO
# ════════════════════════════════════════════════════════════

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Token de autenticação não fornecido",
            headers={"WWW-Authenticate": "Bearer"}
        )
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuário desativado")
    return user

async def get_current_admin_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Session = Depends(get_db)
) -> User:
    user = await get_current_user(token, db)
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Acesso negado. Requer permissão de administrador.")
    return user

# ════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ════════════════════════════════════════════════════════════

def limpar_markdown(texto: str) -> str:
    if not texto:
        return texto
    texto = re.sub(r'```(?:markdown|html|json|text)?\n?', '', texto, flags=re.IGNORECASE)
    texto = texto.replace('```', '')
    texto = texto.replace('***', '').replace('**', '').replace('*', '')
    texto = texto.replace('___', '').replace('__', '').replace('_', '')
    return texto.strip()

def extrair_texto_pdf(conteudo: bytes) -> str:
    try:
        leitor         = PdfReader(io.BytesIO(conteudo))
        texto_completo = []
        for pagina in leitor.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_completo.append(texto_pagina)
        return "\n\n".join(texto_completo)
    except Exception as e:
        logger.error(f"❌ Erro ao extrair texto do PDF: {e}")
        raise HTTPException(status_code=400, detail="Erro ao processar PDF.")

def gerar_resumo_ia(texto: str, setor: str = "juridico") -> str:
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."
    texto_limitado = texto[:15000]
    config_setor   = PROMPTS_SETORES.get(setor, PROMPTS_SETORES["juridico"])
    prompt         = config_setor["resumo"].format(texto=texto_limitado)
    try:
        response = client.models.generate_content(model=MODELO_ATIVO, contents=prompt)
        if response and response.text:
            return limpar_markdown(response.text)
        return "❌ Erro: Resposta vazia da IA"
    except Exception as e:
        return f"❌ Erro ao processar com IA: {str(e)[:200]}"

def gerar_resposta_ia(pergunta: str, contexto: str, setor: str = "juridico") -> str:
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."
    config_setor = PROMPTS_SETORES.get(setor, PROMPTS_SETORES["juridico"])
    prompt       = config_setor["perguntas"].format(
        pergunta = pergunta,
        contexto = contexto[:10000]
    )
    try:
        response = client.models.generate_content(model=MODELO_ATIVO, contents=prompt)
        if response and response.text:
            return limpar_markdown(response.text)
        return "❌ Não foi possível gerar uma resposta."
    except Exception as e:
        return f"❌ Erro ao processar pergunta: {str(e)[:200]}"

def formatar_nome_usuario(user: User) -> str:
    raw = user.name or user.username or ""
    if "@" in raw:
        raw = raw.split("@")[0]
    return " ".join(
        p.capitalize() for p in raw.replace(".", " ").replace("_", " ").replace("-", " ").split()
    ) or "Usuário"

def avatar_color(user_id: int) -> str:
    palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#14b8a6"]
    return palette[user_id % len(palette)]

def get_iniciais(nome: str) -> str:
    partes = nome.strip().split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[-1][0]).upper()
    return nome[:2].upper() if nome else "??"

def is_admin_user(user: User) -> bool:
    return (
        user.role.lower() == "admin" or
        any(r.name.lower() == "admin" for r in user.roles)
    )

def get_setores_permitidos(user: User) -> List[str]:
    if is_admin_user(user):
        return list(PROMPTS_SETORES.keys())
    setores = []
    for role in user.roles:
        slug = role.name.lower().replace(" ", "").replace("ã", "a").replace("ê", "e").replace("ç", "c")
        mapa = {
            "juridico":          "juridico",
            "jurídico":          "juridico",
            "suprimentos":       "suprimentos",
            "gestaocontratos":   "gestaocontratos",
            "gestãodecontratos": "gestaocontratos",
        }
        slug_norm = role.name.lower().replace("ã", "a").replace("ê", "e").replace("ç", "c").replace(" ", "")
        mapped = mapa.get(slug_norm) or mapa.get(role.name.lower())
        if mapped and mapped not in setores:
            setores.append(mapped)
    return list(set(setores)) or ["juridico"]

def _user_info_dict(u: User) -> dict:
    nome = formatar_nome_usuario(u)
    return {
        "id":       u.id,
        "username": u.username,
        "nome":     nome,
        "iniciais": get_iniciais(nome),
        "cor":      avatar_color(u.id),
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS — AUTENTICAÇÃO
# ════════════════════════════════════════════════════════════

@app.post("/token", tags=["Autenticação"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db:        Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    return {
        "access_token": user.username,
        "token_type":   "bearer",
        "user": {
            "id":       user.id,
            "username": user.username,
            "name":     user.name,
            "role":     user.role,
            "roles":    [{"id": r.id, "name": r.name} for r in user.roles]
        }
    }

@app.get("/users/me", tags=["Autenticação"])
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "id":       current_user.id,
        "username": current_user.username,
        "name":     current_user.name,
        "role":     current_user.role,
        "roles":    [{"id": role.id, "name": role.name} for role in current_user.roles]
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS — ADMINISTRAÇÃO DE USUÁRIOS
# ════════════════════════════════════════════════════════════

@app.post("/admin/users", response_model=UserOut, tags=["Administração"])
async def create_user(
    user:  UserCreate,
    db:    Session = Depends(get_db),
    admin: User    = Depends(get_current_admin_user)
):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail=f"Usuário '{user.username}' já existe")
    new_user = User(
        username        = user.username,
        name            = user.name,
        hashed_password = hash_password(user.password),
        role            = user.role
    )
    if user.role_ids:
        roles          = db.query(Role).filter(Role.id.in_(user.role_ids)).all()
        new_user.roles = roles
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/admin/users", response_model=List[UserOut], tags=["Administração"])
async def list_users(
    db:    Session = Depends(get_db),
    admin: User    = Depends(get_current_admin_user)
):
    return db.query(User).all()

@app.delete("/admin/users/{user_id}", tags=["Administração"])
async def delete_user(
    user_id: int,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(get_current_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode deletar sua própria conta")
    username = user.username
    db.delete(user)
    db.commit()
    return {"detail": f"Usuário '{username}' deletado com sucesso"}

@app.put("/admin/users/{user_id}", response_model=UserOut, tags=["Administração"])
def update_user(
    user_id:      int,
    user_data:    UserUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user_data.username:
        db_user.username = user_data.username
    if user_data.password:
        db_user.hashed_password = hash_password(user_data.password)
    if user_data.role_ids is not None:
        roles         = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        db_user.roles = roles
    db.commit()
    db.refresh(db_user)
    return db_user

# ════════════════════════════════════════════════════════════
# ENDPOINTS — ADMINISTRAÇÃO DE ROLES
# ════════════════════════════════════════════════════════════

@app.post("/admin/roles", response_model=RoleOut, tags=["Administração"])
async def create_role(
    role:  RoleCreate,
    db:    Session = Depends(get_db),
    admin: User    = Depends(get_current_admin_user)
):
    if db.query(Role).filter(Role.name == role.name).first():
        raise HTTPException(status_code=400, detail=f"Setor '{role.name}' já existe")
    new_role = Role(name=role.name, description=role.description or "")
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@app.get("/admin/roles", response_model=List[RoleOut], tags=["Administração"])
async def list_roles(
    db:    Session = Depends(get_db),
    admin: User    = Depends(get_current_admin_user)
):
    return db.query(Role).all()

@app.put("/admin/roles/{role_id}", response_model=RoleOut, tags=["Administração"])
async def update_role(
    role_id:   int,
    role_data: RoleUpdate,
    db:        Session = Depends(get_db),
    admin:     User    = Depends(get_current_admin_user)
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    if role_data.name is not None:
        existente = db.query(Role).filter(Role.name == role_data.name, Role.id != role_id).first()
        if existente:
            raise HTTPException(status_code=400, detail=f"Setor '{role_data.name}' já existe")
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    db.commit()
    db.refresh(role)
    return role

@app.delete("/admin/roles/{role_id}", tags=["Administração"])
async def delete_role(
    role_id: int,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(get_current_admin_user)
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    role_name = role.name
    db.delete(role)
    db.commit()
    return {"detail": f"Setor '{role_name}' deletado com sucesso"}

# ════════════════════════════════════════════════════════════
# ENDPOINTS — PERMISSÕES DE VISIBILIDADE
# ════════════════════════════════════════════════════════════

@app.get("/admin/visibility", tags=["Permissões de Visibilidade"])
async def listar_todas_permissoes(
    db:    Session = Depends(get_db),
    admin: User    = Depends(get_current_admin_user)
):
    todos_users = db.query(User).all()
    user_map    = {u.id: u for u in todos_users}
    perms       = db.query(UserVisibilityPermission).all()

    por_viewer: dict = {}
    for p in perms:
        if p.viewer_id not in por_viewer:
            viewer = user_map.get(p.viewer_id)
            if not viewer:
                continue
            nome_viewer = formatar_nome_usuario(viewer)
            por_viewer[p.viewer_id] = {
                "viewer_id":       p.viewer_id,
                "viewer_username": viewer.username,
                "viewer_nome":     nome_viewer,
                "viewer_iniciais": get_iniciais(nome_viewer),
                "viewer_cor":      avatar_color(p.viewer_id),
                "can_see":         [],
                "sectors":         [],
            }

        if p.perm_type == "sector" and p.sector_slug:
            por_viewer[p.viewer_id]["sectors"].append(p.sector_slug)
        elif p.perm_type == "user" and p.target_id:
            target = user_map.get(p.target_id)
            if target:
                nome_target = formatar_nome_usuario(target)
                por_viewer[p.viewer_id]["can_see"].append({
                    "perm_id":         p.id,
                    "target_id":       p.target_id,
                    "target_username": target.username,
                    "target_nome":     nome_target,
                    "target_iniciais": get_iniciais(nome_target),
                    "target_cor":      avatar_color(p.target_id),
                })

    return {
        "permissoes": list(por_viewer.values()),
        "total_users": len(todos_users),
        "users": [
            {
                "id":       u.id,
                "username": u.username,
                "nome":     formatar_nome_usuario(u),
                "iniciais": get_iniciais(formatar_nome_usuario(u)),
                "cor":      avatar_color(u.id),
                "setor":    u.roles[0].name if u.roles else "—",
                "is_admin": is_admin_user(u),
            }
            for u in todos_users
        ]
    }

@app.get("/admin/visibility/{viewer_id}", tags=["Permissões de Visibilidade"])
async def listar_permissoes_viewer(
    viewer_id: int,
    db:        Session = Depends(get_db),
    admin:     User    = Depends(get_current_admin_user)
):
    viewer = db.query(User).filter(User.id == viewer_id).first()
    if not viewer:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    perms = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id
    ).all()

    targets = []
    sectors = []

    for p in perms:
        if p.perm_type == "sector" and p.sector_slug:
            sectors.append(p.sector_slug)
        elif p.perm_type == "user" and p.target_id:
            target = db.query(User).filter(User.id == p.target_id).first()
            if target:
                nome = formatar_nome_usuario(target)
                targets.append({
                    "perm_id":  p.id,
                    "id":       target.id,
                    "username": target.username,
                    "nome":     nome,
                    "iniciais": get_iniciais(nome),
                    "cor":      avatar_color(target.id),
                })

    return {
        "viewer_id": viewer_id,
        "can_see":   targets,
        "sectors":   sectors,
    }

@app.put("/admin/visibility/{viewer_id}", tags=["Permissões de Visibilidade"])
async def definir_permissoes_viewer(
    viewer_id: int,
    body:      SetUserVisibilityBody,
    db:        Session = Depends(get_db),
    admin:     User    = Depends(get_current_admin_user)
):
    viewer = db.query(User).filter(User.id == viewer_id).first()
    if not viewer:
        raise HTTPException(status_code=404, detail="Usuário viewer não encontrado")

    if body.target_ids:
        targets_existentes = db.query(User).filter(User.id.in_(body.target_ids)).all()
        ids_existentes     = {t.id for t in targets_existentes}
        invalidos          = set(body.target_ids) - ids_existentes
        if invalidos:
            raise HTTPException(status_code=400, detail=f"Usuários não encontrados: {list(invalidos)}")

    slugs_validos = set(PROMPTS_SETORES.keys())
    if body.sector_slugs:
        invalidos_setor = set(body.sector_slugs) - slugs_validos
        if invalidos_setor:
            raise HTTPException(status_code=400, detail=f"Setores inválidos: {list(invalidos_setor)}")

    db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id
    ).delete(synchronize_session=False)

    for target_id in set(body.target_ids):
        if target_id == viewer_id:
            continue
        db.add(UserVisibilityPermission(
            viewer_id   = viewer_id,
            target_id   = target_id,
            perm_type   = "user",
            sector_slug = None
        ))

    for slug in set(body.sector_slugs):
        if slug in slugs_validos:
            db.add(UserVisibilityPermission(
                viewer_id   = viewer_id,
                target_id   = None,
                perm_type   = "sector",
                sector_slug = slug
            ))

    db.commit()
    logger.info(f"✅ Permissões atualizadas: viewer={viewer_id}, targets={body.target_ids}, sectors={body.sector_slugs}")

    return {
        "detail":       "Permissões atualizadas com sucesso",
        "viewer_id":    viewer_id,
        "target_ids":   list(set(body.target_ids)),
        "sector_slugs": list(set(body.sector_slugs)),
    }

@app.delete("/admin/visibility/{viewer_id}/{target_id}", tags=["Permissões de Visibilidade"])
async def revogar_permissao(
    viewer_id: int,
    target_id: int,
    db:        Session = Depends(get_db),
    admin:     User    = Depends(get_current_admin_user)
):
    perm = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id,
        UserVisibilityPermission.target_id == target_id,
        UserVisibilityPermission.perm_type == "user"
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permissão não encontrada")
    db.delete(perm)
    db.commit()
    return {"detail": "Permissão revogada com sucesso"}

# ════════════════════════════════════════════════════════════
# ENDPOINT: Permissões do usuário logado
# ════════════════════════════════════════════════════════════

@app.get("/my/visibility", tags=["Permissões de Visibilidade"])
async def minhas_permissoes_visibilidade(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user)
):
    perms = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == current_user.id
    ).all()

    can_see = []
    sectors = []

    for p in perms:
        if p.perm_type == "sector" and p.sector_slug:
            sectors.append(p.sector_slug)
        elif p.perm_type == "user" and p.target_id:
            target = db.query(User).filter(User.id == p.target_id).first()
            if target and target.is_active:
                nome = formatar_nome_usuario(target)
                can_see.append({
                    "id":       target.id,
                    "username": target.username,
                    "nome":     nome,
                    "iniciais": get_iniciais(nome),
                    "cor":      avatar_color(target.id),
                })

    return {
        "viewer_id": current_user.id,
        "can_see":   can_see,
        "sectors":   sectors,
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS — CONTRATOS
# ════════════════════════════════════════════════════════════

@app.post("/upload", tags=["Contratos"])
async def upload_contrato(
    file:         UploadFile = File(...),
    setor:        str        = Form("juridico"),
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(get_current_user)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são permitidos")
    if setor not in PROMPTS_SETORES:
        setor = "juridico"

    try:
        conteudo = await file.read()
        texto    = extrair_texto_pdf(conteudo)
        if not texto or len(texto.strip()) < 50:
            raise HTTPException(status_code=400, detail="Não foi possível extrair texto do PDF.")

        resumo = gerar_resumo_ia(texto, setor)

        novo_contrato = Contract(
            nome    = file.filename,
            texto   = texto,
            resumo  = resumo,
            setor   = setor,
            user_id = current_user.id
        )
        db.add(novo_contrato)
        db.commit()
        db.refresh(novo_contrato)

        db.add(Message(
            contrato_id = novo_contrato.id,
            autor       = "ai",
            texto       = f"Análise concluída pelo setor {PROMPTS_SETORES[setor]['nome']}."
        ))
        db.commit()

        return {
            "id":         novo_contrato.id,
            "nome":       file.filename,
            "resumo":     resumo,
            "setor":      setor,
            "setor_nome": PROMPTS_SETORES[setor]['nome']
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

@app.get("/contratos/listar", tags=["Contratos"])
async def listar_contratos(
    analyst_id:   Optional[int] = None,
    sector_id:    Optional[str] = None,
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(get_current_user)
):
    admin        = is_admin_user(current_user)
    meus_setores = get_setores_permitidos(current_user)

    if admin:
        query = db.query(Contract)
        if sector_id and sector_id in PROMPTS_SETORES:
            query = query.filter(Contract.setor == sector_id)
        if analyst_id:
            query = query.filter(Contract.user_id == analyst_id)
        contratos = query.order_by(Contract.created_at.desc()).all()

    else:
        perms = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id
        ).all()

        target_ids_por_usuario = set()
        slugs_por_setor        = set()

        for p in perms:
            if p.perm_type == "user" and p.target_id:
                target_ids_por_usuario.add(p.target_id)
            elif p.perm_type == "sector" and p.sector_slug:
                slugs_por_setor.add(p.sector_slug)

        if analyst_id:
            if analyst_id != current_user.id and analyst_id not in target_ids_por_usuario:
                analista_obj = db.query(User).filter(User.id == analyst_id).first()
                if analista_obj:
                    setores_analista = get_setores_permitidos(analista_obj)
                    if not any(s in slugs_por_setor for s in setores_analista):
                        raise HTTPException(
                            status_code=403,
                            detail="Você não tem permissão para visualizar contratos deste analista."
                        )
            ids_buscar = [analyst_id]
            query      = db.query(Contract).filter(
                Contract.user_id.in_(ids_buscar),
                Contract.setor.in_(meus_setores)
            )
            if sector_id and sector_id in meus_setores:
                query = query.filter(Contract.setor == sector_id)
            contratos = query.order_by(Contract.created_at.desc()).all()

        else:
            ids_usuario = target_ids_por_usuario | {current_user.id}

            conditions = []

            if ids_usuario:
                conditions.append(
                    and_(
                        Contract.user_id.in_(ids_usuario),
                        Contract.setor.in_(meus_setores)
                    )
                )

            for slug in slugs_por_setor:
                conditions.append(Contract.setor == slug)

            if not conditions:
                contratos = []
            else:
                query = db.query(Contract).filter(or_(*conditions))
                if sector_id:
                    query = query.filter(Contract.setor == sector_id)
                contratos = query.order_by(Contract.created_at.desc()).all()

    user_ids  = list({c.user_id for c in contratos if c.user_id})
    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    result = []
    for c in contratos:
        analista_user = users_map.get(c.user_id)
        if analista_user:
            nome_analista = formatar_nome_usuario(analista_user)
            analista_obj  = {
                "id":       analista_user.id,
                "nome":     nome_analista,
                "iniciais": get_iniciais(nome_analista),
                "cor":      avatar_color(analista_user.id),
            }
        else:
            analista_obj = {"id": None, "nome": "Desconhecido", "iniciais": "??", "cor": "#475569"}

        is_mine      = (c.user_id == current_user.id)
        show_analyst = admin or (not is_mine)

        result.append({
            "id":           c.id,
            "nome":         c.nome,
            "data":         c.created_at.isoformat() if c.created_at else None,
            "setor":        c.setor,
            "setor_nome":   PROMPTS_SETORES.get(c.setor, {}).get('nome', c.setor),
            "preview":      c.resumo[:200] + "..." if c.resumo and len(c.resumo) > 200 else c.resumo,
            "analista":     analista_obj,
            "is_mine":      is_mine,
            "show_analyst": show_analyst,
        })

    return result

@app.get("/contratos/{contrato_id}", tags=["Contratos"])
async def obter_contrato(
    contrato_id:  int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user)
):
    contrato = db.query(Contract).filter(Contract.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    admin = is_admin_user(current_user)
    if not admin and contrato.user_id != current_user.id:
        perm_user = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.target_id == contrato.user_id,
            UserVisibilityPermission.perm_type == "user"
        ).first()

        perm_setor = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.perm_type == "sector",
            UserVisibilityPermission.sector_slug == contrato.setor
        ).first()

        if not perm_user and not perm_setor:
            raise HTTPException(status_code=403, detail="Acesso negado a este contrato.")

    mensagens = db.query(Message).filter(
        Message.contrato_id == contrato_id
    ).order_by(Message.created_at).all()

    analista_user = db.query(User).filter(User.id == contrato.user_id).first()
    analista_obj  = None
    if analista_user:
        nome = formatar_nome_usuario(analista_user)
        analista_obj = {
            "id":       analista_user.id,
            "nome":     nome,
            "iniciais": get_iniciais(nome),
            "cor":      avatar_color(analista_user.id),
        }

    return {
        "id":         contrato.id,
        "nome":       contrato.nome,
        "resumo":     contrato.resumo,
        "setor":      contrato.setor,
        "setor_nome": PROMPTS_SETORES.get(contrato.setor, {}).get('nome', contrato.setor),
        "analista":   analista_obj,
        "mensagens":  [{
            "id":    msg.id,
            "autor": msg.autor,
            "texto": msg.texto,
            "data":  msg.created_at.isoformat() if msg.created_at else None
        } for msg in mensagens]
    }

@app.delete("/contratos/{contrato_id}", tags=["Contratos"])
async def excluir_contrato(
    contrato_id:  int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user)
):
    contrato = db.query(Contract).filter(Contract.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    if not is_admin_user(current_user) and contrato.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Você não pode excluir contratos de outros usuários.")

    db.query(Message).filter(Message.contrato_id == contrato_id).delete()
    nome = contrato.nome
    db.delete(contrato)
    db.commit()
    return {"detail": f"Contrato '{nome}' excluído com sucesso"}

# ════════════════════════════════════════════════════════════
# ENDPOINT CHAT
# ════════════════════════════════════════════════════════════

@app.post("/perguntar", tags=["Chat"])
async def perguntar_contrato(
    request:     Request,
    pergunta:    str           = Form(...),
    setor:       str           = Form("juridico"),
    contrato_id: Optional[int] = Form(None),
    db:          Session       = Depends(get_db)
):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token não fornecido", headers={"WWW-Authenticate": "Bearer"})

    token = auth_header[7:].strip()
    if not token or token in ("null", "undefined", ""):
        raise HTTPException(status_code=401, detail="Token inválido", headers={"WWW-Authenticate": "Bearer"})

    current_user = db.query(User).filter(User.username == token).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado", headers={"WWW-Authenticate": "Bearer"})
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Usuário desativado")

    contrato = None
    if contrato_id:
        contrato = db.query(Contract).filter(Contract.id == contrato_id).first()

    if not contrato:
        contrato = db.query(Contract).filter(
            Contract.user_id == current_user.id
        ).order_by(Contract.created_at.desc()).first()

    if not contrato:
        contrato = db.query(Contract).order_by(Contract.created_at.desc()).first()

    if not contrato:
        raise HTTPException(status_code=404, detail="Nenhum contrato encontrado.")

    admin = is_admin_user(current_user)
    if not admin and contrato.user_id != current_user.id:
        perm_user = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.target_id == contrato.user_id,
            UserVisibilityPermission.perm_type == "user"
        ).first()
        perm_setor = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.perm_type == "sector",
            UserVisibilityPermission.sector_slug == contrato.setor
        ).first()
        if not perm_user and not perm_setor:
            raise HTTPException(status_code=403, detail="Acesso negado a este contrato.")

    if setor not in PROMPTS_SETORES:
        setor = "juridico"

    db.add(Message(contrato_id=contrato.id, autor="user", texto=pergunta))
    db.commit()

    resposta_ia = gerar_resposta_ia(pergunta=pergunta, contexto=contrato.texto, setor=setor)

    db.add(Message(contrato_id=contrato.id, autor="ai", texto=resposta_ia))
    db.commit()

    return {
        "resposta":    resposta_ia,
        "pergunta":    pergunta,
        "setor_usado": setor,
        "setor_nome":  PROMPTS_SETORES[setor]['nome'],
        "contrato_id": contrato.id
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS DO SISTEMA
# ════════════════════════════════════════════════════════════

@app.get("/", tags=["Sistema"])
async def root():
    return {
        "sistema":             "Analisador de Contratos IA - Opersan",
        "versao":              "3.0.0",
        "status":              "online",
        "ia_disponivel":       MODELO_ATIVO is not None,
        "modelo_ia":           MODELO_ATIVO,
        "setores_disponiveis": list(PROMPTS_SETORES.keys())
    }

@app.get("/health", tags=["Sistema"])
async def health_check():
    return {
        "status":   "healthy",
        "database": "connected",
        "ia":       "available" if MODELO_ATIVO else "unavailable"
    }

# ════════════════════════════════════════════════════════════
# EXECUÇÃO
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO SERVIDOR - Sistema Opersan v3.0")
    logger.info("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT)