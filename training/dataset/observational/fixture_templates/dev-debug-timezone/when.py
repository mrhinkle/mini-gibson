from datetime import datetime, timezone
def epoch_to_iso(ts):
    # BUG: naive local assumption; tests expect UTC Z
    return datetime.fromtimestamp(ts).isoformat()
