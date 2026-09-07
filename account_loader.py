import psycopg2


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="mygems",
        user="myuser",
        password="28116"
    )


# -----------------------------------------
# MODULE CONFIGURATION
# -----------------------------------------

MODULE_RULES = {

    "gold_purchase": {
        "type": "SUPPLIER",
        "subtypes": ["GOL/SIL"]
    },

    "stone_purchase": {
        "type": "SUPPLIER",
        "subtypes": ["DI/CS"]
    },

    "customer_sale": {
        "type": "CUSTOMER",
        "subtypes": []
    },

    "bank_payment": {
        "type": "BANK",
        "subtypes": []
    }
}


# -----------------------------------------
# LOAD ACCOUNTS
# -----------------------------------------

def load_accounts(module_name):

    config = MODULE_RULES.get(module_name)

    if not config:
        return []

    try:

        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT DISTINCT a.short_name
            FROM accounts a
            JOIN account_types at
                ON a.type_id = at.type_id
            LEFT JOIN account_sub_types ast
                ON a.subtype_id = ast.sub_type_id
            WHERE UPPER(at.type_name) = %s
        """

        params = [config["type"].upper()]

        # SUBTYPE FILTER
        if config["subtypes"]:

            placeholders = ",".join(["%s"] * len(config["subtypes"]))

            query += f"""
                AND UPPER(ast.sub_type_name)
                IN ({placeholders})
            """

            params.extend(
                [s.upper() for s in config["subtypes"]]
            )

        query += """
            ORDER BY a.short_name
        """

        cur.execute(query, params)

        data = [
            r[0].strip().upper()
            for r in cur.fetchall()
            if r[0]
        ]

        conn.close()

        return data

    except Exception as e:
        print("LOAD ACCOUNT ERROR:", e)
        return []