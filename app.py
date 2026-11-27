import os, sqlite3, uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from gradio_client import Client, handle_file

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "static" / "uploads"
RESULT_DIR = BASE / "static" / "results"
DB_PATH = BASE / "bloomfit.db"
ALLOWED = {"png", "jpg", "jpeg", "webp"}
MAX_BYTES = 12 * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS profiles(
            user_id INTEGER PRIMARY KEY, profile_json TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS wardrobe(
            id INTEGER PRIMARY KEY, user_id INTEGER, filename TEXT NOT NULL)""")

def allowed_file(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED

def save_image(file, folder):
    if not file or not file.filename or not allowed_file(file.filename):
        raise ValueError("Upload a PNG, JPG or WEBP image.")
    data = file.read()
    if len(data) > MAX_BYTES:
        raise ValueError("Each image must be 12 MB or smaller.")
    file.stream.seek(0)
    try:
        im = Image.open(file.stream)
        im.verify()
    except Exception:
        raise ValueError("The uploaded file is not a valid image.")
    file.stream.seek(0)
    name = f"{uuid.uuid4().hex}.{file.filename.rsplit('.',1)[1].lower()}"
    path = folder / name
    file.save(path)
    return path

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/auth/demo")
def demo_auth():
    data = request.get_json(silent=True) or {}
    email, password = (data.get("email") or "").strip().lower(), data.get("password") or ""
    if "@" not in email or len(password) < 1:
        return jsonify(error="Enter a valid email and password."), 400
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            if not check_password_hash(row["password_hash"], password):
                return jsonify(error="Incorrect password for this email."), 401
            user_id = row["id"]
        else:
            cur = con.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",
                              (email, generate_password_hash(password)))
            user_id = cur.lastrowid
    session["user_id"] = user_id
    return jsonify(ok=True, message="Account ready")

@app.post("/api/profile")
def save_profile():
    if not session.get("user_id"):
        return jsonify(error="Please sign in first."), 401
    import json
    data = request.get_json(silent=True) or {}
    with db() as con:
        con.execute("""INSERT INTO profiles(user_id,profile_json) VALUES(?,?)
        ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json""",
                    (session["user_id"], json.dumps(data)))
    return jsonify(ok=True)

@app.post("/api/wardrobe")
def wardrobe_upload():
    if not session.get("user_id"):
        return jsonify(error="Please sign in first."), 401
    files = request.files.getlist("images")
    if not files:
        return jsonify(error="Choose at least one image."), 400
    saved = 0
    try:
        for f in files:
            path = save_image(f, UPLOAD_DIR)
            with db() as con:
                con.execute("INSERT INTO wardrobe(user_id,filename) VALUES(?,?)",
                            (session["user_id"], path.name))
            saved += 1
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, saved=saved)

@app.post("/api/tryon")
def virtual_tryon():
    person = request.files.get("person_image")
    garment = request.files.get("garment_image")
    description = (request.form.get("description") or "clothing item").strip()[:180]
    category = request.form.get("category", "overall")
    if category not in {"upper", "lower", "overall"}:
        category = "overall"
    try:
        person_path = save_image(person, UPLOAD_DIR)
        garment_path = save_image(garment, UPLOAD_DIR)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # Free community-hosted IDM-VTON Space. It may queue, sleep, or enforce daily GPU limits.
    try:
        client = Client("Nymbo/Virtual-Try-On")
        person_editor = {
            "background": handle_file(str(person_path)),
            "layers": [],
            "composite": None
        }
        result = client.predict(
            person_editor,
            handle_file(str(garment_path)),
            description,
            True,       # automatic mask
            False,      # no auto crop
            30,         # denoising steps
            42,         # seed
            api_name="/tryon"
        )
        # Nymbo's Space returns (generated image, mask preview).
        output = result[0] if isinstance(result, (tuple, list)) else result
        if isinstance(output, dict):
            output = output.get("path") or output.get("url")
        if not output or not Path(str(output)).exists():
            # Gradio may return a remote URL instead of a local path.
            if isinstance(output, str) and output.startswith("http"):
                import requests
                r = requests.get(output, timeout=60)
                r.raise_for_status()
                result_name = f"{uuid.uuid4().hex}.png"
                result_path = RESULT_DIR / result_name
                result_path.write_bytes(r.content)
            else:
                raise RuntimeError("The model returned no image. Try a clearer full-body photo.")
        else:
            result_name = f"{uuid.uuid4().hex}.png"
            result_path = RESULT_DIR / result_name
            Image.open(output).convert("RGB").save(result_path)
        return jsonify(ok=True, result_url=url_for("static", filename=f"results/{result_name}"))
    except Exception as e:
        app.logger.exception("Virtual try-on inference failed")
        return jsonify(error=f"Free AI model is unavailable or busy: {type(e).__name__}. Please retry later. Details: {str(e)[:240]}"), 503

@app.get("/api/health")
def health():
    return jsonify(status="ok", virtual_tryon_provider="Nymbo/Virtual-Try-On", note="Free community Space; availability and queue are not guaranteed.")

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
