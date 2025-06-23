from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import sqlite3, os

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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body {
    font-family: 'Inter', sans-serif;
    background: #f9fbfd;
    margin: 0;
    padding: 20px;
    text-align: center;
    color: #2f3542;
  }
  h1, h2 { font-weight: 600; margin: 20px 0; }
  .box {
    background: #ffffff;
    padding: 28px;
    margin: 24px auto;
    max-width: 460px;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
  }
  input, button {
    width: 100%;
    padding: 14px;
    margin: 10px 0;
    border-radius: 8px;
    border: 1px solid #ccc;
    font-size: 16px;
    font-family: inherit;
  }
  input:focus, button:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(0,123,255,0.2);
  }
  button {
    background-color: #1e90ff;
    color: white;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out;
  }
  button:hover {
    background-color: #339af0;
  }
  img {
    max-width: 100%;
    margin: 20px auto;
    border-radius: 10px;
  }
  .footer {
    font-size: 0.9em;
    color: #a4b0be;
    margin-top: 40px;
  }
  a {
    color: #1e90ff;
    text-decoration: none;
  }
  table {
    margin: 0 auto;
    border-collapse: collapse;
    width: 100%;
  }
  table th, table td {
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
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
      <p>Passport Size Photo:</p>
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
<div class="footer">
  Contact: <a href="mailto:anvehsingh0612@gmail.com">anvehsingh0612@gmail.com</a>
</div>
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
    file = request.files['photo']
    filename = secure_filename(current_user.username + '_' + file.filename)
    img_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(img_path)

    processed_filename = "passport_" + current_user.username + ".jpg"
    processed_path = os.path.join(PROCESSED_FOLDER, processed_filename)

    with Image.open(img_path) as im:
        im = im.convert("RGB")
        im = im.resize((600, 600))
        im.save(processed_path, "JPEG")

    session['uploaded'] = True
    session['uploaded_file'] = filename
    session['processed_file']
