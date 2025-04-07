from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import mysql.connector
import os
from datetime import datetime, timedelta

# Load environment variables

# Get username & password from .env file
VALID_USERNAME = "admin"
VALID_PASSWORD = "Pass@123"

app = Flask(__name__)
# Define and create the upload folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), "static/img")  # ✅ Corrected path
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER  # ✅ Set correct upload path

app.secret_key = "your_secret_key"  # Required for session management
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Errors123",
    database="salon"
)
cursor = db.cursor()
# Home Route
@app.route("/")
def home():
    return render_template("index.html")

# About Route
@app.route("/about")
def about():
    return render_template("about.html")

# Contact Route
@app.route("/contact")
def contact():
    return render_template("contact.html")

# Portfolio Route
@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")

# Services Route
@app.route("/services")
def services():
    cursor = db.cursor(dictionary=True)  # Fetch results as dictionary
    cursor.execute("SELECT sno, name, Image, price FROM service WHERE is_active = 1")
    services = cursor.fetchall()
    cursor.close()
    print("Fetched services:", services)  # Debugging statement
    return render_template("services.html", services=services)

# ✅ New Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    print(f"Request method: {request.method}")
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session["user"] = username  # Store session
            return redirect(url_for("dashboard"))  # Redirect to dashboard
        else:
            return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("admin/dashboard.html", username=session["user"])
    else:
        return redirect(url_for("login"))


@app.route("/add_service", methods=["GET", "POST"])
def add_service():
    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        isactive = int(request.form.get("isactive", 1))  # Default to 1 if not provided

        # Handling image upload
        image = request.files.get("image")
        if image and image.filename:  # Check if file is uploaded
            filename = secure_filename(image.filename)  # Secure filename
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)  # ✅ Save image in static/img folder

        else:
            filename = None  # Store NULL in the database if no image is uploaded

        # Insert into database
        cursor = db.cursor()
        query = "INSERT INTO service (name, Image, price, is_active) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (name, filename, price, isactive))
        db.commit()
        cursor.close()
        return redirect(url_for("services"))  # Redirect back after adding service

    return render_template("dashboard.html")  # Render the form if GET request

@app.route('/service/<int:service_id>')
def service_detail(service_id):
    cursor = db.cursor(dictionary=True)  # Fetch results as dictionary
    cursor.execute("SELECT * FROM service WHERE is_active = 1 AND sno = %s", (service_id,))
    service = cursor.fetchone()  # Fetch a single service
    cursor.close()

    if not service:
        return "Service not found", 404

    return render_template('serivce_details.html', service=service)



@app.route('/book_appointment/<int:service_id>', methods=['POST'])
def book_appointment(service_id):
    customer_name = request.form['customer_name']
    customer_email = request.form['customer_email']
    appointment_date = request.form['appointment_date']

    # Convert string date to datetime format
    selected_datetime = datetime.strptime(appointment_date, "%Y-%m-%dT%H:%M")

    # Define 1-hour window
    one_hour_before = selected_datetime - timedelta(hours=1)
    one_hour_after = selected_datetime + timedelta(hours=1)

    cursor = db.cursor(dictionary=True)

    # **Check for conflicting appointments within the 1-hour range**
    cursor.execute("""
        SELECT * FROM appointments 
        WHERE service_id = %s 
        AND appointment_date BETWEEN %s AND %s
    """, (service_id, one_hour_before, one_hour_after))

    existing_appointment = cursor.fetchone()
    
    if existing_appointment:
        flash("Sorry, this time slot is already booked or conflicts with another appointment (1-hour gap required).", "danger")
    else:
        cursor.execute("""
            INSERT INTO appointments (service_id, customer_name, customer_email, appointment_date)
            VALUES (%s, %s, %s, %s)
        """, (service_id, customer_name, customer_email, appointment_date))
        db.commit()
        flash("Appointment booked successfully!", "success")

    cursor.close()
    return redirect(url_for('service_detail', service_id=service_id))


@app.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/view_appointments')
def view_appointments():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT a.id, s.name AS service_name, a.customer_name, a.customer_email, a.appointment_date FROM appointments a JOIN service s ON a.service_id = s.sno")
    appointments = cursor.fetchall()
    cursor.close()

    return render_template('view_appointments.html', appointments=appointments)
if __name__ == "__main__":
    app.run(debug=True)
