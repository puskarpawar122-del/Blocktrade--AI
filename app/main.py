from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext
import sqlite3, os, re, secrets, time
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "blocktrade.db")
app = FastAPI(title="BlockTrade AI Demo")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("BLOCKTRADE_SESSION_SECRET", "change-this-demo-secret-before-deployment"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PRICES = {"ETH": 3148.64, "USDC": 1.0, "BTC": 67432.12}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL, pan_status TEXT NOT NULL DEFAULT 'Not verified',
            pan_masked TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, txid TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL, token_from TEXT, token_to TEXT, amount_from REAL, amount_to REAL,
            status TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS lending(
            user_id INTEGER PRIMARY KEY, collateral REAL NOT NULL DEFAULT 800, borrowed REAL NOT NULL DEFAULT 273.44,
            FOREIGN KEY(user_id) REFERENCES users(id))""")

init_db()

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid: return None
    with db() as c:
        row = c.execute("SELECT id,name,email,created_at,pan_status,pan_masked,bio FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None



def page(request: Request, name: str, **ctx):
    user = current_user(request)
    context = {"request": request, "user": user, **ctx}
    template = templates.get_template(name)
    html = template.render(context)
    return HTMLResponse(content=html)


def require_user(request: Request):
    u = current_user(request)
    if not u:
        return None
    return u

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    with db() as c:
        count = c.execute("SELECT COUNT(*) n FROM transactions WHERE user_id=?", (u["id"],)).fetchone()["n"]
        lend = c.execute("SELECT collateral,borrowed FROM lending WHERE user_id=?", (u["id"],)).fetchone()
    if not lend:
        with db() as c:
            c.execute("INSERT OR IGNORE INTO lending(user_id) VALUES(?)", (u["id"],))
        lend = {"collateral":800, "borrowed":273.44}
    return page(request, "dashboard.html", active="Dashboard", tx_count=count, lending=dict(lend), prices=PRICES)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request): return RedirectResponse("/", status_code=303)
    return page(request, "auth.html", mode="login", error=None)

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    with db() as c:
        user = c.execute("SELECT id,password_hash FROM users WHERE lower(email)=lower(?)", (email.strip(),)).fetchone()
    if not user or not pwd_context.verify(password, user["password_hash"]):
        return page(request, "auth.html", mode="login", error="Email or password is incorrect.")
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if current_user(request): return RedirectResponse("/", status_code=303)
    return page(request, "auth.html", mode="register", error=None)

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    name, email = name.strip(), email.strip().lower()
    if len(name) < 2 or len(password) < 8:
        return page(request, "auth.html", mode="register", error="Enter a name and a password of at least 8 characters.")
    try:
        with db() as c:
            cur = c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                (name, email, pwd_context.hash(password), now()))
            uid = cur.lastrowid
            c.execute("INSERT INTO lending(user_id) VALUES(?)", (uid,))
        request.session["user_id"] = uid
        return RedirectResponse("/", status_code=303)
    except sqlite3.IntegrityError:
        return page(request, "auth.html", mode="register", error="An account with this email already exists.")

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/swap", response_class=HTMLResponse)
def swap_page(request: Request):
    if not require_user(request): return RedirectResponse("/login", status_code=303)
    return page(request, "swap.html", active="Swap", prices=PRICES)

@app.post("/swap")
def swap(request: Request, token_from: str = Form(...), token_to: str = Form(...), amount: float = Form(...)):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    if token_from not in PRICES or token_to not in PRICES or token_from == token_to or amount <= 0 or amount > 1e12:
        return RedirectResponse("/swap?error=invalid", status_code=303)
    received = round(amount * PRICES[token_from] / PRICES[token_to] * 0.999, 8)
    txid = "DEMO-" + secrets.token_hex(6).upper()
    with db() as c:
        c.execute("""INSERT INTO transactions(user_id,txid,kind,token_from,token_to,amount_from,amount_to,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", (u["id"], txid, "Swap", token_from, token_to, amount, received, "Simulated", now()))
    return RedirectResponse("/transactions?created=1", status_code=303)

@app.get("/lending", response_class=HTMLResponse)
def lending_page(request: Request):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    with db() as c:
        l = c.execute("SELECT collateral,borrowed FROM lending WHERE user_id=?", (u["id"],)).fetchone()
    return page(request, "lending.html", active="Lending", lending=dict(l))

@app.post("/lending/action")
def lending_action(request: Request, action: str = Form(...), amount: float = Form(...)):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    if amount <= 0 or amount > 1e9: return RedirectResponse("/lending?error=amount", status_code=303)
    with db() as c:
        row = c.execute("SELECT collateral,borrowed FROM lending WHERE user_id=?", (u["id"],)).fetchone()
        collateral, borrowed = float(row["collateral"]), float(row["borrowed"])
        if action == "deposit": collateral += amount
        elif action == "borrow":
            if borrowed + amount > collateral * 0.75: return RedirectResponse("/lending?error=ltv", status_code=303)
            borrowed += amount
        elif action == "repay": borrowed = max(0, borrowed - amount)
        else: return RedirectResponse("/lending?error=action", status_code=303)
        c.execute("UPDATE lending SET collateral=?,borrowed=? WHERE user_id=?", (collateral, borrowed, u["id"]))
        c.execute("INSERT INTO transactions(user_id,txid,kind,token_from,token_to,amount_from,amount_to,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (u["id"], "DEMO-"+secrets.token_hex(6).upper(), action.title(), "USD", "USD", amount, amount, "Simulated", now()))
    return RedirectResponse("/lending?success=1", status_code=303)

@app.get("/reputation", response_class=HTMLResponse)
def reputation(request: Request):
    if not require_user(request): return RedirectResponse("/login", status_code=303)
    return page(request, "reputation.html", active="Reputation")

@app.get("/transactions", response_class=HTMLResponse)
def transactions(request: Request):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    with db() as c:
        rows = c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],)).fetchall()
    return page(request, "transactions.html", active="Transactions", transactions=[dict(r) for r in rows])

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    return page(request, "profile.html", active="Profile", success=request.query_params.get("success"), pan_error=request.query_params.get("pan_error"))

@app.post("/profile/update")
def profile_update(request: Request, name: str = Form(...), bio: str = Form("")):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    with db() as c:
        c.execute("UPDATE users SET name=?,bio=? WHERE id=?", (name.strip()[:80], bio.strip()[:240], u["id"]))
    return RedirectResponse("/profile?success=profile", status_code=303)

@app.post("/profile/pan-demo")
def pan_demo(request: Request, pan: str = Form(...), consent: str = Form(None)):
    u = require_user(request)
    if not u: return RedirectResponse("/login", status_code=303)
    # Only format-check and simulate; do not store the submitted PAN.
    pan = pan.strip().upper()
    if consent != "yes" or not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        return RedirectResponse("/profile?pan_error=format", status_code=303)
    masked = pan[:2] + "*****" + pan[-1]
    with db() as c:
        c.execute("UPDATE users SET pan_status='Demo verified (simulated)',pan_masked=? WHERE id=?", (masked, u["id"]))
    return RedirectResponse("/profile?success=pan", status_code=303)

@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    if not require_user(request): return RedirectResponse("/login", status_code=303)
    return page(request, "settings.html", active="Settings")

@app.get("/health")
def health():
    return {"status":"ok", "mode":"demo", "blockchain":"not_connected", "pan_verification":"simulated"}
