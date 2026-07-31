FORBIDDEN = [
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "SHUTDOWN",
]

class SQLValidator:

    @staticmethod
    def validate(sql):

        sql_upper = sql.upper()

        for keyword in FORBIDDEN:

            if keyword in sql_upper:
                raise Exception(f"{keyword} is not allowed")

        return sql