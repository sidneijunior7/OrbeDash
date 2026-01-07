import streamlit as st
from streamlit_cookies_controller import CookieController
import include.users_database as udb
import hashlib, secrets, time

cookie_manager = CookieController()


# -------------------------------------------------------------------
# FUNÇÃO DE LOGOUT
# -------------------------------------------------------------------
def logout():
    cookie_manager.set('user_id', 0)
    cookie_manager.set('user_email', None)
    cookie_manager.set('expiration', 0)

    with st.spinner("#### Encerrando Sessão ..."):
        time.sleep(2)

    st.rerun()

def credentials_authorize():
    # Restaurar informações de cookies
    st.session_state["logged_in"] = cookie_manager.get("logged_in")
    st.session_state["user_email"] = cookie_manager.get("user_email")
    st.session_state.email = cookie_manager.get('user_email')
    st.session_state.user_id = cookie_manager.get('user_id')
    st.session_state["expiration"] = cookie_manager.get("expiration")
    # Verificar expiração
    expiration = st.session_state.get("expiration", 0)
    if expiration == 0 or not expiration or expiration <= time.time():
        st.session_state["logged_in"] = False
        st.session_state["user_email"] = ""
        return False
    else:
        return True

if st.sidebar.button("Logout", icon=':material/logout:', type='primary'):
    logout()

if not credentials_authorize():
    st.switch_page('login.py')
# -------------------------------------------------------------------
# BLOQUEIO DE ACESSO PARA NÃO-ADMIN
# -------------------------------------------------------------------
if "access_lvl" not in st.session_state or st.session_state.access_lvl != "Admin":
    st.error("Você não tem permissão para acessar esta página.")
    st.stop()

# -------------------------------------------------------------------
# CONEXÃO MYSQL
# -------------------------------------------------------------------
conn = udb.create_connection()
if not conn:
    st.error("Erro ao conectar ao banco MySQL.")
    st.stop()

# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
name = udb.get_user_info(conn, "user_name", "users", st.session_state.user_email)[0][0]

st.sidebar.write(f"👋 Bem-vindo, {(name.split()[0]).capitalize()}")



# -------------------------------------------------------------------
# TÍTULO
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# SEÇÃO 1 — RESUMO
# -------------------------------------------------------------------
st.subheader("Resumo do sistema")

all_users = udb.get_all_users(conn)
active_users = udb.count_active_users(conn)

colA, colB = st.columns(2)
colA.metric("Usuários cadastrados", len(all_users))
colB.metric("Usuários ativos", active_users)

with colA:
    with st.container(horizontal=True):
        # -------------------------------------------------------------------
        # SEÇÃO 2 — ADICIONAR NOVO USUÁRIO
        # -------------------------------------------------------------------
        @st.dialog('Criador de usuários', width='large')
        def criar_novo_usuario():
            with st.form("create_new_user_form"):
                new_name = st.text_input("Nome completo")
                new_email = st.text_input("Email")
                new_password = st.text_input("Senha", type="password")
                #new_contract_id = st.text_input("Contract ID")
                new_status = st.selectbox("Status inicial", ["active", "revoked"])

                submitted = st.form_submit_button("Criar usuário")

                if submitted:
                    if not new_name or not new_email or not new_password:
                        st.error("Preencha todos os campos obrigatórios.")
                    else:
                        salt = secrets.token_hex(16)
                        hashed = hashlib.sha256((salt+new_password).encode()).hexdigest()

                        result = udb.insert_new_user(
                            conn, new_name, new_email, hashed, salt, new_status
                        )

                        if result:
                            st.success(f"Usuário **{new_name}** criado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro ao criar usuário!")
        if st.button('Criar usuário', type="primary"):
            criar_novo_usuario()

        # -------------------------------------------------------------------
        # SEÇÃO 3 — GERENCIAR USUÁRIO
        # -------------------------------------------------------------------
        @st.dialog('Gerenciador de Usuários', width='large')
        def gerenciar_usuario():
            emails = [u["user_email"] for u in all_users]
            selected_email = st.selectbox("Selecione um usuário", emails)

            if selected_email:
                usr = [u for u in all_users if u["user_email"] == selected_email][0]

                st.write(f"**Nome:** {usr['user_name']}")
                st.write(f"**Status atual:** `{usr['contract_status']}`")
                st.write("")

                col1, col2, col3 = st.columns(3)

                # ---------- ATIVAR ----------
                if col1.button("Liberar acesso", key="liberar"):
                    udb.update_user_status(conn, selected_email, "active")
                    st.success("Acesso liberado!")
                    st.rerun()

                # ---------- REVOGAR ----------
                if col2.button("Revogar acesso", key="revogar"):
                    udb.update_user_status(conn, selected_email, "revoked")
                    st.warning("Acesso revogado!")
                    st.rerun()

                # ---------- APAGAR ----------
                if col3.button("🗑 Apagar usuário", key="delete"):
                    udb.delete_user(conn, selected_email)
                    st.error("Usuário removido!")
                    st.rerun()
        if st.button('Gerenciar Usuários', type="primary"):
            gerenciar_usuario()

st.divider()
# -------------------------------------------------------------------
# SEÇÃO 4 — LISTA DE USUÁRIOS
# -------------------------------------------------------------------
st.subheader("Usuários cadastrados")

expanded = st.expander("📋 Visualizar tabela completa", expanded=True)
with expanded:
    st.dataframe(
        [{k: v for k, v in user.items() if k != "password" and k != "salt"}
         for user in all_users],
        use_container_width=True
    )


