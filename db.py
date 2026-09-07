import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="mygems",
        user="myuser",
        password="28116",
        port=5432
    )

# ---------------- HELPER FUNCTIONS ----------------

def fetch_all(query, params=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params or ())
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result


def execute(query, params=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()

        print("QUERY EXECUTED:", query)
        print("PARAMS:", params)

        cur.close()
        conn.close()

    except Exception as e:
        print("DB ERROR:", e)
        raise e
