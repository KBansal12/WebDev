import email

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config, get_connection
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config.from_object(Config)
#for prviding better security to the session we use flask_login
#LoginManager main object is used to manage user sessions and authentication in a Flask application.
red=LoginManager()
red.init_app(app)
red.login_view = "login"

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email # 🔹 Login Page
    
@red.user_loader #red object is the instance of LoginManager
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM users WHERE ID=%s, "
    cursor.execute(sql, (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(id=user['ID'], name=user['Name'], email=user['Email'])
    return None

@app.route('/')
def login_page():
    return render_template("login.html")
@app.route("/courses")
def courses():
    return render_template("courses.html")
@app.route("/faculty")
def faculty():
    return render_template("faculty.html")
@app.route("/students")
def students():
    return render_template("students.html")
# 🔹 Register Page
@app.route('/register')
def register_page():
    return render_template("register.html")
@app.route("/reports")
def reports():
    return render_template("reports.html")
@app.route("/assignments")
def assignments():
    return render_template("assignments.html")
# 🔹 Register User
@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    hashed_password = generate_password_hash(password)

    conn = get_connection()
    cursor = conn.cursor()

    sql = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
    cursor.execute(sql, (name, email, hashed_password))

    conn.commit()
    conn.close()

    return redirect(url_for('login_page'))

# 🔹 Login Check
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    conn = get_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM users WHERE email=%s"
    cursor.execute(sql, (email,))
    user = cursor.fetchone()

    conn.close()

    if user and check_password_hash(user['password'], password):
        session['ID'] = user['ID']
        session['Name'] = user['Name']
        return redirect(url_for('dashboard'))
    else:
        return "Invalid Email or Password"
# 🔹 Dashboard
@app.route('/dashboard')
def dashboard():
    if 'ID' in session:
        return render_template("dashboard.html", name=session['Name'])
    else:
        return redirect(url_for('login_page'))
app.route('/about')
def about():
    return render_template("about.html")
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))
if __name__ == "__main__":
    app.run(debug=True)