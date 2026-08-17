import streamlit as st
import pandas as pd
import os
import re
import base64
import random
from supabase import create_client
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão LCPC", layout="wide")

# --- CONEXÃO COM SUPABASE ---
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

sb = get_supabase()
sb_admin = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["service_key"])

# --- AUTENTICAÇÃO ---
def fazer_login(email, senha):
    try:
        resp = sb.auth.sign_in_with_password({"email": email, "password": senha})
        return resp.user, None
    except Exception as e:
        return None, str(e)

def fazer_logout():
    try:
        sb.auth.sign_out()
    except:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def verificar_admin(email):
    try:
        resultado = sb.table("perfis").select("is_admin").eq("email", email).execute().data
        if resultado:
            return resultado[0].get("is_admin", False)
    except:
        pass
    return False

# --- TELA DE LOGIN ---
def tela_login():
    logo_path = None
    for nome_arquivo in ["logo.jpg", "logo.jpeg", "logo.png", "logo.PNG", "logo.JPG"]:
        if os.path.exists(nome_arquivo):
            logo_path = nome_arquivo
            break

    st.markdown("<br>", unsafe_allow_html=True)

    col_texto, col_form = st.columns([3, 2], gap="large")

    with col_texto:
        st.markdown("""
Commander sempre foi mais do que cartas na mesa. É conversa atravessando a partida, jogadas improváveis, alianças que duram três turnos e promessas quebradas no quarto. É competição, claro, mas também é encontro.

Esta liga nasceu com uma proposta simples: colocar as pessoas no centro da experiência.

Por isso, nossas partidas são focadas em decks pré-construídos (precons). A ideia não é eliminar estratégia, habilidade ou criatividade. A ideia é criar um ponto de partida mais equilibrado, onde a diferença não esteja em quem investiu mais, encontrou a carta mais rara ou montou a combinação mais explosiva.

Quando todos começam próximos do mesmo nível, algo interessante acontece: o foco volta para a mesa.

Aqui, a política do Commander ganha espaço. As decisões importam. As histórias aparecem. Cada partida vira uma experiência diferente, porque são os jogadores que constroem o jogo, não apenas os decks.
Nossa liga existe para reunir pessoas que gostam de Magic, mas também valorizam o "Gathering" que vive dentro dele.

Então escolha seu comandante, embaralhe seu precon, compre sete cartas e encontre seu lugar na mesa.
A partida está começando.

<br>
Um abraço,<br>
<strong>Adrian Malta.</strong>
<br><br>
<em>Mana, vai!</em>
""", unsafe_allow_html=True)

    with col_form:
        if logo_path:
            _, col_logo, _ = st.columns([1, 3, 1])
            with col_logo:
                st.image(logo_path, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        with st.form("form_login"):
            email = st.text_input("E-mail", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            botao = st.form_submit_button("Entrar", use_container_width=True)

            if botao:
                if not email or not senha:
                    st.error("Preencha e-mail e senha.")
                else:
                    user, erro = fazer_login(email.strip(), senha)
                    if user:
                        st.session_state.usuario_logado = user
                        st.session_state.usuario_email = user.email
                        st.session_state.is_admin = verificar_admin(user.email)
                        st.session_state.dados_carregados = False
                        # Salva token para recuperar sessão após F5 (por usuário, sem conflito)
                        try:
                            sessao = sb.auth.get_session()
                            if sessao and sessao.access_token:
                                st.session_state.auth_token = sessao.access_token
                        except:
                            pass
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
<div style='text-align:left; color:#444; font-size:12px; padding: 0 20px;'>
    Criado por <strong>Suíno Divino</strong>
</div>
""", unsafe_allow_html=True)

# --- VERIFICAR SE ESTÁ LOGADO ---
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "usuario_email" not in st.session_state:
    st.session_state.usuario_email = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# Recupera sessão via token armazenado no session_state (seguro por usuário)
if not st.session_state.usuario_logado:
    token = st.session_state.get("auth_token")
    if token:
        try:
            resp = sb.auth.get_user(token)
            if resp and resp.user:
                st.session_state.usuario_logado = resp.user
                st.session_state.usuario_email = resp.user.email
                st.session_state.is_admin = verificar_admin(resp.user.email)
        except:
            st.session_state.auth_token = None

if not st.session_state.usuario_logado:
    tela_login()
    st.stop()

# --- A PARTIR DAQUI O USUÁRIO ESTÁ LOGADO ---
usuario_email = st.session_state.usuario_email
is_admin = st.session_state.is_admin

# --- FUNÇÕES DE FOTO ---
def upload_foto(nome_jogador, foto_bytes, extensao="jpg"):
    try:
        ext_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "JPG": "jpeg", "JPEG": "jpeg", "PNG": "png"}
        ext_norm = ext_map.get(extensao, "jpeg")
        ext_arquivo = "jpg" if ext_norm == "jpeg" else ext_norm
        caminho = f"{nome_jogador}.{ext_arquivo}"
        sb.storage.from_("fotos-jogadores").upload(
            caminho, foto_bytes,
            file_options={"content-type": f"image/{ext_norm}", "upsert": "true"}
        )
        url = sb.storage.from_("fotos-jogadores").get_public_url(caminho)
        return url
    except Exception as e:
        print(f"Erro ao fazer upload da foto: {e}")
        return ""

def deletar_foto(nome_jogador):
    for ext in ["jpg", "jpeg", "png"]:
        try:
            sb.storage.from_("fotos-jogadores").remove([f"{nome_jogador}.{ext}"])
        except:
            pass

# --- FUNÇÕES DE LEITURA ---
def carregar_dados():
    jogadores = {}
    jogs = sb.table("jogadores").select("*").execute().data
    for j in jogs:
        jogadores[j["nome"]] = {
            "apelido": j["apelido"] or "",
            "telefone": j["telefone"],
            "email": j["email"] or "",
            "foto_url": j.get("foto_url", "") or "",
            "decks": {}
        }
    decks = sb.table("decks").select("*").execute().data
    for d in decks:
        if d["jogador_nome"] in jogadores:
            jogadores[d["jogador_nome"]]["decks"][d["nome_deck"]] = {
                "comandante_primario": d["comandante_primario"],
                "comandante_secundario": d["comandante_secundario"],
                "comandante_adicional": d["comandante_adicional"] or "",
                "url": d["url"]
            }
    partidas_raw = sb.table("partidas").select("*").order("id").execute().data
    if partidas_raw:
        partidas = pd.DataFrame([{
            "ID": p["id"], "Local": p["local"], "Modo": p["modo"],
            "Jogadores": p["qtd_jogadores"], "Detalhes_Pontuacao": p["detalhes"]
        } for p in partidas_raw])
    else:
        partidas = pd.DataFrame(columns=["ID", "Local", "Modo", "Jogadores", "Detalhes_Pontuacao"])
    return jogadores, partidas

@st.cache_data(ttl=3600)
def carregar_catalogo():
    dados = sb.table("catalogo_precons").select("id, nome, comandantes, set_nome, data_lancamento, cartas, ranking, pontuacao_rank").execute().data
    return dados if dados else []

def _cores_mana(mana_cost):
    """Extrai o conjunto de cores (W/U/B/R/G) presentes num mana_cost."""
    if not mana_cost:
        return set()
    return set(re.findall(r"\{([WUBRG])\}", mana_cost.upper()))

@st.cache_data(ttl=3600)
def construir_mapa_comandantes_catalogo(catalogo):
    """Monta um mapa nome_comandante -> lista de decks onde a carta é válida
    como comandante: o(s) comandante(s) oficial(is) de cada deck, mais qualquer
    carta lendária da lista cujas cores batem com as do comandante original
    (podendo assim ser movida para a zona de comando)."""
    mapa = {}
    mapa_deck_cmds_oficiais = {}
    for deck in catalogo:
        nome_deck = deck.get("nome", "")
        cartas_deck = deck.get("cartas", []) or []
        mapa_carta_nome = {c.get("nome"): c for c in cartas_deck}
        comandantes_oficiais = [c for c in (deck.get("comandantes", []) or []) if c]
        mapa_deck_cmds_oficiais[nome_deck] = comandantes_oficiais

        cores_deck = set()
        for cmd_nome in comandantes_oficiais:
            carta_cmd = mapa_carta_nome.get(cmd_nome)
            if carta_cmd:
                cores_deck |= _cores_mana(carta_cmd.get("mana_cost", ""))
            mapa.setdefault(cmd_nome, [])
            if nome_deck not in mapa[cmd_nome]:
                mapa[cmd_nome].append(nome_deck)

        for carta in cartas_deck:
            nome_carta = carta.get("nome")
            if not nome_carta or nome_carta in comandantes_oficiais:
                continue
            if "legendary" not in carta.get("type_line", "").lower():
                continue
            if _cores_mana(carta.get("mana_cost", "")).issubset(cores_deck):
                mapa.setdefault(nome_carta, [])
                if nome_deck not in mapa[nome_carta]:
                    mapa[nome_carta].append(nome_deck)
    return mapa, mapa_deck_cmds_oficiais

def buscar_precon_por_nome(nome_deck):
    resultado = sb.table("catalogo_precons").select("*").eq("nome", nome_deck).execute().data
    return resultado[0] if resultado else None

@st.cache_data(ttl=3600)
def calcular_media_pontuacao_catalogo():
    """Calcula a pontuação média de todos os decks do catálogo (usada como
    referência para colorir os badges de pontuação)."""
    catalogo = carregar_catalogo()
    pontuacoes = [d.get("pontuacao_rank") for d in catalogo if d.get("pontuacao_rank") is not None]
    return sum(pontuacoes) / len(pontuacoes) if pontuacoes else None

def cor_pontuacao(pontuacao, media):
    """Verde para pontuação acima da média, branco na média, vermelho abaixo da média."""
    if pontuacao is None or media is None:
        return "#888888"
    if abs(pontuacao - media) < 0.01:
        return "#FFFFFF"
    if pontuacao > media:
        return "#00CC66"
    return "#FF4444"

def badge_pontuacao(pontuacao, media):
    """Retorna HTML do badge de pontuação colorido."""
    if pontuacao is None:
        return ""
    cor = cor_pontuacao(pontuacao, media)
    return f'<span style="color:{cor}; font-weight:bold; font-size:12px;">{pontuacao:.0f} pts</span>'


# --- FUNÇÕES DE ESCRITA ---
def criar_conta_jogador(email, senha):
    """Cria conta de autenticação para o jogador via Admin API."""
    try:
        resp = sb_admin.auth.admin.create_user({
            "email": email,
            "password": senha,
            "email_confirm": True
        })
        user_id = resp.user.id
        sb.table("perfis").upsert({
            "id": user_id,
            "email": email,
            "is_admin": False
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def salvar_jogador(nome, dados):
    sb.table("jogadores").upsert({
        "nome": nome,
        "apelido": dados["apelido"],
        "telefone": dados["telefone"],
        "email": dados["email"],
        "foto_url": dados.get("foto_url", "")
    }).execute()

def salvar_deck(jogador_nome, nome_deck, info):
    sb.table("decks").upsert({
        "jogador_nome": jogador_nome,
        "nome_deck": nome_deck,
        "comandante_primario": info["comandante_primario"],
        "comandante_secundario": info["comandante_secundario"],
        "comandante_adicional": info.get("comandante_adicional", ""),
        "url": info.get("url", "")
    }, on_conflict="jogador_nome,nome_deck").execute()

def excluir_deck_db(jogador_nome, nome_deck):
    sb.table("decks").delete().eq("jogador_nome", jogador_nome).eq("nome_deck", nome_deck).execute()

def excluir_jogador_db(nome):
    deletar_foto(nome)
    sb.table("jogadores").delete().eq("nome", nome).execute()

def salvar_partida(local, modo, qtd_jogadores, detalhes):
    result = sb.table("partidas").insert({
        "local": local, "modo": modo,
        "qtd_jogadores": qtd_jogadores, "detalhes": detalhes
    }).execute()
    return result.data[0]["id"]

def excluir_partida_db(partida_id):
    sb.table("partidas").delete().eq("id", int(partida_id)).execute()

# --- FUNÇÕES DE TORNEIOS (SUÍÇO EM MESAS DE 4 + MATA-MATA EM MESAS DE 4) ---
TAMANHO_MESA = 4

def carregar_torneios():
    dados = sb.table("torneios").select("*").order("id", desc=True).execute().data
    return dados if dados else []

def carregar_participantes_torneio(torneio_id):
    dados = sb.table("torneio_participantes").select("*").eq("torneio_id", torneio_id).order("id").execute().data
    return dados if dados else []

def carregar_confrontos_torneio(torneio_id):
    dados = sb.table("torneio_confrontos").select("*").eq("torneio_id", torneio_id).order("id").execute().data
    return dados if dados else []

def criar_torneio(nome, modo_jogo, qtd_classificados, criado_por):
    resp = sb.table("torneios").insert({
        "nome": nome, "modo_jogo": modo_jogo, "formato": "SUICO_MESAS",
        "qtd_classificados": qtd_classificados,
        "status": "CONFIGURANDO", "criado_por": criado_por
    }).execute()
    return resp.data[0]["id"] if resp.data else None

def adicionar_participante_torneio(torneio_id, jogador_nome, deck, comandante):
    sb.table("torneio_participantes").insert({
        "torneio_id": torneio_id, "jogador_nome": jogador_nome,
        "deck_escolhido": deck, "comandante_escolhido": comandante
    }).execute()

def excluir_participante_torneio(participante_id):
    sb.table("torneio_participantes").delete().eq("id", participante_id).execute()

def atualizar_status_torneio(torneio_id, status):
    sb.table("torneios").update({"status": status}).eq("id", torneio_id).execute()

def criar_confronto(torneio_id, fase, rodada, jogadores_payload):
    """jogadores_payload: lista de dicts {"jogador": nome, "eliminacoes": 0, "wo": False}"""
    sb.table("torneio_confrontos").insert({
        "torneio_id": torneio_id, "fase": fase, "rodada": rodada,
        "jogadores": jogadores_payload, "vencedor": None, "status": "PENDENTE"
    }).execute()

def registrar_resultado_confronto(confronto_id, jogadores_payload, vencedor):
    sb.table("torneio_confrontos").update({
        "jogadores": jogadores_payload, "vencedor": vencedor, "status": "CONCLUIDO"
    }).eq("id", confronto_id).execute()

def excluir_torneio(torneio_id):
    sb.table("torneio_confrontos").delete().eq("torneio_id", torneio_id).execute()
    sb.table("torneio_participantes").delete().eq("torneio_id", torneio_id).execute()
    sb.table("torneios").delete().eq("id", torneio_id).execute()

def calcular_classificacao_suico(nomes_participantes, confrontos_fase):
    """Calcula a tabela (Pts/V/Elim/J). Vitória = 3 pts. Eliminações servem só
    como critério de desempate (não somam pontos)."""
    tabela = {nome: {"Pts": 0, "V": 0, "Elim": 0, "J": 0} for nome in nomes_participantes}
    for c in confrontos_fase:
        if c.get("status") != "CONCLUIDO":
            continue
        venc = c.get("vencedor")
        for info in c.get("jogadores", []):
            nome = info.get("jogador")
            if nome not in tabela or info.get("wo"):
                continue
            tabela[nome]["J"] += 1
            tabela[nome]["Elim"] += info.get("eliminacoes", 0)
            if nome == venc:
                tabela[nome]["V"] += 1
                tabela[nome]["Pts"] += 3
    linhas = [{"Jogador": nome, **stats} for nome, stats in tabela.items()]
    linhas.sort(key=lambda x: (-x["Pts"], -x["Elim"]))
    return linhas

def montar_mesas(nomes_ordenados, historico_pares, tamanho_mesa=TAMANHO_MESA):
    """Monta as mesas de uma rodada a partir de uma lista já ordenada (por força,
    no suíço, ou aleatória, na 1ª rodada). Tenta evitar que dois jogadores que já
    se enfrentaram em rodadas anteriores caiam na mesma mesa. Se sobrar 1 jogador
    isolado no final, ele é incorporado à mesa anterior (formando uma mesa de 5)."""
    restantes = list(nomes_ordenados)
    mesas = []
    while restantes:
        mesa = [restantes.pop(0)]
        while len(mesa) < tamanho_mesa and restantes:
            candidato_idx = None
            for idx, jogador in enumerate(restantes):
                if all(frozenset((jogador, m)) not in historico_pares for m in mesa):
                    candidato_idx = idx
                    break
            if candidato_idx is None:
                candidato_idx = 0
            mesa.append(restantes.pop(candidato_idx))
        mesas.append(mesa)
    if len(mesas) >= 2 and len(mesas[-1]) == 1:
        orfao = mesas.pop()[0]
        mesas[-1].append(orfao)
    return mesas

def construir_historico_pares(confrontos_fase):
    """Monta o conjunto de pares de jogadores que já dividiram mesa em rodadas anteriores."""
    historico = set()
    for c in confrontos_fase:
        nomes = [info.get("jogador") for info in c.get("jogadores", [])]
        for i in range(len(nomes)):
            for j in range(i + 1, len(nomes)):
                historico.add(frozenset((nomes[i], nomes[j])))
    return historico

def _contar_repeticoes_mesas(mesas, historico_pares):
    total = 0
    for mesa in mesas:
        for i in range(len(mesa)):
            for j in range(i + 1, len(mesa)):
                if frozenset((mesa[i], mesa[j])) in historico_pares:
                    total += 1
    return total

def gerar_rodada_classificatoria(participantes, confrontos_fase, numero_rodada, tentativas=150):
    """Gera a próxima rodada da fase classificatória (suíço): a partir da 2ª
    rodada, agrupa por pontuação atual (Pts, depois Elim). Faz várias tentativas
    (com pequena variação) e fica com a que tiver menos jogadores repetidos na
    mesma mesa — nem sempre dá pra zerar totalmente, dependendo da combinação
    de jogadores/rodadas, mas minimiza ao máximo."""
    historico = construir_historico_pares(confrontos_fase)
    if numero_rodada == 1:
        base_ordenada = list(participantes)
    else:
        tabela = calcular_classificacao_suico(participantes, confrontos_fase)
        base_ordenada = [linha["Jogador"] for linha in tabela]

    melhor_mesas, melhor_rep = None, None
    for _ in range(tentativas):
        ordenados = list(base_ordenada)
        random.shuffle(ordenados)
        mesas = montar_mesas(ordenados, historico)
        rep = _contar_repeticoes_mesas(mesas, historico)
        if melhor_rep is None or rep < melhor_rep:
            melhor_rep, melhor_mesas = rep, mesas
            if rep == 0:
                break
    return melhor_mesas

def determinar_avancantes_mesa(confronto):
    """Numa mesa concluída, retorna (1º colocado, 2º colocado) — o vencedor e,
    entre os demais presentes, quem mais eliminou (critério de desempate)."""
    venc = confronto.get("vencedor")
    outros = [info for info in confronto.get("jogadores", []) if info.get("jogador") != venc and not info.get("wo")]
    outros.sort(key=lambda info: -info.get("eliminacoes", 0))
    segundo = outros[0]["jogador"] if outros else None
    return venc, segundo

def gerar_mesas_matamata(jogadores_avancando, tamanho_mesa=TAMANHO_MESA):
    """Divide os classificados em mesas de 4 (chunks sequenciais, preservando o
    seed de força quando a lista já vier ordenada por classificação)."""
    return [jogadores_avancando[i:i + tamanho_mesa] for i in range(0, len(jogadores_avancando), tamanho_mesa)]

# --- CARREGAMENTO INICIAL ---
if "dados_carregados" not in st.session_state or not st.session_state.dados_carregados:
    st.session_state.jogadores, st.session_state.partidas = carregar_dados()
    st.session_state.dados_carregados = True

if "mensagem_sucesso_partida" not in st.session_state:
    st.session_state.mensagem_sucesso_partida = None
if "mensagem_sucesso_perfil" not in st.session_state:
    st.session_state.mensagem_sucesso_perfil = None
if "deck_precon_preview" not in st.session_state:
    st.session_state.deck_precon_preview = None
if "busca_precon" not in st.session_state:
    st.session_state.busca_precon = ""

# --- FUNÇÃO AUXILIAR ---
def obter_nome_exibicao(dados_jogador, nome_chave):
    if dados_jogador.get("apelido"):
        return dados_jogador["apelido"]
    return nome_chave

# --- FUNÇÃO: EXIBE LISTA DE CARTAS COM HOVER ---
def gerar_texto_deck(cartas, nome_deck=""):
    """Monta a lista de cartas em formato texto padrão (qtd + nome), pronta
    para download ou para colar em sites como Moxfield/Archidekt."""
    linhas = []
    if nome_deck:
        linhas.append(f"// {nome_deck}")
        linhas.append("")
    cartas_ordenadas = sorted(cartas, key=lambda c: c.get("nome", ""))
    for carta in cartas_ordenadas:
        qtd = carta.get("quantidade", 1)
        nome = carta.get("nome", "")
        linhas.append(f"{qtd} {nome}")
    return "\n".join(linhas)


def botao_copiar_lista(texto, key):
    """Renderiza um botão 'Copiar Lista' que copia o texto para a área de
    transferência do usuário via JavaScript (clipboard API)."""
    import streamlit.components.v1 as _components
    b64 = base64.b64encode(texto.encode("utf-8")).decode("ascii")
    html_code = f"""
    <div>
        <button id="btn_copy_{key}" style="
            width:100%; padding:0.5rem 1rem; border-radius:8px;
            border:1px solid rgba(250,250,250,0.2); background-color:transparent;
            color:inherit; font-size:14px; cursor:pointer; font-family:inherit;">
            📋 Copiar Lista
        </button>
    </div>
    <script>
        const btn_{key} = document.getElementById("btn_copy_{key}");
        btn_{key}.addEventListener("click", function() {{
            const decoded = atob("{b64}");
            const bytes = Uint8Array.from(decoded, c => c.charCodeAt(0));
            const texto = new TextDecoder("utf-8").decode(bytes);
            navigator.clipboard.writeText(texto).then(function() {{
                const original = btn_{key}.innerHTML;
                btn_{key}.innerHTML = "✅ Copiado!";
                setTimeout(function() {{ btn_{key}.innerHTML = original; }}, 1500);
            }});
        }});
    </script>
    """
    _components.html(html_code, height=45)


def exibir_lista_cartas(cartas, comandante_primario=None, nome_deck=""):
    import uuid as _uuid
    import streamlit.components.v1 as _components

    if cartas:
        texto_deck = gerar_texto_deck(cartas, nome_deck)
        _key_base = re.sub(r"[^a-zA-Z0-9]", "_", nome_deck or str(_uuid.uuid4()))
        col_dl, col_cp = st.columns(2)
        with col_dl:
            st.download_button(
                "⬇️ Download Lista (.txt)",
                data=texto_deck,
                file_name=f"{(nome_deck or 'deck').strip().replace(' ', '_')}.txt",
                mime="text/plain",
                key=f"dl_{_key_base}",
                use_container_width=True,
            )
        with col_cp:
            botao_copiar_lista(texto_deck, key=_key_base)
        st.markdown("<br>", unsafe_allow_html=True)

    ordem_blocos = ["Comandante", "Criaturas", "Planeswalkers", "Magicas Instantaneas",
                    "Feiticos", "Artefatos", "Encantamentos", "Batalhas", "Terrenos", "Outros"]
    ordem_blocos_display = {
        "Magicas Instantaneas": "Mágicas Instantâneas",
        "Feiticos": "Feitiços"
    }

    grupos = {}
    for carta in cartas:
        bloco_orig = carta.get("tipo_bloco", "Outros") or "Outros"
        # Normaliza para evitar problemas com acentos nas keys
        bloco = bloco_orig.replace("Mágicas Instantâneas", "Magicas Instantaneas").replace("Feitiços", "Feiticos")
        grupos.setdefault(bloco, []).append(carta)
    # Também aceita blocos já com acento
    for carta in cartas:
        bloco_orig = carta.get("tipo_bloco", "Outros") or "Outros"
        if bloco_orig not in grupos:
            grupos.setdefault(bloco_orig, []).append(carta)

    # Imagem inicial = comandante primário
    img_inicial = ""
    nome_inicial = ""
    if comandante_primario:
        for carta in cartas:
            if carta["nome"].lower() == comandante_primario.lower() and carta.get("imagem_url"):
                img_inicial = carta["imagem_url"]
                nome_inicial = carta["nome"]
                break
    if not img_inicial:
        for bloco in ["Comandante", "Criaturas"]:
            if bloco in grupos:
                for c in grupos[bloco]:
                    if c.get("imagem_url"):
                        img_inicial = c["imagem_url"]
                        nome_inicial = c["nome"]
                        break
            if img_inicial:
                break

    # Monta colunas esquerda e direita (blocos alternados)
    blocos_existentes = [b for b in ordem_blocos if b in grupos or ordem_blocos_display.get(b, b) in grupos]
    col_esq = blocos_existentes[:len(blocos_existentes)//2 + len(blocos_existentes)%2]
    col_dir = blocos_existentes[len(blocos_existentes)//2 + len(blocos_existentes)%2:]

    def render_bloco(bloco):
        bloco_real = bloco if bloco in grupos else ordem_blocos_display.get(bloco, bloco)
        if bloco_real not in grupos:
            return ""
        cartas_bloco = sorted(grupos[bloco_real], key=lambda c: c["nome"])
        display = ordem_blocos_display.get(bloco, bloco_real)
        total = sum(c.get("quantidade", 1) for c in cartas_bloco)
        h = f'<div class="bloco-titulo">{display} ({total})</div>'
        for carta in cartas_bloco:
            nome = carta["nome"].replace('"', '&quot;').replace("'", "&#39;")
            qtd = carta.get("quantidade", 1)
            img = carta.get("imagem_url", "").replace('"', '%22')
            mana = carta.get("mana_cost", "")
            mana_html = f'<span class="mana">{mana}</span>' if mana else ""
            h += (f'<div class="ci" data-img="{img}" data-nome="{nome}">'
                  f'<span class="qty">{qtd}x</span>{nome}{mana_html}</div>')
        return h

    esq_html = "".join(render_bloco(b) for b in col_esq)
    dir_html = "".join(render_bloco(b) for b in col_dir)
    total_cartas = sum(c.get("quantidade", 1) for c in cartas)

    html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:8px; background:transparent; font-family: sans-serif; color: #eee; overflow-x: hidden; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px; }}
  @media (max-width: 500px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  .bloco-titulo {{
    font-size: 12px; font-weight: bold; color: #888;
    text-transform: uppercase; letter-spacing: 1px;
    margin: 14px 0 3px 0; padding-bottom: 2px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
  }}
  .ci {{
    display: block; padding: 2px 4px; margin: 1px 0;
    border-radius: 4px; font-size: 13px; cursor: pointer;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .ci:hover {{ background-color: rgba(255,255,255,0.1); }}
  .qty {{
    display: inline-block; min-width: 22px; text-align: center;
    background: rgba(255,255,255,0.12); border-radius: 3px;
    margin-right: 5px; font-size: 11px; padding: 0 3px;
  }}
  .mana {{ font-size: 10px; color: #999; margin-left: 4px; }}

  /* Tooltip flutuante que segue o mouse */
  #card-float {{
    display: none;
    position: fixed;
    z-index: 99999;
    width: 220px;
    pointer-events: none;
    filter: drop-shadow(0 8px 24px rgba(0,0,0,0.8));
  }}
  #card-float img {{ width: 220px; border-radius: 10px; }}
</style>
</head>
<body>
<div id="card-float"><img id="float-img" src="" alt=""/></div>
<div class="two-col">
  <div class="col-esq">{esq_html}</div>
  <div class="col-dir">{dir_html}</div>
</div>
<script>
  var floatEl = document.getElementById('card-float');
  var floatImg = document.getElementById('float-img');
  var lastImg = '{img_inicial}';

  document.addEventListener('mousemove', function(e) {{
    if (floatEl.style.display === 'block') {{
      var x = e.clientX + 16;
      var y = e.clientY - 110;
      if (x + 220 > window.innerWidth) x = e.clientX - 236;
      if (y < 8) y = 8;
      floatEl.style.left = x + 'px';
      floatEl.style.top = y + 'px';
    }}
  }});

  document.querySelectorAll('.ci').forEach(function(el) {{
    el.addEventListener('mouseenter', function() {{
      var img = this.dataset.img;
      if (img) {{
        floatImg.src = img;
        lastImg = img;
        floatEl.style.display = 'block';
      }}
    }});
    el.addEventListener('mouseleave', function() {{
      floatEl.style.display = 'none';
    }});
  }});
</script>
</body>
</html>"""

    altura = max(400, total_cartas * 19 + 120)
    _components.html(html, height=altura, scrolling=True)


# --- BARRA LATERAL ---
formatos_logo = ["logo.jpg", "logo.jpeg", "logo.png", "logo.PNG", "logo.JPG"]
logo_encontrada = None
for nome_arquivo in formatos_logo:
    if os.path.exists(nome_arquivo):
        logo_encontrada = nome_arquivo
        break

if logo_encontrada:
    st.sidebar.image(logo_encontrada, use_container_width=True)

# Info do usuário logado na sidebar
# Busca apelido/nome do jogador logado
_nome_sidebar = usuario_email
for _n, _d in st.session_state.jogadores.items():
    if _d.get("email") == usuario_email:
        _nome_sidebar = _d.get("apelido") or _n
        break

st.sidebar.markdown("---")
st.sidebar.markdown(f"**{_nome_sidebar}**")
if is_admin:
    st.sidebar.markdown("*Administrador*")
if st.sidebar.button("Sair", use_container_width=True):
    fazer_logout()

with st.sidebar:
    aba = option_menu(
        menu_title=None,
        options=["Statistics", "Cadastro", "Jogadores", "Decks", "Nova Partida", "Torneios"],
        icons=["trophy", "person-plus", "people", "card-list", "controller", "diagram-3"],
        menu_icon=None,
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "nav-link": {
                "font-size": "15px", "text-align": "left", "margin": "0px",
                "background-color": "transparent", "color": "#888888"
            },
            "nav-link-selected": {
                "background-color": "transparent", "color": "#FFFFFF",
                "font-weight": "bold", "text-transform": "uppercase"
            }
        }
    )

# ===================== CADASTRO =====================
if aba == "Cadastro":
    st.header("Gerenciamento de Perfis")

    # Abas visíveis dependem do nível de acesso
    if is_admin:
        tab_criar, tab_editar, tab_excluir = st.tabs(["Novo Jogador", "Editar Perfil", "Excluir Jogador"])
    else:
        tab_editar, = st.tabs(["Editar Perfil"])
        tab_criar = None
        tab_excluir = None

    if is_admin and tab_criar:
        with tab_criar:
            st.subheader("Cadastrar Novo Jogador")
            with st.form("form_cadastro_jogador", clear_on_submit=True):
                st.markdown("Nome <span style='color:red;'>*</span>", unsafe_allow_html=True)
                nome = st.text_input("", label_visibility="collapsed", key="txt_cad_nome_real")
                st.markdown("Apelido")
                apelido = st.text_input("", label_visibility="collapsed", key="txt_cad_apelido_real")
                st.markdown("Telefone <span style='color:red;'>*</span>", unsafe_allow_html=True)
                telefone = st.text_input("", label_visibility="collapsed", key="txt_cad_telefone_real")
                st.markdown("E-mail <span style='color:red;'>*</span>", unsafe_allow_html=True)
                email = st.text_input("", label_visibility="collapsed", key="txt_cad_email_real")
                st.markdown("Senha de Acesso <span style='color:red;'>*</span>", unsafe_allow_html=True)
                senha = st.text_input("", type="password", label_visibility="collapsed", key="txt_cad_senha_real")
                st.markdown("Foto do Jogador")
                foto = st.file_uploader("", type=["jpg", "png", "jpeg"], label_visibility="collapsed", key="file_cad_foto_real")
                st.markdown("<span style='color:red;'>* CAMPOS OBRIGATÓRIOS</span>", unsafe_allow_html=True)
                botao_salvar = st.form_submit_button("Salvar Cadastro")

                if botao_salvar:
                    nome = nome.strip()
                    telefone = telefone.strip()
                    email = email.strip()
                    senha = senha.strip()
                    erros = []
                    if not nome or not telefone or not email or not senha:
                        erros.append("Preencha todos os campos obrigatórios.")
                    if nome and not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", nome):
                        erros.append("O campo Nome não pode conter caracteres especiais ou números.")
                    if telefone and not telefone.isdigit():
                        erros.append("O campo Telefone deve conter apenas números.")
                    if email:
                        padrao_email = r"^[\w\.-]+@[\w\.-]+\.(com|com\.br)$"
                        if not re.match(padrao_email, email):
                            erros.append("O formato do E-mail é inválido.")
                    if senha and len(senha) < 6:
                        erros.append("A senha deve ter pelo menos 6 caracteres.")
                    if erros:
                        for erro in erros:
                            st.error(erro)
                    else:
                        if nome not in st.session_state.jogadores:
                            # Cria conta de autenticação
                            ok, erro_auth = criar_conta_jogador(email, senha)
                            if not ok:
                                st.error(f"Erro ao criar conta de acesso: {erro_auth}")
                            else:
                                foto_url = ""
                                if foto:
                                    ext = foto.name.split(".")[-1].lower()
                                    foto_url = upload_foto(nome, foto.read(), ext)
                                novo_jogador = {
                                    "apelido": apelido, "telefone": telefone,
                                    "email": email, "foto_url": foto_url, "decks": {}
                                }
                                st.session_state.jogadores[nome] = novo_jogador
                                salvar_jogador(nome, novo_jogador)
                                st.success(f"Jogador {apelido if apelido else nome} cadastrado com sucesso!")
                        else:
                            st.warning("Este jogador já está cadastrado!")

    with tab_editar:
        st.subheader("Editar Perfil Existente")
        if st.session_state.get("mensagem_sucesso_perfil"):
            st.success(st.session_state.mensagem_sucesso_perfil)
            st.session_state.mensagem_sucesso_perfil = None

        if st.session_state.jogadores:
            # Admin vê todos; jogador comum vê só o próprio
            if is_admin:
                opcoes_edicao = ["Selecione um jogador..."] + list(st.session_state.jogadores.keys())
            else:
                jogador_proprio = next(
                    (n for n, d in st.session_state.jogadores.items() if d["email"] == usuario_email),
                    None
                )
                if jogador_proprio:
                    opcoes_edicao = [jogador_proprio]
                else:
                    st.info("Seu perfil de jogador ainda não foi cadastrado pelo administrador.")
                    opcoes_edicao = []

            if opcoes_edicao:
                if is_admin:
                    jog_editar_real = st.selectbox("Escolha o perfil que deseja alterar:", opcoes_edicao, key="sel_edit_jog")
                else:
                    jog_editar_real = opcoes_edicao[0]
                    st.markdown(f"**Editando seu perfil:** {jog_editar_real}")

                if is_admin and jog_editar_real == "Selecione um jogador...":
                    pass
                else:
                    dados_edit = st.session_state.jogadores[jog_editar_real]
                    # Keys dinâmicas por jogador para evitar cache entre trocas
                    _k = jog_editar_real.replace(" ", "_")
                    novo_apelido = st.text_input("Editar Apelido", value=dados_edit["apelido"], key=f"txt_edit_apelido_{_k}")
                    novo_telefone = st.text_input("Editar Telefone", value=dados_edit["telefone"], key=f"txt_edit_telefone_{_k}")
                    novo_email = st.text_input("Editar E-mail", value=dados_edit["email"], key=f"txt_edit_email_{_k}")
                    if is_admin:
                        nova_senha = st.text_input("Nova Senha (deixe em branco para não alterar)", type="password", key=f"txt_edit_senha_{_k}")
                    nova_foto = st.file_uploader("Atualizar Foto", type=["jpg", "png", "jpeg"], key=f"file_edit_foto_{_k}")

                    if st.button("Salvar Alterações", key="btn_salvar_edit"):
                        novo_telefone = novo_telefone.strip()
                        novo_email = novo_email.strip()
                        erros_edit = []
                        if not novo_telefone:
                            erros_edit.append("O campo Telefone não pode ficar vazio.")
                        elif not novo_telefone.isdigit():
                            erros_edit.append("O campo Telefone deve conter apenas números.")
                        padrao_email = r"^[\w\.-]+@[\w\.-]+\.(com|com\.br)$"
                        if not novo_email:
                            erros_edit.append("O campo E-mail não pode ficar vazio.")
                        elif not re.match(padrao_email, novo_email):
                            erros_edit.append("O formato do E-mail é inválido.")
                        if is_admin and nova_senha and len(nova_senha.strip()) < 6:
                            erros_edit.append("A nova senha deve ter pelo menos 6 caracteres.")
                        if erros_edit:
                            for err in erros_edit:
                                st.error(err)
                        else:
                            st.session_state.jogadores[jog_editar_real]["apelido"] = novo_apelido
                            st.session_state.jogadores[jog_editar_real]["telefone"] = novo_telefone
                            st.session_state.jogadores[jog_editar_real]["email"] = novo_email
                            if nova_foto:
                                ext = nova_foto.name.split(".")[-1].lower()
                                nova_url = upload_foto(jog_editar_real, nova_foto.read(), ext)
                                st.session_state.jogadores[jog_editar_real]["foto_url"] = nova_url
                            salvar_jogador(jog_editar_real, st.session_state.jogadores[jog_editar_real])
                            # Atualiza senha se admin preencheu
                            if is_admin and nova_senha and nova_senha.strip():
                                try:
                                    usuarios = sb_admin.auth.admin.list_users()
                                    user_match = next((u for u in usuarios if u.email == novo_email), None)
                                    if user_match:
                                        sb_admin.auth.admin.update_user_by_id(user_match.id, {"password": nova_senha.strip()})
                                except Exception as e:
                                    st.warning(f"Perfil salvo, mas erro ao atualizar senha: {e}")
                            st.session_state.mensagem_sucesso_perfil = f"Perfil de {jog_editar_real} atualizado com sucesso!"
                            st.rerun()
        else:
            st.info("Nenhum jogador cadastrado para editar.")

    if is_admin and tab_excluir:
        with tab_excluir:
            st.subheader("Remover Jogador da Liga")
            if st.session_state.jogadores:
                opcoes_exclusao = ["Selecione um jogador..."] + list(st.session_state.jogadores.keys())
                jog_excluir = st.selectbox("Escolha o perfil que deseja remover:", opcoes_exclusao, key="sel_excluir_jog")
                if jog_excluir != "Selecione um jogador...":
                    st.warning(f"Atenção: Excluir {jog_excluir} removerá o perfil e seus decks.")
                    if st.button("Confirmar Exclusão do Jogador", type="primary", key="btn_conf_excluir_jog"):
                        excluir_jogador_db(jog_excluir)
                        del st.session_state.jogadores[jog_excluir]
                        st.success("Jogador removido com sucesso!")
                        st.rerun()
            else:
                st.info("Nenhum jogador cadastrado.")

# ===================== JOGADORES =====================
elif aba == "Jogadores":
    st.header("Perfis e Arsenal")
    if st.session_state.jogadores:
        opcoes_selectbox = {"Selecione um jogador...": "NEUTRO"}
        for n, dados in st.session_state.jogadores.items():
            opcoes_selectbox[obter_nome_exibicao(dados, n)] = n

        jogador_sel_exibicao = st.selectbox("Visualizar jogador:", list(opcoes_selectbox.keys()), key="sel_ver_jogador_real")

        # Limpa preview ao trocar de jogador
        if st.session_state.get("ultimo_jogador_visto") != jogador_sel_exibicao:
            st.session_state.ultimo_jogador_visto = jogador_sel_exibicao
            st.session_state.deck_precon_preview = None
            st.session_state.deck_preview_context = None

        if jogador_sel_exibicao != "Selecione um jogador...":
            jogador_real = opcoes_selectbox[jogador_sel_exibicao]
            dados_j = st.session_state.jogadores[jogador_real]

            # Verifica se o jogador logado pode editar este perfil
            pode_editar = is_admin or (dados_j["email"] == usuario_email)

            col1, col2 = st.columns([1, 2])
            with col1:
                foto_url = dados_j.get("foto_url", "")
                if foto_url:
                    st.image(foto_url, width=200, caption=f"Foto de {jogador_sel_exibicao}")
                else:
                    st.info("Jogador não possui foto cadastrada.")
            with col2:
                st.write(f"**Nome Oficial:** {jogador_real}")
                st.write(f"**Apelido de Mesa:** {dados_j['apelido'] if dados_j['apelido'] else 'Não possui'}")
                st.write(f"**Telefone:** {dados_j['telefone']}")
                st.write(f"**E-mail:** {dados_j['email'] if dados_j['email'] else 'Não informado'}")

                st.divider()
                st.subheader("Decks do Arsenal")

                if dados_j["decks"]:
                    for nome_d, info_d in dados_j["decks"].items():
                        cmd_str = f"Primário: {info_d['comandante_primario']}"
                        if info_d.get("comandante_secundario"):
                            cmd_str += f" | Secundário: {info_d['comandante_secundario']}"
                        if info_d.get("comandante_adicional"):
                            cmd_str += f" | Adicional: {info_d['comandante_adicional']}"

                        # Busca pontuação do deck
                        _pts_info = sb.table("catalogo_precons").select("pontuacao_rank").eq("nome", nome_d).execute().data
                        _pts_val = _pts_info[0]["pontuacao_rank"] if _pts_info else None
                        _media_pts = calcular_media_pontuacao_catalogo()
                        _badge = badge_pontuacao(_pts_val, _media_pts)

                        # Botões inline por deck
                        if pode_editar:
                            col_dk, col_ver, col_edit, col_del = st.columns([3, 1, 1, 1])
                        else:
                            col_dk, col_ver = st.columns([4, 1])

                        with col_dk:
                            st.markdown(f"**{nome_d.upper()}** {_badge}  \n{cmd_str}", unsafe_allow_html=True)
                        with col_ver:
                            if st.button("Ver", key=f"ver_lista_{jogador_real}_{nome_d}"):
                                if st.session_state.get("deck_preview_context") == f"arsenal_{nome_d}":
                                    st.session_state.deck_precon_preview = None
                                    st.session_state.deck_preview_context = None
                                else:
                                    precon = buscar_precon_por_nome(nome_d)
                                    if precon:
                                        st.session_state.deck_precon_preview = precon
                                        st.session_state.deck_preview_context = f"arsenal_{nome_d}"
                                    else:
                                        st.warning("Lista não encontrada no catálogo.")
                                st.rerun()

                        if pode_editar:
                            with col_edit:
                                if st.button("Editar", key=f"btn_editar_{jogador_real}_{nome_d}"):
                                    st.session_state[f"editando_deck_{nome_d}"] = not st.session_state.get(f"editando_deck_{nome_d}", False)
                                    st.rerun()
                            with col_del:
                                if st.button("Excluir", key=f"btn_excluir_{jogador_real}_{nome_d}"):
                                    st.session_state[f"confirmar_excluir_deck_{nome_d}"] = True
                                    st.rerun()

                        # Preview da lista inline
                        if st.session_state.get("deck_preview_context") == f"arsenal_{nome_d}" and st.session_state.deck_precon_preview:
                            precon = st.session_state.deck_precon_preview
                            with st.expander(f"Lista: {precon['nome']}", expanded=True):
                                cmds = precon.get("comandantes", [])
                                if cmds:
                                    st.markdown(f"**Comandantes:** {' | '.join(cmds)}")
                                st.markdown(f"*{precon.get('set_nome', '')}*")
                                st.divider()
                                cmd_p = dados_j["decks"].get(nome_d, {}).get("comandante_primario")
                                exibir_lista_cartas(precon.get("cartas", []), comandante_primario=cmd_p, nome_deck=precon.get("nome", nome_d))
                                if st.button("Fechar Lista", key=f"fechar_preview_arsenal_{nome_d}"):
                                    st.session_state.deck_precon_preview = None
                                    st.session_state.deck_preview_context = None
                                    st.rerun()

                        # Formulário de edição inline com comandantes restritos às lendárias do deck
                        if pode_editar and st.session_state.get(f"editando_deck_{nome_d}", False):
                            with st.container():
                                st.markdown(f"**Editando: {nome_d.upper()}**")
                                dados_dk_edit = dados_j["decks"][nome_d]
                                _ke = nome_d.replace(" ", "_")

                                # Busca cartas lendárias do deck no catálogo
                                precon_edit = buscar_precon_por_nome(nome_d)
                                lendarias = []
                                if precon_edit:
                                    lendarias = [
                                        c["nome"] for c in precon_edit.get("cartas", [])
                                        if "legendary" in c.get("type_line", "").lower()
                                    ]

                                if lendarias:
                                    # Monta defaults a partir dos valores já salvos
                                    cmd_p_atual = dados_dk_edit.get("comandante_primario", "")
                                    cmd_s_atual = dados_dk_edit.get("comandante_secundario", "")
                                    cmd_a_atual = dados_dk_edit.get("comandante_adicional", "")
                                    # Junta todos os comandantes atuais em uma lista de defaults
                                    defaults_atuais = [c for c in [cmd_p_atual, cmd_s_atual, cmd_a_atual] if c and c in lendarias]
                                    if not defaults_atuais and lendarias:
                                        defaults_atuais = [lendarias[0]]

                                    st.markdown("**Selecione os comandantes** (1 = primário, 2 = partner, 3 = adicional):")
                                    cmds_selecionados = st.multiselect(
                                        "Comandantes (até 3):",
                                        lendarias,
                                        default=defaults_atuais,
                                        max_selections=3,
                                        key=f"edit_cmds_{_ke}"
                                    )
                                    edit_cmd_p = cmds_selecionados[0] if len(cmds_selecionados) > 0 else ""
                                    edit_cmd_s = cmds_selecionados[1] if len(cmds_selecionados) > 1 else ""
                                    edit_cmd_a = cmds_selecionados[2] if len(cmds_selecionados) > 2 else ""
                                else:
                                    # Fallback para texto livre se não encontrar lendárias
                                    edit_cmd_p = st.text_input("Comandante Primário*", value=dados_dk_edit.get("comandante_primario", ""), key=f"edit_cmd_p_{_ke}")
                                    edit_cmd_s = st.text_input("Comandante Secundário (Opcional)", value=dados_dk_edit.get("comandante_secundario", ""), key=f"edit_cmd_s_{_ke}")
                                    edit_cmd_a = st.text_input("Comandante Adicional (Opcional)", value=dados_dk_edit.get("comandante_adicional", ""), key=f"edit_cmd_a_{_ke}")

                                col_s, col_c, _ = st.columns([1, 1, 4])
                                with col_s:
                                    if st.button("Salvar", type="primary", key=f"salvar_edit_dk_{_ke}"):
                                        if edit_cmd_p:
                                            dados_j["decks"][nome_d] = {
                                                "comandante_primario": edit_cmd_p,
                                                "comandante_secundario": edit_cmd_s,
                                                "comandante_adicional": edit_cmd_a,
                                                "url": dados_dk_edit.get("url", "")
                                            }
                                            salvar_deck(jogador_real, nome_d, dados_j["decks"][nome_d])
                                            st.session_state[f"editando_deck_{nome_d}"] = False
                                            st.success(f"Deck '{nome_d}' atualizado!")
                                            st.rerun()
                                        else:
                                            st.error("Selecione pelo menos um comandante.")
                                with col_c:
                                    if st.button("Cancelar", key=f"cancelar_edit_dk_{_ke}"):
                                        st.session_state[f"editando_deck_{nome_d}"] = False
                                        st.rerun()

                        # Confirmação de exclusão inline
                        if pode_editar and st.session_state.get(f"confirmar_excluir_deck_{nome_d}", False):
                            st.warning(f"Tem certeza que deseja remover **{nome_d}**?")
                            col_sim, col_nao, _ = st.columns([1, 1, 4])
                            with col_sim:
                                if st.button("Sim, remover", type="primary", key=f"sim_excluir_dk_{nome_d}"):
                                    excluir_deck_db(jogador_real, nome_d)
                                    del dados_j["decks"][nome_d]
                                    del st.session_state[f"confirmar_excluir_deck_{nome_d}"]
                                    st.success(f"Deck '{nome_d}' removido!")
                                    st.rerun()
                            with col_nao:
                                if st.button("Cancelar", key=f"nao_excluir_dk_{nome_d}"):
                                    del st.session_state[f"confirmar_excluir_deck_{nome_d}"]
                                    st.rerun()

                        st.markdown("---")
                else:
                    st.info("Sem decks vinculados no momento.")

                # Cadastrar novo deck apenas para quem pode editar
                if pode_editar:
                    st.divider()
                    if "mostrar_form_deck" not in st.session_state:
                        st.session_state.mostrar_form_deck = False

                    if not st.session_state.mostrar_form_deck:
                        if st.button("CADASTRAR NOVO DECK"):
                            st.session_state.mostrar_form_deck = True
                            st.session_state.deck_precon_preview = None
                            st.session_state.deck_preview_context = None
                            st.session_state.busca_precon = ""
                            st.rerun()
                    else:
                        st.write("**Buscar Deck no Catálogo**")
                        catalogo = carregar_catalogo()
                        nomes_catalogo = [d["nome"] for d in catalogo]

                        busca = st.text_input(
                            "Digite o nome do deck (ou parte dele):",
                            value=st.session_state.busca_precon,
                            key="txt_busca_precon",
                            placeholder="Ex: Goblin, Dragon, Wilhelt..."
                        )
                        st.session_state.busca_precon = busca

                        if busca.strip():
                            termo = busca.strip().lower()
                            sugestoes = [
                                d["nome"] for d in catalogo
                                if termo in d["nome"].lower()
                                or any(termo in cmd.lower() for cmd in d.get("comandantes", []))
                            ]
                            if sugestoes:
                                st.markdown(f"*{len(sugestoes)} deck(s) encontrado(s):*")
                                for sug in sugestoes[:10]:
                                    if st.button(sug, key=f"sug_{sug}"):
                                        precon_completo = buscar_precon_por_nome(sug)
                                        st.session_state.deck_precon_preview = precon_completo
                                        st.session_state.deck_preview_context = "cadastro"
                                        st.rerun()
                            else:
                                st.info("Nenhum deck encontrado. Tente outro termo.")

                        if st.session_state.get("deck_preview_context") == "cadastro" and st.session_state.deck_precon_preview:
                            precon = st.session_state.deck_precon_preview
                            st.divider()
                            _pts_prev = precon.get("pontuacao_rank")
                            _media_pts_prev = calcular_media_pontuacao_catalogo()
                            if _pts_prev is not None:
                                _cor_prev = cor_pontuacao(_pts_prev, _media_pts_prev)
                                st.markdown(f'<span style="color:{_cor_prev}; font-weight:bold; font-size:14px;">★ {_pts_prev:.0f} pts</span>', unsafe_allow_html=True)
                            st.markdown(f"### {precon['nome']}")
                            cmds = precon.get("comandantes", [])
                            if cmds:
                                st.markdown(f"**Comandantes:** {' | '.join(cmds)}")
                            st.markdown(f"*{precon.get('set_nome', '')}*")

                            col_vincular, col_fechar = st.columns([1, 1])
                            with col_vincular:
                                if st.button("✔ Vincular este Deck ao Perfil", type="primary", key="btn_vincular_precon"):
                                    nome_deck = precon["nome"]
                                    cmds = precon.get("comandantes", [])
                                    cmd_p = cmds[0] if len(cmds) > 0 else "Desconhecido"
                                    cmd_s = cmds[1] if len(cmds) > 1 else cmd_p
                                    cmd_a = cmds[2] if len(cmds) > 2 else ""
                                    if nome_deck not in dados_j["decks"]:
                                        novo_deck = {
                                            "comandante_primario": cmd_p,
                                            "comandante_secundario": cmd_s,
                                            "comandante_adicional": cmd_a,
                                            "url": ""
                                        }
                                        dados_j["decks"][nome_deck] = novo_deck
                                        salvar_deck(jogador_real, nome_deck, novo_deck)
                                        st.session_state.deck_precon_preview = None
                                        st.session_state.deck_preview_context = None
                                        st.session_state.mostrar_form_deck = False
                                        st.session_state.busca_precon = ""
                                        st.success(f"Deck '{nome_deck}' vinculado com sucesso!")
                                        st.rerun()
                                    else:
                                        st.warning("Este deck já está vinculado ao seu perfil.")
                            with col_fechar:
                                if st.button("✖ Escolher outro deck", key="btn_cancelar_preview"):
                                    st.session_state.deck_precon_preview = None
                                    st.session_state.deck_preview_context = None
                                    st.rerun()

                            st.divider()
                            st.markdown("**Lista de Cartas:**")
                            _cmd_p_prev = precon.get("comandantes", [None])[0]
                            exibir_lista_cartas(precon.get("cartas", []), comandante_primario=_cmd_p_prev, nome_deck=precon.get("nome", ""))

                        if st.button("Cancelar", key="btn_cancelar_deck"):
                            st.session_state.mostrar_form_deck = False
                            st.session_state.deck_precon_preview = None
                            st.session_state.deck_preview_context = None
                            st.session_state.busca_precon = ""
                            st.rerun()
    else:
        st.info("Nenhum jogador cadastrado. Vá até a aba 'Cadastro' para começar.")

# ===================== DECKS =====================
elif aba == "Decks":

    decks_escolhidos = []
    nomes_decks_escolhidos = {}

    for nome_jog, dados_jog in st.session_state.jogadores.items():
        exibicao_jog = obter_nome_exibicao(dados_jog, nome_jog)
        for nome_dk, info_dk in dados_jog["decks"].items():
            cmd_str = f"1º: {info_dk['comandante_primario']}"
            if info_dk.get("comandante_secundario"):
                cmd_str += f" | 2º: {info_dk['comandante_secundario']}"
            if info_dk.get("comandante_adicional"):
                cmd_str += f" | 3º: {info_dk['comandante_adicional']}"
            decks_escolhidos.append({
                "Deck": nome_dk.upper(), "Comandantes": cmd_str,
                "Dono": exibicao_jog, "nome_real": nome_dk
            })
            if nome_dk not in nomes_decks_escolhidos:
                nomes_decks_escolhidos[nome_dk] = []
            nomes_decks_escolhidos[nome_dk].append(exibicao_jog)

    st.subheader("Decks Precons")
    catalogo = carregar_catalogo()
    if catalogo:
        # Remove versões Collector's Edition
        catalogo = [d for d in catalogo if "collector" not in d["nome"].lower()]

        # Ordenação
        col_ord, col_busca = st.columns([1, 2])
        with col_ord:
            ordenacao = st.selectbox(
                "Ordenar por:",
                ["Lançamento (mais novo)", "Lançamento (mais antigo)", "Alfabético (A-Z)", "Alfabético (Z-A)", "Pontuação (maior)", "Pontuação (menor)"],
                key="ord_catalogo"
            )
        with col_busca:
            busca_catalogo = st.text_input("Filtrar catálogo:", placeholder="Digite para filtrar...", key="filtro_catalogo")

        if ordenacao == "Lançamento (mais novo)":
            catalogo = sorted(catalogo, key=lambda d: d.get("data_lancamento", ""), reverse=True)
        elif ordenacao == "Lançamento (mais antigo)":
            catalogo = sorted(catalogo, key=lambda d: d.get("data_lancamento", ""))
        elif ordenacao == "Alfabético (A-Z)":
            catalogo = sorted(catalogo, key=lambda d: d["nome"])
        elif ordenacao == "Alfabético (Z-A)":
            catalogo = sorted(catalogo, key=lambda d: d["nome"], reverse=True)
        elif ordenacao == "Pontuação (maior)":
            catalogo = sorted(catalogo, key=lambda d: d.get("pontuacao_rank") if d.get("pontuacao_rank") is not None else -9999, reverse=True)
        elif ordenacao == "Pontuação (menor)":
            catalogo = sorted(catalogo, key=lambda d: d.get("pontuacao_rank") if d.get("pontuacao_rank") is not None else 9999)
        catalogo_filtrado = catalogo
        if busca_catalogo.strip():
            catalogo_filtrado = [d for d in catalogo if busca_catalogo.strip().lower() in d["nome"].lower()]
        st.markdown(f"*{len(catalogo_filtrado)} deck(s) no catálogo*")

        for deck_cat in catalogo_filtrado:
            nome_cat = deck_cat["nome"]
            cmds_cat = deck_cat.get("comandantes", [])
            donos = nomes_decks_escolhidos.get(nome_cat, [])
            pts_cat = deck_cat.get("pontuacao_rank")
            media_pts_cat = calcular_media_pontuacao_catalogo()
            if donos:
                label_expander = f"{nome_cat.upper()} — ⚠️ Já escolhido por: {', '.join(donos)}"
            else:
                label_expander = f"{nome_cat.upper()}"
            with st.expander(label_expander):
                # Badge de pontuação colorido
                if pts_cat is not None:
                    cor = cor_pontuacao(pts_cat, media_pts_cat)
                    st.markdown(f'<span style="color:{cor}; font-weight:bold; font-size:14px;">★ {pts_cat:.0f} pts</span>', unsafe_allow_html=True)
                if cmds_cat:
                    st.markdown(f"**Comandantes:** {' | '.join(cmds_cat)}")
                st.markdown(f"*{deck_cat.get('set_nome', '')}*")
                if donos:
                    st.warning(f"Este deck já foi escolhido por: **{', '.join(donos)}**. Você ainda pode vinculá-lo, mas considere escolher um diferente!")

                # Verifica se jogador logado tem perfil e se já tem este deck
                jogador_logado_nome = next(
                    (n for n, d in st.session_state.jogadores.items() if d["email"] == usuario_email),
                    None
                )
                ja_tem_deck = jogador_logado_nome and nome_cat in st.session_state.jogadores.get(jogador_logado_nome, {}).get("decks", {})

                col_ver_cat, col_vincular_cat = st.columns([1, 1])
                with col_ver_cat:
                    if st.button("Ver Lista de Cartas", key=f"ver_cat_{nome_cat}"):
                        precon_full = buscar_precon_por_nome(nome_cat)
                        if precon_full:
                            st.session_state.deck_precon_preview = precon_full
                            st.session_state.deck_preview_context = f"catalogo_{nome_cat}"
                        else:
                            st.warning("Lista não encontrada.")
                with col_vincular_cat:
                    if ja_tem_deck:
                        st.info("Já vinculado ao seu perfil")
                    elif jogador_logado_nome:
                        if st.button("Vincular ao meu perfil", key=f"vincular_cat_{nome_cat}"):
                            cmds = deck_cat.get("comandantes", [])
                            cmd_p = cmds[0] if len(cmds) > 0 else "Desconhecido"
                            cmd_s = cmds[1] if len(cmds) > 1 else ""
                            cmd_a = cmds[2] if len(cmds) > 2 else ""
                            novo_deck = {
                                "comandante_primario": cmd_p,
                                "comandante_secundario": cmd_s,
                                "comandante_adicional": cmd_a,
                                "url": ""
                            }
                            st.session_state.jogadores[jogador_logado_nome]["decks"][nome_cat] = novo_deck
                            salvar_deck(jogador_logado_nome, nome_cat, novo_deck)
                            st.success(f"Deck '{nome_cat}' vinculado ao seu perfil!")
                            st.rerun()

                ctx_cat = f"catalogo_{nome_cat}"
                if st.session_state.get("deck_preview_context") == ctx_cat and st.session_state.deck_precon_preview:
                    precon = st.session_state.deck_precon_preview
                    st.divider()
                    _cmd_p_cat = precon.get("comandantes", [None])[0]
                    exibir_lista_cartas(precon.get("cartas", []), comandante_primario=_cmd_p_cat, nome_deck=nome_cat)
                    if st.button("Fechar Lista", key=f"fechar_cat_{nome_cat}"):
                        st.session_state.deck_precon_preview = None
                        st.session_state.deck_preview_context = None
                        st.rerun()
    else:
        st.info("Catálogo de precons não encontrado.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
<div style='text-align:center; color:#444; font-size:12px; border-top:1px solid #333; padding-top:12px;'>
    Listas de decks fornecidas pelo repositório público
    <a href='https://github.com/taw/magic-preconstructed-decks-data' target='_blank' style='color:#555;'>magic-preconstructed-decks-data</a>,
    mantido por <strong>taw</strong>. Imagens das cartas via
    <a href='https://scryfall.com' target='_blank' style='color:#555;'>Scryfall</a>.
    Magic: The Gathering é propriedade da Wizards of the Coast LLC.
</div>
""", unsafe_allow_html=True)

# ===================== NOVA PARTIDA =====================
elif aba == "Nova Partida":
    st.header("Registrar Nova Partida")

    if st.session_state.mensagem_sucesso_partida:
        st.success(st.session_state.mensagem_sucesso_partida)
        st.session_state.mensagem_sucesso_partida = None

    jogadores_com_deck = [j for j, dados in st.session_state.jogadores.items() if len(dados["decks"]) > 0]

    if len(jogadores_com_deck) < 2:
        st.warning("Certifique-se de que pelo menos 2 jogadores possuem decks no arsenal para registrar partidas.")
    else:
        mapa_exib_para_real = {obter_nome_exibicao(st.session_state.jogadores[j], j): j for j in jogadores_com_deck}
        lista_nomes_disponiveis = ["Selecione..."] + list(mapa_exib_para_real.keys())

        OPCAO_CONVIDADO = "➕ Usuário Não Cadastrado"
        catalogo_global = carregar_catalogo()
        mapa_cmd_multideck_catalogo, mapa_deck_cmds_catalogo = construir_mapa_comandantes_catalogo(catalogo_global)

        def _eh_participante_valido(nome):
            return nome != "Selecione..." and (nome in mapa_exib_para_real or nome.endswith(" *"))

        def _resolver_deck_ambiguo(opcoes_decks, key_prefix, label="Este comandante aparece em mais de um deck. Qual usar?"):
            """Se o comandante escolhido pertence a mais de um deck, pede pra escolher qual.
            Se só houver um, retorna direto sem exibir seletor extra."""
            if len(opcoes_decks) <= 1:
                return opcoes_decks[0] if opcoes_decks else "Selecione..."
            escolha = st.selectbox(label, ["Selecione..."] + opcoes_decks, key=f"{key_prefix}_deck_amb")
            return escolha

        def _campo_convidado(key_prefix):
            """Renderiza o fluxo de seleção de nome + comandante + deck para um convidado
            não cadastrado. Retorna (nome_final, deck_escolhido, cmd_escolhido)."""
            nome_conv = st.text_input("Nome do convidado:", key=f"{key_prefix}_conv_nome", placeholder="Digite o nome")
            deck_escolhido = "Selecione..."
            cmd_escolhido = "Selecione..."
            nome_final = "Selecione..."
            if nome_conv.strip():
                nome_final = f"{nome_conv.strip()} *"
                cmd_direto = st.selectbox(
                    "Comandante do convidado:",
                    ["Selecione..."] + sorted(mapa_cmd_multideck_catalogo.keys()),
                    key=f"{key_prefix}_conv_cmd"
                )
                if cmd_direto != "Selecione...":
                    decks_possiveis = mapa_cmd_multideck_catalogo.get(cmd_direto, [])
                    deck_escolhido = _resolver_deck_ambiguo(decks_possiveis, f"{key_prefix}_conv")
                    if deck_escolhido != "Selecione...":
                        cmd_escolhido = cmd_direto
                        st.caption(f"Deck: **{deck_escolhido}**")
                        opcoes_cmd = mapa_deck_cmds_catalogo.get(deck_escolhido, [])
                        if len(opcoes_cmd) > 1:
                            cmd_sel = st.multiselect(
                                "Partners adicionais (opcional):",
                                [c for c in opcoes_cmd if c != cmd_direto],
                                default=[],
                                key=f"{key_prefix}_conv_c"
                            )
                            if cmd_sel:
                                cmd_escolhido = " + ".join([cmd_direto] + cmd_sel)
            else:
                st.caption("Digite o nome para liberar a escolha do comandante.")
            return nome_final, deck_escolhido, cmd_escolhido



        MODO_DUPLAS = "DUEL COMMANDER / DRAGÃO DE DUAS CABEÇAS"
        MODO_PENTAGRAMA = "PENTAGRAMA"

        local_partida = st.selectbox("Local da Partida:", ["PRESENCIAL", "SPELLTABLE"], key="sel_local")
        modo_partida = st.selectbox("Modo de Jogo:", ["SOLO", MODO_DUPLAS, MODO_PENTAGRAMA], key="sel_modo")

        if modo_partida == MODO_DUPLAS:
            qtd_duplas = st.selectbox("Quantidade de Duplas:", [2, 3, 4], index=0, key="sel_qtd_duplas")
            qtd_jogadores = qtd_duplas * 2
            st.info(f"Modo Duel Commander / Dragão de Duas Cabeças: {qtd_duplas} duplas ({qtd_jogadores} jogadores).")
        elif modo_partida == MODO_PENTAGRAMA:
            qtd_jogadores = 5
            st.info("Modo Pentagrama fixado em 5 jogadores.")
        else:
            qtd_jogadores = st.selectbox("Quantidade de Jogadores:", [2, 3, 4, 5, 6, 7, 8], index=2, key="sel_qtd_jog")

        st.divider()
        st.subheader("Configuração dos Integrantes da Mesa")

        if modo_partida == MODO_DUPLAS:
            letras_duplas = ["A", "B", "C", "D"]
            duplas_config = {}
            colunas_duplas = st.columns(qtd_duplas)
            todos_j_selecionados = []

            for d_idx in range(qtd_duplas):
                with colunas_duplas[d_idx]:
                    st.markdown(f"### DUPLA {letras_duplas[d_idx]}")
                    dupla_jogadores = []
                    for p_idx in range(2):
                        num_j = d_idx * 2 + p_idx + 1
                        opcoes_j = ["Selecione...", OPCAO_CONVIDADO] + [n for n in list(mapa_exib_para_real.keys()) if n not in todos_j_selecionados]
                        jog = st.selectbox(f"Jogador {p_idx+1}:", opcoes_j, key=f"dupla_j_{d_idx}_{p_idx}")
                        dk = "Selecione..."
                        cmd = "Selecione..."
                        jog_final = jog
                        if jog == OPCAO_CONVIDADO:
                            jog_final, dk, cmd = _campo_convidado(f"dupla_{d_idx}_{p_idx}")
                        elif jog in mapa_exib_para_real:
                            todos_j_selecionados.append(jog)
                            real_key = mapa_exib_para_real[jog]
                            decks_jog = st.session_state.jogadores[real_key]["decks"]
                            # Seleção por comandante primeiro
                            mapa_cmd_dk = {}
                            for dk_n, dk_i in decks_jog.items():
                                for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                    if c:
                                        mapa_cmd_dk.setdefault(c, [])
                                        if dk_n not in mapa_cmd_dk[c]:
                                            mapa_cmd_dk[c].append(dk_n)
                            cmd_direto = st.selectbox(f"Comandante (J{num_j}):", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"dupla_cmd_{d_idx}_{p_idx}")
                            if cmd_direto != "Selecione...":
                                dk = _resolver_deck_ambiguo(mapa_cmd_dk[cmd_direto], f"dupla_{d_idx}_{p_idx}_dk")
                                if dk != "Selecione...":
                                    cmd = cmd_direto
                                    st.caption(f"Deck: **{dk}**")
                            else:
                                dk = st.selectbox(f"Ou Deck (J{num_j}):", ["Selecione..."] + list(decks_jog.keys()), key=f"dupla_dk_{d_idx}_{p_idx}")
                                if dk != "Selecione...":
                                    dk_obj = decks_jog[dk]
                                    opcoes_cmd = [c for c in [dk_obj.get("comandante_primario",""), dk_obj.get("comandante_secundario",""), dk_obj.get("comandante_adicional","")] if c]
                                    if len(opcoes_cmd) > 1:
                                        cmd_sel = st.multiselect(f"Comandante(s) (J{num_j}):", opcoes_cmd, default=[opcoes_cmd[0]], key=f"dupla_cmd2_{d_idx}_{p_idx}")
                                        cmd = " + ".join(cmd_sel) if cmd_sel else "Selecione..."
                                    else:
                                        cmd = opcoes_cmd[0] if opcoes_cmd else "Selecione..."
                        dupla_jogadores.append({"Jogador": jog_final, "Deck": dk, "Comandante": cmd})
                    duplas_config[letras_duplas[d_idx]] = dupla_jogadores

            # Verifica se todos estão preenchidos
            todos_validos = all(
                _eh_participante_valido(p["Jogador"]) and p["Deck"] != "Selecione..." and p["Comandante"] != "Selecione..."
                for dupla in duplas_config.values() for p in dupla
            )

            if todos_validos:
                st.divider()
                st.subheader("Resultado do Confronto de Duplas")
                letras_disponiveis = [letras_duplas[i] for i in range(qtd_duplas)]
                vencedor_dupla = st.radio("Qual dupla venceu?", [f"DUPLA {l}" for l in letras_disponiveis], key="rad_vencedor_dupla")
                letra_vencedora = vencedor_dupla.replace("DUPLA ", "")
                pts_vencedor = 400 if local_partida == "PRESENCIAL" else 200
                pts_perdedor = 200 if local_partida == "PRESENCIAL" else 100

                if st.button("Gravar Resultado das Duplas", key="btn_salvar_duplas"):
                    detalhes = []
                    for letra, jogadores_dupla in duplas_config.items():
                        venceu = letra == letra_vencedora
                        for p in jogadores_dupla:
                            detalhes.append({
                                "Jogador": p["Jogador"],
                                "Deck": f"{p['Deck']} ({p['Comandante']})",
                                "Pontos": pts_vencedor if venceu else pts_perdedor,
                                "Vencedor": venceu
                            })
                    novo_id = salvar_partida(local_partida, modo_partida, qtd_jogadores, detalhes)
                    nova_linha = pd.DataFrame([{"ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": qtd_jogadores, "Detalhes_Pontuacao": detalhes}])
                    st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                    st.session_state.mensagem_sucesso_partida = "Resultado de duplas gravado com sucesso!"
                    st.rerun()
            else:
                st.info("Aguardando a seleção de todos os integrantes, decks e comandantes para liberar a gravação...")

        elif modo_partida == MODO_PENTAGRAMA:
            selecionados_nomes = []
            colunas_ae = st.columns(5)
            dados_ae = []
            for i in range(5):
                with colunas_ae[i]:
                    st.markdown(f"#### Posição {i+1}")
                    if i == 0:
                        st.markdown("*Pentagrama*")
                    opcoes_filtradas = ["Selecione...", OPCAO_CONVIDADO] + [n for n in list(mapa_exib_para_real.keys()) if n not in selecionados_nomes]
                    jog_escolhido = st.selectbox(f"Jogador {i+1}:", opcoes_filtradas, key=f"ae_j_{i}")
                    deck_escolhido = "Selecione..."
                    cmd_escolhido = "Selecione..."
                    jog_final = jog_escolhido
                    if jog_escolhido == OPCAO_CONVIDADO:
                        jog_final, deck_escolhido, cmd_escolhido = _campo_convidado(f"ae_{i}")
                    elif jog_escolhido in mapa_exib_para_real:
                        selecionados_nomes.append(jog_escolhido)
                        real_key = mapa_exib_para_real[jog_escolhido]
                        decks_jog = st.session_state.jogadores[real_key]["decks"]
                        mapa_cmd_dk = {}
                        for dk_n, dk_i in decks_jog.items():
                            for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                if c:
                                    mapa_cmd_dk.setdefault(c, [])
                                    if dk_n not in mapa_cmd_dk[c]:
                                        mapa_cmd_dk[c].append(dk_n)
                        cmd_direto = st.selectbox(f"Comandante:", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"ae_cmd_{i}")
                        if cmd_direto != "Selecione...":
                            deck_escolhido = _resolver_deck_ambiguo(mapa_cmd_dk[cmd_direto], f"ae_{i}_dk")
                            if deck_escolhido != "Selecione...":
                                cmd_escolhido = cmd_direto
                                st.caption(f"Deck: **{deck_escolhido}**")
                        else:
                            deck_escolhido = st.selectbox(f"Ou Deck:", ["Selecione..."] + list(decks_jog.keys()), key=f"ae_dk_{i}")
                            if deck_escolhido != "Selecione...":
                                dk_obj = decks_jog[deck_escolhido]
                                opcoes_cmd = [c for c in [dk_obj.get("comandante_primario",""), dk_obj.get("comandante_secundario",""), dk_obj.get("comandante_adicional","")] if c]
                                if len(opcoes_cmd) > 1:
                                    cmd_sel = st.multiselect(f"Comandante(s):", opcoes_cmd, default=[opcoes_cmd[0]], key=f"ae_cmd2_{i}")
                                    cmd_escolhido = " + ".join(cmd_sel) if cmd_sel else "Selecione..."
                                else:
                                    cmd_escolhido = opcoes_cmd[0] if opcoes_cmd else "Selecione..."
                    dados_ae.append({"Jogador": jog_final, "Deck": deck_escolhido, "Comandante": cmd_escolhido})

            validos_ae = [d for d in dados_ae if _eh_participante_valido(d["Jogador"]) and d["Deck"] != "Selecione..." and d["Comandante"] != "Selecione..."]

            if len(validos_ae) == 5:
                st.divider()
                st.subheader("Classificação Final — Pentagrama")
                coloca_ordem_ae = []
                nomes_ae = [d["Jogador"] for d in validos_ae]
                for pos in range(5):
                    opcoes_pos = ["Selecione..."] + [n for n in nomes_ae if n not in coloca_ordem_ae]
                    txt_label = "1º Lugar (Vencedor):" if pos == 0 else f"{pos+1}º Lugar:"
                    escolha = st.selectbox(txt_label, opcoes_pos, key=f"ae_pos_{pos}")
                    if escolha in nomes_ae:
                        coloca_ordem_ae.append(escolha)

                if len(coloca_ordem_ae) == 5:
                    if st.button("Gravar Resultado Pentagrama", key="btn_salvar_ae"):
                        tabela_ae = {
                            "PRESENCIAL": [200, 100, 100, 50, 50],
                            "SPELLTABLE": [100, 50, 50, 0, 0]
                        }
                        detalhes_ae = []
                        for pos_idx, jog_nome in enumerate(coloca_ordem_ae):
                            cfg = next(d for d in validos_ae if d["Jogador"] == jog_nome)
                            detalhes_ae.append({
                                "Jogador": jog_nome,
                                "Deck": f"{cfg['Deck']} ({cfg['Comandante']})",
                                "Pontos": tabela_ae[local_partida][pos_idx],
                                "Vencedor": pos_idx == 0
                            })
                        novo_id = salvar_partida(local_partida, modo_partida, 5, detalhes_ae)
                        nova_linha = pd.DataFrame([{"ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": 5, "Detalhes_Pontuacao": detalhes_ae}])
                        st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                        for i in range(5):
                            for k in [f"ae_j_{i}", f"ae_cmd_{i}", f"ae_dk_{i}", f"ae_cmd2_{i}", f"ae_pos_{i}", f"ae_{i}_conv_nome", f"ae_{i}_conv_cmd", f"ae_{i}_conv_c", f"ae_{i}_conv_deck_amb", f"ae_{i}_dk_deck_amb"]:
                                if k in st.session_state: del st.session_state[k]
                        st.session_state.mensagem_sucesso_partida = "Resultado Pentagrama gravado com sucesso!"
                        st.rerun()
            else:
                st.info("Aguardando a seleção de todos os 5 jogadores, decks e comandantes para liberar a classificação...")

        else:
            selecionados_nomes = []
            colunas_jogadores = st.columns(qtd_jogadores)
            dados_confronto = []
            for i in range(qtd_jogadores):
                with colunas_jogadores[i]:
                    st.markdown(f"#### Posição {i+1}")
                    opcoes_filtradas = ["Selecione...", OPCAO_CONVIDADO] + [n for n in list(mapa_exib_para_real.keys()) if n not in selecionados_nomes]
                    jog_escolhido = st.selectbox(f"Jogador {i+1}:", opcoes_filtradas, key=f"solo_j_{i}")
                    deck_escolhido = "Selecione..."
                    cmd_escolhido = "Selecione..."
                    jog_final = jog_escolhido
                    if jog_escolhido == OPCAO_CONVIDADO:
                        jog_final, deck_escolhido, cmd_escolhido = _campo_convidado(f"solo_{i}")
                    elif jog_escolhido in mapa_exib_para_real:
                        selecionados_nomes.append(jog_escolhido)
                        real_key = mapa_exib_para_real[jog_escolhido]
                        decks_jog = st.session_state.jogadores[real_key]["decks"]
                        mapa_cmd_dk = {}
                        for dk_n, dk_i in decks_jog.items():
                            for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                if c:
                                    mapa_cmd_dk.setdefault(c, [])
                                    if dk_n not in mapa_cmd_dk[c]:
                                        mapa_cmd_dk[c].append(dk_n)
                        cmd_direto = st.selectbox(f"Comandante do Jogador {i+1}:", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"solo_cmd_direto_{i}")
                        if cmd_direto != "Selecione...":
                            deck_escolhido = _resolver_deck_ambiguo(mapa_cmd_dk.get(cmd_direto, []), f"solo_{i}_dk")
                            if deck_escolhido != "Selecione...":
                                cmd_escolhido = cmd_direto
                                st.caption(f"Deck: **{deck_escolhido}**")
                                dk_obj = decks_jog.get(deck_escolhido, {})
                                opcoes_cmd = [c for c in [dk_obj.get("comandante_primario",""), dk_obj.get("comandante_secundario",""), dk_obj.get("comandante_adicional","")] if c]
                                if len(opcoes_cmd) > 1:
                                    cmd_sel = st.multiselect("Partners adicionais (opcional):", [c for c in opcoes_cmd if c != cmd_direto], default=[], key=f"solo_c_{i}")
                                    if cmd_sel:
                                        cmd_escolhido = " + ".join([cmd_direto] + cmd_sel)
                        else:
                            deck_escolhido = st.selectbox(f"Ou escolha pelo Deck:", ["Selecione..."] + list(decks_jog.keys()), key=f"solo_d_{i}")
                            if deck_escolhido != "Selecione...":
                                dk_obj = decks_jog[deck_escolhido]
                                opcoes_cmd = [c for c in [dk_obj.get("comandante_primario",""), dk_obj.get("comandante_secundario",""), dk_obj.get("comandante_adicional","")] if c]
                                if len(opcoes_cmd) > 1:
                                    cmd_sel = st.multiselect(f"Comandante(s) do Jogador {i+1}:", opcoes_cmd, default=[opcoes_cmd[0]], key=f"solo_c_{i}")
                                    cmd_escolhido = " + ".join(cmd_sel) if cmd_sel else "Selecione..."
                                else:
                                    cmd_escolhido = opcoes_cmd[0] if opcoes_cmd else "Selecione..."
                    dados_confronto.append({"Jogador": jog_final, "Deck": deck_escolhido, "Comandante": cmd_escolhido})

            validos = [d for d in dados_confronto if _eh_participante_valido(d["Jogador"]) and d["Deck"] != "Selecione..." and d["Comandante"] != "Selecione..."]
            if len(validos) == qtd_jogadores:
                st.divider()
                st.subheader("Classificação Final da Partida Solo")
                coloca_ordem = []
                nomes_na_mesa = [d["Jogador"] for d in validos]
                for pos in range(qtd_jogadores):
                    opcoes_pos = ["Selecione..."] + [n for n in nomes_na_mesa if n not in coloca_ordem]
                    txt_label = "1º Lugar (Campeão):" if pos == 0 else f"{pos+1}º Lugar:"
                    escolha_colocacao = st.selectbox(txt_label, opcoes_pos, key=f"colocacao_pos_{pos}")
                    if escolha_colocacao in nomes_na_mesa:
                        coloca_ordem.append(escolha_colocacao)
                if len(coloca_ordem) == qtd_jogadores:
                    if st.button("Gravar Resultado Solo", key="btn_salvar_solo"):
                        tabela_pontos = {
                            "PRESENCIAL": {8:[400,350,300,250,200,150,100,50], 7:[400,350,300,250,200,150,100], 6:[400,350,300,250,200,150], 5:[400,300,200,100,50], 4:[400,300,200,100], 3:[200,100,50], 2:[100,50]},
                            "SPELLTABLE": {8:[300,250,200,150,100,75,50,25], 7:[300,250,200,150,100,75,50], 6:[300,250,200,150,100,75], 5:[300,200,100,50,25], 4:[200,100,50,25], 3:[100,50,20], 2:[50,25]}
                        }
                        detalhes_finais = []
                        for posicao_index, jog_nome in enumerate(coloca_ordem):
                            config_mesa = next(d for d in validos if d["Jogador"] == jog_nome)
                            pontos_obtidos = tabela_pontos[local_partida][qtd_jogadores][posicao_index]
                            nome_deck_completo = f"{config_mesa['Deck']} ({config_mesa['Comandante']})"
                            detalhes_finais.append({"Jogador": jog_nome, "Deck": nome_deck_completo, "Pontos": pontos_obtidos, "Vencedor": posicao_index == 0})
                        novo_id = salvar_partida(local_partida, modo_partida, qtd_jogadores, detalhes_finais)
                        nova_linha = pd.DataFrame([{"ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": qtd_jogadores, "Detalhes_Pontuacao": detalhes_finais}])
                        st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                        for i in range(qtd_jogadores):
                            for key in [f"solo_j_{i}", f"solo_d_{i}", f"solo_c_{i}", f"solo_cmd_direto_{i}", f"solo_{i}_conv_nome", f"solo_{i}_conv_cmd", f"solo_{i}_conv_c", f"solo_{i}_conv_deck_amb", f"solo_{i}_dk_deck_amb"]:
                                if key in st.session_state: del st.session_state[key]
                        for pos in range(qtd_jogadores):
                            if f"colocacao_pos_{pos}" in st.session_state: del st.session_state[f"colocacao_pos_{pos}"]
                        st.session_state.mensagem_sucesso_partida = "Resultado Solo gravado com sucesso!"
                        st.rerun()
            else:
                st.info("Aguardando a seleção de todos os competidores, decks e comandantes ativos para liberar a classificação...")

# ===================== STATISTICS =====================
elif aba == "Statistics":
    st.header("Classificação e Estatísticas")
    if not st.session_state.partidas.empty:
        MODO_DUPLAS = "DUEL COMMANDER / DRAGÃO DE DUAS CABEÇAS"
        MODO_PENTAGRAMA = "PENTAGRAMA"
        # Compatibilidade com partidas antigas gravadas antes da renomeação dos modos
        ALIASES_MODO = {
            MODO_DUPLAS: [MODO_DUPLAS, "DRAGÃO DE DUAS CABEÇAS"],
            MODO_PENTAGRAMA: [MODO_PENTAGRAMA, "ARCH ENEMY"],
        }

        st.subheader("Filtros de Classificação")
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_local = st.selectbox("Local:", ["TODOS", "PRESENCIAL", "SPELLTABLE"])
        with c2: f_modo = st.selectbox("Modo:", ["TODOS", "SOLO", MODO_DUPLAS, MODO_PENTAGRAMA])
        with c3: f_tipo = st.selectbox("Ranking por:", ["Competidor", "Deck", "Comandante"])
        with c4: f_metrica = st.selectbox("Métrica:", ["Pontuação", "Vitórias"])

        df = st.session_state.partidas.copy()
        if f_local != "TODOS": df = df[df["Local"] == f_local]
        if f_modo != "TODOS": df = df[df["Modo"].isin(ALIASES_MODO.get(f_modo, [f_modo]))]

        if not df.empty:
            dados_rank = []
            for _, row in df.iterrows():
                for item in row["Detalhes_Pontuacao"]:
                    deck_raw = item.get("Deck", "Desconhecido")
                    nome_jogador = item.get("Jogador", "Jogador Removido")
                    if " (" in deck_raw:
                        deck_nome = deck_raw.split(" (")[0]
                        cmd_nome = deck_raw.split(" (")[1].replace(")", "")
                    else:
                        deck_nome = deck_raw
                        cmd_nome = "Desconhecido"
                    dados_rank.append({
                        "Competidor": nome_jogador,
                        "Deck": deck_nome,
                        "Comandante": cmd_nome,
                        "Pontos": item.get("Pontos", 0),
                        "Vitórias": 1 if item.get("Vencedor", False) else 0
                    })

            df_rank = pd.DataFrame(dados_rank)
            coluna_escolhida = f_tipo
            metrica_col = "Pontos" if f_metrica == "Pontuação" else "Vitórias"
            df_final = df_rank.groupby(coluna_escolhida)[metrica_col].sum().reset_index().sort_values(metrica_col, ascending=False)

            import plotly.express as px
            st.divider()
            fig = px.bar(
                df_final, x=coluna_escolhida, y=metrica_col, color=metrica_col,
                color_continuous_scale="Viridis",
                title=f"Ranking: {f_tipo} | {f_metrica} (Modo: {f_modo} | Local: {f_local})"
            )
            fig.update_layout(xaxis={"categoryorder": "total descending"})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma partida encontrada com estes filtros.")

        st.divider()
        st.subheader("Histórico de Partidas")

        # Menu suspenso único para selecionar partida
        opcoes_partidas = {
            f"Partida #{row['ID']} | {row['Local']} | {row['Modo']}": row['ID']
            for _, row in st.session_state.partidas.iterrows()
        }
        partida_sel_label = st.selectbox(
            "Selecione uma partida para visualizar:",
            ["Selecione..."] + list(opcoes_partidas.keys()),
            key="sel_historico_partida"
        )

        if partida_sel_label != "Selecione...":
            partida_id_sel = opcoes_partidas[partida_sel_label]
            row = st.session_state.partidas[st.session_state.partidas["ID"] == partida_id_sel].iloc[0]

            with st.container():
                col_a, col_b, col_c = st.columns(3)
                vencedores = [i["Jogador"] for i in row["Detalhes_Pontuacao"] if i["Vencedor"]]
                col_a.metric("ID", row["ID"])
                col_b.metric("Formato", row["Modo"])
                col_c.metric("Vencedor(es)", ", ".join(vencedores))
                st.write("**Detalhes da Mesa:**")
                df_detalhe = pd.DataFrame(row["Detalhes_Pontuacao"])
                st.table(df_detalhe[["Jogador", "Deck", "Pontos"]])

                if is_admin:
                    col_btn_editar, col_btn_excluir, _ = st.columns([1, 1, 2])
                    with col_btn_editar:
                        if st.button(f"Editar Comandantes", key=f"edit_{row['ID']}"):
                            st.session_state[f"editando_partida_{row['ID']}"] = True
                            st.rerun()
                    with col_btn_excluir:
                        if st.button(f"Excluir Partida #{row['ID']}", key=f"del_{row['ID']}"):
                            st.session_state[f"confirmar_excluir_partida_{row['ID']}"] = True
                            st.rerun()

                    # Formulário de edição de comandantes
                    if st.session_state.get(f"editando_partida_{row['ID']}", False):
                        st.markdown("**Editar Comandantes da Partida:**")
                        detalhes_editados = list(row["Detalhes_Pontuacao"])
                        novos_comandantes = {}
                        for idx, item in enumerate(detalhes_editados):
                            deck_raw = item.get("Deck", "")
                            deck_nome = deck_raw.split(" (")[0] if " (" in deck_raw else deck_raw
                            cmd_atual = deck_raw.split(" (")[1].replace(")", "") if " (" in deck_raw else ""
                            # Busca lendárias do deck para o multiselect
                            precon_rank = buscar_precon_por_nome(deck_nome)
                            lendarias_rank = []
                            if precon_rank:
                                lendarias_rank = [
                                    c["nome"] for c in precon_rank.get("cartas", [])
                                    if "legendary" in c.get("type_line", "").lower()
                                ]
                            if lendarias_rank:
                                # Defaults: comandantes já salvos (podem ser "A + B")
                                cmds_atuais = [c.strip() for c in cmd_atual.split("+") if c.strip() in lendarias_rank]
                                if not cmds_atuais and lendarias_rank:
                                    cmds_atuais = [lendarias_rank[0]]
                                sel = st.multiselect(
                                    f"{item['Jogador']} — {deck_nome}",
                                    lendarias_rank,
                                    default=cmds_atuais,
                                    max_selections=3,
                                    key=f"edit_cmd_{row['ID']}_{idx}"
                                )
                                novos_comandantes[idx] = " + ".join(sel) if sel else cmd_atual
                            else:
                                novo_cmd = st.text_input(
                                    f"{item['Jogador']} — {deck_nome}",
                                    value=cmd_atual,
                                    key=f"edit_cmd_{row['ID']}_{idx}"
                                )
                                novos_comandantes[idx] = novo_cmd

                        col_salvar, col_cancelar, _ = st.columns([1, 1, 4])
                        with col_salvar:
                            if st.button("Salvar", type="primary", key=f"salvar_edit_{row['ID']}"):
                                for idx, item in enumerate(detalhes_editados):
                                    deck_raw = item.get("Deck", "")
                                    deck_nome = deck_raw.split(" (")[0] if " (" in deck_raw else deck_raw
                                    novo_cmd = novos_comandantes[idx]
                                    detalhes_editados[idx]["Deck"] = f"{deck_nome} ({novo_cmd})" if novo_cmd else deck_nome
                                sb.table("partidas").update({"detalhes": detalhes_editados}).eq("id", int(row["ID"])).execute()
                                st.session_state.dados_carregados = False
                                del st.session_state[f"editando_partida_{row['ID']}"]
                                st.success("Comandantes atualizados!")
                                st.rerun()
                        with col_cancelar:
                            if st.button("Cancelar", key=f"cancelar_edit_{row['ID']}"):
                                del st.session_state[f"editando_partida_{row['ID']}"]
                                st.rerun()

                    if st.session_state.get(f"confirmar_excluir_partida_{row['ID']}", False):
                        st.warning(f"Tem certeza que deseja excluir a Partida #{row['ID']}?")
                        col_sim, col_nao, _ = st.columns([1, 1, 4])
                        with col_sim:
                            if st.button("Sim, excluir", type="primary", key=f"sim_del_{row['ID']}"):
                                excluir_partida_db(row["ID"])
                                st.session_state.partidas = st.session_state.partidas[st.session_state.partidas["ID"] != row["ID"]]
                                del st.session_state[f"confirmar_excluir_partida_{row['ID']}"]
                                st.rerun()
                        with col_nao:
                            if st.button("Cancelar", key=f"nao_del_{row['ID']}"):
                                del st.session_state[f"confirmar_excluir_partida_{row['ID']}"]
                                st.rerun()
    else:
        st.info("Nenhuma partida registrada nesta temporada da liga ainda.")


# ===================== TORNEIOS =====================
elif aba == "Torneios":
    st.header("Torneios — Mesas de 4 (Suíço + Mata-mata)")

    torneios_existentes = carregar_torneios()
    opcoes_torneio = ["➕ Criar Novo Torneio"] + [f"#{t['id']} {t['nome']} ({t['status']})" for t in torneios_existentes]
    torneio_sel_label = st.selectbox("Torneio:", opcoes_torneio, key="torneio_selecionado")

    if torneio_sel_label == "➕ Criar Novo Torneio":
        st.subheader("Criar Novo Torneio")
        st.caption("Todos os confrontos são mesas de 4 jogadores, cada um por si. Vitória = 3 pontos. Eliminações contam só como critério de desempate.")
        with st.form("form_criar_torneio"):
            nome_torneio = st.text_input("Nome do Torneio:")
            modo_jogo_torneio = st.text_input("Rótulo do Modo de Jogo:", value="SOLO (mesas de 4)")
            qtd_classificados_novo = st.selectbox(
                "Classificados para o Mata-Mata:",
                [4, 8, 16, 32],
                index=1,
                help="Depende de quantos jogadores vão se inscrever. 4 = final direta · 8 = semifinal · 16 = quartas · 32 = oitavas."
            )
            criar_btn = st.form_submit_button("Criar Torneio", type="primary")
            if criar_btn:
                if not nome_torneio.strip():
                    st.error("Dê um nome ao torneio.")
                else:
                    criar_torneio(nome_torneio.strip(), modo_jogo_torneio.strip(), int(qtd_classificados_novo), st.session_state.usuario_email)
                    st.success(f"Torneio '{nome_torneio}' criado! Selecione-o na lista acima para adicionar participantes.")
                    st.rerun()
    else:
        torneio_id = int(torneio_sel_label.split(" ")[0].replace("#", ""))
        torneio = next((t for t in torneios_existentes if t["id"] == torneio_id), None)
        if not torneio:
            st.error("Torneio não encontrado.")
        else:
            participantes = carregar_participantes_torneio(torneio_id)
            confrontos = carregar_confrontos_torneio(torneio_id)
            nomes_participantes = [p["jogador_nome"] for p in participantes]

            col_tit, col_del = st.columns([5, 1])
            with col_tit:
                st.subheader(f"{torneio['nome']}  ·  Status: {torneio['status']}  ·  Classificados p/ mata-mata: {torneio['qtd_classificados']}")
            with col_del:
                if st.button("🗑️ Excluir", key=f"del_torneio_{torneio_id}"):
                    st.session_state[f"confirmar_del_torneio_{torneio_id}"] = True
            if st.session_state.get(f"confirmar_del_torneio_{torneio_id}", False):
                st.warning("Tem certeza que deseja excluir este torneio e todos os seus dados? Essa ação não pode ser desfeita.")
                c_sim, c_nao, _ = st.columns([1, 1, 4])
                with c_sim:
                    if st.button("Sim, excluir torneio", type="primary", key=f"sim_del_torneio_{torneio_id}"):
                        excluir_torneio(torneio_id)
                        del st.session_state[f"confirmar_del_torneio_{torneio_id}"]
                        st.rerun()
                with c_nao:
                    if st.button("Cancelar", key=f"nao_del_torneio_{torneio_id}"):
                        del st.session_state[f"confirmar_del_torneio_{torneio_id}"]
                        st.rerun()

            st.divider()

            # ---------- FASE 1: CONFIGURANDO (adicionar participantes) ----------
            if torneio["status"] == "CONFIGURANDO":
                st.markdown("### Participantes")
                if participantes:
                    df_part = pd.DataFrame([
                        {"Jogador": p["jogador_nome"], "Deck": p["deck_escolhido"], "Comandante": p["comandante_escolhido"]}
                        for p in participantes
                    ])
                    st.dataframe(df_part, use_container_width=True, hide_index=True)

                jogadores_com_deck_t = [j for j in st.session_state.jogadores if st.session_state.jogadores[j].get("decks")]
                mapa_exib_t = {obter_nome_exibicao(st.session_state.jogadores[j], j): j for j in jogadores_com_deck_t}
                catalogo_t = carregar_catalogo()
                mapa_cmd_multi_t, _ = construir_mapa_comandantes_catalogo(catalogo_t)
                OPCAO_CONV_T = "➕ Usuário Não Cadastrado"
                nomes_ja_no_torneio = [p["jogador_nome"] for p in participantes]

                st.markdown("**Adicionar participante:**")
                opcoes_add = ["Selecione...", OPCAO_CONV_T] + list(mapa_exib_t.keys())
                jog_add = st.selectbox("Jogador:", opcoes_add, key="torneio_add_jog")

                deck_add = "Selecione..."
                cmd_add = "Selecione..."
                nome_final_add = None

                if jog_add == OPCAO_CONV_T:
                    nome_conv_t = st.text_input("Nome do convidado:", key="torneio_add_conv_nome")
                    if nome_conv_t.strip():
                        nome_final_add = f"{nome_conv_t.strip()} *"
                        cmd_direto_t = st.selectbox("Comandante:", ["Selecione..."] + sorted(mapa_cmd_multi_t.keys()), key="torneio_add_conv_cmd")
                        if cmd_direto_t != "Selecione...":
                            decks_poss_t = mapa_cmd_multi_t.get(cmd_direto_t, [])
                            if len(decks_poss_t) > 1:
                                deck_add = st.selectbox("Qual deck?", ["Selecione..."] + decks_poss_t, key="torneio_add_conv_deck_amb")
                            else:
                                deck_add = decks_poss_t[0] if decks_poss_t else "Selecione..."
                            if deck_add != "Selecione...":
                                cmd_add = cmd_direto_t
                                st.caption(f"Deck: **{deck_add}**")
                elif jog_add in mapa_exib_t:
                    nome_final_add = jog_add
                    real_key_t = mapa_exib_t[jog_add]
                    decks_jog_t = st.session_state.jogadores[real_key_t]["decks"]
                    mapa_cmd_dk_t = {}
                    for dk_n, dk_i in decks_jog_t.items():
                        for c in [dk_i.get("comandante_primario", ""), dk_i.get("comandante_secundario", ""), dk_i.get("comandante_adicional", "")]:
                            if c:
                                mapa_cmd_dk_t.setdefault(c, [])
                                if dk_n not in mapa_cmd_dk_t[c]:
                                    mapa_cmd_dk_t[c].append(dk_n)
                    cmd_direto_t2 = st.selectbox("Comandante:", ["Selecione..."] + list(mapa_cmd_dk_t.keys()), key="torneio_add_cmd_direto")
                    if cmd_direto_t2 != "Selecione...":
                        decks_poss_t2 = mapa_cmd_dk_t[cmd_direto_t2]
                        if len(decks_poss_t2) > 1:
                            deck_add = st.selectbox("Qual deck?", ["Selecione..."] + decks_poss_t2, key="torneio_add_deck_amb")
                        else:
                            deck_add = decks_poss_t2[0]
                        if deck_add != "Selecione...":
                            cmd_add = cmd_direto_t2
                            st.caption(f"Deck: **{deck_add}**")

                if st.button("Adicionar ao Torneio", key="torneio_btn_add_part"):
                    if not nome_final_add or nome_final_add == "Selecione...":
                        st.error("Selecione (ou digite) o jogador.")
                    elif nome_final_add in nomes_ja_no_torneio:
                        st.error("Esse jogador já está no torneio.")
                    elif deck_add == "Selecione..." or cmd_add == "Selecione...":
                        st.error("Escolha o comandante/deck do participante.")
                    else:
                        adicionar_participante_torneio(torneio_id, nome_final_add, deck_add, cmd_add)
                        st.success(f"{nome_final_add} adicionado!")
                        st.rerun()

                if participantes:
                    st.markdown("**Remover participante:**")
                    rem_sel = st.selectbox("Jogador:", ["Selecione..."] + [p["jogador_nome"] for p in participantes], key="torneio_rem_sel")
                    if rem_sel != "Selecione..." and st.button("Remover", key="torneio_btn_rem"):
                        p_obj = next(p for p in participantes if p["jogador_nome"] == rem_sel)
                        excluir_participante_torneio(p_obj["id"])
                        st.rerun()

                st.divider()
                st.markdown(f"**{len(participantes)} participante(s) cadastrados**")

                if len(participantes) >= torneio["qtd_classificados"]:
                    if st.button("🎲 Iniciar Fase Classificatória (Sorteia Rodada 1)", type="primary", key="torneio_iniciar_class"):
                        mesas = gerar_rodada_classificatoria(nomes_participantes, [], 1)
                        for mesa in mesas:
                            payload = [{"jogador": n, "eliminacoes": 0, "wo": False} for n in mesa]
                            criar_confronto(torneio_id, "CLASSIFICATORIA", 1, payload)
                        atualizar_status_torneio(torneio_id, "CLASSIFICATORIA")
                        st.rerun()
                else:
                    st.info(f"Adicione pelo menos {torneio['qtd_classificados']} participantes (mesmo total dos classificados p/ mata-mata) para iniciar.")

            # ---------- FASE 2: CLASSIFICATÓRIA (SUÍÇO) ----------
            elif torneio["status"] == "CLASSIFICATORIA":
                confrontos_class = [c for c in confrontos if c.get("fase") == "CLASSIFICATORIA"]
                rodada_atual = max(c["rodada"] for c in confrontos_class) if confrontos_class else 1

                st.markdown("### Classificação Atual")
                tabela = calcular_classificacao_suico(nomes_participantes, confrontos_class)
                st.dataframe(pd.DataFrame(tabela), use_container_width=True, hide_index=True)
                st.caption("Pts = 3 por vitória · Elim = eliminações causadas (usado só como desempate)")

                st.divider()
                st.markdown(f"### Mesas da Rodada {rodada_atual}")
                confrontos_rodada = [c for c in confrontos_class if c["rodada"] == rodada_atual]
                pendentes_rodada = [c for c in confrontos_rodada if c["status"] != "CONCLUIDO"]

                for c in confrontos_rodada:
                    nomes_mesa = [info["jogador"] for info in c["jogadores"]]
                    if c["status"] == "CONCLUIDO":
                        venc = c["vencedor"]
                        detalhes_str = " · ".join(
                            f"{info['jogador']}: {info['eliminacoes']} elim" + (" (WO)" if info.get("wo") else "")
                            for info in c["jogadores"]
                        )
                        st.markdown(f"**{' vs '.join(nomes_mesa)}** — ✅ Vencedor: **{venc}**  \n*{detalhes_str}*")
                    else:
                        with st.expander(f"Mesa: {' vs '.join(nomes_mesa)}"):
                            wo_sel = st.multiselect("Jogadores que faltaram (WO):", nomes_mesa, key=f"torneio_wo_{c['id']}")
                            presentes = [n for n in nomes_mesa if n not in wo_sel]
                            venc_sel = st.selectbox("Vencedor:", ["Selecione..."] + presentes, key=f"torneio_venc_{c['id']}")
                            elims_input = {}
                            for n in presentes:
                                elims_input[n] = st.number_input(
                                    f"Eliminações de {n}:", min_value=0, max_value=max(len(nomes_mesa) - 1, 0),
                                    value=0, step=1, key=f"torneio_elim_{c['id']}_{n}"
                                )
                            if st.button("Confirmar Resultado", key=f"torneio_confirmar_{c['id']}"):
                                if venc_sel == "Selecione...":
                                    st.error("Selecione o vencedor.")
                                else:
                                    bonus_wo = len(wo_sel)
                                    payload = []
                                    for n in nomes_mesa:
                                        if n in wo_sel:
                                            payload.append({"jogador": n, "eliminacoes": 0, "wo": True})
                                        else:
                                            payload.append({"jogador": n, "eliminacoes": elims_input[n] + bonus_wo, "wo": False})
                                    registrar_resultado_confronto(c["id"], payload, venc_sel)
                                    st.rerun()

                st.divider()
                if not pendentes_rodada and confrontos_rodada:
                    col_prox, col_encerrar = st.columns(2)
                    with col_prox:
                        if st.button("➡️ Gerar Próxima Rodada", key="torneio_prox_rodada_class"):
                            proxima = rodada_atual + 1
                            mesas = gerar_rodada_classificatoria(nomes_participantes, confrontos_class, proxima)
                            for mesa in mesas:
                                payload = [{"jogador": n, "eliminacoes": 0, "wo": False} for n in mesa]
                                criar_confronto(torneio_id, "CLASSIFICATORIA", proxima, payload)
                            st.rerun()
                    with col_encerrar:
                        if st.button("🏆 Encerrar Classificatória e Gerar Mata-Mata", type="primary", key="torneio_encerrar_class"):
                            tabela_final = calcular_classificacao_suico(nomes_participantes, confrontos_class)
                            qtd = torneio["qtd_classificados"]
                            if len(tabela_final) < qtd:
                                st.error(f"Só há {len(tabela_final)} participantes; não é possível classificar {qtd}.")
                            else:
                                classificados = [linha["Jogador"] for linha in tabela_final[:qtd]]
                                mesas_mm = gerar_mesas_matamata(classificados)
                                for mesa in mesas_mm:
                                    payload = [{"jogador": n, "eliminacoes": 0, "wo": False} for n in mesa]
                                    criar_confronto(torneio_id, "MATA_MATA", 1, payload)
                                atualizar_status_torneio(torneio_id, "MATA_MATA")
                                st.rerun()
                elif pendentes_rodada:
                    st.info("Conclua todas as mesas da rodada atual antes de avançar.")

            # ---------- FASE 3: MATA-MATA ----------
            elif torneio["status"] == "MATA_MATA":
                confrontos_mm = [c for c in confrontos if c.get("fase") == "MATA_MATA"]
                rodadas_mm = sorted(set(c["rodada"] for c in confrontos_mm))
                rodada_final_num = max(rodadas_mm) if rodadas_mm else 1

                def _rotulo_rodada_mm(r):
                    dist = rodada_final_num - r
                    labels = ["Final", "Semifinal", "Quartas de Final", "Oitavas de Final"]
                    return labels[dist] if dist < len(labels) else f"Rodada {r}"

                st.markdown("### Chaveamento")
                html_bracket = "<div style='display:flex; gap:32px; overflow-x:auto; padding:12px 0;'>"
                for r in rodadas_mm:
                    confrontos_r = [c for c in confrontos_mm if c["rodada"] == r]
                    html_bracket += "<div style='display:flex; flex-direction:column; justify-content:space-around; gap:16px; min-width:230px;'>"
                    html_bracket += f"<div style='text-align:center; color:#FFD700; font-weight:bold; font-size:13px; text-transform:uppercase;'>{_rotulo_rodada_mm(r)}</div>"
                    for c in confrontos_r:
                        nomes_mesa = [info["jogador"] for info in c["jogadores"]]
                        venc = c.get("vencedor")
                        segundo = None
                        if c["status"] == "CONCLUIDO":
                            _, segundo = determinar_avancantes_mesa(c)
                        linhas_html = ""
                        for n in nomes_mesa:
                            if n == venc:
                                cor, peso, tag = "#FFD700", "bold", " 🥇"
                            elif n == segundo:
                                cor, peso, tag = "#00CC66", "bold", " 🥈"
                            elif venc:
                                cor, peso, tag = "#888888", "normal", ""
                            else:
                                cor, peso, tag = "#FFFFFF", "normal", ""
                            linhas_html += f"<div style='color:{cor}; font-weight:{peso}; font-size:13px;'>{n}{tag}</div>"
                        html_bracket += f"<div style='border:1px solid rgba(250,250,250,0.2); border-radius:8px; padding:10px 14px; background-color:rgba(255,255,255,0.03);'>{linhas_html}</div>"
                    html_bracket += "</div>"
                html_bracket += "</div>"
                st.markdown(html_bracket, unsafe_allow_html=True)
                st.caption("🥇 vencedor da mesa · 🥈 segundo colocado (mais eliminações entre os demais) — ambos avançam")

                st.divider()
                st.markdown("### Registrar Resultados")
                confrontos_rodada_mm = [c for c in confrontos_mm if c["rodada"] == rodada_final_num]
                pendentes_mm = [c for c in confrontos_rodada_mm if c["status"] != "CONCLUIDO"]

                for c in pendentes_mm:
                    nomes_mesa = [info["jogador"] for info in c["jogadores"]]
                    with st.expander(f"Mesa: {' vs '.join(nomes_mesa)}"):
                        wo_sel_mm = st.multiselect("Jogadores que faltaram (WO):", nomes_mesa, key=f"torneio_mm_wo_{c['id']}")
                        presentes_mm = [n for n in nomes_mesa if n not in wo_sel_mm]
                        venc_sel_mm = st.selectbox("Vencedor:", ["Selecione..."] + presentes_mm, key=f"torneio_mm_venc_{c['id']}")
                        elims_mm = {}
                        for n in presentes_mm:
                            elims_mm[n] = st.number_input(
                                f"Eliminações de {n}:", min_value=0, max_value=max(len(nomes_mesa) - 1, 0),
                                value=0, step=1, key=f"torneio_mm_elim_{c['id']}_{n}"
                            )
                        if st.button("Confirmar Resultado", key=f"torneio_mm_confirmar_{c['id']}"):
                            if venc_sel_mm == "Selecione...":
                                st.error("Selecione o vencedor.")
                            else:
                                bonus_wo_mm = len(wo_sel_mm)
                                payload = []
                                for n in nomes_mesa:
                                    if n in wo_sel_mm:
                                        payload.append({"jogador": n, "eliminacoes": 0, "wo": True})
                                    else:
                                        payload.append({"jogador": n, "eliminacoes": elims_mm[n] + bonus_wo_mm, "wo": False})
                                registrar_resultado_confronto(c["id"], payload, venc_sel_mm)
                                st.rerun()

                if not pendentes_mm and confrontos_rodada_mm:
                    if len(confrontos_rodada_mm) == 1:
                        campeao, vice = determinar_avancantes_mesa(confrontos_rodada_mm[0])
                        st.balloons()
                        st.success(f"🏆 Campeão do torneio: **{campeao}**! 🥈 Vice: **{vice}**")
                        if st.button("Finalizar Torneio", type="primary", key="torneio_finalizar"):
                            atualizar_status_torneio(torneio_id, "FINALIZADO")
                            st.rerun()
                    else:
                        if st.button("➡️ Gerar Próxima Rodada do Mata-Mata", type="primary", key="torneio_prox_rodada_mm"):
                            avancantes = []
                            for c in confrontos_rodada_mm:
                                primeiro, segundo = determinar_avancantes_mesa(c)
                                if primeiro:
                                    avancantes.append(primeiro)
                                if segundo:
                                    avancantes.append(segundo)
                            mesas_prox = gerar_mesas_matamata(avancantes)
                            for mesa in mesas_prox:
                                payload = [{"jogador": n, "eliminacoes": 0, "wo": False} for n in mesa]
                                criar_confronto(torneio_id, "MATA_MATA", rodada_final_num + 1, payload)
                            st.rerun()

            # ---------- FASE 4: FINALIZADO ----------
            elif torneio["status"] == "FINALIZADO":
                confrontos_mm_final = [c for c in confrontos if c.get("fase") == "MATA_MATA"]
                if confrontos_mm_final:
                    rodada_final = max(c["rodada"] for c in confrontos_mm_final)
                    final_confronto = next((c for c in confrontos_mm_final if c["rodada"] == rodada_final), None)
                    if final_confronto:
                        campeao, vice = determinar_avancantes_mesa(final_confronto)
                        st.success(f"🏆 Torneio finalizado! Campeão: **{campeao}** · Vice: **{vice}**")
                st.markdown("### Classificação Final da Fase Classificatória")
                confrontos_class_final = [c for c in confrontos if c.get("fase") == "CLASSIFICATORIA"]
                tabela_final_hist = calcular_classificacao_suico(nomes_participantes, confrontos_class_final)
                st.dataframe(pd.DataFrame(tabela_final_hist), use_container_width=True, hide_index=True)
