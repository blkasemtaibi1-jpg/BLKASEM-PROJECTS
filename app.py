from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
    abort
)

from werkzeug.utils import secure_filename

import sqlite3
import os
import uuid


# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.secret_key = "BLKASEM_CHANGE_THIS_SECRET_KEY"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "projects.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# ADMIN
# =========================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "blkasem123"


# =========================================================
# ALLOWED FILES
# =========================================================

ALLOWED_PROJECT_EXTENSIONS = {
    "zip",
    "rar",
    "7z",
    "exe",
    "msi",
    "py",
    "apk",
    "pdf"
}

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif"
}


# =========================================================
# DATABASE
# =========================================================

def get_db():

    db = sqlite3.connect(DATABASE)

    db.row_factory = sqlite3.Row

    return db


def init_database():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS projects (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT,

            category TEXT,

            filename TEXT NOT NULL,

            original_filename TEXT,

            image TEXT,

            downloads INTEGER DEFAULT 0,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

        )
    """)

    db.commit()

    db.close()


# =========================================================
# FILE HELPERS
# =========================================================

def get_extension(filename):

    if "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def allowed_project(filename):

    return (
        get_extension(filename)
        in ALLOWED_PROJECT_EXTENSIONS
    )


def allowed_image(filename):

    return (
        get_extension(filename)
        in ALLOWED_IMAGE_EXTENSIONS
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    db = get_db()

    projects = db.execute("""
        SELECT *
        FROM projects
        ORDER BY id DESC
    """).fetchall()

    db.close()

    return render_template(
        "index.html",
        page="home",
        projects=projects
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
def admin():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session["admin"] = True

            return redirect(
                url_for("dashboard")
            )

        error = "Invalid username or password."

    return render_template(
        "index.html",
        page="admin",
        error=error,
        projects=[]
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def dashboard():

    if not session.get("admin"):

        return redirect(
            url_for("admin")
        )

    db = get_db()

    projects = db.execute("""
        SELECT *
        FROM projects
        ORDER BY id DESC
    """).fetchall()

    db.close()

    return render_template(
        "index.html",
        page="dashboard",
        projects=projects
    )


# =========================================================
# UPLOAD PROJECT
# =========================================================

@app.route(
    "/admin/upload",
    methods=["POST"]
)
def upload_project():

    if not session.get("admin"):

        return redirect(
            url_for("admin")
        )

    title = request.form.get(
        "title",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    category = request.form.get(
        "category",
        "Other"
    ).strip()

    project_file = request.files.get(
        "project_file"
    )

    image_file = request.files.get(
        "image_file"
    )


    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not title:

        return redirect(
            url_for("dashboard")
        )


    if (
        not project_file
        or not project_file.filename
    ):

        return redirect(
            url_for("dashboard")
        )


    if not allowed_project(
        project_file.filename
    ):

        return redirect(
            url_for("dashboard")
        )


    # -----------------------------------------------------
    # PROJECT FILE
    # -----------------------------------------------------

    original_filename = secure_filename(
        project_file.filename
    )

    unique_filename = (
        str(uuid.uuid4())
        + "_"
        + original_filename
    )

    project_path = os.path.join(
        UPLOAD_FOLDER,
        unique_filename
    )

    project_file.save(
        project_path
    )


    # -----------------------------------------------------
    # PROJECT IMAGE
    # -----------------------------------------------------

    image_filename = None

    if (
        image_file
        and image_file.filename
        and allowed_image(
            image_file.filename
        )
    ):

        original_image = secure_filename(
            image_file.filename
        )

        image_filename = (
            str(uuid.uuid4())
            + "_"
            + original_image
        )

        image_path = os.path.join(
            UPLOAD_FOLDER,
            image_filename
        )

        image_file.save(
            image_path
        )


    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    db = get_db()

    db.execute("""
        INSERT INTO projects (

            title,
            description,
            category,
            filename,
            original_filename,
            image

        )

        VALUES (?, ?, ?, ?, ?, ?)

    """, (

        title,
        description,
        category,
        unique_filename,
        original_filename,
        image_filename

    ))

    db.commit()

    db.close()


    return redirect(
        url_for("dashboard")
    )


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/download/<int:project_id>"
)
def download(project_id):

    db = get_db()

    project = db.execute("""
        SELECT *
        FROM projects
        WHERE id = ?
    """, (project_id,)).fetchone()


    if not project:

        db.close()

        abort(404)


    # Increase download counter

    db.execute("""
        UPDATE projects

        SET downloads = downloads + 1

        WHERE id = ?

    """, (project_id,))

    db.commit()

    db.close()


    return send_from_directory(

        UPLOAD_FOLDER,

        project["filename"],

        as_attachment=True,

        download_name=project[
            "original_filename"
        ]

    )


# =========================================================
# PROJECT IMAGE
# =========================================================

@app.route(
    "/project-image/<filename>"
)
def project_image(filename):

    return send_from_directory(

        UPLOAD_FOLDER,

        filename

    )


# =========================================================
# DELETE PROJECT
# =========================================================

@app.route(
    "/admin/delete/<int:project_id>",
    methods=["POST"]
)
def delete_project(project_id):

    if not session.get("admin"):

        return redirect(
            url_for("admin")
        )


    db = get_db()

    project = db.execute("""
        SELECT *
        FROM projects
        WHERE id = ?
    """, (project_id,)).fetchone()


    if project:

        # Delete project file

        project_file = os.path.join(
            UPLOAD_FOLDER,
            project["filename"]
        )

        if os.path.exists(
            project_file
        ):

            os.remove(
                project_file
            )


        # Delete image

        if project["image"]:

            image_file = os.path.join(
                UPLOAD_FOLDER,
                project["image"]
            )

            if os.path.exists(
                image_file
            ):

                os.remove(
                    image_file
                )


        # Delete database record

        db.execute("""
            DELETE FROM projects
            WHERE id = ?
        """, (project_id,))

        db.commit()


    db.close()


    return redirect(
        url_for("dashboard")
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/admin/logout")
def logout():

    session.pop(
        "admin",
        None
    )

    return redirect(
        url_for("index")
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@app.errorhandler(
    413
)
def file_too_large(error):

    return (
        "File is too large. Maximum size is 500 MB.",
        413
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )