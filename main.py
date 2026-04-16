from fastapi import FastAPI
import requests
import re
from collections import Counter
from datetime import datetime, timedelta
import threading
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://byte-income.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================
SUBREDDITS = ["worldnews", "technology", "business", "investment"]
POST_LIMIT = 25
CACHE_TTL = timedelta(minutes=30)

TRACKED_KEYWORDS = {
    "fomc", "rate cut", "inflation", "fed",
    "gold", "silver", "oil", "crude",
    "war", "conflict", "china", "russia",
    "recession", "cpi", "dxy", "treasury yields"
}

WEIGHTS = {
    "fomc": 5,
    "rate cut": 5,
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
    "dxy": 5,
    "cpi": 3,
    "treasury yields": 4,
}

STOPWORDS = {
    "the","is","in","on","at","of","and","a","to","for","with","as","by","an",
    "be","are","was","that","this","it","from","into","about","over","after",
    "before","between","while","said","says","will","has","have","had","not",
    "but","they","them","their","you","your","i","we","he","she", "what", "more", 
    "less", "business", "high", "low", "medium"
}

NOISE_WORDS = {
    "new","thread","post","reddit","comment","video","live","update","breaking"
}

# =========================
# CACHE
# =========================
cache = {"data": None, "timestamp": None}
lock = threading.Lock()

HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
}

# =========================
# HELPERS
# =========================

def is_valid_word(w: str) -> bool:
    return (
        w not in STOPWORDS and
        w not in NOISE_WORDS and
        len(w) > 3 and
        w.isalpha()
    )


def extract_words(texts):
    words = []

    for t in texts:
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', t.lower())
        words.extend([w for w in tokens if is_valid_word(w)])

    return words


def fetch_reddit(sub: str):
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={POST_LIMIT}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            print(f"[WARN] {sub} blocked: {res.status_code}")
            return []

        data = res.json()
        return [
            p["data"]["title"]
            for p in data.get("data", {}).get("children", [])
            if p.get("data", {}).get("title")
        ]

    except Exception as e:
        print(f"[ERROR] {sub}: {e}")
        return []


def get_all_titles():
    titles = []

    for sub in SUBREDDITS:
        titles.extend(fetch_reddit(sub))

    return list(set(titles))


def compute_keywords(titles):
    words = extract_words(titles)
    counter = Counter(words)

    return counter.most_common(5)


# =========================
# CORE ENGINE
# =========================

def fetch_trends():
    titles = get_all_titles()

    top_keywords = compute_keywords(titles)

    return {
        "top_keywords": top_keywords,
        "generated_at": datetime.utcnow().isoformat()
    }


# =========================
# CACHE HANDLER
# =========================

def get_cached_trends():
    with lock:
        now = datetime.utcnow()

        if cache["data"] and cache["timestamp"]:
            if now - cache["timestamp"] < CACHE_TTL:
                return cache["data"]

        cache["data"] = fetch_trends()
        cache["timestamp"] = now

        return cache["data"]


# =========================
# API
# =========================

@app.get("/trends")
def trends():
    return get_cached_trends()


@app.get("/health")
@app.head("/health")  # Add this line to support HEAD requests
def health():
    return {
        "status": "ok",
        "cache_exists": cache["data"] is not None,
        "last_updated": cache["timestamp"],
        "uptime": "running"
    }