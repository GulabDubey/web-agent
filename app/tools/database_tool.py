from app.database.schema_loader import SchemaLoader
from app.database.sql_generator import SQLGenerator
from app.database.validator import SQLValidator
from app.database.executor import QueryExecutor
from app.database.formatter import ResponseFormatter

generator = SQLGenerator()

def database_tool(message):

    schema = SchemaLoader.load()

    sql = generator.generate(message, schema)

    SQLValidator.validate(sql)

    rows = QueryExecutor.execute(sql)

    return ResponseFormatter.format(rows)