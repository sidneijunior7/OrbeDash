import mysql.connector, os
import streamlit
from mysql.connector import Error

def create_connection():
    conn = None
    try:
        conn = mysql.connector.connect(
            host='localhost' if os.getenv("MYSQL_HOST") is None else os.getenv("MYSQL_HOST"),# or 'localhost',  # Ex: 'localhost'
            user='root' if os.getenv("MYSQL_USER") is None else os.getenv("MYSQL_USER"),# or 'root',  # Ex: 'root'
            password='' if os.getenv("MYSQL_PASSWORD") is None else os.getenv("MYSQL_PASSWORD"),# or '',
            database='rdx_dash' if os.getenv("MYSQL_DATABASE") is None else os.getenv("MYSQL_DATABASE"),# or 'sap_wise_db',
            port=3306 if os.getenv("MYSQL_PORT") is None else os.getenv("MYSQL_PORT"),# or 3306
        )
        if conn.is_connected():
            return conn
    except Error as e:
        streamlit.error(e)
    return conn

def create_table(conn):
    create_table_sql = """ CREATE TABLE IF NOT EXISTS users (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                user_name VARCHAR(100) NOT NULL,
                                user_email VARCHAR(150) NOT NULL UNIQUE,
                                password VARCHAR(64) NOT NULL,
                                salt VARCHAR(32) NOT NULL,
                                contract_id VARCHAR(28) NOT NULL,
                                contract_status VARCHAR(20) NOT NULL,
                                profile_picture VARCHAR(150),
                                description VARCHAR(150),
                                token VARCHAR(50), 
                                exp_time DATETIME,
                                token_usado BOOLEAN DEFAULT TRUE
                            ); """
    cursor = conn.cursor()
    try:
        cursor.execute(create_table_sql)
        conn.commit()  # Commit the changes to the database
        return True
    except Error as e:
        return False  # Return False in case of an error
    finally:
        cursor.close()  # Close the cursor

def update_value(conn, table, key, value, username):
    sql = f'''UPDATE {table} SET {key} = %s WHERE user_email = %s;'''
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (value, username))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()  # Close the cursor

def get_user_info(conn, key, table, user_email):
    cursor = conn.cursor()
    try:
        query = f"SELECT {key} FROM {table} WHERE user_email=%s"
        cursor.execute(query, (user_email,))
        rows = cursor.fetchall()
        return rows
    finally:
        cursor.close()  # Close the cursor

def get_user_info_by_id(conn, key, table, user_id):
    cursor = conn.cursor()
    try:
        query = f"SELECT {key} FROM {table} WHERE id=%s"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        return rows
    finally:
        cursor.close()  # Close the cursor
# ==========================================================
# NOVAS FUNÇÕES PARA A PÁGINA ADMIN
# ==========================================================

def get_all_users(conn):
    """Retorna todos os usuários cadastrados."""
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users ORDER BY id DESC;")
        return cursor.fetchall()
    finally:
        cursor.close()


def count_active_users(conn):
    """Conta quantidade de usuários com contract_status='active'."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE contract_status='active';")
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def insert_new_user(conn, name, email, password, salt, status):
    """Insere novo usuário no sistema."""
    cursor = conn.cursor()
    sql = """INSERT INTO users (user_name, user_email, password, salt, 
                                contract_status)
             VALUES (%s, %s, %s, %s, %s)"""
    try:
        cursor.execute(sql, (name, email, password, salt, status))
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()


def update_user_status(conn, user_email, new_status):
    """Atualiza o status do usuário (active / revoked)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET contract_status=%s WHERE user_email=%s",
            (new_status, user_email)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()


def delete_user(conn, user_email):
    """Remove um usuário do banco."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_email=%s", (user_email,))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
