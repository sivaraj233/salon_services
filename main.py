from flask import Flask, render_template, jsonify, redirect, url_for, request,g, flash, session
from werkzeug.utils import secure_filename
import mysql.connector
import os
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = Flask(__name__)
# Set a secret key for session management
app.secret_key = "your_secret_key_here"  # Replace with a strong, unique key
UPLOAD_FOLDER = os.path.join(os.getcwd(), "static/img")  # ✅ Corrected path
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER  # ✅ Set correct upload path

# Get username & password from .env file
VALID_USERNAME = "admin"
VALID_PASSWORD = "Pass@123"
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Database connection function
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Errors123",
            database="salon"
        )
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route("/admin/dashboard")
def dashboard():
    return render_template("admin/dashboard.html")

@app.route("/manage-appointment")
def manage_appointment():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
# Get selected date from request (default: today's date)
    filter_date = request.args.get('filter_date', None)

    if filter_date:
        cursor.execute("""
            SELECT appointment_id, customer_name, appointment_date, appointment_time, status 
            FROM appointments 
            WHERE appointment_date = %s
            ORDER BY appointment_time ASC
        """, (filter_date,))
    else:
        cursor.execute("""
            SELECT appointment_id, customer_name, appointment_date, appointment_time, status 
            FROM appointments 
            ORDER BY appointment_date DESC, appointment_time ASC
        """)
    
    appointments = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("admin/manage_appointment.html", appointments=appointments, selected_date=filter_date)

@app.route("/confirm-appointments")
def confirm_appointments():
    today_date = date.today().strftime('%Y-%m-%d')  # Get today's date in YYYY-MM-DD format

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch confirmed appointments for today only
    cursor.execute("""
        SELECT a.appointment_id, a.customer_name, a.phone, a.service, 
               a.appointment_date, a.appointment_time, a.status, 
               s.name AS staff_name
        FROM appointments a
        LEFT JOIN staff s ON a.staff_id = s.staff_id
        WHERE a.status = 'Confirmed' AND a.appointment_date = %s
        ORDER BY a.appointment_time ASC
    """, (today_date,))

    confirmed_appointments = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("admin/confirm_appointment.html", appointments=confirmed_appointments)


@app.route("/cancel-appointments")
def cancel_appointments():
    today_date = date.today().strftime('%Y-%m-%d')  # Get today's date

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch canceled appointments for today only
    cursor.execute("""
        SELECT a.appointment_id, a.customer_name, a.phone, a.service, 
               a.appointment_date, a.appointment_time, a.status, 
               s.name AS staff_name
        FROM appointments a
        LEFT JOIN staff s ON a.staff_id = s.staff_id
        WHERE a.status = 'Cancelled' AND a.appointment_date = %s
        ORDER BY a.appointment_time ASC
    """, (today_date,))

    canceled_appointments = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("admin/cancel_appointment.html", appointments=canceled_appointments)

@app.route("/available_slots")
def available_slots():
    today_date = date.today().strftime('%Y-%m-%d')
    print(today_date)
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Fetch available slots for today
    cursor.execute("""
        SELECT a.appointment_id, a.customer_name, a.phone, a.service, 
            a.appointment_date, a.appointment_time, 
            s.name, a.status 
        FROM appointments a
        LEFT JOIN staff s ON a.staff_id = s.staff_id
        WHERE a.appointment_date = %s AND a.status = 'Pending'
        ORDER BY a.appointment_time ASC
    """, (today_date,))

    
    available_slots = cursor.fetchall()
    cursor.close()

    # Debugging output
    print("Fetched Available Slots:", available_slots)

    return render_template("admin/available_slots.html", appointments=available_slots)

@app.route("/confirm-appointment/<int:appointment_id>", methods=["POST"])
def confirm_appointment(appointment_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Fetch appointment details
        cursor.execute("""
            SELECT customer_email, service, appointment_date, appointment_time 
            FROM appointments 
            WHERE appointment_id = %s
        """, (appointment_id,))
        appointment = cursor.fetchone()

        if not appointment:
            return jsonify({"success": False, "message": "Appointment not found"}), 404

        # Update appointment status to 'Confirmed'
        cursor.execute("""
            UPDATE appointments 
            SET status = 'Confirmed' 
            WHERE appointment_id = %s
        """, (appointment_id,))
        db.commit()

        # Send confirmation email
        send_confirmation_email(appointment)

        cursor.close()
        db.close()

        return jsonify({"success": True, "message": "Appointment confirmed successfully!"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
@app.route("/cancel-appointment/<int:appointment_id>", methods=["POST"])
def cancel_appointment(appointment_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Update appointment status to 'Canceled'
        cursor.execute("""
            UPDATE appointments 
            SET status = 'Cancelled' 
            WHERE appointment_id = %s
        """, (appointment_id,))
        
        db.commit()
        cursor.close()
        db.close()

        # ✅ Return a success message
        return jsonify({"success": True, "message": "Appointment canceled successfully!"}), 200
    
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@app.route("/add-appointment", methods=["GET", "POST"])
def add_appointment():
    if request.method == "POST":
        customer_name = request.form["customer_name"]
        phone = request.form["phone"]
        service_id = request.form["service_id"]
        service_name = request.form["service_name"]
        appointment_date = request.form["appointment_date"]
        appointment_time = request.form["appointment_time"]  # HH:00 format
        staff_id = request.form["staff_id"]
        customer_email = request.form["customer_email"]
        
        status = "Pending"

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Check if the same staff is already booked at the same date & time
        cursor.execute("""
            SELECT COUNT(*) AS count FROM appointments 
            WHERE appointment_date = %s AND appointment_time = %s AND staff_id = %s
        """, (appointment_date, appointment_time, staff_id))

        result = cursor.fetchone()
        if result["count"] > 0:
            print("comming")
            flash("This staff is already booked at the selected time. Please choose a different time or staff.", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("add_appointment"))

        # Insert the new appointment if staff is available
        cursor.execute("""
            INSERT INTO appointments (customer_name, phone, service_id, appointment_date, appointment_time, staff_id, status, service, customer_email) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (customer_name, phone, service_id, appointment_date, appointment_time, staff_id, status, service_name, customer_email))

        db.commit()
        cursor.close()
        db.close()

        flash("Appointment added successfully!", "success")
        return redirect(url_for("manage_appointment"))

    # Fetch staff and services for dropdown
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT staff_id, name FROM staff")
    staff_list = cursor.fetchall()

    cursor.execute("SELECT service_id, service_name FROM services")
    service_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin/add_appointment.html", staff_list=staff_list, service_list=service_list)

@app.route("/request-appointment", methods=["POST"])
def request_appointment():
    if request.method == "POST":
        customer_name = request.form["customer_name"]
        customer_email = request.form["customer_email"]
        phone = request.form["phone"]
        service_id = request.form["service_id"]
        service_name = request.form["service_name"]
        appointment_date = request.form["appointment_date"]
        appointment_time = request.form["appointment_time"]  # HH:00 format
        
        staff_id = request.form["staff_id"]
        status = "Pending"

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Check if the staff is already booked at the same date & time
        cursor.execute("""
            SELECT COUNT(*) AS count FROM appointments 
            WHERE appointment_date = %s AND appointment_time = %s AND staff_id = %s
        """, (appointment_date, appointment_time, staff_id))

        result = cursor.fetchone()
        if result["count"] > 0:
            flash("This staff is already booked at the selected time. Please choose a different time or staff.", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("services"))  # Redirect to services page

        # Insert new appointment
        cursor.execute("""
            INSERT INTO appointments (customer_name, phone, service_id, appointment_date, appointment_time, staff_id, status, service, customer_email) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (customer_name, phone, service_id, appointment_date, appointment_time, staff_id, status, service_name, customer_email))

        db.commit()
        cursor.close()
        db.close()

        flash("Your appointment has been successfully booked!", "success")
        return redirect(url_for("services"))  # Redirect to services page



# client Page
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
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT service_id, service_name, duration_hours, price, Image FROM services")
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

# @app.route("/dashboard")
# def dashboard():
#     if "user" in session:
#         return render_template("dashboard.html", username=session["user"])
#     else:
#         return redirect(url_for("login"))


@app.route("/add_service", methods=["GET", "POST"])
def add_service():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":

        service_name = request.form['service_name']
        duration_hours = request.form['duration_hours']
        price = request.form['price']

        # Handle Image Upload
        image = request.files['image']
        if image and image.filename:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)
            image_url = f"/{image_path}"  # Relative Path for HTML
        else:
            image_url = None

        cursor.execute("INSERT INTO services (service_name, duration_hours, price, image) VALUES (%s, %s, %s, %s)", 
                    (service_name, duration_hours, price, image.filename))
        db.commit()
        cursor.close()
        return redirect(url_for("services"))  # Redirect back after adding service
    cursor.execute("SELECT * FROM services")
    services = cursor.fetchall()
    return render_template("admin/add_service.html", services=services)  # Render the form if GET request

@app.route('/edit/<int:service_id>', methods=['GET', 'POST'])
def edit_service(service_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        service_name = request.form['service_name']
        duration_hours = request.form['duration_hours']
        price = request.form['price']

        # Handle Image Upload
        image = request.files['image']
        if image and image.filename:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)
            image_url = f"/{image_path}"
            cursor.execute("UPDATE services SET service_name=%s, duration_hours=%s, price=%s, image=%s WHERE service_id=%s",
                           (service_name, duration_hours, price, image.filename, service_id))
        else:
            cursor.execute("UPDATE services SET service_name=%s, duration_hours=%s, price=%s WHERE service_id=%s",
                           (service_name, duration_hours, price, service_id))

        db.commit()
        return redirect(url_for('add_service'))

    cursor.execute("SELECT * FROM services WHERE service_id=%s", (service_id,))
    service = cursor.fetchone()
    return render_template('admin/edit_service.html', service=service)


@app.route('/service/<int:service_id>')
def service_detail(service_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Fetch service details
    cursor.execute("SELECT * FROM services WHERE service_id = %s", (service_id,))
    service = cursor.fetchone()
    
    # Fetch staff list
    cursor.execute("SELECT staff_id, name FROM staff")
    staff_list = cursor.fetchall()
    
    # Fetch booked appointments
    cursor.execute("""
    SELECT staff_id, 
           DATE(appointment_time) AS appointment_date, 
           TIME_FORMAT(appointment_time, '%H:%i') AS appointment_time 
    FROM appointments 
    WHERE status = 'Confirmed' 
      AND service_id = %s 
      AND DATE(appointment_date) = CURDATE()
""", (service_id,))

    booked_times = cursor.fetchall()
  # Fetch booked times as properly formatted strings
    
    cursor.close()
    
    if not service:
        return "Service not found", 404

    return render_template('serivce_details.html', service=service, staff_list=staff_list, booked_times=booked_times)


@app.route('/customers')
def list_customers():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch distinct customer details from the appointments table
    cursor.execute("""
        SELECT DISTINCT customer_name, phone 
        FROM appointments
        ORDER BY customer_name ASC
    """)

    customers = cursor.fetchall()
    cursor.close()

    return render_template("admin/customers_list.html", customers=customers)

@app.route('/products')
def products():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    return render_template('admin/products.html', products=products)

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        product_code = request.form['product_code']
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']
        
        # Handle Image Upload
        image_file = request.files['image']
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)  # Save image to static/img/
        else:
            flash("Invalid image format. Allowed: png, jpg, jpeg, gif", "danger")
            return redirect(url_for('add_product'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO products (product_code, name, price, description, image)
            VALUES (%s, %s, %s, %s, %s)
        """, (product_code, name, price, description, filename))
        
        db.commit()
        cursor.close()
        
        flash("Product added successfully!", "success")
        return redirect(url_for('products'))  # Redirect to product list page

    return render_template('admin/add_product.html')

@app.route("/update-product/<int:product_id>", methods=["GET", "POST"])
def update_product(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        product_code = request.form["product_code"]
        name = request.form["name"]
        price = request.form["price"]
        description = request.form["description"]
        image = request.files["image"]

        # Fetch existing product details
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            flash("Product not found!", "danger")
            return redirect(url_for("product_list"))

        # If new image uploaded, save it; otherwise, keep old one
        image_filename = product["image"]
        if image and image.filename:
            image_filename = image.filename
            image.save(os.path.join("static/img", image_filename))

        # Update product in the database
        cursor.execute("""
            UPDATE products 
            SET product_code = %s, name = %s, price = %s, description = %s, image = %s
            WHERE product_id = %s
        """, (product_code, name, price, description, image_filename, product_id))

        db.commit()
        flash("Product updated successfully!", "success")
        return redirect(url_for("products"
        ""))

    # Fetch product details for form pre-filling
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()

    if not product:
        return "Product not found", 404

    return render_template("admin/update_product.html", product=product)


@app.route("/delete-product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    db = get_db()
    cursor = db.cursor()

    # Check if product exists
    cursor.execute("SELECT image FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for("product_list"))

    # Delete the image file if exists
    image_path = os.path.join("static/img", product[0])
    if os.path.exists(image_path):
        os.remove(image_path)

    # Delete product from database
    cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
    db.commit()

    flash("Product deleted successfully!", "success")
    return redirect(url_for("products"))

# Delete Service
@app.route('/delete/<int:service_id>')
def delete_service(service_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM services WHERE service_id=%s", (service_id,))
    db.commit()
    return redirect(url_for('add_service'))

def send_confirmation_email(appointment):
    try:
        sender_email = "test@gmail.com"  # Change to your email
        sender_password = "g*Q%W+f/6456"  # Use an app password if using Gmail
        recipient_email = appointment["customer_email"]

        subject = "Appointment Confirmation - Salon"
        body = f"""
        Dear Customer,

        Your appointment for {appointment['service']} on {appointment['appointment_date']} at {appointment['appointment_time']} has been confirmed.

        We look forward to serving you!

        Regards,  
        Salon
        """

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())

        print("Email sent successfully!")

    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    app.run(debug=True)
