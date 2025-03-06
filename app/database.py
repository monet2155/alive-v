import psycopg2
from .config import DATABASE_URL

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
