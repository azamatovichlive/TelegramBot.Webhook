import json, os
STATS_FILE = "data/stats.json"

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_stats(stats):
    os.makedirs("data", exist_ok=True)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def add_user_stat(user_id, text_count=0, file_count=0):
    stats = load_stats()
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {"texts": 0, "files": 0}
    stats[uid]["texts"] += text_count
    stats[uid]["files"] += file_count
    save_stats(stats)
