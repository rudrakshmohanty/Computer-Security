from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
import logging
import subprocess
import hashlib
import os
import time
import json  # Add import for JSON handling
from werkzeug.utils import secure_filename
from blockchain import blockchain  # Import the Python blockchain
import random
import string

# Comment out problematic model imports
# Try to import, but don't fail if not available
try:
    from models.pretrained_model import CertificateVerifier
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False
    print("Warning: Certificate verification model not available")

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Configure file upload - ensure paths use backslashes for Windows
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Make sure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload directory: {UPLOAD_FOLDER}")

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="rudraksh",
        database="certificate_fraud_detection"
    )

# Password hashing function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication middleware
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Admin middleware
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            return jsonify({"message": "Admin access required"}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Home page
@app.route("/")
def home():
    return render_template("home.html")

# Login page - GET request to show the form
@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

# Register page - GET request to show the form
@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")

# Blockchain page - Admin only
@app.route("/blockchain")
@admin_required
def blockchain_page():
    return render_template("blockchain.html")

# Certificate dashboard page
@app.route("/certificate_dashboard")
@login_required
def certificate_dashboard():
    # Pass user info to template
    user_info = {
        'username': session.get('username'),
        'email': session.get('email'),
        'role': session.get('role'),
        'id': session.get('user_id')
    }
    return render_template("dashboard.html", user=user_info)

# Dashboard page - redirects to certificate_dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    return redirect(url_for("certificate_dashboard"))

# Issue certificate endpoint
@app.route("/issue_certificate", methods=["POST"])
@login_required
def issue_certificate():
    try:
        data = request.get_json()
        certificate_name = data.get("certificate_name")
        issued_by = data.get("issued_by")
        issue_date = data.get("issue_date")
        owner = data.get("owner")  # New owner field

        if not certificate_name or not issued_by or not issue_date or not owner:
            return jsonify({"message": "All fields are required!"}), 400

        # Generate a random, non-repetitive certificate ID
        certificate_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Create certificate data
        certificate_data = {
            "certificate_id": certificate_id,
            "certificate_name": certificate_name,
            "issued_by": issued_by,
            "issue_date": issue_date,
            "owner": owner
        }

        # Generate block ID as the hash of the certificate ID
        block_id = hashlib.sha256(certificate_id.encode()).hexdigest()

        # Add the certificate to the blockchain
        blockchain.add_block({"block_id": block_id, **certificate_data})

        # Save certificate to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO certificates (certificate_id, block_id, certificate_name, issued_by, issue_date, owner, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (certificate_id, block_id, certificate_name, issued_by, issue_date, owner, session.get('user_id'))
        )
        
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Certificate issued successfully!", "certificate_id": certificate_id}), 200

    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500

# Get certificate by ID
@app.route("/get_certificate/<string:certificate_id>", methods=["GET"])
def get_certificate(certificate_id):
    try:
        if not certificate_id:
            return jsonify({"message": "Certificate ID is required!"}), 400

        # Query the database for the certificate
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT * FROM certificates WHERE certificate_id = %s", 
            (certificate_id,)
        )
        
        cert = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if cert:
            return jsonify(cert), 200

        # As fallback, check the blockchain
        for block in blockchain.chain:
            if block.data.get("certificate_id") == certificate_id:
                return jsonify(block.data), 200

        return jsonify({"message": "Certificate not found!"}), 404

    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500

# API endpoint to check blockchain status - Admin only
@app.route("/api/blockchain-status")
@admin_required
def blockchain_status():
    try:
        status = {
            "connected": True,
            "chain_length": len(blockchain.chain),
            "is_valid": blockchain.is_chain_valid()
        }
        return jsonify(status), 200
    except Exception as e:
        logging.error(f"Error checking blockchain status: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# API endpoint to get all certificates - Admin only
@app.route("/api/certificates", methods=["GET"])
@admin_required
def get_all_certificates():
    try:
        certificates = []
        # Skip genesis block (index 0)
        for block in blockchain.chain[1:]:
            block_data = block.data
            if "certificate_id" in block_data:
                certificates.append({
                    "certificate_name": block_data.get("certificate_name"),
                    "issued_by": block_data.get("issued_by"),
                    "issue_date": block_data.get("issue_date"),
                    "owner": block_data.get("owner"),
                })
        return jsonify({"certificates": certificates}), 200
    except Exception as e:
        logging.error(f"Error fetching certificates: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Initialize the CertificateVerifier
#verifier = CertificateVerifier(r"R:\test\test2\flask-template\models\certificate_forgery_model.keras")

# Endpoint for uploading a certificate
@app.route("/upload_certificate", methods=["POST"])
@login_required
def upload_certificate():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400

        # Save the uploaded file temporarily
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(file_path)

        # Simulate extracting certificate ID from the image (e.g., OCR or metadata)
        extracted_certificate_id = "CERT1234"  # Replace with actual extraction logic

        # Check if the certificate exists in the blockchain
        certificate_found = False
        blockchain_certificate = None
        for block in blockchain.chain:
            if block.data.get("certificate_id") == extracted_certificate_id:
                certificate_found = True
                blockchain_certificate = block.data
                break

        if not certificate_found:
            return jsonify({"message": "Certificate not found in the blockchain"}), 404

        # Use the pre-trained model to verify the certificate
        result, confidence = verifier.verify_certificate(file_path)

        # Compare the model's result and blockchain details
        if result == "HIGH CONFIDENCE REAL" and blockchain_certificate:
            # Check if the blockchain details match the uploaded certificate details
            if (blockchain_certificate["certificate_name"] == request.form.get("certificate_name") and
                    blockchain_certificate["issued_by"] == request.form.get("issued_by") and
                    blockchain_certificate["owner"] == request.form.get("owner")):
                return jsonify({
                    "message": "Certificate verified successfully!",
                    "fraud": False,
                    "confidence": confidence
                }), 200
            else:
                return jsonify({
                    "message": "Certificate details do not match the blockchain. Fraud detected!",
                    "fraud": True,
                    "confidence": confidence
                }), 200
        else:
            return jsonify({
                "message": "Certificate verification failed. Fraud detected!",
                "fraud": True,
                "confidence": confidence
            }), 200

    except Exception as e:
        logging.error(f"Error uploading certificate: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route("/admin/upload_certificate", methods=["POST"])
@admin_required
def admin_upload_certificate():
    try:
        data = request.get_json()
        certificate_name = data.get("certificate_name")
        issued_by = data.get("issued_by")
        issue_date = data.get("issue_date")
        owner = data.get("owner")
        custom_certificate_id = data.get("certificate_id")  # Admin-provided certificate ID

        if not certificate_name or not issued_by or not issue_date or not owner or not custom_certificate_id:
            return jsonify({"message": "All fields are required!"}), 400

        # Generate block ID as the hash of the admin-provided certificate ID
        block_id = hashlib.sha256(custom_certificate_id.encode()).hexdigest()

        # Create certificate data
        certificate_data = {
            "certificate_id": custom_certificate_id,
            "certificate_name": certificate_name,
            "issued_by": issued_by,
            "issue_date": issue_date,
            "owner": owner
        }

        # Add the certificate to the blockchain
        blockchain.add_block({"block_id": block_id, **certificate_data})

        # Save certificate to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO certificates (certificate_id, block_id, certificate_name, issued_by, issue_date, owner, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (custom_certificate_id, block_id, certificate_name, issued_by, issue_date, owner, session.get('user_id'))
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Certificate uploaded successfully!", "certificate_id": custom_certificate_id}), 200

    except Exception as e:
        logging.error(f"Error uploading certificate as admin: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# User registration endpoint
@app.route("/register", methods=["POST"])
def register_user():
    try:
        data = request.get_json()
        logging.debug(f"Register request data: {data}")
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        role = "user"  # Default role

        if not username or not email or not password:
            return jsonify({"message": "All fields are required!"}), 400

        hashed_password = hash_password(password)

        # Check if user already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            cursor.close()
            conn.close()
            return jsonify({"message": "User with this email already exists!"}), 400
        
        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)", 
                      (username, email, hashed_password, role))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User registered successfully!"}), 200

    except Exception as e:
        logging.error(f"Error registering user: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# User login endpoint
@app.route("/login", methods=["POST"])
def login_user():
    try:
        data = request.get_json()
        logging.debug(f"Login request data: {data}")
        
        # The login form in login.html uses 'username' for the field name
        # But the field can contain either username or email
        email_or_username = data.get("username")
        password = data.get("password")

        if not email_or_username or not password:
            return jsonify({"message": "All fields are required!"}), 400

        hashed_password = hash_password(password)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Check if input is email or username
        cursor.execute(
            "SELECT * FROM users WHERE (email = %s OR username = %s) AND password = %s", 
            (email_or_username, email_or_username, hashed_password)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # Store user info in session
            session['user_id'] = user["id"]
            session['username'] = user["username"]
            session['email'] = user["email"]
            session['role'] = user["role"]
            
            # Redirect based on role
            if user["role"] == "admin":
                return jsonify({
                    "message": "Login successful!", 
                    "redirect_url": "/dashboard"
                }), 200
            else:
                return jsonify({
                    "message": "Login successful!", 
                    "redirect_url": "/verify_certificate"
                }), 200
        else:
            return jsonify({"message": "Invalid username/email or password"}), 401

    except Exception as e:
        logging.error(f"Error logging in user: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Logout endpoint
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Dashboard stats endpoint
@app.route("/api/dashboard-stats", methods=["GET"])
@login_required
def dashboard_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get user information
        user_info = {
            "username": session.get("username"),
            "email": session.get("email"),
            "role": session.get("role"),
            "joined": session.get("created_at", "N/A")  # Add created_at to session during login
        }

        # Get total certificates
        if session.get("role") == "admin":
            cursor.execute("SELECT COUNT(*) as count FROM certificates")
        else:
            cursor.execute("SELECT COUNT(*) as count FROM certificates WHERE user_id = %s", 
                           (session.get("user_id"),))
        total_certificates = cursor.fetchone()["count"]

        # Get certificates by category
        if session.get("role") == "admin":
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM certificates 
                GROUP BY category
            """)
        else:
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM certificates 
                WHERE user_id = %s 
                GROUP BY category
            """, (session.get("user_id"),))
        categories = cursor.fetchall()

        # Format category data for chart
        category_data = {cat["category"]: cat["count"] for cat in categories}

        # Get recent activity
        if session.get("role") == "admin":
            cursor.execute("""
                SELECT certificate_name, issued_by, issue_date, owner, created_at 
                FROM certificates 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
        else:
            cursor.execute("""
                SELECT certificate_name, issued_by, issue_date, owner, created_at 
                FROM certificates 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 5
            """, (session.get("user_id"),))
        recent_activity = cursor.fetchall()

        cursor.close()
        conn.close()

        # Prepare response
        stats = {
            "user_info": user_info,
            "total_certificates": total_certificates,
            "category_data": category_data,
            "recent_activity": recent_activity,
            "trust_score": "98%"  # Example static value
        }

        return jsonify(stats), 200

    except Exception as e:
        logging.error(f"Error fetching dashboard stats: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Get all certificates for dashboard display
@app.route("/get_certificates", methods=["GET"])
@login_required
def get_certificates():
    """
    This endpoint is used by the dashboard to display a list of certificates.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if session.get('role') == 'admin':
            cursor.execute("""
                SELECT c.*, u.username as creator_username
                FROM certificates c
                JOIN users u ON c.user_id = u.id
                ORDER BY c.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT c.*, u.username as creator_username
                FROM certificates c
                JOIN users u ON c.user_id = u.id
                WHERE c.user_id = %s
                ORDER BY c.created_at DESC
            """, (session.get('user_id'),))
        
        certificates = cursor.fetchall()
        
        # Ensure all required fields are present
        for cert in certificates:
            cert['certificate_name'] = cert.get('certificate_name', 'Unknown Certificate')
            cert['issued_by'] = cert.get('issued_by', 'Unknown Issuer')
            cert['owner'] = cert.get('owner', 'Unknown Owner')
            cert['created_at'] = cert.get('created_at', 'Unknown Date')
        
        cursor.close()
        conn.close()
        
        return jsonify(certificates), 200

    except Exception as e:
        logging.error(f"Error fetching certificates: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Add a function to verify a certificate
@app.route("/verify_certificate/<string:certificate_id>", methods=["GET"])
def verify_certificate_by_id(certificate_id):
    try:
        if not certificate_id:
            return jsonify({"message": "Certificate ID is required!"}), 400
            
        # Check if certificate exists in database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM certificates WHERE certificate_id = %s", (certificate_id,))
        certificate = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if certificate:
            # Verify on blockchain
            for block in blockchain.chain:
                if block.data.get("certificate_id") == certificate_id:
                    # Verify integrity by checking the hash
                    if block.hash == block.calculate_hash():
                        return jsonify({
                            "verified": True, 
                            "message": "Certificate verified successfully!",
                            "certificate": certificate
                        }), 200
                    else:
                        return jsonify({
                            "verified": False, 
                            "message": "Certificate verification failed. Data may have been tampered with."
                        }), 200
                        
            # If not found in blockchain, still return the database record
            return jsonify({
                "verified": True, 
                "message": "Certificate found in database but not in blockchain.",
                "certificate": certificate
            }), 200
        else:
            # Check blockchain directly as fallback
            for block in blockchain.chain:
                if block.data.get("certificate_id") == certificate_id:
                    if block.hash == block.calculate_hash():
                        return jsonify({
                            "verified": True, 
                            "message": "Certificate verified on blockchain but not found in database.",
                            "certificate": block.data
                        }), 200

        return jsonify({"verified": False, "message": "Certificate not found!"}), 404

    except Exception as e:
        logging.error(f"Error verifying certificate: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route("/verify_certificate", methods=["POST"])
@login_required
def verify_certificate_upload():
    try:
        # Check if a file is uploaded
        if 'file' not in request.files:
            return jsonify({"message": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400

        # Save the uploaded file temporarily
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            app.logger.info(f"Created directory: {app.config['UPLOAD_FOLDER']}")
            
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(file_path)
        app.logger.info(f"Saved file to: {file_path}")
        
        # If model is available, use it for verification
        if MODEL_AVAILABLE:
            try:
                # Use the in-memory verifier directly instead of subprocess
                verifier = CertificateVerifier("simulated_model.keras")
                result, confidence = verifier.verify_certificate(file_path)
                
                return jsonify({
                    "message": result,
                    "confidence": f"{confidence * 100:.2f}%",
                    "fraud": result == "HIGH CONFIDENCE FAKE"
                }), 200
                
            except Exception as e:
                app.logger.error(f"Error using in-memory verifier: {str(e)}")
                # Fallback to simple verification
                return jsonify({
                    "message": "Certificate received (verification error, fallback mode)",
                    "confidence": "N/A",
                    "fraud": False
                }), 200
        else:
            # Fallback to simple file verification if model not available
            return jsonify({
                "message": "Certificate received (model verification unavailable)",
                "confidence": "N/A",
                "fraud": False
            }), 200

    except Exception as e:
        app.logger.error(f"Error verifying certificate: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route("/verify_certificate", methods=["GET"])
@login_required
def verify_certificate_page():
    return render_template("verify_certificate.html")

# Admin endpoints
@app.route("/admin/make_admin/<int:user_id>", methods=["POST"])
@admin_required
def make_admin(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"User {user_id} promoted to admin"}), 200
    except Exception as e:
        logging.error(f"Error updating user role: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

@app.route("/admin/users", methods=["GET"])
@admin_required
def get_all_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, role, created_at FROM users")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"users": users}), 200
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# Initialize the model only if available
if MODEL_AVAILABLE:
    try:
        verifier = CertificateVerifier("simulated_model.keras")
        print("Certificate verifier initialized successfully")
    except Exception as e:
        print(f"Error initializing model: {e}")
        MODEL_AVAILABLE = False

if __name__ == '__main__':
    app.run(debug=True)
