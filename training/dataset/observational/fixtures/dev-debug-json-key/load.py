import json
from pathlib import Path
def db_port():
    data=json.loads(Path('cfg.json').read_text())
    return data['database']['Port']  # BUG wrong case
