import streamlit as st
import time

st.set_page_config(layout='wide', page_title='RDX Dashboard')

pg1 = st.Page(page='login.py',        title='Login',             url_path='login',        icon=":material/login:")
pg2 = st.Page(page='app_tv.py',       title='Dashboard',         url_path='dash',         icon=':material/leaderboard:')
pg3 = st.Page(page='admin.py',        title='Admin',             url_path='admin',        icon=':material/manage_accounts:')

from streamlit_cookies_controller import CookieController
cookie_manager = CookieController()

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

if credentials_authorize():
    if 'access_lvl' in st.session_state and st.session_state["access_lvl"] == 'Admin':
        pg = st.navigation(
            {"Páginas" : [pg1, pg2, pg3]}
            )
    else:
        pg = st.navigation(
            {"Páginas" : [pg1, pg2]}
            )
else:
    pg = st.navigation(
        {"Páginas": [pg1, pg2]}
    )

pg.run()