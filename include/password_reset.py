import os
import streamlit as st
import include.users_database as udb
import time, secrets, re, datetime, hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Função para gerar um token seguro
def gerar_token():
    return secrets.token_urlsafe(16)  # Gera um token seguro de 16 caracteres

def hash_data(data, salt):
    # Concatena o salt com os dados e converte para bytes
    combined = (salt + data).encode()
    # Gera o hash
    hashed_data = hashlib.sha256(combined).hexdigest()
    return hashed_data

def stream(text):
    for chunk in text:
        yield str(chunk)
        time.sleep(0.006)


def validar_token(email, token):
    """
    Valida o token de recuperação de senha.
    """
    # Limpar o email de espaços e forçar lowercase
    email = email.strip().lower()

    conn = udb.create_connection()
    cursor = conn.cursor()

    # Consulta o token, expiração e status de uso no banco de dados para o email
    consulta = """
        SELECT token, token_usado, exp_time
        FROM users 
        WHERE user_email = %s
    """
    cursor.execute(consulta, (email,))
    resultado = cursor.fetchone()

    # Fechar a conexão com o banco
    cursor.close()
    conn.close()

    # Verifica se o email foi encontrado
    if resultado is None:
        st.error("Email não encontrado no banco de dados.")
        return False

    # Token e status do banco de dados
    token_armazenado, token_usado, token_expiracao = resultado

    # Verificar se o token já foi usado
    if token_usado:
        st.error("Este token já foi usado.")
        return False

    # Verificar se o token no banco de dados corresponde ao token da URL
    if token_armazenado != token:
        st.error("Token inválido.")
        return False

    # Verificar expiração do token
    if datetime.datetime.now() > token_expiracao:
        st.error("Token expirado.")
        return False

    st.success("Token válido!")
    return True


def validar_senha(senha):
    """
    Função para validar a senha com base em vários critérios de segurança.

    Critérios:
    - Pelo menos 6 caracteres
    - Pelo menos uma letra maiúscula
    - Pelo menos uma letra minúscula
    - Pelo menos um número
    - Pelo menos um caractere especial (!, @, #, $, etc.)

    Retorna True se a senha for válida, senão retorna uma mensagem de erro.
    """
    if len(senha) < 6:
        return "A senha precisa ter pelo menos 6 caracteres."
    if not re.search(r'[A-Z]', senha):
        return "A senha precisa ter pelo menos uma letra maiúscula."
    if not re.search(r'[a-z]', senha):
        return "A senha precisa ter pelo menos uma letra minúscula."
    if not re.search(r'[0-9]', senha):
        return "A senha precisa ter pelo menos um número."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', senha):
        return "A senha precisa ter pelo menos um caractere especial."

    return True

def atualizar_senha():
    nova_senha = st.session_state.get('nova_senha')
    confirmar_senha = st.session_state.get('confirmar_senha')
    email = st.session_state.get('email')

    if nova_senha == confirmar_senha:
        if not validar_senha(nova_senha):
            st.warning(validar_senha(nova_senha))
            exibir_formulario_redefinicao()
        else:
            conn = udb.create_connection()
            salt = udb.get_user_info(conn, 'salt', 'users', email)[0][0]
            senha = hash_data(nova_senha,salt)
            rowcount = udb.update_value(conn, 'users', 'password', senha, email)
            st.write(f'Rowcount: {rowcount}')

            if rowcount == 0:
                st.error('Erro ao atualizar os dados no banco de dados.')
                conn.close()
            else:
                udb.update_value(conn, 'users', 'token_usado', True, email)
                st.success('Senha atualizada com sucesso')
                conn.close()
    else:
        st.error('As senhas digitadas devem ser iguais')
        exibir_formulario_redefinicao()

# Função para exibir o formulário de redefinição de senha
def exibir_formulario_redefinicao():
    with st.form('Reset'):
        st.text_input("Digite sua nova senha", type="password", key='nova_senha')
        st.text_input("Confirme a nova senha", type="password", key='confirmar_senha')
        st.form_submit_button(label="Enviar", type='primary', on_click=atualizar_senha)
    st.markdown('\n\n#### Critérios:\n\nPelo menos 6 caracteres\n\nPelo menos uma letra maiúscula\n\nPelo menos uma letra minúscula\n\nPelo menos um número\n\nPelo menos um caractere especial (!, @, #, $, etc.)')

def inserir_token_e_expiracao(email, token, exp_time, conn):
    cursor = conn.cursor()
    try:
        # Atualizar o token e a data de expiração no banco de dados
        consulta = """
            UPDATE users
            SET token = %s, exp_time = %s, token_usado = %s
            WHERE user_email = %s
        """
        # Converter para o formato aceito pelo MySQL
        exp_time_str = exp_time.strftime('%Y-%m-%d %H:%M:%S')

        # Executar a consulta com os parâmetros
        cursor.execute(consulta, (token, exp_time_str, False, email))

        # Salvar as mudanças no banco de dados
        conn.commit()

        # Verificar se a atualização ocorreu
        if cursor.rowcount > 0:
            print("Token e expiração inseridos com sucesso.")
        else:
            print("Email não encontrado ou não foi possível atualizar.")
    finally:
        cursor.close()


@st.dialog('Esqueci a Senha')
def forgot_password():
    def login_form():
        """Form with widgets to collect user information"""
        text = '''Fique em paz, vou te ajudar a recuperar a senha de sua conta.'''
        st.write_stream(stream(text))
        with st.form("Recovery"):
            st.text_input("Email", key="email")
            st.form_submit_button("Resgatar Senha", on_click=enviar_link_recuperacao, type='primary')

    def validar_email(email):
        regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return re.match(regex, email)

    def enviar_link_recuperacao():
        email = st.session_state["email"]
        if not validar_email(email):
            st.error("Por favor, insira um email válido.")
            return

        conn = udb.create_connection()
        id = buscar_id_por_email(email, conn)

        if id is not None:
            st.title('Redefinição de Senha')
            st.warning(f'O processo de redefinição de senha foi concluído, caso haja algum cadastro no email informado enviaremos um email com mais instruções para redefinir sua senha')
            token = gerar_token()
            exp_time = (datetime.datetime.now() + datetime.timedelta(minutes=15))
            _url = f'https://sapwise.com.br/?token={token}&email={email}&exptime={exp_time}'
            inserir_token_e_expiracao(email, token, exp_time, conn)
            conn.close()

            # Criação da mensagem
            mensagem = f'''
            <!DOCTYPE html>
            <html lang="pt">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Recuperação de Senha</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f9;
                        color: #333333;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 20px auto;
                        background: #ffffff;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        overflow: hidden;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        text-align: center;
                        padding: 20px;
                        font-size: 24px;
                    }}
                    .content {{
                        padding: 20px;
                    }}
                    .content p {{
                        line-height: 1.6;
                        color: #333;
                    }}
                    .btn {{
                        display: inline-block;
                        background-color: #4CAF50;
                        color: white !important;
                        text-decoration: none;
                        padding: 10px 20px;
                        border-radius: 5px;
                        margin-top: 20px;
                        font-size: 16px;
                    }}
                    .btn:hover {{
                        background-color: #45a049;
                    }}
                    .footer {{
                        text-align: center;
                        padding: 10px;
                        font-size: 12px;
                        color: #777777;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        Recuperação de Senha
                    </div>
                    <div class="content">
                        <p>Olá,</p>
                        <p>Você solicitou a recuperação de sua senha. Para redefinir sua senha, clique no botão abaixo:</p>
                        <a href="{_url}" class="btn">Redefinir Senha</a>
                        <p>Esse link será válidos por apenas 15 minutos,caso o link expire será necessário recomeçar o processo de redefinição de senha.</p>
                        <p>Se você não solicitou esta alteração, ignore este e-mail.</p>
                        <p>Atenciosamente,<br>Equipe SAPWise.</p>
                    </div>
                    <div class="footer">
                        <p>SAP Wise &copy; 2024. Todos os direitos reservados.</p>
                    </div>
                </div>
            </body>
            </html>
            '''

            # Configuração do e-mail
            email_msg = MIMEMultipart()
            email_msg['From'] = "noreply@sapwise.com.br"
            email_msg['To'] = email
            email_msg['Subject'] = "Recuperação de Senha | SAP Wise"
            email_msg.attach(MIMEText(mensagem, 'html'))  # Define o conteúdo como HTML

            # Envio do e-mail
            server = smtplib.SMTP_SSL('smtp.titan.email', 465)
            server.login("noreply@sapwise.com.br", os.getenv("EMAIL_PASSWORD") or st.secrets["EMAIL_PASSWORD"])
            server.sendmail(email_msg['From'], email_msg['To'], email_msg.as_string())
            server.quit()

        else:
            st.warning(f'O processo de redefinição de senha foi concluído, caso haja algum cadastro no email informado enviaremos um email com mais instruções para redefinir sua senha')

    login_form()

# Função para buscar o ID baseado no email
def buscar_id_por_email(email, conn):
    cursor = conn.cursor()
    consulta = "SELECT id FROM users WHERE user_email = %s"
    cursor.execute(consulta, (email,))
    resultado = cursor.fetchone()  # Pega uma linha
    cursor.close()
    if resultado:
        return resultado[0]  # Retorna o ID se encontrado
    else:
        return None  # Se o resultado estiver vazio, retorna None

