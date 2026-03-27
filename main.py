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
from google.genai import types
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
    version="4.9.0"
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
"gestaodecontratos": {
    "nome": "Gestão de Contratos",
    "icon": "folder-kanban",
    "cor": "#f59e0b",
    "resumo": """Você é um especialista jurídico-operacional em gestão de contratos da empresa Opersan. Sua função é transformar contratos complexos em resumos operacionais precisos, sem distorcer, inferir ou criar nenhuma informação além do que está literalmente escrito no documento.

════════════════════════════════════════════
PASSO 1 — LEIA O DOCUMENTO INTEIRO ANTES DE ESCREVER QUALQUER COISA
════════════════════════════════════════════

Percorra TODAS as páginas do PDF do início ao fim e mapeie internamente:

① ESTRUTURA DO PDF
   • Quantas páginas tem o documento no total
   • Quais são os documentos que compõem o PDF (ex: Quadro Resumo,
     Condições Gerais, Proposta Comercial, Proposta Técnica etc.)
   • Em que página cada documento começa e termina

② LISTA OFICIAL DE ANEXOS
   • Localize a cláusula ou item que lista formalmente os anexos do
     contrato (ex: "Integram este Contrato os seguintes documentos").
     Essa é a lista oficial. Anote o título exato de cada anexo.
   • Se não houver essa cláusula, identifique os anexos pelos
     cabeçalhos das páginas onde começam.
   • ATENÇÃO: documentos internos de um anexo (sub-tabelas,
     sub-seções numeradas como "Anexo I" dentro de uma proposta
     técnica) NÃO são anexos formais do contrato. Não os trate
     como anexos independentes.

③ SEPARAÇÃO ENTRE OBRIGAÇÕES
   • Leia cada cláusula e identifique o sujeito: é a Opersan
     (CONTRATADA) ou o cliente (CONTRATANTE)?
   • Marque mentalmente quais cláusulas/itens pertencem à Opersan
     e quais pertencem ao cliente. Nunca misture.

④ EXCEÇÕES E CONDIÇÕES
   • Identifique toda vez que uma obrigação vem acompanhada de
     condição, ressalva ou exceção (ex: "salvo se...", "desde que...",
     "exceto quando...", "mediante autorização prévia...").
   • Essas exceções são críticas para a operação e devem ser
     incluídas junto ao item correspondente.

⑤ RISCOS FINANCEIROS ADICIONAIS
   • Identifique situações que podem gerar custo além do valor
     mensal contratado (substituição de equipamentos em fim de vida
     útil, serviços extras, multas, rescisão com investimentos
     pendentes, tratamento de efluentes fora dos parâmetros, etc.)

════════════════════════════════════════════
PASSO 2 — REGRAS INVIOLÁVEIS DE ESCRITA
════════════════════════════════════════════

✅ SEMPRE:
• Extraia somente o que está literalmente escrito no documento.
• Cite a origem de cada informação: [Cláusula X], [Item Y.Z],
  [Nome real do Anexo – Item Y]. Use sempre o nome/título real
  do documento, exatamente como aparece no contrato.
• Escreva "Opersan" no lugar de "CONTRATADA" e o nome real do
  cliente no lugar de "CONTRATANTE" em todo o resumo.
• Quando uma obrigação tiver exceção ou condição relevante para
  a operação, inclua a exceção no mesmo item, logo após a
  obrigação, entre parênteses ou separada por "—".
• Escreva de forma clara e objetiva, como um briefing operacional.

❌ NUNCA:
• Crie, infira, complete ou distorça qualquer informação.
• Misture obrigações da Opersan com obrigações do cliente.
• Cite um anexo com nome diferente do título real no documento.
• Trate um sub-documento interno de um anexo como se fosse um
  anexo formal do contrato.
• Escreva "não consta", "não especificado" ou "não encontrado".
  Se o dado não existe no contrato, omita o campo completamente.
• Repita o mesmo item mais de uma vez.
• Continue escrevendo após o marcador ═══FIM═══.
• Crie seções com títulos como "Informações não encontradas",
  "Pontos sem informação" ou similares.
• Use letras (a, b, c) como marcadores de lista — use traço (—).

════════════════════════════════════════════
PASSO 3 — ESCREVA O RESUMO SEGUINDO ESTA ESTRUTURA EXATA
════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CABEÇALHO DO CONTRATO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nome do Contrato : [título ou objeto resumido + referência]
Cliente          : [nome completo do cliente + referência]
Vigência         : [data de início e término + referência]
Endereço         : [local de prestação dos serviços + referência]
Contato cliente  : [nome, e-mail e telefone do responsável + ref.]
Contato Opersan  : [nome, e-mail e telefone + referência]
Valor mensal     : [valor fixo e variável se houver + referência]
Reajuste         : [índice, periodicidade e data-base + referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. OBJETO DO CONTRATO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Descrição exata do que foi contratado, conforme o contrato.
 Inclua referência ao final.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. OBRIGAÇÕES DA OPERSAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ REGRA ABSOLUTA: inclua nesta seção SOMENTE itens em que o
sujeito da obrigação é a Opersan (CONTRATADA). Para cada item,
verifique: quem deve cumprir isso? Se for o cliente, mova para
a seção 3. Nunca inclua aqui obrigações do cliente.

Fontes a consultar:
— Cláusulas/itens de obrigações da CONTRATADA (bloco formal)
— Cláusulas espalhadas ao longo do contrato que impõem obrigações
  à Opersan (sobre investimentos, manutenção, relatórios,
  paralisações, licenças, qualidade dos serviços etc.)
— Seções de responsabilidades da Opersan nos anexos

Organize por área quando o volume justificar:

OPERAÇÃO E MANUTENÇÃO
— [obrigação exatamente como consta, com exceção se houver]
  [referência]

RELATÓRIOS E MONITORAMENTO
— [obrigação + referência]

MÃO DE OBRA E RH
— [obrigação + referência]

PRODUTOS QUÍMICOS E INSUMOS
— [obrigação + referência]

SEGURANÇA E MEIO AMBIENTE
— [obrigação + referência]

LICENÇAS E DOCUMENTAÇÃO
— [obrigação + referência]

[Use somente as áreas que existirem no contrato. Não crie áreas
 sem conteúdo. Se o contrato não tiver essa separação natural,
 liste tudo em sequência sem subtítulos de área.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. OBRIGAÇÕES DO CLIENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ REGRA ABSOLUTA: inclua nesta seção SOMENTE itens em que o
sujeito da obrigação é o cliente (CONTRATANTE). Para cada item,
verifique: quem deve cumprir isso? Se for a Opersan, mova para
a seção 2. Nunca inclua aqui obrigações da Opersan.

Fontes a consultar:
— Cláusulas/itens de obrigações da CONTRATANTE (bloco formal)
— Cláusulas espalhadas que impõem obrigações ao cliente
  (sobre fornecimento de utilidades, reinvestimentos, licenças
  de responsabilidade do cliente, segurança patrimonial etc.)
— Seções de responsabilidades do cliente nos anexos

— [obrigação exatamente como consta + referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. MÃO DE OBRA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ TÓPICO CRÍTICO — controlar ausências e coberturas é essencial
para evitar glosas e descumprimento contratual.
Cite somente o que está escrito. Cite a referência correta de
cada item (não cite uma cláusula de uniforme para descrever cargo).

Cargos e funções    : [liste cada cargo/função] [referência]
Quantidade por cargo: [ex: 02 operadores, 01 técnico] [referência]
Escala e frequência : [ex: 12x36, visitas mensais] [referência]
Uniformes e EPIs    : [conforme contrato] [referência]
Benefícios exigidos : [transporte, refeição, saúde, insalubridade,
                       documentos — somente o que consta] [ref.]
Substituição        : [prazo e condições para substituição de
                       profissional, se constar] [referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. PRODUTOS QUÍMICOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Responsável pelo fornecimento: [Opersan ou cliente] [referência]

Produto               | Quantidade máxima/mês | Referência
[Nome do produto]     | [qtd + unidade]       | [ref.]
[repita para cada produto listado no contrato ou nos anexos]

⚠️ Não utilizar produtos diferentes dos previstos no contrato.
Consumo acima do previsto gera impacto financeiro e requer
autorização prévia.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. O QUE ESTÁ FORA DO ESCOPO DA OPERSAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Esses itens NÃO são responsabilidade da Opersan. Qualquer
solicitação nesse sentido deve ser tratada como escopo adicional,
sujeito a negociação comercial separada.

[A lista de exclusões geralmente está nos anexos — proposta
 técnica ou similar. Leia todas as páginas do anexo para não
 omitir nenhum item.]

— [item excluído exatamente como consta] [referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. PRAZOS E CRONOGRAMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Liste somente os prazos que existem no contrato]

Início dos serviços          : [+ referência]
Prazo de mobilização         : [+ referência]
Marcos intermediários        : [etapa — prazo — referência]
Vigência total               : [+ referência]
Rescisão sem justa causa     : [aviso prévio exigido + referência]
Reajuste                     : [índice, periodicidade + referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. RELATÓRIOS OBRIGATÓRIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Se o contrato tiver um Rol de Relatórios ou seção específica,
 detalhe cada relatório. Se não tiver, extraia das cláusulas.]

Relatório              | Frequência | Conteúdo resumido | Ref.
[Nome do relatório]    | [freq.]    | [o que contém]    | [ref.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. PENALIDADES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Liste somente as penalidades que existem no contrato,
 com o valor/percentual exato e a situação que as gera]

Situação: [descrição exata da hipótese]
Penalidade: [valor, percentual ou consequência]
Prazo para regularização: [se houver]
Referência: [cláusula/item]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. VEDAÇÕES E CONFIDENCIALIDADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Inclua SOMENTE vedações cujo sujeito seja a Opersan.
Não inclua vedações ao cliente.

O que a Opersan NÃO pode fazer:
— [vedação exatamente como consta] [referência]

Sigilo e confidencialidade:
— [obrigação de sigilo da Opersan + referência]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
11. SITUAÇÕES DE RISCO FINANCEIRO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Esta seção lista SOMENTE situações que podem gerar custo
além do valor mensal contratado — aquelas que a equipe precisa
conhecer para evitar surpresas financeiras.

NÃO inclua aqui custos já cobertos pelo preço mensal (EPI,
salários, produtos químicos dentro do previsto, relatórios
de rotina). Inclua apenas riscos e custos adicionais reais.

Situação: [descrição da situação]
Responsável pelo custo: [Opersan ou cliente]
Observação: [como tratar — negociação, autorização etc.]
Referência: [cláusula/item]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12. ANEXOS DO CONTRATO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ REGRAS PARA ESTA SEÇÃO:

① Use como referência oficial a cláusula/item do contrato que
  lista os anexos formais (ex: "Integram este Contrato...").
  Se não existir, identifique os anexos pelos cabeçalhos.

② O título de cada anexo deve ser EXATAMENTE como aparece no
  documento — não abrevie, não renomeie, não invente.

③ Documentos internos de um anexo (sub-seções, sub-tabelas,
  itens numerados dentro de uma proposta técnica) NÃO são
  anexos do contrato. Trate-os como conteúdo do anexo pai.

④ Para cada anexo, detalhe o conteúdo com profundidade —
  nunca resuma em uma linha.

⑤ Após o último anexo, escreva ═══FIM═══ e PARE imediatamente.

─────────────────────────────────────────
[TÍTULO EXATO DO ANEXO — conforme consta no documento]
─────────────────────────────────────────
Referência formal : [como está listado no contrato]
Páginas           : [ex: pág. 18 a 25]
Finalidade        : [para que serve este anexo no contrato]

Conteúdo:
[Descreva o conteúdo completo com profundidade. Exemplos:]
— Se for proposta comercial: opções de investimento, valores,
  o que cada opção inclui, tarifa fixa, tarifa variável,
  condições de pagamento, reajuste, validade da proposta.
— Se for proposta técnica: premissas de projeto, equipamentos
  a implantar (nome e quantidade de cada um), equipe prevista
  (cargos e escalas), produtos químicos (nome e quantidade),
  plano de análises internas e externas (tabelas completas),
  responsabilidades da Opersan (item a item), responsabilidades
  do cliente (item a item), limites de bateria, exclusões do
  fornecimento (lista completa), garantias, e todos os
  sub-documentos internos com seu conteúdo resumido.
— Se for rol de relatórios: cada relatório com nome, frequência,
  conteúdo e canal de envio.
— Se for especificação de qualidade: cada tabela com parâmetros,
  unidades, limites e uso a que se destina.
— Se for definição de responsabilidades de manutenção: cada item
  da tabela com descrição e quem é responsável.
— Adapte conforme o tipo de conteúdo encontrado.

O que o gestor deve fazer:
— [ação prática e objetiva baseada no conteúdo deste anexo]

[Repita o bloco acima para CADA anexo formal do contrato]

═══FIM═══""",

    "perguntas": """Você é um especialista jurídico-operacional em gestão de contratos da empresa Opersan.

REGRAS:
1. Responda SOMENTE com base no que está literalmente escrito no
   contrato abaixo, incluindo o corpo e todos os seus anexos.
   Nunca infira, complete ou distorça informações.

2. Cite sempre a origem exata de cada informação:
   — [Cláusula X] ou [Item Y.Z] para o corpo do contrato
   — [Nome exato do Anexo – Item Y] para os anexos
   Use sempre o título real do documento, exatamente como
   aparece no contrato.

3. Escreva "Opersan" no lugar de "CONTRATADA" e o nome real
   do cliente no lugar de "CONTRATANTE".

4. Se a informação não constar no contrato, responda:
   "Essa informação não consta no contrato analisado."

5. Ao responder sobre obrigações, identifique sempre quem é
   o responsável — Opersan ou cliente — verificando o sujeito
   da cláusula antes de responder.

6. Quando a resposta envolver uma regra com exceção ou condição
   relevante (ex: "salvo se...", "exceto quando...", "desde que..."),
   inclua sempre a exceção. Ela pode ser decisiva para a operação.

7. Para equipamentos, produtos químicos e especificações técnicas,
   priorize os dados dos ANEXOS — eles geralmente têm mais detalhe.

CONTRATO:
{contexto}

PERGUNTA:
{pergunta}"""
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
    """
    if setor_slug in PROMPTS_SETORES:
        return PROMPTS_SETORES[setor_slug]

    for key, config in PROMPTS_SETORES.items():
        if key in setor_slug or setor_slug in key:
            logger.info(f"⚡ Setor '{setor_slug}' mapeado para '{key}' por similaridade")
            return config

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
logger.info("✅ Tabelas verificadas")

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
    Retorna lista de slugs de setores que o usuário pode acessar.
    CORRIGIDO v4.9: garante que usuário sempre vê seu próprio setor.
    """
    if is_admin_user(user):
        todos_roles = db.query(Role).filter(Role.name.isnot(None)).all()
        return [_slug_setor(r.name) for r in todos_roles
                if r.name.lower() not in ("admin",)]

    setores = []
    for role in user.roles:
        if role.name.lower() == "admin":
            continue
        slug = _slug_setor(role.name)
        if slug and slug not in setores:
            setores.append(slug)

    # ── NOVO: fallback pelo campo role (string) do usuário ──────────────
    # Garante que se o user.role não foi mapeado via roles[], ainda funciona
    if not setores and user.role and user.role.lower() not in ("admin", "user"):
        slug_role = _slug_setor(user.role)
        if slug_role:
            setores.append(slug_role)

    return setores or ["juridico"]

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
# CONFIGURAÇÃO PADRÃO DO GEMINI
# ════════════════════════════════════════════════════════════
GEMINI_CONFIG = types.GenerateContentConfig(
    temperature=0.1,
    max_output_tokens=8192,
    stop_sequences=["═══FIM═══"]
)

def _chamar_gemini(prompt: str, descricao: str = "") -> str:
    if not client or not MODELO_ATIVO:
        raise Exception("IA indisponível: verifique a GEMINI_API_KEY e o modelo configurado.")
    BACKOFF_RATE_LIMIT   = [10, 30, 60]
    BACKOFF_SERVER_ERROR = [5,  15, 30]
    for tentativa in range(4):
        try:
            inicio   = time.time()
            response = client.models.generate_content(
                model=MODELO_ATIVO,
                contents=prompt,
                config=GEMINI_CONFIG
            )
            duracao  = time.time() - inicio
            logger.info(f"✅ Gemini [{descricao}] respondeu em {duracao:.1f}s")
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


def _chamar_gemini_pdf(pdf_bytes: bytes, prompt: str, descricao: str = "") -> str:
    if not client or not MODELO_ATIVO:
        raise Exception("IA indisponível: verifique a GEMINI_API_KEY e o modelo configurado.")
    BACKOFF_RATE_LIMIT   = [10, 30, 60]
    BACKOFF_SERVER_ERROR = [5,  15, 30]
    for tentativa in range(4):
        try:
            inicio = time.time()
            response = client.models.generate_content(
                model=MODELO_ATIVO,
                contents=[
                    types.Part.from_bytes(
                        data=pdf_bytes,
                        mime_type="application/pdf"
                    ),
                    prompt
                ],
                config=GEMINI_CONFIG
            )
            duracao = time.time() - inicio
            logger.info(f"✅ Gemini PDF [{descricao}] respondeu em {duracao:.1f}s")
            texto_bruto = response.text if response and response.text else ""
            if "═══FIM═══" in texto_bruto:
                texto_bruto = texto_bruto.split("═══FIM═══")[0]
            resultado = limpar_markdown(texto_bruto)
            if not resultado and tentativa < 2:
                logger.warning(f"⚠️ Gemini PDF [{descricao}] resposta vazia — retry {tentativa+1}/4")
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
                logger.warning(f"⚠️ Gemini PDF [{descricao}] tent {tentativa+1}/4 — {espera}s ({motivo})")
                time.sleep(espera)
                continue
            else:
                logger.error(f"❌ Gemini PDF [{descricao}] falhou: {err[:200]}")
                raise
    logger.error(f"❌ Gemini PDF [{descricao}] esgotou tentativas")
    return ""


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
    prompt_resumo = config_setor["resumo"]
    if "{texto}" in prompt_resumo:
        template_setor = prompt_resumo.replace(
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
    else:
        template_setor = prompt_resumo + f"""

ATENÇÃO IMPORTANTE:
- Este contrato foi dividido em {total_chunks} partes para análise.
- Abaixo estão as extrações brutas de cada parte.
- Consolide TUDO em um único relatório final, SEM omitir informações importantes.
- NÃO truncar o relatório — inclua todas as seções mesmo que longas.

EXTRAÇÕES BRUTAS DAS {total_chunks} PARTES DO CONTRATO:
{blocos}

INSTRUÇÕES FINAIS: Produza o relatório completo seguindo EXATAMENTE a estrutura acima."""

    resultado = _chamar_gemini(template_setor, "consolidação final")
    if resultado:
        logger.info(f"  ✅ Consolidação final: {len(resultado)} chars")
    else:
        logger.error("  ❌ Consolidação retornou vazio")
    return resultado


def gerar_resumo_ia(texto: str, setor: str = "juridico",
                    pdf_bytes: Optional[bytes] = None) -> str:
    if not client or not MODELO_ATIVO:
        return "❌ Serviço de IA temporariamente indisponível."

    config_setor = _get_config_setor(setor)
    logger.info(f"📄 Iniciando análise | setor={setor} | pdf_nativo={'sim' if pdf_bytes else 'não'}")

    if pdf_bytes:
        try:
            prompt_resumo = config_setor["resumo"]
            if "CONTRATO A ANALISAR:\n{texto}" in prompt_resumo:
                prompt_resumo = prompt_resumo.replace(
                    "CONTRATO A ANALISAR:\n{texto}",
                    "O contrato completo está anexado acima como arquivo PDF. "
                    "Leia TODAS as páginas, incluindo os anexos nas páginas finais."
                )
            elif "{texto}" in prompt_resumo:
                prompt_resumo = prompt_resumo.replace(
                    "{texto}",
                    "[O contrato está anexado como PDF acima. Leia todas as páginas.]"
                )

            logger.info(f"📎 Enviando PDF nativo ao Gemini ({len(pdf_bytes)//1024}KB)...")
            resultado = _chamar_gemini_pdf(pdf_bytes, prompt_resumo, f"PDF nativo [{setor}]")

            if resultado and len(resultado.strip()) > 200:
                logger.info(f"✅ Análise PDF nativa concluída: {len(resultado)} chars")
                return resultado
            else:
                logger.warning("⚠️ PDF nativo retornou resultado insuficiente — usando fallback texto")
        except Exception as e:
            logger.warning(f"⚠️ PDF nativo falhou ({str(e)[:200]}) — usando fallback texto")

    tamanho = len(texto)
    logger.info(f"📄 Fallback texto: {tamanho} chars")

    try:
        if tamanho <= LIMITE_DIRETO:
            logger.info(f"📄 Análise direta (1 chamada): {tamanho} chars")
            prompt_resumo = config_setor["resumo"]
            if "{texto}" in prompt_resumo:
                prompt = prompt_resumo.format(texto=texto)
            else:
                prompt = prompt_resumo + f"\n\nCONTRATO A ANALISAR:\n{texto}"
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


def _processar_em_background(job_id: str, conteudo: bytes, filename: str,
                              setor: str, user_id: int):
    db = None
    try:
        logger.info(f"[job {job_id[:8]}] Extraindo texto do PDF...")
        texto, erro = extrair_texto_pdf_seguro(conteudo)
        if erro:
            logger.warning(f"[job {job_id[:8]}] Extração texto falhou: {erro}")
            texto = ""

        logger.info(f"[job {job_id[:8]}] {len(texto)} chars extraídos — analisando [{setor}] via PDF nativo")

        resumo = gerar_resumo_ia(texto=texto, setor=setor, pdf_bytes=conteudo)

        if not resumo or resumo.startswith("❌"):
            if not texto:
                raise Exception(erro or resumo or "Não foi possível processar o PDF")
            raise Exception(resumo or "Resposta vazia da IA")

        config_setor = _get_config_setor(setor)
        db = SessionLocal()

        novo = Contract(
            nome=filename,
            texto=texto or f"[Texto não extraível — análise feita via PDF nativo | {filename}]",
            resumo=resumo,
            setor=setor,
            user_id=user_id
        )
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
    role:     Optional[str]       = None   # "admin" | "user"

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

    # ── TOGGLE ADMIN v4.9 ───────────────────────────────────────────────────
    # Atualiza o campo role e sincroniza o role "Admin" na tabela de roles
    if user_data.role is not None:
        novo_role = user_data.role.lower()
        if novo_role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Role deve ser 'admin' ou 'user'")

        # Impede que o admin remova sua própria permissão de admin
        if novo_role != "admin" and db_user.id == current_user.id:
            raise HTTPException(status_code=400,
                                detail="Você não pode remover sua própria permissão de administrador.")

        db_user.role = novo_role

        # Sincroniza o role "Admin" no relacionamento user_roles
        admin_role = db.query(Role).filter(Role.name.ilike("admin")).first()
        if admin_role:
            tem_role_admin = any(r.id == admin_role.id for r in db_user.roles)
            if novo_role == "admin" and not tem_role_admin:
                db_user.roles.append(admin_role)
            elif novo_role != "admin" and tem_role_admin:
                db_user.roles = [r for r in db_user.roles if r.id != admin_role.id]

    if user_data.role_ids is not None:
        roles_novos = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        # Se o usuário é admin, garante que o role Admin permanece na lista
        if db_user.role == "admin":
            admin_role = db.query(Role).filter(Role.name.ilike("admin")).first()
            if admin_role and admin_role not in roles_novos:
                roles_novos.append(admin_role)
        db_user.roles = roles_novos

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
    if body.sector_slugs:
        todos_roles      = db.query(Role).all()
        slugs_validos    = {_slug_setor(r.name) for r in todos_roles
                            if r.name.lower() not in ("admin",)}
        invalidos_setor  = set(body.sector_slugs) - slugs_validos
        if invalidos_setor:
            raise HTTPException(status_code=400,
                                detail=f"Setores inválidos: {list(invalidos_setor)}")
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

    conteudo = await file.read()
    if len(conteudo) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400,
                            detail="Arquivo muito grande. O tamanho máximo permitido é 50MB.")

    texto_teste, erro_pdf = extrair_texto_pdf_seguro(conteudo)
    if erro_pdf and len(conteudo) < 1000:
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

# ════════════════════════════════════════════════════════════
# ✅ ENDPOINT CORRIGIDO v4.9 — /contratos/listar
# CORREÇÃO PRINCIPAL: usuário sempre vê seus próprios contratos
# independente de ter permissões de visibilidade configuradas ou não.
# ════════════════════════════════════════════════════════════
@app.get("/contratos/listar", tags=["Contratos"])
async def listar_contratos(
    analyst_id:   Optional[int] = None,
    sector_id:    Optional[str] = None,
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(get_current_user)
):
    admin        = is_admin_user(current_user)
    meus_setores = get_setores_permitidos(current_user, db)

    logger.info(f"📋 listar_contratos | user={current_user.username} | admin={admin} | setores={meus_setores} | analyst_id={analyst_id} | sector_id={sector_id}")

    if admin:
        query = db.query(Contract)
        if sector_id:
            query = query.filter(Contract.setor == sector_id)
        if analyst_id:
            query = query.filter(Contract.user_id == analyst_id)
        contratos = query.order_by(Contract.created_at.desc()).all()
    else:
        # Busca permissões de visibilidade do usuário
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
            # Visualizando contratos de outro analista específico
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
            conditions = []

            # ✅ CORREÇÃO CRÍTICA v4.9:
            # Regra 1 — sempre inclui contratos PRÓPRIOS do usuário no seu setor
            # (independente de permissões configuradas)
            if meus_setores:
                conditions.append(
                    and_(
                        Contract.user_id == current_user.id,
                        Contract.setor.in_(meus_setores)
                    )
                )

            # Regra 2 — contratos de outros usuários com permissão explícita de usuário
            if target_ids_usuario and meus_setores:
                conditions.append(
                    and_(
                        Contract.user_id.in_(target_ids_usuario),
                        Contract.setor.in_(meus_setores)
                    )
                )

            # Regra 3 — contratos de setores inteiros com permissão de setor
            for slug in slugs_setor:
                conditions.append(Contract.setor == slug)

            if not conditions:
                logger.warning(f"⚠️ Nenhuma condição de busca para user={current_user.username}, setores={meus_setores}")
                contratos = []
            else:
                query = db.query(Contract).filter(or_(*conditions))
                if sector_id:
                    query = query.filter(Contract.setor == sector_id)
                contratos = query.order_by(Contract.created_at.desc()).all()

    logger.info(f"📋 Retornando {len(contratos)} contrato(s) para user={current_user.username}")

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
        "versao":        "4.9.0",
        "status":        "online",
        "ia_disponivel": MODELO_ATIVO is not None,
        "modelo_ia":     MODELO_ATIVO,
        "modo_analise":  "PDF nativo (com fallback texto)",
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
    logger.info("🚀 OPERSAN v4.9 — Biblioteca corrigida | Setores dinâmicos | PDF nativo")
    logger.info("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT)