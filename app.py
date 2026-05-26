import streamlit as st
import pandas as pd
import os
import re
from streamlit_option_menu import option_menu

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão LCPC", layout="wide")

# --- INICIALIZAÇÃO DO BANCO DE DADOS (SESSION STATE) ---
if "jogadores" not in st.session_state:
    st.session_state.jogadores = {} # {nome: {"apelido": "", "telefone": "", "email": "", "foto_bytes": None, "decks": {}}}

if "partidas" not in st.session_state:
    st.session_state.partidas = pd.DataFrame(columns=["ID", "Local", "Modo", "Jogadores", "Detalhes_Pontuacao"])

if "mensagem_sucesso_partida" not in st.session_state:
    st.session_state.mensagem_sucesso_partida = None

# --- FUNÇÃO AUXILIAR: RETORNA O NOME DE EXIBIÇÃO (APELIDO OU NOME) ---
def obter_nome_exibicao(dados_jogador, nome_chave):
    if dados_jogador.get("apelido"):
        return dados_jogador["apelido"]
    return nome_chave

# --- BARRA LATERAL (LOGO E MENU) ---
formatos_logo = ["logo.jpg", "logo.jpeg", "logo.png", "logo.PNG", "logo.JPG", "logo.png.jpg"]
logo_encontrada = None

for nome_arquivo in formatos_logo:
    if os.path.exists(nome_arquivo):
        logo_encontrada = nome_arquivo
        break

if logo_encontrada:
    st.sidebar.image(logo_encontrada, use_container_width=True)

with st.sidebar:
    aba = option_menu(
        menu_title=None, # Título removido conforme solicitado
        options=["Home", "Cadastro", "Jogadores", "Decks", "Nova Partida", "Ranking"],
        icons=["house", "person-plus", "people", "card-list", "controller", "trophy"], 
        menu_icon=None,                
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "nav-link": {
                "font-size": "15px", 
                "text-align": "left", 
                "margin": "0px", 
                "background-color": "transparent",
                "color": "#888888"
            },
            "nav-link-selected": {
                "background-color": "transparent", 
                "color": "#FFFFFF", 
                "font-weight": "bold",
                "text-transform": "uppercase"
            }
        }
    )

# --- ESTRUTURA PRINCIPAL DAS ABAS ---
if aba == "Home":
    # Conteúdo da página inicial
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

elif aba == "Cadastro":
    st.header("Gerenciamento de Perfis")
    
    tab_criar, tab_editar, tab_excluir = st.tabs(["Novo Jogador", "Editar Perfil", "Excluir Jogador"])
    
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
            
            st.markdown("Foto do Jogador")
            foto = st.file_uploader("", type=["jpg", "png", "jpeg"], label_visibility="collapsed", key="file_cad_foto_real")
            
            st.markdown("<span style='color:red;'>* CAMPOS OBRIGATÓRIOS</span>", unsafe_allow_html=True)
            
            botao_salvar = st.form_submit_button("Salvar Cadastro")
            
            if botao_salvar:
                nome = nome.strip()
                telefone = telefone.strip()
                email = email.strip()
                erros = []
                
                if not nome or not telefone:
                    erros.append("Preencha todos os campos obrigatórios (Nome e Telefone).")
                if nome and not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", nome):
                    erros.append("O campo Nome não pode conter caracteres especiais ou números.")
                if telefone and not telefone.isdigit():
                    erros.append("O campo Telefone deve conter apenas números.")
                if email:
                    padrao_email = r"^[\w\.-]+@[\w\.-]+\.(com|com\.br)$"
                    if not re.match(padrao_email, email):
                        erros.append("O formato do E-mail é inválido. Deve conter '@' e terminar com '.com' ou '.com.br'.")
                
                if erros:
                    for erro in erros: st.error(erro)
                else:
                    if nome not in st.session_state.jogadores:
                        foto_bytes = foto.read() if foto else None
                        st.session_state.jogadores[nome] = {
                            "apelido": apelido, "telefone": telefone, "email": email, "foto_bytes": foto_bytes, "decks": {}
                        }
                        st.success(f"Jogador {apelido if apelido else nome} cadastrado com sucesso!")
                    else:
                        st.warning("Este jogador já está cadastrado!")

    with tab_editar:
        st.subheader("Editar Perfil Existente")
        if st.session_state.jogadores:
            opcoes_edicao = ["Selecione um jogador..."] + list(st.session_state.jogadores.keys())
            jog_editar_real = st.selectbox("Escolha o perfil que deseja alterar:", opcoes_edicao, key="sel_edit_jog")
            
            if jog_editar_real != "Selecione um jogador...":
                dados_edit = st.session_state.jogadores[jog_editar_real]
                novo_apelido = st.text_input("Editar Apelido", value=dados_edit["apelido"], key="txt_edit_apelido")
                novo_telefone = st.text_input("Editar Telefone", value=dados_edit["telefone"], key="txt_edit_telefone")
                novo_email = st.text_input("Editar E-mail", value=dados_edit["email"], key="txt_edit_email")
                nova_foto = st.file_uploader("Atualizar Foto", type=["jpg", "png", "jpeg"], key="file_edit_foto")
                
                if st.button("Salvar Alterações", key="btn_salvar_edit"):
                    novo_telefone = novo_telefone.strip()
                    novo_email = novo_email.strip()
                    erros_edit = []
                    
                    # Validação de Telefone
                    if not novo_telefone: 
                        erros_edit.append("O campo Telefone não pode ficar vazio.")
                    elif not novo_telefone.isdigit(): 
                        erros_edit.append("O campo Telefone deve conter apenas números.")
                    
                    # Validação de E-mail (Agora OBRIGATÓRIO)
                    padrao_email = r"^[\w\.-]+@[\w\.-]+\.(com|com\.br)$"
                    if not novo_email:
                        erros_edit.append("O campo E-mail não pode ficar vazio.")
                    elif not re.match(padrao_email, novo_email):
                        erros_edit.append("O formato do E-mail é inválido.")
                            
                    if erros_edit:
                        for err in erros_edit: st.error(err)
                    else:
                        st.session_state.jogadores[jog_editar_real]["apelido"] = novo_apelido
                        st.session_state.jogadores[jog_editar_real]["telefone"] = novo_telefone
                        st.session_state.jogadores[jog_editar_real]["email"] = novo_email
                        if nova_foto: st.session_state.jogadores[jog_editar_real]["foto_bytes"] = nova_foto.read()
                        st.success("Perfil atualizado!")
                        st.rerun()
        else:
            st.info("Nenhum jogador cadastrado para editar.")

    with tab_excluir:
        st.subheader("Remover Jogador da Liga")
        if st.session_state.jogadores:
            opcoes_exclusao = ["Selecione um jogador..."] + list(st.session_state.jogadores.keys())
            jog_excluir = st.selectbox("Escolha o perfil que deseja remover:", opcoes_exclusao, key="sel_excluir_jog")
            if jog_excluir != "Selecione um jogador...":
                st.warning(f"Atenção: Excluir {jog_excluir} removerá o perfil e seus decks.")
                if st.button("Confirmar Exclusão do Jogador", type="primary", key="btn_conf_excluir_jog"):
                    del st.session_state.jogadores[jog_excluir]
                    st.success("Jogador removido com sucesso!")
                    st.rerun()
        else:
            st.info("Nenhum jogador cadastrado.")

# --- ABA: JOGADORES (CONSULTA, DECKS E EDIÇÃO DE DECKS) ---
elif aba == "Jogadores":
    st.header("Perfis e Arsenal")
    if st.session_state.jogadores:
        opcoes_selectbox = {"Selecione um jogador...": "NEUTRO"}
        for n, dados in st.session_state.jogadores.items():
            opcoes_selectbox[obter_nome_exibicao(dados, n)] = n
            
        jogador_sel_exibicao = st.selectbox("Visualizar jogador:", list(opcoes_selectbox.keys()), key="sel_ver_jogador_real")
        
        if_valido_real = jogador_sel_exibicao != "Selecione um jogador..."
        if if_valido_real:
            jogador_real = opcoes_selectbox[jogador_sel_exibicao]
            dados_j = st.session_state.jogadores[jogador_real]
            
            col1, col2 = st.columns([1, 2])
            with col1:
                if dados_j["foto_bytes"]: st.image(dados_j["foto_bytes"], width=200, caption=f"Foto de {jogador_sel_exibicao}")
                else: st.info("Jogador não possui foto cadastrada.")
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
                        st.link_button(f"{nome_d.upper()} ({cmd_str})", info_d["url"], key=f"lnk_{nome_d}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # NOVA SEÇÃO: ABAS DE GERENCIAMENTO INTERNO DE DECKS (EDITAR E EXCLUIR)
                    tab_gerenciar_existentes, tab_remover_existente = st.tabs(["Editar Comandantes / Link", "Excluir Deck"])
                    
                    with tab_gerenciar_existentes:
                        opcoes_edit_dk = ["Selecione um deck para editar..."] + list(dados_j["decks"].keys())
                        dk_escolhido_edit = st.selectbox("Qual deck deseja alterar?", opcoes_edit_dk, key="sel_dk_gerenciamento_edit")
                        
                        if dk_escolhido_edit != "Selecione um deck para editar...":
                            dados_dk_edit = dados_j["decks"][dk_escolhido_edit]
                            
                            edit_cmd_p = st.text_input("Comandante Primário*", value=dados_dk_edit["comandante_primario"], key="txt_edit_cmd_p")
                            edit_cmd_s = st.text_input("Comandante Secundário*", value=dados_dk_edit["comandante_secundario"], key="txt_edit_cmd_s")
                            edit_cmd_a = st.text_input("Comandante Adicional (Opcional)", value=dados_dk_edit.get("comandante_adicional", ""), key="txt_edit_cmd_a")
                            edit_url_mox = st.text_input("Link do Moxfield*", value=dados_dk_edit["url"], key="txt_edit_url_mox")
                            
                            if st.button("Salvar Alterações do Deck", key="btn_confirmar_alteracoes_deck"):
                                if edit_cmd_p and edit_cmd_s and edit_url_mox:
                                    dados_j["decks"][dk_escolhido_edit] = {
                                        "comandante_primario": edit_cmd_p.strip(),
                                        "comandante_secundario": edit_cmd_s.strip(),
                                        "comandante_adicional": edit_cmd_a.strip() if edit_cmd_a else "",
                                        "url": edit_url_mox.strip()
                                    }
                                    st.success(f"Configurações do deck '{dk_escolhido_edit}' atualizadas!")
                                    st.rerun()
                                else:
                                    st.error("Campos com * são obrigatórios.")
                                    
                    with tab_remover_existente:
                        opcoes_deck = ["Selecione um deck..."] + list(dados_j["decks"].keys())
                        deck_excluir = st.selectbox("Escolha o deck para remover:", opcoes_deck, key="sel_dk_excluir_real")
                        if deck_excluir != "Selecione um deck...":
                            if st.button("Remover Este Deck", type="primary", key="btn_remover_dk_real"):
                                del dados_j["decks"][deck_excluir]
                                st.success(f"Deck '{deck_excluir}' removido com sucesso!")
                                st.rerun()
                else:
                    st.info("Sem decks vinculados no momento.")
                
                st.divider()
                if "mostrar_form_deck" not in st.session_state: st.session_state.mostrar_form_deck = False
                if not st.session_state.mostrar_form_deck:
                    if st.button("CADASTRAR NOVO DECK"):
                        st.session_state.mostrar_form_deck = True
                        st.rerun()
                else:
                    st.write("**Cadastrar Novo Deck**")
                    with st.form("form_adicionar_deck", clear_on_submit=True):
                        nome_deck = st.text_input("Nome do Deck Precon*:", key="txt_dk_nome")
                        cmd_p = st.text_input("Comandante Primário*:", key="txt_dk_cmd_p")
                        cmd_s = st.text_input("Comandante Secundário*:", key="txt_dk_cmd_s")
                        cmd_a = st.text_input("Comandante Adicional (Opcional):", key="txt_dk_cmd_a")
                        url_moxfield = st.text_input("Link do Moxfield*:", key="txt_dk_url")
                        
                        st.markdown("<span style='color:red;'>* Campos obrigatórios para o deck</span>", unsafe_allow_html=True)
                        
                        col_btn1, col_btn2 = st.columns([1, 4])
                        with col_btn1: botao_vinculo = st.form_submit_button("Vincular Deck")
                        with col_btn2:
                            if st.form_submit_button("Cancelar"):
                                st.session_state.mostrar_form_deck = False
                                st.rerun()
                        
                        if botao_vinculo:
                            if cmd_p and cmd_s and nome_deck and url_moxfield:
                                if nome_deck not in dados_j["decks"]:
                                    dados_j["decks"][nome_deck] = {
                                        "comandante_primario": cmd_p.strip(),
                                        "comandante_secundario": cmd_s.strip(),
                                        "comandante_adicional": cmd_a.strip() if cmd_a else "",
                                        "url": url_moxfield.strip()
                                    }
                                    st.success(f"Deck '{nome_deck}' adicionado com sucesso!")
                                    st.session_state.mostrar_form_deck = False
                                    st.rerun()
                                else: st.warning("Este deck já está cadastrado.")
                            else: st.error("Preencha Nome, Comandante Primário, Secundário e o Link.")
    else:
        st.info("Nenhum jogador cadastrado. Vá até a aba 'Cadastro' para começar.")

# --- ABA: DECKS (ARSENAL GERAL DA LIGA) ---
elif aba == "Decks":
    st.header("Arsenal Geral da LCPC")
    todos_os_decks = []
    for nome_jog, dados_jog in st.session_state.jogadores.items():
        exibicao_jog = obter_nome_exibicao(dados_jog, nome_jog)
        for nome_dk, info_dk in dados_jog["decks"].items():
            cmd_str = f"1º: {info_dk['comandante_primario']} | 2º: {info_dk['comandante_secundario']}"
            if info_dk.get("comandante_adicional"):
                cmd_str += f" | 3º: {info_dk['comandante_adicional']}"
                
            todos_os_decks.append({
                "Deck": nome_dk.upper(), "Comandantes": cmd_str, "Dono": exibicao_jog, "Link": info_dk["url"]
            })
            
    if todos_os_decks:
        df_decks = pd.DataFrame(todos_os_decks)
        st.subheader("Todos os Decks Cadastrados na Temporada")
        st.dataframe(df_decks[["Deck", "Comandantes", "Dono"]], use_container_width=True, hide_index=True)
        st.divider()
        st.write("**Acesso rápido às listas das mesas:**")
        for idx, dk in enumerate(todos_os_decks):
            st.link_button(f"{dk['Deck']} ({dk['Dono']})", dk['Link'], key=f"lnk_geral_{idx}")
    else:
        st.info("Nenhum deck foi cadastrado na liga ainda.")

# --- ABA: NOVA PARTIDA ---
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
        
        # --- LOGICA DE DUPLAS (SUPOSTA SELEÇÃO DE COMANDANTES) ---
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
                        if dk_obj.get("comandante_adicional"): opcoes_cmd.append(dk_obj["comandante_adicional"])
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
                        if dk_obj.get("comandante_adicional"): opcoes_cmd.append(dk_obj["comandante_adicional"])
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
                        if dk_obj.get("comandante_adicional"): opcoes_cmd.append(dk_obj["comandante_adicional"])
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
                        if dk_obj.get("comandante_adicional"): opcoes_cmd.append(dk_obj["comandante_adicional"])
                        c4 = st.selectbox("Comandante em Campo (J4):", ["Selecione..."] + opcoes_cmd, key="dupla_c4")
            
            if j1 in mapa_exib_para_real and j2 in mapa_exib_para_real and j3 in mapa_exib_para_real and j4 in mapa_exib_para_real:
                if "Selecione..." not in [d1, d2, d3, d4, c1, c2, c3, c4]:
                    st.divider()
                    st.subheader("Resultado do Confronto de Duplas")
                    vencedor_dupla = st.radio("Qual dupla venceu o confronto?", ["DUPLA A", "DUPLA B"], key="rad_vencedor_dupla")
                    
                    pts_vencedor = 400 if local_partida == "PRESENCIAL" else 200
                    pts_perdedor = 200 if local_partida == "PRESENCIAL" else 100
                    
                    if st.button("Gravar Resultado das Duplas", key="btn_salvar_duplas"):
                        # Registra o nome do deck concatenado ao comandante escolhido na rodada
                        detalhes = [
                            {"Jogador": j1, "Deck": f"{d1} ({c1})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA A" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA A"},
                            {"Jogador": j2, "Deck": f"{d2} ({c2})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA A" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA A"},
                            {"Jogador": j3, "Deck": f"{d3} ({c3})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA B" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA B"},
                            {"Jogador": j4, "Deck": f"{d4} ({c4})", "Pontos": pts_vencedor if vencedor_dupla == "DUPLA B" else pts_perdedor, "Vencedor": vencedor_dupla == "DUPLA B"}
                        ]
                        novo_id = len(st.session_state.partidas) + 1
                        nova_linha = pd.DataFrame([{
                            "ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": 4, "Detalhes_Pontuacao": detalhes
                        }])
                        st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                        
                        for key in ["dupla_j1", "dupla_d1", "dupla_c1", "dupla_j2", "dupla_d2", "dupla_c2", "dupla_j3", "dupla_d3", "dupla_c3", "dupla_j4", "dupla_d4", "dupla_c4"]:
                            if key in st.session_state: del st.session_state[key]
                        
                        st.session_state.mensagem_sucesso_partida = "Resultado de duplas gravado com sucesso!"
                        st.rerun()
            else:
                st.info("Aguardando a seleção de todos os integrantes, decks e comandantes para liberar a gravação...")

        # --- LOGICA SOLO ---
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
                            if dk_obj.get("comandante_adicional"): opcoes_cmd.append(dk_obj["comandante_adicional"])
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
                    txt_label = f"1º Lugar (Campeão):" if pos == 0 else f"{pos+1}º Lugar:"
                    escolha_colocacao = st.selectbox(txt_label, opcoes_pos, key=f"colocacao_pos_{pos}")
                    if escolha_colocacao in nomes_na_mesa:
                        coloca_ordem.append(escolha_colocacao)
                
                if len(coloca_ordem) == qtd_jogadores:
                    if st.button("Gravar Resultado Solo", key="btn_salvar_solo"):
                        
                        tabela_pontos = {
                            "PRESENCIAL": {
                                5: [400, 300, 200, 100, 50],
                                4: [400, 300, 200, 100],
                                3: [200, 100, 50],
                                2: [100, 50]
                            },
                            "SPELLTABLE": {
                                5: [300, 200, 100, 50, 25],
                                4: [200, 100, 50, 25],
                                3: [100, 50, 20],
                                2: [50, 25]
                            }
                        }
                        
                        detalhes_finais = []
                        for posicao_index, jog_nome in enumerate(coloca_ordem):
                            config_mesa = next(d for d in validos if d["Jogador"] == jog_nome)
                            pontos_obtidos = tabela_pontos[local_partida][qtd_jogadores][posicao_index]
                            
                            # Salva o nome do deck com o comandante da partida entre parênteses para computar a força dele no meta
                            nome_deck_completo = f"{config_mesa['Deck']} ({config_mesa['Comandante']})"
                            
                            detalhes_finais.append({
                                "Jogador": jog_nome, "Deck": nome_deck_completo, "Pontos": pontos_obtidos, "Vencedor": posicao_index == 0
                            })
                            
                        novo_id = len(st.session_state.partidas) + 1
                        nova_linha = pd.DataFrame([{
                            "ID": novo_id, "Local": local_partida, "Modo": modo_partida, "Jogadores": qtd_jogadores, "Detalhes_Pontuacao": detalhes_finais
                        }])
                        st.session_state.partidas = pd.concat([st.session_state.partidas, nova_linha], ignore_index=True)
                        
                        for i in range(qtd_jogadores):
                            if f"solo_j_{i}" in st.session_state: del st.session_state[f"solo_j_{i}"]
                            if f"solo_d_{i}" in st.session_state: del st.session_state[f"solo_d_{i}"]
                            if f"solo_c_{i}" in st.session_state: del st.session_state[f"solo_c_{i}"]
                        for pos in range(qtd_jogadores):
                            if f"colocacao_pos_{pos}" in st.session_state: del st.session_state[f"colocacao_pos_{pos}"]
                        
                        st.session_state.mensagem_sucesso_partida = "Resultado Solo gravado com sucesso!"
                        st.rerun()
            else:
                st.info("Aguardando a seleção de todos os competidores, decks e comandantes ativos para liberar a classificação...")

elif aba == "Ranking":
    st.header("Classificação e Estatísticas")
    
    if not st.session_state.partidas.empty:
        # Filtros Globais
        st.subheader("Filtros de Classificação")
        c1, c2, c3 = st.columns(3)
        with c1: f_local = st.selectbox("Local:", ["TODOS", "PRESENCIAL", "SPELLTABLE"])
        with c2: f_modo = st.selectbox("Modo:", ["TODOS", "SOLO", "DRAGÃO DE DUAS CABEÇAS"])
        with c3: f_tipo = st.selectbox("Ranking por:", ["Competidor", "Deck", "Comandante"])
        
        # Filtragem do DataFrame base
        df = st.session_state.partidas
        if f_local != "TODOS": df = df[df["Local"] == f_local]
        if f_modo != "TODOS": df = df[df["Modo"] == f_modo]
        
        if not df.empty:
            dados_rank = []
            for _, row in st.session_state.partidas.iterrows():
                for item in row["Detalhes_Pontuacao"]:
                    # Extração segura
                    deck_raw = item.get("Deck", "Desconhecido")
                    
                    # Tratamento de segurança para o nome do jogador
                    nome_jogador = item.get("Jogador", "Jogador Removido")
                    
                    # Separação Deck/Comandante com segurança
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
                        "Pontos": item.get("Pontos", 0)
                    })
            
            df_rank = pd.DataFrame(dados_rank)
            
            # Agrupa conforme o filtro
            col_map = {"Competidor": "Competidor", "Deck": "Deck", "Comandante": "Comandante"}
            coluna_escolhida = col_map[f_tipo]
            df_final = df_rank.groupby(coluna_escolhida)["Pontos"].sum().reset_index().sort_values("Pontos", ascending=False)
            
            # --- VISUALIZAÇÃO GRÁFICA ---
            import plotly.express as px
            
            st.divider()
            # Gráfico de barras
            fig = px.bar(
                df_final, 
                x=coluna_escolhida, 
                y="Pontos", 
                color="Pontos",
                color_continuous_scale="Viridis",
                title=f"Ranking: {f_tipo} (Modo: {f_modo} | Local: {f_local})"
            )
            fig.update_layout(xaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela abaixo do gráfico
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
                
                # Botões de Ação alinhados
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"Editar", key=f"edit_{row['ID']}"):
                        st.session_state.partida_em_edicao = row['ID']
                        st.rerun()
                with col_btn2:
                    if st.button(f"Excluir", key=f"del_{row['ID']}"):
                        st.session_state.partidas = st.session_state.partidas[st.session_state.partidas["ID"] != row["ID"]]
                        st.rerun()
    else:
        st.info("Nenhuma partida registrada nesta temporada da liga ainda.")
