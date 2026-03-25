from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
from datetime import datetime, date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TITLE        = "Guardiao da Constituicao: Arena Constitucional"
LOCK         = threading.Lock()
RANKING_LIMIT = 50

# ── SUPABASE PERSISTENCIA ─────────────────────────────────────────────────────
# Banco de dados gratuito e confiavel.
# Configure no Render em Environment:
#   SUPABASE_URL = https://SEU-PROJETO.supabase.co
#   SUPABASE_KEY = sua-anon-key
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def _supa(method: str, table: str, data=None, params: str = "") -> list | dict | None:
    """Faz uma requisicao REST para o Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("AVISO: SUPABASE_URL ou SUPABASE_KEY nao configurados.")
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation,resolution=merge-duplicates",
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"Supabase erro {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Supabase erro: {e}")
        return None
# read = seconds to read question before options appear
# answer = seconds to answer after options appear
LEVELS = [
    {"id": 1, "name": "Teoria Constitucional",   "base": 12, "read": 20, "answer": 60},
    {"id": 2, "name": "Direitos Individuais",     "base": 14, "read": 20, "answer": 65},
    {"id": 3, "name": "Remedios Constitucionais", "base": 16, "read": 20, "answer": 70},
    {"id": 4, "name": "Direitos Sociais",         "base": 18, "read": 20, "answer": 75},
    {"id": 5, "name": "Casos Praticos",           "base": 22, "read": 20, "answer": 80},
]

# ── INVESTIGATION MULTIPLAYER ─────────────────────────────────────────────────
INVESTIGATION_ROOMS: dict = {}   # room_id -> room_state
INV_LOCK = threading.Lock()

INVESTIGATION_CASES = [
  {"id":1,"title":"Print Vazado","historia":"Ana Clara, analista administrativa, teve uma conversa privada com uma colega vazada no grupo geral da empresa apos uma discussao interna sobre metas. O conteudo incluia criticas a gestao e comentarios pessoais sobre colegas.","envolvidos":["Ana Clara (vitima)","Juliana (colega)","Supervisor Marcos"],"evidencias":[{"id":"E1","titulo":"Print do grupo","descricao":"Mensagem enviada no grupo: 'Olha o que ela fala da empresa kkkkk' com o print da conversa privada","peso":0.8,"tipo":"digital"},{"id":"E2","titulo":"Conversa privada","descricao":"Historico da conversa: 'Nao concordo com a pressao absurda que estao colocando, isso e assedio mesmo'","peso":0.9,"tipo":"digital"},{"id":"E3","titulo":"Depoimento da vitima","descricao":"Ana Clara declarou: 'Eu nunca autorizei o envio disso para o grupo. Senti violacao total da minha privacidade'","peso":0.7,"tipo":"testemunhal"},{"id":"E4","titulo":"Politica interna","descricao":"Manual de conduta da empresa nao menciona restricoes sobre compartilhamento de conversas privadas","peso":0.3,"tipo":"documental"}],"duvidas":["Foi vazamento ou denuncia de interesse coletivo?","A empresa tem responsabilidade pelo ambiente que criou?"],"resposta":{"violacao":True,"direito":"Privacidade e Intimidade","artigo":"Art. 5º, X","culpado":"Juliana"}},
  {"id":2,"title":"Demissao por Opiniao","historia":"Carlos, analista de marketing, foi demitido dois dias apos postar nas redes sociais criticas a um politico local que era parceiro comercial da empresa. O RH alegou 'desalinhamento institucional e conduta incompativel com os valores da organizacao'.","envolvidos":["Carlos (funcionario)","Empresa X","Diretor de RH"],"evidencias":[{"id":"E1","titulo":"Postagem de Carlos","descricao":"Post publico: 'Esse politico nao representa a populacao, suas politicas sao um desastre para a cidade'","peso":0.6,"tipo":"digital"},{"id":"E2","titulo":"Email de demissao","descricao":"Email do RH: 'Sua conduta publica nao condiz com os valores e alinhamento institucional da empresa'","peso":0.9,"tipo":"documental"},{"id":"E3","titulo":"Historico profissional","descricao":"Carlos tinha 4 anos de empresa com avaliacoes excelentes e nenhuma advertencia anterior","peso":0.7,"tipo":"documental"},{"id":"E4","titulo":"Contrato de trabalho","descricao":"Contrato nao possui clausula sobre manifestacoes politicas nas redes sociais pessoais","peso":0.8,"tipo":"documental"}],"duvidas":["Liberdade de expressao vs imagem corporativa","Demissao foi retaliacao ou justa causa?"],"resposta":{"violacao":True,"direito":"Liberdade de Expressao","artigo":"Art. 5º, IV","culpado":"Empresa X"}},
  {"id":3,"title":"Revista Intima","historia":"Funcionarios de uma fabrica sao obrigados a levantar as roupas e se submeter a inspecao corporal ao sair do turno, como parte de uma politica anti-furto da empresa. Alguns funcionarios protestaram mas foram ameacados de demissao.","envolvidos":["Funcionarios","Empresa Y","Seguranca da empresa"],"evidencias":[{"id":"E1","titulo":"Norma interna","descricao":"Documento interno: 'Todos os funcionarios devem se submeter a revista corporal ao final de cada turno'","peso":0.9,"tipo":"documental"},{"id":"E2","titulo":"Relato coletivo","descricao":"Depoimento: 'Somos obrigados a mostrar o corpo, levantar roupas, e ainda somos filmados durante o processo'","peso":0.95,"tipo":"testemunhal"},{"id":"E3","titulo":"Indice de furtos","descricao":"Relatorio mostra queda de 40% em furtos apos implementacao da politica","peso":0.4,"tipo":"estatistico"},{"id":"E4","titulo":"Sindicato","descricao":"Sindicato registrou 47 queixas formais sobre o procedimento nos ultimos 6 meses","peso":0.7,"tipo":"documental"}],"duvidas":["Seguranca da empresa justifica tal medida?","Havia alternativas menos invasivas?"],"resposta":{"violacao":True,"direito":"Dignidade da Pessoa Humana","artigo":"Art. 5º, III","culpado":"Empresa Y"}},
  {"id":4,"title":"Entrada sem Mandado","historia":"Policiais entraram em uma residencia as 22h sem mandado judicial, alegando 'fundada suspeita' de trafico de drogas. O morador, estudante universitario, foi algemado enquanto policiais revistaram toda a casa. Nada ilegal foi encontrado.","envolvidos":["Joao (morador)","Delegado Silva","Policiais da PM"],"evidencias":[{"id":"E1","titulo":"Video da entrada","descricao":"Filmagem da vizinha mostra policiais arrombando a porta sem apresentar qualquer documento","peso":0.95,"tipo":"digital"},{"id":"E2","titulo":"Relato do morador","descricao":"'Acordei com a porta sendo arrombada, fui algemado sem nenhuma explicacao, revistaram tudo'","peso":0.8,"tipo":"testemunhal"},{"id":"E3","titulo":"Boletim policial","descricao":"BO registra 'suspeita baseada em denuncia anonima'. Nenhum flagrante, nenhuma droga encontrada","peso":0.9,"tipo":"documental"},{"id":"E4","titulo":"Historico da rua","descricao":"Delegacia registra 3 ocorrencias na rua nos ultimos 30 dias","peso":0.2,"tipo":"estatistico"}],"duvidas":["Denuncia anonima justifica entrada forcada?","Havia situacao de flagrante?"],"resposta":{"violacao":True,"direito":"Inviolabilidade do Domicilio","artigo":"Art. 5º, XI","culpado":"Policiais da PM"}},
  {"id":5,"title":"Discriminacao em Loja","historia":"Michael, jovem negro, foi impedido de entrar em uma loja de roupas de grife pelo seguranca, que alegou 'perfil inadequado ao publico da loja'. Outros clientes brancos com aparencia similar entraram sem problemas.","envolvidos":["Michael (cliente)","Gerente da loja","Seguranca Pedro"],"evidencias":[{"id":"E1","titulo":"Video de seguranca","descricao":"Cameras mostram Michael sendo barrado enquanto outros clientes com roupas similares entram livremente","peso":0.9,"tipo":"digital"},{"id":"E2","titulo":"Depoimento de testemunha","descricao":"Cliente que estava presente declarou: 'Vi claramente que ele foi tratado diferente dos outros clientes'","peso":0.8,"tipo":"testemunhal"},{"id":"E3","titulo":"Politica da loja","descricao":"Manual do funcionario fala em 'criterios subjetivos de acesso para preservar experiencia dos clientes'","peso":0.85,"tipo":"documental"},{"id":"E4","titulo":"Resposta da gerencia","descricao":"Gerente afirmou que 'seguranca agiu dentro dos protocolos da empresa'","peso":0.6,"tipo":"documental"}],"duvidas":["Era politica da empresa ou acao individual do seguranca?","Como provar intencao discriminatoria?"],"resposta":{"violacao":True,"direito":"Igualdade e Nao Discriminacao","artigo":"Art. 5º caput","culpado":"Gerente da loja"}},
  {"id":6,"title":"Vazamento de Dados","historia":"Empresa de e-commerce vendeu base de dados com nome, CPF, endereco e historico de compras de 2 milhoes de clientes para parceiros de marketing sem consentimento previo. Clientes passaram a receber ligacoes e emails nao solicitados.","envolvidos":["TechShop (empresa)","CEO Ricardo","Clientes afetados"],"evidencias":[{"id":"E1","titulo":"Planilha vazada","descricao":"Arquivo com dados de clientes encontrado em servidor de empresa parceira sem qualquer criptografia","peso":0.95,"tipo":"digital"},{"id":"E2","titulo":"Email interno","descricao":"Email do CEO para diretor comercial: 'Vamos monetizar nossa base. Os dados valem ouro no mercado'","peso":0.9,"tipo":"digital"},{"id":"E3","titulo":"Termos de uso","descricao":"Termos de uso do site nao previam compartilhamento de dados com terceiros para fins comerciais","peso":0.85,"tipo":"documental"},{"id":"E4","titulo":"Reclamacoes","descricao":"4.847 reclamacoes formais de clientes sobre contato nao autorizado registradas em 30 dias","peso":0.7,"tipo":"estatistico"}],"duvidas":["Termos de uso permitem algum uso dos dados?","Qual o limite do uso comercial de dados pessoais?"],"resposta":{"violacao":True,"direito":"Privacidade e Protecao de Dados","artigo":"Art. 5º, X","culpado":"CEO Ricardo"}},
  {"id":7,"title":"Sem Direito de Defesa","historia":"Fernando foi demitido por justa causa acusado de fraude sem que lhe fosse dada qualquer oportunidade de apresentar sua versao dos fatos. A empresa conduziu investigacao interna secreta e anunciou a demissao em reuniao de 5 minutos.","envolvidos":["Fernando (funcionario)","RH da empresa","Diretor financeiro"],"evidencias":[{"id":"E1","titulo":"Ata da reuniao","descricao":"Ata de apenas 5 minutos registra: 'Comunicado de demissao por justa causa. Reuniao encerrada'","peso":0.9,"tipo":"documental"},{"id":"E2","titulo":"Processo interno","descricao":"Empresa realizou investigacao de 3 semanas sem notificar Fernando nem dar chance de contraditorio","peso":0.95,"tipo":"documental"},{"id":"E3","titulo":"Depoimento de Fernando","descricao":"'Nunca fui chamado para dar minha versao. Soube da acusacao e da demissao ao mesmo tempo'","peso":0.8,"tipo":"testemunhal"},{"id":"E4","titulo":"Regulamento interno","descricao":"Regulamento prevê proceso disciplinar mas nao especifica direito de defesa do funcionario","peso":0.6,"tipo":"documental"}],"duvidas":["Processo interno de empresa exige contraditorio?","A falta de defesa invalida a justa causa?"],"resposta":{"violacao":True,"direito":"Contraditorio e Ampla Defesa","artigo":"Art. 5º, LV","culpado":"Empresa"}},
  {"id":8,"title":"Censura de Materia","historia":"A Prefeitura de uma cidade obteve liminar judicial para impedir que o jornal local publicasse reportagem sobre contratos suspeitos entre a gestao municipal e empresas de fachada. O editor-chefe foi intimado a destruir todos os materiais.","envolvidos":["Jornal Verdade","Prefeito Sousa","Juiz que concedeu liminar"],"evidencias":[{"id":"E1","titulo":"Liminar judicial","descricao":"Liminar proibe 'sob pena de multa diaria de R$ 50.000 a publicacao de qualquer materia sobre contratos municipais'","peso":0.9,"tipo":"documental"},{"id":"E2","titulo":"Materia pronta","descricao":"Reportagem documentada com notas fiscais, contratos e evidencias de sobrepreco de 340% em obras","peso":0.85,"tipo":"documental"},{"id":"E3","titulo":"Depoimento do editor","descricao":"'Fomos impedidos de publicar materia de interesse publico. Isso e censura pura e simples'","peso":0.8,"tipo":"testemunhal"},{"id":"E4","titulo":"Argumento da prefeitura","descricao":"Advogado da prefeitura alega que publicacao causaria 'dano irreparavel a imagem do gestor publico'","peso":0.5,"tipo":"documental"}],"duvidas":["Protecao de imagem justifica censura previa?","Interesse publico supera direito de imagem?"],"resposta":{"violacao":True,"direito":"Liberdade de Imprensa","artigo":"Art. 5º, IX","culpado":"Prefeito Sousa"}},
]

INVESTIGATION_ROLES = [
  {"id":"icaro","nome":"Icaro Specter","titulo":"Advogado da Defesa","icon":"⚖️","cor":"#3b82f6","desc":"Mestre da narrativa. Contesta evidencias e cria duvida nos demais jogadores.","habilidades":{"contestacao":{"nome":"Contestacao Juridica","cd":25,"desc":"Reduz peso de uma evidencia em 40%"},"tese":{"nome":"Construcao de Tese","cd":40,"desc":"Cria linha de defesa que sugere ausencia de violacao"},"duvida":{"nome":"Duvida Razoavel","cd":9999,"uses":1,"desc":"Remove 1 evidencia do julgamento final (uso unico)"},"reversao":{"nome":"Reversao de Narrativa","cd":9999,"uses":1,"desc":"Troca suspeita entre dois envolvidos (ultimate)"}}},
  {"id":"natan","nome":"Natan Ross","titulo":"Promotor","icon":"🔥","cor":"#ef4444","desc":"Acusacao implacavel. Marca evidencias criticas e eleva seu impacto.","habilidades":{"marcar":{"nome":"Evidencia Critica","cd":20,"desc":"Aumenta peso de uma evidencia em 50%"},"acusar":{"nome":"Acusacao Formal","cd":35,"desc":"Bloqueia tentativa de contestacao do advogado por 30s"}}},
  {"id":"luciano","nome":"Luciano Hardman","titulo":"Delegado","icon":"🕵️","cor":"#f59e0b","desc":"Investigador nato. Desvenda evidencias ocultas que outros nao encontram.","habilidades":{"desbloquear":{"nome":"Investigacao Profunda","cd":45,"desc":"Revela evidencia oculta do caso"},"cruzar":{"nome":"Cruzamento de Dados","cd":30,"desc":"Mostra conexao entre duas evidencias"}}},
  {"id":"giovanna","nome":"Giovanna Pearson","titulo":"Juiza","icon":"⚖️","cor":"#8b5cf6","desc":"Seu voto vale dobrado. Pode ver tendencia dos votos dos outros.","habilidades":{"ver":{"nome":"Leitura do Juri","cd":30,"desc":"Revela tendencia de votos dos outros jogadores"},"peso":{"nome":"Voto Qualificado","cd":9999,"uses":1,"desc":"Seu proximo voto vale 2x (uso unico)"}}},
  {"id":"thalles","nome":"Thalles Litt","titulo":"Pregoeiro","icon":"📊","cor":"#10b981","desc":"Especialista em falhas administrativas e processuais.","habilidades":{"falha":{"nome":"Falha Processual","cd":35,"desc":"Revela falha administrativa no caso que pode mudar o desfecho"},"anular":{"nome":"Nulidade","cd":50,"desc":"Questiona a validade de uma evidencia por vicio formal"}}},
  {"id":"izabella","nome":"Izabella Zane","titulo":"Consultora Juridica","icon":"📚","cor":"#ec4899","desc":"Sugere artigos e fundamenta teorias. Ajuda o time a acertar.","habilidades":{"sugerir":{"nome":"Fundamentacao","cd":20,"desc":"Sugere 2 artigos constitucionais possiveis para o caso"},"analisar":{"nome":"Analise de Risco","cd":30,"desc":"Mostra probabilidade de acerto de cada opcao de voto"}}},
  {"id":"dilerman","nome":"Dilerman Forstman","titulo":"Procurador","icon":"🏛️","cor":"#f97316","desc":"Analisa impacto coletivo. Pode anular acusacoes fracas.","habilidades":{"impacto":{"nome":"Impacto Coletivo","cd":25,"desc":"Mostra quantas pessoas seriam afetadas pela decisao"},"anular_fraca":{"nome":"Anular Acusacao Fraca","cd":9999,"uses":1,"desc":"Se provas sao insuficientes, pode anular acusacao (ultimate)"}}},
]

PHASE_DURATIONS = {
    "lobby": 999,
    "intro": 45,
    "investigacao": 180,
    "debate": 90,
    "votacao": 45,
    "resultado": 999,
}

def _gen_room_id():
    return str(uuid.uuid4())[:8].upper()

def _make_room(creator_id: str, creator_name: str) -> dict:
    room_id = _gen_room_id()
    case = INVESTIGATION_CASES[int(time.time()) % len(INVESTIGATION_CASES)]
    return {
        "id": room_id,
        "phase": "lobby",
        "phase_start": time.time(),
        "case": case,
        "players": [{
            "id": creator_id,
            "name": creator_name,
            "role": None,
            "score": 0,
            "ready": False,
            "vote": None,
            "actions_used": [],
            "joined_at": time.time(),
        }],
        "evidence_weights": {e["id"]: e["peso"] for e in case["evidencias"]},
        "hidden_evidence": None,
        "contested": [],
        "critical": [],
        "removed_evidences": [],
        "shifted_suspect": {},
        "messages": [],
        "actions_log": [],
        "resultado": None,
        "created_at": time.time(),
        "last_action": time.time(),
        "bots_enabled": True,
    }

def _assign_roles(room: dict):
    import random
    roles = INVESTIGATION_ROLES[:]
    random.shuffle(roles)
    for i, p in enumerate(room["players"]):
        p["role"] = roles[i % len(roles)]["id"]

def _advance_phase(room: dict):
    phases = ["lobby", "intro", "investigacao", "debate", "votacao", "resultado"]
    cur = room["phase"]
    if cur == "resultado":
        return
    idx = phases.index(cur) if cur in phases else 0
    nxt = phases[min(idx + 1, len(phases) - 1)]
    room["phase"] = nxt
    room["phase_start"] = time.time()
    if nxt == "investigacao":
        _assign_roles(room)
        _add_hidden_evidence(room)
    if nxt == "resultado":
        _calc_resultado(room)

def _add_hidden_evidence(room: dict):
    # Add a hidden bonus evidence (unlockable by Delegado)
    room["hidden_evidence"] = {"id":"EH","titulo":"Evidencia Oculta","descricao":"Documento confidencial que pode mudar tudo — apenas o Delegado pode revelar","peso":0.7,"tipo":"oculta","revealed":False}

def _calc_resultado(room: dict):
    case = room["case"]
    correct = case["resposta"]
    results = []
    for p in room["players"]:
        v = p.get("vote") or {}
        pts = 0
        details = []
        if v.get("violacao") == correct["violacao"]:
            pts += 20; details.append("✅ Violacao: +20")
        else:
            details.append("❌ Violacao: 0")
        player_artigo = v.get("artigo", "").strip().lower().replace("\u00ba", "").replace(".", "").replace(" ", "")
        correct_artigo = correct["artigo"].lower().replace("\u00ba", "").replace(".", "").replace(" ", "")
        if player_artigo and (player_artigo == correct_artigo or player_artigo in correct_artigo or correct_artigo in player_artigo):
            pts += 50; details.append("\u2705 Artigo: +50")
        else:
            details.append(f"\u274c Artigo correto: {correct['artigo']}")
        if v.get("culpado", "").strip().lower() == correct["culpado"].strip().lower():
            pts += 30; details.append("✅ Culpado: +30")
        else:
            details.append(f"❌ Culpado: {correct['culpado']}")
        # role bonus
        role_obj = next((r for r in INVESTIGATION_ROLES if r["id"]==p.get("role")), None)
        if p.get("role") == "giovanna":
            pts_before = pts
            vote_weight = p.get("vote_weight", 1)
            pts = int(pts * vote_weight)
            if vote_weight > 1:
                details.append(f"⚖️ Voto qualificado x{vote_weight}")
        p["score"] = pts
        p["result_details"] = details
        results.append({"id":p["id"],"name":p["name"],"score":pts,"details":details,"role":p.get("role"),"vote":v})
    results.sort(key=lambda x: -x["score"])
    room["resultado"] = {
        "rankings": results,
        "resposta_correta": correct,
        "case_title": case["title"],
    }


# ── BOT SYSTEM ────────────────────────────────────────────────────────────────
import random as _random

BOT_NAMES = ["Dr. Cunha","Dra. Alves","Prof. Lima","Adv. Torres","Min. Costa","Proc. Neves","Del. Braga"]
BOT_WAIT_SECONDS = 60   # fill with bots after 60s without enough players

def _make_bot_player(bot_name: str) -> dict:
    return {
        "id": "BOT_" + bot_name.replace(" ", "_").upper(),
        "name": bot_name,
        "role": None,
        "score": 0,
        "ready": True,
        "vote": None,
        "actions_used": [],
        "joined_at": time.time(),
        "is_bot": True,
    }

def _fill_with_bots(room: dict):
    """Preenche sala com bots até 3 jogadores, respeitando max 5."""
    MAX_PLAYERS = 5
    MIN_WITH_BOTS = 3   # mínimo confortável de jogadores
    if not room.get("bots_enabled", True):
        return
    existing_bots = {p["id"] for p in room["players"] if p.get("is_bot")}
    available = [n for n in BOT_NAMES
                 if "BOT_" + n.replace(" ","_").upper() not in existing_bots]
    _random.shuffle(available)
    # Preenche até MIN_WITH_BOTS ou MAX_PLAYERS (o que for menor)
    target = min(MIN_WITH_BOTS, MAX_PLAYERS)
    needed = max(0, target - len(room["players"]))
    slots  = MAX_PLAYERS - len(room["players"])
    to_add = min(needed, slots, len(available))
    for i in range(to_add):
        room["players"].append(_make_bot_player(available[i]))
    room["last_action"] = time.time()

def _bot_vote(room: dict):
    """Make bots vote with plausible (but imperfect) answers."""
    case = room["case"]
    correct = case["resposta"]
    all_articles = [
        "Art. 5º, IV","Art. 5º, X","Art. 5º, XI","Art. 5º, III",
        "Art. 5º, LV","Art. 5º, IX","Art. 5º caput","Art. 37","Art. 7º",
    ]
    envolvidos = case["envolvidos"]
    for p in room["players"]:
        if not p.get("is_bot"):
            continue
        if p.get("vote"):
            continue
        # 70% chance of correct violacao, 60% correct artigo, 55% correct culpado
        violacao = correct["violacao"] if _random.random() < 0.70 else (not correct["violacao"])
        artigo   = correct["artigo"]   if _random.random() < 0.60 else _random.choice(all_articles)
        culpado  = correct["culpado"]  if _random.random() < 0.55 else _random.choice(envolvidos)
        p["vote"] = {"violacao": violacao, "artigo": artigo, "culpado": culpado}

def _tick_bots(room: dict, now: float):
    """Tick dos bots: preencher sala, iniciar jogo e votar automaticamente."""
    phase = room["phase"]

    if phase == "lobby":
        humans = [p for p in room["players"] if not p.get("is_bot")]
        bots   = [p for p in room["players"] if p.get("is_bot")]
        elapsed = now - room["created_at"]

        # 1. Preencher com bots após BOT_WAIT_SECONDS
        if room.get("bots_enabled", True) and elapsed >= BOT_WAIT_SECONDS:
            _fill_with_bots(room)
            # Re-listar após preenchimento
            bots = [p for p in room["players"] if p.get("is_bot")]

        # 2. Bots são sempre "prontos"
        for p in bots:
            p["ready"] = True

        # 3. Auto-iniciar quando:
        #    a) Há pelo menos 1 humano + 1 bot, e o humano clicou Pronto
        #    OU
        #    b) Bots entraram há mais de 5s e há pelo menos 2 jogadores no total
        total = len(room["players"])
        all_humans_ready = all(p.get("ready") for p in humans) if humans else False
        bots_just_filled = len(bots) > 0 and elapsed >= BOT_WAIT_SECONDS + 5

        should_start = (
            (total >= 2 and all_humans_ready and len(bots) > 0) or
            (total >= 2 and bots_just_filled and len(humans) >= 1)
        )
        if should_start:
            _advance_phase(room)

    # Auto-votar na fase de votação
    if phase == "votacao":
        elapsed_phase = now - room["phase_start"]
        if elapsed_phase >= 15:
            _bot_vote(room)
# ── END BOT SYSTEM ────────────────────────────────────────────────────────────

def _tick_rooms():
    """Background thread: advance phases by time."""
    while True:
        time.sleep(3)
        try:
            with INV_LOCK:
                now = time.time()
                dead = []
                for rid, room in INVESTIGATION_ROOMS.items():
                    try:
                        # Remove empty/stale rooms
                        if now - room.get("last_action", now) > 3600:
                            dead.append(rid)
                            continue
                        # Tick bots (handles auto-fill and auto-vote)
                        _tick_bots(room, now)
                        # Re-read phase AFTER _tick_bots (it may have advanced)
                        phase = room["phase"]
                        if phase in ("lobby", "resultado"):
                            continue
                        dur = PHASE_DURATIONS.get(phase, 60)
                        elapsed = now - room["phase_start"]
                        if elapsed >= dur:
                            _advance_phase(room)
                            room["last_action"] = now
                        # Auto-advance votacao if all players have voted
                        if room["phase"] == "votacao":
                            if all(p.get("vote") is not None for p in room["players"]):
                                _advance_phase(room)
                                room["last_action"] = now
                    except Exception as e:
                        print(f"Tick erro sala {rid}: {e}")
                for rid in dead:
                    del INVESTIGATION_ROOMS[rid]
        except Exception as e:
            print(f"Tick rooms erro geral: {e}")

# Start background phase ticker
_ticker_thread = threading.Thread(target=_tick_rooms, daemon=True)
_ticker_thread.start()

def inv_join_or_create(player_id: str, player_name: str, room_id: str = "") -> dict:
    with INV_LOCK:
        # Try joining existing room
        if room_id and room_id in INVESTIGATION_ROOMS:
            room = INVESTIGATION_ROOMS[room_id]
            if room["phase"] == "lobby" and len(room["players"]) < 5:
                # Check not already in
                if not any(p["id"] == player_id for p in room["players"]):
                    room["players"].append({
                        "id": player_id, "name": player_name,
                        "role": None, "score": 0, "ready": False,
                        "vote": None, "actions_used": [], "joined_at": time.time(),
                    })
                room["last_action"] = time.time()
                return {"room_id": room_id, "created": False}
        # Create new room
        room = _make_room(player_id, player_name)
        INVESTIGATION_ROOMS[room["id"]] = room
        return {"room_id": room["id"], "created": True}

def inv_list_rooms() -> list:
    with INV_LOCK:
        out = []
        for rid, room in INVESTIGATION_ROOMS.items():
            if room["phase"] == "lobby":
                out.append({"id": rid, "players": len(room["players"]), "case": room["case"]["title"]})
        return out

def inv_get_state(room_id: str, player_id: str) -> dict | None:
    with INV_LOCK:
        room = INVESTIGATION_ROOMS.get(room_id)
        if not room:
            return None
        now = time.time()
        phase = room["phase"]
        dur = PHASE_DURATIONS.get(phase, 60)
        elapsed = now - room["phase_start"]
        time_left = max(0, dur - elapsed) if phase not in ("lobby","resultado") else None
        # Build player list (sanitized)
        players_out = []
        for p in room["players"]:
            role_obj = next((r for r in INVESTIGATION_ROLES if r["id"]==p.get("role")), None)
            players_out.append({
                "id": p["id"],
                "name": p["name"],
                "role_id": p.get("role"),
                "role_name": role_obj["nome"] if role_obj else None,
                "role_icon": role_obj["icon"] if role_obj else None,
                "score": p.get("score", 0),
                "ready": p.get("ready", False),
                "has_voted": p.get("vote") is not None,
                "actions_used": p.get("actions_used", []),
                "is_bot": p.get("is_bot", False),
            })
        # Build evidences for this phase
        evidences = []
        for e in room["case"]["evidencias"]:
            eid = e["id"]
            if eid in room.get("removed_evidences", []):
                continue
            w = room["evidence_weights"].get(eid, e["peso"])
            evidences.append({**e, "peso": round(w, 2),
                "contested": eid in room.get("contested", []),
                "critical": eid in room.get("critical", [])})
        # Hidden evidence
        hidden = room.get("hidden_evidence")
        if hidden and hidden.get("revealed"):
            evidences.append(hidden)
        # My role
        me = next((p for p in room["players"] if p["id"] == player_id), None)
        my_role = None
        if me and me.get("role"):
            my_role = next((r for r in INVESTIGATION_ROLES if r["id"]==me["role"]), None)
        # Tendency (only for Giovanna)
        tendency = None
        if me and me.get("role") == "giovanna" and "ver" in me.get("actions_used", []):
            votes = [p.get("vote",{}).get("violacao") for p in room["players"] if p.get("vote")]
            if votes:
                sim = votes.count(True); nao = votes.count(False)
                tendency = {"sim": sim, "nao": nao}
        return {
            "room_id": room_id,
            "phase": phase,
            "time_left": round(time_left) if time_left is not None else None,
            "players": players_out,
            "case": {
                "id": room["case"]["id"],
                "title": room["case"]["title"],
                "historia": room["case"]["historia"],
                "envolvidos": room["case"]["envolvidos"],
                "duvidas": room["case"]["duvidas"],
            },
            "evidences": evidences if phase not in ("lobby","intro") else [],
            "messages": room.get("messages", [])[-30:],
            "actions_log": room.get("actions_log", [])[-10:],
            "resultado": room.get("resultado"),
            "my_role": my_role,
            "tendency": tendency,
            "shifted_suspect": room.get("shifted_suspect", {}),
            "bots_enabled": room.get("bots_enabled", True),
        }

def inv_action(room_id: str, player_id: str, action: str, target: str = "") -> dict:
    with INV_LOCK:
        room = INVESTIGATION_ROOMS.get(room_id)
        if not room:
            return {"ok": False, "msg": "Sala nao encontrada"}
        me = next((p for p in room["players"] if p["id"] == player_id), None)
        if not me:
            return {"ok": False, "msg": "Jogador nao encontrado"}
        # Handle "ready" action BEFORE role validation (players have no role in lobby)
        if action == "ready":
            me["ready"] = True
            msg_action = f"\u2705 {me['name']} esta pronto"
            # Start game if all ready and at least 2 players
            if all(p.get("ready") for p in room["players"]) and len(room["players"]) >= 2:
                _advance_phase(room)
            me.setdefault("actions_used", []).append(action)
            room.setdefault("actions_log", []).append({"ts": time.time(), "msg": msg_action})
            room["last_action"] = time.time()
            return {"ok": True, "msg": msg_action}
        if room["phase"] not in ("investigacao", "debate"):
            return {"ok": False, "msg": "Fase incorreta para acoes"}
        used = me.get("actions_used", [])
        role = me.get("role")
        role_obj = next((r for r in INVESTIGATION_ROLES if r["id"] == role), None)
        if not role_obj:
            return {"ok": False, "msg": "Sem role"}
        hab = role_obj["habilidades"].get(action)
        if not hab:
            return {"ok": False, "msg": "Habilidade invalida"}
        if hab.get("uses") == 1 and action in used:
            return {"ok": False, "msg": "Uso unico ja utilizado"}
        msg_action = ""
        # Execute action
        if action == "contestacao" and target:
            w = room["evidence_weights"].get(target, 0.5)
            room["evidence_weights"][target] = round(w * 0.6, 2)
            if target not in room["contested"]:
                room["contested"].append(target)
            msg_action = f"⚖️ {me['name']} contestou evidencia {target}"
        elif action == "marcar" and target:
            w = room["evidence_weights"].get(target, 0.5)
            room["evidence_weights"][target] = min(1.0, round(w * 1.5, 2))
            if target not in room["critical"]:
                room["critical"].append(target)
            msg_action = f"🔥 {me['name']} marcou evidencia {target} como CRITICA"
        elif action == "desbloquear":
            h = room.get("hidden_evidence")
            if h:
                h["revealed"] = True
                msg_action = f"🕵️ {me['name']} revelou evidencia oculta!"
        elif action == "duvida" and target:
            if target not in room.get("removed_evidences", []):
                room.setdefault("removed_evidences", []).append(target)
            msg_action = f"❓ {me['name']} usou Duvida Razoavel — evidencia {target} removida!"
        elif action == "reversao":
            suspects = room["case"]["envolvidos"]
            if len(suspects) >= 2:
                room["shifted_suspect"] = {"de": suspects[0], "para": suspects[1], "ativo": True}
            msg_action = f"🔄 {me['name']} ativou Reversao de Narrativa!"
        elif action == "ver":
            msg_action = f"👁️ {me['name']} analisou a tendencia dos votos"
        elif action == "peso":
            me["vote_weight"] = 2
            msg_action = f"⚖️ {me['name']} ativou Voto Qualificado!"
        elif action == "acusar":
            msg_action = f"🔥 {me['name']} emitiu Acusacao Formal!"
        elif action == "sugerir":
            msg_action = f"📚 {me['name']} solicitou fundamentacao juridica"
        elif action == "impacto":
            msg_action = f"🏛️ {me['name']} analisou impacto coletivo do caso"
        elif action == "falha":
            msg_action = f"📊 {me['name']} identificou falha processual!"
        else:
            if not msg_action:
                msg_action = f"⚡ {me['name']} usou {hab['nome']}"
        me.setdefault("actions_used", []).append(action)
        room.setdefault("actions_log", []).append({"ts": time.time(), "msg": msg_action})
        room["last_action"] = time.time()
        return {"ok": True, "msg": msg_action}

def inv_vote(room_id: str, player_id: str, vote: dict) -> dict:
    with INV_LOCK:
        room = INVESTIGATION_ROOMS.get(room_id)
        if not room:
            return {"ok": False, "msg": "Sala nao encontrada"}
        if room["phase"] != "votacao":
            return {"ok": False, "msg": "Nao e fase de votacao"}
        me = next((p for p in room["players"] if p["id"] == player_id), None)
        if not me:
            return {"ok": False, "msg": "Jogador nao encontrado"}
        me["vote"] = vote
        room["last_action"] = time.time()
        # Auto-advance if all voted
        if all(p.get("vote") is not None for p in room["players"]):
            _advance_phase(room)
        return {"ok": True}

def inv_chat(room_id: str, player_id: str, msg_text: str) -> dict:
    with INV_LOCK:
        room = INVESTIGATION_ROOMS.get(room_id)
        if not room:
            return {"ok": False}
        me = next((p for p in room["players"] if p["id"] == player_id), None)
        if not me:
            return {"ok": False}
        room.setdefault("messages", []).append({
            "ts": time.time(),
            "player": me["name"],
            "text": str(msg_text)[:200],
            "role": me.get("role"),
        })
        room["last_action"] = time.time()
        return {"ok": True}

# ── END INVESTIGATION MULTIPLAYER ─────────────────────────────────────────────

QUESTIONS = [
    # ── NIVEL 1 ────────────────────────────────────────────────────────────────
    {"level":1,"q":"O Art. 5, paragrafo 1, da Constituicao de 1988 estabelece que as normas definidoras dos direitos e garantias fundamentais possuem:","o":["Aplicacao imediata","Aplicacao condicionada a lei complementar","Aplicacao apenas subsidiaria","Aplicacao restrita ao Judiciario"],"a":0,"hint":"A Constituicao quis maximizar a eficacia dos direitos fundamentais.","ref":"Art. 5, §1","note":"As normas definidoras dos direitos e garantias fundamentais tem aplicacao imediata.","exp":"O dispositivo afasta a ideia de que direitos fundamentais dependem sempre de regulamentacao para produzir efeitos."},
    {"level":1,"q":"Tratados e convencoes internacionais sobre direitos humanos aprovados em cada Casa do Congresso, em dois turnos, por tres quintos dos votos, equivalem a:","o":["Lei ordinaria federal","Lei complementar federal","Emenda constitucional","Decreto autonomo"],"a":2,"hint":"A Constituicao criou um procedimento reforcado para certos tratados de direitos humanos.","ref":"Art. 5, §3","note":"O texto constitucional equipara esses tratados a emendas constitucionais.","exp":"Nao basta tratar de direitos humanos; o tratado precisa cumprir o rito qualificado previsto na propria Constituicao."},
    {"level":1,"q":"O Art. 5, paragrafo 2, indica que os direitos e garantias expressos na Constituicao:","o":["Formam rol taxativo e exaustivo","Excluem direitos oriundos de tratados","Nao excluem outros decorrentes do regime, dos principios e dos tratados adotados pelo Brasil","Dependem de lei para serem reconhecidos"],"a":2,"hint":"O sistema constitucional brasileiro e materialmente aberto.","ref":"Art. 5, §2","note":"O rol de direitos fundamentais nao e fechado nem puramente enumerativo.","exp":"A Constituicao admite direitos materialmente fundamentais fora do texto literal do caput e dos incisos do Art. 5."},
    {"level":1,"q":"Qual materia e protegida como clausula petrea pelo Art. 60, paragrafo 4?","o":["Direitos e garantias individuais","Plano plurianual","Competencia residual dos municipios","Estrutura administrativa de ministerios"],"a":0,"hint":"A resposta protege o nucleo duro do constitucionalismo liberal-democratico.","ref":"Art. 60, §4","note":"Direitos e garantias individuais nao podem ser abolidos sequer por emenda.","exp":"A Constituicao impede reformas que ataquem o nucleo essencial de direitos e garantias, protegendo a ordem constitucional contra autodestruicao."},
    {"level":1,"q":"A afirmacao de que todo poder emana do povo e por ele sera exercido diretamente ou por representantes eleitos traduz qual vetor constitucional?","o":["Soberania popular","Separacao rigida de poderes","Legalidade estrita tributaria","Federalismo cooperativo"],"a":0,"hint":"A regra conecta legitimidade do poder e democracia.","ref":"Art. 1, paragrafo unico","note":"A origem do poder politico e popular, e nao burocratica.","exp":"O dispositivo funda o Estado Democratico de Direito em uma base de legitimidade popular."},
    {"level":1,"q":"No plano dogmatico, a afirmacao correta sobre direitos fundamentais e:","o":["Sao absolutos em qualquer colisao","Tem eficacia apenas nas relacoes Estado-individuo","Podem irradiar efeitos tambem nas relacoes privadas","Valem apenas para brasileiros natos"],"a":2,"hint":"Pense na eficacia horizontal dos direitos fundamentais.","ref":"Art. 5 e teoria da eficacia horizontal","note":"A protecao dos direitos fundamentais pode repercutir tambem em relacoes entre particulares.","exp":"A leitura contemporanea da Constituicao reconhece que direitos fundamentais tambem condicionam relacoes privadas em maior ou menor grau."},
    {"level":1,"q":"A leitura contemporanea do principio da igualdade autoriza concluir que:","o":["A Constituicao so admite igualdade formal","Tratamentos desiguais sao sempre inconstitucionais","A igualdade pode justificar diferenciacoes normativas quando fundadas em criterio constitucionalmente legitimo","A igualdade impede qualquer politica publica de inclusao"],"a":2,"hint":"A igualdade material busca reduzir assimetrias injustificadas.","ref":"Art. 5, caput","note":"A igualdade constitucional nao se reduz a uniformidade cega.","exp":"A isonomia constitucional permite diferenciacoes justificadas para promover equilibrio e impedir discriminacoes arbitrarias."},
    {"level":1,"q":"Segundo a doutrina e a jurisprudencia do STF, direitos fundamentais podem ser restringidos por lei desde que:","o":["A restricao seja total e definitiva","Preservem o nucleo essencial e respeitem a proporcionalidade","O Executivo concorde com a restricao","A restricao abranja apenas estrangeiros"],"a":1,"hint":"Ha um limite que nem o legislador pode ultrapassar.","ref":"Art. 5 e teoria do nucleo essencial","note":"A restricao legislativa de direito fundamental deve respeitar o nucleo essencial e o principio da proporcionalidade.","exp":"O STF consagrou que leis que esvaziem por completo o conteudo de um direito fundamental sao inconstitucionais por violacao ao seu nucleo essencial."},
    {"level":1,"q":"A dignidade da pessoa humana na Constituicao de 1988 esta posicionada como:","o":["Direito subjetivo passivel de ponderacao ordinaria","Fundamento da Republica Federativa do Brasil","Principio administrativo restrito ao funcionalismo publico","Norma programatica sem eficacia juridica propria"],"a":1,"hint":"Observe onde a Constituicao posiciona esse valor: no titulo sobre os fundamentos.","ref":"Art. 1, III","note":"A dignidade da pessoa humana e fundamento da Republica, com densidade normativa propria.","exp":"Ao ser erigida como fundamento, a dignidade deixa de ser apenas diretriz e passa a condicionar toda a ordem juridica."},
    # ── NIVEL 2 ────────────────────────────────────────────────────────────────
    {"level":2,"q":"Qual afirmacao esta de acordo com a liberdade de manifestacao do pensamento na Constituicao de 1988?","o":["E livre, mas o anonimato e vedado","Depende de licenca administrativa","Admite censura previa em contexto politico sensivel","So protege opinioes favoraveis a ordem constitucional"],"a":0,"hint":"A Constituicao protege a liberdade, mas exige responsabilidade.","ref":"Art. 5, IV","note":"A manifestacao do pensamento e livre, vedado o anonimato.","exp":"A vedacao ao anonimato busca permitir responsabilizacao posterior, sem abrir espaco para censura previa."},
    {"level":2,"q":"A dissolucao compulsoria de associacao civil somente pode ocorrer:","o":["Por ato do Poder Executivo em caso de interesse publico","Por decisao judicial com transito em julgado","Por deliberacao do Ministerio Publico","Por decreto legislativo simples"],"a":1,"hint":"A Constituicao protege fortemente a liberdade associativa.","ref":"Art. 5, XIX","note":"A dissolucao compulsoria depende de decisao judicial transitada em julgado.","exp":"A ordem constitucional nao admite que o Executivo desconstitua associacoes por mera conveniencia politica ou administrativa."},
    {"level":2,"q":"Quanto a inviolabilidade de domicilio, a regra correta e:","o":["A ordem judicial autoriza ingresso forcado a qualquer hora","A entrada e sempre livre em investigacao criminal","A casa e asilo inviolavel, salvo flagrante, desastre, socorro, ou ordem judicial durante o dia","A policia pode ingressar a noite com autorizacao verbal de delegado"],"a":2,"hint":"A excecao da ordem judicial tem limitacao temporal expressa.","ref":"Art. 5, XI","note":"A ordem judicial nao autoriza, por si so, ingresso noturno.","exp":"O texto constitucional foi preciso ao limitar a execucao de ordem judicial ao periodo diurno, salvo outras hipoteses constitucionais."},
    {"level":2,"q":"Sobre a extradicao de brasileiro, a alternativa correta e:","o":["Brasileiro nato pode ser extraditado por crime hediondo","Brasileiro naturalizado nunca pode ser extraditado","Brasileiro naturalizado pode ser extraditado por crime comum antes da naturalizacao ou por trafico de entorpecentes","Todo brasileiro pode ser extraditado mediante tratado bilateral"],"a":2,"hint":"A regra distingue brasileiro nato e naturalizado.","ref":"Art. 5, LI","note":"A Constituicao admite hipoteses restritas de extradicao do naturalizado.","exp":"O nato nao e extraditado; o naturalizado pode ser, nas hipoteses expressamente descritas pelo texto constitucional."},
    {"level":2,"q":"Em relacao ao sigilo das comunicacoes, a Constituicao afirma que:","o":["Toda comunicacao pode ser interceptada por interesse publico generico","As comunicacoes telefonicas podem ser interceptadas por ordem judicial, nas hipoteses e forma que a lei estabelecer","Correspondencia pode ser aberta por qualquer autoridade policial","Comunicacoes de dados nao possuem protecao constitucional"],"a":1,"hint":"A Constituicao traz excecao especifica e controlada.","ref":"Art. 5, XII","note":"A interceptacao telefonica depende de ordem judicial e base legal.","exp":"Nao existe autorizacao ampla e administrativa para afastar o sigilo; a excecao constitucional e estritamente regulada."},
    {"level":2,"q":"No tocante ao direito de resposta, a Constituicao assegura:","o":["Resposta apenas em esfera penal","Resposta proporcional ao agravo, alem de indenizacao por dano material, moral ou a imagem","Resposta apenas quando houver ordem judicial definitiva","Resposta limitada a agentes publicos"],"a":1,"hint":"A garantia nao exclui reparacao civil.","ref":"Art. 5, V","note":"O direito de resposta e autonomo em relacao a indenizacao.","exp":"A Constituicao combina tutela de honra e imagem com a possibilidade de resposta proporcional ao agravo sofrido."},
    {"level":2,"q":"Quanto a liberdade de associacao, a alternativa correta e:","o":["A criacao de associacoes depende de autorizacao estatal","E plena a liberdade de associacao para fins licitos, vedada a de carater paramilitar","Associacoes podem ser dissolvidas por ato do prefeito","A liberdade associativa nao alcanca entidades sindicais"],"a":1,"hint":"A Constituicao dispensa autorizacao, mas nao tolera fins ilicitos ou carater paramilitar.","ref":"Art. 5, XVII e XVIII","note":"Associacoes licitas independem de autorizacao e o Estado nao pode interferir em seu funcionamento, salvo limites constitucionais.","exp":"O texto constitucional protege a autonomia associativa, mas exclui fins ilicitos e estruturas paramilitares."},
    {"level":2,"q":"A liberdade de crenca e culto religioso na Constituicao implica:","o":["Apenas tolerancia passiva do Estado","Livre exercicio dos cultos religiosos e protecao aos locais de culto e liturgias","Financiamento obrigatorio de toda religiao pelo Estado","Proibicao de simbolos religiosos em espacos publicos"],"a":1,"hint":"A liberdade religiosa tem dimensao positiva e negativa.","ref":"Art. 5, VI","note":"O livre exercicio dos cultos religiosos e garantido, e o Estado deve proteger os locais de culto e suas liturgias.","exp":"A Constituicao nao se limita a tolerar religiao; ela garante o exercicio ativo e protege os espacos de culto."},
    {"level":2,"q":"O direito de propriedade na Constituicao de 1988 esta condicionado a:","o":["Uso exclusivo do titular, sem restricoes","Atendimento de sua funcao social","Autorizacao anual do Municipio","Registro obrigatorio em cartorio para todos os bens"],"a":1,"hint":"A Constituicao nao reconhece propriedade como direito absoluto e desvinculado de responsabilidade social.","ref":"Art. 5, XXIII","note":"A propriedade atendera sua funcao social.","exp":"A funcao social e condicao intrinseca do exercicio do direito de propriedade, nao mera restricao externa."},
    # ── NIVEL 3 ────────────────────────────────────────────────────────────────
    {"level":3,"q":"No mandado de seguranca coletivo, possuem legitimidade ativa, entre outros:","o":["Apenas a Defensoria Publica e o Ministerio Publico","Partido politico com representacao no Congresso e entidade associativa constituida ha pelo menos um ano, em defesa de seus membros","Qualquer pessoa fisica em nome do povo","Somente sindicatos de servidores publicos"],"a":1,"hint":"A legitimidade coletiva tem rol constitucional especifico.","ref":"Art. 5, LXX","note":"A Constituicao legitima partido com representacao no Congresso, sindicato, entidade de classe e associacao nos termos constitucionais.","exp":"O mandado de seguranca coletivo nao foi aberto a qualquer individuo, mas a sujeitos coletivos com representatividade definida."},
    {"level":3,"q":"A acao popular pode ser proposta por:","o":["Qualquer eleitor, na qualidade de cidadao","Qualquer residente no territorio nacional","Apenas o Ministerio Publico","Apenas partido politico com representacao no Congresso"],"a":0,"hint":"A acao popular e instrumento de cidadania ativa, nao mera legitimidade difusa aberta a todos indistintamente.","ref":"Art. 5, LXXIII","note":"A legitimidade exige cidadania, e nao simples residencia.","exp":"A Constituicao atribui ao cidadao, e nao a qualquer pessoa, o poder de acionar a jurisdicao para combater ato lesivo ao patrimonio publico."},
    {"level":3,"q":"Quanto ao habeas corpus, e correto afirmar que:","o":["Serve para proteger patrimonio publico","So pode ser impetrado por advogado regularmente inscrito","Protege a liberdade de locomocao contra ilegalidade ou abuso de poder","Exige custas processuais e deposito previo"],"a":2,"hint":"Trata-se do remedio constitucional historicamente ligado ao ir e vir.","ref":"Art. 5, LXVIII","note":"O habeas corpus e gratuito e vocacionado a tutelar a liberdade de locomocao.","exp":"Seu objeto e estrito: nao protege qualquer direito, mas especificamente a liberdade de locomocao ameacada ou violada."},
    {"level":3,"q":"O habeas data mostra-se adequado para:","o":["Assegurar acesso e retificacao de informacoes relativas ao impetrante constantes de registros publicos ou de carater publico","Viabilizar direito constitucional travado por omissao legislativa","Proteger liberdade de reuniao","Anular ato lesivo ao meio ambiente"],"a":0,"hint":"A tutela aqui e informacional e personalissima.","ref":"Art. 5, LXXII","note":"O foco do habeas data e o controle de dados pessoais em registros publicos.","exp":"Nao se confunde com mandado de injuncao nem com tutela da liberdade de locomocao; seu objeto e a informacao pessoal."},
    {"level":3,"q":"O mandado de injuncao e cabivel quando a falta de norma regulamentadora torne inviavel:","o":["Apenas o exercicio do voto","Direitos e liberdades constitucionais e prerrogativas inerentes a nacionalidade, soberania e cidadania","Unicamente direitos patrimoniais privados","Somente a atividade partidaria"],"a":1,"hint":"A Constituicao delimita expressamente o campo do remedio.","ref":"Art. 5, LXXI","note":"A omissao normativa e o elemento central do mandado de injuncao.","exp":"O instituto existe para enfrentar inercia normativa capaz de bloquear o exercicio efetivo de direitos constitucionais."},
    {"level":3,"q":"O direito de peticao aos Poderes Publicos em defesa de direitos ou contra ilegalidade ou abuso de poder e exercido:","o":["Mediante pagamento de taxa administrativa","Independentemente do pagamento de taxas","Apenas por advogado","Somente perante o Poder Judiciario"],"a":1,"hint":"A Constituicao trata essa garantia como franqueada ao administrado sem custo.","ref":"Art. 5, XXXIV, a","note":"O direito de peticao nao se condiciona ao recolhimento de taxas.","exp":"A regra busca impedir barreiras economicas ao acesso do individuo aos Poderes Publicos para defesa de direitos."},
    {"level":3,"q":"Na acao popular, salvo comprovada ma-fe, o autor fica isento de:","o":["Custas judiciais e onus da sucumbencia","Qualquer comparecimento processual","Prova documental minima","Capacidade processual"],"a":0,"hint":"A Constituicao buscou incentivar a fiscalizacao cidada sem risco economico excessivo.","ref":"Art. 5, LXXIII","note":"A isencao e afastada em caso de ma-fe.","exp":"A acao popular foi desenhada para permitir controle civico do patrimonio publico e da moralidade sem desestimular o cidadao por receio financeiro."},
    {"level":3,"q":"O mandado de seguranca individual protege direito liquido e certo nao amparado por habeas corpus ou habeas data, quando o responsavel pela ilegalidade ou abuso e:","o":["Qualquer particular com poder economico relevante","Autoridade publica ou agente de pessoa juridica no exercicio de atribuicoes do Poder Publico","Unicamente o Presidente da Republica","Apenas o Ministerio Publico Federal"],"a":1,"hint":"O polo passivo do mandado de seguranca tem definicao constitucional funcional.","ref":"Art. 5, LXIX","note":"O mandado de seguranca protege contra ato de autoridade publica ou de agente em exercicio de funcao publica.","exp":"O conceito constitucional de autoridade coatora e funcional, nao organico, alcancando agentes privados quando exercem delegacao publica."},
    # ── NIVEL 4 ────────────────────────────────────────────────────────────────
    {"level":4,"q":"A respeito da saude no texto constitucional, assinale a alternativa correta:","o":["A saude e servico facultativo do Estado","A saude e direito de todos e dever do Estado, garantida mediante politicas sociais e economicas que visem a reducao do risco de doenca e ao acesso universal e igualitario","A saude e direito apenas de contribuintes da seguridade social","A saude publica depende de autorizacao legislativa anual para existir"],"a":1,"hint":"A Constituicao vincula saude, risco e acesso universal.","ref":"Art. 196","note":"O direito a saude tem densidade normativa propria e nao e mera diretriz politica vazia.","exp":"O texto constitucional define a saude como direito fundamental social dotado de exigibilidade e vinculado a acesso universal e igualitario."},
    {"level":4,"q":"Entre os direitos dos trabalhadores urbanos e rurais, a irredutibilidade do salario admite excecao:","o":["Por ato unilateral do empregador em crise financeira","Por convencao ou acordo coletivo","Por decreto do Poder Executivo","Por regulamento interno da empresa"],"a":1,"hint":"A flexibilizacao depende de negociacao coletiva constitucionalmente reconhecida.","ref":"Art. 7, VI","note":"A irredutibilidade salarial nao e absoluta, mas a excecao tem forma constitucionalmente delimitada.","exp":"A Constituicao admite reducao salarial apenas dentro de arranjo coletivo, afastando imposicoes unilaterais do empregador ou do Estado."},
    {"level":4,"q":"Qual opcao corresponde a direito social expressamente previsto no Art. 6 apos evolucao do texto constitucional?","o":["Transporte","Protecao cambial","Intervencao administrativa","Resgate bancario"],"a":0,"hint":"Esse direito foi acrescido ao rol por emenda constitucional.","ref":"Art. 6","note":"O transporte integra o rol formal dos direitos sociais.","exp":"O Art. 6 sofreu ampliacoes ao longo do tempo, e o transporte passou a ser expressamente reconhecido como direito social."},
    {"level":4,"q":"Constitui direito dos trabalhadores urbanos e rurais:","o":["Participacao obrigatoria nos lucros em qualquer percentual fixado por lei","Fundo de garantia do tempo de servico","Dispensa livre de descanso semanal remunerado","Supressao do adicional noturno por contrato individual"],"a":1,"hint":"O direito esta literalmente no Art. 7.","ref":"Art. 7, III","note":"O FGTS integra o rol de garantias constitucionais do trabalho.","exp":"A Constituicao incorpora instrumentos de protecao social do trabalho, entre eles o FGTS."},
    {"level":4,"q":"A educacao, conforme a Constituicao, sera promovida e incentivada com a colaboracao da sociedade, visando:","o":["Apenas a capacitacao para o mercado financeiro","Somente a alfabetizacao funcional","O pleno desenvolvimento da pessoa, seu preparo para o exercicio da cidadania e sua qualificacao para o trabalho","Exclusivamente a formacao tecnico-profissionalizante"],"a":2,"hint":"A finalidade constitucional da educacao e ampla e formativa.","ref":"Art. 205","note":"Educacao e desenvolvimento humano, cidadania e trabalho aparecem articulados no texto constitucional.","exp":"A Constituicao nao restringe a educacao a treinamento tecnico; ela a entende como instrumento de emancipacao e cidadania."},
    {"level":4,"q":"O seguro-desemprego, em caso de desemprego involuntario, figura no texto constitucional como:","o":["Favor administrativo eventual","Direito dos trabalhadores urbanos e rurais","Beneficio exclusivo de servidor estatutario","Prestacao civil sem relevancia constitucional"],"a":1,"hint":"A Constituicao trata a perda involuntaria do emprego como risco social merecedor de protecao.","ref":"Art. 7, II","note":"O seguro-desemprego e garantia constitucional do trabalhador.","exp":"A previsao constitucional integra a rede minima de protecao contra vulnerabilidades associadas ao trabalho."},
    {"level":4,"q":"A assistencia social na Constituicao sera prestada a quem dela necessitar:","o":["Apenas mediante contribuicao previa ao sistema","Independentemente de contribuicao a seguridade social","Somente a trabalhadores formalmente registrados","Mediante comprovacao de renda minima por tres anos"],"a":1,"hint":"A assistencia social difere da previdencia exatamente neste ponto.","ref":"Art. 203","note":"A assistencia social independe de contribuicao previa.","exp":"A Constituicao distingue assistencia social de previdencia: aquela nao exige contribuicao; esta sim."},
    {"level":4,"q":"A protecao ao trabalho noturno na Constituicao se expressa, entre outros pontos, por:","o":["Remuneracao do trabalho noturno superior a do diurno","Livre supressao de adicional por contrato individual","Equiparacao obrigatoria entre noturno e diurno sem adicional","Proibicao absoluta de trabalho noturno"],"a":0,"hint":"A resposta esta no rol do Art. 7.","ref":"Art. 7, IX","note":"A Constituicao assegura remuneracao do trabalho noturno superior a do diurno.","exp":"O adicional noturno traduz reconhecimento constitucional do maior desgaste social e biologico associado ao labor noturno."},
    # ── NIVEL 5 ────────────────────────────────────────────────────────────────
    {"level":5,"q":"Uma autoridade municipal exige licenca previa para passeata pacifica, sem armas, em praca publica, ainda que os organizadores tenham apresentado aviso previo. A exigencia e:","o":["Constitucional, porque toda reuniao publica depende de autorizacao","Inconstitucional, porque a liberdade de reuniao exige previo aviso, nao licenca","Constitucional apenas se o tema da manifestacao for politico","Constitucional apenas se a praca for bem publico municipal"],"a":1,"hint":"O aviso organiza o espaco publico; a licenca converte liberdade em permissao estatal.","ref":"Art. 5, XVI","note":"A Constituicao exige previo aviso, nao autorizacao.","exp":"Transformar reuniao pacifica em atividade dependente de licenca esvazia uma liberdade publica expressamente protegida."},
    {"level":5,"q":"Com ordem judicial valida, policiais ingressam as 23h na residencia de investigado apenas para cumprir busca domiciliar, sem flagrante, sem desastre e sem pedido de socorro. A medida e:","o":["Constitucional, porque a ordem judicial afasta qualquer limite horario","Inconstitucional, porque a ordem judicial, por si so, legitima ingresso apenas durante o dia","Constitucional, porque toda busca criminal dispensa as restricoes do Art. 5","Constitucional, desde que haja investigacao de crime hediondo"],"a":1,"hint":"A ordem judicial nao e cheque em branco para ingresso noturno.","ref":"Art. 5, XI","note":"Sem outra excecao constitucional, a ordem judicial se cumpre durante o dia.","exp":"A garantia domiciliar estabelece limite expresso para o cumprimento de ordem judicial, preservando a intimidade domiciliar noturna."},
    {"level":5,"q":"Brasileiro naturalizado e acusado de comprovado envolvimento com trafico ilicito de entorpecentes apos a naturalizacao. Diante do texto constitucional, a extradicao:","o":["E vedada em qualquer hipotese apos a naturalizacao","E possivel, porque a Constituicao admite extradicao do naturalizado por comprovado envolvimento com trafico ilicito de entorpecentes","So seria possivel se o crime fosse politico","Depende de previa cassacao da naturalizacao pelo Executivo"],"a":1,"hint":"A regra do naturalizado tem duas hipoteses constitucionais especificas.","ref":"Art. 5, LI","note":"O trafico ilicito de entorpecentes aparece expressamente como excecao constitucional.","exp":"O texto constitucional trata o naturalizado de forma distinta do nato e preve excecao expressa para trafico ilicito de entorpecentes."},
    {"level":5,"q":"Um servidor necessita de certidao em reparticao publica para defender direito proprio em processo administrativo. O orgao condiciona a emissao ao pagamento de taxa. A conduta do orgao e:","o":["Constitucional, porque toda certidao depende de taxa","Inconstitucional, porque a obtencao de certidoes para defesa de direitos independe do pagamento de taxas","Constitucional, desde que a taxa seja pequena","Constitucional, se a reparticao tiver muita demanda"],"a":1,"hint":"A garantia esta no mesmo inciso que trata do direito de peticao.","ref":"Art. 5, XXXIV, b","note":"A obtencao de certidoes em reparticoes publicas para defesa de direitos independe de taxas.","exp":"A Constituicao retira obstaculos economicos do acesso a certidoes necessarias para defesa de direitos."},
    {"level":5,"q":"Uma associacao regularmente constituida ha cinco anos pretende impetrar mandado de seguranca coletivo em defesa de seus associados. A legitimidade ativa e:","o":["Inexistente, porque associacao nunca pode impetrar mandado de seguranca coletivo","Existente, desde que atue em defesa de seus membros ou associados","Existente apenas com autorizacao judicial previa","Existente apenas se houver representacao no Congresso Nacional"],"a":1,"hint":"Nao confunda legitimidade de associacao com a do partido politico.","ref":"Art. 5, LXX","note":"Associacao legalmente constituida e em funcionamento ha pelo menos um ano possui legitimidade, na forma constitucional.","exp":"A Constituicao admite que a associacao, se preencher os requisitos, atue coletivamente na defesa de seus associados."},
    {"level":5,"q":"Grupo de servidores tem direito constitucional inviabilizado ha anos porque o legislador nao editou a norma regulamentadora indispensavel. A medida constitucional mais adequada e:","o":["Habeas data","Mandado de injuncao","Acao popular","Habeas corpus"],"a":1,"hint":"O foco aqui e a omissao normativa que bloqueia direito.","ref":"Art. 5, LXXI","note":"O mandado de injuncao foi concebido para enfrentar a omissao regulamentadora constitucionalmente relevante.","exp":"Quando a falta de norma inviabiliza direito ou liberdade constitucional, o remedio adequado e o mandado de injuncao."},
    {"level":5,"q":"Autoridade policial determina abertura generalizada de correspondencia fisica de servidores para apuracao administrativa, sem ordem judicial. A medida e:","o":["Constitucional, por se tratar de servidores publicos","Inconstitucional, porque viola a inviolabilidade da correspondencia","Constitucional, desde que haja sindicancia interna","Constitucional, se a correspondencia estiver no local de trabalho"],"a":1,"hint":"A inviolabilidade da correspondencia nao desaparece por vinculacao funcional ao Estado.","ref":"Art. 5, XII","note":"A protecao constitucional do sigilo de correspondencia nao cede a controles administrativos genericos.","exp":"A administracao nao pode afastar, por mera conveniencia investigativa, garantia constitucional de sigilo de correspondencia."},
    {"level":5,"q":"Lei municipal proibe reuniao em praca historica da cidade nos fins de semana, alegando preservacao do patrimonio. Considerando o Art. 5, XVI, essa restricao e:","o":["Plenamente constitucional, pois patrimonio historico justifica qualquer restricao","Inconstitucional, pois a Constituicao nao permite restricoes locais a liberdade de reuniao","Potencialmente inconstitucional se a restricao generalizada anular o nucleo essencial da liberdade de reuniao","Constitucional apenas se aprovada por referendum popular"],"a":2,"hint":"A colisao entre liberdade de reuniao e preservacao do patrimonio exige proporcionalidade.","ref":"Art. 5, XVI e Art. 216","note":"Restricoes a direitos fundamentais devem ser proporcionais e nao podem esvaziar o nucleo essencial da garantia.","exp":"A analise constitucional exige ponderacao: restricoes generalizadas que inviabilizam o exercicio da liberdade sao inconstitucionais, ainda que o fim seja legitimo."},
    # ── V/F QUESTIONS ──────────────────────────────────────────────────────
    {"level":1,"type":"tf","q":"Direitos fundamentais sao absolutos e nao admitem nenhuma restricao.","o":["Verdadeiro","Falso"],"a":1,"hint":"Pense na possibilidade de colisao entre direitos fundamentais.","ref":"Art. 5 e doutrina","note":"Direitos fundamentais nao sao absolutos; podem ser restringidos proporcionalmente.","exp":"A doutrina e o STF reconhecem que direitos fundamentais podem colidir entre si, exigindo ponderacao e proporcionalidade.","diff":"easy"},
    
    # ── GOLDEN QUESTIONS ──────────────────────────────────────────────
    {"level":2,"q":"O principio da presuncao de inocencia, previsto no Art. 5, LVII, da CF/88, estabelece que ninguem sera considerado culpado ate:","o":["A denuncia do Ministerio Publico","O transito em julgado de sentenca penal condenatoria","A prisao em flagrante","O indiciamento policial"],"a":1,"hint":"A Constituicao protege o acusado ate o esgotamento das vias recursais.","ref":"Art. 5, LVII","note":"Ninguem sera considerado culpado ate o transito em julgado de sentenca penal condenatoria.","exp":"O principio da presuncao de inocencia e clausula petrea e garante que a culpa so se estabelece definitivamente apos o transito em julgado da sentenca condenatoria.","diff":"hard",    "golden":True},
        {"level":4,"q":"A Constituicao Federal de 1988 preve que a educacao e direito de todos e dever do Estado e da familia, devendo ser promovida e incentivada com a colaboracao da sociedade. Qual artigo fundamenta essa disposicao?","o":["Art. 196","Art. 205","Art. 215","Art. 225"],"a":1,"hint":"Este artigo inaugura o capitulo sobre educacao na CF/88.","ref":"Art. 205","note":"A educacao e direito de todos e dever do Estado e da familia.","exp":"O Art. 205 estabelece o dever compartilhado entre Estado, familia e sociedade na promocao da educacao, visando o pleno desenvolvimento da pessoa, seu preparo para a cidadania e qualificacao para o trabalho.","diff":"hard","golden":True},
    # ── BOSS QUESTIONS ────────────────────────────────────────────────
    {"level":1,"q":"CASO PRATICO: Um cidadao teve sua residencia invadida por policiais as 23h, sem mandado judicial e sem flagrante delito. Com base na CF/88, analise: a invasao foi constitucional?","o":["Sim, pois a policia tem poder de investigacao","Nao, pois fora das hipoteses constitucionais (flagrante, desastre, socorro) a entrada depende de ordem judicial durante o DIA","Sim, desde que haja autorizacao verbal do delegado","Nao, porque nenhuma entrada em domicilio e permitida"],"a":1,"hint":"Atencao ao periodo do dia e as excecoes constitucionais.","ref":"Art. 5, XI","note":"A casa e asilo inviolavel. A entrada com ordem judicial so e permitida durante o dia.","exp":"A CF/88 estabelece que o ingresso em domicilio alheio sem consentimento so pode ocorrer em flagrante delito, desastre, socorro, ou por determinacao judicial DURANTE O DIA. A invasao noturna sem mandado e flagrante viola diretamente o Art. 5, XI.","diff":"hard",    "boss":True},
        {"level":2,"q":"CASO PRATICO: O Congresso aprovou emenda constitucional que permite a pena de morte para crimes hediondos. Esta emenda e constitucional?","o":["Sim, pois o Congresso tem poder constituinte derivado","Nao, pois o direito a vida e clausula petrea e nao pode ser abolido por emenda","Sim, desde que aprovada por maioria absoluta","Depende de referendum popular"],"a":1,"hint":"Considere os limites materiais ao poder de reforma constitucional.","ref":"Art. 60, §4, IV","note":"Os direitos e garantias individuais sao clausulas petreas.","exp":"O Art. 60, §4, IV proibe emendas tendentes a abolir direitos e garantias individuais. O direito a vida (Art. 5, caput) e clausula petrea. Uma emenda que institua pena de morte fora das hipoteses ja previstas (guerra declarada) seria inconstitucional por violar o nucleo imodificavel da Constituicao.","diff":"hard","boss":True},
        {"level":3,"q":"CASO PRATICO: Um juiz determinou a interceptacao telefonica de um suspeito por 60 dias, sem renovacao fundamentada. A interceptacao e legal?","o":["Sim, o juiz tem ampla discricionariedade","Nao, a Lei 9.296/96 limita a interceptacao a 15 dias, renovavel por igual periodo com fundamentacao","Sim, desde que haja inquerito policial aberto","Depende da gravidade do crime"],"a":1,"hint":"A interceptacao telefonica tem prazo legal definido e exige fundamentacao para renovacao.","ref":"Art. 5, XII e Lei 9.296/96","note":"A interceptacao telefonica tem prazo maximo de 15 dias, renovavel por decisao fundamentada.","exp":"A Lei 9.296/96 regulamenta o Art. 5, XII da CF/88. A interceptacao so pode durar 15 dias, renovavel por igual periodo mediante decisao judicial fundamentada. Uma interceptacao de 60 dias sem renovacao fundamentada viola tanto a lei quanto a garantia constitucional do sigilo das comunicacoes.","diff":"hard","boss":True},
        {"level":4,"q":"CASO PRATICO: Um municipio criou lei proibindo manifestacoes publicas em todas as pracas da cidade. Analise a constitucionalidade dessa lei.","o":["Constitucional, pois o municipio tem autonomia legislativa","Inconstitucional, pois viola a liberdade de reuniao (Art. 5, XVI) que garante reuniao pacifica em locais abertos independente de autorizacao","Constitucional, se houver justificativa de ordem publica","Depende de regulamentacao federal"],"a":1,"hint":"A liberdade de reuniao e direito fundamental que independe de autorizacao estatal.","ref":"Art. 5, XVI","note":"Todos podem reunir-se pacificamente, sem armas, em locais abertos ao publico, independentemente de autorizacao.","exp":"O Art. 5, XVI garante o direito de reuniao pacifica em locais abertos ao publico, independentemente de autorizacao, bastando previo aviso a autoridade competente. Uma lei municipal que proiba manifestacoes em todas as pracas seria inconstitucional por esvaziar o conteudo essencial desse direito fundamental.","diff":"hard","boss":True},
        {"level":5,"q":"CASO PRATICO: O STF deve julgar um caso envolvendo conflito entre liberdade de expressao e direito a honra. Um jornalista publicou reportagem com informacoes verdadeiras mas prejudiciais a reputacao de um politico. Como resolver esse conflito?","o":["A liberdade de expressao sempre prevalece sobre a honra","A honra sempre prevalece sobre a liberdade de expressao","Deve-se aplicar a tecnica da ponderacao, avaliando proporcionalidade, interesse publico e veracidade das informacoes","O caso deve ser resolvido pela legislacao infraconstitucional apenas"],"a":2,"hint":"A colisao de direitos fundamentais exige tecnica hermeneutica especifica.","ref":"Art. 5, IV, V, IX, X e principio da proporcionalidade","note":"Conflitos entre direitos fundamentais sao resolvidos pela ponderacao.","exp":"Quando dois direitos fundamentais colidem, o STF aplica a tecnica da ponderacao (proporcionalidade). Nao ha hierarquia absoluta entre direitos fundamentais. No caso, deve-se avaliar: (1) veracidade da informacao, (2) interesse publico, (3) forma da publicacao, (4) proporcionalidade da restricao. Informacoes verdadeiras sobre agentes publicos gozam de maior protecao constitucional.","diff":"hard","boss":True},
    # ── FILL-IN-BLANK QUESTIONS ───────────────────────────────────────
    {"level":1,"type":"fill","q":"Complete: 'Todo poder emana do ______, que o exerce por meio de representantes eleitos ou diretamente.'","answer":"povo","hint":"Art. 1, paragrafo unico da CF/88.","ref":"Art. 1, paragrafo unico","note":"Todo poder emana do povo.","exp":"O principio da soberania popular e fundamento do Estado Democratico de Direito, estabelecendo que a legitimidade do poder politico tem origem no povo.","diff":"easy"},
    {"level":1,"type":"fill","q":"Complete: 'A Republica Federativa do Brasil tem como fundamentos: a soberania, a cidadania, a ______ da pessoa humana.'","answer":"dignidade","hint":"Art. 1, III da CF/88.","ref":"Art. 1, III","note":"A dignidade da pessoa humana e fundamento da Republica.","exp":"A dignidade da pessoa humana e um dos cinco fundamentos da Republica Federativa do Brasil, funcionando como valor-fonte de todo o ordenamento juridico.","diff":"easy"},
    {"level":2,"type":"fill","q":"Complete: 'A casa e asilo ______ do individuo, ninguem nela podendo penetrar sem consentimento do morador.'","answer":"inviolavel","hint":"Art. 5, XI da CF/88.","ref":"Art. 5, XI","note":"A casa e asilo inviolavel do individuo.","exp":"A inviolabilidade de domicilio e direito fundamental que protege a esfera de privacidade do individuo, admitindo excecoes apenas nas hipoteses taxativas da Constituicao.","diff":"easy"},
    {"level":3,"type":"fill","q":"Complete: 'Conceder-se-a habeas corpus sempre que alguem sofrer ou se achar ameacado de sofrer violencia ou coacao em sua liberdade de ______.'","answer":"locomocao","hint":"Art. 5, LXVIII da CF/88.","ref":"Art. 5, LXVIII","note":"O habeas corpus protege a liberdade de locomocao.","exp":"O habeas corpus e o remedio constitucional mais antigo, destinado especificamente a proteger o direito de ir e vir contra ilegalidade ou abuso de poder.","diff":"medium"},
    {"level":4,"type":"fill","q":"Complete: 'A saude e direito de todos e dever do ______.'","answer":"estado","hint":"Art. 196 da CF/88.","ref":"Art. 196","note":"A saude e direito de todos e dever do Estado.","exp":"O Art. 196 estabelece a saude como direito social fundamental, impondo ao Estado o dever de garanti-la mediante politicas sociais e economicas que visem a reducao do risco de doenca.","diff":"easy"},
    {"level":1,"type":"tf","q":"A Constituicao de 1988 e chamada de Constituicao Cidada.","o":["Verdadeiro","Falso"],"a":0,"hint":"Ulysses Guimaraes a batizou com esse apelido.","ref":"Historico da CF/88","note":"A CF/88 ficou conhecida como Constituicao Cidada.","exp":"O presidente da Assembleia Constituinte, Ulysses Guimaraes, denominou-a Constituicao Cidada pela ampla protecao aos direitos fundamentais.","diff":"easy"},
    {"level":2,"type":"tf","q":"O anonimato e permitido na manifestacao do pensamento segundo a CF/88.","o":["Verdadeiro","Falso"],"a":1,"hint":"A Constituicao veda expressamente o anonimato.","ref":"Art. 5, IV","note":"E livre a manifestacao do pensamento, sendo vedado o anonimato.","exp":"A vedacao ao anonimato visa permitir a responsabilizacao por eventuais danos causados pela manifestacao.","diff":"easy"},
    {"level":2,"type":"tf","q":"A propriedade privada e um direito absoluto na Constituicao de 1988.","o":["Verdadeiro","Falso"],"a":1,"hint":"A Constituicao condiciona a propriedade a algo.","ref":"Art. 5, XXIII","note":"A propriedade deve atender a sua funcao social.","exp":"A funcao social e condicao intrinseca do exercicio do direito de propriedade, nao mera restricao externa.","diff":"easy"},
    {"level":3,"type":"tf","q":"O habeas corpus pode ser impetrado apenas por advogado com OAB.","o":["Verdadeiro","Falso"],"a":1,"hint":"O habeas corpus tem legitimidade ativa universal.","ref":"Art. 5, LXVIII","note":"Qualquer pessoa pode impetrar habeas corpus.","exp":"O habeas corpus e remedio de legitimidade universal, podendo ser impetrado por qualquer pessoa, inclusive o proprio paciente.","diff":"easy"},
    {"level":3,"type":"tf","q":"O mandado de injuncao serve para combater a omissao legislativa.","o":["Verdadeiro","Falso"],"a":0,"hint":"Quando falta norma regulamentadora, qual remedio usar?","ref":"Art. 5, LXXI","note":"O mandado de injuncao combate a falta de norma regulamentadora.","exp":"O instituto existe para enfrentar inercia normativa capaz de bloquear o exercicio efetivo de direitos constitucionais.","diff":"easy"},
    {"level":4,"type":"tf","q":"A assistencia social exige contribuicao previa a seguridade social.","o":["Verdadeiro","Falso"],"a":1,"hint":"A assistencia social tem natureza distinta da previdencia.","ref":"Art. 203","note":"A assistencia social independe de contribuicao previa.","exp":"Diferentemente da previdencia social, a assistencia social nao depende de contribuicao previa.","diff":"easy"},
    {"level":4,"type":"tf","q":"O FGTS e uma garantia constitucional do trabalhador.","o":["Verdadeiro","Falso"],"a":0,"hint":"O FGTS esta no Art. 7.","ref":"Art. 7, III","note":"O FGTS integra o rol de garantias constitucionais do trabalho.","exp":"A Constituicao incorpora instrumentos de protecao social do trabalho, entre eles o FGTS.","diff":"easy"},
    {"level":5,"type":"tf","q":"Brasileiro nato pode ser extraditado em caso de crime hediondo.","o":["Verdadeiro","Falso"],"a":1,"hint":"A Constituicao e categorica quanto ao brasileiro nato.","ref":"Art. 5, LI","note":"Nenhum brasileiro nato sera extraditado.","exp":"A protecao do brasileiro nato contra extradicao e absoluta, independentemente da natureza do crime.","diff":"normal"},
    {"level":5,"type":"tf","q":"A ordem judicial permite ingresso em domicilio a qualquer hora do dia ou da noite.","o":["Verdadeiro","Falso"],"a":1,"hint":"Ha limitacao temporal expressa na Constituicao.","ref":"Art. 5, XI","note":"A ordem judicial so autoriza ingresso durante o dia.","exp":"A garantia domiciliar estabelece limite expresso para o cumprimento de ordem judicial, preservando a intimidade domiciliar noturna.","diff":"normal"},

]

MANIFEST = {
    "name": "Arena Constitucional",
    "short_name": "A3ILPB",
    "description": "Quiz juridico competitivo sobre direitos fundamentais da Constituicao de 1988.",
    "start_url": "/", "scope": "/", "display": "standalone",
    "background_color": "#04080f", "theme_color": "#1565c0",
    "icons": [{"src": "/icon.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}],
}

ICON_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'>
<defs><linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='#02040a'/><stop offset='100%' stop-color='#0a1528'/></linearGradient></defs>
<rect width='512' height='512' rx='112' fill='url(#bg)'/>
<rect x='44' y='44' width='424' height='424' rx='96' fill='none' stroke='#1565c0' stroke-width='18'/>
<text x='256' y='210' text-anchor='middle' font-size='110' font-family='Georgia,serif' fill='#ffffff'>A3</text>
<text x='256' y='316' text-anchor='middle' font-size='78' font-family='Trebuchet MS,sans-serif' font-weight='700' fill='#c8a000'>CF88</text>
</svg>"""

SERVICE_WORKER = """const CACHE_NAME='a3ilpb-v1774407760';
/* NUNCA cacheia o HTML principal — sempre busca fresco do servidor */
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);
  /* API e pagina principal: sempre rede, sem cache */
  if(u.pathname==='/'||u.pathname==='/index.html'||u.pathname.startsWith('/api/')){
    e.respondWith(fetch(e.request,{cache:'no-store'}));return;
  }
  /* Demais assets: cache normal */
  e.respondWith(caches.match(e.request).then(c=>{
    if(c)return c;
    return fetch(e.request).then(n=>{
      if(n.ok){caches.open(CACHE_NAME).then(ca=>ca.put(e.request,n.clone()));}
      return n;
    });
  }));
});"""

HTML = r"""<!DOCTYPE html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover'>
<meta name='theme-color' content='#1565c0'>
<meta name='apple-mobile-web-app-capable' content='yes'>
<link rel='manifest' href='/manifest.webmanifest'>
<link rel='icon' href='/icon.svg' type='image/svg+xml'>
<title>__TITLE__</title>
<style>
/* ── TOKENS ─────────────────────────────────────────────────────── */
:root{
  --bg:#04080f;--card:#0d1520;--text:#e8edf5;--muted:#7a8aaa;
  --red:#1565c0;--red-dim:rgba(21,101,192,.12);--red-border:rgba(21,101,192,.45);
  --green:#00c875;--gold:#c8a000;--r:18px;
  --gold-bright:#ffd700;--bordeaux:#800020;
  --glow:0 0 0 1px rgba(21,101,192,.22),0 0 32px rgba(21,101,192,.12);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  color:var(--text);
  font-family:'Trebuchet MS','Segoe UI',system-ui,sans-serif;
  min-height:100vh;
  background:
    radial-gradient(ellipse at 8% 4%,rgba(21,101,192,.18) 0%,transparent 30%),
    radial-gradient(ellipse at 92% 96%,rgba(200,160,0,.10) 0%,transparent 30%),
    linear-gradient(180deg,#02040a,#05090f 50%,#02040a);
}

/* ── ANIMATIONS ──────────────────────────────────────────────────── */
@keyframes fadeUp   {from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
@keyframes fadeIn   {from{opacity:0}to{opacity:1}}
@keyframes slideIn  {from{opacity:0;transform:translateX(-20px)}to{opacity:1;transform:none}}
@keyframes scaleIn  {from{opacity:0;transform:scale(.92)}to{opacity:1;transform:scale(1)}}
@keyframes medalPop {0%{opacity:0;transform:translateY(40px) scale(.7)} 60%{transform:translateY(-6px) scale(1.08)} 100%{opacity:1;transform:none}}
@keyframes toastOut {to{opacity:0;transform:translateX(120%)}}
@keyframes shimmer  {0%{background-position:-200% center}100%{background-position:200% center}}
@keyframes neonBlink{0%,100%{text-shadow:0 0 8px rgba(21,101,192,.5)} 50%{text-shadow:0 0 22px rgba(21,101,192,1),0 0 44px rgba(21,101,192,.4)}}
@keyframes progressPulse{0%,100%{box-shadow:0 0 8px rgba(200,160,0,.5)}50%{box-shadow:0 0 18px rgba(200,160,0,.9)}}
@keyframes optSlide {from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}
@keyframes comboPop {0%{opacity:0;transform:translate(-50%,-50%) scale(.3)} 55%{transform:translate(-50%,-50%) scale(1.12)} 80%{transform:translate(-50%,-50%) scale(.97)} 100%{opacity:1;transform:translate(-50%,-50%) scale(1)}}
@keyframes comboDie {from{opacity:1} to{opacity:0;transform:translate(-50%,-50%) scale(1.2) translateY(-30px)}}

/* ── LAYOUT ──────────────────────────────────────────────────────── */
.page{width:min(1200px,calc(100% - 20px));margin:0 auto;padding:16px 0 50px}
.layout{display:grid;grid-template-columns:1.55fr .9fr;gap:16px;margin-top:16px}
.stack{display:grid;gap:16px;align-content:start}
.hidden{display:none!important}

/* ── BOX ─────────────────────────────────────────────────────────── */
.box{
  border:1px solid var(--red-border);
  border-radius:var(--r);
  box-shadow:var(--glow);
  background:linear-gradient(160deg,rgba(16,16,20,.97),rgba(9,9,12,.97));
}

/* ── HERO ────────────────────────────────────────────────────────── */
.hero{padding:28px 32px;position:relative;overflow:hidden;animation:fadeUp .5s ease both}
.hero::before{
  content:'';position:absolute;right:-80px;top:-80px;
  width:260px;height:260px;border-radius:50%;
  background:radial-gradient(circle,rgba(21,101,192,.25),transparent 68%);
  filter:blur(24px);pointer-events:none
}
.eyebrow{
  display:inline-flex;align-items:center;gap:6px;padding:6px 14px;
  border-radius:999px;background:var(--red-dim);border:1px solid var(--red-border);
  font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;color:#b8d4ff
}
.hero h1{
  font-family:Georgia,serif;font-size:clamp(1.9rem,5vw,3.6rem);
  line-height:1.05;margin:14px 0 10px;
  background:linear-gradient(135deg,#fff 35%,#3b82f6 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent
}
.hero p{color:#c8c8d8;line-height:1.75;max-width:800px}
.hero-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:18px}
.hero-stat{padding:14px;border-radius:14px;background:var(--red-dim);border:1px solid rgba(21,101,192,.2);animation:fadeUp .5s ease both}
.hero-stat strong{display:block;font-size:1.45rem;color:#fff;font-weight:900}
.hero-stat span{font-size:.8rem;color:var(--muted)}

/* ── PANEL ───────────────────────────────────────────────────────── */
.panel{padding:20px}
.panel h2{font-family:Georgia,serif;font-size:1.25rem;margin-bottom:14px;color:#fff}

/* ── CHIPS / PILLS ───────────────────────────────────────────────── */
.chip,.pill{
  display:inline-flex;align-items:center;padding:5px 11px;border-radius:999px;
  background:var(--red-dim);border:1px solid rgba(21,101,192,.35);
  color:#b8d4ff;font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em
}

/* ── LEVEL CARDS ─────────────────────────────────────────────────── */
.levels{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:10px;margin-top:14px}
.level-card{
  padding:14px;border-radius:14px;
  background:var(--red-dim);border:1px solid rgba(21,101,192,.18);
  animation:fadeUp .4s ease both
}
.level-card:nth-child(2){animation-delay:.05s}
.level-card:nth-child(3){animation-delay:.1s}
.level-card:nth-child(4){animation-delay:.15s}
.level-card:nth-child(5){animation-delay:.2s}
.level-card h3{font-size:.92rem;color:#fff;margin:7px 0 5px}
.level-card p{font-size:.8rem;color:var(--muted);line-height:1.6}

/* ── BUTTONS ─────────────────────────────────────────────────────── */
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  border:1px solid var(--red-border);border-radius:13px;
  padding:12px 18px;font-size:.93rem;font-weight:800;
  cursor:pointer;background:#0e0e12;color:var(--text);
  transition:transform .15s ease,box-shadow .15s ease,opacity .15s ease;
  user-select:none;-webkit-user-select:none
}
.btn:hover:not(:disabled){
  transform:translateY(-2px);
  box-shadow:0 0 0 1px rgba(21,101,192,.5),0 0 22px rgba(21,101,192,.22)
}
.btn:active:not(:disabled){transform:translateY(0)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:linear-gradient(135deg,#1565c0,#0d47a1);color:#fff;border-color:#1565c0}
.btn.secondary{background:rgba(21,101,192,.1);color:#b8d4ff;border-color:rgba(21,101,192,.38)}
.btn.ghost{background:rgba(255,255,255,.03);border-color:rgba(255,255,255,.1);color:var(--muted)}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}

/* ── HUD ─────────────────────────────────────────────────────────── */
.hud{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:10px;margin-bottom:14px}
.hud-box{padding:12px;border-radius:13px;background:var(--red-dim);border:1px solid rgba(21,101,192,.2)}
.lbl{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.09em}
.val{font-size:1.35rem;font-weight:900;color:#fff;margin-top:4px;transition:color .3s}
.val.fire{animation:neonBlink 1s ease infinite;color:#c8a000}

/* ── PROGRESS ────────────────────────────────────────────────────── */
.prog-wrap{height:8px;border-radius:999px;background:rgba(255,255,255,.05);overflow:hidden;margin-bottom:14px}
.prog-bar{
  height:100%;width:0%;
  background:linear-gradient(90deg,#c8a000,#1565c0,#3b82f6);
  transition:width .5s cubic-bezier(.4,0,.2,1);
  animation:progressPulse 2s ease infinite
}

/* ── QUESTION CARD ───────────────────────────────────────────────── */
.qcard{padding:22px;margin-bottom:14px}
.qcard.enter{animation:scaleIn .4s cubic-bezier(.22,1,.36,1) both}
.qtop{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.qnav{display:flex;justify-content:flex-end;margin-bottom:14px;position:sticky;top:8px;z-index:10}
.qcard h2{
  font-family:Georgia,serif;
  font-size:clamp(1.2rem,2.4vw,1.8rem);
  line-height:1.3;margin:12px 0 18px;color:#fff;
  animation:fadeUp .4s ease both
}

/* ── PHASE INDICATOR ─────────────────────────────────────────────── */
.phase-bar{
  display:flex;align-items:center;gap:10px;
  padding:10px 16px;border-radius:12px;margin-bottom:14px;
  font-size:.88rem;font-weight:800;letter-spacing:.03em;
  transition:background .4s,border-color .4s,color .4s
}
.phase-bar.reading{
  background:rgba(255,210,50,.08);border:1px solid rgba(255,210,50,.3);color:#ffe06a
}
.phase-bar.answering{
  background:rgba(21,101,192,.1);border:1px solid rgba(21,101,192,.4);color:#b8d4ff
}
.phase-bar.done-ok{
  background:rgba(0,213,142,.1);border:1px solid rgba(0,213,142,.4);color:#80ffda
}
.phase-bar.done-no{
  background:rgba(128,0,32,.1);border:1px solid rgba(128,0,32,.4);color:#d9a0b0
}
.phase-cd{
  margin-left:auto;font-size:1.2rem;font-weight:900;color:#fff;min-width:36px;text-align:right;
  transition:color .3s
}
.phase-cd.urgent{color:#c8a000;animation:neonBlink .6s ease infinite}

/* ── OPTIONS ─────────────────────────────────────────────────────── */
.options{display:grid;gap:10px}
.option{
  width:100%;text-align:left;padding:14px 16px;border-radius:13px;
  cursor:pointer;font-size:.94rem;font-weight:700;
  background:linear-gradient(160deg,#0b111e,#080e18);
  color:var(--text);border:1px solid var(--red-border);
  transition:transform .15s ease,box-shadow .15s ease,background .2s,border-color .2s;
  animation:optSlide .38s ease forwards;
  user-select:none;-webkit-user-select:none
}
.option:nth-child(2){animation-delay:.08s}
.option:nth-child(3){animation-delay:.16s}
.option:nth-child(4){animation-delay:.24s}
.option:hover:not(:disabled){
  transform:translateX(4px);
  box-shadow:0 0 0 2px rgba(21,101,192,.7),0 0 24px rgba(21,101,192,.28),0 0 44px rgba(21,101,192,.12);
  border-color:rgba(21,101,192,.8);
}
/* glow pulsante aplicado via classe JS para nao re-disparar optSlide */
.option.glow-pulse{
  animation:btnGlow 2s ease infinite !important;
}
@keyframes btnGlow{
  0%,100%{box-shadow:0 0 0 1px rgba(21,101,192,.5),0 0 14px rgba(21,101,192,.2)}
  50%{box-shadow:0 0 0 2px rgba(21,101,192,.9),0 0 30px rgba(21,101,192,.45),0 0 55px rgba(21,101,192,.18)}
}
.option b{
  display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;border-radius:50%;margin-right:10px;flex-shrink:0;
  background:rgba(21,101,192,.15);border:1px solid rgba(21,101,192,.4);
  color:#b8d4ff;font-size:.82rem;transition:background .2s,border-color .2s
}
.option.ok{
  background:rgba(0,213,142,.1);border-color:rgba(0,213,142,.6);
  box-shadow:0 0 0 1px rgba(0,213,142,.25),0 0 18px rgba(0,213,142,.15)
}
.option.ok b{background:rgba(0,213,142,.18);border-color:rgba(0,213,142,.5);color:#00d58e}
.option.no{background:rgba(128,0,32,.15);border-color:rgba(128,0,32,.65)}
.option.no b{background:rgba(128,0,32,.2);color:#d9a0b0}
.option.cut{opacity:.15;pointer-events:none;filter:grayscale(1)}

/* ── HELPERS ─────────────────────────────────────────────────────── */
.help-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin-top:14px}
.help-card{padding:12px;border-radius:14px;border:1px solid rgba(21,101,192,.18);background:rgba(21,101,192,.04)}
.help-card small{display:block;font-size:.76rem;color:var(--muted);margin-top:6px}

/* ── ASSIST / FEEDBACK ───────────────────────────────────────────── */
.info{margin-top:12px;padding:13px 16px;border-radius:13px;background:var(--red-dim);border:1px solid rgba(21,101,192,.25);color:#d0dff0;line-height:1.65;animation:fadeIn .3s ease both}
.feedback{
  margin-top:14px;padding:18px;border-radius:15px;
  border:1px solid rgba(21,101,192,.35);
  background:linear-gradient(160deg,rgba(8,16,32,.97),rgba(6,10,20,.97));
  animation:fadeUp .35s cubic-bezier(.22,1,.36,1) both
}
.feedback.ok{border-color:rgba(0,200,117,.4);background:linear-gradient(160deg,rgba(0,30,20,.97),rgba(4,14,12,.97))}
.feedback h3{font-size:1.05rem;color:#fff;margin-bottom:8px}
.feedback p{color:#b8b8c8;line-height:1.7;margin-top:5px}

function useSkip() {
  if (state.used.skip || state.answered || state.phase === 'idle') return;
  state.used.skip = true;
  if (ui.btnSkip) ui.btnSkip.disabled = true;
  playSound('skip');
  showAssist('⏭ Pergunta pulada! Sem pontos.');
  state.answered = true;
  clearInterval(state.ticker);
  state.wrongQs.push(state.deck[state.idx]);
  setPhase('done-no', 0);
  ui.btnNext.disabled = false;
}

function useExtraTime() {
  if (state.used.extraTime || state.answered || state.phase !== 'answering') return;
  state.used.extraTime = true;
  if (ui.btnExtraTime) ui.btnExtraTime.disabled = true;
  state.timeLeft += 15;
  showAssist('⏱ +15 segundos adicionados!');
  playSound('tick');
}

/* ── RANKING ─────────────────────────────────────────────────────── */
.rank-hdr{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.ranking{display:grid;gap:8px}
.rank-item{
  padding:12px;border-radius:13px;background:var(--red-dim);border:1px solid rgba(21,101,192,.2);
  animation:slideIn .3s ease both
}
.rank-item:nth-child(1){animation-delay:.04s}
.rank-item:nth-child(2){animation-delay:.08s}
.rank-item:nth-child(3){animation-delay:.12s}
.rank-item:nth-child(n+4){animation-delay:.16s}
.rank-item:nth-child(1) .rk-name{color:var(--gold)}
.rank-item:nth-child(2) .rk-name{color:#c8c8c8}
.rank-item:nth-child(3) .rk-name{color:#cd7f32}
.rk-name{font-size:.94rem;font-weight:800;color:#fff}
.rk-meta{display:block;font-size:.8rem;color:#7ab0e0;margin-top:3px}
.rk-sub{display:block;font-size:.76rem;color:var(--muted);margin-top:2px}

/* ── MEDALS ──────────────────────────────────────────────────────── */
.medal-list{display:grid;gap:8px}
.medal{
  padding:12px;border-radius:13px;
  background:rgba(255,215,0,.06);border:1px solid rgba(255,215,0,.24);
  animation:medalPop .5s cubic-bezier(.22,1,.36,1) both
}
.medal strong{color:var(--gold);font-size:.9rem}
.medal span{display:block;font-size:.78rem;color:var(--muted);margin-top:3px}

/* ── MEDAL TOAST (pop-up quando ganha) ───────────────────────────── */
#medal-toasts{position:fixed;bottom:22px;right:22px;z-index:900;display:grid;gap:10px;pointer-events:none}
.m-toast{
  padding:14px 18px;border-radius:16px;max-width:300px;
  background:linear-gradient(135deg,#181206,#0c0a04);
  border:1px solid rgba(255,215,0,.5);
  box-shadow:0 0 0 1px rgba(255,215,0,.15),0 8px 30px rgba(0,0,0,.5),0 0 40px rgba(255,215,0,.1);
  animation:medalPop .5s cubic-bezier(.22,1,.36,1) both;
  color:#fff
}
.m-toast.out{animation:toastOut .35s ease forwards}
.m-toast-head{font-size:.8rem;color:#c8a800;font-weight:800;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.m-toast-name{font-size:.96rem;font-weight:900;color:var(--gold)}
.m-toast-desc{font-size:.8rem;color:#a08820;margin-top:3px;line-height:1.4}

/* ── COMBO BANNER ────────────────────────────────────────────────── */
#combo-banner{
  position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
  z-index:950;pointer-events:none;text-align:center;
  font-family:Georgia,serif;font-weight:900;line-height:1;
  text-shadow:0 0 30px currentColor,0 0 60px currentColor;
  display:none
}
#combo-banner.show{display:block;animation:comboPop .45s cubic-bezier(.22,1,.36,1) both}
#combo-banner.hide{animation:comboDie .5s ease forwards}

/* ── RESULT ──────────────────────────────────────────────────────── */
.result-card{padding:22px}
.result-card h2{font-family:Georgia,serif;font-size:1.45rem;color:#fff;margin-bottom:4px}
.big-score{
  font-size:clamp(2.4rem,7vw,4rem);font-weight:900;margin:10px 0 6px;
  background:linear-gradient(90deg,#fff 0%,#c8a000 40%,#fff 60%,#3b82f6 100%);
  background-size:200% auto;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:shimmer 3s linear infinite
}
.result-card>p{color:#a8a8be;line-height:1.7;margin-bottom:14px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin:14px 0}
.stat-box{padding:12px;border-radius:12px;background:var(--red-dim);border:1px solid rgba(21,101,192,.2);text-align:center}
.stat-box.g{background:rgba(0,213,142,.07);border-color:rgba(0,213,142,.25)}
.stat-box .sv{display:block;font-size:1.5rem;font-weight:900;color:#fff}
.stat-box.g .sv{color:var(--green)}
.stat-box .sl{display:block;font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-top:3px}
.wrong-list{margin-top:12px;display:grid;gap:8px}
.wrong-item{padding:10px 13px;border-radius:11px;background:rgba(128,0,32,.07);border:1px solid rgba(128,0,32,.2);font-size:.84rem;color:#ccc;line-height:1.5}
.wrong-item b{color:#c07080;display:block;font-size:.8rem;margin-bottom:3px}
.wrong-correct{color:var(--green);font-size:.8rem;margin-top:4px;display:block}
.save-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.save-row input{
  flex:1 1 190px;min-width:0;border:1px solid var(--red-border);border-radius:11px;
  padding:11px 13px;background:rgba(255,255,255,.03);color:var(--text);font-size:.93rem;outline:none;
  transition:border-color .2s
}
.save-row input:focus{border-color:rgba(21,101,192,.7)}
.save-row input::placeholder{color:var(--muted)}
.empty{padding:13px;border:1px dashed rgba(21,101,192,.28);border-radius:12px;color:var(--muted);font-size:.85rem}

@media(max-width:900px){.layout{grid-template-columns:1fr}}
@media(max-width:600px){
  .page{width:100%;padding:10px 8px 40px}
  .hero{padding:18px}
  .panel,.qcard,.feedback,.result-card{padding:15px}
  .save-row,.actions{flex-direction:column}
}


/* ── AUTH WALL ───────────────────────────────────────────────────── */
#auth-wall{
  position:fixed;inset:0;z-index:3000;
  display:flex;align-items:center;justify-content:center;
  background:
    radial-gradient(ellipse at 15% 10%,rgba(21,101,192,.25) 0%,transparent 35%),
    radial-gradient(ellipse at 85% 90%,rgba(200,160,0,.12) 0%,transparent 35%),
    linear-gradient(180deg,#02040a,#060b14 50%,#02040a);
  padding:16px;overflow-y:auto;
  animation:fadeIn .4s ease both;
}
.auth-box{
  width:min(440px,100%);
  background:linear-gradient(160deg,rgba(13,18,28,.98),rgba(8,12,20,.98));
  border:1px solid rgba(21,101,192,.35);
  border-radius:22px;
  box-shadow:0 0 0 1px rgba(21,101,192,.15),0 24px 64px rgba(0,0,0,.6),0 0 60px rgba(21,101,192,.1);
  padding:28px 28px 24px;
  animation:fadeUp .45s cubic-bezier(.22,1,.36,1) both;
}
.auth-logo{text-align:center;margin-bottom:22px}
.al-icon{
  font-size:3rem;display:block;margin-bottom:10px;
  filter:drop-shadow(0 0 16px rgba(21,101,192,.6));
  animation:pulse 3s ease infinite;
}
.auth-logo h1{
  font-family:Georgia,serif;
  font-size:clamp(1.5rem,4vw,2rem);
  font-weight:900;
  background:linear-gradient(135deg,#fff 30%,#3b82f6 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  line-height:1.15;margin-bottom:6px;
}
.auth-logo p{color:#7a8aaa;font-size:.85rem;line-height:1.5}
.auth-tabs{
  display:flex;gap:6px;
  background:rgba(255,255,255,.04);
  border-radius:12px;padding:5px;
  margin-bottom:20px;
}
.auth-tab{
  flex:1;padding:10px;border-radius:9px;
  background:transparent;border:none;
  color:#7a8aaa;font-size:.9rem;font-weight:700;
  cursor:pointer;transition:all .22s cubic-bezier(.22,1,.36,1);
}
.auth-tab.active{
  background:linear-gradient(135deg,#1565c0,#0d47a1);
  color:#fff;
  box-shadow:0 4px 14px rgba(21,101,192,.4);
}
.auth-field{margin-bottom:14px}
.auth-field label{
  display:block;font-size:.75rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.09em;
  color:#7a8aaa;margin-bottom:7px;
}
.auth-field input{
  width:100%;padding:13px 14px;
  border-radius:12px;
  background:rgba(255,255,255,.05);
  border:1px solid rgba(21,101,192,.28);
  color:#e8edf5;font-size:.93rem;outline:none;
  transition:border-color .2s,box-shadow .2s;
}
.auth-field input:focus{
  border-color:rgba(59,130,246,.7);
  box-shadow:0 0 0 3px rgba(21,101,192,.15);
}
.auth-field input::placeholder{color:#4a5568}
.auth-error{
  color:#f87171;font-size:.82rem;font-weight:700;
  min-height:18px;margin-bottom:8px;
  animation:fadeIn .2s ease both;
}
.auth-success{
  color:#34d399;font-size:.82rem;font-weight:700;
  min-height:18px;margin-bottom:8px;
}
.auth-submit{
  width:100%;padding:14px;border-radius:13px;
  background:linear-gradient(135deg,#1565c0,#0d47a1);
  color:#fff;font-size:.95rem;font-weight:800;
  border:none;cursor:pointer;
  box-shadow:0 4px 20px rgba(21,101,192,.45);
  transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .18s ease;
  margin-top:4px;position:relative;overflow:hidden;
}
.auth-submit:hover{
  transform:translateY(-2px);
  box-shadow:0 6px 28px rgba(21,101,192,.6);
}
.auth-submit:active{transform:scale(.98)}
.auth-submit:disabled{opacity:.5;cursor:not-allowed;transform:none}
.auth-guest{
  text-align:center;margin-top:16px;
  padding-top:14px;border-top:1px solid rgba(255,255,255,.07);
}
.auth-guest button{
  background:none;border:none;
  color:#4a5568;font-size:.82rem;
  cursor:pointer;text-decoration:underline;
  text-underline-offset:3px;transition:color .2s;
}
.auth-guest button:hover{color:#7a8aaa}
.auth-avatar-grid{
  display:grid;grid-template-columns:repeat(3,1fr);
  gap:8px;margin-top:4px;
}
.auth-av-btn{
  padding:12px 8px;border-radius:12px;
  background:rgba(255,255,255,.04);
  border:1.5px solid rgba(255,255,255,.09);
  color:#e8edf5;font-size:.78rem;font-weight:700;
  cursor:pointer;text-align:center;
  transition:all .2s cubic-bezier(.22,1,.36,1);
}
.auth-av-btn .av-icon{font-size:1.5rem;display:block;margin-bottom:4px}
.auth-av-btn:hover{
  background:rgba(21,101,192,.15);
  border-color:rgba(59,130,246,.5);
  transform:translateY(-2px);
}
.auth-av-btn.selected{
  background:rgba(21,101,192,.2);
  border-color:#1565c0;
  box-shadow:0 0 0 2px rgba(21,101,192,.35);
}
/* ── END AUTH WALL ───────────────────────────────────────────────── */

/* ── PROFILE BAR ────────────────────────────────────────────────────── */
.profile-bar{
  display:flex;align-items:center;gap:14px;padding:14px 18px;
  margin-bottom:12px;border-radius:var(--r);
  background:linear-gradient(160deg,rgba(13,21,32,.97),rgba(8,14,24,.97));
  border:1px solid var(--red-border);box-shadow:var(--glow);
  flex-wrap:wrap;animation:fadeUp .4s ease both
}
.profile-avatar{font-size:2rem;cursor:pointer;transition:transform .2s}
.profile-avatar:hover{transform:scale(1.15)}
.profile-info{flex:1;min-width:120px}
.profile-name{font-weight:900;font-size:1rem;color:#fff}
.profile-title{font-size:.78rem;color:var(--muted)}
.xp-wrap{flex:1;min-width:180px}
.xp-label{font-size:.72rem;color:var(--muted);margin-bottom:4px;display:flex;justify-content:space-between}
.xp-bar-bg{height:10px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden}
.xp-bar-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#1565c0,#c8a000);transition:width .6s cubic-bezier(.4,0,.2,1)}
.streak-badge{
  display:flex;align-items:center;gap:6px;padding:6px 14px;
  border-radius:99px;background:rgba(200,160,0,.10);
  border:1px solid rgba(200,160,0,.35);font-size:.82rem;font-weight:800;color:#c8a000
}
.profile-actions{display:flex;gap:8px}
.icon-btn{
  width:38px;height:38px;border-radius:50%;border:1px solid rgba(255,255,255,.12);
  background:rgba(255,255,255,.04);color:var(--muted);cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:1.1rem;
  transition:background .2s,border-color .2s
}
.icon-btn:hover{background:rgba(21,101,192,.12);border-color:var(--red-border);color:#fff}

/* ── GAME MODE SELECT ───────────────────────────────────────────────── */
.mode-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:14px 0}
.mode-card{
  padding:18px;border-radius:16px;cursor:pointer;
  background:linear-gradient(160deg,rgba(16,16,20,.97),rgba(9,9,12,.97));
  border:1px solid var(--red-border);transition:transform .2s,box-shadow .2s,border-color .2s;
  text-align:center;position:relative;overflow:hidden
}
.mode-card:hover:not(.locked){transform:translateY(-3px);box-shadow:0 0 0 1px rgba(21,101,192,.5),0 0 30px rgba(21,101,192,.2)}
.mode-card.active{border-color:#1565c0;box-shadow:0 0 0 2px rgba(21,101,192,.4),0 0 30px rgba(21,101,192,.2)}
.mode-card.locked{opacity:.5;cursor:not-allowed;filter:grayscale(.5)}
.mode-card .mode-icon{font-size:2.2rem;margin-bottom:8px}
.mode-card h3{font-size:1rem;color:#fff;margin-bottom:4px}
.mode-card p{font-size:.78rem;color:var(--muted);line-height:1.5}
.mode-card .lock-badge{
  position:absolute;top:8px;right:8px;
  padding:3px 8px;border-radius:99px;background:rgba(255,255,255,.08);
  font-size:.68rem;color:var(--muted)
}

/* ── SETTINGS MODAL ─────────────────────────────────────────────────── */
.modal-overlay{
  position:fixed;inset:0;z-index:1000;
  background:rgba(0,0,0,.7);backdrop-filter:blur(6px);
  display:flex;align-items:center;justify-content:center;
  animation:fadeIn .2s ease both
}
.modal-content{
  width:min(480px,calc(100% - 30px));max-height:85vh;overflow-y:auto;
  padding:24px;border-radius:20px;
  background:linear-gradient(160deg,#141418,#0a0a0e);
  border:1px solid var(--red-border);box-shadow:0 0 60px rgba(21,101,192,.15)
}
.modal-content h2{font-family:Georgia,serif;font-size:1.3rem;margin-bottom:16px;color:#fff}
.modal-close{
  float:right;width:32px;height:32px;border-radius:50%;border:none;
  background:rgba(21,101,192,.15);color:#7ab0e0;cursor:pointer;font-size:1.1rem
}
.setting-group{margin-bottom:18px}
.setting-group label{display:block;font-size:.82rem;color:var(--muted);margin-bottom:8px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.theme-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.theme-btn{
  padding:10px;border-radius:12px;border:2px solid rgba(255,255,255,.1);
  cursor:pointer;text-align:center;font-size:.78rem;font-weight:700;
  transition:border-color .2s,transform .2s
}
.theme-btn:hover{transform:scale(1.05)}
.theme-btn.active{border-color:#1565c0}
.avatar-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.avatar-btn{
  padding:12px 8px;border-radius:12px;border:2px solid rgba(255,255,255,.1);
  cursor:pointer;text-align:center;font-size:1.6rem;
  transition:border-color .2s,transform .2s
}
.avatar-btn:hover{transform:scale(1.1)}
.avatar-btn.active{border-color:#1565c0}
.avatar-btn span{display:block;font-size:.68rem;color:var(--muted);margin-top:4px}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0}
.toggle-row span{font-size:.88rem;color:#ccc}
.toggle{
  width:48px;height:26px;border-radius:99px;border:none;cursor:pointer;
  background:rgba(255,255,255,.12);position:relative;transition:background .2s
}
.toggle.on{background:rgba(21,101,192,.5)}
.toggle::after{
  content:'';position:absolute;top:3px;left:3px;width:20px;height:20px;
  border-radius:50%;background:#fff;transition:transform .2s
}
.toggle.on::after{transform:translateX(22px)}

/* ── LEVEL-UP OVERLAY ───────────────────────────────────────────────── */
.levelup-overlay{
  position:fixed;inset:0;z-index:1100;
  background:rgba(0,0,0,.85);backdrop-filter:blur(8px);
  display:flex;align-items:center;justify-content:center;
  animation:fadeIn .3s ease both
}
.levelup-card{
  text-align:center;padding:40px;border-radius:24px;
  background:linear-gradient(160deg,#1a1206,#0c0804);
  border:2px solid rgba(255,215,0,.5);
  box-shadow:0 0 80px rgba(255,215,0,.2);
  animation:medalPop .6s cubic-bezier(.22,1,.36,1) both
}
.levelup-card .lu-icon{font-size:4rem;margin-bottom:12px}
.levelup-card .lu-title{font-family:Georgia,serif;font-size:1.6rem;color:#ffd700;margin-bottom:6px}
.levelup-card .lu-subtitle{font-size:1rem;color:#c8a800}
.levelup-card .lu-desc{font-size:.85rem;color:var(--muted);margin-top:10px}

/* ── STREAK NOTIFICATION ────────────────────────────────────────────── */
.streak-notif{
  position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:1050;
  padding:14px 24px;border-radius:16px;
  background:linear-gradient(135deg,#030a18,#050d20);
  border:1px solid rgba(200,160,0,.5);
  box-shadow:0 0 40px rgba(200,160,0,.2);
  animation:medalPop .5s cubic-bezier(.22,1,.36,1) both;
  text-align:center;color:#c8a000;font-weight:800
}
.streak-notif .sn-fire{font-size:1.4rem}
.streak-notif .sn-text{font-size:.9rem}
.streak-notif .sn-xp{font-size:.78rem;color:#ff9800;margin-top:4px}

/* ── KNOWLEDGE LIBRARY ──────────────────────────────────────────────── */
.lib-item{
  padding:12px;border-radius:12px;margin-bottom:8px;
  background:rgba(21,101,192,.05);border:1px solid rgba(21,101,192,.15);
  font-size:.84rem;color:#ccc;line-height:1.5
}
.lib-item b{color:#7ab0e0;display:block;margin-bottom:4px}
.lib-item .lib-answer{color:var(--green);font-size:.8rem;margin-top:4px}
.lib-clear{margin-top:8px}

/* ── SHARE BUTTON ───────────────────────────────────────────────────── */
.btn.share{background:linear-gradient(135deg,#1877f2,#0d47a1);border-color:#1877f2;color:#fff}

/* ── EVOLUTION CHART ────────────────────────────────────────────────── */
.evo-chart{width:100%;height:120px;border-radius:12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08)}

/* ── TRUE/FALSE OPTIONS ─────────────────────────────────────────────── */
.options.tf-mode{grid-template-columns:1fr 1fr;gap:14px}
.options.tf-mode .option{text-align:center;padding:18px;font-size:1.05rem}

/* ── ANTI-GUESS WARNING ─────────────────────────────────────────────── */
.anti-guess{
  padding:8px 14px;border-radius:10px;margin-top:8px;
  background:rgba(200,160,0,.08);border:1px solid rgba(200,160,0,.3);
  font-size:.82rem;color:#c8a000;font-weight:700
}

/* ── SPEEDRUN TIMER ─────────────────────────────────────────────────── */
.speedrun-timer{
  position:fixed;top:0;left:0;right:0;height:6px;z-index:800;
  background:rgba(255,255,255,.05)
}
.speedrun-timer-fill{
  height:100%;background:linear-gradient(90deg,#1565c0,#c8a000);
  transition:width .5s linear
}

/* ── UNLOCK NOTIFICATION ────────────────────────────────────────────── */
.unlock-notif{
  padding:12px 16px;border-radius:14px;margin-bottom:8px;
  background:linear-gradient(135deg,rgba(168,0,255,.1),rgba(100,0,200,.05));
  border:1px solid rgba(168,0,255,.3);
  animation:medalPop .5s cubic-bezier(.22,1,.36,1) both;
  font-size:.85rem;color:#ce93d8
}

/* ── ENHANCED STATS ─────────────────────────────────────────────────── */
.stat-grid-ext{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin:14px 0}
.stat-box-ext{padding:10px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);text-align:center}
.stat-box-ext .sv{display:block;font-size:1.2rem;font-weight:900;color:#fff}
.stat-box-ext .sl{display:block;font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:3px}

/* ── ENVIRONMENT THEMES ─────────────────────────────────────────────── */
body.theme-light{--bg:#f0f4fa;--card:#ffffff;--text:#1a2030;--muted:#606880;--red:#1565c0;--red-dim:rgba(21,101,192,.08);--red-border:rgba(21,101,192,.3);--green:#00a868;--gold:#b8860b}
body.theme-light{background:linear-gradient(180deg,#f0f4fa,#e8eef8);color:var(--text)}
body.theme-light .box{background:linear-gradient(160deg,rgba(255,255,255,.97),rgba(248,250,255,.97))}
body.theme-light .option{background:linear-gradient(160deg,#f8f9ff,#f0f4fa);color:var(--text)}

body.theme-stf{--bg:#060e1c;--card:#0d1a30;--red:#c8a000;--red-dim:rgba(200,160,0,.1);--red-border:rgba(200,160,0,.35);--gold:#ffd700;--green:#4caf50}
body.theme-stf{background:linear-gradient(180deg,#060e1c,#040a14);color:var(--text)}
body.theme-stf .box{background:linear-gradient(160deg,rgba(13,26,48,.97),rgba(8,16,32,.97));border-color:rgba(200,160,0,.35)}
body.theme-stf .btn.primary{background:linear-gradient(135deg,#c8a000,#8a6e00);border-color:#c8a000}

body.theme-neon{--bg:#0a000a;--card:#1a0a2a;--red:#a855f7;--red-dim:rgba(168,85,247,.1);--red-border:rgba(168,85,247,.35);--gold:#e040fb;--green:#00e676}
body.theme-neon{background:linear-gradient(180deg,#0a000a,#0e0020);color:var(--text)}
body.theme-neon .box{background:linear-gradient(160deg,rgba(26,10,42,.97),rgba(14,4,28,.97));border-color:rgba(168,85,247,.35)}
body.theme-neon .btn.primary{background:linear-gradient(135deg,#a855f7,#6a1b9a);border-color:#a855f7}



/* ── LIVES SYSTEM ──────────────────────────────────────────────────── */
.lives-bar{display:flex;gap:6px;align-items:center;margin-bottom:10px;justify-content:center}
.heart{font-size:1.6rem;transition:transform .3s,opacity .3s;filter:drop-shadow(0 0 4px rgba(21,101,192,.4))}
.heart.lost{opacity:.2;transform:scale(.7);filter:grayscale(1)}
.heart.breaking{animation:heartBreak .5s ease both}
@keyframes heartBreak{0%{transform:scale(1)}30%{transform:scale(1.3)}60%{transform:scale(.5);opacity:.4}100%{transform:scale(.7);opacity:.2}}

/* ── GOLDEN QUESTION ───────────────────────────────────────────────── */
.qcard.golden{border:2px solid rgba(255,215,0,.6);box-shadow:0 0 30px rgba(255,215,0,.2),0 0 60px rgba(255,215,0,.1)}
.golden-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:99px;background:linear-gradient(135deg,rgba(255,215,0,.2),rgba(255,215,0,.08));border:1px solid rgba(255,215,0,.4);color:#ffd700;font-size:.78rem;font-weight:800;animation:shimmer 2s linear infinite;background-size:200% auto}

/* ── BOSS QUESTION ─────────────────────────────────────────────────── */
.qcard.boss{border:2px solid rgba(168,0,255,.5);box-shadow:0 0 30px rgba(168,0,255,.2),0 0 60px rgba(168,0,255,.1)}
.boss-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 14px;border-radius:99px;background:linear-gradient(135deg,rgba(168,0,255,.2),rgba(168,0,255,.08));border:1px solid rgba(168,0,255,.4);color:#ce93d8;font-size:.82rem;font-weight:800}

/* ── FURY MODE ─────────────────────────────────────────────────────── */
.fury-active{animation:furyPulse 1s ease infinite}
@keyframes furyPulse{0%,100%{box-shadow:0 0 20px rgba(21,101,192,.3),0 0 40px rgba(200,160,0,.15)}50%{box-shadow:0 0 40px rgba(21,101,192,.5),0 0 80px rgba(200,160,0,.3)}}
.fury-banner{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:960;pointer-events:none;text-align:center;font-family:Georgia,serif;font-weight:900;font-size:4rem;color:#c8a000;text-shadow:0 0 40px #c8a000,0 0 80px rgba(200,160,0,.5);animation:comboPop .5s cubic-bezier(.22,1,.36,1) both}
.fury-overlay{position:fixed;inset:0;z-index:955;pointer-events:none;background:radial-gradient(ellipse at center,transparent 40%,rgba(21,101,192,.06) 100%);animation:furyPulse 2s ease infinite}

/* ── SUSPENSE ──────────────────────────────────────────────────────── */
.suspense-overlay{position:fixed;inset:0;z-index:970;pointer-events:none;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;animation:fadeIn .2s ease both}
.suspense-text{font-family:Georgia,serif;font-size:1.4rem;color:#ffd700;text-align:center;animation:neonBlink .8s ease infinite}

/* ── PARTICLES ─────────────────────────────────────────────────────── */
#particles-canvas{position:fixed;inset:0;z-index:980;pointer-events:none}

/* ── STAR BACKGROUND ───────────────────────────────────────────────── */
#star-canvas{position:fixed;inset:0;z-index:-2;pointer-events:none;opacity:.7}

/* ── SCORE EXPLOSION ───────────────────────────────────────────────── */
.score-burst{
  position:fixed;z-index:995;pointer-events:none;
  font-family:Georgia,serif;font-weight:900;font-size:2.2rem;
  color:#c8a000;text-shadow:0 0 20px rgba(200,160,0,.8),0 0 40px rgba(200,160,0,.4);
  animation:scoreBurst 1.2s cubic-bezier(.22,1,.36,1) forwards
}
@keyframes scoreBurst{
  0%{opacity:1;transform:scale(.4) translateY(0)}
  40%{opacity:1;transform:scale(1.25) translateY(-30px)}
  100%{opacity:0;transform:scale(1) translateY(-80px)}
}

/* ── ANIMATED BACKGROUND ───────────────────────────────────────────── */
#bg-symbols{position:fixed;inset:0;z-index:-1;pointer-events:none;overflow:hidden;opacity:.04}
.bg-sym{position:absolute;font-size:2rem;animation:bgFloat linear infinite;opacity:.5}
@keyframes bgFloat{0%{transform:translateY(110vh) rotate(0deg)}100%{transform:translateY(-10vh) rotate(360deg)}}

/* ── EPIC INTRO ────────────────────────────────────────────────────── */
.epic-intro{position:fixed;inset:0;z-index:2000;background:linear-gradient(180deg,#000,#020510,#000);display:flex;flex-direction:column;align-items:center;justify-content:center;animation:fadeIn .5s ease both}
.epic-intro .ei-icon{font-size:5rem;margin-bottom:20px;animation:medalPop .8s cubic-bezier(.22,1,.36,1) both}
.epic-intro .ei-title{font-family:Georgia,serif;font-size:clamp(1.6rem,4vw,2.8rem);color:#fff;text-align:center;margin-bottom:10px;animation:fadeUp .6s ease .3s both;background:linear-gradient(135deg,#fff,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.epic-intro .ei-sub{font-size:1rem;color:#c8a800;text-align:center;animation:fadeUp .6s ease .5s both;max-width:400px;line-height:1.6}
.epic-intro .ei-btn{margin-top:30px;animation:fadeUp .6s ease .8s both}
.epic-intro .ei-particles{position:absolute;inset:0;pointer-events:none;overflow:hidden}

/* ── SKILL TREE ────────────────────────────────────────────────────── */
.skill-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:14px 0}
.skill-card{padding:16px;border-radius:16px;cursor:pointer;background:linear-gradient(160deg,rgba(16,16,20,.97),rgba(9,9,12,.97));border:1px solid var(--red-border);transition:transform .2s,box-shadow .2s;text-align:center;position:relative}
.skill-card:hover{transform:translateY(-3px);box-shadow:0 0 20px rgba(21,101,192,.2)}
.skill-card.equipped{border-color:#ffd700;box-shadow:0 0 20px rgba(255,215,0,.2)}
.skill-card .sk-icon{font-size:2rem;margin-bottom:8px}
.skill-card h4{font-size:.92rem;color:#fff;margin-bottom:4px}
.skill-card p{font-size:.76rem;color:var(--muted);line-height:1.4}
.skill-card .sk-cost{font-size:.72rem;color:#ffd700;margin-top:8px;font-weight:800}

/* ── COINS ─────────────────────────────────────────────────────────── */
.coins-display{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:99px;background:rgba(255,215,0,.08);border:1px solid rgba(255,215,0,.2);font-size:.82rem;font-weight:800;color:#ffd700}
.coin-gain{position:fixed;z-index:990;pointer-events:none;font-weight:900;color:#ffd700;font-size:1.2rem;animation:coinFloat 1.5s ease forwards}
@keyframes coinFloat{0%{opacity:1;transform:translateY(0)}100%{opacity:0;transform:translateY(-60px)}}

/* ── STUDY MODE ────────────────────────────────────────────────────── */
.study-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:99px;background:rgba(0,213,142,.1);border:1px solid rgba(0,213,142,.3);color:#80ffda;font-size:.78rem;font-weight:800}

/* ── CONSTITUTION MAP ──────────────────────────────────────────────── */
.const-map{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:12px 0}
.map-item{padding:12px;border-radius:12px;background:rgba(21,101,192,.04);border:1px solid rgba(21,101,192,.15);text-align:center;transition:transform .2s}
.map-item:hover{transform:scale(1.03)}
.map-item .mi-icon{font-size:1.6rem;margin-bottom:6px}
.map-item .mi-name{font-size:.82rem;color:#fff;font-weight:700;margin-bottom:4px}
.map-item .mi-bar{height:6px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:6px}
.map-item .mi-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#1565c0,#00c875);transition:width .5s}
.map-item .mi-pct{font-size:.7rem;color:var(--muted);margin-top:4px}

/* ── NARRATOR BOX ──────────────────────────────────────────────────── */
.narrator-box{margin-top:10px;padding:12px 16px;border-radius:12px;background:linear-gradient(135deg,rgba(100,100,200,.06),rgba(100,100,200,.02));border:1px solid rgba(100,100,200,.2);font-size:.84rem;color:#b0b0d0;line-height:1.6;animation:fadeUp .4s ease both}
.narrator-box .nr-icon{font-size:1.1rem;margin-right:6px}

/* ── FILL-IN-BLANK ─────────────────────────────────────────────────── */
.fill-blank-input{width:100%;padding:14px 16px;border-radius:13px;border:2px solid var(--red-border);background:rgba(255,255,255,.03);color:var(--text);font-size:1rem;font-weight:700;outline:none;transition:border-color .3s;margin:12px 0}
.fill-blank-input:focus{border-color:#1565c0;box-shadow:0 0 20px rgba(21,101,192,.15)}
.fill-blank-input::placeholder{color:var(--muted);font-weight:400}

/* ── MOBILE OPTIMIZATIONS ──────────────────────────────────────────── */
@media(max-width:600px){
  .profile-bar{padding:10px 12px;gap:10px}
  .profile-avatar{font-size:1.6rem}
  .profile-info{min-width:80px}
  .profile-name{font-size:.88rem}
  .xp-wrap{min-width:120px}
  .hero h1{font-size:1.5rem!important}
  .hero p{font-size:.85rem}
  .hero-stats{grid-template-columns:repeat(2,1fr)}
  .hero-stat{padding:10px}
  .hero-stat strong{font-size:1.1rem}
  .help-grid{grid-template-columns:1fr 1fr}
  .help-card{padding:8px}
  .help-card .btn{font-size:.78rem;padding:8px 10px}
  .mode-grid{grid-template-columns:1fr 1fr}
  .mode-card{padding:12px}
  .mode-card .mode-icon{font-size:1.6rem}
  .hud{grid-template-columns:repeat(3,1fr)}
  .hud-box{padding:8px}
  .val{font-size:1.1rem}
  .options .option{padding:12px 14px;font-size:.88rem}
  .options .option b{width:26px;height:26px;font-size:.75rem;margin-right:8px}
  .skill-grid{grid-template-columns:1fr}
  .const-map{grid-template-columns:repeat(2,1fr)}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
  .lives-bar .heart{font-size:1.3rem}
  .btn{padding:10px 14px;font-size:.85rem}
  .result-card h2{font-size:1.2rem}
  .big-score{font-size:2rem!important}
  .feedback{padding:14px}
  .epic-intro .ei-icon{font-size:3.5rem}
  .streak-badge{padding:4px 10px;font-size:.75rem}
  .coins-display{font-size:.75rem;padding:3px 8px}
  .avatar-grid{grid-template-columns:repeat(3,1fr)}
  .theme-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:400px){
  .help-grid{grid-template-columns:1fr}
  .mode-grid{grid-template-columns:1fr}
  .hud{grid-template-columns:repeat(2,1fr)}
  .hero-stats{grid-template-columns:1fr}
}

/* ── TOUCH FRIENDLY ────────────────────────────────────────────────── */
@media(hover:none){
  .option{min-height:54px;touch-action:manipulation}
  .btn{min-height:50px;touch-action:manipulation}
  .option:hover{transform:none;box-shadow:none}
  .option:active{transform:scale(.97);background:rgba(21,101,192,.15);border-color:rgba(21,101,192,.7)}
  .btn:hover{transform:none}
  .btn:active{transform:scale(.97)}
}
/* garante que nao ha delay de 300ms no toque em todos os dispositivos */
button,.btn,.option,.mode-card,.avatar-btn,.theme-btn,.skill-card,.icon-btn{
  touch-action:manipulation;-webkit-tap-highlight-color:rgba(21,101,192,.2);cursor:pointer
}

/* ── SAFE AREA (notch) ─────────────────────────────────────────────── */
@supports(padding:env(safe-area-inset-top)){
  body{padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom);padding-left:env(safe-area-inset-left);padding-right:env(safe-area-inset-right)}
}

/* ═══════════════════════════════════════════════════════════════════════
   INVESTIGATION GAME STYLES v3 — Enhanced & Polished
   ═══════════════════════════════════════════════════════════════════════ */

@keyframes invFadeIn{from{opacity:0}to{opacity:1}}
@keyframes invSlideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
@keyframes invPop{0%{opacity:0;transform:scale(.82)}70%{transform:scale(1.04)}100%{opacity:1;transform:scale(1)}}
@keyframes invGlowPulse{0%,100%{box-shadow:0 0 12px rgba(139,92,246,.3)}50%{box-shadow:0 0 30px rgba(139,92,246,.7),0 0 55px rgba(139,92,246,.18)}}
@keyframes invBorderGlow{0%,100%{border-color:rgba(59,130,246,.25)}50%{border-color:rgba(59,130,246,.8)}}
@keyframes invPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
@keyframes invGlow{0%,100%{box-shadow:0 0 10px rgba(139,92,246,.3)}50%{box-shadow:0 0 30px rgba(139,92,246,.7),0 0 60px rgba(139,92,246,.2)}}
@keyframes invTimerUrgent{0%,100%{color:#ef4444}50%{color:#ff6b6b;text-shadow:0 0 20px rgba(239,68,68,.8)}}

.inv-overlay{
  position:fixed;inset:0;z-index:2500;
  background:linear-gradient(160deg,#030608 0%,#060a12 50%,#04060e 100%);
  display:flex;flex-direction:column;
  animation:invFadeIn .35s cubic-bezier(.22,1,.36,1) both;
  overflow-y:auto;
}
.inv-overlay *::-webkit-scrollbar{width:4px}
.inv-overlay *::-webkit-scrollbar-track{background:rgba(255,255,255,.03)}
.inv-overlay *::-webkit-scrollbar-thumb{background:rgba(139,92,246,.4);border-radius:999px}

/* HEADER */
.inv-header{
  background:linear-gradient(180deg,rgba(5,9,15,.99),rgba(8,14,24,.97));
  border-bottom:1px solid rgba(59,130,246,.2);
  box-shadow:0 2px 20px rgba(0,0,0,.5);
  padding:12px 16px;display:flex;align-items:center;
  gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:100;
}
.inv-back-btn{
  padding:7px 14px;border-radius:10px;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.12);color:#9ca3af;font-size:.82rem;
  font-weight:700;cursor:pointer;transition:all .2s ease;
}
.inv-back-btn:hover{background:rgba(255,255,255,.1);color:#fff}
.inv-header-title{font-weight:900;font-size:1rem;color:#fff;letter-spacing:.02em}
.inv-phase-indicator{
  padding:4px 12px;border-radius:999px;
  background:rgba(139,92,246,.15);border:1px solid rgba(139,92,246,.4);
  color:#a78bfa;font-size:.75rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.08em;
  animation:invPulse 2.5s ease infinite;
}
.inv-timer{
  margin-left:auto;font-size:1.1rem;font-weight:900;
  color:#a78bfa;min-width:48px;text-align:right;transition:color .3s;
}

/* SCREEN */
.inv-screen{transition:opacity .22s ease}
.inv-screen.hidden{display:none}

/* CONTAINERS */
.inv-lobby-container,.inv-waiting-container,.inv-vote-container,.inv-resultado-container,.inv-game-container{
  max-width:780px;margin:0 auto;padding:14px 14px 80px;
}

/* LOBBY HERO */
.inv-lobby-hero{text-align:center;padding:28px 20px 20px;animation:invSlideUp .5s cubic-bezier(.22,1,.36,1) both}
.inv-logo{font-size:3.5rem;margin-bottom:12px;animation:invPulse 3s ease infinite;display:inline-block}
.inv-title{
  font-family:Georgia,serif;font-size:clamp(1.6rem,4vw,2.4rem);font-weight:900;
  background:linear-gradient(135deg,#fff 30%,#a78bfa 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;
}
.inv-subtitle{color:#9ca3af;font-size:.9rem;line-height:1.7;max-width:500px;margin:0 auto}
.inv-lobby-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}

/* CARD */
.inv-card{
  background:linear-gradient(160deg,rgba(15,20,30,.98),rgba(9,12,20,.98));
  border:1px solid rgba(59,130,246,.15);border-radius:16px;padding:16px;
  box-shadow:0 4px 20px rgba(0,0,0,.3);
  animation:invSlideUp .35s cubic-bezier(.22,1,.36,1) both;
  transition:transform .2s ease,box-shadow .2s ease,border-color .25s ease;
}
.inv-card:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.4)}
.inv-card + .inv-card{animation-delay:.06s}
.inv-card h3{font-size:1rem;font-weight:800;color:#fff;margin-bottom:8px}
.inv-card h4{font-size:.82rem;font-weight:800;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}

/* INPUT */
.inv-input{
  width:100%;padding:12px 14px;border-radius:12px;
  background:rgba(255,255,255,.04);border:1px solid rgba(59,130,246,.25);
  color:#e8edf5;font-size:.92rem;outline:none;margin-bottom:10px;
  transition:border-color .2s,box-shadow .2s;
}
.inv-input:focus{border-color:rgba(59,130,246,.7);box-shadow:0 0 0 3px rgba(59,130,246,.12)}

/* BUTTONS */
.inv-btn-primary{
  width:100%;padding:12px 18px;border-radius:12px;
  background:linear-gradient(135deg,#1565c0,#0d47a1);color:#fff;
  font-weight:800;font-size:.92rem;border:none;cursor:pointer;
  transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .18s ease;
  box-shadow:0 4px 16px rgba(21,101,192,.4);position:relative;overflow:hidden;
}
.inv-btn-primary:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(21,101,192,.55)}
.inv-btn-primary:active{transform:scale(.98)}
.inv-btn-secondary{
  width:100%;padding:12px 18px;border-radius:12px;
  background:rgba(139,92,246,.12);color:#a78bfa;
  font-weight:800;font-size:.92rem;border:1px solid rgba(139,92,246,.35);
  cursor:pointer;transition:transform .18s ease,box-shadow .18s ease;margin-top:8px;
  position:relative;overflow:hidden;
}
.inv-btn-secondary:hover{transform:translateY(-2px);box-shadow:0 4px 18px rgba(139,92,246,.3)}
.inv-btn-ghost{
  padding:8px 14px;border-radius:10px;background:transparent;
  color:#6b7280;font-size:.82rem;border:1px solid rgba(255,255,255,.1);
  cursor:pointer;transition:color .2s,border-color .2s,background .2s;
}
.inv-btn-ghost:hover{color:#e8edf5;border-color:rgba(255,255,255,.25);background:rgba(255,255,255,.04)}

/* VOTE BUTTONS */
.inv-vote-btn{
  width:100%;padding:13px 16px;border-radius:12px;
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);
  color:#e8edf5;font-weight:700;font-size:.88rem;cursor:pointer;
  text-align:left;margin-bottom:8px;
  transition:transform .18s ease,border-color .2s,background .2s;
}
.inv-vote-btn:hover{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.4);transform:translateX(4px)}
.inv-vote-btn.selected{
  background:linear-gradient(135deg,rgba(59,130,246,.2),rgba(139,92,246,.15));
  border-color:rgba(59,130,246,.7);color:#93c5fd;
  box-shadow:0 0 14px rgba(59,130,246,.25);
  animation:invPop .3s cubic-bezier(.22,1,.36,1) both;
}
.inv-vote-btn.small{font-size:.8rem;padding:10px 12px}

/* SKILL BUTTONS */
.inv-skill-btn{
  width:100%;padding:9px 12px;border-radius:10px;
  background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.25);
  color:#c4b5fd;font-size:.8rem;font-weight:700;cursor:pointer;
  text-align:left;transition:all .2s ease;margin-bottom:4px;
}
.inv-skill-btn:hover:not(:disabled){background:rgba(139,92,246,.22);box-shadow:0 0 14px rgba(139,92,246,.3);transform:scale(1.02)}
.inv-skill-btn:disabled{opacity:.4;cursor:not-allowed}
.inv-skill-cd{font-size:.72rem;color:#6b7280}

/* COUNTDOWN RING */
.inv-countdown-ring{
  width:90px;height:90px;border-radius:50%;
  background:conic-gradient(#a78bfa var(--prog,100%),rgba(255,255,255,.06) 0);
  display:inline-flex;align-items:center;justify-content:center;
  font-size:1.8rem;font-weight:900;color:#fff;
  box-shadow:0 0 24px rgba(139,92,246,.4);
  transition:all .3s ease;animation:invGlowPulse 2s ease infinite;
}
.inv-countdown-ring.urgent{
  background:conic-gradient(#ef4444 var(--prog,100%),rgba(255,255,255,.06) 0);
  box-shadow:0 0 28px rgba(239,68,68,.5);color:#fca5a5;
  animation:invTimerUrgent .6s ease infinite,invGlowPulse 1s ease infinite;
}

/* TABS */
.inv-tabs{
  display:flex;gap:4px;background:rgba(255,255,255,.03);
  border-radius:12px;padding:4px;margin-bottom:12px;
}
.inv-tab{
  flex:1;padding:9px 12px;border-radius:9px;background:transparent;
  border:none;color:#6b7280;font-size:.82rem;font-weight:700;
  cursor:pointer;transition:all .2s ease;
}
.inv-tab.active{background:rgba(59,130,246,.2);color:#93c5fd;border:1px solid rgba(59,130,246,.3)}

/* ROOM CODE DISPLAY */
.inv-room-code-display{
  font-size:2rem;font-weight:900;letter-spacing:.15em;color:#a78bfa;
  padding:14px 20px;background:rgba(139,92,246,.1);
  border:2px dashed rgba(139,92,246,.4);border-radius:14px;
  display:inline-block;margin:12px 0;
  text-shadow:0 0 20px rgba(139,92,246,.5);
  animation:invGlowPulse 2s ease infinite;
}

/* CASE */
.inv-case-badge{
  display:inline-flex;align-items:center;gap:6px;
  padding:5px 12px;border-radius:999px;
  background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.3);
  color:#93c5fd;font-size:.75rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;
}
.inv-case-title{font-family:Georgia,serif;font-size:clamp(1.2rem,3vw,1.8rem);color:#fff;margin-bottom:12px;line-height:1.3}
.inv-case-historia{color:#c8c8d8;line-height:1.8;font-size:.9rem}
.inv-duvida-item{
  padding:8px 12px;border-radius:9px;
  background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.2);
  color:#fcd34d;font-size:.82rem;margin-bottom:6px;
}
.inv-envolvidos-list{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px}
.inv-envolvido-chip{
  display:inline-block;padding:5px 12px;border-radius:8px;
  background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.25);
  color:#93c5fd;font-size:.8rem;font-weight:700;
}

/* EVIDENCE */
.inv-evidence-item{
  padding:14px;border-radius:12px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
  margin-bottom:10px;
  transition:border-color .2s ease,background .2s ease,transform .2s ease;
}
.inv-evidence-item:hover{transform:translateX(4px);border-color:rgba(139,92,246,.4)}
.inv-evidence-item.contested{border-color:rgba(239,68,68,.35);background:rgba(239,68,68,.05)}
.inv-evidence-item.critical{border-color:rgba(245,158,11,.45);background:rgba(245,158,11,.07);box-shadow:0 0 14px rgba(245,158,11,.15)}
.inv-ev-header{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.inv-ev-title{font-weight:800;color:#fff;font-size:.88rem}
.inv-ev-desc{color:#9ca3af;font-size:.82rem;line-height:1.6;margin-top:6px}
.inv-ev-peso{padding:2px 8px;border-radius:6px;font-size:.72rem;font-weight:800;white-space:nowrap}
.inv-ev-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.inv-ev-btn{
  padding:5px 10px;border-radius:8px;
  background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.3);
  color:#93c5fd;font-size:.75rem;font-weight:700;cursor:pointer;transition:all .18s ease;
}
.inv-ev-btn:hover{background:rgba(59,130,246,.2);transform:scale(1.04)}
.inv-ev-btn.danger{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.3);color:#fca5a5}

/* PLAYERS */
.inv-player-row{
  display:flex;align-items:center;gap:8px;padding:8px 10px;
  border-radius:9px;background:rgba(255,255,255,.03);margin-bottom:6px;
  border:1px solid rgba(255,255,255,.06);transition:border-color .2s ease;
}
.inv-player-row:hover{border-color:rgba(59,130,246,.25)}
.inv-player-row-role{padding:3px 8px;border-radius:6px;font-size:.7rem;font-weight:800}
.inv-waiting-player{
  display:flex;align-items:center;gap:10px;padding:8px 12px;
  border-radius:10px;background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.07);margin-bottom:6px;
  animation:invSlideUp .3s cubic-bezier(.22,1,.36,1) both;
}
.inv-waiting-player.ready{border-color:rgba(52,211,153,.25)}

/* ROLE DISPLAY */
.inv-role-display{display:flex;gap:14px;align-items:flex-start}
.inv-role-name{font-weight:900;font-size:1rem;color:#fff}
.inv-role-title{font-size:.82rem;font-weight:700}
.inv-role-card{
  padding:18px;border-radius:14px;margin-top:14px;text-align:center;
  animation:invPop .5s cubic-bezier(.22,1,.36,1) both;
}

/* CHAT */
.inv-chat-messages{max-height:220px;overflow-y:auto;scroll-behavior:smooth}
.inv-chat-msg{
  padding:8px 10px;border-radius:10px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
  margin-bottom:6px;animation:invSlideUp .25s ease both;
}
.inv-chat-sender{font-size:.75rem;font-weight:800;margin-bottom:2px}
.inv-chat-text{font-size:.84rem;color:#c8c8d8}
.inv-chat-input-row{border-top:1px solid rgba(255,255,255,.07);padding-top:10px;margin-top:8px}
.inv-quick-args{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.inv-arg-btn{
  padding:6px 12px;border-radius:8px;
  background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.25);
  color:#a78bfa;font-size:.75rem;font-weight:700;cursor:pointer;
  transition:all .2s ease;white-space:nowrap;
}
.inv-arg-btn:hover{background:rgba(139,92,246,.22);transform:translateY(-1px)}

/* ACTIONS LOG */
.inv-actions-log{max-height:180px;overflow-y:auto}
.inv-log-item{
  padding:6px 10px;border-radius:8px;background:rgba(255,255,255,.02);
  font-size:.78rem;color:#9ca3af;margin-bottom:4px;
  border-left:2px solid rgba(139,92,246,.3);
  animation:invSlideUp .25s ease both;
}

/* TIMER BOX */
.inv-timer-box{
  padding:12px 16px;border-radius:12px;
  background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.25);
  text-align:center;margin-bottom:12px;animation:invGlowPulse 3s ease infinite;
}

/* ROOM LIST */
.inv-room-item{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 14px;border-radius:12px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
  margin-bottom:8px;transition:border-color .2s,background .2s;
}
.inv-room-item:hover{border-color:rgba(59,130,246,.4);background:rgba(59,130,246,.06)}
.inv-room-join-btn{
  padding:7px 16px;border-radius:9px;
  background:linear-gradient(135deg,#1565c0,#0d47a1);color:#fff;
  font-size:.82rem;font-weight:800;border:none;cursor:pointer;
  transition:transform .18s ease,box-shadow .18s ease;
}
.inv-room-join-btn:hover{transform:scale(1.04);box-shadow:0 4px 14px rgba(21,101,192,.45)}

/* RESULTADO */
.inv-resultado-hero{text-align:center;padding:24px}
.inv-resposta-correta{margin-top:14px}
.inv-resposta-item{
  display:flex;justify-content:space-between;align-items:center;
  padding:10px 14px;border-radius:10px;
  background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);
  margin-top:8px;font-size:.88rem;
}
.inv-rank-item{
  display:flex;align-items:center;gap:12px;
  padding:12px 14px;border-radius:12px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  margin-bottom:8px;
  animation:invSlideUp .35s cubic-bezier(.22,1,.36,1) both;
}
.inv-rank-item:nth-child(2){animation-delay:.06s}
.inv-rank-item:nth-child(3){animation-delay:.12s}
.inv-rank-item:first-child{border-color:rgba(255,215,0,.3);background:rgba(255,215,0,.06)}
.inv-rank-item:nth-child(2){border-color:rgba(192,192,192,.2)}
.inv-rank-pos{font-size:1.5rem}
.inv-rank-name{font-weight:800;color:#fff;font-size:.92rem}
.inv-rank-details{font-size:.75rem;color:#6b7280;margin-top:2px}
.inv-rank-score{margin-left:auto;font-size:1.1rem;font-weight:900;color:#ffd700;text-shadow:0 0 12px rgba(255,215,0,.4)}

/* RULES */
.inv-rules-grid{display:grid;gap:10px;margin-top:10px}
.inv-rule{display:flex;align-items:flex-start;gap:12px}
.inv-rule-icon{font-size:1.5rem}

/* EMPTY */
.inv-empty{color:#4b5563;font-size:.85rem;text-align:center;padding:16px}

/* VOTE SECTION */
.inv-vote-grid{display:grid;gap:14px}
.inv-vote-section h3{font-size:.95rem;font-weight:800;color:#fff;margin-bottom:12px}
.inv-vote-summary{
  padding:14px;border-radius:12px;
  background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);
  font-size:.85rem;line-height:1.8;color:#c8c8d8;margin-top:12px;
}

/* INVESTIGATION LAYOUT */
.inv-investigation-layout{
  display:grid;grid-template-columns:1.4fr 1fr;gap:14px;padding:14px;
}
.inv-left-panel,.inv-right-panel{display:grid;gap:12px;align-content:start;scroll-behavior:smooth}

/* DUVIDAS */
.inv-duvidas{margin-top:12px}

/* RESPONSIVE */
@media(max-width:700px){
  .inv-investigation-layout{grid-template-columns:1fr}
  .inv-lobby-grid{grid-template-columns:1fr}
  .inv-lobby-container,.inv-waiting-container,.inv-vote-container,
  .inv-resultado-container,.inv-game-container{padding:10px 10px 80px}
}


/* ── GLOBAL TRANSITIONS & ANIMATIONS v3 ─────────────────────────── */
@keyframes slideUp    {from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
@keyframes slideDown  {from{opacity:0;transform:translateY(-18px)}to{opacity:1;transform:none}}
@keyframes popIn      {0%{opacity:0;transform:scale(.82)}70%{transform:scale(1.04)}100%{opacity:1;transform:scale(1)}}
@keyframes glowPulse  {0%,100%{box-shadow:0 0 12px rgba(21,101,192,.3)}50%{box-shadow:0 0 28px rgba(21,101,192,.7)}}
@keyframes borderAnim {0%,100%{border-color:rgba(21,101,192,.35)}50%{border-color:rgba(59,130,246,.85)}}
@keyframes ripple     {from{transform:scale(0);opacity:.55}to{transform:scale(4);opacity:0}}
@keyframes pageEnter  {from{opacity:0;transform:translateY(14px) scale(.99)}to{opacity:1;transform:none}}

/* Universal entrance for main page sections */
#main-page {animation:pageEnter .45s cubic-bezier(.22,1,.36,1) both}

/* Boxes staggered entrance */
.box{animation:fadeUp .4s cubic-bezier(.22,1,.36,1) both}
.box:nth-child(2){animation-delay:.05s}
.box:nth-child(3){animation-delay:.1s}
.box:nth-child(4){animation-delay:.16s}
.box:nth-child(5){animation-delay:.22s}

/* Level cards hover lift */
.level-card{transition:transform .22s cubic-bezier(.22,1,.36,1),box-shadow .22s ease,border-color .22s ease}
.level-card:hover{transform:translateY(-5px) scale(1.02);box-shadow:0 10px 32px rgba(21,101,192,.28);border-color:rgba(59,130,246,.6)}

/* Option cards smoother transitions */
.option{transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .18s ease,background .2s ease,border-color .2s ease!important}
.option:hover:not(:disabled){transform:translateX(6px) scale(1.005)!important}

/* Feedback slide down */
.feedback{animation:slideDown .35s cubic-bezier(.22,1,.36,1) both}

/* Question card */
.qcard.enter{animation:pageEnter .42s cubic-bezier(.22,1,.36,1) both!important}

/* Profile bar shimmer */
.profile-bar{position:relative;overflow:hidden}
.profile-bar::after{
  content:'';position:absolute;inset:0;border-radius:inherit;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,.04) 50%,transparent 100%);
  background-size:200%;animation:shimmer 3.5s linear infinite;pointer-events:none
}

/* Hero stat hover */
.hero-stat{transition:transform .2s ease,box-shadow .2s ease}
.hero-stat:hover{transform:translateY(-2px)}
.hero-stat strong{transition:color .3s}
.hero-stat:hover strong{color:#60a5fa}

/* Mode cards */
.mode-card{transition:transform .22s cubic-bezier(.22,1,.36,1),box-shadow .22s ease,border-color .22s ease!important}
.mode-card:hover:not(.locked){transform:translateY(-5px) scale(1.02);box-shadow:0 10px 36px rgba(21,101,192,.28);border-color:rgba(59,130,246,.7)}

/* Button ripple base */
.btn{position:relative;overflow:hidden}
.btn::after{
  content:'';position:absolute;inset:0;border-radius:inherit;
  background:radial-gradient(circle at var(--rx,50%) var(--ry,50%),rgba(255,255,255,.2) 0%,transparent 70%);
  opacity:0;pointer-events:none;transition:opacity .4s;
}
.btn:active::after{opacity:1;transition:opacity .05s}

/* Auth panel smooth entrance */
#auth-overlay{transition:opacity .3s ease}

/* Toast */
.inv-toast-notif{
  position:fixed;bottom:72px;left:50%;
  transform:translateX(-50%) translateY(0);
  background:linear-gradient(135deg,rgba(21,101,192,.96),rgba(13,71,161,.96));
  border:1px solid rgba(59,130,246,.5);border-radius:12px;
  padding:10px 22px;color:#fff;font-weight:700;font-size:.88rem;
  z-index:9999;animation:slideUp .3s ease both;
  box-shadow:0 8px 28px rgba(0,0,0,.4);white-space:nowrap;
}
/* ── END GLOBAL ANIMATIONS v3 ─────────────────────────────────────── */

</style>
</head>
<body>
<!-- ═══════════════════════════════════════════════════════════════════
     AUTH WALL — aparece antes do jogo
     ═══════════════════════════════════════════════════════════════════ -->
<div id='auth-wall'>
  <div class='auth-box'>
    <div class='auth-logo'>
      <span class='al-icon'>⚖️</span>
      <h1>Guardiao da Constituicao</h1>
      <p>Crie sua conta ou entre para salvar seu progresso</p>
    </div>
    <div class='auth-tabs'>
      <button class='auth-tab active' id='tab-login' onclick='switchTab("login")'>Entrar</button>
      <button class='auth-tab' id='tab-register' onclick='switchTab("register")'>Criar conta</button>
    </div>
    <!-- LOGIN -->
    <div id='auth-login-form'>
      <div class='auth-field'>
        <label>Nome de usuario</label>
        <input type='text' id='login-user' placeholder='Seu nome de usuario' autocomplete='username' autocapitalize='none'>
      </div>
      <div class='auth-field'>
        <label>Senha</label>
        <input type='password' id='login-pass' placeholder='Sua senha' autocomplete='current-password'>
      </div>
      <div class='auth-error' id='login-error'></div>
      <div class='auth-success' id='login-success'></div>
      <button class='auth-submit' id='btn-login' onclick='doLogin()'>Entrar na Arena ⚔️</button>
    </div>
    <!-- REGISTER -->
    <div id='auth-register-form' style='display:none'>
      <div class='auth-field'>
        <label>Escolha seu avatar</label>
        <div class='auth-avatar-grid' id='auth-av-grid'></div>
      </div>
      <div class='auth-field'>
        <label>Nome de usuario</label>
        <input type='text' id='reg-user' placeholder='Como voce quer ser chamado?' autocomplete='username' autocapitalize='none' maxlength='20'>
      </div>
      <div class='auth-field'>
        <label>Senha</label>
        <input type='password' id='reg-pass' placeholder='Minimo 4 caracteres' autocomplete='new-password'>
      </div>
      <div class='auth-field'>
        <label>Confirmar senha</label>
        <input type='password' id='reg-pass2' placeholder='Repita a senha' autocomplete='new-password'>
      </div>
      <div class='auth-error' id='reg-error'></div>
      <div class='auth-success' id='reg-success'></div>
      <button class='auth-submit' id='btn-register' onclick='doRegister()'>Criar minha conta 🏛️</button>
    </div>
    <div class='auth-guest'>
      <button onclick='playAsGuest()'>Jogar sem conta (progresso nao salvo)</button>
    </div>
  </div>
</div>

<div class='page' id='main-page' style='display:none'>


  <!-- PROFILE BAR -->
  <section class='profile-bar' id='profile-bar'>
    <div class='profile-avatar' id='profile-avatar' title='Trocar avatar'>📚</div>
    <div class='profile-info'>
      <div class='profile-name' id='profile-display-name'>Jogador</div>
      <div class='profile-title' id='profile-display-title'>Nv 1 — Estudante</div>
    </div>
    <div class='xp-wrap'>
      <div class='xp-label'><span id='xp-level-label'>Nivel 1</span><span id='xp-amount'>0 / 100 XP</span></div>
      <div class='xp-bar-bg'><div class='xp-bar-fill' id='xp-bar-fill' style='width:0%'></div></div>
    </div>
    <div class='streak-badge' id='streak-badge' title='Sequencia diaria'>🔥 <span id='streak-days'>0</span> dias</div>
    <div class='coins-display' id='coins-display'>🪙 <span id='coins-amount'>0</span></div>
    <div class='profile-actions'>
      <div id='user-badge' style='display:none'>
        <span class='ub-avatar' id='ub-av'>📚</span>
        <span class='ub-name' id='ub-name'>Jogador</span>
        <span class='ub-logout' onclick='doLogout()' title='Sair'>⏏</span>
      </div>
      <button class='icon-btn' id='btn-sound' title='Som'>🔊</button>
      <button class='icon-btn' id='btn-settings' title='Configuracoes'>⚙️</button>
    </div>
  </section>

  <!-- HERO -->
  <section class='box hero'>
    <div class='eyebrow'>⚖️ Arena Constitucional — Ranking em Tempo Real</div>
    <h1>Guardiao da Constituicao</h1>
    <p>Prove que voce domina a Constituicao Federal de 1988. Cinco niveis progressivos, multiplos modos de jogo, sistema de XP e progressao, ranking global ao vivo.</p>
    <div class='hero-stats'>
      <div class='hero-stat'><strong>15</strong><span>Perguntas por desafio</span></div>
      <div class='hero-stat'><strong>+60</strong><span>Questoes no banco</span></div>
      <div class='hero-stat'><strong>Live</strong><span>Ranking atualiza a cada 5s</span></div>
      <div class='hero-stat'><strong>Desempate</strong><span>Pontos + menor tempo</span></div>
      <div class='hero-stat'><strong>5 Modos</strong><span>Classico, Infinito, Relampago, Treino, Estudo</span></div>
    </div>
  </section>

  <div class='layout'>
    <main>

      <!-- INTRO -->
      <section class='box panel' id='intro'>
        <h2>Como funciona</h2>
        <p>Cada partida sorteia <strong>3 questoes por nivel</strong>. A pergunta aparece sozinha por <strong>20 segundos</strong> para voce ler — depois as alternativas sao reveladas. Quanto mais dificil o nivel, mais tempo para responder.</p>
        <div class='levels' id='levels'></div>

        <!-- GAME MODE SELECT -->
        <div class='setting-group' style='margin-top:14px'>
          <label>Modo de jogo</label>
          <div class='mode-grid' id='mode-grid'>
            <div class='mode-card active' data-mode='classic' onclick='selectMode("classic")'>
              <div class='mode-icon'>📜</div>
              <h3>Classico</h3>
              <p>15 questoes, 5 niveis progressivos</p>
            </div>
            <div class='mode-card' data-mode='infinite' onclick='selectMode("infinite")'>
              <div class='mode-icon'>♾️</div>
              <h3>Infinito</h3>
              <p>Jogue ate errar. Quanto mais longe, melhor!</p>
            </div>
            <div class='mode-card' data-mode='speedrun' onclick='selectMode("speedrun")'>
              <div class='mode-icon'>⚡</div>
              <h3>Relampago</h3>
              <p>2 minutos. Quantas voce consegue?</p>
            </div>
            <div class='mode-card' data-mode='study' onclick='selectMode("study")'>
              <div class='mode-icon'>📖</div>
              <h3>Estudo</h3>
              <p>Sem tempo. Explicacoes detalhadas.</p>
            </div>
            <div class='mode-card' data-mode='replay' onclick='selectMode("replay")'>
              <div class='mode-icon'>🔄</div>
              <h3>Treino</h3>
              <p>Refaca as perguntas que voce errou</p>
            </div>
          </div>
        </div>
        <div class='actions'>
          <button class='btn primary' id='btn-start'>▶ Iniciar desafio</button>
          <button class='btn secondary' id='btn-reload-rank'>↻ Atualizar ranking</button>
          <button class='btn ghost hidden' id='btn-install'>📲 Instalar app</button>
        </div>
        <div style='margin-top:14px'>
          <button class='btn inv-btn' onclick='openInvestigacao()' style='width:100%;padding:16px 20px;font-size:1rem;background:linear-gradient(135deg,rgba(139,92,246,.18),rgba(59,130,246,.12));border:1px solid rgba(139,92,246,.5);color:#c4b5fd;border-radius:16px;display:flex;align-items:center;justify-content:center;gap:10px;transition:all .3s ease;cursor:pointer;'>
            <span style='font-size:1.4rem'>🔍</span>
            <span><strong style='color:#a78bfa'>Investigação Criminal</strong><br><small style='font-weight:400;font-size:.78rem;color:#8b5cf6'>Multiplayer em tempo real — Resolva casos constitucionais</small></span>
            <span style='margin-left:auto;font-size:.75rem;padding:3px 10px;border-radius:99px;background:rgba(139,92,246,.2);border:1px solid rgba(139,92,246,.4);color:#a78bfa'>NOVO</span>
          </button>
        </div>
        <div class='info' style='margin-top:14px'><strong>Ranking:</strong> salvo localmente no servidor. Para compartilhar entre jogadores, mantenha o servidor Python rodando na rede.</div>
        <div style='margin-top:18px;padding:12px 16px;border-radius:12px;background:linear-gradient(135deg,rgba(21,101,192,.08),rgba(21,101,192,.03));border:1px solid rgba(21,101,192,.25);text-align:center;font-size:.82rem;color:#7ab0e0'>
          <span style='font-size:1rem'>⚖️</span> Programado por <strong style='color:#c8a000'>Icaro Lucas Pereira Batista</strong>
        </div>
      </section>

      <!-- GAME -->
      <section class='box panel hidden' id='game'>
        <div class='lives-bar' id='lives-bar'>
          <span class='heart' id='heart-1'>❤️</span>
          <span class='heart' id='heart-2'>❤️</span>
          <span class='heart' id='heart-3'>❤️</span>
        </div>
        <div class='hud'>
          <div class='hud-box'><div class='lbl'>Pontuacao</div><div class='val' id='hud-score'>0</div></div>
          <div class='hud-box'><div class='lbl'>Sequencia</div><div class='val' id='hud-streak'>0</div></div>
          <div class='hud-box'><div class='lbl'>Fase</div><div class='val' id='hud-timer'>--</div></div>
          <div class='hud-box'><div class='lbl'>Tempo total</div><div class='val' id='hud-elapsed'>00:00</div></div>
          <div class='hud-box'><div class='lbl'>Nivel</div><div class='val' id='hud-level'>--</div></div>
        </div>
        <div class='prog-wrap'><div class='prog-bar' id='progress'></div></div>

        <!-- QUESTION CARD -->
        <div class='box qcard' id='qcard'>
          <div class='qnav'>
            <button class='btn primary' id='btn-next' disabled>Proxima ▶</button>
          </div>
          <div class='qtop'>
            <span class='pill' id='counter'>Pergunta 1/15</span>
            <span class='pill' id='pts-pill'>+12 pts</span>
          </div>
          <!-- phase indicator -->
          <div class='phase-bar reading' id='phase-bar'>
            <span id='phase-label'>📖 Leia a pergunta</span>
            <span class='phase-cd' id='phase-cd'>20</span>
          </div>
          <h2 id='question-text'></h2>
          <div class='options' id='options'></div>
        </div>

        <!-- AJUDAS -->
        <div class='help-grid'>
          <div class='help-card'>
            <button class='btn secondary' id='btn-cut' style='width:100%'>✂ Eliminar 2 opcoes</button>
            <small>Uso unico por partida</small>
          </div>
          <div class='help-card'>
            <button class='btn secondary' id='btn-hint' style='width:100%'>💡 Dica juridica</button>
            <small>Uso unico por partida</small>
          </div>
          <div class='help-card'>
            <button class='btn secondary' id='btn-law' style='width:100%'>📜 Base constitucional</button>
            <small>Uso unico por partida</small>
          </div>
          <div class='help-card'>
            <button class='btn secondary' id='btn-skip' style='width:100%'>⏭ Pular pergunta</button>
            <small>Uso unico por partida</small>
          </div>
          <div class='help-card'>
            <button class='btn secondary' id='btn-extra-time' style='width:100%'>⏱ +15 segundos</button>
            <small>Uso unico por partida</small>
          </div>
        </div>

        <div class='info hidden' id='assist-box'></div>
        <div class='feedback hidden' id='feedback-box'>
          <h3 id='fb-title'></h3>
          <p id='fb-body'></p>
          <p id='fb-ref'></p>
        </div>
      </section>

    </main>

    <aside class='stack'>

      <!-- RANKING -->
      <section class='box panel'>
        <div class='rank-hdr'>
          <h2>🏆 Ranking Global</h2>
          <span class='chip'>Atualiza 5s</span>
        </div>
        <div class='ranking' id='ranking-list'>
          <div class='empty'>Carregando ranking...</div>
        </div>
      </section>

      <!-- MEDALS -->
      <section class='box panel'>
        <h2>🥇 Medalhas</h2>
        <div class='medal-list' id='medal-list'>
          <div class='empty'>Inicie uma partida para ganhar medalhas.</div>
        </div>
      </section>

      <!-- RESULT -->
      <section class='box result-card hidden' id='result'>
        <h2 id='res-title'>Resultado</h2>
        <div class='big-score' id='res-score'>0 pts</div>
        <p id='res-text'></p>
        <div class='stat-grid' id='stat-grid'></div>
        <div id='wrong-section' class='hidden'>
          <div style='font-size:.88rem;font-weight:800;color:#7ab0e0;margin-bottom:8px'>❌ Perguntas que voce errou:</div>
          <div class='wrong-list' id='wrong-list'></div>
        </div>
        <div class='save-row'>
          <input id='player-name' maxlength='30' placeholder='Seu nome para o ranking'>
          <button class='btn primary' id='btn-save'>Salvar</button>
        </div>
        <div class='actions' style='margin-top:10px'>
          <button class='btn secondary' id='btn-restart'>↺ Jogar novamente</button>
          <button class='btn share' id='btn-share'>📤 Compartilhar resultado</button>
          <button class='btn secondary' id='btn-save-library'>📚 Salvar erros para estudo</button>
        </div>
        <div id='easter-egg-msg' class='hidden' style='margin-top:12px;padding:14px;border-radius:12px;background:linear-gradient(135deg,rgba(255,215,0,.1),rgba(255,215,0,.04));border:1px solid rgba(255,215,0,.3);text-align:center;font-family:Georgia,serif;font-size:1rem;color:#ffd700'></div>
      </section>

      <!-- CONSTITUTION MAP -->
      <section class='box panel' id='const-map-section'>
        <h2>🗺️ Mapa da Constituicao</h2>
        <div class='const-map' id='const-map'></div>
      </section>

      <!-- SKILL TREE -->
      <section class='box panel' id='skill-section'>
        <h2>🌳 Habilidades</h2>
        <div class='skill-grid' id='skill-grid'></div>
      </section>

      <!-- KNOWLEDGE LIBRARY -->
      <section class='box panel' id='library-section'>
        <h2>📚 Biblioteca de Estudo</h2>
        <div id='library-list'>
          <div class='empty'>Nenhuma questao salva para estudo.</div>
        </div>
        <button class='btn ghost lib-clear hidden' id='btn-clear-library'>Limpar biblioteca</button>
      </section>

      <!-- EVOLUTION -->
      <section class='box panel' id='evolution-section'>
        <h2>📈 Evolucao</h2>
        <canvas class='evo-chart' id='evo-chart'></canvas>
        <div style='font-size:.75rem;color:var(--muted);margin-top:6px;text-align:center' id='evo-label'>Historico de precisao por partida</div>
      </section>

    </aside>
  </div>
</div><!-- /main-page -->
<canvas id='star-canvas'></canvas>
<div id='bg-symbols'></div>
<canvas id='particles-canvas'></canvas>
<div id='epic-intro-overlay' class='hidden'></div>
<div id='fury-overlay' class='hidden'></div>
<div id='suspense-overlay' class='hidden'></div>
<div id='medal-toasts'></div>
<div id='speedrun-bar' class='speedrun-timer hidden'><div class='speedrun-timer-fill' id='speedrun-fill'></div></div>
<div id='level-up-overlay' class='hidden'></div>
<div id='streak-notif' class='hidden'></div>
<div id='settings-modal' class='hidden'></div>
<div id='combo-banner'></div>

<!-- ── INVESTIGATION GAME OVERLAY ── -->
<div id='inv-overlay' class='inv-overlay hidden'>
  <div class='inv-header'>
    <button class='inv-back-btn' onclick='closeInvestigacao()'>← Voltar</button>
    <div class='inv-header-title'>🔍 Investigação Criminal</div>
    <div class='inv-phase-indicator' id='inv-phase-indicator'></div>
    <div class='inv-timer' id='inv-global-timer'></div>
  </div>

  <!-- LOBBY SCREEN -->
  <div id='inv-screen-lobby' class='inv-screen'>
    <div class='inv-lobby-container'>
      <div class='inv-lobby-hero'>
        <div class='inv-logo'>⚖️</div>
        <h1 class='inv-title'>Investigação Criminal</h1>
        <p class='inv-subtitle'>Assuma um papel jurídico. Analise evidências. Descubra a verdade constitucional.</p>
      </div>

      <div class='inv-lobby-grid'>
        <!-- Create Room -->
        <div class='inv-card'>
          <h3>🆕 Nova Sala</h3>
          <p style='color:var(--muted);font-size:.85rem;margin:8px 0 14px'>Crie uma sala e espere outros jogadores</p>
          <input id='inv-player-name' class='inv-input' placeholder='Seu nome (ex: Dr. Silva)' maxlength='20'>
          <button class='inv-btn-primary' onclick='invCreateRoom()'>Criar Sala</button>
        </div>
        <!-- Join Room -->
        <div class='inv-card'>
          <h3>🚪 Entrar em Sala</h3>
          <p style='color:var(--muted);font-size:.85rem;margin:8px 0 14px'>Entre em uma sala existente com o código</p>
          <input id='inv-room-code' class='inv-input' placeholder='Código da sala (ex: AB12CD34)' maxlength='10' style='text-transform:uppercase'>
          <button class='inv-btn-secondary' onclick='invJoinRoom()'>Entrar</button>
        </div>
      </div>

      <!-- Available Rooms -->
      <div class='inv-card' style='margin-top:16px'>
        <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
          <h3>🌐 Salas Disponíveis</h3>
          <button class='inv-btn-ghost' onclick='invRefreshRooms()'>↻ Atualizar</button>
        </div>
        <div id='inv-rooms-list'><div class='inv-empty'>Nenhuma sala aberta. Crie a primeira!</div></div>
      </div>

      <!-- Rules Quick -->
      <div class='inv-card' style='margin-top:16px;background:rgba(139,92,246,.06);border-color:rgba(139,92,246,.25)'>
        <h3 style='color:#a78bfa'>📋 Como Jogar</h3>
        <div class='inv-rules-grid'>
          <div class='inv-rule'><span class='inv-rule-icon'>👥</span><div><strong>2-5 jogadores</strong><br><small>Cada um recebe um papel jurídico único</small></div></div>
          <div class='inv-rule'><span class='inv-rule-icon'>🔍</span><div><strong>Investigação (3 min)</strong><br><small>Analise evidências e use suas habilidades</small></div></div>
          <div class='inv-rule'><span class='inv-rule-icon'>⚖️</span><div><strong>Votação (45s)</strong><br><small>Vote em violação, artigo e culpado</small></div></div>
          <div class='inv-rule'><span class='inv-rule-icon'>🏆</span><div><strong>Pontuação</strong><br><small>Violação +20, Artigo +50, Culpado +30</small></div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- WAITING ROOM SCREEN -->
  <div id='inv-screen-waiting' class='inv-screen hidden'>
    <div class='inv-waiting-container'>
      <div class='inv-card' style='text-align:center'>
        <div style='font-size:3rem;margin-bottom:12px;animation:pulse 2s ease infinite'>⏳</div>
        <h2>Aguardando Jogadores</h2>
        <div class='inv-room-code-display' id='inv-my-room-code'>----</div>
        <p style='color:var(--muted);font-size:.85rem'>Compartilhe este código para outros entrarem</p>
      </div>

      <div class='inv-card' style='margin-top:14px'>
        <h3>👥 Jogadores na Sala (<span id='inv-waiting-count'>1</span>/5)</h3>
        <div id='inv-waiting-players'></div>
        <div style='margin-top:14px'>
          <button class='inv-btn-primary' id='inv-btn-ready' onclick='invMarkReady()'>✅ Estou Pronto!</button>
          <p style='color:var(--muted);font-size:.78rem;margin-top:8px;text-align:center'>Mín. 2 jogadores para iniciar • Máx. 5 jogadores</p>

          <!-- Bot toggle: só aparece para o criador da sala -->
          <div id='inv-bot-toggle-row' style='display:none;margin-top:12px;padding:12px 14px;border-radius:12px;background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.25)'>
            <div style='display:flex;align-items:center;justify-content:space-between;gap:10px'>
              <div>
                <div style='font-weight:800;font-size:.85rem;color:#c4b5fd'>🤖 Preencher com Bots</div>
                <div style='font-size:.75rem;color:#6b7280;margin-top:2px'>Bots completam vagas vazias após 60s</div>
              </div>
              <button id='inv-bot-toggle-btn' onclick='invToggleBots()' style='padding:7px 16px;border-radius:9px;font-size:.8rem;font-weight:800;border:1px solid rgba(139,92,246,.5);background:rgba(139,92,246,.15);color:#a78bfa;cursor:pointer;transition:all .2s ease;min-width:60px'>
                ON
              </button>
            </div>
          </div>

          <div id='inv-bot-countdown' style='display:none;margin-top:10px;padding:10px 14px;border-radius:10px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);text-align:center;font-size:.8rem;color:#f59e0b'>
            🤖 Bots entrarão automaticamente em <strong id='inv-bot-secs'>60</strong>s
          </div>
        </div>
      </div>

      <div class='inv-card' style='margin-top:14px;background:rgba(59,130,246,.06);border-color:rgba(59,130,246,.25)'>
        <h3>📁 Caso: <span id='inv-waiting-case' style='color:#60a5fa'></span></h3>
        <p style='color:var(--muted);font-size:.85rem;margin-top:8px'>Detalhes do caso serão revelados quando o jogo começar</p>
      </div>
    </div>
  </div>

  <!-- INTRO SCREEN -->
  <div id='inv-screen-intro' class='inv-screen hidden'>
    <div class='inv-game-container'>
      <div class='inv-case-intro inv-card'>
        <div class='inv-case-badge'>📋 Caso</div>
        <h2 id='inv-intro-title' class='inv-case-title'></h2>
        <p id='inv-intro-historia' class='inv-case-historia'></p>
        <div class='inv-envolvidos-list' id='inv-intro-envolvidos'></div>
      </div>
      <div class='inv-card' style='margin-top:14px;text-align:center'>
        <div class='inv-countdown-ring' id='inv-intro-countdown'>45</div>
        <p style='color:var(--muted)'>Leia o caso. A investigação começa em breve.</p>
      </div>
      <div id='inv-role-reveal' class='inv-role-card hidden'></div>
    </div>
  </div>

  <!-- INVESTIGATION SCREEN -->
  <div id='inv-screen-investigacao' class='inv-screen hidden'>
    <div class='inv-investigation-layout'>
      <!-- Left: Case + Evidence -->
      <div class='inv-left-panel'>
        <div class='inv-tabs'>
          <button class='inv-tab active' onclick='invTab("case")'>📋 Caso</button>
          <button class='inv-tab' onclick='invTab("evidence")'>🔍 Evidências</button>
          <button class='inv-tab' onclick='invTab("chat")'>💬 Debate</button>
        </div>
        <div id='inv-tab-case' class='inv-tab-content'>
          <div class='inv-card'>
            <h3 id='inv-case-title-small'></h3>
            <p id='inv-case-historia-small' style='color:#b8b8c8;line-height:1.7;font-size:.88rem'></p>
            <div class='inv-duvidas' id='inv-case-duvidas'></div>
          </div>
        </div>
        <div id='inv-tab-evidence' class='inv-tab-content hidden'>
          <div id='inv-evidence-list'></div>
        </div>
        <div id='inv-tab-chat' class='inv-tab-content hidden'>
          <div id='inv-chat-messages' class='inv-chat-messages'></div>
          <div class='inv-chat-input-row'>
            <div class='inv-quick-args' id='inv-quick-args'>
              <button class='inv-arg-btn' onclick='invSendArg("Há violação clara dos direitos")'>Há violação clara</button>
              <button class='inv-arg-btn' onclick='invSendArg("Faltam provas suficientes")'>Faltam provas</button>
              <button class='inv-arg-btn' onclick='invSendArg("O direito de defesa foi ignorado")'>Direito de defesa</button>
              <button class='inv-arg-btn' onclick='invSendArg("A evidência foi contestada validamente")'>Evidência contestada</button>
            </div>
            <div style='display:flex;gap:8px;margin-top:8px'>
              <input id='inv-chat-text' class='inv-input' placeholder='Digite sua análise...' maxlength='150' onkeydown='if(event.key==="Enter")invSendChat()'>
              <button class='inv-btn-ghost' onclick='invSendChat()'>Enviar</button>
            </div>
          </div>
        </div>
      </div>
      <!-- Right: Players + Skills + Log -->
      <div class='inv-right-panel'>
        <!-- Timer -->
        <div class='inv-timer-box' id='inv-inv-timer'></div>
        <!-- My Role -->
        <div id='inv-my-role-card' class='inv-card inv-role-display'></div>
        <!-- Players -->
        <div class='inv-card'>
          <h4 style='margin-bottom:10px;font-size:.88rem;color:var(--muted)'>👥 JOGADORES</h4>
          <div id='inv-players-list'></div>
        </div>
        <!-- Actions Log -->
        <div class='inv-card'>
          <h4 style='margin-bottom:10px;font-size:.88rem;color:var(--muted)'>⚡ LOG DE AÇÕES</h4>
          <div id='inv-actions-log' class='inv-actions-log'></div>
        </div>
      </div>
    </div>
  </div>

  <!-- VOTACAO SCREEN -->
  <div id='inv-screen-votacao' class='inv-screen hidden'>
    <div class='inv-vote-container'>
      <div class='inv-card' style='text-align:center;margin-bottom:14px'>
        <div class='inv-countdown-ring urgent' id='inv-vote-countdown'>45</div>
        <h2 style='margin-top:10px'>⚖️ Hora da Decisão</h2>
        <p style='color:var(--muted);font-size:.85rem'>Baseado nas evidências analisadas, como você decide?</p>
      </div>
      <div class='inv-vote-grid'>
        <!-- Violacao -->
        <div class='inv-card inv-vote-section'>
          <h3>❓ Houve violação constitucional?</h3>
          <div class='inv-vote-options'>
            <button class='inv-vote-btn' id='vbtn-sim' onclick='invSetVote("violacao",true)'>✅ SIM — Houve violação</button>
            <button class='inv-vote-btn' id='vbtn-nao' onclick='invSetVote("violacao",false)'>❌ NÃO — Não houve violação</button>
          </div>
        </div>
        <!-- Artigo -->
        <div class='inv-card inv-vote-section'>
          <h3>📜 Qual artigo foi violado?</h3>
          <div class='inv-artigo-options' id='inv-artigo-options'>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, IV")'>Art. 5º, IV — Liberdade de expressão</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, X")'>Art. 5º, X — Privacidade e honra</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, XI")'>Art. 5º, XI — Inviolabilidade domicílio</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, III")'>Art. 5º, III — Dignidade humana</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, LV")'>Art. 5º, LV — Contraditório e defesa</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º, IX")'>Art. 5º, IX — Livre manifestação</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 5º caput")'>Art. 5º caput — Igualdade</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 37")'>Art. 37 — Administração pública</button>
            <button class='inv-vote-btn small' onclick='invSetVote("artigo","Art. 7º")'>Art. 7º — Direitos trabalhistas</button>
          </div>
        </div>
        <!-- Culpado -->
        <div class='inv-card inv-vote-section'>
          <h3>🎯 Quem é o responsável?</h3>
          <div class='inv-culpado-options' id='inv-culpado-options'></div>
        </div>
      </div>
      <div class='inv-vote-summary' id='inv-vote-summary' style='display:none'></div>
      <button class='inv-btn-primary' id='inv-btn-submit-vote' onclick='invSubmitVote()' style='margin-top:16px;width:100%;opacity:.4' disabled>Confirmar Voto ⚖️</button>
    </div>
  </div>

  <!-- RESULTADO SCREEN -->
  <div id='inv-screen-resultado' class='inv-screen hidden'>
    <div class='inv-resultado-container'>
      <div class='inv-card inv-resultado-hero'>
        <div style='font-size:3rem;margin-bottom:10px'>🏛️</div>
        <h2>Veredicto Final</h2>
        <div class='inv-resposta-correta' id='inv-resposta-correta'></div>
      </div>
      <div class='inv-card' style='margin-top:14px'>
        <h3>🏆 Ranking da Partida</h3>
        <div id='inv-resultado-ranking'></div>
      </div>
      <div class='inv-card' style='margin-top:14px'>
        <h3>📄 Análise do Caso</h3>
        <div id='inv-resultado-analise'></div>
      </div>
      <div style='display:flex;gap:10px;margin-top:16px;flex-wrap:wrap'>
        <button class='inv-btn-primary' onclick='invPlayAgain()'>🔄 Jogar Novamente</button>
        <button class='inv-btn-secondary' onclick='closeInvestigacao()'>← Voltar ao Menu</button>
      </div>
    </div>
  </div>

</div>
<!-- ── END INVESTIGATION OVERLAY ── -->

<script id='q-data' type='application/json'>__QUESTIONS__</script>
<script id='l-data' type='application/json'>__LEVELS__</script>
<script>
'use strict';

/* ══════════════════════════════════════════════════════════════════════
   ACCOUNT SYSTEM
   ══════════════════════════════════════════════════════════════════════ */

const AVATARS_AUTH = [
  {id:'estudante', icon:'📚', name:'Estudante'},
  {id:'advogado',  icon:'⚖️', name:'Advogado'},
  {id:'juiza',     icon:'⚖️', name:'Juiza'},
  {id:'ministra',  icon:'⚖️',  name:'Ministra'},
  {id:'professor', icon:'📖', name:'Professor'},
  {id:'guardiao',  icon:'🛡️', name:'Guardiao'},
];

let currentUser = null;   // {username, avatar, guest}
let selectedAvatar = 'estudante';

/* Carrega sessão do localStorage */
function loadSession() {
  try {
    const s = localStorage.getItem('gc_session');
    if (s) return JSON.parse(s);
  } catch(e) {}
  return null;
}
function saveSession(u) {
  try { localStorage.setItem('gc_session', JSON.stringify(u)); } catch(e) {}
}
function clearSession() {
  try { localStorage.removeItem('gc_session'); } catch(e) {}
}

/* Renderiza grid de avatares */
function renderAuthAvatars() {
  const grid = document.getElementById('auth-av-grid');
  if (!grid) return;
  grid.innerHTML = AVATARS_AUTH.map(a =>
    `<button class='auth-av-btn${a.id===selectedAvatar?" active":""}' onclick='selectAvatar("${a.id}")'>${a.icon}<span>${a.name}</span></button>`
  ).join('');
}
function selectAvatar(id) {
  selectedAvatar = id;
  renderAuthAvatars();
}

/* Troca aba Login / Cadastro */
function switchTab(tab) {
  document.getElementById('auth-login-form').style.display    = tab==='login'    ? '' : 'none';
  document.getElementById('auth-register-form').style.display = tab==='register' ? '' : 'none';
  document.getElementById('tab-login').classList.toggle('active',    tab==='login');
  document.getElementById('tab-register').classList.toggle('active', tab==='register');
}

/* Hash simples (sem crypto nativo para manter zero-deps) */
function simpleHash(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8,'0');
}

function showAuthError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg; el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 5000);
}
function showAuthSuccess(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg; el.style.display = 'block';
}

async function doLogin() {
  const btn  = document.getElementById('btn-login');
  const user = document.getElementById('login-user').value.trim();
  const pass = document.getElementById('login-pass').value;
  if (!user || !pass) { showAuthError('login-error','Preencha usuario e senha.'); return; }
  btn.disabled = true; btn.textContent = 'Entrando...';
  try {
    const r = await fetch('/api/account?name=' + encodeURIComponent(user));
    if (!r.ok) throw new Error('not_found');
    const data = await r.json();
    if (!data.pwHash) throw new Error('not_found');
    if (data.pwHash !== simpleHash(pass)) {
      showAuthError('login-error','Senha incorreta.'); return;
    }
    enterGame({username: user, avatar: data.avatar || 'estudante', guest: false});
  } catch(e) {
    showAuthError('login-error', e.message === 'not_found' ? 'Conta nao encontrada.' : 'Erro de conexao.');
  } finally {
    btn.disabled = false; btn.textContent = 'Entrar na Arena ⚔️';
  }
}

async function doRegister() {
  const btn   = document.getElementById('btn-register');
  const user  = document.getElementById('reg-user').value.trim();
  const pass  = document.getElementById('reg-pass').value;
  const pass2 = document.getElementById('reg-pass2').value;
  if (!user)          { showAuthError('reg-error','Escolha um nome de usuario.'); return; }
  if (user.length < 3){ showAuthError('reg-error','Nome deve ter ao menos 3 caracteres.'); return; }
  if (pass.length < 4){ showAuthError('reg-error','Senha deve ter ao menos 4 caracteres.'); return; }
  if (pass !== pass2) { showAuthError('reg-error','As senhas nao coincidem.'); return; }
  btn.disabled = true; btn.textContent = 'Criando conta...';
  try {
    // verifica se ja existe
    const check = await fetch('/api/account?name=' + encodeURIComponent(user));
    if (check.ok) { const d = await check.json(); if (d.pwHash) { showAuthError('reg-error','Nome ja em uso.'); return; } }
    // salva
    const payload = {
      name: user, pwHash: simpleHash(pass), avatar: selectedAvatar,
      xp:0, gamesPlayed:0, totalCorrect:0, totalQuestions:0,
      dailyStreak:0, lastPlayDate:null, coins:0, history:[], wrongLibrary:[],
      soundEnabled:true, theme:'dark', unlockedMedals:[], equippedSkill:null, purchasedSkills:[],
      createdAt: new Date().toISOString()
    };
    const r = await fetch('/api/account', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error('save_fail');
    showAuthSuccess('reg-success','Conta criada! Bem-vindo(a)! 🎉');
    setTimeout(() => enterGame({username:user, avatar:selectedAvatar, guest:false}), 900);
  } catch(e) {
    showAuthError('reg-error','Erro ao criar conta. Tente novamente.');
  } finally {
    btn.disabled = false; btn.textContent = 'Criar minha conta 🏛️';
  }
}

function playAsGuest() {
  enterGame({username:'Visitante_' + Math.floor(Math.random()*9999), avatar:'estudante', guest:true});
}

function enterGame(user) {
  currentUser = user;
  if (!user.guest) saveSession(user);
  document.getElementById('auth-wall').style.display = 'none';
  document.getElementById('main-page').style.display = '';
  // Atualiza badge no topo
  const av = AVATARS_AUTH.find(a => a.id === user.avatar) || AVATARS_AUTH[0];
  const badge = document.getElementById('user-badge');
  document.getElementById('ub-av').textContent   = av.icon;
  document.getElementById('ub-name').textContent = user.guest ? '👤 Visitante' : user.username;
  if (badge) badge.style.display = 'flex';
  // Carrega perfil do servidor (se nao-guest)
  if (!user.guest) syncProfileFromServer(user.username);
}

async function syncProfileFromServer(username) {
  try {
    const r = await fetch('/api/account?name=' + encodeURIComponent(username));
    if (!r.ok) return;
    const data = await r.json();
    if (!data.name) return;
    // Merge com localStorage — servidor tem prioridade para campos numéricos
    const local = loadProfile();
    const merged = Object.assign({}, local, {
      xp:             Math.max(local.xp||0, data.xp||0),
      gamesPlayed:    Math.max(local.gamesPlayed||0, data.gamesPlayed||0),
      totalCorrect:   Math.max(local.totalCorrect||0, data.totalCorrect||0),
      totalQuestions: Math.max(local.totalQuestions||0, data.totalQuestions||0),
      coins:          Math.max(local.coins||0, data.coins||0),
      dailyStreak:    Math.max(local.dailyStreak||0, data.dailyStreak||0),
      avatar:         data.avatar || local.avatar,
      soundEnabled:   data.soundEnabled !== undefined ? data.soundEnabled : local.soundEnabled,
      wrongLibrary:   data.wrongLibrary && data.wrongLibrary.length > (local.wrongLibrary||[]).length ? data.wrongLibrary : (local.wrongLibrary||[]),
      history:        data.history && data.history.length > (local.history||[]).length ? data.history : (local.history||[]),
    });
    Object.assign(profile, merged);
    saveProfile();
    refreshProfileBar();
  } catch(e) {}
}

async function pushProfileToServer() {
  if (!currentUser || currentUser.guest) return;
  try {
    await fetch('/api/account', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({...profile, name: currentUser.username})
    });
  } catch(e) {}
}

function doLogout() {
  if (!confirm('Sair da sua conta?')) return;
  clearSession();
  currentUser = null;
  document.getElementById('main-page').style.display = 'none';
  document.getElementById('user-badge').style.display = 'none';
  document.getElementById('auth-wall').style.display  = '';
  document.getElementById('login-user').value = '';
  document.getElementById('login-pass').value = '';
}

/* ── DATA ───────────────────────────────────────────────────────── */
const QUESTIONS = JSON.parse(document.getElementById('q-data').textContent);
const LEVELS    = JSON.parse(document.getElementById('l-data').textContent);
const LETTERS   = ['A','B','C','D'];
const QPL       = 3;
const STREAK_BONUS = 5;
const POLL_MS   = 5000;

/* ── STATE ───────────────────────────────────────────────────────── */
const state = {
  deck:[], idx:0, score:0, streak:0,
  phase:'idle',        // 'reading' | 'answering' | 'done'
  timeLeft:0, ticker:null,
  answered:false, opts:[],
  startedAt:0, totalSec:0,
  saved:false, used:{cut:false,hint:false,law:false},
  lvStats:{}, rankTick:null,
  prevMedals:[],       // medalhas ja exibidas nesta partida
  wrongQs:[],          // perguntas erradas para revisao
};
LEVELS.forEach(lv => state.lvStats[lv.id] = {total:0,ok:0,bestStreak:0});

let installPrompt = null;

/* ── UI REFS ─────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const ui = {
  intro:        $('intro'),
  game:         $('game'),
  result:       $('result'),
  levels:       $('levels'),
  hudScore:     $('hud-score'),
  hudStreak:    $('hud-streak'),
  hudTimer:     $('hud-timer'),
  hudElapsed:   $('hud-elapsed'),
  hudLevel:     $('hud-level'),
  progress:     $('progress'),
  qcard:        $('qcard'),
  counter:      $('counter'),
  ptsPill:      $('pts-pill'),
  phaseBar:     $('phase-bar'),
  phaseLabel:   $('phase-label'),
  phaseCd:      $('phase-cd'),
  qtext:        $('question-text'),
  options:      $('options'),
  btnNext:      $('btn-next'),
  assistBox:    $('assist-box'),
  feedbackBox:  $('feedback-box'),
  fbTitle:      $('fb-title'),
  fbBody:       $('fb-body'),
  fbRef:        $('fb-ref'),
  medalList:    $('medal-list'),
  rankingList:  $('ranking-list'),
  resTitle:     $('res-title'),
  resScore:     $('res-score'),
  resText:      $('res-text'),
  statGrid:     $('stat-grid'),
  wrongSection: $('wrong-section'),
  wrongList:    $('wrong-list'),
  playerName:   $('player-name'),
  btnSave:      $('btn-save'),
  btnStart:     $('btn-start'),
  btnRestart:   $('btn-restart'),
  btnReload:    $('btn-reload-rank'),
  btnInstall:   $('btn-install'),
  btnCut:       $('btn-cut'),
  btnHint:      $('btn-hint'),
  btnLaw:       $('btn-law'),
  btnSkip:      $('btn-skip'),
  btnExtraTime: $('btn-extra-time'),
  medalToasts:  $('medal-toasts'),
  comboBanner:  $('combo-banner'),
};

/* ── UTILS ───────────────────────────────────────────────────────── */
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length-1; i > 0; i--) {
    const j = Math.floor(Math.random()*(i+1));
    [a[i],a[j]] = [a[j],a[i]];
  }
  return a;
}
function fmtTime(s) {
  s = Math.max(0, s|0);
  return String(s/60|0).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
}
function lvMeta(id) { return LEVELS.find(l=>l.id===id); }
function elapsed() { return state.startedAt ? Math.floor((Date.now()-state.startedAt)/1000) : 0; }

/* ── BUILD DECK ──────────────────────────────────────────────────── */
function buildDeck() {
  let deck = [];
  LEVELS.forEach(lv => {
    const pool = shuffle(QUESTIONS.filter(q=>q.level===lv.id));
    deck = deck.concat(pool.slice(0, QPL));
  });
  return deck;
}

/* ── MEDALS ──────────────────────────────────────────────────────── */
function computeMedals() {
  const stats  = state.lvStats;
  const allTot = Object.values(stats).reduce((s,x)=>s+x.total, 0);
  const allOk  = Object.values(stats).reduce((s,x)=>s+x.ok,    0);
  const acc    = allTot > 0 ? allOk/allTot : 0;
  const sec    = elapsed();
  const medals = [];

  // 1. Precisao
  if (allTot > 0 && acc >= 0.8)
    medals.push({id:'acc', name:'🎯 Precisao Constitucional', desc:'Acertou 80% ou mais das questoes.'});

  // 2. Velocidade — usa elapsed() em tempo real, nao totalSec (so setado no fim)
  if (state.score >= 190 && sec > 0 && sec <= 900)
    medals.push({id:'speed', name:'⚡ Celeridade Juridica', desc:'Alta pontuacao com agilidade.'});

  // 3. Remedios perfeito
  if (stats[3] && stats[3].total > 0 && stats[3].ok === stats[3].total)
    medals.push({id:'rem', name:'⚖️ Mestre dos Remedios', desc:'Dominou todos os remedios constitucionais.'});

  // 4. Casos praticos
  if (stats[5] && stats[5].ok >= 2)
    medals.push({id:'caso', name:'🏛️ Caso Concreto', desc:'Bom desempenho nos casos praticos.'});

  // 5. Sequencia
  if (Object.values(stats).some(x => x.bestStreak >= 4))
    medals.push({id:'streak', name:'🔥 Sequencia Implacavel', desc:'Manteve 4 ou mais acertos consecutivos.'});

  // 6. Perfeito
  if (allOk > 0 && allOk === allTot && allTot >= 15)
    medals.push({id:'perfect', name:'👑 Perfeicao Constitucional', desc:'Gabarito perfeito! 15/15!'});

  // 7. Sem ajudas
  if (!state.used.cut && !state.used.hint && !state.used.law && allTot >= 15)
    medals.push({id:'nohelp', name:'🧠 Mente Propria', desc:'Terminou sem usar nenhuma ajuda.'});

  // 8. Iniciante
  if (allOk >= 1 && allTot >= 1 && !medals.some(m=>m.id==='first'))
    medals.push({id:'first', name:'⭐ Primeiro Acerto', desc:'Acertou a primeira questao!'});

  // 9. Velocista (menos de 2 min)
  if (sec > 0 && sec <= 120 && allTot >= 15)
    medals.push({id:'fast', name:'⏱️ Velocista', desc:'Terminou em menos de 2 minutos!'});

  // 10. Sequencia longa
  if (Object.values(stats).some(x => x.bestStreak >= 8))
    medals.push({id:'longstreak', name:'💎 Sequencia Lendaria', desc:'8+ acertos consecutivos!'});

  // 11. Modo infinito longe
  if (gameMode === 'infinite' && allOk >= 20)
    medals.push({id:'infinite20', name:'♾️ Maratonista', desc:'20+ acertos no modo infinito!'});

  // 12. Speedrun master
  if (gameMode === 'speedrun' && allOk >= 10)
    medals.push({id:'speedmaster', name:'⚡ Relampago', desc:'10+ acertos no modo relampago!'});

  // 13. Estudioso (tem questoes na biblioteca)
  if (profile.wrongLibrary && profile.wrongLibrary.length >= 10)
    medals.push({id:'studious', name:'📚 Estudioso', desc:'10+ questoes na biblioteca de estudo.'});

  // 14. Veterano (10+ partidas)
  if (profile.gamesPlayed >= 10)
    medals.push({id:'veteran', name:'🎖️ Veterano', desc:'10+ partidas jogadas!'});

  // 15. Streak diario
  if (profile.dailyStreak >= 5)
    medals.push({id:'dailystreak', name:'🔥 Fogo Diario', desc:'5+ dias consecutivos!'});

  return medals;
}

function refreshMedals() {
  const current = computeMedals();
  // Detecta medalhas novas (nao exibidas ainda)
  current.forEach((m, i) => {
    if (!state.prevMedals.includes(m.id)) {
      showMedalToast(m, i * 500);
    }
  });
  state.prevMedals = current.map(m=>m.id);

  // Renderiza painel
  if (current.length === 0) {
    ui.medalList.innerHTML = "<div class='empty'>Responda questoes para ganhar medalhas.</div>";
    return;
  }
  ui.medalList.innerHTML = current.map((m, i) =>
    `<div class='medal' style='animation-delay:${i*0.06}s'>
       <strong>${m.name}</strong>
       <span>${m.desc}</span>
     </div>`
  ).join('');
}

function showMedalToast(medal, delayMs) {
  setTimeout(() => {
    const t = document.createElement('div');
    t.className = 'm-toast';
    t.innerHTML = `<div class='m-toast-head'>🏅 Medalha desbloqueada!</div>
                   <div class='m-toast-name'>${medal.name}</div>
                   <div class='m-toast-desc'>${medal.desc}</div>`;
    ui.medalToasts.appendChild(t);
    playSound('medal');
    // Remove apos 4s
    setTimeout(() => {
      t.classList.add('out');
      setTimeout(() => t.remove(), 400);
    }, 4000);
  }, delayMs);
}

/* ── COMBO BANNER ─────────────────────────────────────────────────── */
function showCombo(streak) {
  const map = {3:['🔥 Combo x3!  +5pts','2.8rem','#ff9800'], 5:['🔥🔥 Combo x5!  +15pts','3.8rem','#ff5722'], 8:['🔥🔥🔥 Combo x8!  +30pts','5rem','#800020'], 10:['⚡ MODO GENIO ⚡  +50pts','5.5rem','#ffd700'], 15:['💎 LENDARIO 💎','6rem','#e040fb']};
  if (!map[streak]) return;
  const [text, size, color] = map[streak];
  const b = ui.comboBanner;
  b.textContent = text;
  b.style.fontSize = size;
  b.style.color = color;
  b.className = 'show';
  clearTimeout(b._t);
  b._t = setTimeout(() => {
    b.classList.remove('show');
    b.classList.add('hide');
    setTimeout(() => { b.className = ''; }, 600);
  }, 1200);
}

/* ── PLAYER TITLE ─────────────────────────────────────────────────── */
function playerTitle(score) {
  if (score >= 280) return 'Jurista Supremo';
  if (score >= 250) return 'Guardiao da Lei';
  if (score >= 220) return 'Arquiteto Constitucional';
  if (score >= 190) return 'Constitucionalista';
  if (score >= 170) return 'Guardiao da Constituicao';
  if (score >= 140) return 'Defensor dos Direitos';
  if (score >= 120) return 'Interprete da Lei';
  if (score >= 80)  return 'Estudioso do Direito';
  return 'Aprendiz Constitucional';
}

/* ── HUD ──────────────────────────────────────────────────────────── */
function updateHud() {
  const q = state.deck[state.idx];
  ui.hudScore.textContent   = state.score;
  ui.hudStreak.textContent  = state.streak;
  ui.hudStreak.className    = 'val' + (state.streak >= 3 ? ' fire' : '');
  ui.hudElapsed.textContent = fmtTime(elapsed());
  ui.hudLevel.textContent   = q ? 'Nv ' + q.level : '--';
  const pct = state.deck.length ? (state.idx / state.deck.length) * 100 : 0;
  ui.progress.style.width = pct + '%';
}

/* ── PHASE DISPLAY ────────────────────────────────────────────────── */
function setPhase(phase, seconds) {
  ui.phaseCd.textContent = seconds;
  ui.phaseCd.classList.toggle('urgent', seconds <= 5 && phase === 'answering');

  if (phase === 'reading') {
    ui.phaseBar.className  = 'phase-bar reading';
    ui.phaseLabel.textContent = '📖 Leia a pergunta — as alternativas aparecem em breve';
    ui.hudTimer.textContent   = '📖 ' + seconds + 's';
  } else if (phase === 'answering') {
    ui.phaseBar.className  = 'phase-bar answering';
    ui.phaseLabel.textContent = '⏳ Escolha sua resposta';
    ui.hudTimer.textContent   = seconds + 's';
  } else if (phase === 'done-ok') {
    ui.phaseBar.className  = 'phase-bar done-ok';
    ui.phaseLabel.textContent = '✅ Resposta correta!';
    ui.phaseCd.textContent = '';
    ui.hudTimer.textContent   = '--';
  } else if (phase === 'done-no') {
    ui.phaseBar.className  = 'phase-bar done-no';
    ui.phaseLabel.textContent = '❌ Resposta incorreta';
    ui.phaseCd.textContent = '';
    ui.hudTimer.textContent   = '--';
  } else if (phase === 'done-time') {
    ui.phaseBar.className  = 'phase-bar done-no';
    ui.phaseLabel.textContent = '⏰ Tempo esgotado';
    ui.phaseCd.textContent = '';
    ui.hudTimer.textContent   = '--';
  }
}

/* ── RENDER QUESTION ──────────────────────────────────────────────── */
function renderQuestion() {
  const q  = state.deck[state.idx];
  const lv = lvMeta(q.level);

  state.answered = false;
  state.phase    = 'reading';
  if (q.type !== 'fill') {
    state.opts = shuffle(q.o.map((text, i) => ({text, correct: i === q.a})));
  }
  clearInterval(state.ticker);

  // Reset UI
  ui.feedbackBox.classList.add('hidden');
  ui.assistBox.classList.add('hidden');
  ui.btnNext.disabled = true;
  ui.options.innerHTML = '';

  // Golden/Boss styling
  ui.qcard.classList.remove('golden', 'boss');
  if (isGoldenQuestion(q)) ui.qcard.classList.add('golden');
  if (isBossQuestion(q)) ui.qcard.classList.add('boss');

  // Animate card entrance
  ui.qcard.classList.remove('enter');
  void ui.qcard.offsetWidth;
  ui.qcard.classList.add('enter');

  // Counter & points
  const mult = getDifficultyMultiplier(q);
  const pts = Math.round(lv.base * mult);
  ui.counter.textContent = 'Pergunta ' + (state.idx+1) + '/' + state.deck.length;
  let ptsTxt = '+' + pts + ' pts';
  if (isGoldenQuestion(q)) ptsTxt = '⭐ ' + ptsTxt + ' (3x)';
  if (isBossQuestion(q)) ptsTxt = '🧠 BOSS ' + ptsTxt;
  if (furyActive) ptsTxt += ' 🔥x2';
  ui.ptsPill.textContent = ptsTxt;

  // Question text with badges
  let qPrefix = '';
  if (isGoldenQuestion(q)) qPrefix = '<span class="golden-badge">⭐ Questao Dourada</span> ';
  if (isBossQuestion(q)) qPrefix = '<span class="boss-badge">🧠 Pergunta Chefe</span> ';
  if (q.type === 'fill') qPrefix += '<span class="study-badge">✍️ Preencher</span> ';
  ui.qtext.innerHTML = qPrefix + q.q;

  // Help buttons
  ui.btnCut.disabled  = state.used.cut;
  if (ui.btnSkip) ui.btnSkip.disabled = state.used.skip;
  if (ui.btnExtraTime) ui.btnExtraTime.disabled = state.used.extraTime;
  answerStartTime = 0;
  ui.btnHint.disabled = state.used.hint;
  ui.btnLaw.disabled  = state.used.law;

  // Study mode: no timer
  const isStudy = gameMode === 'study';
  const skillEffect = getEquippedSkill() ? SKILLS.find(s => s.id === getEquippedSkill()) : null;
  const extraTime = (skillEffect && skillEffect.effect === 'extraTime') ? 10 : 0;

  // ── FASE 1: LEITURA ──────────────────────────────────
  if (isStudy) {
    // Study mode: skip reading phase, show options immediately
    state.timeLeft = 0;
    setPhase('reading', 0);
    updateHud();
    if (q.type === 'fill') { renderFillBlank(q); state.phase = 'answering'; setPhase('answering', 999); }
    else revealOptions(q, lv);
  } else {
    state.timeLeft = lv.read;
    setPhase('reading', state.timeLeft);
    updateHud();

    state.ticker = setInterval(() => {
      state.timeLeft--;
      setPhase('reading', state.timeLeft);
      if (state.timeLeft <= 0) {
        clearInterval(state.ticker);
        if (q.type === 'fill') { renderFillBlank(q); state.phase = 'answering'; state.timeLeft = lv.answer + extraTime; setPhase('answering', state.timeLeft); state.ticker = setInterval(() => { state.timeLeft--; setPhase('answering', state.timeLeft); if (state.timeLeft <= 0) { clearInterval(state.ticker); if (!state.answered) doFillAnswer(false, q); } }, 1000); }
        else revealOptions(q, lv);
      }
    }, 1000);
  }

  setTimeout(() => ui.qcard.scrollIntoView({behavior: window.innerWidth < 900 ? 'auto' : 'smooth', block:'start'}), 70);
}

/* ── REVEAL OPTIONS (fase 2) ──────────────────────────────────────── */
function revealOptions(q, lv) {
  state.phase    = 'answering';
  const isStudy = gameMode === 'study';
  const skillEffect = getEquippedSkill() ? SKILLS.find(s => s.id === getEquippedSkill()) : null;
  const extraTime = (skillEffect && skillEffect.effect === 'extraTime') ? 10 : 0;
  state.timeLeft = isStudy ? 9999 : lv.answer + extraTime;

  // Check if True/False question
  const isTF = q.type === 'tf';
  if (isTF) ui.options.classList.add('tf-mode'); else ui.options.classList.remove('tf-mode');

  // Renderiza alternativas com delay escalonado via CSS
  const letters = isTF ? ['V', 'F'] : LETTERS;
  ui.options.innerHTML = state.opts.map((opt, i) => `
    <button class='option' data-i='${i}'>
      <b>${letters[i] || ''}</b>${opt.text}
    </button>
  `).join('');
  answerStartTime = Date.now();
  ui.options.querySelectorAll('.option').forEach(btn => {
    btn.addEventListener('touchend', (e) => {
      e.preventDefault();
      doAnswer(+btn.dataset.i, false);
    }, {passive: false});
    btn.addEventListener('click', () => doAnswer(+btn.dataset.i, false));
  });

  // Auto-eliminate skill effect
  const activeSkill = getEquippedSkill();
  if (activeSkill === 'memory') {
    setTimeout(() => {
      const wrong = [...ui.options.querySelectorAll('.option')]
        .filter(b => !state.opts[+b.dataset.i].correct);
      if (wrong.length > 0) shuffle(wrong).slice(0,1).forEach(b => b.classList.add('cut'));
    }, 500);
  }
  // Auto-hint skill effect
  if (activeSkill === 'intuition' && !state.used.hint) {
    setTimeout(() => { state.used.hint = true; ui.btnHint.disabled = true; showAssist('💡 (Auto) ' + q.hint); }, 300);
  }

  setPhase('answering', state.timeLeft);
  updateHud();

  clearInterval(state.ticker);
  state.ticker = setInterval(() => {
    state.timeLeft--;
    setPhase('answering', state.timeLeft);
    updateHud();
    if (state.timeLeft <= 0) {
      clearInterval(state.ticker);
      if (!state.answered) doAnswer(null, true);
    }
  }, 1000);
}

/* ── ANSWER ───────────────────────────────────────────────────────── */
async function doAnswer(sel, timedOut) {
  if (state.answered) return;
  state.answered = true;
  clearInterval(state.ticker);

  const q    = state.deck[state.idx];
  const lv   = lvMeta(q.level);
  const btns = [...ui.options.querySelectorAll('.option')];
  const cor  = state.opts.findIndex(o => o.correct);

  // Suspense effect (0.7s delay)
  if (!timedOut && sel !== null) {
    btns.forEach(b => b.style.pointerEvents = 'none');
    await showSuspense();
  }

  // Highlight correto/errado
  btns.forEach(b => b.disabled = true);
  if (cor >= 0) btns[cor].classList.add('ok');
  if (!timedOut && sel !== null && sel !== cor) btns[sel].classList.add('no');

  state.lvStats[q.level].total++;
  let isCorrect = false;
  let fbTitle = timedOut ? '⏰ Tempo esgotado' : WRONG_REACTIONS[Math.floor(Math.random() * WRONG_REACTIONS.length)];
  let fbBody  = q.exp;

  // Anti-guess check
  const answerTime = answerStartTime ? Date.now() - answerStartTime : 99999;
  const antiGuess = checkAntiGuess(answerTime);

  // Time bonus
  const timeBonus = calcTimeBonus(answerTime, lv.answer * 1000);
  const diffMult = getDifficultyMultiplier(q);

  if (!timedOut && sel === cor) {
    isCorrect = true;
    state.lvStats[q.level].ok++;
    state.streak++;
    state.lvStats[q.level].bestStreak = Math.max(state.lvStats[q.level].bestStreak, state.streak);
    let gain = lv.base + (state.streak >= 2 ? STREAK_BONUS : 0);

    // Difficulty multiplier
    gain = Math.round(gain * diffMult);

    // Time bonus
    gain += timeBonus;

    // Combo bonus points
    if (state.streak >= 10) gain += 50;
    else if (state.streak >= 8) gain += 30;
    else if (state.streak >= 5) gain += 15;
    else if (state.streak >= 3) gain += 5;

    // Fury mode doubles
    if (furyActive) gain *= 2;

    // Anti-guess penalty
    if (antiGuess.penalty) gain = Math.round(gain * antiGuess.multiplier);

    state.score += gain;
    fbTitle = CORRECT_REACTIONS[Math.floor(Math.random() * CORRECT_REACTIONS.length)];
    let bonusText = '';
    if (state.streak >= 2) bonusText += ' (+' + STREAK_BONUS + ' sequencia)';
    if (timeBonus > 0) bonusText += ' (+' + timeBonus + ' velocidade)';
    if (furyActive) bonusText += ' (🔥 FURIA x2)';
    if (antiGuess.penalty) bonusText += ' [anti-chute]';
    fbBody = q.exp + bonusText + ' — +' + gain + ' pts.';
    showCombo(state.streak);
    playSound(state.streak >= 3 ? 'combo' : 'correct');
    spawnParticles(isGoldenQuestion(q) ? 'golden' : 'correct');
    spawnConfetti();
    showScoreExplosion(gain);
    vibrate([50]);

    // Coins
    const coinGain = Math.round(gain / 5) * (getEquippedSkill() === 'double' ? 2 : 1);
    addCoins(coinGain, 'answer');

    // Fury activation at 10 streak
    if (state.streak >= 10 && !furyActive) activateFury();
  } else {
    state.streak = 0;
    state.wrongQs.push(q);
    if (furyActive) deactivateFury();
    if (timedOut) fbBody = q.exp + ' — Tempo encerrado antes da resposta.';
    playSound('wrong');
    vibrate([100, 50, 100]);

    // Lose life
    if (livesEnabled && !timedOut) loseLife();
  }

  // Topic stats
  updateTopicStats(q.level, isCorrect);

  // Anti-guess warning
  if (antiGuess.penalty && !timedOut) {
    const agDiv = document.createElement('div');
    agDiv.className = 'anti-guess';
    agDiv.textContent = antiGuess.msg;
    ui.feedbackBox.parentElement.insertBefore(agDiv, ui.feedbackBox.nextSibling);
    setTimeout(() => agDiv.remove(), 5000);
  }

  // Feedback
  ui.feedbackBox.className = 'feedback' + (isCorrect ? ' ok' : '');
  ui.fbTitle.textContent = fbTitle;
  ui.fbBody.textContent  = fbBody;
  ui.fbRef.textContent   = '📜 ' + q.ref + '. ' + q.note;
  ui.feedbackBox.classList.remove('hidden');
  ui.btnNext.disabled = false;

  // Narrator comment
  const narr = getNarratorComment(isCorrect, q.diff || 'normal');
  const narrDiv = document.createElement('div');
  narrDiv.className = 'narrator-box';
  narrDiv.innerHTML = '<span class="nr-icon">🎙️</span>' + narr;
  ui.feedbackBox.appendChild(narrDiv);

  // Phase indicator
  setPhase(isCorrect ? 'done-ok' : timedOut ? 'done-time' : 'done-no', 0);

  refreshMedals();
  updateHud();
}

/* ── NEXT QUESTION ────────────────────────────────────────────────── */
function nextQuestion() {
  state.idx++;
  // Infinite mode: keep going if last answer was correct, otherwise finish
  if (gameMode === 'infinite' && state.wrongQs.length > 0 && state.wrongQs[state.wrongQs.length-1] === state.deck[state.idx-1]) {
    finishGame(); return;
  }
  // If we ran out of questions in infinite mode, reshuffle
  if (gameMode === 'infinite' && state.idx >= state.deck.length) {
    state.deck = state.deck.concat(shuffle([...QUESTIONS]));
  }
  if (state.idx >= state.deck.length) { finishGame(); return; }
  renderQuestion();
}

/* ── FINISH ───────────────────────────────────────────────────────── */
function finishGame() {
  clearInterval(state.ticker);
  state.totalSec = elapsed();
  ui.game.classList.add('hidden');
  ui.result.classList.remove('hidden');
  ui.progress.style.width = '100%';
  refreshMedals();

  const allOk  = Object.values(state.lvStats).reduce((s,x)=>s+x.ok, 0);
  const allTot = state.deck.length;
  const acc    = allTot > 0 ? Math.round(allOk/allTot*100) : 0;
  const bStrk  = Object.values(state.lvStats).reduce((m,x)=>Math.max(m,x.bestStreak), 0);

  ui.resTitle.textContent = playerTitle(state.score);
  ui.resScore.textContent = `${state.score} pts`;
  ui.resText.textContent  = `Acertou ${allOk} de ${allTot} questoes em ${fmtTime(state.totalSec)}.`;

  // Stats grid
  ui.statGrid.innerHTML = `
    <div class='stat-box ${acc>=80?"g":""}'><span class='sv'>${acc}%</span><span class='sl'>Precisao</span></div>
    <div class='stat-box'><span class='sv'>${allOk}/${allTot}</span><span class='sl'>Acertos</span></div>
    <div class='stat-box'><span class='sv'>${bStrk}</span><span class='sl'>Melhor combo</span></div>
    <div class='stat-box'><span class='sv'>${fmtTime(state.totalSec)}</span><span class='sl'>Tempo total</span></div>
  `;

  // Perguntas erradas
  if (state.wrongQs.length > 0) {
    ui.wrongList.innerHTML = state.wrongQs.map(q => `
      <div class='wrong-item'>
        <b>Nivel ${q.level} · ${q.ref}</b>
        ${q.q.length > 110 ? q.q.slice(0,110)+'...' : q.q}
        <span class='wrong-correct'>✓ Correto: ${q.o[q.a]}</span>
      </div>
    `).join('');
    ui.wrongSection.classList.remove('hidden');
  } else {
    ui.wrongSection.classList.add('hidden');
  }

  // Enhanced stats
  const avgTime = allTot > 0 ? (state.totalSec / allTot).toFixed(1) : 0;
  const weak = getWeakestTopics();
  const strong = getStrongestTopics();
  ui.statGrid.innerHTML += '<div class="stat-box"><span class="sv">' + avgTime + 's</span><span class="sl">Tempo medio</span></div>' +
    '<div class="stat-box ' + (gameMode !== "classic" ? "g" : "") + '"><span class="sv">' + gameMode + '</span><span class="sl">Modo</span></div>';

  if (strong.length > 0) {
    ui.statGrid.innerHTML += '<div class="stat-box g" style="grid-column:1/-1"><span class="sv">💪 ' + strong.join(', ') + '</span><span class="sl">Temas dominados</span></div>';
  }
  if (weak.length > 0) {
    ui.statGrid.innerHTML += '<div class="stat-box" style="grid-column:1/-1"><span class="sv">📖 ' + weak.join(', ') + '</span><span class="sl">Temas para revisar</span></div>';
  }

  // XP calculation
  const gameXP = calcGameXP();
  const xpMultSkill = getEquippedSkill() === 'scholar' ? 1.25 : 1;
  addXP(Math.round(gameXP * xpMultSkill));

  // Update profile stats
  profile.gamesPlayed++;
  profile.totalCorrect += allOk;
  profile.totalQuestions += allTot;
  profile.history.push({ accuracy: acc, score: state.score, date: new Date().toISOString().slice(0,10), mode: gameMode });
  if (profile.history.length > 50) profile.history = profile.history.slice(-50);
  saveProfile();

  // Coins reward
  const gameCoins = Math.round(gameXP / 3) * (getEquippedSkill() === 'double' ? 2 : 1);
  addCoins(gameCoins, 'game');

  // XP notification
  ui.resText.textContent += ' (+' + Math.round(gameXP * xpMultSkill) + ' XP, +' + gameCoins + ' moedas)';

  // Particles
  spawnParticles('finish');

  // Speedrun cleanup
  if (gameMode === 'speedrun') stopSpeedrunTimer();

  // Easter eggs
  checkEasterEggs();

  // Render evolution
  renderEvolution();

  ui.btnSave.disabled    = false;
  ui.btnSave.textContent = 'Salvar no ranking';
  setTimeout(() => ui.result.scrollIntoView({behavior: window.innerWidth < 900 ? 'auto' : 'smooth', block:'start'}), 90);
}

/* ── HELPERS (ajudas) ─────────────────────────────────────────────── */
function showAssist(msg) {
  ui.assistBox.textContent = msg;
  ui.assistBox.classList.remove('hidden');
}
function useCut() {
  if (state.used.cut || state.answered || state.phase !== 'answering') return;
  const wrong = [...ui.options.querySelectorAll('.option')]
    .filter(b => !state.opts[+b.dataset.i].correct);
  shuffle(wrong).slice(0,2).forEach(b => b.classList.add('cut'));
  state.used.cut = true; ui.btnCut.disabled = true;
  showAssist('Duas opcoes incorretas foram eliminadas.');
}
function useHint() {
  if (state.used.hint || state.answered) return;
  state.used.hint = true; ui.btnHint.disabled = true;
  showAssist('💡 Dica: ' + state.deck[state.idx].hint);
}
function useLaw() {
  if (state.used.law || state.answered) return;
  const q = state.deck[state.idx];
  state.used.law = true; ui.btnLaw.disabled = true;
  showAssist(`📜 ${q.ref}: ${q.note}`);
}

function useSkip() {
  if (state.used.skip || state.answered || state.phase === 'idle') return;
  state.used.skip = true;
  if (ui.btnSkip) ui.btnSkip.disabled = true;
  playSound('skip');
  showAssist('⏭ Pergunta pulada! Sem pontos.');
  state.answered = true;
  clearInterval(state.ticker);
  state.wrongQs.push(state.deck[state.idx]);
  setPhase('done-no', 0);
  ui.btnNext.disabled = false;
}

function useExtraTime() {
  if (state.used.extraTime || state.answered || state.phase !== 'answering') return;
  state.used.extraTime = true;
  if (ui.btnExtraTime) ui.btnExtraTime.disabled = true;
  state.timeLeft += 15;
  showAssist('⏱ +15 segundos adicionados!');
  playSound('tick');
}

/* ── RANKING ──────────────────────────────────────────────────────── */
function renderRanking(list) {
  if (!Array.isArray(list) || !list.length) {
    ui.rankingList.innerHTML = "<div class='empty'>Nenhum resultado ainda.</div>"; return;
  }
  const sorted = [...list].sort((a,b) => b.score!==a.score ? b.score-a.score : a.completion_seconds-b.completion_seconds);
  const icons  = ['🥇','🥈','🥉'];
  ui.rankingList.innerHTML = sorted.slice(0,12).map((e,i) => `
    <div class='rank-item' style='animation-delay:${i*0.06}s'>
      <span class='rk-name'>${icons[i]||((i+1)+'.')} ${e.name} — ${e.score} pts</span>
      <span class='rk-meta'>⏱ ${fmtTime(e.completion_seconds)} | ✓ ${e.correct_answers}/${e.total_questions}</span>
      <span class='rk-sub'>${e.title}${e.medals&&e.medals.length?' · '+e.medals.join(', '):''}</span>
      <span class='rk-sub'>${e.saved_at}</span>
    </div>
  `).join('');
}

async function loadRanking() {
  try {
    const r = await fetch('/api/ranking?t='+Date.now(), {cache:'no-store'});
    if (!r.ok) throw new Error();
    renderRanking(await r.json());
  } catch {
    ui.rankingList.innerHTML = "<div class='empty'>Ranking indisponivel no momento.</div>";
  }
}

function startPoll() {
  if (state.rankTick) clearInterval(state.rankTick);
  state.rankTick = setInterval(() => { if (!document.hidden) loadRanking(); }, POLL_MS);
}

async function saveResult() {
  if (state.saved) return;
  const name = ui.playerName.value.trim();
  if (!name) { ui.playerName.focus(); return; }

  const allOk = Object.values(state.lvStats).reduce((s,x)=>s+x.ok, 0);
  const payload = {
    name,
    score: state.score,
    title: playerTitle(state.score),
    medals: computeMedals().map(m=>m.name),
    completion_seconds: state.totalSec,
    correct_answers: allOk,
    total_questions: state.deck.length,
  };

  ui.btnSave.disabled = true; ui.btnSave.textContent = 'Salvando...';
  try {
    const r = await fetch('/api/ranking', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error();
    state.saved = true; ui.btnSave.textContent = '✓ Salvo!';
    renderRanking(await r.json());
  } catch {
    ui.btnSave.disabled = false; ui.btnSave.textContent = 'Erro — tente novamente';
  }
}

/* ── RESET & START ────────────────────────────────────────────────── */
function resetGame() {
  clearInterval(state.ticker);
  state.deck = buildDeck();
  state.idx = 0; state.score = 0; state.streak = 0;
  state.phase = 'idle'; state.timeLeft = 0;
  state.answered = false; state.opts = [];
  state.startedAt = Date.now(); state.totalSec = 0;
  state.saved = false;
  state.used = {cut:false, hint:false, law:false, skip:false, extraTime:false};
  resetLives();
  state.prevMedals = [];
  state.wrongQs = [];
  state.lvStats = {};
  LEVELS.forEach(lv => state.lvStats[lv.id] = {total:0, ok:0, bestStreak:0});
  ui.playerName.value = '';
  ui.feedbackBox.classList.add('hidden');
  ui.assistBox.classList.add('hidden');
  ui.btnNext.disabled = true;
  refreshMedals();
  updateHud();
}

async function startGame() {
  await showEpicIntro();
  resetGame();
  resetLives();
  deactivateFury();
  initAudio();
  checkDailyStreak();
  checkStreakMilestones();
  applySkillEffects();

  // Build deck based on mode
  if (gameMode !== 'classic') {
    state.deck = buildDeckForMode();
    if (state.deck.length === 0) { alert('Sem questoes disponiveis!'); return; }
  }

  // Hide lives bar in study/speedrun mode
  const livesBar = document.getElementById('lives-bar');
  if (livesBar) livesBar.classList.toggle('hidden', gameMode === 'study' || gameMode === 'speedrun');

  ui.intro.classList.add('hidden');
  ui.result.classList.add('hidden');
  ui.game.classList.remove('hidden');

  // Speedrun mode timer
  if (gameMode === 'speedrun') startSpeedrunTimer();

  renderQuestion();
  setTimeout(() => ui.game.scrollIntoView({behavior: window.innerWidth < 900 ? 'auto' : 'smooth', block:'start'}), 60);
}

/* ── RENDER LEVEL CARDS ───────────────────────────────────────────── */
function renderLevelCards() {
  ui.levels.innerHTML = LEVELS.map(lv => `
    <div class='level-card'>
      <span class='chip'>Nivel ${lv.id}</span>
      <h3>${lv.name}</h3>
      <p>${QPL} questoes sorteadas<br>+${lv.base} pts base por acerto<br>📖 ${lv.read}s leitura + ⏳ ${lv.answer}s resposta</p>
    </div>
  `).join('');
}

/* ── PWA ──────────────────────────────────────────────────────────── */
function setupPWA() {
  /* Limpa TODOS os caches antigos e re-registra o SW sempre */
  if ('caches' in window) {
    caches.keys().then(keys => keys.forEach(k => {
      if (!k.includes('a3ilpb-v1774407760')) caches.delete(k);
    }));
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(regs => {
      regs.forEach(r => r.update());
    });
  }

  if ('serviceWorker' in navigator)
    navigator.serviceWorker.register('/service-worker.js').catch(()=>{});
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault(); installPrompt = e; ui.btnInstall.classList.remove('hidden');
  });
  window.addEventListener('appinstalled', () => { installPrompt=null; ui.btnInstall.classList.add('hidden'); });
}

/* ── EVENTS ───────────────────────────────────────────────────────── */
ui.btnStart.addEventListener('click',   startGame);
ui.btnRestart.addEventListener('click', startGame);
ui.btnNext.addEventListener('click',    nextQuestion);
ui.btnReload.addEventListener('click',  loadRanking);
ui.btnSave.addEventListener('click',    saveResult);
ui.btnCut.addEventListener('click',     useCut);
ui.btnHint.addEventListener('click',    useHint);
ui.btnLaw.addEventListener('click',     useLaw);
ui.btnSkip?.addEventListener('click',    useSkip);
ui.btnExtraTime?.addEventListener('click', useExtraTime);
document.getElementById('btn-share')?.addEventListener('click', shareResults);
document.getElementById('btn-save-library')?.addEventListener('click', saveToLibrary);
document.getElementById('btn-clear-library')?.addEventListener('click', clearLibrary);
document.getElementById('btn-sound')?.addEventListener('click', () => { profile.soundEnabled = !profile.soundEnabled; saveProfile(); document.getElementById('btn-sound').textContent = profile.soundEnabled ? '🔊' : '🔇'; });
document.getElementById('btn-settings')?.addEventListener('click', openSettings);
ui.btnInstall.addEventListener('click', async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null; ui.btnInstall.classList.add('hidden');
});



/* ══════════════════════════════════════════════════════════════════════
   NEW SYSTEMS - XP, Levels, Modes, Sound, Themes, etc.
   ══════════════════════════════════════════════════════════════════════ */

/* ── PLAYER LEVELS ─────────────────────────────────────────────────── */
const PLAYER_LEVELS = [
  {level:1,  xp:0,    title:'Estudante',               icon:'📚'},
  {level:2,  xp:100,  title:'Estagiario Juridico',     icon:'📝'},
  {level:3,  xp:250,  title:'Bacharel em Direito',     icon:'🎓'},
  {level:5,  xp:500,  title:'Jurista',                  icon:'⚖️'},
  {level:8,  xp:1000, title:'Magistrado',               icon:'⚖️'},
  {level:10, xp:1500, title:'Desembargador',            icon:'🏛️'},
  {level:15, xp:2500, title:'Ministro do STF',          icon:'🏆'},
  {level:20, xp:4000, title:'Guardiao da Constituicao', icon:'👑'},
];

const AVATARS = [
  {id:'estudante', icon:'📚', name:'Estudante'},
  {id:'advogado',  icon:'⚖️', name:'Advogado'},
  {id:'juiza',     icon:'⚖️', name:'Juiza'},
  {id:'ministra',  icon:'⚖️',  name:'Ministra'},
  {id:'professor', icon:'📖', name:'Professor'},
  {id:'guardiao',  icon:'🛡️', name:'Guardiao'},
];

const THEMES_MAP = {
  dark:  {cls:'',            name:'Juridico', preview:'#04080f'},
  light: {cls:'theme-light', name:'Claro',    preview:'#f0f4fa'},
  stf:   {cls:'theme-stf',   name:'STF',      preview:'#060e1c'},
  neon:  {cls:'theme-neon',  name:'Neon',     preview:'#0a000a'},
};

const UNLOCKS = [
  {level:3,  feature:'themes',   desc:'Temas visuais desbloqueados!'},
  {level:5,  feature:'hard',     desc:'Perguntas dificeis habilitadas!'},
  {level:8,  feature:'speedrun', desc:'Modo Relampago desbloqueado!'},
  {level:10, feature:'infinite', desc:'Modo Infinito desbloqueado!'},
];

const CORRECT_REACTIONS = [
  '🎉 Excelente interpretacao constitucional!',
  '⚖️ Perfeito! Fundamentacao juridica impecavel!',
  '🏛️ Nem o STF discordaria!',
  '📜 Conhecimento constitucional solido!',
  '🎯 Precisao juridica impressionante!',
  '⭐ Resposta digna de um constitucionalista!',
  '🔥 Voce domina o texto constitucional!',
  '💎 Interpretacao constitucional impecavel!',
];

const WRONG_REACTIONS = [
  '⚖️ Quase! Veja o fundamento juridico.',
  '📖 Boa tentativa! Revise esse artigo.',
  '🔍 Atencao ao texto constitucional.',
  '📚 Oportunidade de aprendizado!',
  '💡 A Constituicao surpreende as vezes.',
];

/* ── PROFILE MANAGEMENT ────────────────────────────────────────────── */
function loadProfile() {
  try {
    const s = localStorage.getItem('gc_profile');
    if (s) return JSON.parse(s);
  } catch(e) {}
  return {
    xp:0, gamesPlayed:0, totalCorrect:0, totalQuestions:0,
    dailyStreak:0, lastPlayDate:null,
    avatar:'estudante', theme:'dark', soundEnabled:true,
    unlockedMedals:[], history:[], wrongLibrary:[]
  };
}
const profile = loadProfile();

function saveProfile() {
  try { localStorage.setItem('gc_profile', JSON.stringify(profile)); } catch(e) {}
  pushProfileToServer();
}

function getPlayerLevel(xp) {
  let lvl = PLAYER_LEVELS[0];
  for (const l of PLAYER_LEVELS) { if (xp >= l.xp) lvl = l; }
  return lvl;
}

function getNextLevel(xp) {
  const cur = getPlayerLevel(xp);
  for (const l of PLAYER_LEVELS) { if (l.xp > xp) return l; }
  return null;
}

function addXP(amount) {
  const oldLevel = getPlayerLevel(profile.xp);
  profile.xp += amount;
  const newLevel = getPlayerLevel(profile.xp);
  if (newLevel.level > oldLevel.level) {
    showLevelUp(newLevel);
    playSound('levelup');
    checkUnlocks(newLevel.level);
  }
  saveProfile();
  refreshProfileBar();
}

function refreshProfileBar() {
  const lvl = getPlayerLevel(profile.xp);
  const next = getNextLevel(profile.xp);
  const av = AVATARS.find(a => a.id === profile.avatar) || AVATARS[0];

  const pAvatar = document.getElementById('profile-avatar');
  const pName = document.getElementById('profile-display-name');
  const pTitle = document.getElementById('profile-display-title');
  const xpLabel = document.getElementById('xp-level-label');
  const xpAmount = document.getElementById('xp-amount');
  const xpFill = document.getElementById('xp-bar-fill');
  const streakDays = document.getElementById('streak-days');

  if (pAvatar) pAvatar.textContent = av.icon;
  if (pName) pName.textContent = ui.playerName.value || 'Jogador';
  if (pTitle) pTitle.textContent = 'Nv ' + lvl.level + ' — ' + lvl.title;
  if (xpLabel) xpLabel.textContent = 'Nivel ' + lvl.level;
  if (streakDays) streakDays.textContent = profile.dailyStreak;

  if (next) {
    const progress = ((profile.xp - lvl.xp) / (next.xp - lvl.xp)) * 100;
    if (xpAmount) xpAmount.textContent = profile.xp + ' / ' + next.xp + ' XP';
    if (xpFill) xpFill.style.width = Math.min(progress, 100) + '%';
  } else {
    if (xpAmount) xpAmount.textContent = profile.xp + ' XP (MAX)';
    if (xpFill) xpFill.style.width = '100%';
  }
}

/* ── SOUND SYSTEM ──────────────────────────────────────────────────── */
let audioCtx;
const SND = {
  correct:  [523.25, 659.25, 783.99],
  wrong:    [311.13, 233.08],
  combo:    [523.25, 659.25, 783.99, 1046.5],
  medal:    [783.99, 987.77, 1174.66],
  levelup:  [261.63, 329.63, 392, 523.25, 659.25, 783.99],
  tick:     [880],
  skip:     [440, 554.37],
};

function initAudio() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  }
}

function playTone(freq, dur, delay) {
  if (!audioCtx || !profile.soundEnabled) return;
  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.frequency.value = freq; osc.type = 'sine';
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime + delay);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + delay + dur);
    osc.start(audioCtx.currentTime + delay);
    osc.stop(audioCtx.currentTime + delay + dur);
  } catch(e) {}
}

function playSound(type) {
  initAudio();
  const notes = SND[type];
  if (!notes) return;
  notes.forEach((f, i) => playTone(f, 0.18, i * 0.1));
}

/* ── THEME SYSTEM ──────────────────────────────────────────────────── */
function applyTheme(t) {
  const theme = THEMES_MAP[t] || THEMES_MAP.dark;
  document.body.className = theme.cls;
  profile.theme = t;
  saveProfile();
}

/* ── DAILY STREAK ──────────────────────────────────────────────────── */
function checkDailyStreak() {
  const today = new Date().toISOString().slice(0, 10);
  if (profile.lastPlayDate === today) return;
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  if (profile.lastPlayDate === yesterday) {
    profile.dailyStreak++;
  } else if (profile.lastPlayDate !== today) {
    profile.dailyStreak = 1;
  }
  profile.lastPlayDate = today;
  const streakXP = Math.min(profile.dailyStreak * 10, 100);
  addXP(streakXP);
  showStreakNotification(profile.dailyStreak, streakXP);
  saveProfile();
  refreshProfileBar();
}

function showStreakNotification(days, xp) {
  const el = document.getElementById('streak-notif');
  if (!el) return;
  el.innerHTML = '<div class="sn-fire">' + '🔥'.repeat(Math.min(days, 5)) + '</div>' +
    '<div class="sn-text">Sequencia de ' + days + ' dia' + (days > 1 ? 's' : '') + '!</div>' +
    '<div class="sn-xp">+' + xp + ' XP bonus</div>';
  el.className = 'streak-notif';
  setTimeout(() => { el.className = 'hidden'; }, 4000);
}

/* ── LEVEL UP DISPLAY ──────────────────────────────────────────────── */
function showLevelUp(lvl) {
  const el = document.getElementById('level-up-overlay');
  if (!el) return;
  el.innerHTML = '<div class="levelup-card">' +
    '<div class="lu-icon">' + lvl.icon + '</div>' +
    '<div class="lu-title">Nivel ' + lvl.level + '!</div>' +
    '<div class="lu-subtitle">' + lvl.title + '</div>' +
    '<div class="lu-desc">Continue jogando para desbloquear mais conteudo!</div>' +
    '<button class="btn primary" style="margin-top:16px" onclick="closeLevelUp()">Continuar</button>' +
    '</div>';
  el.className = 'levelup-overlay';
}

function closeLevelUp() {
  const el = document.getElementById('level-up-overlay');
  if (el) el.className = 'hidden';
}

/* ── UNLOCK SYSTEM ─────────────────────────────────────────────────── */
function checkUnlocks(level) {
  UNLOCKS.forEach(u => {
    if (level >= u.level) {
      const modeCard = document.querySelector('.mode-card[data-mode="' + u.feature + '"]');
      if (modeCard) modeCard.classList.remove('locked');
    }
  });
}

function isUnlocked(feature) {
  const lvl = getPlayerLevel(profile.xp).level;
  const unlock = UNLOCKS.find(u => u.feature === feature);
  return !unlock || lvl >= unlock.level;
}

/* ── GAME MODES ────────────────────────────────────────────────────── */
let gameMode = 'classic';
let speedrunTimer = null;
let speedrunTimeLeft = 120;

function selectMode(mode) {
  if (mode !== 'classic' && mode !== 'replay' && mode !== 'study' && !isUnlocked(mode)) {
    const unlock = UNLOCKS.find(u => u.feature === mode);
    if (unlock) alert('Desbloqueado no nivel ' + unlock.level + '!');
    return;
  }
  if (mode === 'replay' && profile.wrongLibrary.length === 0) {
    alert('Nenhuma questao errada salva para treino!');
    return;
  }
  gameMode = mode;
  document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('active'));
  const card = document.querySelector('.mode-card[data-mode="' + mode + '"]');
  if (card) card.classList.add('active');
}

function buildDeckForMode() {
  if (gameMode === 'infinite') {
    return shuffle([...QUESTIONS]);
  }
  if (gameMode === 'speedrun') {
    return shuffle([...QUESTIONS]);
  }
  if (gameMode === 'study') {
    return shuffle([...QUESTIONS]);
  }
  if (gameMode === 'replay') {
    return shuffle(profile.wrongLibrary.map(q => {
      const found = QUESTIONS.find(oq => oq.q === q.q);
      return found || q;
    }));
  }
  return buildDeck();
}

/* ── ANTI-GUESS ────────────────────────────────────────────────────── */
let answerStartTime = 0;

function checkAntiGuess(answerTimeMs) {
  if (answerTimeMs < 1500 && state.phase === 'answering') {
    return { penalty: true, multiplier: 0.5, msg: '⚠️ Resposta muito rapida! Pontuacao reduzida pela metade.' };
  }
  return { penalty: false, multiplier: 1 };
}

/* ── SHARE RESULTS ─────────────────────────────────────────────────── */
function shareResults() {
  const allOk = Object.values(state.lvStats).reduce((s, x) => s + x.ok, 0);
  const allTot = state.deck.length;
  const text = 'Fiz ' + allOk + '/' + allTot + ' no Guardiao da Constituicao! Pontuacao: ' + state.score + ' pts. Modo: ' + gameMode;
  if (navigator.share) {
    navigator.share({ title: 'Guardiao da Constituicao', text: text }).catch(() => {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => alert('Resultado copiado!')).catch(() => {});
  } else {
    prompt('Copie seu resultado:', text);
  }
}

/* ── KNOWLEDGE LIBRARY ─────────────────────────────────────────────── */
function saveToLibrary() {
  if (state.wrongQs.length === 0) return;
  state.wrongQs.forEach(q => {
    if (!profile.wrongLibrary.some(w => w.q === q.q)) {
      profile.wrongLibrary.push({ q: q.q, o: q.o, a: q.a, ref: q.ref, exp: q.exp, level: q.level });
    }
  });
  saveProfile();
  renderLibrary();
  alert('Questoes salvas na biblioteca de estudo!');
}

function renderLibrary() {
  const el = document.getElementById('library-list');
  const clearBtn = document.getElementById('btn-clear-library');
  if (!el) return;
  if (profile.wrongLibrary.length === 0) {
    el.innerHTML = '<div class="empty">Nenhuma questao salva para estudo.</div>';
    if (clearBtn) clearBtn.classList.add('hidden');
    return;
  }
  if (clearBtn) clearBtn.classList.remove('hidden');
  el.innerHTML = profile.wrongLibrary.slice(-10).reverse().map(q =>
    '<div class="lib-item"><b>Nv ' + q.level + ' · ' + q.ref + '</b>' +
    (q.q.length > 100 ? q.q.slice(0, 100) + '...' : q.q) +
    '<span class="lib-answer">✓ ' + q.o[q.a] + '</span></div>'
  ).join('');
}

function clearLibrary() {
  if (!confirm('Limpar toda a biblioteca de estudo?')) return;
  profile.wrongLibrary = [];
  saveProfile();
  renderLibrary();
}

/* ── EVOLUTION CHART ───────────────────────────────────────────────── */
function renderEvolution() {
  const canvas = document.getElementById('evo-chart');
  if (!canvas || profile.history.length < 2) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.offsetWidth;
  const h = canvas.height = canvas.offsetHeight;
  ctx.clearRect(0, 0, w, h);

  const data = profile.history.slice(-20);
  const maxVal = 100;
  const step = w / (data.length - 1 || 1);
  const pad = 10;

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad + ((h - 2 * pad) * i) / 4;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  // Line
  ctx.strokeStyle = '#1565c0';
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = i * step;
    const y = h - pad - ((d.accuracy / maxVal) * (h - 2 * pad));
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Points
  ctx.fillStyle = '#1565c0';
  data.forEach((d, i) => {
    const x = i * step;
    const y = h - pad - ((d.accuracy / maxVal) * (h - 2 * pad));
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
  });
}

/* ── SETTINGS MODAL ────────────────────────────────────────────────── */
function openSettings() {
  const modal = document.getElementById('settings-modal');
  if (!modal) return;
  const lvl = getPlayerLevel(profile.xp);
  modal.className = 'modal-overlay';
  modal.innerHTML = '<div class="modal-content">' +
    '<button class="modal-close" onclick="closeSettings()">✕</button>' +
    '<h2>⚙️ Configuracoes</h2>' +

    '<div class="setting-group"><label>Tema visual' +
    (isUnlocked('themes') ? '' : ' 🔒 (Nivel 3)') + '</label>' +
    '<div class="theme-grid">' +
    Object.entries(THEMES_MAP).map(([k, v]) =>
      '<div class="theme-btn' + (profile.theme === k ? ' active' : '') + '" ' +
      'style="background:' + v.preview + ';color:#fff" ' +
      (isUnlocked('themes') || k === 'dark' ? 'onclick="applyTheme(\'' + k + '\');openSettings()"' : '') +
      '>' + v.name + '</div>'
    ).join('') +
    '</div></div>' +

    '<div class="setting-group"><label>Avatar</label>' +
    '<div class="avatar-grid">' +
    AVATARS.map(a =>
      '<div class="avatar-btn' + (profile.avatar === a.id ? ' active' : '') + '" ' +
      'onclick="profile.avatar=\'' + a.id + '\';saveProfile();refreshProfileBar();openSettings()">' +
      a.icon + '<span>' + a.name + '</span></div>'
    ).join('') +
    '</div></div>' +

    '<div class="setting-group"><label>Audio</label>' +
    '<div class="toggle-row"><span>Efeitos sonoros</span>' +
    '<button class="toggle' + (profile.soundEnabled ? ' on' : '') + '" ' +
    'onclick="profile.soundEnabled=!profile.soundEnabled;saveProfile();openSettings()"></button>' +
    '</div></div>' +

    '<div class="setting-group"><label>Estatisticas do jogador</label>' +
    '<div class="stat-grid-ext">' +
    '<div class="stat-box-ext"><span class="sv">' + lvl.level + '</span><span class="sl">Nivel</span></div>' +
    '<div class="stat-box-ext"><span class="sv">' + profile.xp + '</span><span class="sl">XP Total</span></div>' +
    '<div class="stat-box-ext"><span class="sv">' + profile.gamesPlayed + '</span><span class="sl">Partidas</span></div>' +
    '<div class="stat-box-ext"><span class="sv">' + profile.totalCorrect + '</span><span class="sl">Acertos</span></div>' +
    '<div class="stat-box-ext"><span class="sv">' + (profile.totalQuestions > 0 ? Math.round(profile.totalCorrect / profile.totalQuestions * 100) : 0) + '%</span><span class="sl">Precisao</span></div>' +
    '<div class="stat-box-ext"><span class="sv">' + profile.dailyStreak + '</span><span class="sl">Streak</span></div>' +
    '</div></div>' +

    '<div class="setting-group"><label>Titulo atual</label>' +
    '<p style="color:#ffd700;font-weight:800;font-size:1.1rem">' + lvl.icon + ' ' + lvl.title + '</p></div>' +

    '<div class="setting-group"><label>Moedas</label>' +
    '<p style="color:#ffd700;font-weight:800;font-size:1.3rem">🪙 ' + getCoins() + ' moedas</p></div>' +

    '<div class="setting-group"><label>Habilidade equipada</label>' +
    '<p style="color:#ce93d8;font-weight:800;font-size:1rem">' +
    (getEquippedSkill() ? (SKILLS.find(s=>s.id===getEquippedSkill()) || {icon:'',name:'Nenhuma'}).icon + ' ' + (SKILLS.find(s=>s.id===getEquippedSkill()) || {name:'Nenhuma'}).name : 'Nenhuma') +
    '</p></div>' +

    '</div>';
}

function closeSettings() {
  const modal = document.getElementById('settings-modal');
  if (modal) modal.className = 'hidden';
}

/* ── ADAPTIVE DIFFICULTY ───────────────────────────────────────────── */
function getAdaptiveDifficulty() {
  if (profile.totalQuestions < 10) return 'normal';
  const acc = profile.totalCorrect / profile.totalQuestions;
  if (acc >= 0.85) return 'hard';
  if (acc <= 0.45) return 'easy';
  return 'normal';
}

/* ── EASTER EGGS ───────────────────────────────────────────────────── */
function checkEasterEggs() {
  const allOk = Object.values(state.lvStats).reduce((s, x) => s + x.ok, 0);
  const allTot = state.deck.length;
  const el = document.getElementById('easter-egg-msg');
  if (!el) return;

  if (allOk === allTot && allTot >= 15) {
    el.textContent = '🏛️ "Voce e digno do Supremo. A Constituicao esta em boas maos." — Guardiao da Constituicao';
    el.classList.remove('hidden');
  } else if (allOk === allTot && allTot >= 5) {
    el.textContent = '⚖️ "Interpretacao constitucional impecavel. Nem o STF discordaria."';
    el.classList.remove('hidden');
  } else if (state.score >= 250) {
    el.textContent = '👑 "Poucos alcancam esse patamar. Voce honra a Constituicao."';
    el.classList.remove('hidden');
  } else {
    el.classList.add('hidden');
  }
}

/* ── ENHANCED FINISH GAME ──────────────────────────────────────────── */
function calcGameXP() {
  const allOk = Object.values(state.lvStats).reduce((s, x) => s + x.ok, 0);
  const bStrk = Object.values(state.lvStats).reduce((m, x) => Math.max(m, x.bestStreak), 0);
  let xp = 50;
  xp += allOk * 10;
  xp += bStrk * 5;
  if (gameMode === 'speedrun') xp = Math.round(xp * 1.5);
  if (gameMode === 'infinite') xp = Math.round(xp * 1.3);
  return xp;
}

/* ── INIT MODE CARDS ───────────────────────────────────────────────── */
function initModeCards() {
  UNLOCKS.forEach(u => {
    const card = document.querySelector('.mode-card[data-mode="' + u.feature + '"]');
    if (card && !isUnlocked(u.feature)) {
      card.classList.add('locked');
      let badge = card.querySelector('.lock-badge');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'lock-badge';
        card.appendChild(badge);
      }
      badge.textContent = '🔒 Nv ' + u.level;
    }
  });
}

/* ── SPEEDRUN MODE ─────────────────────────────────────────────────── */
function startSpeedrunTimer() {
  speedrunTimeLeft = 120;
  const bar = document.getElementById('speedrun-bar');
  const fill = document.getElementById('speedrun-fill');
  if (bar) bar.classList.remove('hidden');

  speedrunTimer = setInterval(() => {
    speedrunTimeLeft--;
    if (fill) fill.style.width = ((speedrunTimeLeft / 120) * 100) + '%';
    if (speedrunTimeLeft <= 0) {
      clearInterval(speedrunTimer);
      finishGame();
    }
  }, 1000);
}

function stopSpeedrunTimer() {
  clearInterval(speedrunTimer);
  const bar = document.getElementById('speedrun-bar');
  if (bar) bar.classList.add('hidden');
}



/* ══════════════════════════════════════════════════════════════════════
   V2 SYSTEMS – Lives, Fury, Golden, Boss, Particles, Skills, Coins, etc.
   ══════════════════════════════════════════════════════════════════════ */

/* ── LIVES SYSTEM ──────────────────────────────────────────────────── */
let lives = 3;
let livesEnabled = true;

function resetLives() {
  lives = 3;
  livesEnabled = (gameMode === 'classic' || gameMode === 'infinite');
  const bar = document.getElementById('lives-bar');
  if (bar) bar.classList.toggle('hidden', !livesEnabled);
  for (let i = 1; i <= 3; i++) {
    const h = document.getElementById('heart-' + i);
    if (h) { h.className = 'heart'; }
  }
}

function loseLife() {
  if (!livesEnabled) return false;
  lives--;
  const idx = lives + 1;
  const h = document.getElementById('heart-' + idx);
  if (h) { h.className = 'heart breaking'; setTimeout(() => h.className = 'heart lost', 500); }
  vibrate([100, 50, 100]);
  if (lives <= 0) {
    setTimeout(() => finishGame(), 600);
    return true;
  }
  return false;
}

/* ── FURY MODE ─────────────────────────────────────────────────────── */
let furyActive = false;
let furyTimeout = null;

function activateFury() {
  if (furyActive) return;
  furyActive = true;
  playSound('levelup');

  const game = document.getElementById('game');
  if (game) game.classList.add('fury-active');

  const ov = document.getElementById('fury-overlay');
  if (ov) { ov.className = 'fury-overlay'; }

  // Show fury banner
  const banner = document.createElement('div');
  banner.className = 'fury-banner';
  banner.textContent = '🔥 MODO FURIA 🔥';
  document.body.appendChild(banner);
  setTimeout(() => banner.remove(), 2000);

  vibrate([200, 100, 200, 100, 200]);

  // Fury lasts until streak breaks
  furyTimeout = null;
}

function deactivateFury() {
  furyActive = false;
  const game = document.getElementById('game');
  if (game) game.classList.remove('fury-active');
  const ov = document.getElementById('fury-overlay');
  if (ov) ov.className = 'hidden';
}

/* ── GOLDEN & BOSS QUESTION DETECTION ──────────────────────────────── */
function isGoldenQuestion(q) { return q.golden === true; }
function isBossQuestion(q) { return q.boss === true; }

/* ── SUSPENSE EFFECT ───────────────────────────────────────────────── */
function showSuspense() {
  return new Promise(resolve => {
    const el = document.getElementById('suspense-overlay');
    if (!el) { resolve(); return; }
    el.className = 'suspense-overlay';
    el.innerHTML = '<div class="suspense-text">⚖️ Processando resposta...</div>';
    setTimeout(() => { el.className = 'hidden'; resolve(); }, 700);
  });
}

/* ── PARTICLE SYSTEM ───────────────────────────────────────────────── */
function spawnParticles(type) {
  const canvas = document.getElementById('particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const colors = type === 'correct' ? ['#00c875','#80ffc8','#00e676','#c8a000','#ffd700'] :
                 type === 'medal'   ? ['#ffd700','#c8a000','#ffe082','#fff9c4'] :
                 type === 'finish'  ? ['#1565c0','#c8a000','#00c875','#3b82f6','#ffd700'] :
                 type === 'golden'  ? ['#ffd700','#c8a000','#fff176','#ffe082'] :
                 ['#1565c0','#3b82f6','#7ab0e0'];

  const particles = [];
  for (let i = 0; i < 50; i++) {
    particles.push({
      x: canvas.width / 2 + (Math.random() - .5) * 200,
      y: canvas.height / 2 + (Math.random() - .5) * 200,
      vx: (Math.random() - .5) * 9,
      vy: (Math.random() - .5) * 9 - 3,
      size: Math.random() * 7 + 2,
      color: colors[Math.floor(Math.random() * colors.length)],
      life: 1,
      decay: Math.random() * .014 + .009,
      shape: Math.random() > .5 ? 'circle' : 'rect'
    });
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;
    particles.forEach(p => {
      if (p.life <= 0) return;
      alive = true;
      p.x += p.vx; p.y += p.vy; p.vy += .15;
      p.life -= p.decay;
      ctx.globalAlpha = p.life;
      ctx.fillStyle = p.color;
      if (p.shape === 'rect') {
        ctx.fillRect(p.x - p.size/2, p.y - p.size/2, p.size, p.size * 1.6);
      } else {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    ctx.globalAlpha = 1;
    if (alive) requestAnimationFrame(animate);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  animate();
}

/* ── CONFETTI (resposta correta) ───────────────────────────────────── */
function spawnConfetti() {
  const canvas = document.getElementById('particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const palette = ['#1565c0','#3b82f6','#c8a000','#ffd700','#00c875','#ffffff','#800020'];
  const pieces = [];
  for (let i = 0; i < 90; i++) {
    pieces.push({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * 100,
      vx: (Math.random() - .5) * 4,
      vy: Math.random() * 4 + 2,
      w: Math.random() * 10 + 5,
      h: Math.random() * 6 + 3,
      rot: Math.random() * Math.PI * 2,
      rotV: (Math.random() - .5) * .2,
      color: palette[Math.floor(Math.random() * palette.length)],
      life: 1,
      decay: Math.random() * .008 + .005
    });
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;
    pieces.forEach(p => {
      if (p.life <= 0) return;
      alive = true;
      p.x += p.vx; p.y += p.vy; p.rot += p.rotV;
      p.life -= p.decay;
      ctx.save();
      ctx.globalAlpha = p.life;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
      ctx.restore();
    });
    ctx.globalAlpha = 1;
    if (alive) requestAnimationFrame(draw);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  draw();
}

/* ── SCORE EXPLOSION ───────────────────────────────────────────────── */
function showScoreExplosion(pts) {
  const el = document.createElement('div');
  el.className = 'score-burst';
  el.textContent = '+' + pts + ' pts!';
  el.style.left = (30 + Math.random() * 40) + '%';
  el.style.top = (30 + Math.random() * 20) + '%';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1300);
}

/* ── ANIMATED BACKGROUND ───────────────────────────────────────────── */
function initAnimatedBG() {
  const container = document.getElementById('bg-symbols');
  if (!container) return;
  const symbols = ['⚖️','📜','🏛️','📚','🔨','⭐','🗽','📖','🎓','⚖️','🏆','🛡️'];
  for (let i = 0; i < 15; i++) {
    const sym = document.createElement('div');
    sym.className = 'bg-sym';
    sym.textContent = symbols[Math.floor(Math.random() * symbols.length)];
    sym.style.left = Math.random() * 100 + '%';
    sym.style.animationDuration = (15 + Math.random() * 25) + 's';
    sym.style.animationDelay = Math.random() * 20 + 's';
    sym.style.fontSize = (1 + Math.random() * 2) + 'rem';
    container.appendChild(sym);
  }
}

/* ── STAR BACKGROUND ───────────────────────────────────────────────── */
function initStarBG() {
  const canvas = document.getElementById('star-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; drawStars(); }
  function drawStars() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const count = Math.floor((canvas.width * canvas.height) / 6000);
    for (let i = 0; i < count; i++) {
      const x = Math.random() * canvas.width;
      const y = Math.random() * canvas.height;
      const r = Math.random() * 1.4 + 0.2;
      const alpha = Math.random() * 0.6 + 0.15;
      // Occasional gold star
      const isGold = Math.random() < 0.08;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = isGold ? `rgba(200,160,0,${alpha})` : `rgba(180,210,255,${alpha})`;
      ctx.fill();
    }
  }
  resize();
  window.addEventListener('resize', resize);
  // Gentle twinkle
  let tick = 0;
  function twinkle() {
    tick++;
    if (tick % 90 === 0) drawStars();
    requestAnimationFrame(twinkle);
  }
  twinkle();
}

/* ── EPIC INTRO ────────────────────────────────────────────────────── */
let introShown = false;

function showEpicIntro() {
  if (introShown) return Promise.resolve();
  introShown = true;
  const el = document.getElementById('epic-intro-overlay');
  if (!el) return Promise.resolve();
  return new Promise(resolve => {
    el.className = 'epic-intro';
    el.innerHTML =
      '<div class="ei-icon">⚖️</div>' +
      '<div class="ei-title">Voce esta prestes a entrar na Arena Constitucional</div>' +
      '<div class="ei-sub">Defenda a Constituicao. Prove seu conhecimento juridico. Torne-se o Guardiao.</div>' +
      '<button class="btn primary ei-btn" id="btn-enter-arena">Entrar na Arena ⚔️</button>';
    document.getElementById('btn-enter-arena').addEventListener('click', () => {
      el.style.animation = 'fadeIn .3s ease reverse forwards';
      playSound('levelup');
      vibrate([100, 50, 100]);
      setTimeout(() => { el.className = 'hidden'; resolve(); }, 400);
    });
  });
}

/* ── VIBRATION (mobile haptic) ─────────────────────────────────────── */
function vibrate(pattern) {
  try { if (navigator.vibrate) navigator.vibrate(pattern); } catch(e) {}
}

/* ── COINS SYSTEM ──────────────────────────────────────────────────── */
function getCoins() { return profile.coins || 0; }

function addCoins(amount, source) {
  if (!profile.coins) profile.coins = 0;
  profile.coins += amount;
  saveProfile();
  refreshCoinsDisplay();
  showCoinGain(amount, source);
}

function refreshCoinsDisplay() {
  const el = document.getElementById('coins-amount');
  if (el) el.textContent = getCoins();
}

function showCoinGain(amount, source) {
  const el = document.createElement('div');
  el.className = 'coin-gain';
  el.textContent = '+' + amount + ' 🪙';
  el.style.left = (Math.random() * 60 + 20) + '%';
  el.style.top = '40%';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1500);
}

/* ── SKILL TREE ────────────────────────────────────────────────────── */
const SKILLS = [
  {id:'fast', name:'Jurista Rapido', icon:'⚡', desc:'+10s extra em cada pergunta', cost:100, effect:'extraTime'},
  {id:'memory', name:'Memoria Fotografica', icon:'🧠', desc:'Elimina 1 alternativa automaticamente', cost:150, effect:'autoElim'},
  {id:'intuition', name:'Intuicao Juridica', icon:'💡', desc:'Dica automatica no inicio', cost:200, effect:'autoHint'},
  {id:'shield', name:'Escudo Constitucional', icon:'🛡️', desc:'+1 vida extra por partida', cost:250, effect:'extraLife'},
  {id:'double', name:'Dobro ou Nada', icon:'💰', desc:'Moedas em dobro por partida', cost:300, effect:'doubleCoins'},
  {id:'scholar', name:'Erudito', icon:'📚', desc:'+25% XP por partida', cost:350, effect:'bonusXP'},
];

function getEquippedSkill() { return profile.equippedSkill || null; }
function getPurchasedSkills() { return profile.purchasedSkills || []; }

function renderSkillTree() {
  const el = document.getElementById('skill-grid');
  if (!el) return;
  const purchased = getPurchasedSkills();
  const equipped = getEquippedSkill();
  const coins = getCoins();

  el.innerHTML = SKILLS.map(s => {
    const owned = purchased.includes(s.id);
    const isEquipped = equipped === s.id;
    const canBuy = coins >= s.cost;
    return '<div class="skill-card' + (isEquipped ? ' equipped' : '') + '" onclick="handleSkill(\'' + s.id + '\')">' +
      '<div class="sk-icon">' + s.icon + '</div>' +
      '<h4>' + s.name + '</h4>' +
      '<p>' + s.desc + '</p>' +
      '<div class="sk-cost">' + (owned ? (isEquipped ? '✅ Equipada' : '📌 Equipar') : (canBuy ? '🪙 ' + s.cost : '🔒 ' + s.cost + ' moedas')) + '</div>' +
      '</div>';
  }).join('');
}

function handleSkill(id) {
  const skill = SKILLS.find(s => s.id === id);
  if (!skill) return;
  const purchased = getPurchasedSkills();

  if (purchased.includes(id)) {
    // Toggle equip
    profile.equippedSkill = (profile.equippedSkill === id) ? null : id;
    saveProfile();
    renderSkillTree();
    return;
  }

  // Purchase
  if (getCoins() < skill.cost) {
    alert('Moedas insuficientes! Voce precisa de ' + skill.cost + ' moedas.');
    return;
  }
  if (!confirm('Comprar ' + skill.name + ' por ' + skill.cost + ' moedas?')) return;
  profile.coins -= skill.cost;
  if (!profile.purchasedSkills) profile.purchasedSkills = [];
  profile.purchasedSkills.push(id);
  profile.equippedSkill = id;
  saveProfile();
  refreshCoinsDisplay();
  renderSkillTree();
  playSound('medal');
}

function applySkillEffects() {
  const skill = SKILLS.find(s => s.id === getEquippedSkill());
  if (!skill) return;
  switch (skill.effect) {
    case 'extraLife':
      lives = 4;
      const bar = document.getElementById('lives-bar');
      if (bar && livesEnabled) {
        let h4 = document.getElementById('heart-4');
        if (!h4) {
          h4 = document.createElement('span');
          h4.className = 'heart'; h4.id = 'heart-4'; h4.textContent = '💜';
          bar.appendChild(h4);
        } else { h4.className = 'heart'; }
      }
      break;
    case 'autoHint':
      // Will trigger after question renders
      break;
    case 'autoElim':
      // Will trigger after options reveal
      break;
  }
}

/* ── CONSTITUTION MAP ──────────────────────────────────────────────── */
const CONST_TOPICS = [
  {id:'teoria', name:'Teoria Constitucional', icon:'📜', levels:[1]},
  {id:'individuais', name:'Direitos Individuais', icon:'🛡️', levels:[2]},
  {id:'remedios', name:'Remedios Constitucionais', icon:'⚖️', levels:[3]},
  {id:'sociais', name:'Direitos Sociais', icon:'🤝', levels:[4]},
  {id:'praticos', name:'Casos Praticos', icon:'🏛️', levels:[5]},
];

function renderConstitutionMap() {
  const el = document.getElementById('const-map');
  if (!el) return;
  const history = profile.history || [];

  el.innerHTML = CONST_TOPICS.map(topic => {
    // Calculate mastery based on performance in relevant levels
    const topicStats = computeTopicStats(topic.levels);
    const pct = topicStats.total > 0 ? Math.round(topicStats.correct / topicStats.total * 100) : 0;
    const status = pct >= 80 ? 'Dominado' : pct >= 50 ? 'Em progresso' : pct > 0 ? 'Iniciado' : 'Inexplorado';

    return '<div class="map-item">' +
      '<div class="mi-icon">' + topic.icon + '</div>' +
      '<div class="mi-name">' + topic.name + '</div>' +
      '<div class="mi-bar"><div class="mi-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="mi-pct">' + pct + '% — ' + status + '</div>' +
      '</div>';
  }).join('');
}

function computeTopicStats(levels) {
  if (!profile.topicStats) return {correct: 0, total: 0};
  let c = 0, t = 0;
  levels.forEach(lv => {
    const s = profile.topicStats[lv];
    if (s) { c += s.correct; t += s.total; }
  });
  return {correct: c, total: t};
}

function updateTopicStats(level, correct) {
  if (!profile.topicStats) profile.topicStats = {};
  if (!profile.topicStats[level]) profile.topicStats[level] = {correct: 0, total: 0};
  profile.topicStats[level].total++;
  if (correct) profile.topicStats[level].correct++;
  saveProfile();
}

/* ── NARRATOR COMMENTS ─────────────────────────────────────────────── */
const NARRATOR_COMMENTS = {
  correct_easy: [
    '📖 O STF consolidou esse entendimento em diversas decisoes.',
    '⚖️ Essa e uma questao basilar do direito constitucional brasileiro.',
    '🏛️ Importante fundamento para qualquer operador do direito.',
  ],
  correct_hard: [
    '🎓 Poucos dominam esse tema com tanta clareza. Parabens!',
    '⚖️ Esse e um tema complexo que exige profundo conhecimento constitucional.',
    '⚖️ O proprio STF ja debateu longamente essa questao.',
  ],
  wrong: [
    '📚 Revise esse tema. E fundamental para o direito constitucional.',
    '💡 Esse artigo e frequentemente cobrado em concursos e provas.',
    '🔍 Aprofunde-se nessa materia. A Constituicao tem nuances importantes.',
  ],
};

function getNarratorComment(correct, difficulty) {
  let pool;
  if (correct) {
    pool = (difficulty === 'hard' || difficulty === 'boss') ? NARRATOR_COMMENTS.correct_hard : NARRATOR_COMMENTS.correct_easy;
  } else {
    pool = NARRATOR_COMMENTS.wrong;
  }
  return pool[Math.floor(Math.random() * pool.length)];
}

/* ── ENHANCED SCORING ──────────────────────────────────────────────── */
function calcTimeBonus(answerTimeMs, totalTimeMs) {
  if (answerTimeMs <= 0 || totalTimeMs <= 0) return 0;
  const ratio = 1 - (answerTimeMs / (totalTimeMs * 1000));
  if (ratio <= 0) return 0;
  return Math.round(ratio * 20);
}

function getDifficultyMultiplier(q) {
  if (q.boss) return 2.5;
  if (q.golden) return 3;
  if (q.diff === 'hard') return 1.5;
  if (q.diff === 'easy') return 0.8;
  return 1;
}

/* ── STREAK MILESTONES ─────────────────────────────────────────────── */
const STREAK_MILESTONES = [
  {days:3, reward:'medal', desc:'🏅 Medalha de Consistencia!', coins:20},
  {days:5, reward:'avatar', desc:'🎭 Avatar especial desbloqueado!', coins:50},
  {days:7, reward:'theme', desc:'🎨 Tema exclusivo desbloqueado!', coins:100},
  {days:14, reward:'title', desc:'👑 Titulo "Constitucionalista Dedicado"!', coins:200},
  {days:30, reward:'legendary', desc:'💎 Status Lendario alcancado!', coins:500},
];

function checkStreakMilestones() {
  const days = profile.dailyStreak;
  STREAK_MILESTONES.forEach(m => {
    if (days === m.days) {
      addCoins(m.coins, 'streak');
      showMedalToast({name: m.desc, desc: 'Sequencia de ' + m.days + ' dias!'}, 0);
    }
  });
}

/* ── FILL-IN-BLANK HANDLER ─────────────────────────────────────────── */
function renderFillBlank(q) {
  ui.options.innerHTML = '<input class="fill-blank-input" id="fill-input" type="text" placeholder="Digite sua resposta..." autocomplete="off" autocapitalize="none">' +
    '<button class="btn primary" id="fill-submit" style="margin-top:8px;width:100%">✓ Confirmar resposta</button>';
  document.getElementById('fill-submit').addEventListener('click', () => {
    const input = document.getElementById('fill-input');
    if (!input) return;
    const answer = input.value.trim().toLowerCase();
    const correct = q.answer.toLowerCase();
    const isCorrect = answer === correct || answer.includes(correct) || correct.includes(answer);
    doFillAnswer(isCorrect, q);
  });
  document.getElementById('fill-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('fill-submit').click();
  });
  document.getElementById('fill-input').focus();
}

function doFillAnswer(isCorrect, q) {
  if (state.answered) return;
  state.answered = true;
  clearInterval(state.ticker);

  const lv = lvMeta(q.level);
  state.lvStats[q.level].total++;

  const input = document.getElementById('fill-input');
  const btn = document.getElementById('fill-submit');
  if (input) { input.disabled = true; input.style.borderColor = isCorrect ? '#00c875' : '#800020'; }
  if (btn) btn.disabled = true;

  let fbTitle, fbBody;

  if (isCorrect) {
    state.lvStats[q.level].ok++;
    state.streak++;
    state.lvStats[q.level].bestStreak = Math.max(state.lvStats[q.level].bestStreak, state.streak);
    let gain = lv.base + (state.streak >= 2 ? STREAK_BONUS : 0);
    gain = Math.round(gain * getDifficultyMultiplier(q));
    if (furyActive) gain *= 2;
    state.score += gain;
    fbTitle = CORRECT_REACTIONS[Math.floor(Math.random() * CORRECT_REACTIONS.length)];
    fbBody = q.exp + ' — +' + gain + ' pts.';
    showCombo(state.streak);
    playSound(state.streak >= 3 ? 'combo' : 'correct');
    spawnParticles('correct');
    vibrate([50]);
    updateTopicStats(q.level, true);
    addCoins(Math.round(gain / 5), 'answer');
    if (state.streak >= 10 && !furyActive) activateFury();
  } else {
    state.streak = 0;
    state.wrongQs.push(q);
    if (furyActive) deactivateFury();
    fbTitle = WRONG_REACTIONS[Math.floor(Math.random() * WRONG_REACTIONS.length)];
    fbBody = q.exp + ' — Resposta correta: ' + q.answer;
    playSound('wrong');
    vibrate([100, 50, 100]);
    updateTopicStats(q.level, false);
    if (livesEnabled) loseLife();
  }

  setPhase(isCorrect ? 'done-ok' : 'done-no', 0);
  ui.feedbackBox.className = 'feedback' + (isCorrect ? ' ok' : '');
  ui.fbTitle.textContent = fbTitle;
  ui.fbBody.textContent = fbBody;
  ui.fbRef.textContent = '📜 ' + q.ref + '. ' + q.note;
  ui.feedbackBox.classList.remove('hidden');
  ui.btnNext.disabled = false;

  // Narrator
  const narr = getNarratorComment(isCorrect, q.diff || 'normal');
  const narrDiv = document.createElement('div');
  narrDiv.className = 'narrator-box';
  narrDiv.innerHTML = '<span class="nr-icon">🎙️</span>' + narr;
  ui.feedbackBox.appendChild(narrDiv);

  refreshMedals();
  updateHud();
}

/* ── ENHANCED STATS (post-game) ────────────────────────────────────── */
function getWeakestTopics() {
  if (!profile.topicStats) return [];
  return CONST_TOPICS.filter(t => {
    const s = computeTopicStats(t.levels);
    return s.total > 0 && (s.correct / s.total) < 0.6;
  }).map(t => t.name);
}

function getStrongestTopics() {
  if (!profile.topicStats) return [];
  return CONST_TOPICS.filter(t => {
    const s = computeTopicStats(t.levels);
    return s.total >= 3 && (s.correct / s.total) >= 0.8;
  }).map(t => t.name);
}
/* ── INIT ─────────────────────────────────────────────────────────── */
renderLevelCards();
setupPWA();
loadRanking();
startPoll();
refreshProfileBar();
applyTheme(profile.theme || 'dark');
initModeCards();
renderLibrary();
renderEvolution();
renderSkillTree();
renderConstitutionMap();
refreshCoinsDisplay();
initAnimatedBG();
initStarBG();
document.getElementById('btn-sound').textContent = profile.soundEnabled ? '🔊' : '🔇';

/* ── AUTH INIT (must be last — needs ui, state, profile all ready) ── */
(function initAuth() {
  renderAuthAvatars();
  ['login-user','login-pass'].forEach(id => {
    document.getElementById(id)?.addEventListener('keydown', e => { if (e.key==='Enter') doLogin(); });
  });
  ['reg-user','reg-pass','reg-pass2'].forEach(id => {
    document.getElementById(id)?.addEventListener('keydown', e => { if (e.key==='Enter') doRegister(); });
  });
  const sess = loadSession();
  if (sess && sess.username) {
    enterGame(sess);
  }
})();

/* ══════════════════════════════════════════════════════════════════════
   INVESTIGATION GAME — COMPLETE MULTIPLAYER SYSTEM
   ══════════════════════════════════════════════════════════════════════ */

const INV = {
  playerId: null,
  roomId: null,
  phase: null,
  pollTimer: null,
  lastState: null,
  waitingSince: null,
  botsEnabled: true,
  pendingVote: { violacao: null, artigo: null, culpado: null },
  roleColors: {
    icaro:'#3b82f6', natan:'#ef4444', luciano:'#f59e0b',
    giovanna:'#8b5cf6', thalles:'#10b981', izabella:'#ec4899', dilerman:'#f97316'
  },
  phaseName: {
    lobby:'Aguardando', intro:'Intro do Caso', investigacao:'Investigação',
    debate:'Debate', votacao:'Votação', resultado:'Resultado'
  },
};

function invGetPlayerId() {
  if (INV.playerId) return INV.playerId;
  let id = localStorage.getItem('inv_player_id');
  if (!id) { id = 'P' + Math.random().toString(36).substr(2,10).toUpperCase(); localStorage.setItem('inv_player_id', id); }
  INV.playerId = id;
  return id;
}

function invGetPlayerName() {
  const nameEl = document.getElementById('inv-player-name');
  const name = nameEl?.value.trim() || (currentUser?.username) || 'Jogador';
  return name || 'Jogador';
}

function openInvestigacao() {
  invGetPlayerId();
  document.getElementById('inv-overlay').classList.remove('hidden');
  invShowScreen('lobby');
  invRefreshRooms();
}

function closeInvestigacao() {
  document.getElementById('inv-overlay').classList.add('hidden');
  if (INV.pollTimer) { clearInterval(INV.pollTimer); INV.pollTimer = null; }
  INV.roomId = null; INV.phase = null;
}

function invShowScreen(name) {
  const current = document.querySelector('#inv-overlay .inv-screen:not(.hidden)');
  const doSwitch = () => {
    ['lobby','waiting','intro','investigacao','votacao','resultado'].forEach(s => {
      const el = document.getElementById('inv-screen-' + s);
      if (el) el.classList.toggle('hidden', s !== name);
    });
  };
  if (current && !current.classList.contains('hidden')) {
    current.style.transition = 'opacity .2s ease';
    current.style.opacity = '0';
    setTimeout(() => { doSwitch(); if(current) { current.style.opacity=''; current.style.transition=''; } }, 200);
  } else {
    doSwitch();
  }
}

async function invRefreshRooms() {
  const list = document.getElementById('inv-rooms-list');
  if (!list) return;
  try {
    const r = await fetch('/api/inv/rooms');
    const rooms = await r.json();
    if (!rooms.length) { list.innerHTML = "<div class='inv-empty'>Nenhuma sala aberta. Seja o primeiro!</div>"; return; }
    list.innerHTML = rooms.map(rm => `
      <div class='inv-room-item'>
        <div><div style='font-weight:800;color:#fff;font-size:.9rem'>📁 ${rm.case}</div>
        <div style='font-size:.75rem;color:#6b7280;margin-top:2px'>👥 ${rm.players} jogador(es) • ID: ${rm.id}</div></div>
        <button class='inv-room-join-btn' onclick='invJoinRoomId("${rm.id}")'>Entrar</button>
      </div>`).join('');
  } catch(e) { list.innerHTML = "<div class='inv-empty'>Erro ao carregar salas.</div>"; }
}

async function invCreateRoom() {
  const name = invGetPlayerName();
  if (!name || name.length < 2) { alert('Digite seu nome!'); return; }
  try {
    const r = await fetch('/api/inv/join', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ player_id: invGetPlayerId(), player_name: name }) });
    const data = await r.json();
    if (data.room_id) { INV.roomId = data.room_id; invEnterWaiting(); }
  } catch(e) { alert('Erro ao criar sala.'); }
}

async function invJoinRoom() {
  const code = document.getElementById('inv-room-code')?.value.trim().toUpperCase();
  if (!code) { alert('Digite o código da sala!'); return; }
  await invJoinRoomId(code);
}

async function invJoinRoomId(roomId) {
  const name = invGetPlayerName() || ('Jogador_' + Math.floor(Math.random()*999));
  try {
    const r = await fetch('/api/inv/join', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ player_id: invGetPlayerId(), player_name: name, room_id: roomId }) });
    const data = await r.json();
    if (data.room_id) { INV.roomId = data.room_id; invEnterWaiting(); }
    else alert('Sala não encontrada ou cheia.');
  } catch(e) { alert('Erro ao entrar na sala.'); }
}

function invEnterWaiting() {
  invShowScreen('waiting');
  document.getElementById('inv-my-room-code').textContent = INV.roomId;
  INV.waitingSince = Date.now();
  if (INV.pollTimer) clearInterval(INV.pollTimer);
  INV.pollTimer = setInterval(invPoll, 2000);
  invPoll();
}

async function invPoll() {
  if (!INV.roomId) return;
  try {
    const r = await fetch(`/api/inv/state?room_id=${INV.roomId}&player_id=${invGetPlayerId()}`);
    if (!r.ok) return;
    const state = await r.json();
    INV.lastState = state;
    invRenderState(state);
  } catch(e) {}
}

function invRenderState(state) {
  const phase = state.phase;
  // Update header
  const phaseEl = document.getElementById('inv-phase-indicator');
  if (phaseEl) phaseEl.textContent = INV.phaseName[phase] || phase;
  const timerEl = document.getElementById('inv-global-timer');
  if (timerEl && state.time_left != null) {
    timerEl.textContent = invFmtTime(state.time_left);
    timerEl.style.color = state.time_left < 15 ? '#ef4444' : '#a78bfa';
  } else if (timerEl) timerEl.textContent = '';

  // Phase transitions
  if (phase !== INV.phase) {
    INV.phase = phase;
    const phaseMessages = {
      intro: '📋 Caso revelado! Leia os detalhes.',
      investigacao: '🔍 Investigação iniciada! Use suas habilidades.',
      debate: '💬 Fase de debate! Convença os outros.',
      votacao: '⚖️ Hora de votar! Decida com sabedoria.',
      resultado: '🏛️ Veredicto final!'
    };
    if (phaseMessages[phase]) invToast(phaseMessages[phase]);
    if (phase === 'intro') invShowScreen('intro');
    else if (phase === 'investigacao') { invShowScreen('investigacao'); invRenderMyRole(state); }
    else if (phase === 'debate') { invShowScreen('investigacao'); invTab('chat'); }
    else if (phase === 'votacao') { invShowScreen('votacao'); invSetupVoteOptions(state); }
    else if (phase === 'resultado') invShowScreen('resultado');
  }

  // Per-phase rendering
  if (phase === 'lobby' || phase === 'waiting' || INV.phase === null) invRenderWaiting(state);
  if (phase === 'intro') invRenderIntro(state);
  if (phase === 'investigacao' || phase === 'debate') invRenderInvestigation(state);
  if (phase === 'votacao') invRenderVotacao(state);
  if (phase === 'resultado') invRenderResultado(state);
}

function invRenderWaiting(state) {
  const cnt = document.getElementById('inv-waiting-count');
  if (cnt) cnt.textContent = state.players.length;
  const caseEl = document.getElementById('inv-waiting-case');
  if (caseEl) caseEl.textContent = state.case?.title || '';
  const playersEl = document.getElementById('inv-waiting-players');
  if (playersEl) playersEl.innerHTML = state.players.map(p => {
    const isMe = p.id === invGetPlayerId();
    const col = p.is_bot ? '#f59e0b' : (isMe ? '#60a5fa' : '#fff');
    return `<div class='inv-waiting-player${p.ready?" ready":""}' style='display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);margin-bottom:6px;animation:fadeUp .3s ease both;transition:border-color .3s' ${p.ready?'style="border-color:rgba(52,211,153,.3)"':''}>
      <span style='font-size:1.4rem'>${p.is_bot?'🤖':'⚖️'}</span>
      <span style='flex:1;font-weight:700;color:${col}'>${p.name}${isMe?' <small style="color:#60a5fa;font-weight:400">(você)</small>':''}${p.is_bot?' <small style="color:#6b7280">[bot]</small>':''}</span>
      <span style='font-size:.78rem;font-weight:800;color:${p.ready?"#34d399":"#6b7280"}'>${p.ready?'✅ Pronto':'⏳ Aguardando'}</span>
    </div>`;
  }).join('');

  // Bot toggle row: only for room creator (first player)
  const toggleRow = document.getElementById('inv-bot-toggle-row');
  const toggleBtn = document.getElementById('inv-bot-toggle-btn');
  const isCreator = state.players.length > 0 && state.players[0].id === invGetPlayerId();
  if (toggleRow) {
    toggleRow.style.display = isCreator ? 'block' : 'none';
    if (toggleBtn) {
      const botsOn = state.bots_enabled !== false;
      INV.botsEnabled = botsOn;
      toggleBtn.textContent = botsOn ? 'ON' : 'OFF';
      toggleBtn.style.background = botsOn ? 'rgba(139,92,246,.2)' : 'rgba(255,255,255,.05)';
      toggleBtn.style.color = botsOn ? '#a78bfa' : '#6b7280';
    }
  }

  // Bot countdown
  const botDiv = document.getElementById('inv-bot-countdown');
  const botSecs = document.getElementById('inv-bot-secs');
  if (botDiv && INV.waitingSince) {
    const elapsed = Math.floor((Date.now() - INV.waitingSince) / 1000);
    const humanCount = state.players.filter(p => !p.is_bot).length;
    const botsEnabled = state.bots_enabled !== false;
    const secsLeft = Math.max(0, 60 - elapsed);
    const hasBots = state.players.some(p => p.is_bot);
    if (botsEnabled && !hasBots && humanCount < 5 && elapsed >= 10) {
      botDiv.style.display = 'block';
      if (botSecs) botSecs.textContent = secsLeft;
    } else {
      // Bots já entraram ou não habilitado — esconde o countdown
      botDiv.style.display = 'none';
    }
  }
}

function invRenderIntro(state) {
  const t = document.getElementById('inv-intro-title');
  const h = document.getElementById('inv-intro-historia');
  const e = document.getElementById('inv-intro-envolvidos');
  if (t) t.textContent = state.case.title;
  if (h) h.textContent = state.case.historia;
  if (e) e.innerHTML = (state.case.envolvidos||[]).map(ev => `<span class='inv-envolvido-chip'>${ev}</span>`).join('');
  const cd = document.getElementById('inv-intro-countdown');
  if (cd && state.time_left != null) {
    cd.textContent = Math.ceil(state.time_left);
    cd.classList.toggle('urgent', state.time_left < 10);
  }
  // Show role if available
  const roleReveal = document.getElementById('inv-role-reveal');
  if (roleReveal && state.my_role) {
    roleReveal.classList.remove('hidden');
    const col = INV.roleColors[state.my_role.id] || '#8b5cf6';
    roleReveal.style.background = `linear-gradient(135deg,${col}22,${col}08)`;
    roleReveal.style.border = `1px solid ${col}40`;
    roleReveal.innerHTML = `
      <div style='font-size:2.5rem;margin-bottom:8px'>${state.my_role.icon}</div>
      <div style='font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:${col};margin-bottom:6px'>Seu Papel</div>
      <div style='font-size:1.2rem;font-weight:900;color:#fff;margin-bottom:4px'>${state.my_role.nome}</div>
      <div style='font-size:.82rem;color:#9ca3af;margin-bottom:12px'>${state.my_role.titulo}</div>
      <div style='font-size:.83rem;color:#c8c8d8;line-height:1.6;text-align:left;padding:10px;background:rgba(255,255,255,.03);border-radius:10px;border:1px solid rgba(255,255,255,.08)'>${state.my_role.desc}</div>`;
  }
}

function invRenderMyRole(state) {
  const el = document.getElementById('inv-my-role-card');
  if (!el || !state.my_role) return;
  const r = state.my_role;
  const col = INV.roleColors[r.id] || '#8b5cf6';
  el.style.background = `linear-gradient(135deg,${col}18,${col}06)`;
  el.style.borderColor = `${col}40`;
  // Find my player
  const me = state.players.find(p => p.id === invGetPlayerId());
  const used = me?.actions_used || [];
  const habs = Object.entries(r.habilidades || {});
  el.innerHTML = `
    <div style='font-size:2rem'>${r.icon}</div>
    <div style='flex:1'>
      <div class='inv-role-name'>${r.nome}</div>
      <div class='inv-role-title' style='color:${col}'>${r.titulo}</div>
      <div style='margin-top:10px;display:grid;gap:5px'>
        ${habs.map(([key, hab]) => {
          const isUsed = used.includes(key);
          const isUltimate = hab.uses === 1;
          return `<button class='inv-skill-btn' onclick='invUseSkill("${key}")' ${isUsed && isUltimate?'disabled':''}>
            ${isUltimate?'⚡ ':''}${hab.nome} ${isUltimate?'<span class=\'inv-skill-cd\'>(único)</span>':''}
            ${isUsed && isUltimate?'<span class=\'inv-skill-cd\'>✓ Usado</span>':''}
          </button>`;
        }).join('')}
      </div>
    </div>`;
}

function invRenderInvestigation(state) {
  // Case
  const ct = document.getElementById('inv-case-title-small');
  const ch = document.getElementById('inv-case-historia-small');
  if (ct) ct.textContent = state.case.title;
  if (ch) ch.textContent = state.case.historia;
  const duvEl = document.getElementById('inv-case-duvidas');
  if (duvEl) duvEl.innerHTML = '<div style="font-size:.8rem;color:#9ca3af;font-weight:700;margin-bottom:6px">💭 PONTOS DE DEBATE</div>' + (state.case.duvidas||[]).map(d => `<div class='inv-duvida-item'>❓ ${d}</div>`).join('');

  // Evidences
  const evList = document.getElementById('inv-evidence-list');
  if (evList) {
    const me = state.players.find(p => p.id === invGetPlayerId());
    const myRole = state.my_role?.id;
    evList.innerHTML = (state.evidences||[]).map(ev => {
      const pct = Math.round(ev.peso * 100);
      const col = pct > 60 ? '#ef4444' : pct > 30 ? '#f59e0b' : '#6b7280';
      let btns = '';
      if (myRole==='icaro') btns += `<button class='inv-ev-btn prim' onclick='invUseSkillOn("contestacao","${ev.id}")'>⚖️ Contestar</button>`;
      if (myRole==='natan') btns += `<button class='inv-ev-btn danger' onclick='invUseSkillOn("marcar","${ev.id}")'>🔥 Marcar Crítica</button>`;
      if (myRole==='icaro' && !me?.actions_used?.includes('duvida')) btns += `<button class='inv-ev-btn' onclick='invUseSkillOn("duvida","${ev.id}")'>❓ Dúvida Razoável</button>`;
      return `<div class='inv-evidence-item${ev.contested?' contested':''}${ev.critical?' critical':''}'>
        <div class='inv-ev-header'>
          <span class='inv-ev-title'>${ev.titulo}</span>
          <span class='inv-ev-peso' style='background:${col}22;border:1px solid ${col}44;color:${col}'>${pct}% peso</span>
        </div>
        <div class='inv-ev-desc'>${ev.descricao}</div>
        ${btns?`<div class='inv-ev-actions'>${btns}</div>`:''}
      </div>`;
    }).join('') || '<div class="inv-empty">Carregando evidências...</div>';
  }

  // Players
  const plList = document.getElementById('inv-players-list');
  if (plList) plList.innerHTML = state.players.map(p => {
    const col = INV.roleColors[p.role_id] || '#8b5cf6';
    return `<div class='inv-player-row'>
      <span>${p.role_icon||'👤'}</span>
      <span style='font-size:.88rem;color:#fff;font-weight:700'>${p.name}${p.id===invGetPlayerId()?' (você)':''}</span>
      ${p.role_name?`<span class='inv-player-row-role' style='background:${col}22;border:1px solid ${col}44;color:${col}'>${p.role_name}</span>`:''}
    </div>`;
  }).join('');

  // Actions log
  const logEl = document.getElementById('inv-actions-log');
  if (logEl) logEl.innerHTML = (state.actions_log||[]).slice(-8).reverse().map(a =>
    `<div class='inv-log-item'>${a.msg}</div>`).join('') || '<div class="inv-log-item" style="color:#4b5563">Sem ações ainda...</div>';

  // Timer
  const tmEl = document.getElementById('inv-inv-timer');
  if (tmEl && state.time_left!=null) {
    tmEl.innerHTML = `<div style='font-size:.72rem;color:#6b7280;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em'>${INV.phaseName[state.phase]||''}</div><div style='font-size:1.8rem;font-weight:900;color:${state.time_left<20?"#ef4444":"#a78bfa"}'>${invFmtTime(state.time_left)}</div>`;
  }

  // Chat
  const chatEl = document.getElementById('inv-chat-messages');
  if (chatEl) {
    const msgs = state.messages || [];
    chatEl.innerHTML = msgs.map(m => {
      const col = INV.roleColors[m.role] || '#8b5cf6';
      return `<div class='inv-chat-msg'>
        <div class='inv-chat-sender' style='color:${col}'>${m.player}</div>
        <div class='inv-chat-text'>${m.text}</div>
      </div>`;
    }).join('');
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  // Tendency (Giovanna)
  if (state.tendency) {
    const logEl2 = document.getElementById('inv-actions-log');
    if (logEl2) {
      const tendDiv = `<div class='inv-log-item' style='color:#8b5cf6;border-bottom:1px solid rgba(139,92,246,.2)'>👁️ Tendência: SIM ${state.tendency.sim} | NÃO ${state.tendency.nao}</div>`;
      logEl2.innerHTML = tendDiv + logEl2.innerHTML;
    }
  }
}

function invSetupVoteOptions(state) {
  const culpadoEl = document.getElementById('inv-culpado-options');
  if (culpadoEl) {
    const envolvidos = state.case.envolvidos || [];
    culpadoEl.innerHTML = envolvidos.map(ev =>
      `<button class='inv-vote-btn' onclick='invSetVote("culpado","${ev.replace(/['"]/g,'')}")'>${ev}</button>`
    ).join('');
  }
  INV.pendingVote = { violacao: null, artigo: null, culpado: null };
}

function invRenderVotacao(state) {
  const cd = document.getElementById('inv-vote-countdown');
  if (cd && state.time_left != null) {
    cd.textContent = Math.ceil(state.time_left);
    cd.classList.toggle('urgent', state.time_left < 15);
  }
  const waitingVotes = state.players.filter(p => !p.has_voted).length;
  const summaryEl = document.getElementById('inv-vote-summary');
  if (summaryEl) {
    if (INV.pendingVote.violacao !== null || INV.pendingVote.artigo || INV.pendingVote.culpado) {
      summaryEl.style.display = 'block';
      summaryEl.innerHTML = `<strong>Seu voto:</strong><br>
        ${INV.pendingVote.violacao !== null ? `✅ Violação: ${INV.pendingVote.violacao?'SIM':'NÃO'}<br>` : ''}
        ${INV.pendingVote.artigo ? `📜 ${INV.pendingVote.artigo}<br>` : ''}
        ${INV.pendingVote.culpado ? `🎯 ${INV.pendingVote.culpado}` : ''}
        <br><small style='color:#6b7280'>${waitingVotes} jogador(es) ainda votando</small>`;
    }
    const canSubmit = INV.pendingVote.violacao !== null && INV.pendingVote.artigo && INV.pendingVote.culpado;
    const btn = document.getElementById('inv-btn-submit-vote');
    if (btn) { btn.disabled = !canSubmit; btn.style.opacity = canSubmit ? '1' : '0.4'; }
  }
}

function invRenderResultado(state) {
  if (!state.resultado) return;
  const res = state.resultado;
  const respEl = document.getElementById('inv-resposta-correta');
  if (respEl) respEl.innerHTML = `
    <h4>✅ Resposta Correta</h4>
    <div class='inv-resposta-item'><span>Violação</span><strong style='color:#34d399'>${res.resposta_correta.violacao?'SIM':'NÃO'}</strong></div>
    <div class='inv-resposta-item'><span>Artigo</span><strong style='color:#34d399'>${res.resposta_correta.artigo}</strong></div>
    <div class='inv-resposta-item'><span>Responsável</span><strong style='color:#34d399'>${res.resposta_correta.culpado}</strong></div>
    <div class='inv-resposta-item'><span>Direito Violado</span><strong style='color:#34d399'>${res.resposta_correta.direito}</strong></div>`;
  const medals = ['🥇','🥈','🥉'];
  const rankEl = document.getElementById('inv-resultado-ranking');
  if (rankEl) rankEl.innerHTML = res.rankings.map((p,i) => `
    <div class='inv-rank-item'>
      <span class='inv-rank-pos'>${medals[i]||'🏅'}</span>
      <div>
        <div class='inv-rank-name'>${p.name}${p.id===invGetPlayerId()?' 👈':''}</div>
        <div class='inv-rank-details'>${(p.details||[]).join(' • ')}</div>
      </div>
      <div class='inv-rank-score'>${p.score} pts</div>
    </div>`).join('');
}

function invSetVote(field, value) {
  INV.pendingVote[field] = value;
  // Update UI
  if (field === 'violacao') {
    document.querySelectorAll('#vbtn-sim, #vbtn-nao').forEach(b => b.classList.remove('selected'));
    document.getElementById(value ? 'vbtn-sim' : 'vbtn-nao')?.classList.add('selected');
  } else {
    document.querySelectorAll(`.inv-${field === 'artigo' ? 'artigo' : 'culpado'}-options .inv-vote-btn`).forEach(b => {
      b.classList.toggle('selected', b.textContent.trim() === value || b.onclick?.toString().includes(`"${value}"`));
    });
  }
  invRenderVotacao(INV.lastState || {players:[]});
}

async function invSubmitVote() {
  const v = INV.pendingVote;
  if (v.violacao === null || !v.artigo || !v.culpado) return;
  try {
    await fetch('/api/inv/vote', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), vote: v }) });
    document.getElementById('inv-btn-submit-vote').textContent = '✅ Voto enviado!';
    document.getElementById('inv-btn-submit-vote').disabled = true;
  } catch(e) {}
}

async function invMarkReady() {
  await fetch('/api/inv/action', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), action: 'ready' }) });
  document.getElementById('inv-btn-ready').textContent = '✅ Aguardando outros...';
  document.getElementById('inv-btn-ready').disabled = true;
}

async function invToggleBots() {
  const newState = !(INV.botsEnabled !== false);
  try {
    await fetch('/api/inv/toggle_bots', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), enabled: newState }) });
    INV.botsEnabled = newState;
    invPoll();
    invToast(newState ? '🤖 Bots ativados' : '🚫 Bots desativados');
  } catch(e) {}
}

async function invUseSkill(action) {
  await fetch('/api/inv/action', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), action }) });
  invPoll();
}

async function invUseSkillOn(action, target) {
  await fetch('/api/inv/action', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), action, target }) });
  invPoll();
}

async function invSendChat() {
  const inp = document.getElementById('inv-chat-text');
  const text = inp?.value.trim();
  if (!text) return;
  inp.value = '';
  await fetch('/api/inv/chat', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), text }) });
  invPoll();
}

async function invSendArg(text) {
  await fetch('/api/inv/chat', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ room_id: INV.roomId, player_id: invGetPlayerId(), text }) });
  invPoll();
}

function invTab(name) {
  ['case','evidence','chat'].forEach(t => {
    document.getElementById('inv-tab-'+t)?.classList.toggle('hidden', t!==name);
    document.querySelectorAll('.inv-tab').forEach((btn,i) => {
      const names = ['case','evidence','chat'];
      btn.classList.toggle('active', names[i]===name);
    });
  });
}

function invFmtTime(s) {
  const m = Math.floor(s/60); const sec = Math.floor(s%60);
  return m > 0 ? `${m}:${sec.toString().padStart(2,'0')}` : `${Math.ceil(s)}s`;
}


/* ── TOAST NOTIFICATION (v3) ───────────────────────────────────────── */
function invToast(msg, duration=2500) {
  const t = document.createElement('div');
  t.className = 'inv-toast-notif';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => {
    t.style.animation = 'toastOut .4s ease forwards';
    setTimeout(() => t.remove(), 400);
  }, duration);
}

/* ── BUTTON RIPPLE ──────────────────────────────────────────────────── */
document.addEventListener('click', e => {
  const btn = e.target.closest('.btn,.inv-btn-primary,.inv-btn-secondary,.inv-btn-ghost');
  if (!btn) return;
  const rect = btn.getBoundingClientRect();
  const rx = ((e.clientX - rect.left) / rect.width * 100).toFixed(1) + '%';
  const ry = ((e.clientY - rect.top)  / rect.height * 100).toFixed(1) + '%';
  btn.style.setProperty('--rx', rx);
  btn.style.setProperty('--ry', ry);
});


function invPlayAgain() {
  if (INV.pollTimer) { clearInterval(INV.pollTimer); INV.pollTimer = null; }
  INV.roomId = null; INV.phase = null;
  invShowScreen('lobby');
  invRefreshRooms();
}

/* ══ END INVESTIGATION GAME ═══════════════════════════════════════════ */
</script>
</body>
</html>"""


# ── BACKEND ──────────────────────────────────────────────────────────────────

def clean_entry(item: dict) -> dict:
    return {
        "name":               str(item.get("name", "Anonimo"))[:30],
        "score":              max(int(item.get("score", 0)), 0),
        "title":              str(item.get("title", "Participante"))[:80],
        "medals":             [str(m)[:60] for m in item.get("medals", [])][:8],
        "completion_seconds": max(int(item.get("completion_seconds", 0)), 0),
        "correct_answers":    max(int(item.get("correct_answers", 0)), 0),
        "total_questions":    max(int(item.get("total_questions", 15)), 1),
        "saved_at":           str(item.get("saved_at", ""))[:32],
        "created_at":         str(item.get("created_at", ""))[:40],
    }


def sort_ranking(entries: list) -> list:
    return sorted(
        entries,
        key=lambda x: (-x["score"], x["completion_seconds"], x.get("created_at",""), x["name"].lower()),
    )


def load_ranking() -> list:
    result = _supa("GET", "ranking", params="?select=*&order=score.desc,completion_seconds.asc")
    if not isinstance(result, list):
        return []
    entries = []
    for row in result:
        medals = row.get("medals", [])
        if isinstance(medals, str):
            try: medals = json.loads(medals)
            except: medals = []
        entries.append(clean_entry({**row, "medals": medals}))
    return entries[:RANKING_LIMIT]


def save_ranking(entry: dict) -> list:
    with LOCK:
        cleaned = clean_entry(entry)
        payload = {**cleaned, "medals": json.dumps(cleaned["medals"], ensure_ascii=False)}
        _supa("POST", "ranking", data=payload)
        return load_ranking()


def get_account(name: str) -> dict:
    enc = urllib.parse.quote(name, safe="")
    result = _supa("GET", "accounts", params=f"?name=eq.{enc}&select=*")
    if isinstance(result, list) and result:
        raw = result[0].get("data", {})
        if isinstance(raw, str):
            try: return json.loads(raw)
            except: return {}
        return raw if isinstance(raw, dict) else {}
    return {}


def save_account(name: str, data: dict) -> None:
    with LOCK:
        # Preserva o hash de senha se ja existir e nao vier novo
        existing = get_account(name)
        if "pwHash" not in data and "pwHash" in existing:
            data["pwHash"] = existing["pwHash"]
        payload = {"name": name[:30], "data": json.dumps(data, ensure_ascii=False)}
        _supa("POST", "accounts", data=payload)


def load_profiles() -> dict:
    result = _supa("GET", "profiles", params="?select=*")
    if not isinstance(result, list):
        return {}
    out = {}
    for row in result:
        n = row.get("name", "")
        raw = row.get("data", {})
        if isinstance(raw, str):
            try: raw = json.loads(raw)
            except: raw = {}
        out[n] = raw
    return out


def save_profile_data(name: str, data: dict) -> dict:
    with LOCK:
        payload = {"name": name[:30], "data": json.dumps(data, ensure_ascii=False)}
        _supa("POST", "profiles", data=payload)
        return {}


def load_accounts() -> dict:
    # Mantido por compatibilidade — use get_account() diretamente
    result = _supa("GET", "accounts", params="?select=*")
    if not isinstance(result, list):
        return {}
    out = {}
    for row in result:
        n = row.get("name", "")
        raw = row.get("data", {})
        if isinstance(raw, str):
            try: raw = json.loads(raw)
            except: raw = {}
        out[n] = raw
    return out


def render_html() -> bytes:
    html = HTML.replace("__TITLE__", TITLE)
    html = html.replace("__QUESTIONS__", json.dumps(QUESTIONS, ensure_ascii=False))
    html = html.replace("__LEVELS__",    json.dumps(LEVELS,    ensure_ascii=False))
    return html.encode("utf-8")


# ── HTTP HANDLER ──────────────────────────────────────────────────────────────

class QuizHandler(BaseHTTPRequestHandler):
    def send_bytes(self, body, ct, status=HTTPStatus.OK, cc=None):
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        if cc: self.send_header("Cache-Control", cc)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8", status, "no-store,no-cache,must-revalidate")

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in {"/", "/index.html"}:
            body = render_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)
        elif p == "/manifest.webmanifest":
            self.send_bytes(json.dumps(MANIFEST, ensure_ascii=False).encode(), "application/manifest+json; charset=utf-8")
        elif p == "/service-worker.js":
            self.send_bytes(SERVICE_WORKER.encode(), "application/javascript; charset=utf-8")
        elif p == "/icon.svg":
            self.send_bytes(ICON_SVG.encode(), "image/svg+xml; charset=utf-8")
        elif p == "/api/ranking":
            self.send_json(load_ranking())
        elif p.startswith("/api/account"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = qs.get("name", [""])[0].strip()
            if name:
                self.send_json(get_account(name))
            else:
                self.send_json({})
        elif p.startswith("/api/profile"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = qs.get("name", [""])[0]
            if name:
                profiles = load_profiles()
                self.send_json(profiles.get(name, {}))
            else:
                self.send_json({})
        elif p == "/api/inv/rooms":
            self.send_json(inv_list_rooms())
        elif p == "/api/inv/state":
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            room_id   = qs.get("room_id",   [""])[0].strip()
            player_id = qs.get("player_id", [""])[0].strip()
            state = inv_get_state(room_id, player_id)
            if state:
                self.send_json(state)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        elif p == "/api/daily":
            today = date.today().isoformat()
            self.send_json({"date": today, "challenge": "daily"})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path == "/api/inv/toggle_bots":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST); return
            room_id   = str(payload.get("room_id", ""))
            player_id = str(payload.get("player_id", ""))
            enabled   = bool(payload.get("enabled", True))
            with INV_LOCK:
                room = INVESTIGATION_ROOMS.get(room_id)
                if room and room["players"] and room["players"][0]["id"] == player_id:
                    room["bots_enabled"] = enabled
                    self.send_json({"ok": True, "bots_enabled": enabled})
                else:
                    self.send_json({"ok": False, "msg": "Apenas o criador pode alterar"})
            return
        if self.path == "/api/inv/join":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            result = inv_join_or_create(
                str(payload.get("player_id", ""))[:30],
                str(payload.get("player_name", "Jogador"))[:20],
                str(payload.get("room_id", ""))[:12],
            )
            self.send_json(result, HTTPStatus.CREATED)
            return
        if self.path == "/api/inv/action":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            result = inv_action(
                str(payload.get("room_id", "")),
                str(payload.get("player_id", "")),
                str(payload.get("action", "")),
                str(payload.get("target", "")),
            )
            self.send_json(result)
            return
        if self.path == "/api/inv/vote":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            result = inv_vote(
                str(payload.get("room_id", "")),
                str(payload.get("player_id", "")),
                payload.get("vote", {}),
            )
            self.send_json(result)
            return
        if self.path == "/api/inv/chat":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            result = inv_chat(
                str(payload.get("room_id", "")),
                str(payload.get("player_id", "")),
                str(payload.get("text", ""))[:200],
            )
            self.send_json(result)
            return
        if self.path == "/api/account":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            name = str(payload.get("name", "")).strip()[:30]
            if not name:
                self.send_error(HTTPStatus.BAD_REQUEST, "Nome obrigatorio"); return
            save_account(name, payload)
            self.send_json({"ok": True}, HTTPStatus.CREATED)
            return
        if self.path == "/api/profile":
            size = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
            except json.JSONDecodeError:
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
            name = str(payload.get("name", "")).strip()
            if not name:
                self.send_error(HTTPStatus.BAD_REQUEST, "Nome obrigatorio"); return
            save_profile_data(name, payload)
            self.send_json({"ok": True}, HTTPStatus.CREATED)
            return
        if self.path != "/api/ranking":
            self.send_error(HTTPStatus.NOT_FOUND); return
        size = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(size) or b"{}")
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido"); return
        name = str(payload.get("name", "")).strip()
        if not name:
            self.send_error(HTTPStatus.BAD_REQUEST, "Nome obrigatorio"); return
        now = datetime.now()
        entry = {**payload, "name": name[:30],
                 "saved_at": now.strftime("%d/%m/%Y %H:%M"),
                 "created_at": now.isoformat(timespec="seconds")}
        try:
            ranking = save_ranking(entry)
        except OSError as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e)); return
        self.send_json(ranking, HTTPStatus.CREATED)

    def log_message(self, fmt, *args):
        pass


# ── SERVER ────────────────────────────────────────────────────────────────────

def guess_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def parse_args():
    import os
    p = argparse.ArgumentParser(description="Arena Constitucional")
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 10000)))
    p.add_argument("--no-browser", action="store_true", default=True)
    return p.parse_args()


def main():
    args = parse_args()
    host, port = args.host, args.port
    local = f"http://127.0.0.1:{port}" if host in {"0.0.0.0", "::"} else f"http://{host}:{port}"
    net   = f"http://{guess_ip()}:{port}" if host in {"0.0.0.0", "::"} else local
    server = ThreadingHTTPServer((host, port), QuizHandler)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(local)).start()
    print(f"Arena ativa:  {local}")
    if net != local:
        print(f"Rede local:   {net}")
    print("Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
