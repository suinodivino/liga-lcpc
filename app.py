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
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        formatos_logo = ["logo.jpg", "logo.jpeg", "logo.png", "logo.PNG", "logo.JPG"]
        for nome_arquivo in formatos_logo:
            if os.path.exists(nome_arquivo):
                st.image(nome_arquivo, width=300)
                break

        st.markdown("<h2 style='text-align:center;'>Liga Commander Pré-Con</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#888;'>Faça login para acessar</p>", unsafe_allow_html=True)
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
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")

# --- VERIFICAR SE ESTÁ LOGADO ---
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "usuario_email" not in st.session_state:
    st.session_state.usuario_email = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

if not st.session_state.usuario_logado:
    tela_login()
    st.stop()

# --- A PARTIR DAQUI O USUÁRIO ESTÁ LOGADO ---
usuario_email = st.session_state.usuario_email
is_admin = st.session_state.is_admin

# --- FUNÇÕES DE FOTO ---
def upload_foto(nome_jogador, foto_bytes, extensao="jpg"):
    try:
        caminho = f"{nome_jogador}.{extensao}"
        sb.storage.from_("fotos-jogadores").upload(
            caminho, foto_bytes,
            file_options={"content-type": f"image/{extensao}", "upsert": "true"}
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
    dados = sb.table("catalogo_precons").select("id, nome, comandantes, set_nome, data_lancamento, cartas").execute().data
    return dados if dados else []

def buscar_precon_por_nome(nome_deck):
    resultado = sb.table("catalogo_precons").select("*").eq("nome", nome_deck).execute().data
    return resultado[0] if resultado else None

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
def exibir_lista_cartas(cartas):
    st.markdown("""
    <style>
    .card-list-wrap { column-count: 2; column-gap: 24px; }
    @media (max-width: 768px) { .card-list-wrap { column-count: 1; } }
    .card-item {
        position: relative; display: block; padding: 3px 8px;
        margin: 2px 0; border-radius: 4px; font-size: 14px;
        cursor: default; break-inside: avoid;
    }
    .card-item:hover { background-color: rgba(255,255,255,0.08); }
    .card-qty {
        display: inline-block; min-width: 24px; text-align: center;
        background: rgba(255,255,255,0.12); border-radius: 3px;
        margin-right: 6px; font-size: 12px; padding: 0 4px;
    }
    .card-mana {
        font-size: 11px; color: #aaa; margin-left: 6px;
    }
    .card-tooltip {
        display: none; position: fixed; z-index: 99999;
        pointer-events: none; top: 50%; transform: translateY(-50%);
        left: 55%; width: 280px; border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.7);
    }
    @media (max-width: 768px) {
        .card-tooltip {
            left: 50%; transform: translate(-50%, -50%);
            top: 40%; width: 200px;
        }
    }
    .card-tooltip img { width: 100%; border-radius: 10px; }
    .card-item:hover .card-tooltip { display: block; }
    .bloco-titulo {
        font-size: 13px; font-weight: bold; color: #888;
        text-transform: uppercase; letter-spacing: 1px;
        margin: 14px 0 4px 0; padding-bottom: 2px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

    # Ordem dos blocos
    ordem_blocos = ["Comandante", "Criaturas", "Planeswalkers", "Mágicas Instantâneas",
                    "Feitiços", "Artefatos", "Encantamentos", "Batalhas", "Terrenos", "Outros"]

    # Agrupa por tipo_bloco
    grupos = {}
    for carta in cartas:
        bloco = carta.get("tipo_bloco", "Outros") or "Outros"
        grupos.setdefault(bloco, []).append(carta)

    html = ""
    for bloco in ordem_blocos:
        if bloco not in grupos:
            continue
        cartas_bloco = sorted(grupos[bloco], key=lambda c: c["nome"])
        total = sum(c.get("quantidade", 1) for c in cartas_bloco)
        html += f'<div class="bloco-titulo">{bloco} ({total})</div>'
        html += '<div class="card-list-wrap">'
        for carta in cartas_bloco:
            nome = carta["nome"]
            qtd = carta.get("quantidade", 1)
            img = carta.get("imagem_url", "")
            mana = carta.get("mana_cost", "")
            tooltip = f'<span class="card-tooltip"><img src="{img}" alt="{nome}"/></span>' if img else ""
            mana_span = f'<span class="card-mana">{mana}</span>' if mana else ""
            html += f'<div class="card-item"><span class="card-qty">{qtd}x</span>{nome}{mana_span}{tooltip}</div>'
        html += "</div>"

    st.markdown(html, unsafe_allow_html=True)

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
st.sidebar.markdown("---")
st.sidebar.markdown(f"👤 **{usuario_email}**")
if is_admin:
    st.sidebar.markdown("🔑 *Administrador*")
if st.sidebar.button("Sair", use_container_width=True):
    fazer_logout()

with st.sidebar:
    aba = option_menu(
        menu_title=None,
        options=["Home", "Cadastro", "Jogadores", "Decks", "Nova Partida", "Ranking"],
        icons=["house", "person-plus", "people", "card-list", "controller", "trophy"],
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

# ===================== HOME =====================
if aba == "Home":
    container_home = st.container()
    with container_home:
        _, col_center, _ = st.columns([1, 2, 1])
        with col_center:
            if logo_encontrada:
                st.image(logo_encontrada, width=455)
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

# ===================== CADASTRO =====================
elif aba == "Cadastro":
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
                    novo_apelido = st.text_input("Editar Apelido", value=dados_edit["apelido"], key="txt_edit_apelido")
                    novo_telefone = st.text_input("Editar Telefone", value=dados_edit["telefone"], key="txt_edit_telefone")
                    novo_email = st.text_input("Editar E-mail", value=dados_edit["email"], key="txt_edit_email")
                    if is_admin:
                        nova_senha = st.text_input("Nova Senha (deixe em branco para não alterar)", type="password", key="txt_edit_senha")
                    nova_foto = st.file_uploader("Atualizar Foto", type=["jpg", "png", "jpeg"], key="file_edit_foto")

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
                        cmd_str = f"Primário: {info_d['comandante_primario']} | Secundário: {info_d['comandante_secundario']}"
                        if info_d.get("comandante_adicional"):
                            cmd_str += f" | Adicional: {info_d['comandante_adicional']}"
                        col_dk, col_btn_ver = st.columns([3, 1])
                        with col_dk:
                            st.markdown(f"**{nome_d.upper()}**  \n{cmd_str}")
                        with col_btn_ver:
                            if st.button("Ver Lista", key=f"ver_lista_{jogador_real}_{nome_d}"):
                                precon = buscar_precon_por_nome(nome_d)
                                if precon:
                                    st.session_state.deck_precon_preview = precon
                                    st.session_state.deck_preview_context = "arsenal"
                                else:
                                    st.warning("Lista não encontrada no catálogo.")

                    if st.session_state.get("deck_preview_context") == "arsenal" and st.session_state.deck_precon_preview:
                        precon = st.session_state.deck_precon_preview
                        with st.expander(f"Lista: {precon['nome']}", expanded=True):
                            cmds = precon.get("comandantes", [])
                            if cmds:
                                st.markdown(f"**Comandantes:** {' | '.join(cmds)}")
                            st.markdown(f"*{precon.get('set_nome', '')}*")
                            st.divider()
                            exibir_lista_cartas(precon.get("cartas", []))
                            if st.button("Fechar Lista", key="fechar_preview_arsenal"):
                                st.session_state.deck_precon_preview = None
                                st.session_state.deck_preview_context = None
                                st.rerun()

                    # Edição e exclusão de deck apenas para quem pode editar
                    if pode_editar:
                        st.markdown("<br>", unsafe_allow_html=True)
                        tab_gerenciar_existentes, tab_remover_existente = st.tabs(["Editar Deck", "Excluir Deck"])

                        with tab_gerenciar_existentes:
                            opcoes_edit_dk = ["Selecione um deck para editar..."] + list(dados_j["decks"].keys())
                            dk_escolhido_edit = st.selectbox("Qual deck deseja alterar?", opcoes_edit_dk, key="sel_dk_gerenciamento_edit")
                            if dk_escolhido_edit != "Selecione um deck para editar...":
                                dados_dk_edit = dados_j["decks"][dk_escolhido_edit]
                                edit_cmd_p = st.text_input("Comandante Primário*", value=dados_dk_edit["comandante_primario"], key="txt_edit_cmd_p")
                                edit_cmd_s = st.text_input("Comandante Secundário*", value=dados_dk_edit["comandante_secundario"], key="txt_edit_cmd_s")
                                edit_cmd_a = st.text_input("Comandante Adicional (Opcional)", value=dados_dk_edit.get("comandante_adicional", ""), key="txt_edit_cmd_a")
                                if st.button("Salvar Alterações do Deck", key="btn_confirmar_alteracoes_deck"):
                                    if edit_cmd_p and edit_cmd_s:
                                        dados_j["decks"][dk_escolhido_edit] = {
                                            "comandante_primario": edit_cmd_p.strip(),
                                            "comandante_secundario": edit_cmd_s.strip(),
                                            "comandante_adicional": edit_cmd_a.strip() if edit_cmd_a else "",
                                            "url": dados_dk_edit.get("url", "")
                                        }
                                        salvar_deck(jogador_real, dk_escolhido_edit, dados_j["decks"][dk_escolhido_edit])
                                        st.success(f"Deck '{dk_escolhido_edit}' atualizado!")
                                        st.rerun()
                                    else:
                                        st.error("Comandante Primário e Secundário são obrigatórios.")

                        with tab_remover_existente:
                            opcoes_deck = ["Selecione um deck..."] + list(dados_j["decks"].keys())
                            deck_excluir = st.selectbox("Escolha o deck para remover:", opcoes_deck, key="sel_dk_excluir_real")
                            if deck_excluir != "Selecione um deck...":
                                if st.button("Remover Este Deck", type="primary", key="btn_remover_dk_real"):
                                    excluir_deck_db(jogador_real, deck_excluir)
                                    del dados_j["decks"][deck_excluir]
                                    st.success(f"Deck '{deck_excluir}' removido com sucesso!")
                                    st.rerun()
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
                            sugestoes = [n for n in nomes_catalogo if busca.strip().lower() in n.lower()]
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
                            exibir_lista_cartas(precon.get("cartas", []))

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
    st.header("Arsenal Geral da LCPC")

    decks_escolhidos = []
    nomes_decks_escolhidos = {}

    for nome_jog, dados_jog in st.session_state.jogadores.items():
        exibicao_jog = obter_nome_exibicao(dados_jog, nome_jog)
        for nome_dk, info_dk in dados_jog["decks"].items():
            cmd_str = f"1º: {info_dk['comandante_primario']} | 2º: {info_dk['comandante_secundario']}"
            if info_dk.get("comandante_adicional"):
                cmd_str += f" | 3º: {info_dk['comandante_adicional']}"
            decks_escolhidos.append({
                "Deck": nome_dk.upper(), "Comandantes": cmd_str,
                "Dono": exibicao_jog, "nome_real": nome_dk
            })
            if nome_dk not in nomes_decks_escolhidos:
                nomes_decks_escolhidos[nome_dk] = []
            nomes_decks_escolhidos[nome_dk].append(exibicao_jog)

    st.subheader("Decks Disponíveis no Catálogo")
    catalogo = carregar_catalogo()
    if catalogo:
        # Ordena do mais novo para o mais antigo
        catalogo = sorted(catalogo, key=lambda d: d.get("data_lancamento", ""), reverse=True)
        busca_catalogo = st.text_input("Filtrar catálogo:", placeholder="Digite para filtrar...", key="filtro_catalogo")
        catalogo_filtrado = catalogo
        if busca_catalogo.strip():
            catalogo_filtrado = [d for d in catalogo if busca_catalogo.strip().lower() in d["nome"].lower()]
        st.markdown(f"*{len(catalogo_filtrado)} deck(s) no catálogo*")

        for deck_cat in catalogo_filtrado:
            nome_cat = deck_cat["nome"]
            cmds_cat = deck_cat.get("comandantes", [])
            donos = nomes_decks_escolhidos.get(nome_cat, [])
            if donos:
                label_expander = f"{nome_cat.upper()} — ⚠️ Já escolhido por: {', '.join(donos)}"
            else:
                label_expander = f"{nome_cat.upper()}"
            with st.expander(label_expander):
                if cmds_cat:
                    st.markdown(f"**Comandantes:** {' | '.join(cmds_cat)}")
                st.markdown(f"*{deck_cat.get('set_nome', '')}*")
                if donos:
                    st.warning(f"Este deck já foi escolhido por: **{', '.join(donos)}**. Você ainda pode vinculá-lo, mas considere escolher um diferente!")
                if st.button("Ver Lista de Cartas", key=f"ver_cat_{nome_cat}"):
                    precon_full = buscar_precon_por_nome(nome_cat)
                    if precon_full:
                        st.session_state.deck_precon_preview = precon_full
                        st.session_state.deck_preview_context = f"catalogo_{nome_cat}"
                    else:
                        st.warning("Lista não encontrada.")
                ctx_cat = f"catalogo_{nome_cat}"
                if st.session_state.get("deck_preview_context") == ctx_cat and st.session_state.deck_precon_preview:
                    precon = st.session_state.deck_precon_preview
                    st.divider()
                    exibir_lista_cartas(precon.get("cartas", []))
                    if st.button("Fechar Lista", key=f"fechar_cat_{nome_cat}"):
                        st.session_state.deck_precon_preview = None
                        st.session_state.deck_preview_context = None
                        st.rerun()
    else:
        st.info("Catálogo de precons não encontrado.")

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
        modo_partida = st.selectbox("Modo de Jogo:", ["SOLO", "DRAGÃO DE DUAS CABEÇAS"], key="sel_modo")

        if modo_partida == "DRAGÃO DE DUAS CABEÇAS":
            qtd_jogadores = 4
            st.info("Modo Dragão de Duas Cabeças fixado em 4 jogadores (2 duplas).")
        else:
            qtd_jogadores = st.selectbox("Quantidade de Jogadores:", [2, 3, 4, 5], index=2, key="sel_qtd_jog")

        st.divider()
        st.subheader("Configuração dos Integrantes da Mesa")

        if modo_partida == "DRAGÃO DE DUAS CABEÇAS":
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.markdown("### DUPLA A")
                j1 = st.selectbox("Jogador 1 (Dupla A):", lista_nomes_disponiveis, key="dupla_j1")
                d1, c1 = "Selecione...", "Selecione..."
                if j1 in mapa_exib_para_real:
                    real_j1 = mapa_exib_para_real[j1]
                    d1 = st.selectbox("Deck do Jogador 1:", ["Selecione..."] + list(st.session_state.jogadores[real_j1]["decks"].keys()), key="dupla_d1")
                    if d1 != "Selecione...":
                        dk_obj = st.session_state.jogadores[real_j1]["decks"][d1]
                        opcoes_cmd = [dk_obj["comandante_primario"], dk_obj["comandante_secundario"]]
                        if dk_obj.get("comandante_adicional"):
                            opcoes_cmd.append(dk_obj["comandante_adicional"])
                        c1 = st.selectbox("Comandante em Campo (J1):", ["Selecione..."] + opcoes_cmd, key="dupla_c1")
                st.markdown("---")
                opcoes_j2 = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n != j1]
                j2 = st.selectbox("Jogador 2 (Dupla A):", opcoes_j2, key="dupla_j2")
                d2, c2 = "Selecione...", "Selecione..."
                if j2 in mapa_exib_para_real:
                    real_j2 = mapa_exib_para_real[j2]
                    d2 = st.selectbox("Deck do Jogador 2:", ["Selecione..."] + list(st.session_state.jogadores[real_j2]["decks"].keys()), key="dupla_d2")
                    if d2 != "Selecione...":
                        dk_obj = st.session_state.jogadores[real_j2]["decks"][d2]
                        opcoes_cmd = [dk_obj["comandante_primario"], dk_obj["comandante_secundario"]]
                        if dk_obj.get("comandante_adicional"):
                            opcoes_cmd.append(dk_obj["comandante_adicional"])
                        c2 = st.selectbox("Comandante em Campo (J2):", ["Selecione..."] + opcoes_cmd, key="dupla_c2")
            with col_d2:
                st.markdown("### DUPLA B")
                opcoes_j3 = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n not in [j1, j2]]
                j3 = st.selectbox("Jogador 3 (Dupla B):", opcoes_j3, key="dupla_j3")
                d3, c3 = "Selecione...", "Selecione..."
                if j3 in mapa_exib_para_real:
                    real_j3 = mapa_exib_para_real[j3]
                    d3 = st.selectbox("Deck do Jogador 3:", ["Selecione..."] + list(st.session_state.jogadores[real_j3]["decks"].keys()), key="dupla_d3")
                    if d3 != "Selecione...":
                        dk_obj = st.session_state.jogadores[real_j3]["decks"][d3]
                        opcoes_cmd = [dk_obj["comandante_primario"], dk_obj["comandante_secundario"]]
                        if dk_obj.get("comandante_adicional"):
                            opcoes_cmd.append(dk_obj["comandante_adicional"])
                        c3 = st.selectbox("Comandante em Campo (J3):", ["Selecione..."] + opcoes_cmd, key="dupla_c3")
                st.markdown("---")
                opcoes_j4 = ["Selecione..."] + [n for n in list(mapa_exib_para_real.keys()) if n not in [j1, j2, j3]]
                j4 = st.selectbox("Jogador 4 (Dupla B):", opcoes_j4, key="dupla_j4")
                d4, c4 = "Selecione...", "Selecione..."
                if j4 in mapa_exib_para_real:
                    real_j4 = mapa_exib_para_real[j4]
                    d4 = st.selectbox("Deck do Jogador 4:", ["Selecione..."] + list(st.session_state.jogadores[real_j4]["decks"].keys()), key="dupla_d4")
                    if d4 != "Selecione...":
                        dk_obj = st.session_state.jogadores[real_j4]["decks"][d4]
                        opcoes_cmd = [dk_obj["comandante_primario"], dk_obj["comandante_secundario"]]
                        if dk_obj.get("comandante_adicional"):
                            opcoes_cmd.append(dk_obj["comandante_adicional"])
                        c4 = st.selectbox("Comandante em Campo (J4):", ["Selecione..."] + opcoes_cmd, key="dupla_c4")

            if j1 in mapa_exib_para_real and j2 in mapa_exib_para_real and j3 in mapa_exib_para_real and j4 in mapa_exib_para_real:
                if "Selecione..." not in [d1, d2, d3, d4, c1, c2, c3, c4]:
                    st.divider()
                    st.subheader("Resultado do Confronto de Duplas")
                    vencedor_dupla = st.radio("Qual dupla venceu o confronto?", ["DUPLA A", "DUPLA B"], key="rad_vencedor_dupla")
                    pts_vencedor = 400 if local_partida == "PRESENCIAL" else 200
                    pts_perdedor = 200 if local_partida == "PRESENCIAL" else 100
                    if st.button("Gravar Resultado das Duplas", key="btn_salvar_duplas"):
                        detalhes = [
                            {"Jogador": j1, "Deck": f"{d1} ({c1})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA A" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA A"},
                            {"Jogador": j2, "Deck": f"{d2} ({c2})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA A" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA A"},
                            {"Jogador": j3, "Deck": f"{d3} ({c3})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA B" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA B"},
                            {"Jogador": j4, "Deck": f"{d4} ({c4})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA B" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA B"}
                        ]
                        novo_id = salvar_partida(local_partida, modo_partida, 4, detalhes)
                        nova_linha = pd.DataFrame([{"ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": 4, "Detalhes_Pontuacao": detalhes}])
                        st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                        for key in ["dupla_j1","dupla_d1","dupla_c1","dupla_j2","dupla_d2","dupla_c2","dupla_j3","dupla_d3","dupla_c3","dupla_j4","dupla_d4","dupla_c4"]:
                            if key in st.session_state: del st.session_state[key]
                        st.session_state.mensagem_sucesso_partida = "Resultado de duplas gravado com sucesso!"
                        st.rerun()
                else:
                    st.info("Aguardando a seleção de todos os integrantes, decks e comandantes para liberar a gravação...")
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
                        deck_escolhido = st.selectbox(f"Deck do Jogador {i+1}:", ["Selecione..."] + list(st.session_state.jogadores[real_key]["decks"].keys()), key=f"solo_d_{i}")
                        if deck_escolhido != "Selecione...":
                            dk_obj = st.session_state.jogadores[real_key]["decks"][deck_escolhido]
                            opcoes_cmd = [dk_obj["comandante_primario"], dk_obj["comandante_secundario"]]
                            if dk_obj.get("comandante_adicional"):
                                opcoes_cmd.append(dk_obj["comandante_adicional"])
                            cmd_escolhido = st.selectbox(f"Comandante do Jogador {i+1}:", ["Selecione..."] + opcoes_cmd, key=f"solo_c_{i}")
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
                            "PRESENCIAL": {5:[400,300,200,100,50], 4:[400,300,200,100], 3:[200,100,50], 2:[100,50]},
                            "SPELLTABLE": {5:[300,200,100,50,25], 4:[200,100,50,25], 3:[100,50,20], 2:[50,25]}
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
                            for key in [f"solo_j_{i}", f"solo_d_{i}", f"solo_c_{i}"]:
                                if key in st.session_state: del st.session_state[key]
                        for pos in range(qtd_jogadores):
                            if f"colocacao_pos_{pos}" in st.session_state: del st.session_state[f"colocacao_pos_{pos}"]
                        st.session_state.mensagem_sucesso_partida = "Resultado Solo gravado com sucesso!"
                        st.rerun()
            else:
                st.info("Aguardando a seleção de todos os competidores, decks e comandantes ativos para liberar a classificação...")

# ===================== RANKING =====================
elif aba == "Ranking":
    st.header("Classificação e Estatísticas")
    if not st.session_state.partidas.empty:
        st.subheader("Filtros de Classificação")
        c1, c2, c3 = st.columns(3)
        with c1: f_local = st.selectbox("Local:", ["TODOS", "PRESENCIAL", "SPELLTABLE"])
        with c2: f_modo = st.selectbox("Modo:", ["TODOS", "SOLO", "DRAGÃO DE DUAS CABEÇAS"])
        with c3: f_tipo = st.selectbox("Ranking por:", ["Competidor", "Deck", "Comandante"])

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
                    dados_rank.append({"Competidor": nome_jogador, "Deck": deck_nome, "Comandante": cmd_nome, "Pontos": item.get("Pontos", 0)})

            df_rank = pd.DataFrame(dados_rank)
            coluna_escolhida = f_tipo
            df_final = df_rank.groupby(coluna_escolhida)["Pontos"].sum().reset_index().sort_values("Pontos", ascending=False)

            import plotly.express as px
            st.divider()
            fig = px.bar(df_final, x=coluna_escolhida, y="Pontos", color="Pontos",
                         color_continuous_scale="Viridis",
                         title=f"Ranking: {f_tipo} (Modo: {f_modo} | Local: {f_local})")
            fig.update_layout(xaxis={'categoryorder': 'total descending'})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma partida encontrada com estes filtros.")

        st.divider()
        st.subheader("Histórico de Partidas")
        for _, row in st.session_state.partidas.iterrows():
            with st.expander(f"Partida #{row['ID']} | {row['Local']} | {row['Modo']}"):
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
                                    novo_cmd = novos_comandantes[idx].strip()
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
