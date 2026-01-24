import os
import streamlit
import pymysql
from pymysql import MySQLError
from dotenv import load_dotenv

def create_connection():
    try:
        load_dotenv()
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "rdx_dash"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            connect_timeout=5,
            cursorclass=pymysql.cursors.Cursor,
            autocommit=False
        )
        return conn
    except MySQLError as e:
        streamlit.error(f"Erro ao conectar ao banco: {e}")
        return None

def create_table(conn):
    if conn is None:
        return False

    create_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
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
        );
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute(create_table_sql)
        conn.commit()
        return True
    except MySQLError as e:
        streamlit.error(e)
        return False

def update_value(conn, table, key, value, username):
    if conn is None:
        return 0

    sql = f"UPDATE {table} SET {key}=%s WHERE user_email=%s;"
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (value, username))
        conn.commit()
        return cursor.rowcount
    except MySQLError:
        return 0


def get_user_info(conn, key, table, user_email):
    if conn is None:
        return []

    query = f"SELECT {key} FROM {table} WHERE user_email=%s"
    with conn.cursor() as cursor:
        cursor.execute(query, (user_email,))
        return cursor.fetchall()


def get_user_info_by_id(conn, key, table, user_id):
    if conn is None:
        return []

    query = f"SELECT {key} FROM {table} WHERE id=%s"
    with conn.cursor() as cursor:
        cursor.execute(query, (user_id,))
        return cursor.fetchall()

# ==========================================================
# NOVAS FUNÇÕES PARA A PÁGINA ADMIN
# ==========================================================

def get_all_users(conn):
    if conn is None:
        return []

    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT * FROM users ORDER BY id DESC;")
        return cursor.fetchall()

def count_active_users(conn):
    if conn is None:
        return 0

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE contract_status='active';"
        )
        return cursor.fetchone()[0]

def insert_new_user(conn, name, email, password, salt, status):
    if conn is None:
        return None

    sql = """
        INSERT INTO users 
        (user_name, user_email, password, salt, contract_status)
        VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (name, email, password, salt, status))
        conn.commit()
        return cursor.lastrowid

def update_user_status(conn, user_email, new_status):
    if conn is None:
        return 0

    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET contract_status=%s WHERE user_email=%s",
            (new_status, user_email)
        )
        conn.commit()
        return cursor.rowcount



def delete_user(conn, user_email):
    if conn is None:
        return 0

    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM users WHERE user_email=%s",
            (user_email,)
        )
        conn.commit()
        return cursor.rowcount