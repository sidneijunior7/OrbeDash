import streamlit as st
import time
import hashlib
from include import users_database as udb
from include.password_reset import forgot_password
from streamlit_extras.stylable_container import stylable_container
st.write(st.session_state)
def update_login_cookies():
    from streamlit_cookies_controller import CookieController
    controller = CookieController()
    # Salvar no cookie
    controller.set('logged_in', True)
    controller.set('user_email', st.session_state['user_email'])
    controller.set('expiration', st.session_state['expiration'])
    controller.set('access_lvl', st.session_state['access_lvl'])

def hash_data(data, salt):
    combined = (salt + data).encode()
    hashed_data = hashlib.sha256(combined).hexdigest()
    return hashed_data

def stream(text):
    for chunk in text:
        yield str(chunk)
        time.sleep(0.006)

def verify_password(conn, email, password):
    cursor = conn.cursor()
    cursor.execute("SELECT password, salt FROM users WHERE user_email = %s", (email,))
    result = cursor.fetchone()
    cursor.close()
    if result:
        stored_hash, salt = result
        hashed_password = hash_data(password, salt)
        return hashed_password == stored_hash
    else:
        st.error('Erro ao conectar com o banco de dados')
        return False

def login():
    """Returns `True` if the user had a correct password."""
    exp_time = 60*12  # Session Expiration Time in Minutes

    text = '''Faça login para acessar sua conta e explorar todas as funcionalidades que oferecemos.'''

    def login_form():
        """Form with widgets to collect user information"""
        st.image(r'images/logo_white.png', width=230)
        #st.write('# TradeMetric')
        st.write('## Bem-vindo')

        #st.divider()
        colf1, colf3 = st.columns([0.6 , 0.3], gap='large')
        with colf1:
            st.write_stream(stream(text))
        with colf3:
            if st.button(label=':material/build: Esqueci a Senha', type='tertiary'):
                forgot_password()
        with st.form("Credentials"):
            st.text_input("Email", key="user_email")
            st.text_input("Senha", type="password", key="password")
            st.form_submit_button("Entrar", on_click=password_entered, type='primary')


    def password_entered():
        """Checks whether a password entered by the user is correct."""
        conn = udb.create_connection()

        if verify_password(conn, st.session_state["user_email"], st.session_state["password"]):
            st.session_state["logged_in"] = True

            st.session_state["email"] = st.session_state["user_email"]
            st.session_state['access_lvl'] = udb.get_user_info(conn, 'access_lvl', 'users', st.session_state['user_email'])[0][0]
            st.session_state['contract_status'] = \
            udb.get_user_info(conn, 'contract_status', 'users', st.session_state['user_email'])[0][0]
            st.session_state["expiration"] = time.time() + (60 * exp_time)
            st.session_state['user_id'] = udb.get_user_info(conn, 'id', 'users', st.session_state.user_email)[0][0]
            del st.session_state["password"]  # Don't store the password.
            update_login_cookies()
            conn.close()
        else:
            st.session_state["logged_in"] = False
            st.session_state["user_email"] = ""
            st.session_state["expiration"] = 0
            st.error('Erro: Credenciais Incorretas.')
            conn.close()


    # Return True if the user is validated and the session is still valid
    if st.session_state.get("logged_in") and st.session_state.get("expiration", 0) > time.time():
        return True

    # Show inputs for username + password.
    login_form()
    if "logged_in" in st.session_state:
        return False

def credentials_authorize():
    if 'cookies' not in st.session_state or st.session_state.cookies is None or 'logged_in' not in st.session_state:
        return False
    else:
        # Verificar expiração
        expiration = st.session_state.cookies.get("expiration", 0)
        if expiration == 0 or not expiration or expiration <= time.time() or st.session_state.logged_in==False:
            st.session_state.cookies["logged_in"] = False
            st.session_state.cookies["user_email"] = ""
            return False
        else:
            return True

#===============================================================+
#           INICIO DO CÓDIGO                                    +
#===============================================================+

# Função para carregar o CSS
def load_css(file_path):
    with open(file_path, "r") as f:
        css_content = f.read()
    return f"<style>{css_content}</style>"
css = load_css('styles/login.css')
st.markdown(css,unsafe_allow_html=True)
#st.write(st.session_state)
cole, colc, cold = st.columns([0.3, 0.4, 0.3], gap='large')

with colc:
    # Coluna central
    with stylable_container(key='login', css_styles='{}'):

        if not credentials_authorize():
            if not login():
                st.stop()
        else:
            st.switch_page('app_tv.py')

