from fastapi import FastAPI
import requests
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import threading

app = FastAPI()

# ==============================
# CONFIG
# ==============================

SUBREDDITS = ["worldnews", "technology", "business"]
POST_LIMIT = 20
CACHE_TTL = timedelta(minutes=30)

tracked_keywords = [
    "fomc", "rate cut", "interest rate", "inflation", "fed",
    "gold", "silver", "oil", "crude",
    "war", "conflict", "china", "russia", "recession"
]

weights = {
    "fomc": 5,
    "rate cut": 5,
    "interest rate": 4,
    "inflation": 4,
    "fed": 4,
    "war": 5,
    "conflict": 4,
    "gold": 3,
    "silver": 3,
    "oil": 3,
    "crude": 3,
    "china": 2,
    "russia": 2,
    "recession": 4
}

categories = {
    "monetary": ["fomc", "rate cut", "interest rate", "inflation", "fed"],
    "commodities": ["gold", "silver", "oil", "crude"],
    "geopolitics": ["war", "conflict", "china", "russia"],
    "economy": ["recession"]
}

stopwords = {
    "the","is","in","on","at","of","and","a","to","for","with","as","by","an","be","are","was"
}

ignore = {
    "says","said","new","will","after","over","more","has","have"
}

# ==============================
# CACHE
# ==============================

cache = {
    "data": None,
    "timestamp": None
}

lock = threading.Lock()

# ==============================
# CORE LOGIC
# ==============================

def fetch_trends():
    titles = []
    headers = {"User-Agent": "trend-app"}

    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={POST_LIMIT}"

        try:
            res = requests.get(url, headers=headers, timeout=10)
            data = res.json()

            for post in data["data"]["children"]:
                titles.append(post["data"]["title"])

        except Exception:
            continue

    titles = list(set(titles))

    # ================= GENERAL KEYWORDS =================
    words = []

    for title in titles:
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        filtered = [w for w in tokens if w not in stopwords and w not in ignore]
        words.extend(filtered)

    top_keywords = Counter(words).most_common(10)

    # ================= TRACKED KEYWORDS =================
    keyword_count = Counter()

    for title in titles:
        lower_title = title.lower()

        for kw in tracked_keywords:
            if re.search(rf'\b{re.escape(kw)}\b', lower_title):
                keyword_count[kw] += 1

    # ================= WEIGHTED SCORE =================
    keyword_score = {
        kw: count * weights.get(kw, 1)
        for kw, count in keyword_count.items()
    }

    sorted_keywords = sorted(keyword_score.items(), key=lambda x: x[1], reverse=True)

    # ================= CATEGORY SCORE =================
    category_score = defaultdict(int)

    for category, kws in categories.items():
        for kw in kws:
            category_score[category] += keyword_score.get(kw, 0)

    sorted_categories = sorted(category_score.items(), key=lambda x: x[1], reverse=True)

    return {
        "titles": titles[:20],
        "top_keywords": top_keywords,
        "tracked_keywords": dict(keyword_count),
        "weighted_keywords": sorted_keywords,
        "categories": sorted_categories,
        "generated_at": datetime.utcnow().isoformat()
    }

# ==============================
# CACHE HANDLER (30 min)
# ==============================

def get_cached_trends():
    with lock:
        now = datetime.utcnow()

        if cache["data"] and cache["timestamp"]:
            if now - cache["timestamp"] < CACHE_TTL:
                return cache["data"]

        # refresh cache
        data = fetch_trends()
        cache["data"] = data
        cache["timestamp"] = now

        return data

# ==============================
# API ENDPOINTS
# ==============================

@app.get("/trends")
def trends():
    return get_cached_trends()

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_exists": cache["data"] is not None,
        "last_updated": cache["timestamp"],
        "uptime": "running"
    }