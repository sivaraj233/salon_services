from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = "test"

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Errors123',
    'database': 'salon'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Helper functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Login required'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or user['role'] != 'admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Frontend Routes
# Frontend Routes
@app.route('/')
def index():
    """Render the home page"""
    # Check if user is logged in to potentially show personalized content
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user details for potential personalization
        cursor.execute("SELECT first_name, last_name FROM users WHERE user_id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return render_template('index.html', 
                            logged_in=True,
                            user_name=f"{user['first_name']} {user['last_name']}" if user else None,
                            is_admin=session.get('role') == 'admin')
    
    return render_template('index.html', logged_in=False)

@app.route('/login')
def login_page():
    """Render the login page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    """Render the registration page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Render the appropriate dashboard based on user role"""
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('client_dashboard'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Render the admin dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get stats for admin dashboard
    cursor.execute("SELECT COUNT(*) as total_appointments FROM appointments")
    appointments = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as total_users FROM users WHERE role = 'client'")
    users = cursor.fetchone()
    
    cursor.execute("SELECT SUM(total_price) as revenue FROM sales WHERE DATE(sale_date) = CURDATE()")
    revenue = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html',
                         total_appointments=appointments['total_appointments'],
                         total_users=users['total_users'],
                         daily_revenue=revenue['revenue'] or 0)

@app.route('/client/dashboard')
@login_required
def client_dashboard():
    """Render the client dashboard"""
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user's upcoming appointments
    cursor.execute("""
        SELECT a.*, s.name as service_name 
        FROM appointments a
        JOIN services s ON a.service_id = s.service_id
        WHERE a.client_id = %s AND a.appointment_date >= CURDATE()
        ORDER BY a.appointment_date, a.start_time
        LIMIT 3
    """, (user_id,))
    appointments = cursor.fetchall()
    
    # Format dates
    for appt in appointments:
        appt['appointment_date'] = appt['appointment_date'].strftime('%Y-%m-%d')
        appt['start_time'] = appt['start_time'].strftime('%H:%M')
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', appointments=appointments)

@app.route('/booking')
@login_required
def booking_page():
    """Render the booking page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get available services
    cursor.execute("SELECT * FROM services WHERE is_active = TRUE")
    services = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('booking.html', services=services)

@app.route('/services')
def services_page():
    """Render the services page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM services WHERE is_active = TRUE")
    services = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('services.html', services=services)

@app.route('/products')
def products_page():
    """Render the products page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE is_active = TRUE")
    products = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('products.html', products=products)

@app.route('/logout')
def logout_page():
    """Handle logout"""
    session.clear()
    return redirect(url_for('index'))

# Auth Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'client')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if username exists
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'message': 'Username already exists'}), 400
    
    # Check if email exists
    cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'message': 'Email already exists'}), 400
    
    # Insert new user
    cursor.execute(
        "INSERT INTO users (username, password_hash, email, role, first_name, last_name, phone) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            username,
            generate_password_hash(password),
            email,
            role,
            data.get('first_name'),
            data.get('last_name'),
            data.get('phone')
        )
    )
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'User registered successfully', 'user_id': user_id}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'message': 'Invalid username or password'}), 401
    
    session['user_id'] = user['user_id']
    session['role'] = user['role']
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'user_id': user['user_id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'first_name': user['first_name'],
            'last_name': user['last_name']
        }
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

# Appointment Routes
@app.route('/api/appointments', methods=['GET'])
@login_required
def get_appointments():
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if role == 'admin':
        cursor.execute("""
            SELECT a.*, s.name as service_name, u.first_name, u.last_name 
            FROM appointments a
            JOIN services s ON a.service_id = s.service_id
            JOIN users u ON a.client_id = u.user_id
            ORDER BY a.appointment_date, a.start_time
        """)
    else:
        cursor.execute("""
            SELECT a.*, s.name as service_name 
            FROM appointments a
            JOIN services s ON a.service_id = s.service_id
            WHERE a.client_id = %s
            ORDER BY a.appointment_date, a.start_time
        """, (user_id,))
    
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Format dates and times for response
    for appt in appointments:
        appt['appointment_date'] = appt['appointment_date'].strftime('%Y-%m-%d')
        appt['start_time'] = appt['start_time'].strftime('%H:%M')
        appt['end_time'] = appt['end_time'].strftime('%H:%M')
        appt['created_at'] = appt['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if 'updated_at' in appt and appt['updated_at']:
            appt['updated_at'] = appt['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(appointments)

@app.route('/api/appointments', methods=['POST'])
@login_required
def create_appointment():
    data = request.get_json()
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get service details
    cursor.execute("SELECT * FROM services WHERE service_id = %s", (data['service_id'],))
    service = cursor.fetchone()
    if not service:
        cursor.close()
        conn.close()
        return jsonify({'message': 'Service not found'}), 404
    
    # Calculate end time
    start_time = datetime.strptime(data['start_time'], '%H:%M').time()
    duration = timedelta(minutes=service['duration'])
    end_time = (datetime.combine(datetime.today(), start_time) + duration).time()
    
    # Insert appointment
    cursor.execute("""
        INSERT INTO appointments 
        (client_id, service_id, staff_id, appointment_date, start_time, end_time, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        user_id,
        data['service_id'],
        data.get('staff_id'),
        data['appointment_date'],
        start_time,
        end_time,
        data.get('notes')
    ))
    
    conn.commit()
    appointment_id = cursor.lastrowid
    
    # Get the created appointment to return
    cursor.execute("""
        SELECT a.*, s.name as service_name 
        FROM appointments a
        JOIN services s ON a.service_id = s.service_id
        WHERE a.appointment_id = %s
    """, (appointment_id,))
    
    appointment = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # Format dates and times
    appointment['appointment_date'] = appointment['appointment_date'].strftime('%Y-%m-%d')
    appointment['start_time'] = appointment['start_time'].strftime('%H:%M')
    appointment['end_time'] = appointment['end_time'].strftime('%H:%M')
    
    return jsonify({
        'message': 'Appointment created successfully',
        'appointment': appointment
    }), 201

@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
def update_appointment(appointment_id):
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get existing appointment
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        cursor.close()
        conn.close()
        return jsonify({'message': 'Appointment not found'}), 404
    
    # Check authorization
    if role != 'admin' and appointment['client_id'] != user_id:
        cursor.close()
        conn.close()
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    updates = []
    params = []
    
    # Build update query based on provided data
    if 'service_id' in data:
        cursor.execute("SELECT * FROM services WHERE service_id = %s", (data['service_id'],))
        service = cursor.fetchone()
        if not service:
            cursor.close()
            conn.close()
            return jsonify({'message': 'Service not found'}), 404
        
        updates.append("service_id = %s")
        params.append(data['service_id'])
        
        # Recalculate end time if service changed
        start_time = datetime.strptime(
            data.get('start_time', appointment['start_time'].strftime('%H:%M')), 
            '%H:%M'
        ).time()
        duration = timedelta(minutes=service['duration'])
        end_time = (datetime.combine(datetime.today(), start_time) + duration).time()
        
        updates.append("start_time = %s")
        params.append(start_time)
        updates.append("end_time = %s")
        params.append(end_time)
    
    if 'start_time' in data and 'service_id' not in data:
        start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        updates.append("start_time = %s")
        params.append(start_time)
        
        # Get service duration to calculate end time
        cursor.execute("SELECT duration FROM services WHERE service_id = %s", (appointment['service_id'],))
        service = cursor.fetchone()
        duration = timedelta(minutes=service['duration'])
        end_time = (datetime.combine(datetime.today(), start_time) + duration).time()
        
        updates.append("end_time = %s")
        params.append(end_time)
    
    if 'appointment_date' in data:
        updates.append("appointment_date = %s")
        params.append(data['appointment_date'])
    
    if 'status' in data and role == 'admin':
        updates.append("status = %s")
        params.append(data['status'])
    
    if 'notes' in data:
        updates.append("notes = %s")
        params.append(data['notes'])
    
    if not updates:
        cursor.close()
        conn.close()
        return jsonify({'message': 'No updates provided'}), 400
    
    # Execute update
    query = "UPDATE appointments SET " + ", ".join(updates) + " WHERE appointment_id = %s"
    params.append(appointment_id)
    
    cursor.execute(query, params)
    conn.commit()
    
    # Get updated appointment
    cursor.execute("""
        SELECT a.*, s.name as service_name 
        FROM appointments a
        JOIN services s ON a.service_id = s.service_id
        WHERE a.appointment_id = %s
    """, (appointment_id,))
    
    updated_appointment = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # Format dates and times
    updated_appointment['appointment_date'] = updated_appointment['appointment_date'].strftime('%Y-%m-%d')
    updated_appointment['start_time'] = updated_appointment['start_time'].strftime('%H:%M')
    updated_appointment['end_time'] = updated_appointment['end_time'].strftime('%H:%M')
    
    return jsonify({
        'message': 'Appointment updated successfully',
        'appointment': updated_appointment
    })

@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
@login_required
def cancel_appointment(appointment_id):
    user_id = session['user_id']
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get appointment
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        cursor.close()
        conn.close()
        return jsonify({'message': 'Appointment not found'}), 404
    
    # Check authorization
    if role != 'admin' and appointment['client_id'] != user_id:
        cursor.close()
        conn.close()
        return jsonify({'message': 'Unauthorized'}), 403
    
    # Update status to cancelled
    cursor.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE appointment_id = %s",
        (appointment_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'Appointment cancelled successfully'})

# Product Routes
@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE is_active = TRUE")
    products = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(products)

@app.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO products 
        (name, description, category, price, quantity, reorder_level)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        data['name'],
        data.get('description'),
        data.get('category'),
        data['price'],
        data.get('quantity', 0),
        data.get('reorder_level', 5)
    ))
    
    conn.commit()
    product_id = cursor.lastrowid
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'message': 'Product added successfully',
        'product_id': product_id
    }), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check if product exists
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'message': 'Product not found'}), 404
    
    # Build update query
    updates = []
    params = []
    
    if 'name' in data:
        updates.append("name = %s")
        params.append(data['name'])
    if 'description' in data:
        updates.append("description = %s")
        params.append(data['description'])
    if 'category' in data:
        updates.append("category = %s")
        params.append(data['category'])
    if 'price' in data:
        updates.append("price = %s")
        params.append(data['price'])
    if 'quantity' in data:
        updates.append("quantity = %s")
        params.append(data['quantity'])
    if 'reorder_level' in data:
        updates.append("reorder_level = %s")
        params.append(data['reorder_level'])
    if 'is_active' in data:
        updates.append("is_active = %s")
        params.append(data['is_active'])
    
    if not updates:
        cursor.close()
        conn.close()
        return jsonify({'message': 'No updates provided'}), 400
    
    query = "UPDATE products SET " + ", ".join(updates) + " WHERE product_id = %s"
    params.append(product_id)
    
    cursor.execute(query, params)
    conn.commit()
    
    # Get updated product
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'message': 'Product updated successfully',
        'product': product
    })

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Soft delete (set is_active to FALSE)
    cursor.execute(
        "UPDATE products SET is_active = FALSE WHERE product_id = %s",
        (product_id,)
    )
    conn.commit()
    
    affected_rows = cursor.rowcount
    cursor.close()
    conn.close()
    
    if affected_rows == 0:
        return jsonify({'message': 'Product not found'}), 404
    
    return jsonify({'message': 'Product deactivated successfully'})

# Sales Routes
@app.route('/api/sales', methods=['POST'])
@login_required
def create_sale():
    data = request.get_json()
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get product details
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (data['product_id'],))
        product = cursor.fetchone()
        if not product:
            return jsonify({'message': 'Product not found'}), 404
        
        if product['quantity'] < data['quantity']:
            return jsonify({'message': 'Insufficient stock'}), 400
        
        total_price = product['price'] * data['quantity']
        
        # Record sale
        cursor.execute("""
            INSERT INTO sales 
            (client_id, product_id, quantity, unit_price, total_price, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            data['product_id'],
            data['quantity'],
            product['price'],
            total_price,
            data['payment_method']
        ))
        
        # Update product quantity
        cursor.execute("""
            UPDATE products 
            SET quantity = quantity - %s 
            WHERE product_id = %s
        """, (data['quantity'], data['product_id']))
        
        conn.commit()
        sale_id = cursor.lastrowid
        
        # Get the created sale to return
        cursor.execute("""
            SELECT s.*, p.name as product_name 
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE s.sale_id = %s
        """, (sale_id,))
        
        sale = cursor.fetchone()
        
        return jsonify({
            'message': 'Sale recorded successfully',
            'sale': sale
        }), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({'message': 'Error recording sale', 'error': str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

# Financial Reports
@app.route('/api/reports/sales', methods=['GET'])
@admin_required
def sales_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT 
            DATE(sale_date) as date,
            SUM(total_price) as total_sales,
            COUNT(sale_id) as num_transactions
        FROM sales
    """
    
    params = []
    where_clauses = []
    
    if start_date:
        where_clauses.append("DATE(sale_date) >= %s")
        params.append(start_date)
    if end_date:
        where_clauses.append("DATE(sale_date) <= %s")
        params.append(end_date)
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " GROUP BY DATE(sale_date) ORDER BY DATE(sale_date)"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Convert Decimal to float for JSON serialization
    for result in results:
        result['total_sales'] = float(result['total_sales'])
        result['date'] = result['date'].strftime('%Y-%m-%d')
    
    return jsonify(results)

@app.route('/api/reports/profit-loss', methods=['GET'])
@admin_required
def profit_loss_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total sales
    sales_query = "SELECT SUM(total_price) as total_sales FROM sales"
    sales_params = []
    sales_where = []
    
    if start_date:
        sales_where.append("DATE(sale_date) >= %s")
        sales_params.append(start_date)
    if end_date:
        sales_where.append("DATE(sale_date) <= %s")
        sales_params.append(end_date)
    
    if sales_where:
        sales_query += " WHERE " + " AND ".join(sales_where)
    
    cursor.execute(sales_query, sales_params)
    total_sales = cursor.fetchone()['total_sales'] or 0
    
    # Get total expenses
    expenses_query = "SELECT SUM(amount) as total_expenses FROM expenses"
    expenses_params = []
    expenses_where = []
    
    if start_date:
        expenses_where.append("DATE(expense_date) >= %s")
        expenses_params.append(start_date)
    if end_date:
        expenses_where.append("DATE(expense_date) <= %s")
        expenses_params.append(end_date)
    
    if expenses_where:
        expenses_query += " WHERE " + " AND ".join(expenses_where)
    
    cursor.execute(expenses_query, expenses_params)
    total_expenses = cursor.fetchone()['total_expenses'] or 0
    
    cursor.close()
    conn.close()
    
    profit_loss = total_sales - total_expenses
    
    return jsonify({
        'total_sales': float(total_sales),
        'total_expenses': float(total_expenses),
        'profit_loss': float(profit_loss)
    })

# Feedback Routes
@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    data = request.get_json()
    user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO feedback 
        (client_id, appointment_id, rating, comments)
        VALUES (%s, %s, %s, %s)
    """, (
        user_id,
        data.get('appointment_id'),
        data['rating'],
        data.get('comments')
    ))
    
    conn.commit()
    feedback_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    return jsonify({
        'message': 'Feedback submitted successfully',
        'feedback_id': feedback_id
    }), 201

if __name__ == '__main__':
    app.run(debug=True)