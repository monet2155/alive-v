import psycopg2
from psycopg2 import pool
from .config import DATABASE_URL

db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)


def get_connection():
    return db_pool.getconn()


def release_connection(conn):
    db_pool.putconn(conn)
