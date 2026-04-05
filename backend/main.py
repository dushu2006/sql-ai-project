import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import uuid
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import jwt
from contextlib import asynccontextmanager
import aiosqlite
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# --------------------------------------------------------------
# Settings (via .env or defaults)
# --------------------------------------------------------------
settings = {
    'db_path': 'retail.db',
    'memory_db_path': 'memory.db',
    'ollama_url': 'http://localhost:11434/api/generate',
    'model': 'gpt-oss:120b-cloud',
    'max_memory': 20,
    'secret_key': 'your-secret-key-change-in-production',
    'algorithm': 'HS256',
    'access_token_expire_minutes': 1440,
    'use_redis': False,
    'redis_url': 'redis://localhost:6379',
    'environment': 'development'
}

DB_PATH = settings['db_path']
MEMORY_DB_PATH = settings['memory_db_path']
OLLAMA_URL = settings['ollama_url']
MODEL = settings['model']
MAX_MEMORY = settings['max_memory']
SECRET_KEY = settings['secret_key']
ALGORITHM = settings['algorithm']
ACCESS_TOKEN_EXPIRE_MINUTES = settings['access_token_expire_minutes']
USE_REDIS = settings['use_redis']
REDIS_URL = settings['redis_url']

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------
# limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])
app = FastAPI(title="Retail AI Assistant", version="5.0")
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --------------------------------------------------------------
# CSP header (covers everything the UI loads)
# --------------------------------------------------------------
@app.middleware("http")
async def csp_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000 https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com blob:; "
        "worker-src 'self' blob:"
    )
    return response

# --------------------------------------------------------------
# Validation error handler
# --------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Validation error: %s", exc.errors(), exc_info=True)
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# --------------------------------------------------------------
# Global error handling (preserves status codes)
# --------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {exc}", exc_info=True)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "chat",
                "message": exc.detail if isinstance(exc.detail, str) else "A server error occurred.",
                "sql": None,
                "data": None,
                "chart": None,
                "insights": None,
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "type": "chat",
            "message": "A server error occurred. Please try again.",
            "sql": None,
            "data": None,
            "chart": None,
            "insights": None,
        },
    )

# --------------------------------------------------------------
# Cache (Redis if you enable it, otherwise a tiny in‑memory fallback)
# --------------------------------------------------------------
class MemoryCache:
    def __init__(self):
        self._cache = {}

    async def get(self, key: str) -> Optional[str]:
        return self._cache.get(key)

    async def setex(self, key: str, seconds: int, value: str):
        self._cache[key] = value

    async def close(self):
        pass


redis_client = None
if USE_REDIS:
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("Redis cache enabled")
    except Exception as exc:
        logger.warning(f"Redis init failed → using memory cache: {exc}")
        redis_client = MemoryCache()
else:
    redis_client = MemoryCache()
    logger.info("Using in‑memory cache")

# --------------------------------------------------------------
# SQLite WAL mode (better concurrency)
# --------------------------------------------------------------
def enable_wal_mode():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.commit()
    except Exception as exc:
        logger.warning(f"Unable to enable WAL: {exc}")

# --------------------------------------------------------------
# Application lifespan (creates tables, pings cache)
# --------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    enable_wal_mode()
    init_memory_db()
    if redis_client and hasattr(redis_client, "ping"):
        try:
            await redis_client.ping()
        except Exception:
            pass
    logger.info("Application started")
    yield
    if redis_client:
        await redis_client.close()
    logger.info("Application shut down")

app.router.lifespan_context = lifespan

# --------------------------------------------------------------
# DB helpers (async where needed)
# --------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_memory_conn():
    conn = sqlite3.connect(MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def execute_sql_async(sql: str) -> List[Dict]:
    """Run a SELECT query (adds a safe LIMIT) using aiosqlite."""
    sql = sql.rstrip(";")
    if "LIMIT" not in sql.upper() and "SELECT" in sql.upper():
        sql += " LIMIT 1000"
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(sql) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        logger.error(f"SQL error: {exc}")
        raise HTTPException(status_code=400, detail=f"SQL error: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected SQL error: {exc}")
        raise HTTPException(status_code=500, detail="Internal query error")

# --------------------------------------------------------------
# Memory (conversation) handling
# --------------------------------------------------------------
def init_memory_db():
    with get_memory_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                bookmarked INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Backward‑compatibility – ignore error if column already exists
        try:
            conn.execute("ALTER TABLE session_memory ADD COLUMN bookmarked INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON session_memory(session_id)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboards (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get_memory(session_id: str) -> List[Dict]:
    """Return the most recent MAX_MEMORY rows for a session (chronological order)."""
    with get_memory_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, role, content, bookmarked
            FROM session_memory
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, MAX_MEMORY),
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "role": r[1], "content": r[2], "bookmarked": bool(r[3])}
            for r in rows
        ]


def filter_memory(memory: List[Dict]) -> List[Dict]:
    """Keep only user messages and assistant messages that are proper JSON."""
    filtered = []
    for m in memory:
        if m["role"] == "user":
            filtered.append(m)
        elif m["role"] == "assistant":
            try:
                content = json.loads(m["content"])
                if content.get("type") in ["chat", "intent"]:
                    filtered.append(m)
            except json.JSONDecodeError:
                pass
    return filtered


def update_memory(session_id: str, user_msg: str, assistant_msg: Dict):
    """
    Store a *minimal* representation of the assistant reply – only type + short
    text, never the huge data payloads.
    """
    clean = {
        "type": assistant_msg.get("type", "chat"),
        "content": assistant_msg.get("message") or assistant_msg.get("explanation") or "",
    }
    with get_memory_conn() as conn:
        conn.execute(
            "INSERT INTO session_memory (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "user", user_msg),
        )
        conn.execute(
            "INSERT INTO session_memory (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "assistant", json.dumps(clean)),
        )
        conn.commit()


# --------------------------------------------------------------
# Schema helpers (cached)
# --------------------------------------------------------------
_SCHEMA_CACHE = None


def get_schema() -> str:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE:
        return _SCHEMA_CACHE
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    schemas = [row[0] for row in cur.fetchall()]
    conn.close()
    _SCHEMA_CACHE = "\n".join(schemas)
    return _SCHEMA_CACHE


def get_sample_data() -> str:
    """3 rows per table – helps the LLM understand column formatting."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row[0] for row in cur.fetchall()]
    samples = []
    for tbl in tables:
        try:
            cur.execute(f"SELECT * FROM {tbl} LIMIT 3;")
            rows = [dict(r) for r in cur.fetchall()]
            samples.append(f"Table: {tbl}\nSamples: {json.dumps(rows)}")
        except Exception:
            pass
    conn.close()
    return "\n\n".join(samples)


# --------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------
def validate_sql(sql: str) -> bool:
    sql_clean = re.sub(r"--.*", "", sql)
    sql_clean = re.sub(r"/\*.*?\*/", "", sql_clean, flags=re.DOTALL)
    sql_clean = sql_clean.strip().upper()
    if not (sql_clean.startswith("SELECT") or sql_clean.startswith("WITH")):
        return False
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
    if any(word in sql_clean for word in forbidden):
        return False
    return True


def is_simple_list_query(sql: str) -> bool:
    sql_up = sql.upper().strip()
    if not sql_up.startswith("SELECT"):
        return False
    if "GROUP BY" in sql_up or "JOIN" in sql_up:
        return False
    if any(agg in sql_up for agg in ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]):
        return False
    return True


# --------------------------------------------------------------
# Prompt / LLM helpers
# --------------------------------------------------------------
def handle_special_questions(question: str) -> Optional[Dict]:
    q = question.lower().strip()
    if any(k in q for k in ["present date", "current date", "today's date", "what is the date"]):
        now = datetime.now()
        return {
            "type": "chat",
            "message": f"Today's date is {now.strftime('%B %d, %Y')}.",
            "sql": None,
            "data": None,
            "chart": None,
            "insights": None,
        }
    if any(k in q for k in ["present time", "current time", "what is the time"]):
        now = datetime.now()
        return {
            "type": "chat",
            "message": f"The current time is {now.strftime('%I:%M %p')}.",
            "sql": None,
            "data": None,
            "chart": None,
            "insights": None,
        }
    return None

def get_top_customers_sql(question: str) -> Optional[str]:
    q = question.lower().strip()
    match = re.search(r"\btop\s+(\d+)\s+customers\b", q)
    limit = int(match.group(1)) if match else 10
    if re.search(r"\btop\s+(\d+)?\s*customers\b", q):
        return f"""
            SELECT c.id, c.name, c.email, COALESCE(SUM(s.total_amount), 0) as total_spent
            FROM customers c
            LEFT JOIN sales s ON c.id = s.customer_id
            GROUP BY c.id
            ORDER BY total_spent DESC
            LIMIT {limit}
        """
    return None


def sanitize_response_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("$", "₹")
    text = re.sub(r"\b(USD|dollars|USD dollars)\b", "rupees", text, flags=re.IGNORECASE)
    return text


SQL_SAFETY_OVERRIDES = {
    "list all customers": "SELECT * FROM customers",
    "show all customers": "SELECT * FROM customers",
    "get all customers": "SELECT * FROM customers",
    "list all workers": "SELECT * FROM workers",
    "show all workers": "SELECT * FROM workers",
    "list all employees": "SELECT * FROM workers",
    "show all products": "SELECT * FROM products",
    "list all products": "SELECT * FROM products",
    "show inventory": "SELECT * FROM products p JOIN stock s ON p.id = s.product_id",
}


def broaden_sql(sql: str) -> str:
    match = re.match(r"(SELECT\s+.*?\s+FROM\s+\w+)", sql, re.IGNORECASE)
    if match:
        return match.group(1)
    return sql


SYNONYMS = {
    "staff": "workers",
    "employee": "workers",
    "employees": "workers",
    "client": "customers",
    "clients": "customers",
    "buyer": "customers",
    "buyers": "customers",
    "order": "sales",
    "orders": "sales",
    "revenue": "total_amount",
    "earnings": "profit",
    "stock": "quantity",
}


def normalize_query(query: str) -> str:
    q = query.lower()
    for k, v in SYNONYMS.items():
        q = re.sub(rf"\b{k}\b", v, q)
    return q


def refine_chart(ai_chart: Optional[Dict], data: List[Dict]) -> Dict:
    if not data or not ai_chart or ai_chart.get("type") == "none":
        return {"type": "none"}
    cols = list(data[0].keys())
    chart_type = ai_chart.get("type", "bar")
    x = ai_chart.get("x")
    y = ai_chart.get("y")
    if x not in cols:
        x = next((c for c in cols if isinstance(data[0][c], str)), cols[0])
    if y not in cols:
        y = next((c for c in cols if isinstance(data[0][c], (int, float))), cols[1] if len(cols) > 1 else cols[0])
    return {"type": chart_type, "x": x, "y": y}


async def call_llm(prompt: str, json_mode: bool = True) -> Dict:
    """
    Calls Ollama. If ``json_mode`` is True the model is expected to return a JSON
    object; otherwise we just return its raw text.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            raw = resp.json().get("response", "")
            if not json_mode:
                return {"message": raw.strip()}
            # Grab the first JSON blob
            match = re.search(r"(\{.*\})", raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Fallback – strip markdown fences and try again
            clean = re.sub(r"^```json\s*", "", raw.strip())
            clean = re.sub(r"\s*```$", "", clean)
            return json.loads(clean)
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}")
        return {"error": True, "message": str(exc)}


async def generate_insights_agent(question: str, data: List[Dict]) -> str:
    prompt = f"""
You are a concise data analyst.
Give a very short (max 3‑sentence) insight for the question:

{question}

DATA (first 15 rows):
{json.dumps(data[:15])}

RULES:
- Use Indian Rupee (₹) for any money.
- No fluff, just facts.
"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            return sanitize_response_text(resp.json().get("response", "").strip())
    except Exception:
        return f"Found {len(data)} records."


# --------------------------------------------------------------
# Core orchestration – decides intent, builds / runs SQL, adds insights
# --------------------------------------------------------------
async def process_query(original_q: str, session_id: str, intent: str, is_new_topic: bool) -> Dict:
    try:
        # ---- special shortcuts (date / time) ----
        special = handle_special_questions(original_q)
        if special:
            return special

        # ---- HEURISTIC: top customers / products ----
        if intent in ["data", "analysis", "lookup"]:
            hardcoded_sql = get_top_customers_sql(original_q)
            if hardcoded_sql:
                data = await execute_sql_async(hardcoded_sql)
                result = {
                    "type": "data",
                    "sql": hardcoded_sql,
                    "data": data,
                    "message": f"Top customers by total spending:",
                    "chart": refine_chart({"type": "bar", "x": "name", "y": "total_spent"}, data) if data else None,
                    "insights": f"Found {len(data)} customers." if data else None,
                }
                update_memory(session_id, original_q, result)
                return result

        # ---- brand‑specific rule: “list all customer names starting with X” ----
        import re
        m = re.match(r"list all customer names starting with (\w)", original_q, re.IGNORECASE)
        if m:
            letter = m.group(1).upper()
            sql = f"SELECT name FROM customers WHERE name LIKE '{letter}%' ORDER BY name LIMIT 1000"
            data = await execute_sql_async(sql)
            return {
                "type": "data",
                "sql": sql,
                "data": data,
                "message": f"Customers whose names start with '{letter}':",
                "chart": None,
                "insights": f"Found {len(data)} customers.",
            }

        # ---- normal flow: gather memory ----
        memory = [] if is_new_topic else filter_memory(get_memory(session_id))

        # ---- intent handling ------------------------------------------------
        if intent == "chat":
            chat_prompt = f"""
You are a concise business assistant.
User asks: {original_q}

Give a short, professional answer (max 4‑5 sentences). No code, no charts.
"""
            llm_res = await call_llm(chat_prompt, json_mode=False)
            result = {
                "type": "chat",
                "message": llm_res.get("message", "I’m not sure how to help."),
                "sql": None,
                "data": None,
                "chart": None,
                "insights": None,
            }

        elif intent in ["data", "analysis", "lookup"]:
            schema = get_schema()
            samples = get_sample_data()
            sql_prompt = f"""
You are a senior SQL analyst. Use ONLY the schema below:

{schema}

RULES:
- Use LOWER(column) LIKE LOWER('%value%') for case‑insensitive searches.
- For "list all" / "show all" use SELECT * FROM <table>.
- When user asks for "top customers" without a metric, assume by total sales amount (join with sales table).
- For "top products", assume by quantity sold.
- The JSON you return must contain the keys: sql, explanation, chart (type,x,y).
- LIMIT results to 1000 rows.

Question: {original_q}
Sample data (to show value shapes):
{samples}
"""
            sql_res = await call_llm(sql_prompt, json_mode=True)

            # Fallback to heuristic if LLM fails
            if not sql_res.get("sql") or not validate_sql(sql_res.get("sql")):
                # Try heuristic again
                fallback_sql = get_top_customers_sql(original_q)
                if fallback_sql:
                    data = await execute_sql_async(fallback_sql)
                    result = {
                        "type": "data",
                        "sql": fallback_sql,
                        "data": data,
                        "message": "Top customers by total spending (fallback):",
                        "chart": refine_chart({"type": "bar", "x": "name", "y": "total_spent"}, data) if data else None,
                        "insights": f"Found {len(data)} customers." if data else None,
                    }
                    update_memory(session_id, original_q, result)
                    return result
                # Otherwise, fallback to chat
                result = {
                    "type": "chat",
                    "message": "I couldn't generate a valid query for that. Please rephrase or specify 'by revenue' or 'by number of orders'.",
                    "sql": None,
                    "data": None,
                    "chart": None,
                    "insights": None,
                }
            else:
                sql = sql_res["sql"]
                data = await execute_sql_async(sql)
                result = {
                    "type": intent,
                    "sql": sql,
                    "data": data,
                    "message": sql_res.get("explanation", ""),
                    "chart": refine_chart(sql_res.get("chart"), data),
                    "insights": None,
                }
                if data and not is_simple_list_query(sql):
                    result["insights"] = await generate_insights_agent(original_q, data)

        else:
            result = {
                "type": "chat",
                "message": "I don't understand.",
                "sql": None,
                "data": None,
                "chart": None,
                "insights": None,
            }

        # ---- normalise result & persist ----
        for key in ["sql", "data", "chart", "insights"]:
            if key not in result:
                result[key] = None
        result["message"] = sanitize_response_text(result.get("message", ""))
        update_memory(session_id, original_q, result)
        return result

    except Exception as exc:
        logger.error(f"process_query error: {exc}", exc_info=True)
        return {
            "type": "chat",
            "message": "I encountered an error while processing your request. Please try re‑phrasing.",
            "sql": None,
            "data": None,
            "chart": None,
            "insights": None,
        }
# --------------------------------------------------------------
# Authentication (JWT – optional, currently not enforced)
# -------------------------------------------------------------- – optional, currently not enforced)
# --------------------------------------------------------------
security = HTTPBearer(auto_error=False)  # allow anonymous for now


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.JWSError:
        return None


# --------------------------------------------------------------
# WebSocket manager (supports multiple tabs)
# --------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        conns = self.active_connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: dict):
        for ws in self.active_connections.get(session_id, []):
            await ws.send_json(message)


manager = ConnectionManager()


# --------------------------------------------------------------
# WebSocket endpoint (planner → orchestrator)
# --------------------------------------------------------------
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("question")
            if not question:
                continue

            await manager.send_message(session_id, {"type": "start", "message": "Analyzing query…"})

            # ----- planner (tiny prompt that just decides intent) -----
            planner_prompt = f"""
You are an AI system planner.

Classify the user query into one of:
- data
- analysis
- chat
- lookup

Rules:
- Queries like “how to increase sales”, “tips for my shop” → intent = "chat".
- Use "analysis" only when the user explicitly wants charts, trends, or comparative data.
- Return ONLY JSON: {{"intent":"...", "is_new_topic": true|false, "reason":"..."}}

Question: {question}
"""
            plan = await call_llm(planner_prompt, json_mode=True)
            intent = plan.get("intent", "chat")
            is_new_topic = plan.get("is_new_topic", False)

            # ----- full pipeline -----
            result = await process_query(question, session_id, intent, is_new_topic)

            await manager.send_message(session_id, {"type": "result", "payload": result})
            await manager.send_message(session_id, {"type": "end", "message": "Done"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)


# --------------------------------------------------------------
# REST API endpoints (query, export, bookmarks, dashboards, SSE)
# --------------------------------------------------------------
class DashboardModel(BaseModel):
    name: str
    session_id: str
    config: Dict[str, Any]
    id: Optional[str] = None


class Query(BaseModel):
    query: str
    session_id: Optional[str] = "default"


@app.post("/api/query")
# @limiter.limit("20/minute")
async def query_endpoint(request: Request, q: Query, user: str = Depends(get_current_user)):
    # -------- planner (same as WS) --------
    planner_prompt = f"""
You are an AI system planner.

Classify the user query into one of:
- data
- analysis
- chat
- lookup

Rules:
- Queries like “how to increase sales”, “tips for my shop” → intent = "chat".
- Use "analysis" only when the user explicitly wants charts, trends, or comparative data.
- Return ONLY JSON: {{"intent":"...", "is_new_topic": true|false, "reason":"..."}}

Question: {q.query}
"""
    plan = await call_llm(planner_prompt, json_mode=True)
    if plan.get("error"):
        return await process_query(q.query, q.session_id, "chat", False)

    intent = plan.get("intent", "chat")
    is_new_topic = plan.get("is_new_topic", False)

    # ----- simple memory‑based cache key -----
    mem_hash = hashlib.md5(str(get_memory(q.session_id)).encode()).hexdigest()
    cache_key = hashlib.sha256(f"{q.query}:{intent}:{mem_hash}".encode()).hexdigest()
    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    result = await process_query(q.query, q.session_id, intent, is_new_topic)

    if redis_client:
        await redis_client.setex(cache_key, 300, json.dumps(result))

    return result


@app.post("/api/bookmark/toggle")
async def toggle_bookmark(payload: Dict[str, Any]):
    chat_id = payload.get("chat_id")
    message_id = payload.get("message_id")
    message_index = payload.get("message_index")
    if not chat_id or (message_id is None and message_index is None):
        raise HTTPException(status_code=400, detail="chat_id and message_id/message_index required")
    with get_memory_conn() as conn:
        cur = conn.cursor()
        if message_id is not None:
            cur.execute(
                "SELECT id, bookmarked FROM session_memory WHERE session_id = ? AND id = ?",
                (chat_id, message_id),
            )
        else:
            cur.execute(
                "SELECT id, bookmarked FROM session_memory WHERE session_id = ? ORDER BY timestamp ASC LIMIT 1 OFFSET ?",
                (chat_id, int(message_index)),
            )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        new_flag = 0 if row[1] else 1
        conn.execute("UPDATE session_memory SET bookmarked = ? WHERE id = ?", (new_flag, row[0]))
        conn.commit()
    return {"bookmarked": bool(new_flag), "id": row[0]}


@app.get("/api/export/{chat_id}")
async def export_chat(chat_id: str):
    with get_memory_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT content FROM session_memory WHERE session_id = ? AND role = 'assistant'",
            (chat_id,),
        )
        rows = cur.fetchall()
    all_data = []
    for r in rows:
        try:
            content = json.loads(r[0])
            if isinstance(content, dict) and isinstance(content.get("data"), list):
                all_data.extend(content["data"])
        except json.JSONDecodeError:
            continue
    if not all_data:
        raise HTTPException(status_code=404, detail="No tabular data found for this chat")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=all_data[0].keys())
    writer.writeheader()
    writer.writerows(all_data)
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={chat_id}_export.csv"},
    )


@app.post("/api/dashboard/save")
async def save_dashboard(dashboard: DashboardModel):
    dash_id = dashboard.id or str(uuid.uuid4())
    with get_memory_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO dashboards
            (id, session_id, name, config_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (dash_id, dashboard.session_id, dashboard.name, json.dumps(dashboard.config)),
        )
        conn.commit()
    return {"id": dash_id, "session_id": dashboard.session_id, "name": dashboard.name, "config": dashboard.config}


@app.get("/api/dashboards/{session_id}")
async def list_dashboards(session_id: str):
    with get_memory_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, created_at, updated_at FROM dashboards WHERE session_id = ? ORDER BY updated_at DESC",
            (session_id,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows
    ]


@app.get("/api/dashboard/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    with get_memory_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, session_id, name, config_json, created_at, updated_at FROM dashboards WHERE id = ?",
            (dashboard_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {
        "id": row[0],
        "session_id": row[1],
        "name": row[2],
        "config": json.loads(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
    }


@app.delete("/api/dashboard/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    with get_memory_conn() as conn:
        conn.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
        conn.commit()
    return {"deleted": True}


@app.get("/api/dashboard-data")
async def get_dashboard_data():
    conn = get_conn()
    cur = conn.cursor()
    # Mock data to demonstrate chart dynamic render
    try:
        cur.execute("SELECT COUNT(*) FROM customers")
        user_count = cur.fetchone()[0] or 1240
    except: user_count = 1240
    
    try:
        cur.execute("SELECT COUNT(*) FROM sales")
        order_count = cur.fetchone()[0] or 320
    except: order_count = 320
    
    conn.close()
    
    return {
        "stats": {
            "users": user_count,
            "orders": order_count
        },
        "salesTrend": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "data": [12, 19, 30, 25]
        },
        "profitLoss": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "data": [
                 {"o":4,"h":6,"l":3,"c":5},
                 {"o":-1,"h":1,"l":-3,"c":-2},
                 {"o":5,"h":9,"l":4,"c":8},
                 {"o":3,"h":6,"l":2,"c":4}
            ]
        }
    }

@app.get("/api/dashboard/stream")
async def dashboard_stream(request: Request):
    async def generator():
        while True:
            if await request.is_disconnected():
                break
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT SUM(total_amount) FROM sales WHERE date_time >= date('now', '-30 days')"
            )
            rev_30 = cur.fetchone()[0] or 0
            cur.execute(
                "SELECT COUNT(*) FROM sales WHERE date_time >= datetime('now', '-1 hour')"
            )
            orders_last_hour = cur.fetchone()[0] or 0
            conn.close()
            data = {
                "revenue_30d": rev_30,
                "orders_last_hour": orders_last_hour,
                "timestamp": datetime.now().isoformat(),
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(generator(), media_type="text/event-stream")


# --------------------------------------------------------------
# Serve static files (includes index.html)
# --------------------------------------------------------------
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("templates/index.html")


# --------------------------------------------------------------
# Run server
# --------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["."],
        reload_excludes=[".venv", "__pycache__", "retail.db", "memory.db", "*.log"],
    )
