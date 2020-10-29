import os

CLOSE = 2

ROWS = 6
COLUMNS = int(24 / ROWS)

DB_PATH = os.getenv('DB_PATH', 'basic_app.sqlite')