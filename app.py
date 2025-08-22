from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    jsonify,
)
import bcrypt
import pandas as pd
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
from utils.db_mysql import (
    get_connection,
    save_job,
    get_user_jobs,
    get_job_by_id,
    delete_job_by_id,
)
from utils.cleaning import (
    impute_missing,
    detect_outliers,
    remove_outliers,
    winsorize_values,
    validate_rules,
)
from utils.weights import apply_weights, compute_weighted_summary
from utils.report import generate_report_html, generate_pdf_report, plot_histograms

# ----------------------------------------------------------------------------- 
# App setup
# ----------------------------------------------------------------------------- 
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ----------------------------------------------------------------------------- 
# Helpers
# ----------------------------------------------------------------------------- 
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _safe_close(cursor=None, conn=None):
    try:
        if cursor:
            cursor.close()
    except Exception:
        pass
    try:
        if conn:
            conn.close()
    except Exception:
        pass


# ----------------------------------------------------------------------------- 
# Routes
# ----------------------------------------------------------------------------- 
@app.route("/")
def home():
    return render_template("index.html")


# ---------------------------- Auth: Signup ----------------------------------- 
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password_raw = request.form.get("password", "")

        if not username or not email or not password_raw:
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("signup"))

        password_h = bcrypt.hashpw(password_raw.encode("utf-8"), bcrypt.gensalt())
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, password_h.decode("utf-8")),
            )
            conn.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            if "Duplicate entry" in str(e):
                flash("Username or email already exists.", "danger")
            else:
                flash(f"Registration error: {str(e)}", "danger")
            return redirect(url_for("signup"))
        finally:
            _safe_close(cursor, conn)

    return render_template("signup.html")


# ----------------------------- Auth: Login ----------------------------------- 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")

        if not username or not password_raw:
            flash("Please enter both username and password.", "warning")
            return redirect(url_for("login"))

        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()

            if user and bcrypt.checkpw(
                password_raw.encode("utf-8"), user["password"].encode("utf-8")
            ):
                session["user"] = {
                    "username": user["username"],
                    "role": user.get("role", "user"),
                    "email": user["email"],
                }
                flash("Logged in successfully!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid username or password.", "danger")
                return redirect(url_for("login"))
        except Exception as e:
            msg = str(e)
            if "pool" in msg.lower() and "exhaust" in msg.lower():
                flash("Temporary database busy. Please try again.", "warning")
            else:
                flash(f"Login error: {msg}", "danger")
            return redirect(url_for("login"))
        finally:
            _safe_close(cursor, conn)

    return render_template("login.html")


# --------------------------- Auth: Admin Login ------------------------------- 
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")

        if not username or not password_raw:
            flash("Please enter both username and password.", "warning")
            return redirect(url_for("admin_login"))

        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE username=%s AND role='admin'", (username,)
            )
            admin = cursor.fetchone()

            if admin and bcrypt.checkpw(
                password_raw.encode("utf-8"), admin["password"].encode("utf-8")
            ):
                session["user"] = {
                    "username": admin["username"],
                    "role": admin.get("role", "admin"),
                    "email": admin["email"],
                }
                flash("Admin logged in!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid admin credentials.", "danger")
                return redirect(url_for("admin_login"))
        except Exception as e:
            flash(f"Login error: {str(e)}", "danger")
            return redirect(url_for("admin_login"))
        finally:
            _safe_close(cursor, conn)

    return render_template("admin_login.html")


# -------------------------------- Dashboard ---------------------------------- 
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        recent_jobs = get_user_jobs(session["user"]["username"])
    except Exception as e:
        recent_jobs = []
        flash(f"Error loading recent jobs: {str(e)}", "danger")

    return render_template("dashboard.html", user=session["user"], recent=recent_jobs)


# -------------------------- Upload + Process form ----------------------------
# Single consolidated route to handle GET (render) and POST (process).
@app.route("/process-form", methods=["GET", "POST"])
def process_form():
    # Ensure user logged in
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    # If GET, render upload/process page
    if request.method == "GET":
        return render_template("upload_process.html")

    # POST: processing. Accept either an uploaded file in this request or the previously-uploaded file saved in session.
    filepath = None

    # Case A: frontend form uploaded a file in this POST
    if "data_file" in request.files and request.files["data_file"].filename:
        file = request.files["data_file"]
        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload CSV or Excel files.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        try:
            file.save(filepath)
            # Save full path into session for later reference (view, report generation, etc.)
            session["uploaded_file"] = filepath
        except Exception as e:
            flash(f"Could not save uploaded file: {e}", "danger")
            return redirect(request.url)

    # Case B: no file in this POST — maybe preview already uploaded and session has path
    elif session.get("uploaded_file"):
        stored = session.get("uploaded_file")
        # stored is saved as full path by preview_data/process above — accept both full path or filename
        if os.path.isabs(stored):
            filepath = stored
        else:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored)

    # Validate we have a file to process
    if not filepath or not os.path.exists(filepath):
        flash("No file uploaded or file not found.", "danger")
        return redirect(url_for("dashboard"))

    # Now process file
    try:
        # Read data
        if filepath.lower().endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        # Coerce numeric-like columns to numeric to avoid downstream errors
        for column_name in df.columns:
            if df[column_name].dtype == object:
                df[column_name] = pd.to_numeric(df[column_name], errors="ignore")

        rows_before = len(df)
        workflow_logs = [f"Data loaded: {rows_before} rows, {len(df.columns)} columns"]

        # Params
        impute_method = request.form.get("impute_method", "Mean")
        outlier_method = request.form.get("outlier_method", "IQR")
        weight_col = request.form.get("weight_col", "").strip()
        rules_json = request.form.get("rules_json", "{}")

        # Imputation
        if impute_method and impute_method != "None":
            df = impute_missing(df, impute_method)
            workflow_logs.append(f"Applied {impute_method} imputation")

        # Outliers detection & handling
        if outlier_method and outlier_method != "None":
            outliers = detect_outliers(df, outlier_method)

            # compute outlier_count robustly
            outlier_count = 0
            try:
                if isinstance(outliers, pd.Series):
                    outlier_count = int(outliers.sum())
                elif isinstance(outliers, pd.DataFrame):
                    # Row-level flagging: any True in the row means the row is an outlier
                    outlier_count = int(outliers.any(axis=1).sum())
                elif hasattr(outliers, "sum"):
                    outlier_count = int(outliers.sum())
            except Exception:
                outlier_count = 0

            if outlier_count > 0:
                action = request.form.get("outlier_action", "winsorize")
                if action == "remove":
                    df = remove_outliers(df, outliers)
                    workflow_logs.append(f"Removed {outlier_count} outliers using {outlier_method}")
                else:
                    df = winsorize_values(df)
                    workflow_logs.append(f"Winsorized {outlier_count} outliers using {outlier_method}")

        # Weights
        if weight_col and weight_col in df.columns:
            df = apply_weights(df, weight_col)
            workflow_logs.append(f"Applied weights from column: {weight_col}")

        # Rules validation
        try:
            rules = json.loads(rules_json) if rules_json else {}
            if rules:
                violations = validate_rules(df, rules)
                if isinstance(violations, list):
                    workflow_logs.extend(violations)
                else:
                    workflow_logs.append(str(violations))
        except json.JSONDecodeError:
            workflow_logs.append("Warning: Invalid JSON in rules configuration")

        rows_after = len(df)
        workflow_logs.append(f"Final dataset: {rows_after} rows")

        # Save job record to DB with safe fallback
        violations_count = len([log for log in workflow_logs if "violation" in log.lower()])
        job_id = None
        try:
            job_id = save_job(
                username=session["user"]["username"],
                uploaded_filename=os.path.basename(filepath),
                rows_before=rows_before,
                rows_after=rows_after,
                impute_method=impute_method,
                outlier_method=outlier_method,
                weight_col=weight_col,
                violations_count=violations_count,
            )
        except Exception as db_err:
            # Fallback: create a temporary session-backed job id
            job_id = int(datetime.now().timestamp())
            temp_jobs = session.get("temp_jobs", {})
            temp_jobs[str(job_id)] = {
                "id": job_id,
                "username": session["user"]["username"],
                "uploaded_filename": os.path.basename(filepath),
                "rows_before": rows_before,
                "rows_after": rows_after,
                "impute_method": impute_method,
                "outlier_method": outlier_method,
                "weight_col": weight_col,
                "violations_count": violations_count,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_saved": False,
            }
            session["temp_jobs"] = temp_jobs
            flash("Database unavailable. Proceeded with a temporary job.", "warning")

        # Persist processed data
        processed_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"processed_{job_id}.csv")
        df.to_csv(processed_filepath, index=False)

        flash("Data processed successfully!", "success")
        return redirect(url_for("view_details", job_id=job_id))

    except Exception as e:
        flash(f"Error processing file: {str(e)}", "danger")
        return redirect(request.url)


# ------------------------------ AJAX Preview ---------------------------------
@app.route("/preview-data", methods=["POST"])
def preview_data():
    try:
        file = request.files.get("data_file")
        if not file or not file.filename:
            return jsonify({"error": "No file uploaded"}), 400

        # Validate extension
        if not allowed_file(file.filename):
            return jsonify({"error": "Unsupported file type. Please upload CSV or Excel."}), 400

        # Save with secure, unique name into configured UPLOAD_FOLDER
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        upload_folder = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)

        # Persist path for subsequent processing
        session["uploaded_file"] = filepath

        # Read small preview from file (CSV or Excel - use first sheet)
        lower = filename.lower()
        if lower.endswith(".csv"):
            df = pd.read_csv(filepath, nrows=50)
        elif lower.endswith((".xlsx",)):
            df = pd.read_excel(filepath, sheet_name=0, nrows=50, engine="openpyxl")
        elif lower.endswith((".xls",)):
            return jsonify({"error": ".xls not supported for preview. Please save as .xlsx or CSV."}), 400
        else:
            return jsonify({"error": "Unsupported file type. Please upload CSV or Excel (.xlsx)."}), 400

        # Coerce obvious numeric text to numeric for better detection
        for column_name in df.columns:
            if df[column_name].dtype == object:
                df[column_name] = pd.to_numeric(df[column_name], errors="ignore")

        preview = df.head(10).to_dict(orient="records")
        columns = list(df.columns)

        return jsonify({"columns": columns, "preview": preview, "stored": unique_filename})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------ View Details --------------------------------- 
@app.route("/view-details/<int:job_id>")
def view_details(job_id: int):
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        job = get_job_by_id(job_id)
        if not job:
            # Try session temp job fallback
            temp = session.get("temp_jobs", {}).get(str(job_id))
            if temp and temp.get("username") == session["user"]["username"]:
                job = temp
            else:
                flash("Job not found or access denied.", "danger")
                return redirect(url_for("dashboard"))
        elif job["username"] != session["user"]["username"]:
            flash("Job not found or access denied.", "danger")
            return redirect(url_for("dashboard"))

        processed_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"processed_{job_id}.csv")
        if os.path.exists(processed_filepath):
            df = pd.read_csv(processed_filepath)

            # Ensure numeric-only selection is robust by coercing numeric-like columns
            for column_name in df.columns:
                if df[column_name].dtype == object:
                    df[column_name] = pd.to_numeric(df[column_name], errors="ignore")

            numeric_cols = df.select_dtypes(include=["number"]).columns
            summary_data = []

            for col in numeric_cols:
                if col == "weight":
                    continue
                if "weight" in df.columns:
                    try:
                        weighted_stats = compute_weighted_summary(df, col, "weight")
                        summary_data.append(
                            {
                                "Variable": col,
                                "Weighted Mean": weighted_stats["weighted_mean"],
                                "Margin of Error (95% CI)": weighted_stats["margin_of_error"],
                            }
                        )
                    except Exception:
                        # fallback to unweighted
                        summary_data.append(
                            {
                                "Variable": col,
                                "Weighted Mean": float(df[col].mean()),
                                "Margin of Error (95% CI)": float(df[col].std() * 1.96 / max(len(df), 1)),
                            }
                        )
                else:
                    summary_data.append(
                        {
                            "Variable": col,
                            "Weighted Mean": float(df[col].mean()),
                            "Margin of Error (95% CI)": float(df[col].std() * 1.96 / max(len(df), 1)),
                        }
                    )

            summary_df = pd.DataFrame(summary_data)
            hist_images = plot_histograms(df, numeric_cols[:5])  # list of image paths/urls

            return render_template(
                "view_details.html",
                job=job,
                summary_df=summary_df,
                hist_images=hist_images,
                user=session["user"],
            )
        else:
            flash("Processed data not found.", "danger")
            return redirect(url_for("dashboard"))

    except Exception as e:
        flash(f"Error loading job details: {str(e)}", "danger")
        return redirect(url_for("dashboard"))


# ------------------------------ Save/Delete Job ------------------------------ 
@app.route("/save-job", methods=["POST"])
def save_job_route():
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    job_id = request.form.get("job_id")
    display_name = request.form.get("display_name", "").strip()

    if not display_name:
        flash("Please provide a name for the saved job.", "warning")
        return redirect(url_for("dashboard"))

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE processing_jobs
            SET display_name = %s, is_saved = 1
            WHERE id = %s AND username = %s
            """,
            (display_name, job_id, session["user"]["username"]),
        )
        conn.commit()
        flash("Job saved successfully!", "success")
    except Exception as e:
        flash(f"Error saving job: {str(e)}", "danger")
    finally:
        _safe_close(cursor, conn)

    return redirect(url_for("dashboard"))


@app.route("/delete-job/<int:job_id>", methods=["POST"])
def delete_job(job_id: int):
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        delete_job_by_id(job_id, session["user"]["username"])
        processed_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"processed_{job_id}.csv")
        if os.path.exists(processed_filepath):
            os.remove(processed_filepath)

        flash("Job deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting job: {str(e)}", "danger")

    return redirect(url_for("dashboard"))


# -------------------------------- Analytics ---------------------------------- 
@app.route("/analytics")
def analytics():
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        all_jobs = get_user_jobs(session["user"]["username"])
        total_runs = len(all_jobs)
        total_rows_after = sum(job.get("rows_after", 0) for job in all_jobs)

        # Admin-only top users
        top_users = []
        if session["user"].get("role") == "admin":
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT username, COUNT(*) AS runs
                FROM processing_jobs
                GROUP BY username
                ORDER BY runs DESC
                LIMIT 10
                """
            )
            top_users = cursor.fetchall()
            _safe_close(cursor, conn)

        stats = {"total_runs": total_runs, "total_rows_after": total_rows_after}

        return render_template(
            "analytics_dashboard.html",
            stats=stats,
            rows=all_jobs,
            top_users=top_users,
            user=session["user"],
        )
    except Exception as e:
        flash(f"Error loading analytics: {str(e)}", "danger")
        return render_template(
            "analytics_dashboard.html",
            stats={"total_runs": 0, "total_rows_after": 0},
            rows=[],
            top_users=[],
            user=session.get("user"),
        )


# --------------------------------- Profile ----------------------------------- 
@app.route("/profile")
def profile():
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        recent_jobs = get_user_jobs(session["user"]["username"])
        saved_jobs = [job for job in recent_jobs if job.get("is_saved")]
        return render_template("profile.html", recent_jobs=recent_jobs, saved_jobs=saved_jobs, user=session["user"])
    except Exception as e:
        flash(f"Error loading profile: {str(e)}", "danger")
        return render_template("profile.html", recent_jobs=[], saved_jobs=[], user=session["user"])


# ------------------------------- Report Gen ---------------------------------- 
@app.route("/generate-report/<int:job_id>")
def generate_report(job_id: int):
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        job = get_job_by_id(job_id)
        if not job:
            temp = session.get("temp_jobs", {}).get(str(job_id))
            if temp and temp.get("username") == session["user"]["username"]:
                job = temp
            else:
                flash("Job not found or access denied.", "danger")
                return redirect(url_for("dashboard"))
        elif job["username"] != session["user"]["username"]:
            flash("Job not found or access denied.", "danger")
            return redirect(url_for("dashboard"))

        processed_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"processed_{job_id}.csv")
        if not os.path.exists(processed_filepath):
            flash("Processed data not found.", "danger")
            return redirect(url_for("dashboard"))

        df = pd.read_csv(processed_filepath)

        numeric_cols = df.select_dtypes(include=["number"]).columns
        summary_data = []

        for col in numeric_cols:
            if col == "weight":
                continue
            if "weight" in df.columns:
                try:
                    weighted_stats = compute_weighted_summary(df, col, "weight")
                    summary_data.append(
                        {
                            "Variable": col,
                            "Weighted Mean": weighted_stats["weighted_mean"],
                            "Margin of Error (95% CI)": weighted_stats["margin_of_error"],
                        }
                    )
                except Exception:
                    summary_data.append(
                        {
                            "Variable": col,
                            "Weighted Mean": float(df[col].mean()),
                            "Margin of Error (95% CI)": float(df[col].std() * 1.96 / max(len(df), 1)),
                        }
                    )
            else:
                summary_data.append(
                    {
                        "Variable": col,
                        "Weighted Mean": float(df[col].mean()),
                        "Margin of Error (95% CI)": float(df[col].std() * 1.96 / max(len(df), 1)),
                    }
                )

        summary_df = pd.DataFrame(summary_data)
        hist_images = plot_histograms(df, numeric_cols[:5])

        metadata = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "prepared_by": session["user"]["username"],
            "rows_before": job["rows_before"],
            "rows_after": job["rows_after"],
            "violations_count": job.get("violations_count"),
            "params": {
                "impute_method": job.get("impute_method"),
                "outlier_method": job.get("outlier_method"),
                "weight_col": job.get("weight_col"),
            },
        }

        workflow_logs = [
            f"Data loaded: {job['rows_before']} rows, {len(df.columns)} columns",
            f"Applied {job['impute_method']} imputation" if job.get("impute_method") != "None" else "No imputation applied",
            f"Applied {job['outlier_method']} outlier detection" if job.get("outlier_method") != "None" else "No outlier detection applied",
            f"Applied weights from column: {job.get('weight_col')}" if job.get("weight_col") else "No weights applied",
            f"Final dataset: {job['rows_after']} rows",
            f"Data quality violations: {job.get('violations_count') or 0}",
        ]

        report_title = f"Survey Data Processing Report - {job['uploaded_filename']}"
        html_path, _html_content = generate_report_html(
            summary_df=summary_df,
            hist_images=hist_images,
            workflow_logs=workflow_logs,
            output_path=os.path.join(app.config["UPLOAD_FOLDER"], f"report_{job_id}.html"),
            report_title=report_title,
            metadata=metadata,
        )

        pdf_path = generate_pdf_report(html_path, os.path.join(app.config["UPLOAD_FOLDER"], f"report_{job_id}.pdf"))

        flash("Report generated successfully!", "success")
        return render_template(
            "report_generated.html", job=job, html_path=html_path, pdf_path=pdf_path, user=session["user"]
        )

    except Exception as e:
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for("dashboard"))


# ------------------------------ Download Report ------------------------------ 
@app.route("/download-report/<int:job_id>/<format>")
def download_report(job_id: int, format: str):
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        job = get_job_by_id(job_id)
        if not job:
            temp = session.get("temp_jobs", {}).get(str(job_id))
            if temp and temp.get("username") == session["user"]["username"]:
                job = temp
            else:
                flash("Job not found or access denied.", "danger")
                return redirect(url_for("dashboard"))
        elif job["username"] != session["user"]["username"]:
            flash("Job not found or access denied.", "danger")
            return redirect(url_for("dashboard"))

        if format == "html":
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], f"report_{job_id}.html")
            mime_type = "text/html"
            filename = f"{job['uploaded_filename']}_report.html"
        elif format == "pdf":
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], f"report_{job_id}.pdf")
            mime_type = "application/pdf"
            filename = f"{job['uploaded_filename']}_report.pdf"
        else:
            flash("Invalid format specified.", "danger")
            return redirect(url_for("dashboard"))

        if not os.path.exists(file_path):
            flash("Report file not found. Please generate the report first.", "danger")
            return redirect(url_for("dashboard"))

        return send_file(file_path, as_attachment=True, download_name=filename, mimetype=mime_type)

    except Exception as e:
        flash(f"Error downloading report: {str(e)}", "danger")
        return redirect(url_for("dashboard"))


# --------------------------------- Logout ------------------------------------ 
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# -------------------------- Optional: Simple Preview -------------------------- 
@app.route("/preview/<path:filename>")
def preview_file(filename):
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(path):
        flash("File not found.", "danger")
        return redirect(url_for("dashboard"))
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
        # The template 'preview.html' expects `tables` (list of HTML) and `titles`
        return render_template(
            "preview.html",
            tables=[df.head(50).to_html(classes="data table", header=True, index=False)],
            titles=df.columns.values,
        )
    except Exception as e:
        flash(f"Error previewing file: {str(e)}", "danger")
        return redirect(url_for("dashboard"))


# --------------------------- Download Processed Data ---------------------------
@app.route("/download-data/<int:job_id>")
def download_data_legacy(job_id: int):
    # Backward-compat CSV download with Excel-friendly BOM
    return _download_processed(job_id, format="csv")


@app.route("/download-data/<int:job_id>/<format>")
def download_data(job_id: int, format: str):
    return _download_processed(job_id, format=format)


def _download_processed(job_id: int, format: str = "csv"):
    if "user" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    try:
        job = get_job_by_id(job_id)
        if not job:
            temp = session.get("temp_jobs", {}).get(str(job_id))
            if temp and temp.get("username") == session["user"]["username"]:
                job = temp
            else:
                flash("Job not found or access denied.", "danger")
                return redirect(url_for("dashboard"))
        elif job["username"] != session["user"]["username"]:
            flash("Job not found or access denied.", "danger")
            return redirect(url_for("dashboard"))

        processed_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"processed_{job_id}.csv")
        if not os.path.exists(processed_filepath):
            flash("Processed data not found. Please run processing again.", "danger")
            return redirect(url_for("view_details", job_id=job_id))

        base_name, _ = os.path.splitext(job.get("uploaded_filename", f"job_{job_id}"))

        fmt = (format or "csv").lower()
        if fmt == "xlsx":
            # Load CSV and write as Excel to a temp file
            df = pd.read_csv(processed_filepath)
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                temp_path = tmp.name
            try:
                df.to_excel(temp_path, index=False, engine="openpyxl")
                filename = f"{base_name}_processed.xlsx"
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                return send_file(temp_path, as_attachment=True, download_name=filename, mimetype=mime)
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        else:
            # Ensure CSV opens nicely in Excel by prepending UTF-8 BOM
            from io import BytesIO
            with open(processed_filepath, "rb") as f:
                content = f.read()
            if not content.startswith(b"\xef\xbb\xbf"):
                content = b"\xef\xbb\xbf" + content
            mem = BytesIO(content)
            filename = f"{base_name}_processed.csv"
            return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv; charset=utf-8")

    except Exception as e:
        flash(f"Error downloading processed data: {str(e)}", "danger")
        return redirect(url_for("view_details", job_id=job_id))


if __name__ == "__main__":
    app.run(debug=True)
