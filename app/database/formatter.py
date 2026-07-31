class ResponseFormatter:

    @staticmethod
    def format(rows):
        if not rows:
            return "No records found."

        return rows