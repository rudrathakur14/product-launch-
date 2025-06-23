from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from rembg import remove
import sqlite3, os, traceback

app = Flask(__name__)
app.secret_key = "super-secret"

UPLOAD_FOLDER = "static/uploads"
PROCESSED_FOLDER = "static/passports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

ADMIN_EMAIL = "anvehsingh0612@gmail.com"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, username, email, password_hash, registered_on=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.registered_on = registered_on

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return User(*row) if row else None

def get_user_by_email(email):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return User(*row) if row else None

def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            registered_on TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

if not os.path.exists("users.db"):
    init_db()

STYLE = """
<style>
  * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
  body { margin: 0; background: #f0f4f8; color: #2d3436; padding: 20px; }
  h1 { text-align: center; margin: 20px 0 30px; font-size: 2rem; }
  .box {
    background: #ffffff;
    max-width: 480px;
    margin: 0 auto 30px;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    text-align: center;
  }
  form { margin-top: 10px; }
  input[type="file"], input[type="email"], input[type="password"], input[name="username"], button {
    width: 100%; padding: 12px 14px; font-size: 1rem; margin: 10px 0;
    border-radius: 8px; border: 1px solid #ccc;
  }
  button {
    background: #0077ff; color: white; border: none;
    font-weight: 600; cursor: pointer; transition: background 0.3s ease;
  }
  button:hover { background: #005fd1; }
  a { color: #0077ff; text-decoration: none; }
  img {
    width: 100%; max-width: 400px; margin-top: 20px;
    border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  .footer {
    text-align: center; font-size: 0.9em;
    margin-top: 40px; color: #a4a4a4;
  }
  @media (max-width: 480px) {
    h1 { font-size: 1.5rem; }
    .box { padding: 18px; }
    button { font-size: 0.95rem; }
    img { max-width: 100%; }
  }
</style>
"""

HOME_HTML = STYLE + """
<h1>🪪 Passport Photo Generator</h1>
{% if current_user.is_authenticated %}
  <div class='box'>
    <p>Welcome, <b>{{ current_user.username }}</b></p>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="photo" accept="image/*" required><br>
      <button type="submit">Upload & Convert</button>
    </form>
    {% if uploaded %}
      <p>Your uploaded image:</p>
      <img src="{{ uploaded_url }}" alt="Uploaded Image">
      <p>Passport Size Photo (600x600, background removed):</p>
      <img src="{{ processed_url }}" alt="Passport Photo">
      <a href="{{ processed_url }}" download><button>Download Passport Photo</button></a>
    {% endif %}
    <p><a href="/logout">Logout</a></p>
    {% if current_user.email == admin %}
      <p><a href="/admin">View All Users</a></p>
    {% endif %}
  </div>
{% else %}
  <div class='box'>
    <p><a href='/login'>Login</a> or <a href='/register'>Register</a> to get started!</p>
  </div>
{% endif %}
<div class="footer">Contact: <a href="mailto:anvehsingh0612@gmail.com">anvehsingh0612@gmail.com</a></div>
"""

REGISTER_HTML = STYLE + """
<h2>Create Account</h2>
<div class='box'>
  <form method="post">
    <input name="username" placeholder="Username" required>
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password" required>
    <button type="submit">Register</button>
  </form>
  <p>Have an account? <a href="/login">Login</a></p>
</div>
"""

LOGIN_HTML = STYLE + """
<h2>Login</h2>
<div class='box'>
  <form method="post">
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>
  <p>No account? <a href="/register">Register</a></p>
</div>
"""

@app.route('/')
def home():
    uploaded = session.pop('uploaded', False)
    uploaded_file = session.pop('uploaded_file', None)
    processed_file = session.pop('processed_file', None)
    uploaded_url = url_for('static', filename='uploads/' + uploaded_file) if uploaded_file else None
    processed_url = url_for('static', filename='passports/' + processed_file) if processed_file else None
    return render_template_string(HOME_HTML, uploaded=uploaded, uploaded_url=uploaded_url, processed_url=processed_url, admin=ADMIN_EMAIL)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name, email = request.form['username'], request.form['email']
        pwd_hash = generate_password_hash(request.form['password'])
        try:
            conn = sqlite3.connect("users.db")
            conn.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (name, email, pwd_hash))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Email already registered."
    return render_template_string(REGISTER_HTML)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = get_user_by_email(request.form['email'])
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect('/')
        return "Invalid login."
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    try:
        file = request.files.get('photo')
        if not file:
            return "No file uploaded", 400

        filename = secure_filename(current_user.username + '_' + file.filename)
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(img_path)

        processed_filename = "passport_" + current_user.username + ".jpg"
        processed_path = os.path.join(PROCESSED_FOLDER, processed_filename)

        with Image.open(img_path) as im:
            im = im.convert("RGBA")
            bg_removed = remove(im)
            resized = bg_removed.resize
