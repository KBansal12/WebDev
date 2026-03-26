import secrets
from functools import wraps

import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config, get_connection


app = Flask(__name__)
app.config.from_object(Config)


def ensure_users_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def get_users_columns(cursor):
    cursor.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'users'
    """)
    cols = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    col_map = {
        "id": "ID" if "ID" in cols else ("id" if "id" in cols else None),
        "name": "Name" if "Name" in cols else ("name" if "name" in cols else None),
        "email": "Email" if "Email" in cols else ("email" if "email" in cols else None),
        "password": "password" if "password" in cols else ("Password" if "Password" in cols else None),
        "role": "role" if "role" in cols else None,
    }

    missing = [k for k, v in col_map.items() if v is None and k in {"id", "name", "email", "password"}]
    if missing:
        raise RuntimeError(f"users table missing columns: {missing}")

    if col_map["role"] is None:
        cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'")
        col_map["role"] = "role"

    if "created_at" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cols.add("created_at")

    return col_map


def ensure_students_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def ensure_courses_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) UNIQUE,
            title VARCHAR(150) NOT NULL,
            description TEXT NULL,
            faculty_id INT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def ensure_enrollments_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            course_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_student_course (student_id, course_id)
        )
    """)


def ensure_assignments_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT NOT NULL,
            title VARCHAR(150) NOT NULL,
            description TEXT NULL,
            due_date DATE NULL,
            created_by INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def ensure_access_keys_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_keys (
            id INT AUTO_INCREMENT PRIMARY KEY,
            key_type VARCHAR(50) NOT NULL,
            key_value VARCHAR(255) NOT NULL,
            course_id INT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'access_keys'
          AND COLUMN_NAME = 'course_id'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE access_keys ADD COLUMN course_id INT NULL")


def ensure_core_tables(cursor):
    ensure_users_table(cursor)
    ensure_students_table(cursor)
    ensure_courses_table(cursor)
    ensure_enrollments_table(cursor)
    ensure_assignments_table(cursor)
    ensure_access_keys_table(cursor)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login_page"))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login_page"))
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def student_access_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("student_access"):
            return redirect(url_for("student_access"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required")

    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)
    cols = get_users_columns(cursor)

    try:
        cursor.execute(
            f"INSERT INTO users (`{cols['name']}`, `{cols['email']}`, `{cols['password']}`, `{cols['role']}`) VALUES (%s, %s, %s, %s)",
            (name, email, generate_password_hash(password), "admin"),
        )
        conn.commit()
    except pymysql.IntegrityError:
        conn.close()
        return render_template("register.html", error="Email already exists")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return redirect(url_for("login_page"))


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)
    cols = get_users_columns(cursor)

    cursor.execute(
        f"SELECT `{cols['id']}` AS id, `{cols['name']}` AS name, `{cols['email']}` AS email, `{cols['password']}` AS password, `{cols['role']}` AS role FROM users WHERE `{cols['email']}`=%s LIMIT 1",
        (email,),
    )
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        return render_template("login.html", error="Invalid email or password")

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["role"] = user.get("role") or "admin"

    if session["role"] == "faculty":
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("admin_dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    cursor.execute("SELECT COUNT(*) AS c FROM students")
    students_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM courses")
    courses_count = cursor.fetchone()["c"]

    cols = get_users_columns(cursor)
    cursor.execute(f"SELECT COUNT(*) AS c FROM users WHERE `{cols['role']}`=%s", ("faculty",))
    faculty_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM assignments")
    assignments_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT s.id, s.name, s.email,
               COALESCE(GROUP_CONCAT(c.title ORDER BY c.title SEPARATOR ', '), '') AS courses
        FROM students s
        LEFT JOIN enrollments e ON e.student_id = s.id
        LEFT JOIN courses c ON c.id = e.course_id
        GROUP BY s.id, s.name, s.email
        ORDER BY s.id DESC
        LIMIT 8
    """)
    recent_students = cursor.fetchall()

    student_access_key = None
    cursor.execute("""
        SELECT key_value
        FROM access_keys
        WHERE key_type=%s AND is_active=1 AND course_id IS NULL
        ORDER BY id DESC
        LIMIT 1
    """, ("student",))
    row = cursor.fetchone()
    if row:
        student_access_key = row["key_value"]

    conn.close()
    return render_template(
        "dashboard.html",
        students=recent_students,
        students_count=students_count,
        courses_count=courses_count,
        faculty_count=faculty_count,
        assignments_count=assignments_count,
        student_access_key=student_access_key,
    )


@app.route("/admin/generate-student-key", methods=["POST"])
@role_required("admin")
def generate_student_key():
    new_key = secrets.token_urlsafe(9)[:12]
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    cursor.execute("UPDATE access_keys SET is_active=0 WHERE key_type=%s AND course_id IS NULL", ("student",))
    cursor.execute(
        "INSERT INTO access_keys (key_type, key_value, course_id, is_active) VALUES (%s, %s, NULL, 1)",
        ("student", new_key),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/faculty", methods=["GET", "POST"])
@role_required("admin")
def admin_faculty():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)
    cols = get_users_columns(cursor)

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "All fields are required"
        else:
            try:
                cursor.execute(
                    f"INSERT INTO users (`{cols['name']}`, `{cols['email']}`, `{cols['password']}`, `{cols['role']}`) VALUES (%s, %s, %s, %s)",
                    (name, email, generate_password_hash(password), "faculty"),
                )
                conn.commit()
            except pymysql.IntegrityError:
                error = "Faculty email already exists"

    cursor.execute(
        f"SELECT `{cols['id']}` AS id, `{cols['name']}` AS name, `{cols['email']}` AS email, `{cols['role']}` AS role, created_at FROM users WHERE `{cols['role']}`=%s ORDER BY `{cols['id']}` DESC",
        ("faculty",),
    )
    faculty = cursor.fetchall()
    conn.close()
    return render_template("faculty_manage.html", faculty=faculty, error=error)


@app.route("/courses", methods=["GET", "POST"])
@login_required
def courses():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)
    cols = get_users_columns(cursor)

    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        code = request.form.get("code", "").strip() or None
        description = request.form.get("description", "").strip() or None

        faculty_id = None
        if session.get("role") == "admin":
            faculty_id = request.form.get("faculty_id") or None
        elif session.get("role") == "faculty":
            faculty_id = session.get("user_id")
        else:
            abort(403)

        if not title:
            error = "Course title is required"
        else:
            try:
                cursor.execute(
                    "INSERT INTO courses (code, title, description, faculty_id) VALUES (%s, %s, %s, %s)",
                    (code, title, description, faculty_id),
                )
                conn.commit()
            except pymysql.IntegrityError:
                error = "Course code already exists"

    user_id_col = cols["id"]
    user_name_col = cols["name"]

    if session.get("role") == "faculty":
        cursor.execute(f"""
            SELECT c.*,
                   u.`{user_name_col}` AS faculty_name,
                   (SELECT ak.key_value
                    FROM access_keys ak
                    WHERE ak.key_type='course' AND ak.course_id=c.id AND ak.is_active=1
                    ORDER BY ak.id DESC
                    LIMIT 1) AS access_key
            FROM courses c
            LEFT JOIN users u ON c.faculty_id = u.`{user_id_col}`
            WHERE c.faculty_id=%s
            ORDER BY c.id DESC
        """, (session.get("user_id"),))
    else:
        cursor.execute(f"""
            SELECT c.*,
                   u.`{user_name_col}` AS faculty_name,
                   (SELECT ak.key_value
                    FROM access_keys ak
                    WHERE ak.key_type='course' AND ak.course_id=c.id AND ak.is_active=1
                    ORDER BY ak.id DESC
                    LIMIT 1) AS access_key
            FROM courses c
            LEFT JOIN users u ON c.faculty_id = u.`{user_id_col}`
            ORDER BY c.id DESC
        """)
    courses_rows = cursor.fetchall()

    cursor.execute(
        f"SELECT `{cols['id']}` AS id, `{cols['name']}` AS name, `{cols['email']}` AS email FROM users WHERE `{cols['role']}`=%s ORDER BY `{cols['name']}` ASC",
        ("faculty",),
    )
    faculty = cursor.fetchall()
    layout = "base_admin.html" if session.get("role") == "admin" else "base_faculty.html"
    conn.close()
    return render_template("courses.html", courses=courses_rows, faculty=faculty, error=error, layout=layout)


@app.route("/courses/<int:course_id>/delete", methods=["POST"])
@login_required
def delete_course(course_id):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    if session.get("role") == "faculty":
        cursor.execute("DELETE FROM courses WHERE id=%s AND faculty_id=%s", (course_id, session.get("user_id")))
    elif session.get("role") == "admin":
        cursor.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    else:
        abort(403)

    conn.commit()
    conn.close()
    return redirect(url_for("courses"))


@app.route("/faculty")
@role_required("faculty")
def faculty_root():
    return redirect(url_for("faculty_dashboard"))


@app.route("/faculty/dashboard")
@role_required("faculty")
def faculty_dashboard():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    cursor.execute("SELECT COUNT(*) AS c FROM courses WHERE faculty_id=%s", (session.get("user_id"),))
    courses_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        WHERE c.faculty_id=%s
    """, (session.get("user_id"),))
    students_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) AS c
        FROM assignments a
        JOIN courses c ON c.id = a.course_id
        WHERE c.faculty_id=%s
    """, (session.get("user_id"),))
    assignments_count = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT c.*,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) AS student_count,
               (SELECT ak.key_value
                FROM access_keys ak
                WHERE ak.key_type='course' AND ak.course_id=c.id AND ak.is_active=1
                ORDER BY ak.id DESC
                LIMIT 1) AS access_key
        FROM courses c
        WHERE c.faculty_id=%s
        ORDER BY c.id DESC
    """, (session.get("user_id"),))
    my_courses = cursor.fetchall()

    conn.close()
    return render_template(
        "faculty_dashboard.html",
        courses_count=courses_count,
        students_count=students_count,
        assignments_count=assignments_count,
        my_courses=my_courses,
    )


@app.route("/faculty/course/<int:course_id>/generate-key", methods=["POST"])
@role_required("faculty", "admin")
def generate_course_key(course_id):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    if session.get("role") == "faculty":
        cursor.execute("SELECT id FROM courses WHERE id=%s AND faculty_id=%s", (course_id, session.get("user_id")))
        if not cursor.fetchone():
            conn.close()
            abort(403)

    new_key = secrets.token_urlsafe(9)[:12]
    cursor.execute("UPDATE access_keys SET is_active=0 WHERE key_type=%s AND course_id=%s", ("course", course_id))
    cursor.execute(
        "INSERT INTO access_keys (key_type, key_value, course_id, is_active) VALUES (%s, %s, %s, 1)",
        ("course", new_key, course_id),
    )
    conn.commit()
    conn.close()
    if session.get("role") == "faculty":
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("courses"))


@app.route("/students", methods=["GET", "POST"])
@role_required("admin")
def students():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        course_id = request.form.get("course_id")

        if not name or not email or not course_id:
            error = "Name, email, and course are required"
        else:
            try:
                cursor.execute("SELECT id FROM students WHERE email=%s LIMIT 1", (email,))
                existing = cursor.fetchone()
                if existing:
                    student_id = existing["id"]
                    cursor.execute("UPDATE students SET name=%s WHERE id=%s", (name, student_id))
                else:
                    cursor.execute("INSERT INTO students (name, email) VALUES (%s, %s)", (name, email))
                    student_id = cursor.lastrowid

                cursor.execute(
                    "INSERT IGNORE INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                    (student_id, int(course_id)),
                )
                conn.commit()
            except pymysql.IntegrityError:
                error = "Student email already exists"

    cursor.execute("SELECT id, title FROM courses ORDER BY title ASC")
    courses_list = cursor.fetchall()

    cursor.execute("""
        SELECT s.id, s.name, s.email,
               COALESCE(GROUP_CONCAT(c.title ORDER BY c.title SEPARATOR ', '), '') AS courses
        FROM students s
        LEFT JOIN enrollments e ON e.student_id = s.id
        LEFT JOIN courses c ON c.id = e.course_id
        GROUP BY s.id, s.name, s.email
        ORDER BY s.id DESC
    """)
    students_rows = cursor.fetchall()

    conn.close()
    return render_template(
        "students.html",
        students=students_rows,
        courses=courses_list,
        error=error,
    )


@app.route("/delete_student/<int:student_id>", methods=["POST"])
@role_required("admin")
def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    cursor.execute("DELETE FROM enrollments WHERE student_id=%s", (student_id,))
    cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("students"))


@app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        course_id = request.form.get("course_id")

        if not name or not email:
            error = "Name and email are required"
        else:
            cursor.execute("UPDATE students SET name=%s, email=%s WHERE id=%s", (name, email, student_id))
            cursor.execute("DELETE FROM enrollments WHERE student_id=%s", (student_id,))
            if course_id:
                cursor.execute(
                    "INSERT IGNORE INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                    (student_id, int(course_id)),
                )
            conn.commit()
            conn.close()
            return redirect(url_for("students"))

    cursor.execute("SELECT * FROM students WHERE id=%s", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        abort(404)

    cursor.execute("SELECT id, title FROM courses ORDER BY title ASC")
    courses_list = cursor.fetchall()

    cursor.execute("SELECT course_id FROM enrollments WHERE student_id=%s LIMIT 1", (student_id,))
    current = cursor.fetchone()
    current_course_id = current["course_id"] if current else None

    conn.close()
    return render_template(
        "edit_student.html",
        student=student,
        courses=courses_list,
        current_course_id=current_course_id,
        error=error,
    )


@app.route("/assignments", methods=["GET", "POST"])
def assignments():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    error = None
    can_create = session.get("role") in {"admin", "faculty"}

    if request.method == "POST":
        if not can_create:
            conn.close()
            abort(403)

        course_id = request.form.get("course_id")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        due_date = request.form.get("due_date") or None

        if not course_id or not title:
            error = "Course and title are required"
        else:
            if session.get("role") == "faculty":
                cursor.execute("SELECT id FROM courses WHERE id=%s AND faculty_id=%s", (course_id, session.get("user_id")))
                if not cursor.fetchone():
                    conn.close()
                    abort(403)

            cursor.execute(
                "INSERT INTO assignments (course_id, title, description, due_date, created_by) VALUES (%s, %s, %s, %s, %s)",
                (int(course_id), title, description, due_date, session.get("user_id")),
            )
            conn.commit()

    if session.get("role") == "faculty":
        cursor.execute("SELECT id, title FROM courses WHERE faculty_id=%s ORDER BY title ASC", (session.get("user_id"),))
        courses_list = cursor.fetchall()
        cursor.execute("""
            SELECT a.*, c.title AS course_title
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
            WHERE c.faculty_id=%s
            ORDER BY a.id DESC
        """, (session.get("user_id"),))
        assignments_rows = cursor.fetchall()
    elif session.get("role") == "admin":
        cursor.execute("SELECT id, title FROM courses ORDER BY title ASC")
        courses_list = cursor.fetchall()
        cursor.execute("""
            SELECT a.*, c.title AS course_title
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
            ORDER BY a.id DESC
        """)
        assignments_rows = cursor.fetchall()
    elif session.get("student_access"):
        course_ids = session.get("student_courses", [])
        if course_ids:
            cursor.execute(
                f"SELECT id, title FROM courses WHERE id IN ({','.join(['%s']*len(course_ids))}) ORDER BY title ASC",
                tuple(course_ids),
            )
            courses_list = cursor.fetchall()
            cursor.execute(
                f"""
                SELECT a.*, c.title AS course_title
                FROM assignments a
                JOIN courses c ON c.id = a.course_id
                WHERE a.course_id IN ({','.join(['%s']*len(course_ids))})
                ORDER BY a.id DESC
                """,
                tuple(course_ids),
            )
            assignments_rows = cursor.fetchall()
        else:
            courses_list = []
            assignments_rows = []
    else:
        courses_list = []
        assignments_rows = []

    if session.get("role") == "admin":
        layout = "base_admin.html"
    elif session.get("role") == "faculty":
        layout = "base_faculty.html"
    elif session.get("student_access"):
        layout = "base_student.html"
    else:
        conn.close()
        return redirect(url_for("login_page"))

    conn.close()
    return render_template(
        "assignments.html",
        assignments=assignments_rows,
        courses=courses_list,
        can_create=can_create,
        error=error,
        layout=layout,
    )


@app.route("/reports")
@login_required
def reports():
    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)
    cols = get_users_columns(cursor)

    cursor.execute("SELECT COUNT(*) AS c FROM students")
    students_count = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM courses")
    courses_count = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM assignments")
    assignments_count = cursor.fetchone()["c"]
    cursor.execute(f"SELECT COUNT(*) AS c FROM users WHERE `{cols['role']}`=%s", ("faculty",))
    faculty_count = cursor.fetchone()["c"]

    cursor.execute(f"""
        SELECT c.title, c.code, c.created_at, u.`{cols['name']}` AS faculty_name
        FROM courses c
        LEFT JOIN users u ON u.`{cols['id']}` = c.faculty_id
        ORDER BY c.id DESC
        LIMIT 6
    """)
    recent_courses = cursor.fetchall()

    cursor.execute("""
        SELECT a.title, a.due_date, a.created_at, c.title AS course_title
        FROM assignments a
        JOIN courses c ON c.id = a.course_id
        ORDER BY a.id DESC
        LIMIT 6
    """)
    recent_assignments = cursor.fetchall()

    cursor.execute("""
        SELECT s.name AS student_name, c.title AS course_title, e.created_at
        FROM enrollments e
        JOIN students s ON s.id = e.student_id
        JOIN courses c ON c.id = e.course_id
        ORDER BY e.id DESC
        LIMIT 8
    """)
    recent_enrollments = cursor.fetchall()

    layout = "base_admin.html" if session.get("role") == "admin" else "base_faculty.html"
    conn.close()
    return render_template(
        "reports.html",
        students_count=students_count,
        courses_count=courses_count,
        assignments_count=assignments_count,
        faculty_count=faculty_count,
        recent_courses=recent_courses,
        recent_assignments=recent_assignments,
        recent_enrollments=recent_enrollments,
        layout=layout,
    )


@app.route("/student", methods=["GET", "POST"])
def student_access():
    if request.method == "POST":
        entered_key = request.form.get("access_key", "").strip()
        if not entered_key:
            return render_template("student_access.html", error="Access key is required")

        conn = get_connection()
        cursor = conn.cursor()
        ensure_core_tables(cursor)
        cursor.execute("""
            SELECT key_type, key_value, course_id
            FROM access_keys
            WHERE key_value=%s AND is_active=1
            ORDER BY id DESC
            LIMIT 1
        """, (entered_key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return render_template("student_access.html", error="Invalid access key")

        session["student_access"] = True
        if row["key_type"] == "course" and row["course_id"]:
            current = session.get("student_courses", [])
            if row["course_id"] not in current:
                current.append(row["course_id"])
            session["student_courses"] = current
        return redirect(url_for("student_dashboard"))

    return render_template("student_access.html")


@app.route("/student/dashboard")
@student_access_required
def student_dashboard():
    course_ids = session.get("student_courses", [])
    courses_list = []

    if course_ids:
        conn = get_connection()
        cursor = conn.cursor()
        ensure_core_tables(cursor)
        cursor.execute(
            f"SELECT id, code, title, description FROM courses WHERE id IN ({','.join(['%s']*len(course_ids))}) ORDER BY title ASC",
            tuple(course_ids),
        )
        courses_list = cursor.fetchall()
        conn.close()

    return render_template("student_dashboard.html", courses=courses_list)


@app.route("/student/course/<int:course_id>")
@student_access_required
def student_course(course_id):
    if course_id not in session.get("student_courses", []):
        abort(403)

    conn = get_connection()
    cursor = conn.cursor()
    ensure_core_tables(cursor)

    cursor.execute("SELECT * FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    cursor.execute("""
        SELECT id, title, description, due_date, created_at
        FROM assignments
        WHERE course_id=%s
        ORDER BY id DESC
    """, (course_id,))
    assignments_rows = cursor.fetchall()
    conn.close()

    return render_template("student_course.html", course=course, assignments=assignments_rows)


@app.route("/student/logout")
def student_logout():
    session.pop("student_access", None)
    session.pop("student_courses", None)
    return redirect(url_for("student_access"))


@app.route("/about")
@role_required("admin")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
