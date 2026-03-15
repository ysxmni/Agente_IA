import io
import re
import time
import uuid
import sqlite3
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
import logging

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

from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey,
    Table, TIMESTAMP, Text, Boolean, Float, and_, or_
)
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from passlib.context import CryptContext
from pydantic import BaseModel
import datetime
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from google import genai
from google.genai import types  # ✅ AJUSTE 1 — importação necessária para GenerateContentConfig
from dotenv import load_dotenv
import os
import json

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL", "sqlite:///contratos_v2.db")
HOST           = os.getenv("HOST", "0.0.0.0")
PORT           = int(os.getenv("PORT", 8000))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info(f"pymupdf: {PYMUPDF_DISPONIVEL} | pdfplumber: {PDFPLUMBER_DISPONIVEL}")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class UserLogin(BaseModel):
    username: str
    password: str

app = FastAPI(
    title="Analisador de Contratos IA - Sistema Opersan",
    description="Sistema de análise de contratos com IA e gestão multi-setorial",
    version="4.7.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ysxmni.github.io",
        "http://127.0.0.1:5500", "http://localhost:5500",
        "http://127.0.0.1:5501", "http://localhost:5501",
        "http://127.0.0.1:8080", "http://localhost:8080",
        "http://127.0.0.1:1500", "http://localhost:1500",
        "http://127.0.0.1:3000", "http://localhost:3000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY não encontrada no .env!")

MODELOS_PREFERENCIA = [
    'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.0-flash',
    'gemini-flash-lite-latest', 'gemini-flash-latest',
]

client       = None
MODELO_ATIVO = None

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        modelos_disponiveis = [m.name for m in client.models.list()]
        logger.info(f"📋 Modelos disponíveis: {len(modelos_disponiveis)}")
        for modelo in MODELOS_PREFERENCIA:
            if any(modelo in m for m in modelos_disponiveis):
                MODELO_ATIVO = modelo
                logger.info(f"✅ Modelo Gemini selecionado: {modelo}")
                break
    except Exception as list_err:
        logger.warning(f"⚠️  Não foi possível listar modelos ({list_err}). Assumindo: {MODELOS_PREFERENCIA[0]}")
        MODELO_ATIVO = MODELOS_PREFERENCIA[0]
    if not MODELO_ATIVO:
        MODELO_ATIVO = MODELOS_PREFERENCIA[0]
        logger.warning(f"⚠️  Nenhum modelo encontrado. Usando fallback: {MODELO_ATIVO}")
except Exception as e:
    logger.error(f"❌ Gemini: {e}")
    client = None
    MODELO_ATIVO = None

# ════════════════════════════════════════════════════════════
# PROMPTS ESPECIALIZADOS POR SETOR (3 fixos + geração dinâmica)
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
❌ PROIBIÇÕES ABSOLUTAS — NUNCA FAÇA ISSO
════════════════════════════════════════════
❌ NUNCA crie uma seção chamada "Pontos sem informação",
   "Informações não encontradas", "Campos não preenchidos",
   "Riscos identificados", "Informações relevantes"
   ou qualquer variação disso. Se um dado não constar, simplesmente omita.
❌ NUNCA ignore páginas do PDF por serem tabelas, listas ou planilhas.
❌ NUNCA resuma os anexos em uma linha. Cada anexo exige um bloco completo.
❌ NUNCA pare de ler antes da última página do documento.
❌ NUNCA repita o mesmo item mais de uma vez.
❌ NUNCA continue escrevendo após o marcador ═══FIM═══

════════════════════════════════════════════
✅ REGRAS OBRIGATÓRIAS
════════════════════════════════════════════
1. Este PDF contém o contrato principal E seus anexos em sequência,
   podendo ter 30, 50, 70 páginas ou mais. LEIA TODAS SEM EXCEÇÃO.
2. Extraia SOMENTE informações literalmente escritas no documento.
3. Após cada informação, cite a origem: [Cláusula X], [Item Y.Z],
   [Anexo X – Item Y], [Tabela Z do Anexo X].
4. Se um dado não constar no documento, simplesmente NÃO mencione
   aquele campo. Não escreva "não consta" e não crie listas do que falta.
5. Use linguagem clara e objetiva.
6. Ao terminar o item 11, escreva ═══FIM═══ e PARE imediatamente.

════════════════════════════════════════════
⚠️ PASSO OBRIGATÓRIO ANTES DE ESCREVER
════════════════════════════════════════════
Antes de iniciar o resumo, percorra visualmente TODAS as páginas do PDF
e liste internamente (sem escrever para o usuário):
- Número total de páginas
- Onde termina o corpo do contrato
- Título e localização de CADA anexo encontrado
- Quais páginas contêm tabelas, listas de equipamentos,
  planilhas de preços ou especificações técnicas

Somente após essa varredura completa, escreva o resumo abaixo.

════════════════════════════════════════════
RESUMO OPERACIONAL DO CONTRATO
════════════════════════════════════════════

CABEÇALHO
──────────────────────────────────────────
Nome do Contrato : [objeto do contrato + cláusula]
Cliente          : [nome + cláusula]
Vigência         : [início e término + cláusula]
Unidade / Local  : [endereço + cláusula]
Responsável      : [nome/cargo + cláusula]

──────────────────────────────────────────
1. OBJETO DO CONTRATO
──────────────────────────────────────────
[Descrição direta do que foi contratado + cláusula]

──────────────────────────────────────────
2. ESCOPO DOS SERVIÇOS / OBRIGAÇÕES DA EMPRESA
──────────────────────────────────────────
Separe por área técnica quando houver:
- [atividade] — [cláusula/item]

──────────────────────────────────────────
3. OBRIGAÇÕES DO CLIENTE
──────────────────────────────────────────
- [obrigação] — [cláusula/item]

──────────────────────────────────────────
4. MÃO DE OBRA PREVISTA NO CONTRATO 👷
──────────────────────────────────────────
⚠️ TÓPICO CRÍTICO — controlar ausências e coberturas para evitar glosas.

- Cargos / Funções: [liste + cláusula]
- Quantidade por cargo: [+ cláusula]
- Escala / Frequência: [+ cláusula]
- Qualificações obrigatórias (NRs, cursos): [+ cláusula]
- Uniformes e EPIs: [+ cláusula]
- Benefícios exigidos: [+ cláusula]
- Penalidades por ausência: [+ cláusula]

──────────────────────────────────────────
5. PRODUTOS QUÍMICOS 🧪
──────────────────────────────────────────
- Responsável pela aquisição: [Empresa / Cliente + cláusula]
- Produtos previstos (busque também nos anexos):
  → [Nome] | Quantidade: [qtd/período] | Obs: [licença, armazenamento]
  → [repita para cada produto encontrado]

⚠️ Não usar produtos diferentes dos previstos. Consumo acima do
contratado gera impacto financeiro. Autorização prévia obrigatória.

──────────────────────────────────────────
6. SERVIÇOS FORA DO ESCOPO ⚠️
──────────────────────────────────────────
- [item] — [cláusula]

──────────────────────────────────────────
7. PRAZOS E NÍVEIS DE SERVIÇO (SLAs)
──────────────────────────────────────────
- Data de início: [+ cláusula]
- Prazo de mobilização: [+ cláusula]
- Vigência total: [+ cláusula]
- Frequência das atividades: [+ cláusula]
- Tempo de resposta/atendimento: [+ cláusula]
- Relatórios obrigatórios: [liste + cláusula]
- KPIs e indicadores: [+ cláusula]
- Marcos intermediários: [+ cláusula]

──────────────────────────────────────────
8. RESPONSABILIDADE POR CUSTOS ADICIONAIS
──────────────────────────────────────────
- [descrição] | Responsável: [Empresa/Cliente] | [cláusula]

──────────────────────────────────────────
9. PENALIDADES E RISCOS OPERACIONAIS
──────────────────────────────────────────
- Hipótese: [descrição] — [cláusula]
  Valor/Percentual: [valor ou %]
  Reincidência: [conforme contrato]

Vedações (o que a contratada NÃO pode fazer):
- [item] — [cláusula]

Sigilo e confidencialidade:
- [conforme contrato + cláusula]

──────────────────────────────────────────
10. CONTATOS E CANAIS INTERNOS
──────────────────────────────────────────
- [Nome / Cargo / Área] — [responsabilidade] — [cláusula ou anexo]

──────────────────────────────────────────
11. ANEXOS E DOCUMENTOS IMPORTANTES
──────────────────────────────────────────
⚠️ INSTRUÇÃO CRÍTICA:
Você recebeu um PDF com múltiplas páginas. Os ANEXOS estão nas páginas
FINAIS do documento. Volte agora às páginas finais e leia cada anexo
com atenção. Para cada anexo encontrado, preencha OBRIGATORIAMENTE
o modelo abaixo. Nenhum anexo pode ser ignorado ou resumido em uma linha.
Máximo de 10 anexos. Após o último anexo, escreva ═══FIM═══ e PARE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANEXO [número/letra] — [Título exato do anexo]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ Finalidade: [para que serve este anexo no contrato]
→ Páginas: [ex: pág. 45 a 52]
→ Conteúdo detalhado:
   • [Se lista de equipamentos: nome, quantidade, responsável por cada item]
   • [Se tabela de preços: itens e valores]
   • [Se produtos químicos: nome, dosagem, frequência de uso]
   • [Se cronograma: etapas, prazos e responsáveis]
   • [Se especificação técnica: parâmetros, limites, unidades]
   • [Se checklist ou roteiro: todos os pontos listados]
   • [Se memorial descritivo: resumo do que representa]
   • [Se planilha de análises: parâmetros monitorados e frequências]
→ O que o gestor deve fazer com base neste anexo:
   • [ação prática e objetiva]

[Repita o bloco acima para CADA anexo encontrado, sem exceção]

═══FIM═══

CONTRATO A ANALISAR:
{texto}""",

    "perguntas": """Você é um especialista em gestão operacional de contratos.

REGRAS:
1. Responda SOMENTE com base no contrato abaixo, incluindo
   o corpo do contrato E todos os seus anexos.
2. Cite sempre: [Cláusula X], [Item Y.Z] ou [Anexo X – Item Y].
3. Se não encontrar a informação:
   "Essa informação não consta no contrato analisado."
4. NUNCA especule. Linguagem simples e direta.
5. Para equipamentos, produtos químicos e especificações técnicas,
   priorize os dados dos ANEXOS.

CONTRATO:
{contexto}

PERGUNTA:
{pergunta}

Responda citando a cláusula, item ou anexo exato."""
}
}


def _slug_setor(nome: str) -> str:
    """Converte nome de setor em slug (sem acentos, sem espaços, minúsculas)."""
    slug = nome.lower()
    for a, b in [("ã","a"),("â","a"),("á","a"),("à","a"),("ä","a"),
                 ("ê","e"),("é","e"),("è","e"),("ë","e"),
                 ("î","i"),("í","i"),("ì","i"),("ï","i"),
                 ("õ","o"),("ô","o"),("ó","o"),("ò","o"),("ö","o"),
                 ("û","u"),("ú","u"),("ù","u"),("ü","u"),
                 ("ç","c"),("ñ","n")]:
        slug = slug.replace(a, b)
    slug = re.sub(r'[^a-z0-9]', '', slug)
    return slug


def _get_config_setor(setor_slug: str) -> dict:
    """
    Retorna a configuração do setor. Se não existir em PROMPTS_SETORES,
    gera um prompt genérico mas especializado com o nome do setor.
    NUNCA retorna None — garante que qualquer setor criado dinamicamente funciona.
    """
    if setor_slug in PROMPTS_SETORES:
        return PROMPTS_SETORES[setor_slug]

    # Tenta encontrar por slug parcial (ex: "financeiro" encontra "financeiro")
    for key, config in PROMPTS_SETORES.items():
        if key in setor_slug or setor_slug in key:
            logger.info(f"⚡ Setor '{setor_slug}' mapeado para '{key}' por similaridade")
            return config

    # Gera prompt genérico especializado para o setor
    nome_legivel = setor_slug.replace("-", " ").replace("_", " ").title()
    logger.info(f"⚡ Gerando prompt dinâmico para setor: '{setor_slug}' ({nome_legivel})")
    return {
        "nome": nome_legivel,
        "icon": "briefcase",
        "cor":  "#8b5cf6",
        "resumo": f"""Você é um especialista em análise de contratos para o setor de {nome_legivel}.

════════════════════════════════════════════
REGRAS ABSOLUTAS — LEIA ANTES DE COMEÇAR
════════════════════════════════════════════
1. Extraia SOMENTE informações que estejam literalmente escritas no contrato abaixo.
2. Após cada informação, indique entre colchetes a origem exata: [Cláusula X], [Item Y.Z], [Preâmbulo], etc.
3. Se uma informação NÃO estiver no contrato, escreva: "Não consta no contrato."
4. NUNCA especule ou invente informações não presentes no texto.

════════════════════════════════════════════
ESTRUTURA OBRIGATÓRIA DO RESUMO
════════════════════════════════════════════

ANÁLISE DO CONTRATO — SETOR: {nome_legivel.upper()}
════════════════════════════════════════════

1. PARTES CONTRATANTES
   - Contratante: [nome completo, CNPJ, endereço e representante legal + cite seção]
   - Contratado: [nome completo, CNPJ, endereço e representante legal + cite seção]

2. OBJETO DO CONTRATO
   - Descrição completa: [transcreva ou resuma fielmente + cite cláusula]

3. PRAZOS E VIGÊNCIA
   - Vigência: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Prazo de mobilização/início: [transcreva + cite cláusula, ou "Não consta no contrato."]

4. VALORES E CONDIÇÕES FINANCEIRAS
   - Valor total: [valor exato + cite cláusula, ou "Não consta no contrato."]
   - Forma de pagamento: [conforme contrato + cite cláusula, ou "Não consta no contrato."]
   - Reajuste: [conforme contrato + cite cláusula, ou "Não consta no contrato."]

5. OBRIGAÇÕES PRINCIPAIS
   Do Contratante (cite cada obrigação com sua cláusula):
   Do Contratado (cite cada obrigação com sua cláusula):

6. PENALIDADES E RESCISÃO
   - Multas/penalidades: [transcreva + cite cláusula, ou "Não consta no contrato."]
   - Hipóteses de rescisão: [liste + cite cláusula, ou "Não consta no contrato."]

7. INFORMAÇÕES RELEVANTES PARA O SETOR DE {nome_legivel.upper()}
   Liste todos os pontos específicos relevantes para este setor encontrados no contrato [cite cláusula].

8. RISCOS IDENTIFICADOS
   Para cada risco: descrição, trecho de origem [Cláusula X], nível ALTO/MÉDIO/BAIXO.

9. PONTOS SEM INFORMAÇÃO NO CONTRATO
   Liste todos os campos não encontrados no texto.

════════════════════════════════════════════

CONTRATO A ANALISAR:
{{texto}}""",
        "perguntas": f"""Você é um especialista em contratos para o setor de {nome_legivel}.

REGRAS:
1. Responda SOMENTE com base no texto do contrato fornecido abaixo.
2. Para cada informação, cite exatamente: [Cláusula X] ou [Item Y.Z].
3. Se a resposta NÃO estiver no contrato: "Essa informação não consta no contrato analisado."
4. NUNCA especule. Seja direto e objetivo.

CONTRATO:
{{contexto}}

PERGUNTA:
{{pergunta}}

Responda citando a cláusula exata de cada informação."""
    }


# ════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ════════════════════════════════════════════════════════════
Base        = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 60},
        pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800,
    )
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

class AnalysisJob(Base):
    __tablename__ = 'analysis_jobs'
    job_id      = Column(String,  primary_key=True, index=True)
    status      = Column(String,  default='processing')
    result_json = Column(Text,    nullable=True)
    error       = Column(Text,    nullable=True)
    contrato_id = Column(Integer, nullable=True)
    user_id     = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at  = Column(Float,   default=time.time)

Base.metadata.create_all(bind=engine)
logger.info("✅ Tabelas verificadas (incluindo analysis_jobs)")

def migrar_banco():
    if not DATABASE_URL.startswith("sqlite"):
        return
    db_path = DATABASE_URL.replace("sqlite:///", "")
    try:
        conn   = sqlite3.connect(db_path, timeout=60)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        conn.commit()
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
            u = User(username=admin_username, name="Administrador",
                     hashed_password=hash_password("admin123"), role='admin')
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
# OPERAÇÕES DE JOB
# ════════════════════════════════════════════════════════════
def _criar_job(user_id: int) -> str:
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(AnalysisJob(job_id=job_id, status="processing",
                           user_id=user_id, created_at=time.time()))
        db.commit()
    finally:
        db.close()
    return job_id

def _finalizar_job(job_id: str, contrato_id: int, result: dict):
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).first()
        if job:
            job.status      = "done"
            job.result_json = json.dumps(result, ensure_ascii=False)
            job.contrato_id = contrato_id
            db.commit()
    finally:
        db.close()

def _falhar_job(job_id: str, erro: str):
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).first()
        if job:
            job.status = "error"
            job.error  = erro[:2000]
            db.commit()
    finally:
        db.close()

def _ler_job(job_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).first()
        if not job:
            return None
        return {
            "status":      job.status,
            "result":      json.loads(job.result_json) if job.result_json else None,
            "error":       job.error,
            "contrato_id": job.contrato_id,
            "created_at":  job.created_at,
        }
    finally:
        db.close()

def _limpar_jobs_antigos():
    db = SessionLocal()
    try:
        limite = time.time() - 10800
        db.query(AnalysisJob).filter(AnalysisJob.created_at < limite).delete()
        db.commit()
    except Exception:
        pass
    finally:
        db.close()

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

def get_setores_permitidos(user: User, db: Session) -> List[str]:
    """
    Retorna slugs dos setores permitidos para o usuário.
    Para admin: todos os setores do banco.
    Para outros: slugs baseados nos roles do usuário.
    DINÂMICO — não usa lista hardcoded.
    """
    if is_admin_user(user):
        # Admin vê todos os setores existentes no banco
        todos_roles = db.query(Role).filter(
            Role.name.isnot(None)
        ).all()
        return [_slug_setor(r.name) for r in todos_roles
                if r.name.lower() not in ("admin",)]

    setores = []
    for role in user.roles:
        if role.name.lower() == "admin":
            continue
        slug = _slug_setor(role.name)
        if slug and slug not in setores:
            setores.append(slug)
    return setores or [_slug_setor(user.roles[0].name) if user.roles else "juridico"]

# ════════════════════════════════════════════════════════════
# EXTRAÇÃO DE PDF
# ════════════════════════════════════════════════════════════
def _extrair_com_pymupdf(conteudo: bytes) -> str:
    doc = fitz.open(stream=conteudo, filetype="pdf")
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
    leitor = PdfReader(io.BytesIO(conteudo))
    paginas = []
    for p in leitor.pages:
        t = p.extract_text()
        if t and t.strip():
            paginas.append(t)
    return "\n\n".join(paginas)

def extrair_texto_pdf_seguro(conteudo: bytes) -> tuple[str, Optional[str]]:
    erros = []
    if PYMUPDF_DISPONIVEL:
        try:
            t = _extrair_com_pymupdf(conteudo)
            if t and len(t.strip()) >= 50:
                logger.info(f"✅ pymupdf: {len(t)} chars")
                return t, None
            erros.append(f"pymupdf: insuficiente ({len(t.strip())} chars)")
        except Exception as e:
            erros.append(f"pymupdf: {str(e)[:80]}")
    if PDFPLUMBER_DISPONIVEL:
        try:
            t = _extrair_com_pdfplumber(conteudo)
            if t and len(t.strip()) >= 50:
                logger.info(f"✅ pdfplumber: {len(t)} chars")
                return t, None
            erros.append(f"pdfplumber: insuficiente ({len(t.strip())} chars)")
        except Exception as e:
            erros.append(f"pdfplumber: {str(e)[:80]}")
    try:
        t = _extrair_com_pypdf(conteudo)
        if t and len(t.strip()) >= 50:
            logger.info(f"✅ pypdf: {len(t)} chars")
            return t, None
        erros.append(f"pypdf: insuficiente ({len(t.strip())} chars)")
    except Exception as e:
        erros.append(f"pypdf: {str(e)[:80]}")
    msg = (
        "Não foi possível extrair texto deste PDF. "
        "Possíveis causas: (1) PDF é imagem escaneada sem texto selecionável, "
        "(2) PDF protegido contra cópia, (3) PDF corrompido. "
        f"Detalhes: {' | '.join(erros)}"
    )
    logger.error(f"❌ Extração falhou: {erros}")
    return "", msg

def extrair_texto_pdf(conteudo: bytes) -> str:
    texto, erro = extrair_texto_pdf_seguro(conteudo)
    if erro:
        raise HTTPException(status_code=400, detail=erro)
    return texto

# ════════════════════════════════════════════════════════════
# PROCESSAMENTO POR CHUNKS
# ════════════════════════════════════════════════════════════
CHUNK_SIZE    = 50_000
CHUNK_OVERLAP = 300
LIMITE_DIRETO = 60_000
MAX_CHUNKS    = 4

def _dividir_em_chunks(texto: str) -> list[str]:
    chunks  = []
    inicio  = 0
    tamanho = len(texto)
    while inicio < tamanho:
        fim = min(inicio + CHUNK_SIZE, tamanho)
        if fim < tamanho:
            quebra = texto.rfind("\n\n", inicio + CHUNK_SIZE // 2, fim)
            if quebra == -1:
                quebra = texto.rfind("\n", inicio + CHUNK_SIZE // 2, fim)
            if quebra == -1:
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
    if not client or not MODELO_ATIVO:
        raise Exception("IA indisponível: verifique a GEMINI_API_KEY e o modelo configurado.")
    BACKOFF_RATE_LIMIT   = [10, 30, 60]
    BACKOFF_SERVER_ERROR = [5,  15, 30]
    for tentativa in range(4):
        try:
            inicio   = time.time()
            # ✅ AJUSTE 2 — config com temperature, max_output_tokens e stop_sequences
            response = client.models.generate_content(
                model=MODELO_ATIVO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                    stop_sequences=["═══FIM═══"]
                )
            )
            duracao  = time.time() - inicio
            logger.info(f"✅ Gemini [{descricao}] respondeu em {duracao:.1f}s")
            # ✅ AJUSTE 3 — corta tudo após o marcador de fim para evitar loops infinitos
            texto_bruto = response.text if response and response.text else ""
            if "═══FIM═══" in texto_bruto:
                texto_bruto = texto_bruto.split("═══FIM═══")[0]
            resultado = limpar_markdown(texto_bruto)
            if not resultado and tentativa < 2:
                logger.warning(f"⚠️ Gemini [{descricao}] resposta vazia — retry {tentativa+1}/4, aguardando 5s...")
                time.sleep(5)
                continue
            return resultado
        except Exception as e:
            err       = str(e)
            is_rate   = "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err
            is_server = "503" in err or "overloaded" in err.lower() or "unavailable" in err.lower()
            recuperavel = is_rate or is_server
            if recuperavel and tentativa < 3:
                espera = (BACKOFF_RATE_LIMIT if is_rate else BACKOFF_SERVER_ERROR)[tentativa]
                motivo = "rate limit/quota" if is_rate else "servidor sobrecarregado"
                logger.warning(f"⚠️ Gemini [{descricao}] tent {tentativa+1}/4 — {espera}s ({motivo})")
                time.sleep(espera)
                continue
            else:
                logger.error(f"❌ Gemini [{descricao}] falhou: {err[:200]}")
                raise
    logger.error(f"❌ Gemini [{descricao}] esgotou tentativas")
    return ""

def _pre_analisar_chunk(chunk: str, numero: int, total: int, setor: str) -> str:
    prompt = f"""Você está lendo a PARTE {numero} de {total} de um contrato.

TAREFA CRÍTICA: Extraia TODOS os dados relevantes desta parte sem omitir NADA.
- Identifique e liste: partes contratantes, valores, datas, prazos, obrigações, penalidades, garantias, legislação citada, cláusulas importantes, itens de serviço, quantitativos, endereços, CNPJs.
- Cite o número de cada cláusula/item encontrado (ex: [Cláusula 3.1], [Item 2.a]).
- Se uma informação parecer incompleta (continua na próxima parte), registre o que encontrou assim mesmo, indicando "(continua...)".
- NÃO formate como relatório final. Apenas liste os dados encontrados de forma clara.
- NÃO invente informações. SOMENTE o que está escrito no texto abaixo.
- NÃO resuma demais — prefira extrair mais dados do que menos.

PARTE {numero} DE {total}:
{chunk}

DADOS EXTRAÍDOS:"""
    resultado = _chamar_gemini(prompt, f"chunk {numero}/{total}")
    if resultado:
        logger.info(f"  ✅ Chunk {numero}/{total}: {len(resultado)} chars extraídos")
    else:
        logger.warning(f"  ⚠️  Chunk {numero}/{total}: resposta vazia")
    return resultado or f"[Parte {numero}: nenhum dado pôde ser extraído]"

def _consolidar_analise(pre_analises: list[str], setor: str, total_chunks: int) -> str:
    config_setor = _get_config_setor(setor)
    blocos = "\n\n".join([
        f"═══ EXTRAÇÃO DA PARTE {i+1}/{total_chunks} ═══\n{pa}"
        for i, pa in enumerate(pre_analises) if pa.strip()
    ])
    template_setor = config_setor["resumo"].replace(
        "CONTRATO A ANALISAR:\n{texto}",
        f"""ATENÇÃO IMPORTANTE:
- Este contrato foi dividido em {total_chunks} partes para análise.
- Abaixo estão as extrações brutas de cada parte.
- Consolide TUDO em um único relatório final, SEM omitir informações importantes.
- NÃO truncar o relatório — inclua todas as seções mesmo que longas.
- Unifique informações repetidas entre partes sem perder detalhes.
- Se houver contradições entre partes, registre ambas com nota "Verificar partes X e Y".

EXTRAÇÕES BRUTAS DAS {total_chunks} PARTES DO CONTRATO:
{blocos}

INSTRUÇÕES FINAIS: Produza o relatório completo seguindo EXATAMENTE a estrutura acima."""
    )
    resultado = _chamar_gemini(template_setor, "consolidação final")
    if resultado:
        logger.info(f"  ✅ Consolidação final: {len(resultado)} chars")
    else:
        logger.error("  ❌ Consolidação retornou vazio")
    return resultado

def gerar_resumo_ia(texto: str, setor: str = "juridico") -> str:
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."
    config_setor = _get_config_setor(setor)
    tamanho      = len(texto)
    logger.info(f"📄 Iniciando análise: {tamanho} chars | setor={setor}")
    try:
        if tamanho <= LIMITE_DIRETO:
            logger.info(f"📄 Análise direta (1 chamada): {tamanho} chars")
            prompt    = config_setor["resumo"].format(texto=texto)
            resultado = _chamar_gemini(prompt, f"análise direta [{tamanho} chars]")
            if not resultado:
                return "❌ Erro: a IA retornou uma resposta vazia. Tente novamente."
            logger.info(f"✅ Análise direta concluída: {len(resultado)} chars")
            return resultado
        chunks = _dividir_em_chunks(texto)
        logger.info(f"📚 Análise em chunks: {tamanho} chars → {len(chunks)} partes")
        pre_analises = []
        for i, chunk in enumerate(chunks):
            logger.info(f"  🔍 Parte {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            try:
                pa = _pre_analisar_chunk(chunk, i + 1, len(chunks), setor)
                pre_analises.append(pa)
            except Exception as e:
                logger.error(f"  ❌ Chunk {i+1} falhou: {e}")
                pre_analises.append(f"[Parte {i+1} não processada: {str(e)[:200]}]")
        logger.info(f"  🔗 Consolidando {len(chunks)} partes...")
        try:
            resultado = _consolidar_analise(pre_analises, setor, len(chunks))
            if resultado:
                logger.info(f"✅ Chunks concluídos: {len(resultado)} chars")
                return resultado
        except Exception as e:
            logger.error(f"  ❌ Consolidação falhou: {e}")
        logger.warning("⚠️ Usando fallback: pré-análises brutas")
        return (
            f"ANÁLISE PARCIAL ({len(chunks)} PARTES DO CONTRATO)\n"
            "Nota: A consolidação final não foi possível. Dados extraídos de cada parte:\n"
            "═══════════════════════════════════════════\n\n" +
            "\n\n".join([f"═══ PARTE {i+1}/{len(chunks)} ═══\n{pa}" for i, pa in enumerate(pre_analises)])
        )
    except Exception as e:
        logger.error(f"❌ gerar_resumo_ia: {e}")
        return f"❌ Erro ao processar contrato: {str(e)[:500]}"

def gerar_resposta_ia(pergunta: str, contexto: str, setor: str = "juridico") -> str:
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."
    config_setor = _get_config_setor(setor)
    try:
        if len(contexto) <= LIMITE_DIRETO:
            prompt    = config_setor["perguntas"].format(pergunta=pergunta, contexto=contexto)
            resultado = _chamar_gemini(prompt, f"pergunta direta [{len(contexto)} chars]")
            return resultado if resultado else "❌ Não foi possível gerar uma resposta. Tente novamente."
        chunks = _dividir_em_chunks(contexto)
        logger.info(f"💬 Pergunta em contexto longo: {len(chunks)} chunks")
        resumos = "\n".join([
            f"PARTE {i+1}: {chunk[:400].replace(chr(10), ' ')}..."
            for i, chunk in enumerate(chunks)
        ])
        prompt_triagem = f"""Um contrato foi dividido em {len(chunks)} partes.
Pergunta do usuário: "{pergunta}"
Leia os inícios de cada parte e identifique quais contêm informações para responder.
Responda APENAS com os números das partes relevantes separados por vírgula. Exemplo: 1,3,5

{resumos}

Partes relevantes:"""
        triagem = _chamar_gemini(prompt_triagem, "triagem de chunks")
        partes_relevantes = []
        if triagem:
            nums = re.findall(r'\d+', triagem)
            partes_relevantes = [int(n) - 1 for n in nums if 0 < int(n) <= len(chunks)]
            partes_relevantes = list(dict.fromkeys(partes_relevantes))[:5]
        if not partes_relevantes:
            partes_relevantes = list(range(min(3, len(chunks))))
        contexto_filtrado = "\n\n".join([
            f"═══ PARTE {i+1} DO CONTRATO ═══\n{chunks[i]}"
            for i in partes_relevantes if i < len(chunks)
        ])
        prompt_final = config_setor["perguntas"].format(pergunta=pergunta, contexto=contexto_filtrado)
        resultado = _chamar_gemini(prompt_final, "pergunta final")
        return resultado if resultado else "❌ Não foi possível gerar uma resposta. Tente novamente."
    except Exception as e:
        logger.error(f"❌ gerar_resposta_ia: {e}")
        return f"❌ Erro ao processar pergunta: {str(e)[:500]}"

# ════════════════════════════════════════════════════════════
# BACKGROUND JOB
# ════════════════════════════════════════════════════════════
def _processar_em_background(job_id: str, conteudo: bytes, filename: str,
                              setor: str, user_id: int):
    db = None
    try:
        logger.info(f"[job {job_id[:8]}] Extraindo texto do PDF...")
        texto, erro = extrair_texto_pdf_seguro(conteudo)
        if erro:
            raise Exception(erro)
        logger.info(f"[job {job_id[:8]}] {len(texto)} chars extraídos — analisando [{setor}]")
        resumo = gerar_resumo_ia(texto, setor)
        if not resumo or resumo.startswith("❌"):
            raise Exception(resumo or "Resposta vazia da IA")
        config_setor = _get_config_setor(setor)
        db = SessionLocal()
        novo = Contract(nome=filename, texto=texto, resumo=resumo, setor=setor, user_id=user_id)
        db.add(novo)
        db.commit()
        db.refresh(novo)
        db.add(Message(contrato_id=novo.id, autor="ai",
                       texto=f"Análise concluída pelo setor {config_setor['nome']}."))
        db.commit()
        _finalizar_job(job_id, novo.id, {
            "id":         novo.id,
            "nome":       filename,
            "resumo":     resumo,
            "setor":      setor,
            "setor_nome": config_setor['nome']
        })
        logger.info(f"[job {job_id[:8]}] ✅ Concluído — contrato #{novo.id}")
    except Exception as e:
        logger.error(f"[job {job_id[:8]}] ❌ {e}")
        _falhar_job(job_id, str(e)[:2000])
    finally:
        if db is not None:
            db.close()
        try:
            _limpar_jobs_antigos()
        except Exception:
            pass

# ════════════════════════════════════════════════════════════
# PYDANTIC MODELS
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
    perms   = db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id).all()
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

    # ── VALIDAÇÃO DINÂMICA DE SLUGS ──────────────────────────────────────────
    # Obtém todos os roles do banco e converte para slugs válidos (sem hardcode)
    if body.sector_slugs:
        todos_roles      = db.query(Role).all()
        slugs_validos    = {_slug_setor(r.name) for r in todos_roles
                            if r.name.lower() not in ("admin",)}
        invalidos_setor  = set(body.sector_slugs) - slugs_validos
        if invalidos_setor:
            raise HTTPException(status_code=400,
                                detail=f"Setores inválidos: {list(invalidos_setor)}")
    # ─────────────────────────────────────────────────────────────────────────

    db.query(UserVisibilityPermission).filter(
        UserVisibilityPermission.viewer_id == viewer_id
    ).delete(synchronize_session=False)
    for target_id in set(body.target_ids):
        if target_id != viewer_id:
            db.add(UserVisibilityPermission(viewer_id=viewer_id, target_id=target_id,
                                            perm_type="user", sector_slug=None))
    for slug in set(body.sector_slugs):
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
    background_tasks: BackgroundTasks,
    file:             UploadFile = File(...),
    setor:            str        = Form("juridico"),
    db:               Session    = Depends(get_db),
    current_user:     User       = Depends(get_current_user)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são permitidos")

    # Aceita qualquer setor — sem validação hardcoded
    conteudo = await file.read()
    if len(conteudo) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400,
                            detail="Arquivo muito grande. O tamanho máximo permitido é 50MB.")
    _, erro_pdf = extrair_texto_pdf_seguro(conteudo)
    if erro_pdf:
        raise HTTPException(status_code=400, detail=erro_pdf)

    job_id = _criar_job(current_user.id)
    background_tasks.add_task(
        _processar_em_background,
        job_id, conteudo, file.filename, setor, current_user.id
    )
    logger.info(f"🚀 Job {job_id[:8]} iniciado — '{file.filename}' [{setor}] ({len(conteudo)//1024}KB)")
    return {"job_id": job_id, "status": "processing",
            "mensagem": "Análise iniciada. Acompanhe em /job/{job_id}"}

@app.get("/job/{job_id}", tags=["Contratos"])
async def status_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = _ler_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=(
            "Job não encontrado. O servidor reiniciou antes de registrar o job. "
            "Aguarde 30 segundos e tente enviar o arquivo novamente."
        ))
    return {"job_id": job_id, "status": job["status"], "result": job.get("result"),
            "error": job.get("error"), "contrato_id": job.get("contrato_id")}

@app.get("/contratos/listar", tags=["Contratos"])
async def listar_contratos(
    analyst_id:   Optional[int] = None,
    sector_id:    Optional[str] = None,
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(get_current_user)
):
    admin        = is_admin_user(current_user)
    meus_setores = get_setores_permitidos(current_user, db)

    if admin:
        query = db.query(Contract)
        if sector_id:
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
                    setores_analista = get_setores_permitidos(analista_obj, db)
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
            analista_obj = {"id": au.id, "nome": nome, "iniciais": get_iniciais(nome),
                            "cor": avatar_color(au.id)}
        else:
            analista_obj = {"id": None, "nome": "Desconhecido", "iniciais": "??", "cor": "#475569"}
        config_setor = _get_config_setor(c.setor)
        is_mine = (c.user_id == current_user.id)
        result.append({
            "id": c.id, "nome": c.nome,
            "data": c.created_at.isoformat() if c.created_at else None,
            "setor": c.setor,
            "setor_nome": config_setor.get('nome', c.setor),
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
    mensagens = db.query(Message).filter(
        Message.contrato_id == contrato_id).order_by(Message.created_at).all()
    au = db.query(User).filter(User.id == contrato.user_id).first()
    analista = None
    if au:
        nome     = formatar_nome_usuario(au)
        analista = {"id": au.id, "nome": nome, "iniciais": get_iniciais(nome),
                    "cor": avatar_color(au.id)}
    config_setor = _get_config_setor(contrato.setor)
    return {
        "id": contrato.id, "nome": contrato.nome, "resumo": contrato.resumo,
        "setor": contrato.setor,
        "setor_nome": config_setor.get('nome', contrato.setor),
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

    # setor aceito sem validação hardcoded — _get_config_setor gera prompt dinâmico se necessário
    db.add(Message(contrato_id=contrato.id, autor="user", texto=pergunta))
    db.commit()
    resposta_ia = gerar_resposta_ia(pergunta=pergunta, contexto=contrato.texto, setor=setor)
    db.add(Message(contrato_id=contrato.id, autor="ai", texto=resposta_ia))
    db.commit()

    config_setor = _get_config_setor(setor)
    return {
        "resposta":    resposta_ia,
        "pergunta":    pergunta,
        "setor_usado": setor,
        "setor_nome":  config_setor['nome'],
        "contrato_id": contrato.id
    }

# ════════════════════════════════════════════════════════════
# ENDPOINTS DO SISTEMA
# ════════════════════════════════════════════════════════════
@app.get("/", tags=["Sistema"])
async def root():
    return {
        "sistema":       "Analisador de Contratos IA - Opersan",
        "versao":        "4.7.0",
        "status":        "online",
        "ia_disponivel": MODELO_ATIVO is not None,
        "modelo_ia":     MODELO_ATIVO,
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
        "setores_base": list(PROMPTS_SETORES.keys()),
        "setores_dinamicos": True,
    }

@app.get("/ping", tags=["Sistema"])
async def ping():
    return {"pong": True, "ts": time.time()}

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

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("🚀 OPERSAN v4.7 — Setores dinâmicos | prompts gerados automaticamente")
    logger.info("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT)