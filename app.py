import streamlit as st
import pandas as pd
import os
import re
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

    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        if logo_path:
            _, col_logo, _ = st.columns([1, 2, 1])
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
    _, col_center_texto, _ = st.columns([1, 2, 1])
    with col_center_texto:
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

def buscar_precon_por_nome(nome_deck):
    resultado = sb.table("catalogo_precons").select("*").eq("nome", nome_deck).execute().data
    return resultado[0] if resultado else None

def cor_ranking(pos, total=185):
    """Retorna a cor HTML baseada na posição do ranking."""
    if pos is None:
        return "#888888"
    if pos == 1:
        return "#FFD700"   # Dourado
    if pos == 2:
        return "#C0C0C0"   # Prateado
    if pos == 3:
        return "#CD7F32"   # Bronze
    media = total // 2 + 1  # posição 93
    if pos < media:
        return "#00CC66"   # Verde
    if pos == media:
        return "#FFFFFF"   # Branco
    return "#FF4444"       # Vermelho

def emoji_ranking(pos, total=185):
    """Retorna emoji colorido para usar no título do expander."""
    if pos is None:
        return ""
    if pos == 1:
        return "🥇"
    if pos == 2:
        return "🥈"
    if pos == 3:
        return "🥉"
    media = total // 2 + 1
    if pos < media:
        return "🟢"
    if pos == media:
        return "⚪"
    return "🔴"

def badge_ranking(pos, total=185):
    """Retorna HTML do badge de ranking colorido."""
    if pos is None:
        return ""
    cor = cor_ranking(pos, total)
    return f'<span style="color:{cor}; font-weight:bold; font-size:12px;">Rank #{pos}</span>'


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
def exibir_lista_cartas(cartas, comandante_primario=None):
    import uuid as _uuid
    import streamlit.components.v1 as _components

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
        options=["Statistics", "Cadastro", "Jogadores", "Decks", "Nova Partida"],
        icons=["trophy", "person-plus", "people", "card-list", "controller"],
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

                        # Busca ranking do deck
                        _rank_info = sb.table("catalogo_precons").select("ranking").eq("nome", nome_d).execute().data
                        _rank_pos = _rank_info[0]["ranking"] if _rank_info else None
                        _badge = badge_ranking(_rank_pos)

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
                                exibir_lista_cartas(precon.get("cartas", []), comandante_primario=cmd_p)
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
                            _rank_prev = precon.get("ranking")
                            _pts_prev = precon.get("pontuacao_rank")
                            if _rank_prev:
                                _cor_prev = cor_ranking(_rank_prev)
                                _pts_str = f" ({_pts_prev:.0f} pts)" if _pts_prev else ""
                                st.markdown(f'<span style="color:{_cor_prev}; font-weight:bold; font-size:14px;">★ Rank #{_rank_prev}{_pts_str}</span>', unsafe_allow_html=True)
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
                            exibir_lista_cartas(precon.get("cartas", []), comandante_primario=_cmd_p_prev)

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
                ["Lançamento (mais novo)", "Lançamento (mais antigo)", "Alfabético (A-Z)", "Alfabético (Z-A)", "Ranking (melhor)", "Ranking (pior)"],
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
        elif ordenacao == "Ranking (melhor)":
            catalogo = sorted(catalogo, key=lambda d: d.get("ranking") or 9999)
        elif ordenacao == "Ranking (pior)":
            catalogo = sorted(catalogo, key=lambda d: d.get("ranking") or 0, reverse=True)
        catalogo_filtrado = catalogo
        if busca_catalogo.strip():
            catalogo_filtrado = [d for d in catalogo if busca_catalogo.strip().lower() in d["nome"].lower()]
        st.markdown(f"*{len(catalogo_filtrado)} deck(s) no catálogo*")

        for deck_cat in catalogo_filtrado:
            nome_cat = deck_cat["nome"]
            cmds_cat = deck_cat.get("comandantes", [])
            donos = nomes_decks_escolhidos.get(nome_cat, [])
            rank_cat = deck_cat.get("ranking")
            emoji = emoji_ranking(rank_cat)
            rank_label = f" {emoji} Rank #{rank_cat}" if rank_cat else ""
            if donos:
                label_expander = f"{nome_cat.upper()}{rank_label} — ⚠️ Já escolhido por: {', '.join(donos)}"
            else:
                label_expander = f"{nome_cat.upper()}{rank_label}"
            with st.expander(label_expander):
                # Badge de ranking colorido
                if rank_cat:
                    cor = cor_ranking(rank_cat)
                    pts = deck_cat.get("pontuacao_rank", "")
                    pts_str = f" ({pts:.0f} pts)" if pts else ""
                    st.markdown(f'<span style="color:{cor}; font-weight:bold; font-size:14px;">★ Rank #{rank_cat}{pts_str}</span>', unsafe_allow_html=True)
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
                    exibir_lista_cartas(precon.get("cartas", []), comandante_primario=_cmd_p_cat)
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

        local_partida = st.selectbox("Local da Partida:", ["PRESENCIAL", "SPELLTABLE"], key="sel_local")
        modo_partida = st.selectbox("Modo de Jogo:", ["SOLO", "DRAGÃO DE DUAS CABEÇAS", "ARCH ENEMY"], key="sel_modo")

        if modo_partida == "DRAGÃO DE DUAS CABEÇAS":
            qtd_duplas = st.selectbox("Quantidade de Duplas:", [2, 3, 4], index=0, key="sel_qtd_duplas")
            qtd_jogadores = qtd_duplas * 2
            st.info(f"Modo Dragão de Duas Cabeças: {qtd_duplas} duplas ({qtd_jogadores} jogadores).")
        elif modo_partida == "ARCH ENEMY":
            qtd_jogadores = 5
            st.info("Modo Arch Enemy fixado em 5 jogadores.")
        else:
            qtd_jogadores = st.selectbox("Quantidade de Jogadores:", [2, 3, 4, 5, 6, 7, 8], index=2, key="sel_qtd_jog")

        st.divider()
        st.subheader("Configuração dos Integrantes da Mesa")

        if modo_partida == "DRAGÃO DE DUAS CABEÇAS":
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
                        opcoes_j = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n not in todos_j_selecionados]
                        jog = st.selectbox(f"Jogador {p_idx+1}:", opcoes_j, key=f"dupla_j_{d_idx}_{p_idx}")
                        dk = "Selecione..."
                        cmd = "Selecione..."
                        if jog in mapa_exib_para_real:
                            todos_j_selecionados.append(jog)
                            real_key = mapa_exib_para_real[jog]
                            decks_jog = st.session_state.jogadores[real_key]["decks"]
                            # Seleção por comandante primeiro
                            mapa_cmd_dk = {}
                            for dk_n, dk_i in decks_jog.items():
                                for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                    if c: mapa_cmd_dk[c] = dk_n
                            cmd_direto = st.selectbox(f"Comandante (J{num_j}):", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"dupla_cmd_{d_idx}_{p_idx}")
                            if cmd_direto != "Selecione...":
                                dk = mapa_cmd_dk[cmd_direto]
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
                        dupla_jogadores.append({"Jogador": jog, "Deck": dk, "Comandante": cmd})
                    duplas_config[letras_duplas[d_idx]] = dupla_jogadores

            # Verifica se todos estão preenchidos
            todos_validos = all(
                p["Jogador"] in mapa_exib_para_real and p["Deck"] != "Selecione..." and p["Comandante"] != "Selecione..."
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

        elif modo_partida == "ARCH ENEMY":
            selecionados_nomes = []
            colunas_ae = st.columns(5)
            dados_ae = []
            for i in range(5):
                with colunas_ae[i]:
                    st.markdown(f"#### Posição {i+1}")
                    if i == 0:
                        st.markdown("*Arch Enemy*")
                    opcoes_filtradas = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n not in selecionados_nomes]
                    jog_escolhido = st.selectbox(f"Jogador {i+1}:", opcoes_filtradas, key=f"ae_j_{i}")
                    deck_escolhido = "Selecione..."
                    cmd_escolhido = "Selecione..."
                    if jog_escolhido in mapa_exib_para_real:
                        selecionados_nomes.append(jog_escolhido)
                        real_key = mapa_exib_para_real[jog_escolhido]
                        decks_jog = st.session_state.jogadores[real_key]["decks"]
                        mapa_cmd_dk = {}
                        for dk_n, dk_i in decks_jog.items():
                            for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                if c: mapa_cmd_dk[c] = dk_n
                        cmd_direto = st.selectbox(f"Comandante:", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"ae_cmd_{i}")
                        if cmd_direto != "Selecione...":
                            deck_escolhido = mapa_cmd_dk[cmd_direto]
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
                    dados_ae.append({"Jogador": jog_escolhido, "Deck": deck_escolhido, "Comandante": cmd_escolhido})

            validos_ae = [d for d in dados_ae if d["Jogador"] in mapa_exib_para_real and d["Deck"] != "Selecione..." and d["Comandante"] != "Selecione..."]

            if len(validos_ae) == 5:
                st.divider()
                st.subheader("Classificação Final — Arch Enemy")
                coloca_ordem_ae = []
                nomes_ae = [d["Jogador"] for d in validos_ae]
                for pos in range(5):
                    opcoes_pos = ["Selecione..."] + [n for n in nomes_ae if n not in coloca_ordem_ae]
                    txt_label = "1º Lugar (Vencedor):" if pos == 0 else f"{pos+1}º Lugar:"
                    escolha = st.selectbox(txt_label, opcoes_pos, key=f"ae_pos_{pos}")
                    if escolha in nomes_ae:
                        coloca_ordem_ae.append(escolha)

                if len(coloca_ordem_ae) == 5:
                    if st.button("Gravar Resultado Arch Enemy", key="btn_salvar_ae"):
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
                            for k in [f"ae_j_{i}", f"ae_cmd_{i}", f"ae_dk_{i}", f"ae_cmd2_{i}", f"ae_pos_{i}"]:
                                if k in st.session_state: del st.session_state[k]
                        st.session_state.mensagem_sucesso_partida = "Resultado Arch Enemy gravado com sucesso!"
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
                    opcoes_filtradas = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n not in selecionados_nomes]
                    jog_escolhido = st.selectbox(f"Jogador {i+1}:", opcoes_filtradas, key=f"solo_j_{i}")
                    deck_escolhido = "Selecione..."
                    cmd_escolhido = "Selecione..."
                    if jog_escolhido in mapa_exib_para_real:
                        selecionados_nomes.append(jog_escolhido)
                        real_key = mapa_exib_para_real[jog_escolhido]
                        decks_jog = st.session_state.jogadores[real_key]["decks"]
                        mapa_cmd_dk = {}
                        for dk_n, dk_i in decks_jog.items():
                            for c in [dk_i.get("comandante_primario",""), dk_i.get("comandante_secundario",""), dk_i.get("comandante_adicional","")]:
                                if c: mapa_cmd_dk[c] = dk_n
                        cmd_direto = st.selectbox(f"Comandante do Jogador {i+1}:", ["Selecione..."] + list(mapa_cmd_dk.keys()), key=f"solo_cmd_direto_{i}")
                        if cmd_direto != "Selecione...":
                            deck_escolhido = mapa_cmd_dk.get(cmd_direto, "Selecione...")
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
                    dados_confronto.append({"Jogador": jog_escolhido, "Deck": deck_escolhido, "Comandante": cmd_escolhido})

            validos = [d for d in dados_confronto if d["Jogador"] in mapa_exib_para_real and d["Deck"] != "Selecione..." and d["Comandante"] != "Selecione..."]
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
                            for key in [f"solo_j_{i}", f"solo_d_{i}", f"solo_c_{i}", f"solo_cmd_direto_{i}"]:
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
        st.subheader("Filtros de Classificação")
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_local = st.selectbox("Local:", ["TODOS", "PRESENCIAL", "SPELLTABLE"])
        with c2: f_modo = st.selectbox("Modo:", ["TODOS", "SOLO", "DRAGÃO DE DUAS CABEÇAS", "ARCH ENEMY"])
        with c3: f_tipo = st.selectbox("Ranking por:", ["Competidor", "Deck", "Comandante"])
        with c4: f_metrica = st.selectbox("Métrica:", ["Pontuação", "Vitórias"])

        df = st.session_state.partidas.copy()
        if f_local != "TODOS": df = df[df["Local"] == f_local]
        if f_modo != "TODOS": df = df[df["Modo"] == f_modo]

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
