from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from rembg import remove
import sqlite3
import os
import traceback
import uuid

app = Flask(__name__)
app.secret_key = "your-very-secret-key-change-this"  # Change this in production

UPLOAD_FOLDER = "static/uploads"
PROCESSED_FOLDER = "static/passports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

ADMIN_EMAIL = "anvehsingh0612@gmail.com"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

class User(UserMixin):
    def __init__(self, id, username, email, password_hash, registered_on=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.registered_on = registered_on

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if row:
            return User(*row)
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_email(email):
    conn = None
    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if row:
            return User(*row)
        return None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_users():
    """Get all users for admin panel"""
    conn = None
    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, registered_on FROM users ORDER BY registered_on DESC")
        rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []
    finally:
        if conn:
            conn.close()

def init_db():
    conn = None
    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                registered_on DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if conn:
            conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize database
if not os.path.exists("users.db"):
    init_db()

STYLE = """
<style>
  * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
  body { margin: 0; background: #f0f4f8; color: #2d3436; padding: 20px; }
  h1, h2 { text-align: center; margin: 20px 0 30px; font-size: 2rem; }
  h2 { font-size: 1.8rem; }
  .box {
    background: #ffffff;
    max-width: 480px;
    margin: 0 auto 30px;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    text-align: center;
  }
  .error {
    background: #ffe6e6;
    color: #d63031;
    padding: 12px;
    border-radius: 8px;
    margin: 10px 0;
    border: 1px solid #fab1a0;
  }
  .success {
    background: #e8f5e8;
    color: #00b894;
    padding: 12px;
    border-radius: 8px;
    margin: 10px 0;
    border: 1px solid #a4d6a4;
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
  button:disabled { background: #ccc; cursor: not-allowed; }
  a { color: #0077ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  img {
    width: 100%; max-width: 400px; margin-top: 20px;
    border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  .footer {
    text-align: center; font-size: 0.9em;
    margin-top: 40px; color: #a4a4a4;
  }
  .admin-table {
    width: 100%; border-collapse: collapse; margin-top: 20px;
  }
  .admin-table th, .admin-table td {
    border: 1px solid #ddd; padding: 8px; text-align: left;
  }
  .admin-table th {
    background-color: #f2f2f2;
  }
  @media (max-width: 480px) {
    h1, h2 { font-size: 1.5rem; }
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
    <p>Welcome, <b>{{ current_user.username }}</b>!</p>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="photo" accept="image/*" required>
      <small>Supported formats: PNG, JPG, JPEG, GIF, BMP, WEBP (Max: 16MB)</small><br>
      <button type="submit">Upload & Convert</button>
    </form>
    {% if uploaded %}
      <div class="success">Photo processed successfully!</div>
      <p><strong>Your uploaded image:</strong></p>
      <img src="{{ uploaded_url }}" alt="Uploaded Image">
      <p><strong>Passport Size Photo (600x600, background removed):</strong></p>
      <img src="{{ processed_url }}" alt="Passport Photo">
      <a href="{{ processed_url }}" download><button>Download Passport Photo</button></a>
    {% endif %}
    <p><a href="/logout">Logout</a></p>
    {% if current_user.email == admin %}
      <p><a href="/admin">👑 Admin Panel</a></p>
    {% endif %}
  </div>
{% else %}
  <div class='box'>
    <p>Transform your photos into professional passport-size images!</p>
    <p><a href='/login'><button>Login</button></a></p>
    <p><a href='/register'>Don't have an account? Register here</a></p>
  </div>
{% endif %}
<div class="footer">
  Created with ❤️ | Contact: <a href="mailto:anvehsingh0612@gmail.com">anvehsingh0612@gmail.com</a>
</div>
"""

REGISTER_HTML = STYLE + """
<h2>Create Account</h2>
<div class='box'>
  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}
  <form method="post">
    <input name="username" placeholder="Username" required minlength="3" maxlength="50">
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password (min 6 characters)" required minlength="6">
    <button type="submit">Create Account</button>
  </form>
  <p>Already have an account? <a href="/login">Login here</a></p>
</div>
"""

LOGIN_HTML = STYLE + """
<h2>Login</h2>
<div class='box'>
  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}
  <form method="post">
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>
  <p>Don't have an account? <a href="/register">Register here</a></p>
</div>
"""

ADMIN_HTML = STYLE + """
<h2>👑 Admin Panel</h2>
<div class='box' style="max-width: 800px;">
  <p>Total Users: <strong>{{ user_count }}</strong></p>
  <table class="admin-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Username</th>
        <th>Email</th>
        <th>Registered On</th>
      </tr>
    </thead>
    <tbody>
      {% for user in users %}
      <tr>
        <td>{{ user[0] }}</td>
        <td>{{ user[1] }}</td>
        <td>{{ user[2] }}</td>
        <td>{{ user[3] }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p><a href="/">← Back to Home</a></p>
</div>
"""

@app.route('/')
def home():
    uploaded = session.pop('uploaded', False)
    uploaded_file = session.pop('uploaded_file', None)
    processed_file = session.pop('processed_file', None)
    uploaded_url = url_for('static', filename='uploads/' + uploaded_file) if uploaded_file else None
    processed_url = url_for('static', filename='passports/' + processed_file) if processed_file else None
    return render_template_string(HOME_HTML, 
                                uploaded=uploaded, 
                                uploaded_url=uploaded_url, 
                                processed_url=processed_url, 
                                admin=ADMIN_EMAIL)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # Validation
        if not username or len(username) < 3:
            return render_template_string(REGISTER_HTML, error="Username must be at least 3 characters long.")
        
        if not email:
            return render_template_string(REGISTER_HTML, error="Email is required.")
        
        if not password or len(password) < 6:
            return render_template_string(REGISTER_HTML, error="Password must be at least 6 characters long.")
        
        # Check if user already exists
        if get_user_by_email(email):
            return render_template_string(REGISTER_HTML, error="Email is already registered.")
        
        # Create user
        pwd_hash = generate_password_hash(password)
        conn = None
        try:
            conn = sqlite3.connect("users.db")
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", 
                       (username, email, pwd_hash))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template_string(REGISTER_HTML, error="Email is already registered.")
        except Exception as e:
            print(f"Registration error: {e}")
            return render_template_string(REGISTER_HTML, error="Registration failed. Please try again.")
        finally:
            if conn:
                conn.close()
    
    return render_template_string(REGISTER_HTML)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            return render_template_string(LOGIN_HTML, error="Email and password are required.")
        
        user = get_user_by_email(email)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            return render_template_string(LOGIN_HTML, error="Invalid email or password.")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/admin')
@login_required
def admin():
    if current_user.email != ADMIN_EMAIL:
        return redirect(url_for('home'))
    
    users = get_all_users()
    return render_template_string(ADMIN_HTML, users=users, user_count=len(users))

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    try:
        # Check if file is in request
        if 'photo' not in request.files:
            return "No file selected", 400
        
        file = request.files['photo']
        if file.filename == '':
            return "No file selected", 400
        
        # Check file extension
        if not allowed_file(file.filename):
            session['error'] = "Invalid file format. Please upload PNG, JPG, JPEG, GIF, BMP, or WEBP files."
            return redirect(url_for('home'))
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{current_user.username}_{uuid.uuid4().hex[:8]}.{file_extension}"
        img_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save uploaded file
        file.save(img_path)
        
        # Check file size after saving
        if os.path.getsize(img_path) > MAX_FILE_SIZE:
            os.remove(img_path)  # Clean up the file
            return "File too large. Maximum size is 16MB.", 400
        
        # Process the image
        processed_filename = f"passport_{current_user.username}_{uuid.uuid4().hex[:8]}.jpg"
        processed_path = os.path.join(PROCESSED_FOLDER, processed_filename)
        
        # Open and process image
        with Image.open(img_path) as im:
            # Convert to RGBA for background removal
            if im.mode != 'RGBA':
                im = im.convert("RGBA")
            
            # Remove background
            bg_removed = remove(im)
            
            # Resize to passport size (600x600)
            resized = bg_removed.resize((600, 600), Image.Resampling.LANCZOS)
            
            # Create white background and paste the image
            final_image = Image.new("RGB", (600, 600), (255, 255, 255))
            if resized.mode == 'RGBA':
                final_image.paste(resized, (0, 0), resized)
            else:
                final_image.paste(resized, (0, 0))
            
            # Save the final image
            final_image.save(processed_path, "JPEG", quality=95, optimize=True)
        
        # Set session variables for displaying results
        session['uploaded'] = True
        session['uploaded_file'] = unique_filename
        session['processed_file'] = processed_filename
        
        return redirect(url_for('home'))
        
    except Exception as e:
        print("Upload error:", str(e))
        traceback.print_exc()
        # Clean up files in case of error
        try:
            if 'img_path' in locals() and os.path.exists(img_path):
                os.remove(img_path)
            if 'processed_path' in locals() and os.path.exists(processed_path):
                os.remove(processed_path)
        except:
            pass
        return "An error occurred while processing your image. Please try again.", 500

@app.errorhandler(404)
def not_found(error):
    return render_template_string(STYLE + """
    <h2>Page Not Found</h2>
    <div class='box'>
        <p>The page you're looking for doesn't exist.</p>
        <p><a href="/">← Go back to home</a></p>
    </div>
    """), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template_string(STYLE + """
    <h2>Internal Server Error</h2>
    <div class='box'>
        <p>Something went wrong on our end. Please try again later.</p>
        <p><a href="/">← Go back to home</a></p>
    </div>
    """), 500

if __name__ == '__main__':
    # In production, use environment variables for configuration
    app.run(debug=True, host='0.0.0.0', port=5000)


