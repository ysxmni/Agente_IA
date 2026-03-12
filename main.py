import io
import re
import time
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
import logging

# ════════════════════════════════════════════════════════════
# IMPORTAÇÕES PARA EXTRAÇÃO ROBUSTA DE PDF
# pip install pymupdf pdfplumber
# ════════════════════════════════════════════════════════════
try:
    import fitz
    PYMUPDF_DISPONIVEL = True
except ImportError:
    PYMUPDF_DISPONIVEL = False

try:
    import pdfplumber
    PDFPLUMBER_DISPONIVEL = True
except ImportError:
    PDFPLUMBER_DISPONIVEL = False

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, TIMESTAMP, Text, Boolean, and_, or_
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from passlib.context import CryptContext
from pydantic import BaseModel
import datetime
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from google import genai
from dotenv import load_dotenv
import os

# ════════════════════════════════════════════════════════════
# VARIÁVEIS DE AMBIENTE
# ════════════════════════════════════════════════════════════
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL", "sqlite:///contratos_v2.db")
HOST           = os.getenv("HOST", "0.0.0.0")
PORT           = int(os.getenv("PORT", 8000))

# ════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"pymupdf: {PYMUPDF_DISPONIVEL} | pdfplumber: {PDFPLUMBER_DISPONIVEL}")

# ════════════════════════════════════════════════════════════
# OAUTH2
# ════════════════════════════════════════════════════════════
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class UserLogin(BaseModel):
    username: str
    password: str

# ════════════════════════════════════════════════════════════
# FASTAPI
# ════════════════════════════════════════════════════════════
app = FastAPI(
    title="Analisador de Contratos IA - Sistema Opersan",
    description="Sistema de análise de contratos com IA e gestão multi-setorial",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ysxmni.github.io",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════
# GEMINI — INICIALIZAÇÃO COM FALLBACK DE MODELOS
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
            response = client.models.generate_content(model=modelo, contents="teste")
            MODELO_ATIVO = modelo
            logger.info(f"✅ Modelo Gemini ativo: {modelo}")
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                logger.warning(f"⚠️  {modelo} - Cota excedida")
            elif "404" in error_str:
                logger.warning(f"⚠️  {modelo} - Não disponível")
            else:
                logger.warning(f"⚠️  {modelo} - Erro: {error_str[:80]}")
    if not MODELO_ATIVO:
        raise Exception("Nenhum modelo Gemini disponível.")
except Exception as e:
    logger.error(f"❌ Gemini: {e}")
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

════════════════════════════════════════════
REGRAS ABSOLUTAS — LEIA ANTES DE COMEÇAR
════════════════════════════════════════════
1. Extraia SOMENTE informações que estejam literalmente escritas no contrato abaixo.
2. Após cada informação, indique entre colchetes a origem exata: [Cláusula X], [Item Y.Z], [Preâmbulo], [Cabeçalho], etc.
3. Se uma informação NÃO estiver no contrato, escreva: "Não consta no contrato."
4. NUNCA use palavras como "provavelmente", "possivelmente", "deve estar" ou "conforme anexo" sem transcrever o que o contrato diz.
5. Se o contrato mencionar um anexo, transcreva o trecho exato que o menciona.

════════════════════════════════════════════
ESTRUTURA OBRIGATÓRIA DO RESUMO
════════════════════════════════════════════

ANÁLISE JURÍDICA DO CONTRATO
════════════════════════════════════════════

1. QUALIFICAÇÃO JURÍDICA DO CONTRATO
   - Natureza jurídica: [extraia do objeto + cite cláusula]
   - Legislação mencionada: [liste todas as leis/normas citadas + cite onde aparecem]
   - Foro/Jurisdição: [transcreva a cláusula de foro, ou "Não consta no contrato."]

2. PARTES CONTRATANTES
   - Contratante: [nome completo, CNPJ, endereço e representante legal + cite seção]
   - Contratado: [nome completo, CNPJ, endereço e representante legal + cite seção]

3. OBJETO CONTRATUAL
   - Descrição completa: [transcreva ou resuma fielmente + cite cláusula]
   - Restrições/condicionantes: [liste qualquer limitação + cite cláusula]

4. OBRIGAÇÕES PRINCIPAIS
   Do Contratante (cite cada obrigação com sua cláusula):
   Do Contratado (cite cada obrigação com sua cláusula):

5. PRAZOS E VIGÊNCIA
   - Vigência do contrato: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Prazo de mobilização: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Outros prazos relevantes: [liste + cite cada cláusula]

6. VALORES E PAGAMENTO
   - Valor total do contrato: [valor exato + cite cláusula, ou "Não consta no contrato."]
   - Forma de pagamento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Reajuste: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

7. PENALIDADES E RESCISÃO
   - Multas/penalidades: [transcreva valores/percentuais + cite cláusula, ou "Não consta no contrato."]
   - Hipóteses de rescisão: [liste + cite cláusula, ou "Não consta no contrato."]

8. RISCOS JURÍDICOS IDENTIFICADOS
   Para cada risco: descrição, trecho de origem [Cláusula X], nível ALTO/MÉDIO/BAIXO.

9. PONTOS SEM INFORMAÇÃO NO CONTRATO
   Liste todos os campos não encontrados no texto.

════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um assistente jurídico especializado em contratos.

REGRAS:
1. Responda SOMENTE com base no texto do contrato fornecido abaixo.
2. Para cada informação, cite exatamente: [Cláusula X] ou [Item Y.Z].
3. Se a resposta NÃO estiver no contrato: "Essa informação não consta no contrato analisado."
4. NUNCA especule. Seja direto e objetivo.

CONTRATO:
{contexto}

PERGUNTA:
{pergunta}

Responda citando a cláusula exata de cada informação."""
    },

    "suprimentos": {
        "nome": "Suprimentos",
        "icon": "package",
        "cor": "#10b981",
        "resumo": """Você é um especialista em gestão de suprimentos e compras.

════════════════════════════════════════════
REGRAS ABSOLUTAS — LEIA ANTES DE COMEÇAR
════════════════════════════════════════════
1. Extraia SOMENTE informações que estejam literalmente escritas no contrato abaixo.
2. Após cada informação, indique entre colchetes a origem exata: [Cláusula X], [Item Y.Z], [Cabeçalho], etc.
3. Se uma informação NÃO estiver no contrato, escreva: "Não consta no contrato."
4. NUNCA especule ou remeta a anexos sem transcrever o que está escrito.

════════════════════════════════════════════
ESTRUTURA OBRIGATÓRIA DO RESUMO
════════════════════════════════════════════

ANÁLISE DE SUPRIMENTOS E COMPRAS
════════════════════════════════════════════

1. INFORMAÇÕES DO FORNECEDOR
   - Razão Social: [nome completo + cite seção]
   - CNPJ(s): [número(s) + cite seção]
   - Endereço: [conforme contrato + cite seção, ou "Não consta no contrato."]
   - Contato Comercial: [nome, e-mail, telefone + cite seção, ou "Não consta no contrato."]

2. ESPECIFICAÇÃO DO FORNECIMENTO
   Para CADA produto/serviço mencionado:
   - Descrição: [transcreva + cite cláusula]
   - Quantidade/Volume: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Padrões de qualidade/normas exigidas: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

3. CONDIÇÕES COMERCIAIS
   - Preço unitário: [valor exato + cite cláusula, ou "Não consta no contrato."]
   - Valor total: [valor exato + cite cláusula, ou "Não consta no contrato."]
   - Frete (CIF/FOB): [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Forma de pagamento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Prazo de pagamento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Política de reajuste: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

4. LOGÍSTICA E ENTREGA
   - Lead time / Prazo de mobilização: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Prazo de implantação: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Local de entrega/execução: [endereço completo + cite cláusula, ou "Não consta no contrato."]
   - Responsabilidade pelo transporte: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

5. GARANTIAS E QUALIDADE
   - Prazo de garantia: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Escopo da garantia: [o que está coberto + cite cláusula, ou "Não consta no contrato."]
   - Certificações exigidas: [liste + cite cláusula, ou "Não consta no contrato."]

6. RISCOS DE SUPRIMENTOS
   Para cada risco: descrição, trecho de origem [Cláusula X], impacto operacional/financeiro.

7. PONTOS SEM INFORMAÇÃO NO CONTRATO
   Liste todos os campos não encontrados no texto.

════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um especialista em compras e gestão de suprimentos.

REGRAS:
1. Responda SOMENTE com base no texto do contrato fornecido abaixo.
2. Para cada informação, cite exatamente: [Cláusula X] ou [Item Y.Z].
3. Se a resposta NÃO estiver no contrato: "Essa informação não consta no contrato analisado."
4. NUNCA especule. Use linguagem simples e objetiva.

CONTRATO:
{contexto}

PERGUNTA:
{pergunta}

Responda citando a cláusula ou item exato de cada informação."""
    },

    "gestaocontratos": {
        "nome": "Gestão de Contratos",
        "icon": "folder-kanban",
        "cor": "#f59e0b",
        "resumo": """Você é um especialista em gestão operacional de contratos.

════════════════════════════════════════════
REGRAS ABSOLUTAS — LEIA ANTES DE COMEÇAR
════════════════════════════════════════════
1. Extraia SOMENTE informações que estejam literalmente escritas no contrato abaixo.
2. Após cada informação, indique entre colchetes a origem exata: [Cláusula X], [Item Y.Z], [Alínea 'a'], etc.
3. Se uma informação NÃO estiver no contrato, escreva: "Não consta no contrato."
4. Use linguagem clara e objetiva para que o gestor saiba exatamente o que fazer.

════════════════════════════════════════════
ESTRUTURA OBRIGATÓRIA DO RESUMO
════════════════════════════════════════════

ANÁLISE DE GESTÃO OPERACIONAL
════════════════════════════════════════════

1. RESUMO DO ESCOPO OPERACIONAL
   Liste cada atividade prevista no contrato [cite cláusula/item]:
   - Local de execução: [endereço completo + cite cláusula, ou "Não consta no contrato."]
   - Horário de atendimento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

2. MÃO DE OBRA E EQUIPE
   - Quantitativo exigido: [número de pessoas + cite cláusula, ou "Não consta no contrato."]
   - Qualificações obrigatórias (cursos, NRs, habilitações): [liste + cite cláusula, ou "Não consta no contrato."]
   - Uniformes: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - EPIs obrigatórios: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Benefícios exigidos: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

3. MATERIAIS, INSUMOS E EQUIPAMENTOS
   Para cada item: [item] — responsável: [contratante/contratada] [cite cláusula]
   - Responsabilidade por manutenção: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

4. NÍVEIS DE SERVIÇO (SLA) E FREQUÊNCIAS
   - Frequência de cada atividade: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Tempo de resposta/atendimento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Relatórios obrigatórios: [liste + cite cláusula, ou "Não consta no contrato."]
   - KPIs: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

5. PENALIDADES, GLOSAS E MULTAS
   Para cada penalidade: hipótese [cite cláusula], valor/percentual, reincidência.

6. CRONOGRAMA E PRAZOS
   - Data de início: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Prazo de mobilização: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Vigência total: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Marcos intermediários: [liste + cite cada cláusula]

7. RESPONSABILIDADES ESPECIAIS E VEDAÇÕES
   - O que a contratada NÃO pode fazer: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Sigilo/confidencialidade: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Outras responsabilidades: [conforme contrato + cite cláusula]

8. PONTOS SEM INFORMAÇÃO NO CONTRATO
   Liste todos os campos não encontrados no texto.

════════════════════════════════════════════

CONTRATO A ANALISAR:
{texto}""",

        "perguntas": """Você é um especialista em gestão operacional de contratos.

REGRAS:
1. Responda SOMENTE com base no texto do contrato fornecido abaixo.
2. Para cada informação, cite exatamente: [Cláusula X], [Item Y.Z] ou [Alínea 'a'].
3. Se a resposta NÃO estiver no contrato: "Essa informação não consta no contrato analisado."
4. NUNCA especule. Use linguagem simples e prática.

CONTRATO:
{contexto}

PERGUNTA:
{pergunta}

Responda de forma direta e prática, citando a cláusula ou item exato."""
    }
}

# ════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ════════════════════════════════════════════════════════════
Base         = declarative_base()
pwd_context  = CryptContext(schemes=["bcrypt"], deprecated="auto")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

user_role_association = Table(
    'user_role_association', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id',  ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id',  ondelete='CASCADE'), primary_key=True)
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

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
    can_see         = relationship(
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

class UserVisibilityPermission(Base):
    __tablename__ = 'user_visibility_permissions'
    id          = Column(Integer, primary_key=True, index=True)
    viewer_id   = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    target_id   = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    perm_type   = Column(String,  default='user')
    sector_slug = Column(String,  nullable=True)
    created_at  = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    viewer      = relationship("User", foreign_keys=[viewer_id], back_populates="can_see")
    target      = relationship("User", foreign_keys=[target_id])

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
    target_ids:   List[int] = []
    sector_slugs: List[str] = []

# ════════════════════════════════════════════════════════════
# CRIAÇÃO DO BANCO + MIGRAÇÃO
# ════════════════════════════════════════════════════════════
Base.metadata.create_all(bind=engine)
logger.info("✅ Tabelas verificadas")

def migrar_banco():
    db_path = DATABASE_URL.replace("sqlite:///", "")
    try:
        conn   = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(roles)")
        if "description" not in [r[1] for r in cursor.fetchall()]:
            cursor.execute("ALTER TABLE roles ADD COLUMN description TEXT DEFAULT ''")
            conn.commit()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_visibility_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                target_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                perm_type TEXT DEFAULT 'user',
                sector_slug TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        conn.commit()
        cursor.execute("PRAGMA table_info(user_visibility_permissions)")
        cols = [r[1] for r in cursor.fetchall()]
        if "perm_type" not in cols:
            cursor.execute("ALTER TABLE user_visibility_permissions ADD COLUMN perm_type TEXT DEFAULT 'user'")
            conn.commit()
        if "sector_slug" not in cols:
            cursor.execute("ALTER TABLE user_visibility_permissions ADD COLUMN sector_slug TEXT")
            conn.commit()
        conn.close()
        logger.info("✅ Migração concluída")
    except Exception as e:
        logger.warning(f"⚠️ Migração: {e}")

migrar_banco()

def create_default_roles_and_admin():
    db = SessionLocal()
    try:
        setores_padrao = [
            ("Admin",               "Acesso administrativo completo"),
            ("Jurídico",            "Análise jurídica de contratos"),
            ("Suprimentos",         "Gestão de compras e fornecedores"),
            ("Gestão de Contratos", "Gestão operacional de contratos"),
        ]
        for nome, desc in setores_padrao:
            if not db.query(Role).filter(Role.name == nome).first():
                db.add(Role(name=nome, description=desc))
        db.commit()

        admin_username = "admin@opersan.com.br"
        if not db.query(User).filter(User.username == admin_username).first():
            admin_role = db.query(Role).filter(Role.name == "Admin").first()
            u = User(
                username        = admin_username,
                name            = "Administrador",
                hashed_password = hash_password("admin123"),
                role            = 'admin'
            )
            if admin_role:
                u.roles.append(admin_role)
            db.add(u)
            db.commit()
            logger.info("✅ Admin criado")
    except Exception as e:
        logger.error(f"❌ Dados iniciais: {e}")
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
# AUTENTICAÇÃO
# ════════════════════════════════════════════════════════════
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Token não fornecido",
                            headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuário desativado")
    return user

async def get_current_admin_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Session = Depends(get_db)
) -> User:
    user = await get_current_user(token, db)
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Requer permissão de administrador.")
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

def formatar_nome_usuario(user: User) -> str:
    raw = user.name or user.username or ""
    if "@" in raw:
        raw = raw.split("@")[0]
    return " ".join(
        p.capitalize() for p in raw.replace(".", " ").replace("_", " ").replace("-", " ").split()
    ) or "Usuário"

def avatar_color(user_id: int) -> str:
    palette = ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#14b8a6"]
    return palette[user_id % len(palette)]

def get_iniciais(nome: str) -> str:
    partes = nome.strip().split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[-1][0]).upper()
    return nome[:2].upper() if nome else "??"

def is_admin_user(user: User) -> bool:
    return (user.role.lower() == "admin" or
            any(r.name.lower() == "admin" for r in user.roles))

def get_setores_permitidos(user: User) -> List[str]:
    if is_admin_user(user):
        return list(PROMPTS_SETORES.keys())
    setores = []
    mapa = {
        "juridico":          "juridico",
        "jurídico":          "juridico",
        "suprimentos":       "suprimentos",
        "gestaocontratos":   "gestaocontratos",
        "gestãodecontratos": "gestaocontratos",
    }
    for role in user.roles:
        slug = role.name.lower().replace("ã","a").replace("ê","e").replace("ç","c").replace(" ","")
        mapped = mapa.get(slug) or mapa.get(role.name.lower())
        if mapped and mapped not in setores:
            setores.append(mapped)
    return list(set(setores)) or ["juridico"]

# ════════════════════════════════════════════════════════════
# EXTRAÇÃO DE PDF — 3 CAMADAS DE FALLBACK
# ════════════════════════════════════════════════════════════
def _extrair_com_pymupdf(conteudo: bytes) -> str:
    doc     = fitz.open(stream=conteudo, filetype="pdf")
    paginas = []
    for pagina in doc:
        texto = pagina.get_text("text")
        if texto.strip():
            paginas.append(texto)
        else:
            blocos = pagina.get_text("blocks")
            t = "\n".join(b[4] for b in blocos if b[4].strip())
            if t.strip():
                paginas.append(t)
    doc.close()
    return "\n\n".join(paginas)

def _extrair_com_pdfplumber(conteudo: bytes) -> str:
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        paginas = []
        for p in pdf.pages:
            t = p.extract_text()
            if t and t.strip():
                paginas.append(t)
        return "\n\n".join(paginas)

def _extrair_com_pypdf(conteudo: bytes) -> str:
    leitor  = PdfReader(io.BytesIO(conteudo))
    paginas = []
    for p in leitor.pages:
        t = p.extract_text()
        if t and t.strip():
            paginas.append(t)
    return "\n\n".join(paginas)

def extrair_texto_pdf(conteudo: bytes) -> str:
    erros = []
    if PYMUPDF_DISPONIVEL:
        try:
            t = _extrair_com_pymupdf(conteudo)
            if t and len(t.strip()) >= 50:
                logger.info(f"✅ pymupdf: {len(t)} chars")
                return t
            erros.append("pymupdf: insuficiente")
        except Exception as e:
            erros.append(f"pymupdf: {str(e)[:80]}")

    if PDFPLUMBER_DISPONIVEL:
        try:
            t = _extrair_com_pdfplumber(conteudo)
            if t and len(t.strip()) >= 50:
                logger.info(f"✅ pdfplumber: {len(t)} chars")
                return t
            erros.append("pdfplumber: insuficiente")
        except Exception as e:
            erros.append(f"pdfplumber: {str(e)[:80]}")

    try:
        t = _extrair_com_pypdf(conteudo)
        if t and len(t.strip()) >= 50:
            logger.info(f"✅ pypdf: {len(t)} chars")
            return t
        erros.append("pypdf: insuficiente")
    except Exception as e:
        erros.append(f"pypdf: {str(e)[:80]}")

    logger.error(f"❌ Todos falharam: {erros}")
    raise HTTPException(
        status_code=400,
        detail=(
            "Não foi possível extrair texto deste PDF. "
            "Possíveis causas: (1) PDF é imagem escaneada sem texto selecionável, "
            "(2) PDF protegido contra cópia, (3) PDF corrompido. "
            "Tente Ctrl+A no PDF e verifique se o texto é selecionável."
        )
    )

# ════════════════════════════════════════════════════════════
# PROCESSAMENTO INTELIGENTE POR CHUNKS
#
# ESTRATÉGIA DE 3 FASES:
#
#  FASE 0 — DIRETO (contratos ≤ LIMITE_DIRETO chars)
#    Contrato pequeno → uma única chamada ao Gemini com o prompt
#    completo do setor. Mais rápido e mais preciso.
#
#  FASE 1 — PRÉ-ANÁLISE POR CHUNK (contratos grandes)
#    O texto é dividido em partes de CHUNK_SIZE chars com sobreposição
#    de CHUNK_OVERLAP. Cada parte é enviada ao Gemini com um prompt
#    de extração bruta (sem formatar relatório final). O objetivo é
#    extrair TODOS os dados relevantes de cada trecho.
#    Retry automático em caso de erro 429/503.
#
#  FASE 2 — CONSOLIDAÇÃO FINAL
#    As pré-análises de todos os chunks são reunidas e enviadas numa
#    segunda chamada ao Gemini, que produz o relatório final estruturado
#    no formato correto do setor. Ele sabe que está consolidando dados
#    de um contrato longo, então não repete informações.
#
#  FALLBACK — Se a consolidação falhar, retorna as pré-análises brutas
#    concatenadas para que o usuário não perca o trabalho.
#
# PARÂMETROS:
#  CHUNK_SIZE    = 6000   chars por pedaço enviado ao Gemini
#  CHUNK_OVERLAP = 400    chars de sobreposição entre chunks
#  LIMITE_DIRETO = 5500   chars — acima disso ativa o modo chunks
#  MAX_CHUNKS    = 12     limite de segurança (evita cota excessiva)
# ════════════════════════════════════════════════════════════

CHUNK_SIZE    = 9000   # maior = menos chunks = menos chamadas à API
CHUNK_OVERLAP = 300    # sobreposição suficiente sem desperdiçar tokens
LIMITE_DIRETO = 8500   # contratos menores que isso → análise direta
MAX_CHUNKS    = 6      # máximo 6 chunks → no máximo 7 chamadas total
PAUSA_CHUNKS  = 4      # segundos entre chamadas para não estourar cota


def _dividir_em_chunks(texto: str) -> list[str]:
    """
    Divide o texto em chunks com sobreposição.
    Prioriza pontos de quebra naturais (parágrafo, ponto final)
    para não cortar cláusulas no meio.
    """
    chunks  = []
    inicio  = 0
    tamanho = len(texto)

    while inicio < tamanho:
        fim = min(inicio + CHUNK_SIZE, tamanho)

        if fim < tamanho:
            # Tenta quebrar em parágrafo duplo
            quebra = texto.rfind("\n\n", inicio + CHUNK_SIZE // 2, fim)
            if quebra == -1:
                # Tenta parágrafo simples
                quebra = texto.rfind("\n", inicio + CHUNK_SIZE // 2, fim)
            if quebra == -1:
                # Tenta ponto final
                quebra = texto.rfind(". ", inicio + CHUNK_SIZE // 2, fim)
            if quebra != -1:
                fim = quebra + 1

        chunk = texto[inicio:fim].strip()
        if chunk:
            chunks.append(chunk)

        if len(chunks) >= MAX_CHUNKS:
            restante = texto[fim:].strip()
            if restante:
                if len(chunks[-1]) + len(restante) < CHUNK_SIZE * 2:
                    chunks[-1] = chunks[-1] + "\n\n" + restante
                else:
                    chunks.append(restante[:CHUNK_SIZE])
            break

        inicio = max(fim - CHUNK_OVERLAP, fim - (fim - inicio) + 1)
        if inicio >= tamanho:
            break

    return [c for c in chunks if c]


def _chamar_gemini(prompt: str, descricao: str = "") -> str:
    """
    Wrapper com retry automático (4 tentativas, espera exponencial agressiva).
    Trata erros 429 (rate limit) e 503 (indisponível).
    """
    if not client or not MODELO_ATIVO:
        raise Exception("IA indisponível")

    for tentativa in range(4):
        try:
            response = client.models.generate_content(
                model    = MODELO_ATIVO,
                contents = prompt
            )
            if response and response.text:
                return limpar_markdown(response.text)
            return ""
        except Exception as e:
            err = str(e)
            recuperavel = "429" in err or "503" in err or "quota" in err.lower() or "overloaded" in err.lower() or "RESOURCE_EXHAUSTED" in err
            if recuperavel and tentativa < 3:
                espera = [8, 20, 45][tentativa]  # 8s, 20s, 45s
                logger.warning(f"⚠️  Gemini [{descricao}] tentativa {tentativa+1}/4 — aguardando {espera}s... (429/quota)")
                time.sleep(espera)
            else:
                logger.error(f"❌ Gemini [{descricao}] falhou: {err[:120]}")
                raise
    return ""


def _pre_analisar_chunk(chunk: str, numero: int, total: int, setor: str) -> str:
    """
    Fase 1: extração bruta dos dados de um chunk.
    Prompt leve — sem estrutura de relatório final.
    """
    prompt = f"""Você está lendo a PARTE {numero} de {total} de um contrato.

TAREFA: Extraia TODOS os dados relevantes desta parte sem omitir nada.
- Identifique: partes contratantes, valores, datas, prazos, obrigações, penalidades, garantias, legislação citada, cláusulas importantes.
- Cite o número de cada cláusula/item encontrado.
- Se uma informação parecer incompleta (continua na próxima parte), registre o que encontrou assim mesmo.
- NÃO formate como relatório final. Apenas liste os dados encontrados de forma clara e organizada.
- NÃO invente informações. Apenas o que está escrito abaixo.

PARTE {numero} DE {total}:
{chunk}

DADOS EXTRAÍDOS:"""

    resultado = _chamar_gemini(prompt, f"chunk {numero}/{total}")
    logger.info(f"  ✅ Chunk {numero}/{total}: {len(resultado)} chars extraídos")
    return resultado or f"[Parte {numero}: nenhum dado extraído]"


def _consolidar_analise(pre_analises: list[str], setor: str, total_chunks: int) -> str:
    """
    Fase 2: consolida todas as pré-análises no relatório final estruturado.
    Usa o template completo do setor, mas alimentado pelas extrações brutas.
    """
    config_setor = PROMPTS_SETORES.get(setor, PROMPTS_SETORES["juridico"])

    blocos = "\n\n".join([
        f"═══ EXTRAÇÃO DA PARTE {i+1}/{total_chunks} ═══\n{pa}"
        for i, pa in enumerate(pre_analises)
        if pa.strip()
    ])

    # Substitui a variável {texto} do template pelo bloco de extrações
    template_setor = config_setor["resumo"].replace(
        "CONTRATO A ANALISAR:\n{texto}",
        f"""ATENÇÃO: Este contrato foi dividido em {total_chunks} partes para análise.
Abaixo estão as extrações de dados de cada parte. Consolide tudo em um único relatório final,
sem repetições, unificando informações que aparecem em múltiplas partes.
Se houver contradições entre partes, registre ambas com nota "Ver partes X e Y".

EXTRAÇÕES BRUTAS DAS {total_chunks} PARTES:
{blocos}"""
    )

    resultado = _chamar_gemini(template_setor, "consolidação final")
    logger.info(f"  ✅ Consolidação final: {len(resultado)} chars")
    return resultado


def gerar_resumo_ia(texto: str, setor: str = "juridico") -> str:
    """
    Análise completa do contrato.
    - Contratos curtos (≤ LIMITE_DIRETO chars): análise direta em 1 chamada.
    - Contratos longos: chunks → pré-análise de cada parte → consolidação final.
    """
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."

    config_setor = PROMPTS_SETORES.get(setor, PROMPTS_SETORES["juridico"])
    tamanho      = len(texto)

    try:
        # ── MODO DIRETO ──────────────────────────────────────────────────
        if tamanho <= LIMITE_DIRETO:
            logger.info(f"📄 Análise direta: {tamanho} chars")
            prompt    = config_setor["resumo"].format(texto=texto)
            resultado = _chamar_gemini(prompt, "análise direta")
            return resultado if resultado else "❌ Erro: resposta vazia da IA."

        # ── MODO CHUNKS ──────────────────────────────────────────────────
        chunks = _dividir_em_chunks(texto)
        logger.info(f"📚 Análise em chunks: {tamanho} chars → {len(chunks)} partes")

        # FASE 1: pré-análise de cada chunk com pausa entre chamadas
        pre_analises = []
        for i, chunk in enumerate(chunks):
            logger.info(f"  🔍 Processando parte {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            try:
                pa = _pre_analisar_chunk(chunk, i + 1, len(chunks), setor)
                pre_analises.append(pa)
                # Pausa entre chunks para não estourar cota da API
                if i < len(chunks) - 1:
                    logger.info(f"  ⏳ Aguardando {PAUSA_CHUNKS}s antes do próximo chunk...")
                    time.sleep(PAUSA_CHUNKS)
            except Exception as e:
                logger.error(f"  ❌ Chunk {i+1} falhou: {e}")
                pre_analises.append(f"[Parte {i+1} não processada: {str(e)[:80]}]")

        # FASE 2: consolidação final
        logger.info(f"  🔗 Consolidando {len(chunks)} partes...")
        try:
            resultado = _consolidar_analise(pre_analises, setor, len(chunks))
            if resultado:
                return resultado
        except Exception as e:
            logger.error(f"  ❌ Consolidação falhou: {e}")

        # FALLBACK: retorna pré-análises brutas se a consolidação falhar
        logger.warning("⚠️  Usando fallback: pré-análises brutas")
        return (
            f"ANÁLISE PARCIAL ({len(chunks)} PARTES DO CONTRATO)\n"
            "═══════════════════════════════════════════\n\n" +
            "\n\n".join([f"═══ PARTE {i+1}/{len(chunks)} ═══\n{pa}"
                         for i, pa in enumerate(pre_analises)])
        )

    except Exception as e:
        logger.error(f"❌ gerar_resumo_ia: {e}")
        return f"❌ Erro ao processar contrato: {str(e)[:200]}"


def gerar_resposta_ia(pergunta: str, contexto: str, setor: str = "juridico") -> str:
    """
    Responde perguntas sobre o contrato.
    - Contexto curto: resposta direta.
    - Contexto longo: triagem → identifica partes relevantes → responde com base nelas.
    """
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."

    config_setor = PROMPTS_SETORES.get(setor, PROMPTS_SETORES["juridico"])

    try:
        # ── CONTEXTO CURTO: resposta direta ─────────────────────────────
        if len(contexto) <= LIMITE_DIRETO:
            prompt    = config_setor["perguntas"].format(pergunta=pergunta, contexto=contexto)
            resultado = _chamar_gemini(prompt, "pergunta direta")
            return resultado if resultado else "❌ Não foi possível gerar uma resposta."

        # ── CONTEXTO LONGO: triagem + resposta focada ────────────────────
        chunks = _dividir_em_chunks(contexto)
        logger.info(f"💬 Pergunta longa: {len(chunks)} chunks, triagem em andamento...")

        # Etapa A: triagem — quais partes são relevantes para esta pergunta
        resumos = "\n".join([
            f"PARTE {i+1}: {chunk[:400].replace(chr(10), ' ')}..."
            for i, chunk in enumerate(chunks)
        ])
        prompt_triagem = f"""Um contrato foi dividido em {len(chunks)} partes.
Pergunta do usuário: "{pergunta}"

Leia os inícios de cada parte abaixo e identifique quais contêm informações para responder a pergunta.
Responda APENAS com os números das partes relevantes separados por vírgula. Exemplo: 1,3,5

{resumos}

Partes relevantes:"""

        triagem = _chamar_gemini(prompt_triagem, "triagem de chunks")

        # Extrai os índices retornados
        partes_relevantes = []
        if triagem:
            nums = re.findall(r'\d+', triagem)
            partes_relevantes = [int(n) - 1 for n in nums if 0 < int(n) <= len(chunks)]
            partes_relevantes = list(dict.fromkeys(partes_relevantes))[:5]

        # Se triagem não retornar nada útil, usa as primeiras 3 partes
        if not partes_relevantes:
            partes_relevantes = list(range(min(3, len(chunks))))

        # Etapa B: resposta com base nas partes relevantes
        contexto_filtrado = "\n\n".join([
            f"═══ PARTE {i+1} DO CONTRATO ═══\n{chunks[i]}"
            for i in partes_relevantes
            if i < len(chunks)
        ])
        prompt_final = config_setor["perguntas"].format(
            pergunta=pergunta,
            contexto=contexto_filtrado
        )
        resultado = _chamar_gemini(prompt_final, "pergunta final")
        return resultado if resultado else "❌ Não foi possível gerar uma resposta."

    except Exception as e:
        logger.error(f"❌ gerar_resposta_ia: {e}")
        return f"❌ Erro ao processar pergunta: {str(e)[:200]}"


# ════════════════════════════════════════════════════════════
# ENDPOINTS — AUTENTICAÇÃO
# ════════════════════════════════════════════════════════════

@app.post("/token", tags=["Autenticação"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db:        Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
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
        "roles":    [{"id": r.id, "name": r.name} for r in current_user.roles]
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS — ADMINISTRAÇÃO DE USUÁRIOS
# ════════════════════════════════════════════════════════════

@app.post("/admin/users", response_model=UserOut, tags=["Administração"])
async def create_user(user: UserCreate, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin_user)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail=f"Usuário '{user.username}' já existe")
    new_user = User(username=user.username, name=user.name,
                    hashed_password=hash_password(user.password), role=user.role)
    if user.role_ids:
        new_user.roles = db.query(Role).filter(Role.id.in_(user.role_ids)).all()
    db.add(new_user); db.commit(); db.refresh(new_user)
    return new_user

@app.get("/admin/users", response_model=List[UserOut], tags=["Administração"])
async def list_users(db: Session = Depends(get_db),
                     admin: User = Depends(get_current_admin_user)):
    return db.query(User).all()

@app.delete("/admin/users/{user_id}", tags=["Administração"])
async def delete_user(user_id: int, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Não pode deletar sua própria conta")
    username = user.username
    db.delete(user); db.commit()
    return {"detail": f"Usuário '{username}' deletado"}

@app.put("/admin/users/{user_id}", response_model=UserOut, tags=["Administração"])
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user_data.username:
        db_user.username = user_data.username
    if user_data.password:
        db_user.hashed_password = hash_password(user_data.password)
    if user_data.role_ids is not None:
        db_user.roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
    db.commit(); db.refresh(db_user)
    return db_user

# ════════════════════════════════════════════════════════════
# ENDPOINTS — ADMINISTRAÇÃO DE ROLES
# ════════════════════════════════════════════════════════════

@app.post("/admin/roles", response_model=RoleOut, tags=["Administração"])
async def create_role(role: RoleCreate, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin_user)):
    if db.query(Role).filter(Role.name == role.name).first():
        raise HTTPException(status_code=400, detail=f"Setor '{role.name}' já existe")
    new_role = Role(name=role.name, description=role.description or "")
    db.add(new_role); db.commit(); db.refresh(new_role)
    return new_role

@app.get("/admin/roles", response_model=List[RoleOut], tags=["Administração"])
async def list_roles(db: Session = Depends(get_db),
                     admin: User = Depends(get_current_admin_user)):
    return db.query(Role).all()

@app.put("/admin/roles/{role_id}", response_model=RoleOut, tags=["Administração"])
async def update_role(role_id: int, role_data: RoleUpdate, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin_user)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    if role_data.name is not None:
        if db.query(Role).filter(Role.name == role_data.name, Role.id != role_id).first():
            raise HTTPException(status_code=400, detail=f"Setor '{role_data.name}' já existe")
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    db.commit(); db.refresh(role)
    return role

@app.delete("/admin/roles/{role_id}", tags=["Administração"])
async def delete_role(role_id: int, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin_user)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    name = role.name
    db.delete(role); db.commit()
    return {"detail": f"Setor '{name}' deletado"}

# ════════════════════════════════════════════════════════════
# ENDPOINTS — PERMISSÕES DE VISIBILIDADE
# ════════════════════════════════════════════════════════════

@app.get("/admin/visibility", tags=["Permissões de Visibilidade"])
async def listar_todas_permissoes(db: Session = Depends(get_db),
                                  admin: User = Depends(get_current_admin_user)):
    todos_users = db.query(User).all()
    user_map    = {u.id: u for u in todos_users}
    perms       = db.query(UserVisibilityPermission).all()
    por_viewer: dict = {}
    for p in perms:
        if p.viewer_id not in por_viewer:
            viewer = user_map.get(p.viewer_id)
            if not viewer:
                continue
            nome = formatar_nome_usuario(viewer)
            por_viewer[p.viewer_id] = {
                "viewer_id": p.viewer_id, "viewer_username": viewer.username,
                "viewer_nome": nome, "viewer_iniciais": get_iniciais(nome),
                "viewer_cor": avatar_color(p.viewer_id), "can_see": [], "sectors": [],
            }
        if p.perm_type == "sector" and p.sector_slug:
            por_viewer[p.viewer_id]["sectors"].append(p.sector_slug)
        elif p.perm_type == "user" and p.target_id:
            target = user_map.get(p.target_id)
            if target:
                nome = formatar_nome_usuario(target)
                por_viewer[p.viewer_id]["can_see"].append({
                    "perm_id": p.id, "target_id": p.target_id,
                    "target_username": target.username, "target_nome": nome,
                    "target_iniciais": get_iniciais(nome), "target_cor": avatar_color(p.target_id),
                })
    return {
        "permissoes": list(por_viewer.values()),
        "total_users": len(todos_users),
        "users": [{
            "id": u.id, "username": u.username,
            "nome": formatar_nome_usuario(u),
            "iniciais": get_iniciais(formatar_nome_usuario(u)),
            "cor": avatar_color(u.id),
            "setor": u.roles[0].name if u.roles else "—",
            "is_admin": is_admin_user(u),
        } for u in todos_users]
    }

@app.get("/admin/visibility/{viewer_id}", tags=["Permissões de Visibilidade"])
async def listar_permissoes_viewer(viewer_id: int, db: Session = Depends(get_db),
                                   admin: User = Depends(get_current_admin_user)):
    viewer = db.query(User).filter(User.id == viewer_id).first()
    if not viewer:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    perms   = db.query(UserVisibilityPermission).filter(UserVisibilityPermission.viewer_id == viewer_id).all()
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
                    "perm_id": p.id, "id": target.id, "username": target.username,
                    "nome": nome, "iniciais": get_iniciais(nome), "cor": avatar_color(target.id),
                })
    return {"viewer_id": viewer_id, "can_see": targets, "sectors": sectors}

@app.put("/admin/visibility/{viewer_id}", tags=["Permissões de Visibilidade"])
async def definir_permissoes_viewer(viewer_id: int, body: SetUserVisibilityBody,
                                    db: Session = Depends(get_db),
                                    admin: User = Depends(get_current_admin_user)):
    viewer = db.query(User).filter(User.id == viewer_id).first()
    if not viewer:
        raise HTTPException(status_code=404, detail="Usuário viewer não encontrado")
    if body.target_ids:
        ids_existentes = {t.id for t in db.query(User).filter(User.id.in_(body.target_ids)).all()}
        invalidos      = set(body.target_ids) - ids_existentes
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
        if target_id != viewer_id:
            db.add(UserVisibilityPermission(viewer_id=viewer_id, target_id=target_id,
                                            perm_type="user", sector_slug=None))
    for slug in set(body.sector_slugs):
        if slug in slugs_validos:
            db.add(UserVisibilityPermission(viewer_id=viewer_id, target_id=None,
                                            perm_type="sector", sector_slug=slug))
    db.commit()
    return {"detail": "Permissões atualizadas", "viewer_id": viewer_id,
            "target_ids": list(set(body.target_ids)), "sector_slugs": list(set(body.sector_slugs))}

@app.delete("/admin/visibility/{viewer_id}/{target_id}", tags=["Permissões de Visibilidade"])
async def revogar_permissao(viewer_id: int, target_id: int, db: Session = Depends(get_db),
                            admin: User = Depends(get_current_admin_user)):
    perm = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id,
        UserVisibilityPermission.target_id == target_id,
        UserVisibilityPermission.perm_type == "user"
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permissão não encontrada")
    db.delete(perm); db.commit()
    return {"detail": "Permissão revogada"}

@app.get("/my/visibility", tags=["Permissões de Visibilidade"])
async def minhas_permissoes(db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    perms   = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == current_user.id).all()
    can_see = []
    sectors = []
    for p in perms:
        if p.perm_type == "sector" and p.sector_slug:
            sectors.append(p.sector_slug)
        elif p.perm_type == "user" and p.target_id:
            target = db.query(User).filter(User.id == p.target_id).first()
            if target and target.is_active:
                nome = formatar_nome_usuario(target)
                can_see.append({"id": target.id, "username": target.username,
                                "nome": nome, "iniciais": get_iniciais(nome),
                                "cor": avatar_color(target.id)})
    return {"viewer_id": current_user.id, "can_see": can_see, "sectors": sectors}

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
        logger.info(f"📄 Texto extraído: {len(texto)} chars — iniciando análise [{setor}]")
        resumo   = gerar_resumo_ia(texto, setor)
        novo     = Contract(nome=file.filename, texto=texto, resumo=resumo,
                            setor=setor, user_id=current_user.id)
        db.add(novo); db.commit(); db.refresh(novo)
        db.add(Message(contrato_id=novo.id, autor="ai",
                       texto=f"Análise concluída pelo setor {PROMPTS_SETORES[setor]['nome']}."))
        db.commit()
        return {"id": novo.id, "nome": file.filename, "resumo": resumo,
                "setor": setor, "setor_nome": PROMPTS_SETORES[setor]['nome']}
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
            UserVisibilityPermission.viewer_id == current_user.id).all()
        target_ids_usuario = set()
        slugs_setor        = set()
        for p in perms:
            if p.perm_type == "user" and p.target_id:
                target_ids_usuario.add(p.target_id)
            elif p.perm_type == "sector" and p.sector_slug:
                slugs_setor.add(p.sector_slug)

        if analyst_id:
            if analyst_id != current_user.id and analyst_id not in target_ids_usuario:
                analista_obj = db.query(User).filter(User.id == analyst_id).first()
                if analista_obj:
                    setores_analista = get_setores_permitidos(analista_obj)
                    if not any(s in slugs_setor for s in setores_analista):
                        raise HTTPException(status_code=403,
                                            detail="Sem permissão para contratos deste analista.")
            query = db.query(Contract).filter(
                Contract.user_id.in_([analyst_id]),
                Contract.setor.in_(meus_setores)
            )
            if sector_id and sector_id in meus_setores:
                query = query.filter(Contract.setor == sector_id)
            contratos = query.order_by(Contract.created_at.desc()).all()
        else:
            ids_usuario = target_ids_usuario | {current_user.id}
            conditions  = []
            if ids_usuario:
                conditions.append(and_(Contract.user_id.in_(ids_usuario),
                                       Contract.setor.in_(meus_setores)))
            for slug in slugs_setor:
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
    result    = []
    for c in contratos:
        au = users_map.get(c.user_id)
        if au:
            nome = formatar_nome_usuario(au)
            analista_obj = {"id": au.id, "nome": nome, "iniciais": get_iniciais(nome), "cor": avatar_color(au.id)}
        else:
            analista_obj = {"id": None, "nome": "Desconhecido", "iniciais": "??", "cor": "#475569"}
        is_mine = (c.user_id == current_user.id)
        result.append({
            "id": c.id, "nome": c.nome,
            "data": c.created_at.isoformat() if c.created_at else None,
            "setor": c.setor,
            "setor_nome": PROMPTS_SETORES.get(c.setor, {}).get('nome', c.setor),
            "preview": c.resumo[:200] + "..." if c.resumo and len(c.resumo) > 200 else c.resumo,
            "analista": analista_obj, "is_mine": is_mine,
            "show_analyst": admin or (not is_mine),
        })
    return result

@app.get("/contratos/{contrato_id}", tags=["Contratos"])
async def obter_contrato(contrato_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    contrato = db.query(Contract).filter(Contract.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    admin = is_admin_user(current_user)
    if not admin and contrato.user_id != current_user.id:
        perm_user  = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.target_id == contrato.user_id,
            UserVisibilityPermission.perm_type == "user").first()
        perm_setor = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.perm_type == "sector",
            UserVisibilityPermission.sector_slug == contrato.setor).first()
        if not perm_user and not perm_setor:
            raise HTTPException(status_code=403, detail="Acesso negado a este contrato.")
    mensagens = db.query(Message).filter(Message.contrato_id == contrato_id).order_by(Message.created_at).all()
    au        = db.query(User).filter(User.id == contrato.user_id).first()
    analista  = None
    if au:
        nome     = formatar_nome_usuario(au)
        analista = {"id": au.id, "nome": nome, "iniciais": get_iniciais(nome), "cor": avatar_color(au.id)}
    return {
        "id": contrato.id, "nome": contrato.nome, "resumo": contrato.resumo,
        "setor": contrato.setor,
        "setor_nome": PROMPTS_SETORES.get(contrato.setor, {}).get('nome', contrato.setor),
        "analista": analista,
        "mensagens": [{"id": m.id, "autor": m.autor, "texto": m.texto,
                       "data": m.created_at.isoformat() if m.created_at else None}
                      for m in mensagens]
    }

@app.delete("/contratos/{contrato_id}", tags=["Contratos"])
async def excluir_contrato(contrato_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    contrato = db.query(Contract).filter(Contract.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    if not is_admin_user(current_user) and contrato.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão para excluir este contrato.")
    nome = contrato.nome
    db.query(Message).filter(Message.contrato_id == contrato_id).delete()
    db.delete(contrato); db.commit()
    return {"detail": f"Contrato '{nome}' excluído"}

# ════════════════════════════════════════════════════════════
# ENDPOINT — CHAT
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
        raise HTTPException(status_code=401, detail="Token não fornecido",
                            headers={"WWW-Authenticate": "Bearer"})
    token = auth_header[7:].strip()
    if not token or token in ("null", "undefined", ""):
        raise HTTPException(status_code=401, detail="Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})
    current_user = db.query(User).filter(User.username == token).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado",
                            headers={"WWW-Authenticate": "Bearer"})
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Usuário desativado")

    contrato = None
    if contrato_id:
        contrato = db.query(Contract).filter(Contract.id == contrato_id).first()
    if not contrato:
        contrato = db.query(Contract).filter(
            Contract.user_id == current_user.id).order_by(Contract.created_at.desc()).first()
    if not contrato:
        contrato = db.query(Contract).order_by(Contract.created_at.desc()).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Nenhum contrato encontrado.")

    admin = is_admin_user(current_user)
    if not admin and contrato.user_id != current_user.id:
        perm_user  = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.target_id == contrato.user_id,
            UserVisibilityPermission.perm_type == "user").first()
        perm_setor = db.query(UserVisibilityPermission).filter(
            UserVisibilityPermission.viewer_id == current_user.id,
            UserVisibilityPermission.perm_type == "sector",
            UserVisibilityPermission.sector_slug == contrato.setor).first()
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
        "sistema":  "Analisador de Contratos IA - Opersan",
        "versao":   "4.0.0",
        "status":   "online",
        "ia_disponivel":  MODELO_ATIVO is not None,
        "modelo_ia":      MODELO_ATIVO,
        "chunk_config": {
            "limite_direto": LIMITE_DIRETO,
            "chunk_size":    CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "max_chunks":    MAX_CHUNKS,
        },
        "extratores_pdf": {
            "pymupdf":    PYMUPDF_DISPONIVEL,
            "pdfplumber": PDFPLUMBER_DISPONIVEL,
            "pypdf":      True
        },
        "setores_disponiveis": list(PROMPTS_SETORES.keys()),
    }

@app.get("/health", tags=["Sistema"])
async def health_check():
    return {
        "status":   "healthy",
        "database": "connected",
        "ia":       "available" if MODELO_ATIVO else "unavailable",
        "extratores_pdf": {
            "pymupdf":    PYMUPDF_DISPONIVEL,
            "pdfplumber": PDFPLUMBER_DISPONIVEL,
        }
    }

# ════════════════════════════════════════════════════════════
# EXECUÇÃO
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("🚀 OPERSAN v4.0 — Análise com chunks inteligentes")
    logger.info("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT)