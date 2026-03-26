import email
import pymysql
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

@app.route("/students", methods=["GET", "POST"])
def students():
    conn = get_connection()
    cursor = conn.cursor()

    # ADD STUDENT
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        course = request.form["course"]

        cursor.execute(
            "INSERT INTO students (name, email, course) VALUES (%s, %s, %s)",
            (name, email, course)
        )
        conn.commit()

    # FETCH DATA
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    total_students = len(students)
    active_students = total_students   # (you can improve later)
    graduated_students = 0

    return render_template(
        "students.html",
        students=students,
        total_students=total_students,
        active_students=active_students,
        graduated_students=graduated_students
    )
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
        return redirect(url_for('admin'))
    else:
        return "Invalid Email or Password"
# 🔹 Dashboard
@app.route("/admin")
def admin():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    students_count = len(students)

    courses_count = 5
    faculty_count = 3
    assignments_count = 7

    return render_template(
        "dashboard.html",
        students=students,
        students_count=students_count,
        courses_count=courses_count,
        faculty_count=faculty_count,
        assignments_count=assignments_count
    )
app.route('/about')
def about():
    return render_template("about.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route("/delete_student/<int:id>")
def delete_student(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE id=%s", (id,))
    conn.commit()

    return redirect("/admin")

@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        course = request.form["course"]

        cursor.execute("""
            UPDATE students 
            SET name=%s, email=%s, course=%s 
            WHERE id=%s
        """, (name, email, course, id))

        conn.commit()
        return redirect("/admin")

    cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
    student = cursor.fetchone()

    return render_template("edit_student.html", student=student)
if __name__ == "__main__":
    app.run(debug=True)