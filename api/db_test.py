import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "ai_cost"),
    user=os.getenv("DB_USER", "ai_user"),
    password=os.getenv("DB_PASSWORD", "ai_password"),
)

cur = conn.cursor()
cur.execute("SELECT NOW();")
print("Connected OK, DB time:", cur.fetchone())
cur.close()
conn.close()
