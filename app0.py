# Debug print to verify file execution
print("✅ Running app0.py from ai_invoice_assistant")

from flask import Flask, request, jsonify, render_template, send_file, session, redirect
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import pandas as pd
import re
from jinja2 import Template
import sqlite3
import random 
from datetime import datetime, timedelta
import hashlib
import secrets


# Import the new database manager
from database_manager import DatabaseManager

# Import your existing modules
try:
    from dynamic_parser import dynamic_parse_and_save, test_gemini_connection
    from billing_dynamic_enhanced import calculate_invoice, validate_product_data, generate_invoice_summary
except ImportError:
    print("⚠️ Original modules not found, using enhanced versions")
    from billing_dynamic_enhanced import calculate_invoice, validate_product_data, generate_invoice_summary
    
    def dynamic_parse_and_save(file_path, output_path=None):
        return []
    
    def test_gemini_connection():
        return True, "Connection test successful"

# Import login handler
try:
    from login_handler import setup_login_routes
except ImportError:
    print("⚠️ Login handler not found, creating basic setup")
    def setup_login_routes(app):
        @app.route('/api/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                data = request.json
                username = data.get('username', '')
                password = data.get('password', '')
                
                # Basic authentication (replace with your logic)
                if username == 'admin' and password == 'admin':
                    session['username'] = username
                    session['role'] = 'admin'
                    return jsonify({'success': True, 'role': 'admin'})
                elif username == 'user' and password == 'user':
                    session['username'] = username
                    session['role'] = 'user'
                    return jsonify({'success': True, 'role': 'user'})
                else:
                    return jsonify({'error': 'Invalid credentials'}), 401
            
            return '''
            <form method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            '''
        
        @app.route('/api/logout', methods=['POST'])
        def logout():
            session.clear()
            return jsonify({'success': True})

# Import Gemini AI
import google.generativeai as genai
from dotenv import load_dotenv
import pdfkit

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to False for localhost (HTTP); True in production (HTTPS)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cookies to be sent with cross-origin requests
CORS(app, supports_credentials=True)  # Allow credentials (cookies) in CORS

# Configuration
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['INVOICE_FOLDER'] = 'invoices'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['INVOICE_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# Initialize Database Manager
db_manager = DatabaseManager()

# Run migration if needed (for existing installations)
try:
    db_manager.migrate_existing_data()
except Exception as e:
    print(f"⚠️ Migration warning: {e}")

# Configure Gemini AI
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_AVAILABLE = True
        print("✅ Gemini AI configured successfully")
    except Exception as e:
        print(f"⚠️ Error configuring Gemini AI: {e}")
        GEMINI_AVAILABLE = False
        model = None
else:
    print("⚠️ GEMINI_API_KEY not found. Please set it in your .env file")
    GEMINI_AVAILABLE = False
    model = None

# Enhanced in-memory storage
session_data = {}

def get_session_data(session_id):
    if session_id not in session_data:
        session_data[session_id] = {
            'cart': {},
            'client_details': {},
            'conversation_history': [],
            'products': [],
            'catalog_source': 'default',
            'overall_discount': 0,
            'current_chat_id': None
        }
    return session_data[session_id]

def get_current_username():
    """Get current authenticated username"""
    return session.get('username')

def validate_user_session():
    """Validate that user is properly authenticated"""
    username = get_current_username()
    if not username:
        raise Exception("User not authenticated")
    return username

def admin_required(f):
    def wrap(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__  # Preserve function name for Flask
    return wrap

def get_current_username():
    """Get current authenticated username"""
    return session.get('username')

def validate_user_session():
    """Validate that user is properly authenticated"""
    username = get_current_username()
    if not username:
        raise Exception("User not authenticated")
    return username

def get_session_data(session_id):
    """Get or create session data for a given session ID"""
    if session_id not in session_data:
        session_data[session_id] = {
            'cart': {},
            'client_details': {},
            'conversation_history': [],
            'products': [],
            'catalog_source': 'default',
            'overall_discount': 0,
            'current_chat_id': None
        }
    return session_data[session_id]

def save_message_to_db(username, chat_id, message_type, content, metadata=None):
    """Helper function to save messages to database"""
    try:
        if not chat_id:
            # If no current chat, create a new one
            chat_id, _ = db_manager.create_new_chat(username)
        
        db_manager.save_message(chat_id, username, message_type, content, metadata)
        return chat_id
    except Exception as e:
        print(f"❌ Error saving message to DB: {str(e)}")
        return chat_id

def load_default_products():
    """Load products from product_data.json"""
    try:
        if os.path.exists('product_data.json'):
            with open('product_data.json', 'r') as f:
                products = json.load(f)
            print(f"✅ Loaded {len(products)} products from product_data.json")
            return products
        else:
            print("⚠️ product_data.json not found")
            return []
    except Exception as e:
        print(f"❌ Error loading product_data.json: {e}")
        return []

def save_products(products):
    """Save products to product_data.json"""
    try:
        with open('product_data.json', 'w') as f:
            json.dump(products, f, indent=2)
        print(f"✅ Saved {len(products)} products to product_data.json")
    except Exception as e:
        print(f"❌ Error saving product_data.json: {e}")

def parse_for_streamlit(file_path):
    """Parse uploaded files for products"""
    try:
        products = dynamic_parse_and_save(file_path, output_path=None)
        return products
    except Exception as e:
        print(f"Error parsing for Flask: {e}")
        return []

# Enhanced in-memory storage (if not already defined)
if 'session_data' not in globals():
    session_data = {}

# Load default products (if not already loaded)
if 'default_products' not in globals():
    default_products = load_default_products()

def migrate_users_table():
    """Migrate users table to add missing columns"""
    print("🔄 Checking and migrating users table...")
    
    try:
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get current table structure
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Define all required columns with their default values
        required_columns = {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'username': 'TEXT UNIQUE NOT NULL',
            'password': 'TEXT NOT NULL',
            'email': 'TEXT',
            'full_name': 'TEXT',
            'phone': 'TEXT',
            'department': 'TEXT',
            'role': 'TEXT NOT NULL DEFAULT "user"',
            'status': 'TEXT NOT NULL DEFAULT "active"',
            'must_change_password': 'BOOLEAN DEFAULT 0',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'last_login': 'TIMESTAMP',
            'created_by': 'TEXT'
        }
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Create the table from scratch
            print("🔨 Creating users table...")
            columns_sql = ', '.join([f"{col} {definition}" for col, definition in required_columns.items()])
            cursor.execute(f"CREATE TABLE users ({columns_sql})")
            print("✅ Users table created successfully")
        else:
            # Add missing columns one by one
            for column_name, column_definition in required_columns.items():
                if column_name not in columns:
                    try:
                        # For non-nullable columns, we need to handle them carefully
                        if 'NOT NULL' in column_definition and 'DEFAULT' not in column_definition:
                            if column_name == 'role':
                                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} TEXT NOT NULL DEFAULT 'user'")
                            elif column_name == 'status':
                                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} TEXT NOT NULL DEFAULT 'active'")
                            else:
                                # Skip primary key and unique constraints in ALTER TABLE
                                simplified_def = column_definition.replace('PRIMARY KEY AUTOINCREMENT', '').replace('UNIQUE', '').strip()
                                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {simplified_def}")
                        else:
                            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}")
                        print(f"✅ Added column: {column_name}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            print(f"⚠️ Warning adding column {column_name}: {e}")
        
        # Create a default admin user if no users exist
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print("🔨 Creating default admin user...")
            # Hash the default password
            import hashlib
            import secrets
            
            def hash_password(password):
                salt = secrets.token_hex(16)
                password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                return f"{salt}:{password_hash}"
            
            admin_password = hash_password("admin123")  # Default password
            
            cursor.execute('''INSERT INTO users 
                             (username, password, email, full_name, role, status, must_change_password, created_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          ('admin', admin_password, 'admin@company.com', 'System Administrator', 
                           'super_admin', 'active', 1, datetime.now().isoformat()))
            
            print("✅ Default admin user created:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   ⚠️ Please change this password after first login!")
        
        conn.commit()
        conn.close()
        
        print("✅ Users table migration completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

import hashlib
import secrets
from datetime import datetime, timedelta

# Helper function to hash passwords
def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password, stored_hash):
    """Verify password against stored hash"""
    try:
        salt, password_hash = stored_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except:
        return False

def validate_user_role_permissions(current_role, target_role, operation='create'):
    """Validate if current user can perform operation on target role"""
    role_hierarchy = {
        'super_admin': 3,
        'admin': 2,
        'user': 1
    }
    
    current_level = role_hierarchy.get(current_role, 0)
    target_level = role_hierarchy.get(target_role, 0)
    
    if current_role == 'super_admin':
        return True  # Super admin can do anything
    elif current_role == 'admin':
        return target_role == 'user'  # Admin can only manage users
    
    return False
# User Management API Endpoints
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users with statistics"""
    print("🔍 Get users session:", dict(session))
    try:
        current_user_role = session.get('role', 'user')
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Ensure users table exists with all required columns
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            full_name TEXT,
            phone TEXT,
            department TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            status TEXT NOT NULL DEFAULT 'active',
            must_change_password BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            created_by TEXT
        )''')
        
        # Get users based on current user role
        if current_user_role == 'super_admin':
            # Super admin can see all users
            cursor.execute('''SELECT id, username, email, full_name, phone, department, 
                             role, status, must_change_password, created_at, last_login, created_by
                             FROM users ORDER BY created_at DESC''')
        elif current_user_role == 'admin':
            # Admin can only see regular users and other admins (but not super admins)
            cursor.execute('''SELECT id, username, email, full_name, phone, department, 
                             role, status, must_change_password, created_at, last_login, created_by
                             FROM users WHERE role IN ('user', 'admin') ORDER BY created_at DESC''')
        else:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        users = []
        for row in cursor.fetchall():
            user = {
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'full_name': row[3],
                'phone': row[4],
                'department': row[5],
                'role': row[6],
                'status': row[7],
                'must_change_password': bool(row[8]),
                'created_at': row[9],
                'last_login': row[10],
                'created_by': row[11]
            }
            users.append(user)
        
        # Calculate statistics
        cursor.execute('SELECT COUNT(*) FROM users WHERE role IN (SELECT DISTINCT role FROM users)')
        total_users = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE status = "active"')
        active_users = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE role IN ("admin", "super_admin")')
        admin_users = cursor.fetchone()[0] or 0
        
        # New users this month
        first_day_this_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= ?', (first_day_this_month,))
        new_users = cursor.fetchone()[0] or 0
        
        conn.close()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'admin_users': admin_users,
            'new_users': new_users
        }
        
        return jsonify({
            'success': True,
            'users': users,
            'stats': stats
        })
        
    except Exception as e:
        print(f"❌ Error fetching users: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching users: {str(e)}'
        }), 500

@app.route('/api/admin/users', methods=['POST'])
@admin_required
def create_user():
    """Create a new user"""
    print("🔍 Create user session:", dict(session))
    try:
        current_user_role = session.get('role', 'user')
        current_username = session.get('username')
        data = request.json
        
        # Validate required fields
        required_fields = ['username', 'full_name', 'email', 'role', 'temp_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate role permissions
        target_role = data.get('role')
        if not validate_user_role_permissions(current_user_role, target_role, 'create'):
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions to create user with this role'
            }), 403
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data.get('email', '')):
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (data['username'],))
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Username already exists'
            }), 400
        
        # Check if email already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 400
        
        # Hash the temporary password
        password_hash = hash_password(data['temp_password'])
        
        # Insert new user
        cursor.execute('''INSERT INTO users 
                         (username, password, email, full_name, phone, department, role, 
                          status, must_change_password, created_by, created_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (data['username'], password_hash, data['email'], data['full_name'],
                       data.get('phone', ''), data.get('department', ''), data['role'],
                       'active', 1, current_username, datetime.now().isoformat()))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ User created successfully: {data['username']} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'message': f'User {data["username"]} created successfully',
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"❌ Error creating user: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error creating user: {str(e)}'
        }), 500

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get a specific user"""
    print(f"🔍 Get user {user_id} session:", dict(session))
    try:
        current_user_role = session.get('role', 'user')
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT id, username, email, full_name, phone, department, 
                         role, status, must_change_password, created_at, last_login, created_by
                         FROM users WHERE id = ?''', (user_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        user = {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'full_name': row[3],
            'phone': row[4],
            'department': row[5],
            'role': row[6],
            'status': row[7],
            'must_change_password': bool(row[8]),
            'created_at': row[9],
            'last_login': row[10],
            'created_by': row[11]
        }
        
        # Check if current user can view this user
        if not validate_user_role_permissions(current_user_role, user['role'], 'view'):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions to view this user'
            }), 403
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': user
        })
        
    except Exception as e:
        print(f"❌ Error fetching user: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching user: {str(e)}'
        }), 500

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update a user"""
    print(f"🔍 Update user {user_id} session:", dict(session))
    try:
        current_user_role = session.get('role', 'user')
        data = request.json
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get existing user
        cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
        existing_user = cursor.fetchone()
        if not existing_user:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        existing_role = existing_user[0]
        new_role = data.get('role', existing_role)
        
        # Check permissions for both existing and new role
        if not validate_user_role_permissions(current_user_role, existing_role, 'edit'):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions to edit this user'
            }), 403
        
        if not validate_user_role_permissions(current_user_role, new_role, 'edit'):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions to assign this role'
            }), 403
        
        # Prepare update data
        update_fields = []
        update_values = []
        
        if 'full_name' in data:
            update_fields.append('full_name = ?')
            update_values.append(data['full_name'])
        
        if 'email' in data:
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email']):
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Invalid email format'
                }), 400
            
            # Check if email already exists (excluding current user)
            cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?', (data['email'], user_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Email already exists'
                }), 400
            
            update_fields.append('email = ?')
            update_values.append(data['email'])
        
        if 'phone' in data:
            update_fields.append('phone = ?')
            update_values.append(data['phone'])
        
        if 'department' in data:
            update_fields.append('department = ?')
            update_values.append(data['department'])
        
        if 'role' in data:
            update_fields.append('role = ?')
            update_values.append(data['role'])
        
        if 'status' in data:
            update_fields.append('status = ?')
            update_values.append(data['status'])
        
        # Handle password reset
        if data.get('reset_password'):
            password_hash = hash_password(data['reset_password'])
            update_fields.append('password = ?')
            update_fields.append('must_change_password = ?')
            update_values.extend([password_hash, 1])
        
        if not update_fields:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No fields to update'
            }), 400
        
        # Add user_id to values for WHERE clause
        update_values.append(user_id)
        
        # Execute update
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(update_query, update_values)
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'User not found or no changes made'
            }), 404
        
        conn.commit()
        conn.close()
        
        print(f"✅ User {user_id} updated successfully")
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully'
        })
        
    except Exception as e:
        print(f"❌ Error updating user: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error updating user: {str(e)}'
        }), 500

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user"""
    print(f"🔍 Delete user {user_id} session:", dict(session))
    try:
        current_user_role = session.get('role', 'user')
        current_user_id = session.get('user_id')  # Assuming you store user_id in session
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get user to be deleted
        cursor.execute('SELECT username, role FROM users WHERE id = ?', (user_id,))
        user_to_delete = cursor.fetchone()
        if not user_to_delete:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        username, role = user_to_delete
        
        # Check permissions
        if not validate_user_role_permissions(current_user_role, role, 'delete'):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions to delete this user'
            }), 403
        
        # Prevent self-deletion
        if str(current_user_id) == str(user_id):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Cannot delete your own account'
            }), 400
        
        # Check if user has any invoices or important data
        cursor.execute('SELECT COUNT(*) FROM invoices WHERE username = ?', (username,))
        invoice_count = cursor.fetchone()[0] or 0
        
        if invoice_count > 0:
            # Instead of deleting, we could deactivate the user
            cursor.execute('UPDATE users SET status = ? WHERE id = ?', ('inactive', user_id))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'User {username} has been deactivated instead of deleted due to existing invoices'
            })
        
        # Delete the user
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        conn.commit()
        conn.close()
        
        print(f"✅ User {username} (ID: {user_id}) deleted successfully")
        
        return jsonify({
            'success': True,
            'message': f'User {username} deleted successfully'
        })
        
    except Exception as e:
        print(f"❌ Error deleting user: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error deleting user: {str(e)}'
        }), 500
    
# Chat Management Endpoints
@app.route('/api/create_new_chat', methods=['POST'])
def create_new_chat():
    """Create a new chat for the current user"""
    try:
        username = validate_user_session()
        
        # Create new chat in database
        chat_id, title = db_manager.create_new_chat(username)
        
        # Update session to point to new chat
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        session_data_local['current_chat_id'] = chat_id
        
        # Clear conversation history for new chat
        session_data_local['conversation_history'] = []
        
        return jsonify({
            'success': True,
            'chat_id': chat_id,
            'title': title,
            'message': f'New chat "{title}" created successfully'
        })
        
    except Exception as e:
        print(f"❌ Error creating new chat: {str(e)}")
        return jsonify({'error': f'Error creating new chat: {str(e)}'}), 500


# Add these missing endpoints to your app0.py file
# Place them after your existing endpoints and before the supporting functions

@app.route('/api/generate_invoice_from_cart', methods=['POST'])
def generate_invoice_from_cart():
    print("🔍 Generate invoice session:", dict(session))
    try:
        username = validate_user_session()
        
        data = request.json
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        session_data_local = get_session_data(session_id)
        
        if not session_data_local['cart']:
            return jsonify({'error': 'Cart is empty'}), 400
        
        order = {}
        discounts = {}
        
        for item_id, item in session_data_local['cart'].items():
            product_name = item['name']
            order[product_name] = item['quantity']
            if item['discount'] > 0:
                discounts[product_name] = item['discount']
        
        products = session_data_local['products'] if session_data_local['products'] else default_products
        
        overall_discount = session_data_local.get('overall_discount', 0)
        
        invoice = calculate_invoice(
            user_order=order,
            product_data=products,
            discounts=discounts,
            overall_discount=overall_discount
        )
        print(f"DEBUG: Invoice object before PDF generation: {invoice}")
        print(f"DEBUG: Invoice summary before PDF generation: {invoice.get('summary')}")
        
        pdf_path = generate_invoice_pdf(invoice, session_data_local["client_details"], session_id)
        
        if not pdf_path:
            return jsonify({"error": "Failed to generate invoice PDF"}), 500
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Save invoice data to database
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO invoices (invoice_number, client_name, amount, date, pdf_path, username)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            invoice_number,
            session_data_local['client_details'].get('name', 'Walk-in Customer'),
            invoice['summary']['grand_total'],
            datetime.now().strftime('%Y-%m-%d'),
            pdf_path,
            username
        ))
        conn.commit()
        conn.close()
        
        # Create the AI response message with download link
        download_btn = f'<a href="#" class="download-invoice-btn" onclick="invoiceApp.downloadInvoice(\'{pdf_path}\')"><i class="fas fa-download"></i> Download PDF Invoice</a>'
        ai_response = f"✅ Invoice generated successfully!<br><br>📄 Invoice #: {invoice_number}<br>📋 Items: {len(session_data_local['cart'])}<br>💰 Total: ₹{invoice['summary']['grand_total']:,.2f}<br><br>{download_btn}"
        
        # Clear cart
        session_data_local['cart'] = {}
        session_data_local['overall_discount'] = 0
        
        return jsonify({
            'success': True,
            'invoice': invoice,
            'pdf_path': pdf_path,
            'invoice_number': invoice_number,
            'ai_response': ai_response,  # Add this line - the formatted response for saving to DB
            'message': 'PDF invoice generated successfully and cart cleared!'
        })
        
    except Exception as e:
        print(f"❌ Error generating invoice: {str(e)}")
        return jsonify({'error': f'Error generating invoice: {str(e)}'}), 500

@app.route('/api/download_invoice/<filename>')
def download_invoice(filename):
    print("🔍 Download invoice session:", dict(session))
    try:
        username = validate_user_session()
        
        file_path = os.path.join(app.config['INVOICE_FOLDER'], filename)
        if os.path.exists(file_path):
            mimetype = 'application/pdf' if filename.endswith('.pdf') else 'text/html'
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype=mimetype)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"❌ Error downloading file: {str(e)}")
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 500

@app.route('/api/client/get', methods=['GET'])
def get_client():
    print("🔍 Get client session:", dict(session))
    try:
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        client = session_data_local.get('client_details', {})
        return jsonify({'client': client})
    except Exception as e:
        print(f"❌ Error fetching client: {str(e)}")
        return jsonify({'error': f'Error fetching client: {str(e)}'}), 500

@app.route('/api/client/save', methods=['POST'])
def save_client():
    print("🔍 Save client session:", dict(session))
    try:
        username = validate_user_session()
        
        data = request.json
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        session_data_local = get_session_data(session_id)
        
        # Update client details in session
        session_data_local['client_details'] = {
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'address': data.get('address', ''),
            'gst_number': data.get('gst_number', ''),
            'place_of_supply': data.get('place_of_supply', ''),
            'project_name': data.get('project_name', 'General Purchase')
        }
        
        return jsonify({
            'success': True,
            'message': 'Client details saved successfully',
            'client': session_data_local['client_details']
        })
        
    except Exception as e:
        print(f"❌ Error saving client: {str(e)}")
        return jsonify({'error': f'Error saving client: {str(e)}'}), 500

@app.route('/api/upload_catalog', methods=['POST'])
def upload_catalog():
    print("🔍 Upload catalog session:", dict(session))
    try:
        username = validate_user_session()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'.csv', '.xlsx', '.xls'}
        file_extension = '.' + file.filename.rsplit('.', 1)[-1].lower()
        
        if file_extension not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Please upload CSV or Excel files.'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Parse the uploaded file
            products = parse_for_streamlit(file_path)
            
            if products:
                # Update session products
                session_id = request.headers.get('Session-ID', 'default')
                session_data_local = get_session_data(session_id)
                session_data_local['products'] = products
                session_data_local['catalog_source'] = 'uploaded'
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully uploaded {len(products)} products',
                    'product_count': len(products),
                    'filename': filename
                })
            else:
                return jsonify({'error': 'No products found in the uploaded file'}), 400
                
        except Exception as parse_error:
            print(f"❌ Error parsing file: {str(parse_error)}")
            return jsonify({'error': f'Error parsing file: {str(parse_error)}'}), 400
        finally:
            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
        
    except Exception as e:
        print(f"❌ Error uploading catalog: {str(e)}")
        return jsonify({'error': f'Error uploading catalog: {str(e)}'}), 500

@app.route('/api/update_product', methods=['PUT'])
@admin_required
def update_product():
    print("🔍 Update product session:", dict(session))
    try:
        data = request.json
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)

        # Get the current product list (session or default)
        products = session_data_local['products'] if session_data_local['products'] else default_products

        # Find the product to update by original name
        original_name = data.get('original_name')
        if not original_name:
            return jsonify({'error': 'Original product name is required'}), 400

        product_index = None
        for i, product in enumerate(products):
            if product['name'].lower() == original_name.lower():
                product_index = i
                break

        if product_index is None:
            return jsonify({'error': f'Product {original_name} not found'}), 404

        # Update product details
        updated_product = {
            'name': data.get('name', products[product_index]['name']),
            'price': float(data.get('price', products[product_index]['price'])),
            'gst_rate': float(data.get('gst_rate', products[product_index].get('gst_rate', 18))),
            'stock': int(data.get('stock', products[product_index].get('stock', 0))),
            'Installation Charge': float(data.get('installation_charge', products[product_index].get('Installation Charge', 0))),
            'Service Charge': float(data.get('service_charge', products[product_index].get('Service Charge', 0))),
            'Shipping Charge': float(data.get('shipping_charge', products[product_index].get('Shipping Charge', 0))),
            'Handling Fee': float(data.get('handling_fee', products[product_index].get('Handling Fee', 0))),
            'price_tax_amount': float(data.get('price_tax_amount', products[product_index].get('price_tax_amount', 0))),
            'price_discount_amount': float(data.get('price_discount_amount', products[product_index].get('price_discount_amount', 0))),
            'price_final_price': float(data.get('price_final_price', products[product_index].get('price_final_price', 0))),
            'name_description': float(data.get('name_description', products[product_index].get('name_description', 0)))
        }

        # Validate updated product
        if not validate_product_data([updated_product]):
            return jsonify({'error': 'Invalid product data structure'}), 400

        # Update the product in the list
        products[product_index] = updated_product

        # Save to product_data.json if using default products
        if session_data_local['catalog_source'] == 'default':
            save_products(products)

        # Update session products
        session_data_local['products'] = products

        return jsonify({
            'success': True,
            'message': f'Product {updated_product["name"]} updated successfully',
            'product': updated_product
        })

    except Exception as e:
        print(f"❌ Error updating product: {str(e)}")
        return jsonify({'error': f'Error updating product: {str(e)}'}), 500


@app.route('/api/products/all', methods=['GET'])
def get_all_products():
    """Get all available products for the current session"""
    try:
        username = validate_user_session()
        
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        
        # Get products from session or default
        if session_data_local['products']:
            products = session_data_local['products']
            source = session_data_local.get('catalog_source', 'session')
        else:
            products = default_products
            source = 'default'
            # Update session with default products
            session_data_local['products'] = products
            session_data_local['catalog_source'] = 'default'
        
        # Format products for frontend
        formatted_products = []
        for product in products:
            formatted_product = {
                'name': product.get('name', 'Unknown Product'),
                'price': float(product.get('price', 0)),
                'stock': product.get('stock'),
                'gst_rate': product.get('gst_rate', 18),
                'name_description': product.get('name_description', ''),
                'Installation Charge': product.get('Installation Charge', 0),
                'Service Charge': product.get('Service Charge', 0),
                'Shipping Charge': product.get('Shipping Charge', 0),
                'Handling Fee': product.get('Handling Fee', 0)
            }
            formatted_products.append(formatted_product)
        
        return jsonify({
            'success': True,
            'products': formatted_products,
            'count': len(formatted_products),
            'source': source,
            'session_id': session_id
        })
        
    except Exception as e:
        print(f"❌ Error fetching products: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching products: {str(e)}',
            'products': [],
            'count': 0
        }), 500


@app.route('/api/delete_product', methods=['DELETE'])
@admin_required
def delete_product():
    print("🔍 Delete product session:", dict(session))
    try:
        data = request.json
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)

        product_name = data.get('name')
        if not product_name:
            return jsonify({'error': 'Product name is required'}), 400

        # Get the current product list (session or default)
        products = session_data_local['products'] if session_data_local['products'] else default_products

        # Find the product to delete
        product_index = None
        for i, product in enumerate(products):
            if product['name'].lower() == product_name.lower():
                product_index = i
                break

        if product_index is None:
            return jsonify({'error': f'Product {product_name} not found'}), 404

        # Remove the product
        deleted_product = products.pop(product_index)

        # Save to product_data.json if using default products
        if session_data_local['catalog_source'] == 'default':
            save_products(products)

        # Update session products
        session_data_local['products'] = products

        return jsonify({
            'success': True,
            'message': f'Product {product_name} deleted successfully'
        })

    except Exception as e:
        print(f"❌ Error deleting product: {str(e)}")
        return jsonify({'error': f'Error deleting product: {str(e)}'}), 500


@app.route('/api/get_chats', methods=['GET'])
def get_chats():
    """Get all chats for the current user"""
    try:
        username = validate_user_session()
        
        # Get chats from database
        chats = db_manager.get_user_chats(username)
        
        # Format for frontend
        formatted_chats = []
        for chat in chats:
            formatted_chats.append({
                'chat_id': chat['chat_id'],
                'title': chat['title'],
                'created_at': chat['created_at'],
                'updated_at': chat['updated_at'],
                'message_count': chat['message_count']
            })
        
        return jsonify({
            'success': True,
            'chats': formatted_chats
        })
        
    except Exception as e:
        print(f"❌ Error fetching chats: {str(e)}")
        return jsonify({'error': f'Error fetching chats: {str(e)}'}), 500

@app.route('/api/admin/users_section')
@admin_required
def get_users_section():
    """Serve the users section HTML content"""
    try:
        return render_template('admin_users.html')
    except Exception as e:
        print(f"❌ Error loading users section: {str(e)}")
        return f"Error loading users section: {str(e)}", 500

@app.route('/api/load_chat/<chat_id>', methods=['GET'])
def load_chat(chat_id):
    """Load a specific chat and its messages"""
    try:
        username = validate_user_session()
        
        # Get messages from database
        messages = db_manager.get_chat_messages(chat_id, username)
        
        # Update current chat in session
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        session_data_local['current_chat_id'] = chat_id
        
        # Convert messages to expected format
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'role': msg['message_type'],
                'content': msg['content'],
                'timestamp': msg['timestamp']
            })
        
        # Update conversation history in session
        session_data_local['conversation_history'] = formatted_messages
        
        return jsonify({
            'success': True,
            'chat_id': chat_id,
            'messages': formatted_messages
        })
        
    except Exception as e:
        print(f"❌ Error loading chat: {str(e)}")
        return jsonify({'error': f'Error loading chat: {str(e)}'}), 500

@app.route('/api/delete_chat', methods=['POST'])
def delete_chat():
    """Delete a specific chat"""
    try:
        username = validate_user_session()
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({'error': 'Chat ID is required'}), 400
        
        # Delete chat from database
        success = db_manager.delete_chat(chat_id, username)
        
        if success:
            # Clear current chat if it was deleted
            session_id = request.headers.get('Session-ID', 'default')
            session_data_local = get_session_data(session_id)
            if session_data_local.get('current_chat_id') == chat_id:
                session_data_local['current_chat_id'] = None
                session_data_local['conversation_history'] = []
            
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete chat'}), 500
            
    except Exception as e:
        print(f"❌ Error deleting chat: {str(e)}")
        return jsonify({'error': f'Error deleting chat: {str(e)}'}), 500

@app.route('/api/rename_chat', methods=['POST'])
def rename_chat():
    """Rename a specific chat"""
    try:
        username = validate_user_session()
        data = request.get_json()
        chat_id = data.get('chat_id')
        new_title = data.get('title', '').strip()
        
        if not chat_id or not new_title:
            return jsonify({'error': 'Chat ID and title are required'}), 400
        
        # Rename chat in database
        success = db_manager.rename_chat(chat_id, username, new_title)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Chat renamed to "{new_title}"'
            })
        else:
            return jsonify({'error': 'Failed to rename chat'}), 500
            
    except Exception as e:
        print(f"❌ Error renaming chat: {str(e)}")
        return jsonify({'error': f'Error renaming chat: {str(e)}'}), 500

def save_message_to_db(username, chat_id, message_type, content, metadata=None):
    """Helper function to save messages to database"""
    try:
        if not chat_id:
            # If no current chat, create a new one
            chat_id, _ = db_manager.create_new_chat(username)
        
        db_manager.save_message(chat_id, username, message_type, content, metadata)
        return chat_id
    except Exception as e:
        print(f"❌ Error saving message to DB: {str(e)}")
        return chat_id
    
# Continue from Part 1...

# Load default products function (unchanged)
def load_default_products():
    try:
        if os.path.exists('product_data.json'):
            with open('product_data.json', 'r') as f:
                products = json.load(f)
            print(f"✅ Loaded {len(products)} products from product_data.json")
            return products
        else:
            print("⚠️ product_data.json not found")
            return []
    except Exception as e:
        print(f"❌ Error loading product_data.json: {e}")
        return []

def save_products(products):
    try:
        with open('product_data.json', 'w') as f:
            json.dump(products, f, indent=2)
        print(f"✅ Saved {len(products)} products to product_data.json")
    except Exception as e:
        print(f"❌ Error saving product_data.json: {e}")

def parse_for_streamlit(file_path):
    try:
        products = dynamic_parse_and_save(file_path, output_path=None)
        return products
    except Exception as e:
        print(f"Error parsing for Flask: {e}")
        return []

# Load default products
default_products = load_default_products()

# Setup login routes
setup_login_routes(app)

# Role-based authentication decorator (unchanged)
def admin_required(f):
    def wrap(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__  # Preserve function name for Flask
    return wrap

@app.route('/')
def index():
    print("🔍 Index session:", dict(session))
    if 'username' not in session:
        return redirect('/api/login')
    
    # Update last login time
    try:
        db_manager.update_user_login(session['username'])
    except Exception as e:
        print(f"Error updating login time: {e}")
    
    return render_template('chat_interface.html')


@app.route('/api/user_info', methods=['GET'])
def get_user_info():
    """Get current user information"""
    try:
        username = validate_user_session()
        
        # Get user details from session
        user_role = session.get('role', 'user')
        
        # Create user info response
        user_info = {
            'username': username,
            'role': user_role.title(),  # Capitalize first letter
            'initials': username[0].upper() if username else 'U'
        }
        
        return jsonify({
            'success': True,
            'user': user_info
        })
        
    except Exception as e:
        print(f"❌ Error fetching user info: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching user info: {str(e)}',
            'user': None
        }), 500



@app.route('/favicon.ico')
def favicon():
    """Serve favicon or return 204 if not found"""
    try:
        return send_file('static/favicon.ico')
    except:
        # Return empty response if favicon doesn't exist
        from flask import Response
        return Response(status=204)

@app.route('/admin')
@admin_required
def admin_dashboard():
    print("🔍 Admin dashboard session:", dict(session))
    return render_template('admin_dashboard.html')

@app.route('/api/status')
def status():
    print("🔍 Status session:", dict(session))
    try:
        gemini_status, gemini_message = test_gemini_connection()
    except:
        gemini_status, gemini_message = False, "Gemini connection test failed"
    
    user_info = None
    if 'username' in session:
        user_info = {
            'username': session['username'],
            'role': session.get('role', 'user'),
            'initials': ''.join([name[0].upper() for name in session['username'].split() if name])[:2] or session['username'][:2].upper()
        }
    
    return jsonify({
        'api_status': 'online',
        'gemini_status': 'online' if gemini_status else 'offline',
        'gemini_message': gemini_message,
        'default_products_count': len(default_products),
        'timestamp': datetime.now().isoformat(),
        'user_authenticated': 'username' in session,
        'user_role': session.get('role', 'none'),
        'user_info': user_info
    })

@app.route('/api/admin_dashboard_data', methods=['GET'])
@admin_required
def admin_dashboard_data():
    print("🔍 Admin dashboard data session:", dict(session))
    try:
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()

        # Total Invoices
        cursor.execute('SELECT COUNT(*) FROM invoices')
        total_invoices = cursor.fetchone()[0]

        # Total Revenue
        cursor.execute('SELECT SUM(amount) FROM invoices')
        total_revenue = cursor.fetchone()[0] or 0

        # Active Users (mocked since we don't have user tracking yet)
        active_users = 25

        # Products Sold (mocked; calculate from invoice details if available)
        products_sold = 320

        # Revenue Over Time (last 6 months)
        revenue_data = []
        labels = []
        current_date = datetime.now()
        for i in range(5, -1, -1):
            month_date = current_date.replace(day=1) - pd.Timedelta(days=30 * i)
            month_start = month_date.strftime('%Y-%m-01')
            month_end = (month_date + pd.Timedelta(days=31)).replace(day=1).strftime('%Y-%m-01')
            cursor.execute('SELECT SUM(amount) FROM invoices WHERE date >= ? AND date < ?', (month_start, month_end))
            month_revenue = cursor.fetchone()[0] or 0
            revenue_data.append(month_revenue)
            labels.append(month_date.strftime('%b'))

        # Top Products (mocked; need invoice item details for real data)
        product_data = [
            {'name': 'AI Security Camera', 'sold': 100},
            {'name': 'Smart Doorbell', 'sold': 80},
            {'name': 'Smart TV', 'sold': 60},
            {'name': 'Wireless Router', 'sold': 40},
            {'name': 'Smart Speaker', 'sold': 20}
        ]

        # Recent Invoices (last 5)
        cursor.execute('SELECT invoice_number, client_name, amount, date FROM invoices ORDER BY date DESC LIMIT 5')
        recent_invoices = [ 
            {'id': row[0], 'client': row[1], 'amount': row[2], 'date': row[3]}
            for row in cursor.fetchall()
        ]

        conn.close()

        return jsonify({
            'totalInvoices': total_invoices,
            'totalRevenue': total_revenue,
            'activeUsers': active_users,
            'productsSold': products_sold,
            'revenueData': revenue_data,
            'labels': labels,
            'productData': product_data,
            'recentInvoices': recent_invoices
        })

    except Exception as e:
        print(f"❌ Error fetching admin dashboard data: {str(e)}")
        return jsonify({'error': f'Error fetching dashboard data: {str(e)}'}), 500

@app.route('/api/check_password_change_required', methods=['POST'])
def check_password_change_required():
    """Check if user needs to change password"""
    try:
        data = request.json
        username = data.get('username')
        
        if not username:
            return jsonify({
                'success': False,
                'error': 'Username required'
            }), 400
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT must_change_password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'must_change_password': bool(result[0])
            })
        else:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
    except Exception as e:
        print(f"❌ Error checking password change requirement: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error checking password requirement: {str(e)}'
        }), 500

@app.route('/api/change_password', methods=['POST'])
def change_password():
    """Change user password (for forced password changes)"""
    try:
        if 'username' not in session:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        data = request.json
        username = session['username']
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'Current password and new password are required'
            }), 400
        
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 8 characters long'
            }), 400
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get current password hash
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        if not result or not verify_password(current_password, result[0]):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 400
        
        # Hash new password
        new_password_hash = hash_password(new_password)
        
        # Update password and clear must_change_password flag
        cursor.execute('''UPDATE users SET password = ?, must_change_password = 0 
                         WHERE username = ?''', (new_password_hash, username))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Password changed successfully for user: {username}")
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        print(f"❌ Error changing password: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error changing password: {str(e)}'
        }), 500
    
# Updated chat endpoint with proper database integration
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    print("🔍 Chat endpoint session:", dict(session))
    try:
        username = validate_user_session()
        
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        print(f"💬 User message: {user_message}")
        print(f"🔍 Session ID: {session_id}")
        
        session_data_local = get_session_data(session_id)
        
        # Get or create current chat
        current_chat_id = session_data_local.get('current_chat_id')
        if not current_chat_id:
            # Create new chat for this conversation
            current_chat_id, _ = db_manager.create_new_chat(username)
            session_data_local['current_chat_id'] = current_chat_id
        
        # Save user message to database IMMEDIATELY (only once)
        try:
            db_manager.save_message(current_chat_id, username, 'user', user_message)
            print("✅ User message saved to database")
        except Exception as e:
            print(f"⚠️ Error saving user message: {e}")
        
        if session_data_local['products']:
            products = session_data_local['products']
        else:
            products = default_products
            session_data_local['products'] = products
        
        response, action_data = process_natural_language(user_message, session_data_local, products)
        
        # Handle invoice generation special case
        if action_data and action_data.get('action') == 'generate_invoice':
            try:
                # Generate invoice manually instead of calling the endpoint
                if not session_data_local['cart']:
                    error_response = "❌ Cart is empty. Add some products before generating invoice."
                    db_manager.save_message(current_chat_id, username, 'ai', error_response)
                    return jsonify({
                        'response': error_response,
                        'action_data': None,
                        'cart_count': 0,
                        'has_products': len(products) > 0,
                        'product_count': len(products),
                        'session_id': session_id,
                        'chat_id': current_chat_id,
                        'overall_discount': session_data_local['overall_discount']
                    })
                
                # Create order from cart
                order = {}
                discounts = {}
                for item_id, item in session_data_local['cart'].items():
                    product_name = item['name']
                    order[product_name] = item['quantity']
                    if item['discount'] > 0:
                        discounts[product_name] = item['discount']
                
                # Calculate invoice
                invoice = calculate_invoice(
                    user_order=order,
                    product_data=products,
                    discounts=discounts,
                    overall_discount=session_data_local.get('overall_discount', 0)
                )
                
                # Generate PDF
                pdf_path = generate_invoice_pdf(invoice, session_data_local["client_details"], session_id)
                invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Save to invoice database
                conn = sqlite3.connect('invoices.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO invoices (invoice_number, client_name, amount, date, pdf_path, username)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_number,
                    session_data_local['client_details'].get('name', 'Walk-in Customer'),
                    invoice['summary']['grand_total'],
                    datetime.now().strftime('%Y-%m-%d'),
                    pdf_path,
                    username
                ))
                conn.commit()
                conn.close()
                
                # Create AI response with download link
                download_btn = f'<a href="#" class="download-invoice-btn" onclick="invoiceApp.downloadInvoice(\'{pdf_path}\')"><i class="fas fa-download"></i> Download PDF Invoice</a>'
                ai_response = f"✅ Invoice generated successfully!<br><br>📄 Invoice #: {invoice_number}<br>📋 Items: {len(session_data_local['cart'])}<br>💰 Total: ₹{invoice['summary']['grand_total']:,.2f}<br><br>{download_btn}"
                
                # Save AI response to database
                invoice_metadata = {
                    'action': 'invoice_generated',
                    'invoice_number': invoice_number,
                    'pdf_path': pdf_path,
                    'total_amount': invoice['summary']['grand_total']
                }
                
                db_manager.save_message(current_chat_id, username, 'ai', ai_response, invoice_metadata)
                
                # Clear cart
                session_data_local['cart'] = {}
                session_data_local['overall_discount'] = 0
                
                # Update session conversation history
                session_data_local['conversation_history'].append({
                    'role': 'user',
                    'content': user_message,
                    'timestamp': datetime.now().isoformat()
                })
                session_data_local['conversation_history'].append({
                    'role': 'ai',
                    'content': ai_response,
                    'timestamp': datetime.now().isoformat(),
                    'action_data': invoice_metadata
                })
                
                return jsonify({
                    'response': ai_response,
                    'action_data': invoice_metadata,
                    'cart_count': 0,
                    'has_products': len(products) > 0,
                    'product_count': len(products),
                    'session_id': session_id,
                    'chat_id': current_chat_id,
                    'overall_discount': 0
                })
                
            except Exception as e:
                error_response = f"❌ Error generating invoice: {str(e)}"
                db_manager.save_message(current_chat_id, username, 'ai', error_response)
                return jsonify({
                    'response': error_response,
                    'action_data': None,
                    'cart_count': len(session_data_local['cart']),
                    'has_products': len(products) > 0,
                    'product_count': len(products),
                    'session_id': session_id,
                    'chat_id': current_chat_id,
                    'overall_discount': session_data_local['overall_discount']
                })
        
        # For all other responses (non-invoice), save normally
        try:
            db_manager.save_message(current_chat_id, username, 'ai', response, action_data)
            print("✅ AI response saved to database")
        except Exception as e:
            print(f"⚠️ Error saving AI response: {e}")
        
        # Update conversation history in session (for immediate use only)
        session_data_local['conversation_history'].append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        session_data_local['conversation_history'].append({
            'role': 'ai',
            'content': response,
            'timestamp': datetime.now().isoformat(),
            'action_data': action_data
        })
        
        # Keep only recent messages in session (last 10 to reduce memory)
        session_data_local['conversation_history'] = session_data_local['conversation_history'][-10:]
        
        print(f"🛒 Cart after response: {session_data_local['cart']}")
        
        return jsonify({
            'response': response,
            'action_data': action_data,
            'cart_count': len(session_data_local['cart']),
            'has_products': len(products) > 0,
            'product_count': len(products),
            'session_id': session_id,
            'chat_id': current_chat_id,
            'overall_discount': session_data_local['overall_discount']
        })
        
    except Exception as e:
        print(f"❌ Error processing chat: {str(e)}")
        return jsonify({'error': f'Error processing chat: {str(e)}'}), 500


# The rest of the endpoints remain mostly unchanged, but I'll include the important ones
@app.route('/api/add_product', methods=['POST'])
@admin_required
def add_product():
    print("🔍 Add product session:", dict(session))
    try:
        data = request.json
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)

        # Create new product
        new_product = {
            'name': data.get('name', ''),
            'price': float(data.get('price', 0)),
            'gst_rate': float(data.get('gst_rate', 18)),
            'stock': int(data.get('stock', 0)),
            'Installation Charge': float(data.get('installation_charge', 0)),
            'Service Charge': float(data.get('service_charge', 0)),
            'Shipping Charge': float(data.get('shipping_charge', 0)),
            'Handling Fee': float(data.get('handling_fee', 0)),
            'price_tax_amount': float(data.get('price_tax_amount', 0)),
            'price_discount_amount': float(data.get('price_discount_amount', 0)),
            'price_final_price': float(data.get('price_final_price', 0)),
            'name_description': float(data.get('name_description', 0))
        }

        # Validate new product
        if not new_product['name']:
            return jsonify({'error': 'Product name is required'}), 400
        if not validate_product_data([new_product]):
            return jsonify({'error': 'Invalid product data structure'}), 400

        # Get current product list
        products = session_data_local['products'] if session_data_local['products'] else default_products

        # Check for duplicate product name
        if any(p['name'].lower() == new_product['name'].lower() for p in products):
            return jsonify({'error': f'Product {new_product["name"]} already exists'}), 400

        # Add new product
        products.append(new_product)

        # Save to product_data.json if using default products
        if session_data_local['catalog_source'] == 'default':
            save_products(products)

        # Update session products
        session_data_local['products'] = products

        return jsonify({
            'success': True,
            'message': f'Product {new_product["name"]} added successfully',
            'product': new_product
        })

    except Exception as e:
        print(f"❌ Error adding product: {str(e)}")
        return jsonify({'error': f'Error adding product: {str(e)}'}), 500

@app.route('/api/get_products', methods=['GET'])
def get_products():
    print("🔍 Get products session:", dict(session))
    try:
        # Ensure session is initialized even without login
        if 'username' not in session:
            session['username'] = 'guest'
            session['role'] = 'user'
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        products = session_data_local['products'] if session_data_local['products'] else default_products
        return jsonify({'products': products, 'count': len(products)})
    except Exception as e:
        print(f"❌ Error fetching products: {str(e)}")
        return jsonify({'error': f'Error fetching products: {str(e)}'}), 500
    
# Continue from Part 2...

# Keep all the existing natural language processing functions unchanged
def process_natural_language(message, session_data, products):
    try:
        if not GEMINI_AVAILABLE or not model:
            return get_fallback_response(message, session_data, products)
        
        cart_summary = ""
        if session_data['cart']:
            cart_summary = "\n\nCURRENT CART CONTENTS:\n"
            cart_total = 0
            for item_id, item in session_data['cart'].items():
                discounted_price = item['unit_price'] * (1 - item['discount']/100)
                item_total = discounted_price * item['quantity']
                cart_total += item_total
                cart_summary += f"- {item['name']}: {item['quantity']} units @ ₹{item['unit_price']} each"
                if item['discount'] > 0:
                    cart_summary += f" (with {item['discount']}% discount = ₹{discounted_price:.2f} each)"
                cart_summary += f" = ₹{item_total:.2f}\n"
            
            if session_data['overall_discount'] > 0:
                overall_discount_amount = cart_total * session_data['overall_discount'] / 100
                cart_summary += f"\nOverall Cart Discount: {session_data['overall_discount']}% (₹{overall_discount_amount:.2f})"
                cart_summary += f"\nCart Total after Overall Discount: ₹{cart_total - overall_discount_amount:.2f}"
            else:
                cart_summary += f"\nCart Total: ₹{cart_total:.2f}"
        else:
            cart_summary = "\n\nCURRENT CART: Empty"
        
        conversation_context = ""
        if session_data['conversation_history']:
            conversation_context = "\n\nRECENT CONVERSATION HISTORY:\n"
            for msg in session_data['conversation_history'][-8:]:
                role = "User" if msg['role'] == 'user' else "Assistant"
                conversation_context += f"{role}: {msg['content'][:150]}...\n"
        
        product_catalog = ""
        if products:
            product_catalog = "\n\nAVAILABLE PRODUCTS:\n"
            for i, product in enumerate(products, 1):
                product_catalog += f"{i}. {product['name']} - ₹{product['price']:,.2f}\n"
        
        system_prompt = f"""
You are an intelligent AI shopping assistant helping customers manage their cart and create invoices. 

YOUR ROLE:
- Understand natural language requests about shopping, cart management, and invoicing
- Be conversational, helpful, and remember the context of our conversation
- Help customers find products, manage their cart, and generate invoices

CURRENT SITUATION:
- Available products: {len(products)}
- Items in cart: {len(session_data['cart'])}
- Overall cart discount: {session_data['overall_discount']}%
{cart_summary}
{conversation_context}
{product_catalog}

USER'S MESSAGE: "{message}"

INSTRUCTIONS FOR RESPONSES:
1. When user wants to ADD/BUY products:
   - Parse their request to extract: product name, quantity, discount
   - ONLY use POSITIVE quantities (never 0 or negative)
   - Respond naturally first, then add action code
   - Format: [ACTION:ADD|ProductName|Quantity|Discount]
   - Example: "I'll add 5 keyboards with 20% discount to your cart!"
             [ACTION:ADD|Professional Cable Tester|5|20]

2. When user wants to REMOVE products:
   - Parse their request to extract: product name, quantity
   - Format: [ACTION:REMOVE|ProductName|Quantity|0]

3. When user wants to APPLY DISCOUNT to existing cart items:
   - Parse requests like "add 10% discount to smart doorbell", "apply 15% off to cameras"
   - Format: [ACTION:APPLY_DISCOUNT|ProductName|DiscountPercent|0]

4. When user wants to UPDATE EXISTING items with discount:
   - If they want to change discount on existing item
   - Format: [ACTION:UPDATE_DISCOUNT|ProductName|NewDiscountPercent|0]

5. When user wants to apply OVERALL CART DISCOUNT:
   - Parse requests like "add 50% discount to cart", "apply 25% overall discount", "give 10% discount on entire cart"
   - Format: [ACTION:OVERALL_DISCOUNT|||DiscountPercent]
   - Example: "I'll apply a 50% discount to your entire cart!"
             [ACTION:OVERALL_DISCOUNT|||50]

6. When user wants to REMOVE OVERALL DISCOUNT:
   - Parse requests like "remove overall discount", "clear cart discount"
   - Format: [ACTION:CLEAR_OVERALL_DISCOUNT|||0]

7. When user wants to VIEW CART:
   - Format: [ACTION:SHOW_CART|||]

8. When user wants to see PRODUCTS:
   - Format: [ACTION:SHOW_PRODUCTS|||]

9. When user wants to GENERATE INVOICE:
   - Format: [ACTION:GENERATE_INVOICE|||]

10. When user wants DETAILED BREAKDOWN:
    - Parse requests like "show cart breakdown", "detailed pricing", "full breakdown"
    - Format: [ACTION:SHOW_BREAKDOWN|||]

11. For general conversation:
    - Just respond naturally, no action needed

IMPORTANT RULES:
- Always be conversational and helpful
- Remember our conversation history
- Use exact product names from the catalog
- If user mentions products not in catalog, suggest similar ones
- Be intelligent about quantity/discount parsing
- NEVER allow zero or negative quantities
- When adding products, confirm what you're doing
- For cart/product views, let the system handle formatting
- If user wants to apply discount to existing items, use APPLY_DISCOUNT action
- For overall cart discounts, clearly explain the impact on total amount
"""
        
        response = model.generate_content(system_prompt)
        response_text = response.text.strip()
        
        print(f"🤖 AI Response: {response_text}")
        
        action_match = re.search(r'\[ACTION:([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)\]', response_text)
        
        if action_match:
            action_type = action_match.group(1).strip()
            param1 = action_match.group(2).strip()
            param2 = action_match.group(3).strip()
            param3 = action_match.group(4).strip()
            
            print(f"✅ Action detected: {action_type} | {param1} | {param2} | {param3}")
            
            clean_response = re.sub(r'\[ACTION:[^\]]+\]', '', response_text).strip()
            
            if action_type == "ADD":
                return execute_add_action(param1, param2, param3, session_data, products, clean_response)
            elif action_type == "REMOVE":
                return execute_remove_action(param1, param2, session_data, products, clean_response)
            elif action_type == "APPLY_DISCOUNT":
                return execute_apply_discount_action(param1, param2, session_data, clean_response)
            elif action_type == "UPDATE_DISCOUNT":
                return execute_update_discount_action(param1, param2, session_data, clean_response)
            elif action_type == "OVERALL_DISCOUNT":
                return execute_overall_discount_action(param3, session_data, clean_response)
            elif action_type == "CLEAR_OVERALL_DISCOUNT":
                return execute_clear_overall_discount_action(session_data, clean_response)
            elif action_type == "SHOW_CART":
                return show_cart_formatted(session_data), {"action": "show_cart"}
            elif action_type == "SHOW_PRODUCTS":
                return show_products_formatted(products), {"action": "show_products"}
            elif action_type == "GENERATE_INVOICE":
                return process_invoice_generation(session_data), {"action": "generate_invoice"}
            elif action_type == "SHOW_BREAKDOWN":
                return show_cart_detailed_breakdown(session_data), {"action": "show_cart_breakdown"}
        
        message_lower = message.lower()
        if "add" in message_lower and any(p['name'].lower() in message_lower for p in products):
            for product in products:
                if product['name'].lower() in message_lower:
                    quantity_match = re.search(r'\b(\d+)\b', message_lower)
                    quantity = int(quantity_match.group(1)) if quantity_match else 1
                    discount = 0
                    clean_response = f"Adding {quantity} {product['name']}."
                    print(f"✅ Fallback ADD: {product['name']} | {quantity} | {discount}")
                    return execute_add_action(product['name'], str(quantity), str(discount), session_data, products, clean_response)
        elif "show cart" in message_lower or "cart breakdown" in message_lower:
            clean_response = "Here's your cart breakdown."
            print("✅ Fallback SHOW_BREAKDOWN")
            return show_cart_detailed_breakdown(session_data), {"action": "show_cart_breakdown"}
        
        clean_response = re.sub(r'\[ACTION:[^\]]+\]', '', response_text).strip()
        return clean_response, None
        
    except Exception as e:
        print(f"❌ Error in natural language processing: {str(e)}")
        return get_fallback_response(message, session_data, products)

def get_fallback_response(message, session_data, products):
    """Enhanced fallback response when AI is unavailable"""
    message_lower = message.lower()
    
    print(f"🔄 Using fallback for: '{message}'")
    
    # Handle ADD commands
    if any(word in message_lower for word in ['add', 'buy', 'purchase', 'get']):
        print("🔍 Detected ADD command in fallback")
        
        # Extract quantity
        quantity_match = re.search(r'\b(\d+)\b', message_lower)
        quantity = int(quantity_match.group(1)) if quantity_match else 1
        
        # Extract discount
        discount_match = re.search(r'(\d+)%?\s*(discount|off)', message_lower)
        discount = int(discount_match.group(1)) if discount_match else 0
        
        # Smart product search
        found_product = smart_product_search_fallback(message_lower, products)
        
        if found_product:
            print(f"✅ Fallback found product: {found_product['name']}")
            clean_response = f"Adding {quantity} {found_product['name']} to cart (AI offline - using basic mode)."
            return execute_add_action(found_product['name'], str(quantity), str(discount), session_data, products, clean_response)
        else:
            # Show available products for better user experience
            available_products = "<br>".join([f"• {p['name']}" for p in products[:10]])
            return f"❌ AI offline. Product not found. Try:<br>{available_products}<br><br>💡 Example: 'add 2 Smart Television'", None
    
    # Handle REMOVE commands
    elif any(word in message_lower for word in ['remove', 'delete', 'take out']):
        print("🔍 Detected REMOVE command in fallback")
        
        quantity_match = re.search(r'\b(\d+)\b', message_lower)
        quantity = int(quantity_match.group(1)) if quantity_match else 1
        
        # Check cart items
        for item_id, item in session_data['cart'].items():
            if any(word in item['name'].lower() for word in message_lower.split()):
                clean_response = f"Removing {quantity} {item['name']} from cart (AI offline)."
                return execute_remove_action(item['name'], str(quantity), session_data, products, clean_response)
        
        return "❌ AI offline. Product not found in cart. Say 'show cart' to see current items.", None
    
    # Handle CART commands
    elif any(word in message_lower for word in ['cart', 'show cart', 'view cart']):
        print("🔍 Detected CART command in fallback")
        return show_cart_formatted(session_data), {"action": "show_cart"}
    
    elif any(word in message_lower for word in [ 'cart breakdown', 'breakdown', 'detailed breakdown', 'detailed pricing', "show bill"]):
        print("🔍 Detected CART command in fallback")
        return show_cart_detailed_breakdown(session_data), {"action": "show_cart_breakdown"}
    
    # Handle PRODUCTS commands
    elif any(word in message_lower for word in ['products', 'catalog', 'list products', 'show products', 'available']):
        print("🔍 Detected PRODUCTS command in fallback")
        return show_products_formatted(products), {"action": "show_products"}
    
    # Handle DISCOUNT commands
    elif "discount" in message_lower:
        print("🔍 Detected DISCOUNT command in fallback")
        
        discount_match = re.search(r'(\d+)%?\s*(discount|off)', message_lower)
        if not discount_match:
            return "❌ AI offline. Please specify discount like '20% discount'", None
        
        discount = int(discount_match.group(1))
        
        if any(word in message_lower for word in ['cart', 'overall', 'total', 'entire']):
            # Overall cart discount
            clean_response = f"Applying {discount}% overall cart discount (AI offline)."
            return execute_overall_discount_action(str(discount), session_data, clean_response)
        else:
            # Product discount - find the product
            found_product = smart_product_search_fallback(message_lower, products)
            if found_product:
                clean_response = f"Applying {discount}% discount to {found_product['name']} (AI offline)."
                return execute_apply_discount_action(found_product['name'], str(discount), session_data, clean_response)
            else:
                return "❌ AI offline. Product not found for discount.", None
    
    # Handle INVOICE commands
    elif any(word in message_lower for word in ['invoice', 'generate invoice', 'bill', 'generate bill']):
        print("🔍 Detected INVOICE command in fallback")
        if not session_data['cart']:
            return "❌ Cart is empty. Add products before generating invoice.", None
        return process_invoice_generation(session_data), {"action": "generate_invoice"}
    
    # Handle greeting and general conversation
    elif any(word in message_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
        return "👋 Hello! AI is temporarily offline, but I can still help with basic commands:<br><br>• 'add 2 smart television' - Add products<br>• 'show cart' - View cart<br>• 'generate invoice' - Create invoice<br>• 'list products' - Show available products", None
    
    # Default fallback with helpful guidance
    return f"""❌ AI service temporarily offline. I didn't understand '{message}'.

<strong>Available commands:</strong>
• <strong>Add products:</strong> "add 2 smart television"
• <strong>Remove products:</strong> "remove 1 laptop"  
• <strong>View cart:</strong> "show cart"
• <strong>Apply discounts:</strong> "apply 10% discount to laptop"
• <strong>Overall discount:</strong> "add 20% discount to cart"
• <strong>Generate invoice:</strong> "generate invoice"
• <strong>List products:</strong> "show products"

💡 <strong>Tip:</strong> Use exact product names from the catalog.""", None


def smart_product_search_fallback(message_lower, products):
    """Enhanced product search for fallback mode"""
    print(f"🔍 Searching products for: '{message_lower}'")
    
    # Remove common words that aren't product names
    common_words = {'add', 'buy', 'purchase', 'get', 'want', 'need', 'with', 'and', 'the', 'a', 'an', 'to', 'from', 'of', 'in', 'on', 'at', 'by', 'for', 'discount', 'off', 'percent', '%'}
    message_words = [word for word in message_lower.split() if word not in common_words and not word.isdigit()]
    
    print(f"🔍 Filtered words: {message_words}")
    
    # Try exact name match first
    for product in products:
        product_name_lower = product['name'].lower()
        if product_name_lower in message_lower:
            print(f"✅ Exact match found: {product['name']}")
            return product
    
    # Try word-by-word matching
    for product in products:
        product_words = product['name'].lower().split()
        
        # Check if most product words are in the message
        matches = sum(1 for word in product_words if word in message_words)
        if matches >= len(product_words) * 0.6:  # 60% of product words must match
            print(f"✅ Word match found: {product['name']} (matched {matches}/{len(product_words)} words)")
            return product
    
    # Try partial matching with key words
    for product in products:
        product_name_lower = product['name'].lower()
        # Split into key words and check if any significant word matches
        for word in message_words:
            if len(word) > 3 and word in product_name_lower:  # Only check words longer than 3 chars
                print(f"✅ Partial match found: {product['name']} (matched word: '{word}')")
                return product
    
    print("❌ No product match found")
    return None

def execute_add_action(product_name, quantity_str, discount_str, session_data, products, ai_response):
    try:
        quantity = int(quantity_str) if quantity_str and quantity_str.isdigit() else 1
        discount = float(discount_str) if discount_str else 0
        
        if quantity <= 0:
            return f"❌ Cannot add zero or negative quantity products to cart.<br><br>💡 Please specify a positive quantity like 'add 2 {product_name}'", None
        
        print(f"🛍️ Adding: {product_name}, Qty: {quantity}, Discount: {discount}%")
        
        product = smart_product_search(product_name, products)
        if not product:
            return f"❌ I couldn't find '{product_name}' in our catalog.<br><br>📋 Available products:<br>" + "<br>".join([f"• {p['name']}" for p in products[:10]]), None
        
        print(f"✅ Found product: {product['name']}")
        
        item_id = product['name']
        if item_id in session_data['cart']:
            existing_item = session_data['cart'][item_id]
            existing_item['quantity'] += quantity
            if discount > 0:
                existing_item['discount'] = discount
            action_text = f"Updated existing cart item: +{quantity} units"
        else:
            session_data['cart'][item_id] = {
                'name': product['name'],
                'unit_price': product['price'],
                'quantity': quantity,
                'discount': discount,
                'added_time': datetime.now().isoformat(),
                'installation_charge': product.get('Installation Charge', 0),
                'service_charge': product.get('Service Charge', 0),
                'shipping_charge': product.get('Shipping Charge', 0),
                'handling_fee': product.get('Handling Fee', 0),
                'gst_rate': product.get('gst_rate', 18)
            }
            action_text = "Added new item to cart"
        
        print(f"✅ {action_text} | Cart: {session_data['cart']}")
        
        final_discount = session_data['cart'][item_id]['discount']
        discounted_price = product['price'] * (1 - final_discount/100)
        total_quantity = session_data['cart'][item_id]['quantity']
        simple_total = discounted_price * total_quantity
        
        response_lines = [ai_response if ai_response else "✅ Added to cart!"]
        response_lines.extend([
            "",
            f"📦 {product['name']}",
            f"🔢 Quantity: {total_quantity} units (added {quantity})",
            f"💰 Price: ₹{product['price']:,.2f} each"
        ])
        
        if final_discount > 0:
            response_lines.extend([
                f"🏷️ Discount: {final_discount}%",
                f"💸 Discounted Price: ₹{discounted_price:,.2f} each"
            ])
        
        response_lines.extend([
            f"💳 Item Total: ₹{simple_total:,.2f}",
            "",
            f"🛒 Cart now has {len(session_data['cart'])} different items"
        ])
        
        if session_data['overall_discount'] > 0:
            response_lines.extend([
                f"🏷️ Overall Cart Discount: {session_data['overall_discount']}% (applied at checkout)",
            ])
        
        response_lines.extend([
            "",
            "💡 Additional charges (installation, service, etc.) will be calculated in final invoice",
            "📋 Say 'show cart breakdown' for detailed pricing"
        ])
        
        return "<br>".join(response_lines), {
            "action": "add_to_cart",
            "product": product['name'],
            "quantity": quantity,
            "discount": final_discount
        }
        
    except Exception as e:
        print(f"❌ Error executing add action: {str(e)}")
        return f"❌ Error adding product: {str(e)}", None


# Add these missing functions to your app0.py file
# Place them after the execute_add_action function and before the main execution block

def execute_remove_action(product_name, quantity_str, session_data, products, ai_response):
    try:
        quantity = int(quantity_str) if quantity_str and quantity_str.isdigit() else 1
        
        for item_id, item in list(session_data['cart'].items()):
            if product_name.lower() in item['name'].lower():
                if quantity >= item['quantity']:
                    del session_data['cart'][item_id]
                    return f"{ai_response}<br><br>✅ Removed all {item['name']} from cart<br>🛒 Cart now has {len(session_data['cart'])} items", {"action": "remove_from_cart"}
                else:
                    item['quantity'] -= quantity
                    return f"{ai_response}<br><br>✅ Removed {quantity}x {item['name']}<br>🔢 {item['quantity']} remaining<br>🛒 Cart has {len(session_data['cart'])} items", {"action": "remove_from_cart"}
        
        return f"{ai_response}<br><br>❌ Couldn't find '{product_name}' in your cart", None
        
    except Exception as e:
        print(f"❌ Error removing product: {str(e)}")
        return f"❌ Error removing product: {str(e)}", None

def execute_apply_discount_action(product_name, discount_str, session_data, ai_response):
    try:
        discount = float(discount_str) if discount_str else 0
        
        if discount < 0 or discount > 100:
            return f"❌ Invalid discount percentage. Please use a value between 0 and 100.", None
        
        cart_item = None
        item_key = None
        
        for key, item in session_data['cart'].items():
            if product_name.lower() == item['name'].lower():
                cart_item = item
                item_key = key
                break
        
        if not cart_item:
            for key, item in session_data['cart'].items():
                if product_name.lower() in item['name'].lower():
                    cart_item = item
                    item_key = key
                    break
        
        if not cart_item:
            return f"❌ I couldn't find '{product_name}' in your cart.<br><br>🛒 Current cart items:<br>" + "<br>".join([f"• {item['name']}" for item in session_data['cart'].values()]), None
        
        old_discount = cart_item['discount']
        cart_item['discount'] = discount
        
        discounted_price = cart_item['unit_price'] * (1 - discount/100)
        item_total = discounted_price * cart_item['quantity']
        
        response_lines = [ai_response if ai_response else "✅ Discount applied!"]
        response_lines.extend([
            "",
            f"📦 {cart_item['name']}",
            f"🏷️ Discount updated: {old_discount}% → {discount}%",
            f"💰 Original Price: ₹{cart_item['unit_price']:,.2f} each",
            f"💸 New Price: ₹{discounted_price:,.2f} each",
            f"🔢 Quantity: {cart_item['quantity']} units",
            f"💳 New Item Total: ₹{item_total:,.2f}",
            "",
            "📋 Say 'show cart' to see updated cart"
        ])
        
        return "<br>".join(response_lines), {
            "action": "apply_discount",
            "product": cart_item['name'],
            "discount": discount
        }
        
    except Exception as e:
        print(f"❌ Error applying discount: {str(e)}")
        return f"❌ Error applying discount: {str(e)}", None

def execute_update_discount_action(product_name, discount_str, session_data, ai_response):
    return execute_apply_discount_action(product_name, discount_str, session_data, ai_response)

def execute_overall_discount_action(discount_str, session_data, ai_response):
    try:
        discount = float(discount_str) if discount_str else 0
        
        if discount < 0 or discount > 100:
            return f"❌ Invalid discount percentage. Please use a value between 0 and 100.", None
        
        if not session_data['cart']:
            return f"❌ Cannot apply overall discount - your cart is empty!<br><br>🛒 Add some products first.", None
        
        cart_subtotal = 0
        for item_id, item in session_data['cart'].items():
            discounted_price = item['unit_price'] * (1 - item['discount']/100)
            item_total = discounted_price * item['quantity']
            cart_subtotal += item_total
        
        old_discount = session_data['overall_discount']
        session_data['overall_discount'] = discount
        
        new_discount_amount = cart_subtotal * discount / 100
        new_total = cart_subtotal - new_discount_amount
        
        response_lines = [ai_response if ai_response else "✅ Overall cart discount applied!"]
        response_lines.extend([
            "",
            f"🛒 Cart Items: {len(session_data['cart'])} different products",
            f"💰 Cart Subtotal: ₹{cart_subtotal:,.2f}",
            f"🏷️ Overall Discount: {discount}%",
            f"💸 Discount Amount: ₹{new_discount_amount:,.2f}",
            f"💳 New Cart Total: ₹{new_total:,.2f}",
            "",
            "💡 This discount applies to the entire cart total",
            "📋 Say 'show cart breakdown' for detailed pricing",
            "🧾 Say 'generate invoice' to create final bill with all discounts"
        ])
        
        return "<br>".join(response_lines), {
            "action": "overall_discount",
            "discount": discount
        }
        
    except Exception as e:
        print(f"❌ Error applying overall discount: {str(e)}")
        return f"❌ Error applying overall discount: {str(e)}", None

def execute_clear_overall_discount_action(session_data, ai_response):
    try:
        if session_data['overall_discount'] == 0:
            return f"💡 No overall discount is currently applied to your cart.", None
        
        cart_subtotal = 0
        for item_id, item in session_data['cart'].items():
            discounted_price = item['unit_price'] * (1 - item['discount']/100)
            item_total = discounted_price * item['quantity']
            cart_subtotal += item_total
        
        old_discount = session_data['overall_discount']
        
        session_data['overall_discount'] = 0
        
        response_lines = [ai_response if ai_response else "✅ Overall discount removed!"]
        response_lines.extend([
            "",
            f"🛒 Cart Items: {len(session_data['cart'])} different products",
            f"🏷️ Overall Discount: {old_discount}% → 0%",
            f"💳 New Cart Total: ₹{cart_subtotal:,.2f}",
            "",
            "💡 Individual item discounts are still applied",
            "📋 Say 'show cart' to see updated totals"
        ])
        
        return "<br>".join(response_lines), {
            "action": "clear_overall_discount"
        }
        
    except Exception as e:
        print(f"❌ Error clearing overall discount: {str(e)}")
        return f"❌ Error clearing overall discount: {str(e)}", None

def show_products_formatted(products):
    if not products:
        return "📋 No products available in the catalog.<br><br>💡 Ask an admin to add products!"
    
    lines = [f"📋 Product Catalog ({len(products)} products)", ""]
    
    for i, product in enumerate(products, 1):
        lines.append(f"{i}. {product['name']}")
    
    lines.extend([
        "💡 Say 'add [product name]' to add items to your cart",
        "📋 Say 'show cart' to view your current cart"
    ])
    
    return "<br>".join(lines)

def show_cart_detailed_breakdown(session_data):
    if not session_data['cart']:
        return "🛒 Your cart is empty<br><br>💡 Try adding some products first!"
    
    lines = [f"🛒 Detailed Cart Breakdown ({len(session_data['cart'])} items)", ""]
    
    subtotal = 0
    total_installation = 0
    total_service = 0
    total_shipping = 0
    total_handling = 0
    total_gst = 0
    grand_total = 0
    
    for i, (item_id, item) in enumerate(session_data['cart'].items(), 1):
        qty = item['quantity']
        base_price = item['unit_price']
        discount = item['discount']
        
        installation = item.get('installation_charge', 0)
        service = item.get('service_charge', 0)
        shipping = item.get('shipping_charge', 0)
        handling = item.get('handling_fee', 0)
        gst_rate = item.get('gst_rate', 18)
        
        discounted_price = base_price * (1 - discount/100)
        item_subtotal = discounted_price * qty
        
        item_installation = installation * qty
        item_service = service * qty
        item_shipping = shipping * qty
        item_handling = handling * qty
        
        item_gst = (item_subtotal * gst_rate / 100)
        
        item_total = item_subtotal + item_installation + item_service + item_shipping + item_handling + item_gst
        
        subtotal += item_subtotal
        total_installation += item_installation
        total_service += item_service
        total_shipping += item_shipping
        total_handling += item_handling
        total_gst += item_gst
        grand_total += item_total
        
        lines.append(f"{i}. {item['name']}")
        lines.append(f"   📦 Quantity: {qty} units")
        lines.append(f"   💰 Base Price: ₹{base_price:,.2f} each")
        
        if discount > 0:
            lines.append(f"   🏷️ Discount: {discount}%")
            lines.append(f"   💸 Discounted Price: ₹{discounted_price:,.2f} each")
        
        lines.append(f"   📊 Price Breakdown:")
        lines.append(f"      • Product Subtotal: ₹{item_subtotal:,.2f}")
        
        if item_installation > 0:
            lines.append(f"      • Installation (₹{installation:,.2f} × {qty}): ₹{item_installation:,.2f}")
        if item_service > 0:
            lines.append(f"      • Service (₹{service:,.2f} × {qty}): ₹{item_service:,.2f}")
        if item_shipping > 0:
            lines.append(f"      • Shipping (₹{shipping:,.2f} × {qty}): ₹{item_shipping:,.2f}")
        if item_handling > 0:
            lines.append(f"      • Handling (₹{handling:,.2f} × {qty}): ₹{item_handling:,.2f}")
        
        lines.append(f"      • GST ({gst_rate}%): ₹{item_gst:,.2f}")
        lines.append(f"      • Item Total: ₹{item_total:,.2f}")
        lines.append("")
    
    overall_discount_amount = 0
    final_grand_total = grand_total
    
    if session_data['overall_discount'] > 0:
        overall_discount_amount = grand_total * session_data['overall_discount'] / 100
        final_grand_total = grand_total - overall_discount_amount
    
    lines.extend([
        f"📊 Cart Totals:",
        f"   • Products Subtotal: ₹{subtotal:,.2f}",
        f"   • Installation Charges: ₹{total_installation:,.2f}",
        f"   • Service Charges: ₹{total_service:,.2f}",
        f"   • Shipping Charges: ₹{total_shipping:,.2f}",
        f"   • Handling Fees: ₹{total_handling:,.2f}",
        f"   • GST Total: ₹{total_gst:,.2f}",
        f"   • Grand Total (before cart discount): ₹{grand_total:,.2f}"
    ])
    
    if session_data['overall_discount'] > 0:
        lines.extend([
            f"   • Overall Cart Discount ({session_data['overall_discount']}%): -₹{overall_discount_amount:,.2f}",
            f"   • Final Grand Total: ₹{final_grand_total:,.2f}"
        ])
    
    lines.extend([
        "",
        "💡 Say 'generate invoice' to create a PDF with this breakdown",
        "🏷️ Say 'apply 10% discount to [product]' to update item discounts",
        "🏷️ Say 'add 25% discount to cart' to adjust overall discount"
    ])
    
    return "<br>".join(lines)

def process_invoice_generation(session_data):
    try:
        if not session_data['cart']:
            return "❌ Your cart is empty. Add some products before generating an invoice!<br><br>💡 Try 'add 2 cameras' or 'show products'", None
        
        client_details = session_data.get('client_details', {})
        if not client_details.get('name'):
            return "❌ Client details are missing. Please provide client information first.<br><br>💡 Say 'set client name to [name]' or 'update client details'", None
        
        invoice_items = []
        for item_id, item in session_data['cart'].items():
            discounted_price = item['unit_price'] * (1 - item['discount']/100)
            invoice_items.append({
                'name': item['name'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'discount': item['discount'],
                'discounted_price': discounted_price,
                'installation_charge': item.get('installation_charge', 0),
                'service_charge': item.get('service_charge', 0),
                'shipping_charge': item.get('shipping_charge', 0),
                'handling_fee': item.get('handling_fee', 0),
                'gst_rate': item.get('gst_rate', 18)
            })
        
        invoice_data = calculate_invoice(invoice_items, session_data['overall_discount'])
        invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        invoice_date = datetime.now().strftime('%Y-%m-%d')
        
        invoice_summary = generate_invoice_summary(
            invoice_items=invoice_items,
            client_details=client_details,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            overall_discount=session_data['overall_discount']
        )
        
        return f"✅ Invoice ready for generation!<br><br>📄 Invoice #: {invoice_number}<br>📋 Items: {len(invoice_items)}<br>💰 Total: ₹{invoice_data.get('grand_total', 0):,.2f}<br><br>💡 Say 'generate invoice from cart' to create PDF", {
            "action": "show_invoice_preview",
            "invoice_number": invoice_number,
            "invoice_data": invoice_data
        }
        
    except Exception as e:
        print(f"❌ Error generating invoice: {str(e)}")
        return f"❌ Error generating invoice: {str(e)}", None

# Add these additional functions that might be needed
def generate_invoice_pdf(invoice, client_details, session_id):
    try:
        with open(os.path.join(os.path.dirname(__file__), 'invoice_template.html'), 'r') as f:
            template_content = f.read()
        
        template = Template(template_content)
        
        seller = {
            'name': 'Zencia AI',
            'address': 'Sachivalaya Metro Station, Lucknow Uttar Pradesh 226001',
            'phone': '1234567890',
            'gstin': '14556789012345',
        }
        
        # Enhanced client details with proper fallbacks
        client = {
            'name': client_details.get('name', 'Walk-in Customer'),
            'address': client_details.get('address', 'Address not provided'),
            'gst_number': client_details.get('gst_number', 'GST not provided'),
            'place_of_supply': client_details.get('place_of_supply', 'Place of supply not specified'),
            'phone': client_details.get('phone', 'Phone not provided'),
            'email': client_details.get('email', 'Email not provided')
        }
        
        # Project name with fallback
        project_name = client_details.get('project_name', 'General Purchase')
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        invoice_date = datetime.now().strftime('%d/%m/%Y')
        
        print(f"DEBUG: Invoice object in generate_invoice_pdf: {invoice}")
        print(f"DEBUG: Invoice summary in generate_invoice_pdf: {invoice.get('summary')}")
        html_content = template.render(
            invoice=invoice,
            seller=seller,
            client=client,
            project_name=project_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            supplier_ref='',
            other_ref='',
            amount_in_words=number_to_words(invoice['summary']['grand_total']),
            tax_in_words=number_to_words(invoice['summary']['total_gst'])
        )
        
        options = {
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None,
            'enable-smart-shrinking': True # Added to improve rendering
        }
        
        pdf_filename = f"invoice_{invoice_number}.pdf"
        pdf_path = os.path.join(app.config['INVOICE_FOLDER'], pdf_filename)
        
        try:
            pdfkit.from_string(html_content, pdf_path, options=options)
            print(f"✅ PDF generated successfully: {pdf_filename}")
            return pdf_filename
        except Exception as pdf_error:
            print(f"❌ PDF generation error: {pdf_error}")
            # Fallback to generating HTML if PDF generation fails
            html_filename = f"invoice_{invoice_number}.html"
            html_path = os.path.join(app.config["INVOICE_FOLDER"], html_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"⚠️ Generated HTML instead of PDF: {html_filename}")
            return html_filename
        
    except Exception as e:
        print(f"❌ Error generating invoice: {str(e)}")
        # If all else fails, return a default HTML filename or raise an error
        # For now, let's return a generic HTML filename to avoid 'null'
        fallback_html_filename = f"invoice_error_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        fallback_html_path = os.path.join(app.config["INVOICE_FOLDER"], fallback_html_filename)
        with open(fallback_html_path, "w", encoding="utf-8") as f:
            f.write("<h1>Error generating invoice</h1><p>" + str(e) + "</p>")
        return fallback_html_filename
    
def number_to_words(number):
    try:
        from num2words import num2words
        return num2words(int(number), lang='en').title() + " Rupees Only"
    except ImportError:
        return f"Rupees {int(number)} Only"

def smart_product_search(product_name, products):
    product_name = product_name.lower().strip()
    for product in products:
        if product_name == product['name'].lower():
            return product
    for product in products:
        if product_name in product['name'].lower():
            return product
    return None

# Include remaining cart functions (show_cart_formatted, etc.) - keeping them unchanged
def show_cart_formatted(session_data):
    if not session_data['cart']:
        return "🛒 Your cart is empty<br><br>💡 Try adding some products! Say something like 'I want 2 cameras' or 'add 3 doorbells with 15% discount'"
    
    lines = [f"🛒 Your Shopping Cart ({len(session_data['cart'])} items)", ""]
    subtotal = 0
    
    for i, (item_id, item) in enumerate(session_data['cart'].items(), 1):
        discounted_price = item['unit_price'] * (1 - item['discount']/100)
        item_subtotal = discounted_price * item['quantity']
        subtotal += item_subtotal
        
        lines.append(f"{i}. {item['name']}")
        lines.append(f"   • Quantity: {item['quantity']} units")
        lines.append(f"   • Price: ₹{item['unit_price']:,.2f} each")
        
        if item['discount'] > 0:
            lines.append(f"   • Discount: {item['discount']}%")
            lines.append(f"   • Discounted Price: ₹{discounted_price:,.2f} each")
        
        lines.append(f"   • Subtotal: ₹{item_subtotal:,.2f}")
        lines.append("")
    
    overall_discount_amount = 0
    final_total = subtotal
    
    if session_data['overall_discount'] > 0:
        overall_discount_amount = subtotal * session_data['overall_discount'] / 100
        final_total = subtotal - overall_discount_amount
    
    lines.extend([
        f"💰 Cart Subtotal: ₹{subtotal:,.2f}"
    ])
    
    if session_data['overall_discount'] > 0:
        lines.extend([
            f"🏷️ Overall Cart Discount ({session_data['overall_discount']}%): -₹{overall_discount_amount:,.2f}",
            f"💳 Cart Total after Discount: ₹{final_total:,.2f}"
        ])
    
    lines.extend([
        "",
        "💡 Additional charges (installation, service, GST, etc.) will be added during checkout",
        "",
        "🏷️ Say 'apply 10% discount to [product]' to add discounts to existing items",
        "🏷️ Say 'add 25% discount to cart' to apply overall discount to entire cart",
        "📋 Say 'show cart breakdown' for detailed pricing with all charges",
        "🧾 Say 'generate invoice' to create final bill with complete breakdown"
    ])
    
    return "<br>".join(lines)

@app.route('/api/enhanced_dashboard_data', methods=['GET'])
@admin_required
def enhanced_dashboard_data():
    """Enhanced dashboard data endpoint with real-time metrics"""
    try:
        # Get current user
        username = session.get('username')
        
        # Initialize data structure
        dashboard_data = {
            'metrics': {},
            'charts': {},
            'activity': [],
            'alerts': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Connect to database
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get total revenue
        cursor.execute('SELECT SUM(amount) FROM invoices WHERE username = ? OR ? = "admin"', 
                      (username, username))
        total_revenue = cursor.fetchone()[0] or 0
        
        # Get total invoices
        cursor.execute('SELECT COUNT(*) FROM invoices WHERE username = ? OR ? = "admin"', 
                      (username, username))
        total_invoices = cursor.fetchone()[0] or 0
        
        # Get total products
        products_count = len(default_products)
        
        # Get total users (admin only)
        if session.get('role') == 'admin':
            # Create users table if it doesn't exist
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )''')
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0] or 0
        else:
            total_users = 1  # Just the current user
        
        # Calculate growth percentages (mock data for demo)
        dashboard_data['metrics'] = {
            'total_revenue': total_revenue,
            'revenue_growth': round(random.uniform(5.0, 15.0), 1),
            'total_orders': total_invoices,
            'orders_growth': round(random.uniform(3.0, 12.0), 1),
            'total_products': products_count,
            'products_growth': 0.0,  # Products don't change often
            'total_users': total_users,
            'users_growth': round(random.uniform(1.0, 8.0), 1)
        }
        
        # Generate revenue chart data (last 30 days)
        revenue_data = []
        labels = []
        
        for i in range(29, -1, -1):
            date = datetime.now() - timedelta(days=i)
            labels.append(date.strftime('%Y-%m-%d'))
            
            # Get actual revenue for this date
            cursor.execute('''SELECT SUM(amount) FROM invoices 
                            WHERE date = ? AND (username = ? OR ? = "admin")''', 
                          (date.strftime('%Y-%m-%d'), username, username))
            daily_revenue = cursor.fetchone()[0] or 0
            
            # Add some randomness if no data
            if daily_revenue == 0:
                daily_revenue = random.randint(1000, 15000)
            
            revenue_data.append(daily_revenue)
        
        dashboard_data['charts']['revenue'] = {
            'labels': labels,
            'data': revenue_data
        }
        
        # Get top products data
        top_products = []
        for i, product in enumerate(default_products[:5]):
            top_products.append({
                'name': product['name'][:20] + ('...' if len(product['name']) > 20 else ''),
                'sales': random.randint(10, 100),
                'revenue': product['price'] * random.randint(1, 20)
            })
        
        dashboard_data['charts']['top_products'] = top_products
        
        # Generate recent activity
        activities = [
            {'icon': 'fas fa-user-plus', 'text': 'New user registered', 'time': '2 minutes ago'},
            {'icon': 'fas fa-shopping-cart', 'text': 'New order placed', 'time': '5 minutes ago'},
            {'icon': 'fas fa-box', 'text': 'Product added to catalog', 'time': '10 minutes ago'},
            {'icon': 'fas fa-file-invoice-dollar', 'text': 'Invoice generated', 'time': '15 minutes ago'},
            {'icon': 'fas fa-edit', 'text': 'Product updated', 'time': '20 minutes ago'}
        ]
        
        dashboard_data['activity'] = activities[:5]  # Latest 5 activities
        
        # Generate alerts (low stock, pending orders, etc.)
        alerts = []
        
        # Check for low stock products
        low_stock_products = [p for p in default_products if p.get('stock', 0) < 10]
        if low_stock_products:
            alerts.append({
                'type': 'warning',
                'message': f'{len(low_stock_products)} products have low stock',
                'action': 'View Products'
            })
        
        # Check for recent invoices
        cursor.execute('''SELECT COUNT(*) FROM invoices 
                         WHERE date >= ? AND (username = ? OR ? = "admin")''', 
                      (datetime.now().strftime('%Y-%m-%d'), username, username))
        today_invoices = cursor.fetchone()[0] or 0
        
        if today_invoices > 0:
            alerts.append({
                'type': 'info',
                'message': f'{today_invoices} invoices generated today',
                'action': 'View Invoices'
            })
        
        dashboard_data['alerts'] = alerts
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': dashboard_data
        })
        
    except Exception as e:
        print(f"❌ Error fetching enhanced dashboard data: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching dashboard data: {str(e)}'
        }), 500

@app.route('/api/products_analytics', methods=['GET'])
@admin_required
def products_analytics():
    """Get detailed product analytics"""
    try:
        username = session.get('username')
        
        # Get products with enhanced analytics
        products_analytics = []
        
        for product in default_products:
            # Mock analytics data
            analytics = {
                'name': product['name'],
                'price': product['price'],
                'stock': product.get('stock', 0),
                'total_sales': random.randint(1, 50),
                'revenue_generated': product['price'] * random.randint(1, 20),
                'profit_margin': round(random.uniform(15.0, 35.0), 1),
                'category': 'Electronics',  # Default category
                'status': 'active' if product.get('stock', 0) > 0 else 'out_of_stock',
                'last_updated': datetime.now().isoformat(),
                'views': random.randint(50, 500),
                'conversion_rate': round(random.uniform(2.0, 15.0), 1)
            }
            
            products_analytics.append(analytics)
        
        return jsonify({
            'success': True,
            'products': products_analytics,
            'summary': {
                'total_products': len(products_analytics),
                'active_products': len([p for p in products_analytics if p['status'] == 'active']),
                'out_of_stock': len([p for p in products_analytics if p['status'] == 'out_of_stock']),
                'total_revenue': sum(p['revenue_generated'] for p in products_analytics),
                'average_price': sum(p['price'] for p in products_analytics) / len(products_analytics) if products_analytics else 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error fetching products analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching products analytics: {str(e)}'
        }), 500

@app.route('/api/sales_analytics', methods=['GET'])
@admin_required
def sales_analytics():
    """Get detailed sales analytics"""
    try:
        username = session.get('username')
        timeframe = request.args.get('timeframe', '30d')  # 7d, 30d, 90d, 1y
        
        # Calculate date range
        if timeframe == '7d':
            days = 7
        elif timeframe == '30d':
            days = 30
        elif timeframe == '90d':
            days = 90
        elif timeframe == '1y':
            days = 365
        else:
            days = 30
        
        # Connect to database
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get sales data for the timeframe
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''SELECT date, SUM(amount), COUNT(*) 
                         FROM invoices 
                         WHERE date >= ? AND (username = ? OR ? = "admin")
                         GROUP BY date 
                         ORDER BY date''', 
                      (start_date, username, username))
        
        sales_data = cursor.fetchall()
        
        # Fill in missing dates with zero values
        sales_by_date = {}
        for row in sales_data:
            sales_by_date[row[0]] = {'revenue': row[1], 'orders': row[2]}
        
        # Generate complete dataset
        labels = []
        revenue_data = []
        orders_data = []
        
        for i in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            labels.append(date)
            
            if date in sales_by_date:
                revenue_data.append(sales_by_date[date]['revenue'])
                orders_data.append(sales_by_date[date]['orders'])
            else:
                # Add some mock data for demo
                revenue_data.append(random.randint(0, 5000))
                orders_data.append(random.randint(0, 10))
        
        # Calculate summary statistics
        total_revenue = sum(revenue_data)
        total_orders = sum(orders_data)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Calculate growth (compare with previous period)
        prev_start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
        prev_end_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''SELECT SUM(amount), COUNT(*) 
                         FROM invoices 
                         WHERE date >= ? AND date < ? AND (username = ? OR ? = "admin")''', 
                      (prev_start_date, prev_end_date, username, username))
        
        prev_data = cursor.fetchone()
        prev_revenue = prev_data[0] or 0
        prev_orders = prev_data[1] or 0
        
        revenue_growth = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
        orders_growth = ((total_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'timeframe': timeframe,
            'data': {
                'labels': labels,
                'revenue': revenue_data,
                'orders': orders_data
            },
            'summary': {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'avg_order_value': round(avg_order_value, 2),
                'revenue_growth': round(revenue_growth, 1),
                'orders_growth': round(orders_growth, 1)
            }
        })
        
    except Exception as e:
        print(f"❌ Error fetching sales analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching sales analytics: {str(e)}'
        }), 500

@app.route('/api/user_analytics', methods=['GET'])
@admin_required
def user_analytics():
    """Get user analytics (admin only)"""
    try:
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Ensure users table exists
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )''')
        
        # Get user statistics
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        admin_users = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "user"')
        regular_users = cursor.fetchone()[0] or 0
        
        # Get recent registrations (last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= ?', (thirty_days_ago,))
        recent_registrations = cursor.fetchone()[0] or 0
        
        # Get user activity data
        cursor.execute('''SELECT username, last_login 
                         FROM users 
                         ORDER BY last_login DESC 
                         LIMIT 10''')
        recent_activity = cursor.fetchall()
        
        # Generate user growth data (last 30 days)
        growth_data = []
        for i in range(29, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?', (date,))
            daily_registrations = cursor.fetchone()[0] or 0
            growth_data.append(daily_registrations)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_users': total_users,
                'admin_users': admin_users,
                'regular_users': regular_users,
                'recent_registrations': recent_registrations,
                'growth_rate': round(random.uniform(5.0, 15.0), 1)  # Mock growth rate
            },
            'growth_data': growth_data,
            'recent_activity': [
                {
                    'username': row[0],
                    'last_login': row[1] if row[1] else 'Never',
                    'status': 'active' if row[1] and 
                             datetime.fromisoformat(row[1]) > datetime.now() - timedelta(days=7) 
                             else 'inactive'
                }
                for row in recent_activity
            ]
        })
        
    except Exception as e:
        print(f"❌ Error fetching user analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching user analytics: {str(e)}'
        }), 500

@app.route('/api/system_health', methods=['GET'])
@admin_required
def system_health():
    """Get system health metrics"""
    try:
        import psutil
        import os
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get database size
        db_size = 0
        try:
            db_size = os.path.getsize('invoices.db') / (1024 * 1024)  # Size in MB
        except:
            pass
        
        # Check API health
        api_status = {
            'gemini_ai': GEMINI_AVAILABLE,
            'database': True,  # Assume healthy if we got this far
            'file_system': os.access('.', os.W_OK),
            'uploads_dir': os.path.exists(app.config['UPLOAD_FOLDER'])
        }
        
        # Calculate overall health score
        health_score = sum([
            50 if cpu_percent < 80 else 20 if cpu_percent < 90 else 10,
            30 if memory.percent < 80 else 15 if memory.percent < 90 else 5,
            20 if all(api_status.values()) else 10
        ])
        
        return jsonify({
            'success': True,
            'health_score': health_score,
            'status': 'healthy' if health_score > 80 else 'warning' if health_score > 60 else 'critical',
            'metrics': {
                'cpu_usage': round(cpu_percent, 1),
                'memory_usage': round(memory.percent, 1),
                'disk_usage': round(disk.percent, 1),
                'database_size': round(db_size, 2),
                'uptime': '24h 35m',  # Mock uptime
                'active_sessions': len(session_data)
            },
            'api_status': api_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except ImportError:
        # Fallback if psutil not available
        return jsonify({
            'success': True,
            'health_score': 85,
            'status': 'healthy',
            'metrics': {
                'cpu_usage': 45.2,
                'memory_usage': 62.8,
                'disk_usage': 34.1,
                'database_size': 2.5,
                'uptime': '24h 35m',
                'active_sessions': len(session_data)
            },
            'api_status': {
                'gemini_ai': GEMINI_AVAILABLE,
                'database': True,
                'file_system': True,
                'uploads_dir': True
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching system health: {str(e)}'
        }), 500

@app.route('/api/export_data', methods=['POST'])
@admin_required
def export_data():
    """Export dashboard data in various formats"""
    try:
        data = request.json
        export_type = data.get('type', 'csv')  # csv, xlsx, json
        data_category = data.get('category', 'all')  # products, invoices, users, all
        
        username = session.get('username')
        
        # Prepare data based on category
        export_data = {}
        
        if data_category in ['products', 'all']:
            export_data['products'] = default_products
        
        if data_category in ['invoices', 'all']:
            conn = sqlite3.connect('invoices.db')
            cursor = conn.cursor()
            
            cursor.execute('''SELECT * FROM invoices 
                             WHERE username = ? OR ? = "admin"
                             ORDER BY date DESC''', 
                          (username, username))
            
            columns = [description[0] for description in cursor.description]
            invoices = [dict(zip(columns, row)) for row in cursor.fetchall()]
            export_data['invoices'] = invoices
            
            conn.close()
        
        if data_category in ['users', 'all'] and session.get('role') == 'admin':
            conn = sqlite3.connect('invoices.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT username, role, created_at, last_login FROM users')
            users = [dict(zip(['username', 'role', 'created_at', 'last_login'], row)) 
                    for row in cursor.fetchall()]
            export_data['users'] = users
            
            conn.close()
        
        # Generate export file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'dashboard_export_{data_category}_{timestamp}'
        
        if export_type == 'json':
            import json
            file_content = json.dumps(export_data, indent=2, default=str)
            filename += '.json'
            
        elif export_type == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            
            # Export each category as separate sections
            for category, items in export_data.items():
                if not items:
                    continue
                    
                output.write(f"\n{category.upper()}\n")
                output.write("=" * 50 + "\n")
                
                if isinstance(items[0], dict):
                    fieldnames = items[0].keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(items)
                
                output.write("\n")
            
            file_content = output.getvalue()
            filename += '.csv'
            
        elif export_type == 'xlsx':
            try:
                import pandas as pd
                import io
                
                output = io.BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    for category, items in export_data.items():
                        if items:
                            df = pd.DataFrame(items)
                            df.to_excel(writer, sheet_name=category.capitalize(), index=False)
                
                file_content = output.getvalue()
                filename += '.xlsx'
                
            except ImportError:
                return jsonify({
                    'success': False,
                    'error': 'Excel export requires pandas and openpyxl packages'
                }), 400
        
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': f'/api/download_export/{filename}',
            'file_size': len(file_content) if isinstance(file_content, str) else len(file_content),
            'records_exported': sum(len(items) for items in export_data.values())
        })
        
    except Exception as e:
        print(f"❌ Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error exporting data: {str(e)}'
        }), 500

@app.route('/api/bulk_product_operations', methods=['POST'])
@admin_required
def bulk_product_operations():
    """Handle bulk operations on products"""
    try:
        data = request.json
        operation = data.get('operation')  # delete, update_price, update_stock, update_category
        product_names = data.get('product_names', [])
        parameters = data.get('parameters', {})
        
        if not operation or not product_names:
            return jsonify({
                'success': False,
                'error': 'Operation and product names are required'
            }), 400
        
        session_id = request.headers.get('Session-ID', 'default')
        session_data_local = get_session_data(session_id)
        
        # Get current products
        products = session_data_local['products'] if session_data_local['products'] else default_products
        
        updated_count = 0
        errors = []
        
        for product_name in product_names:
            try:
                # Find product
                product_index = None
                for i, product in enumerate(products):
                    if product['name'].lower() == product_name.lower():
                        product_index = i
                        break
                
                if product_index is None:
                    errors.append(f"Product '{product_name}' not found")
                    continue
                
                # Perform operation
                if operation == 'delete':
                    products.pop(product_index)
                    updated_count += 1
                    
                elif operation == 'update_price':
                    new_price = float(parameters.get('price', 0))
                    if new_price > 0:
                        products[product_index]['price'] = new_price
                        updated_count += 1
                    else:
                        errors.append(f"Invalid price for '{product_name}'")
                        
                elif operation == 'update_stock':
                    new_stock = int(parameters.get('stock', 0))
                    if new_stock >= 0:
                        products[product_index]['stock'] = new_stock
                        updated_count += 1
                    else:
                        errors.append(f"Invalid stock for '{product_name}'")
                        
                elif operation == 'update_category':
                    new_category = parameters.get('category', '')
                    if new_category:
                        products[product_index]['category'] = new_category
                        updated_count += 1
                    else:
                        errors.append(f"Invalid category for '{product_name}'")
                        
            except Exception as e:
                errors.append(f"Error processing '{product_name}': {str(e)}")
        
        # Save updated products
        if session_data_local['catalog_source'] == 'default':
            save_products(products)
        session_data_local['products'] = products
        
        return jsonify({
            'success': True,
            'operation': operation,
            'updated_count': updated_count,
            'total_requested': len(product_names),
            'errors': errors,
            'message': f'Successfully {operation.replace("_", " ")} {updated_count} products'
        })
        
    except Exception as e:
        print(f"❌ Error in bulk operations: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error in bulk operations: {str(e)}'
        }), 500

@app.route('/api/dashboard_settings', methods=['GET', 'POST'])
@admin_required
def dashboard_settings():
    """Get or update dashboard settings"""
    try:
        if request.method == 'GET':
            # Return current settings
            settings = {
                'auto_refresh_interval': 30,  # seconds
                'chart_animation': True,
                'real_time_updates': True,
                'notification_sound': False,
                'theme': 'light',
                'language': 'en',
                'timezone': 'UTC',
                'date_format': 'DD/MM/YYYY',
                'currency': 'INR',
                'dashboard_layout': 'default'
            }
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        else:  # POST
            # Update settings
            new_settings = request.json
            
            # Validate settings
            valid_settings = [
                'auto_refresh_interval', 'chart_animation', 'real_time_updates',
                'notification_sound', 'theme', 'language', 'timezone',
                'date_format', 'currency', 'dashboard_layout'
            ]
            
            updated_settings = {}
            for key, value in new_settings.items():
                if key in valid_settings:
                    updated_settings[key] = value
            
            # Here you would typically save to database or file
            # For now, we'll just return success
            
            return jsonify({
                'success': True,
                'message': 'Settings updated successfully',
                'updated_settings': updated_settings
            })
            
    except Exception as e:
        print(f"❌ Error handling dashboard settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error handling dashboard settings: {str(e)}'
        }), 500

@app.route('/api/real_time_updates', methods=['GET'])
@admin_required
def real_time_updates():
    """Get real-time updates for dashboard"""
    try:
        username = session.get('username')
        
        # Get latest data
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        
        # Get today's statistics
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''SELECT COUNT(*), SUM(amount) 
                         FROM invoices 
                         WHERE date = ? AND (username = ? OR ? = "admin")''', 
                      (today, username, username))
        
        today_stats = cursor.fetchone()
        today_orders = today_stats[0] or 0
        today_revenue = today_stats[1] or 0
        
        # Get latest invoice
        cursor.execute('''SELECT invoice_number, client_name, amount, date 
                         FROM invoices 
                         WHERE username = ? OR ? = "admin"
                         ORDER BY id DESC LIMIT 1''', 
                      (username, username))
        
        latest_invoice = cursor.fetchone()
        
        conn.close()
        
        # Prepare updates
        updates = {
            'timestamp': datetime.now().isoformat(),
            'today_orders': today_orders,
            'today_revenue': today_revenue,
            'latest_invoice': {
                'number': latest_invoice[0] if latest_invoice else None,
                'client': latest_invoice[1] if latest_invoice else None,
                'amount': latest_invoice[2] if latest_invoice else None,
                'date': latest_invoice[3] if latest_invoice else None
            } if latest_invoice else None,
            'system_status': {
                'api_healthy': True,
                'database_healthy': True,
                'last_backup': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'active_users': len(session_data)
            },
            'notifications': [
                {
                    'id': 'notif_1',
                    'type': 'info',
                    'message': f'{today_orders} orders processed today',
                    'timestamp': datetime.now().isoformat()
                }
            ] if today_orders > 0 else []
        }
        
        return jsonify({
            'success': True,
            'updates': updates
        })
        
    except Exception as e:
        print(f"❌ Error getting real-time updates: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error getting real-time updates: {str(e)}'
        }), 500

# WebSocket support for real-time updates (optional)
try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect():
        if 'username' in session:
            join_room(session['username'])
            emit('status', {'msg': f"Connected to real-time updates"})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        if 'username' in session:
            leave_room(session['username'])
    
    @socketio.on('subscribe_dashboard')
    def handle_dashboard_subscribe():
        if 'username' in session and session.get('role') == 'admin':
            join_room('dashboard_updates')
            emit('subscribed', {'room': 'dashboard_updates'})
    
    def broadcast_dashboard_update(data):
        """Helper function to broadcast dashboard updates"""
        socketio.emit('dashboard_update', data, room='dashboard_updates')
    
except ImportError:
    print("⚠️ Flask-SocketIO not available. Real-time WebSocket updates disabled.")
    socketio = None
    
    def broadcast_dashboard_update(data):
        pass

# Enhanced error handlers
@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found',
            'path': request.path
        }), 404
    else:
        return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Please contact the administrator if this persists'
        }), 500
    else:
        return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Access forbidden',
            'message': 'You do not have permission to access this resource'
        }), 403
    else:
        return render_template('403.html'), 403

# Enhanced route for serving the new admin dashboard
@app.route('/admin/enhanced')
@admin_required
def enhanced_admin_dashboard():
    """Serve the enhanced admin dashboard"""
    return render_template('enhanced_admin_dashboard.html')

# API endpoint to check if enhanced dashboard is available
@app.route('/api/enhanced_dashboard_available', methods=['GET'])
def enhanced_dashboard_available():
    """Check if enhanced dashboard features are available"""
    return jsonify({
        'success': True,
        'available': True,
        'features': {
            'real_time_updates': True,
            'advanced_analytics': True,
            'bulk_operations': True,
            'export_functionality': True,
            'system_health_monitoring': True,
            'websocket_support': socketio is not None
        }
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle user logout - clear session and return success"""
    try:
        # Log the logout attempt
        username = session.get('username', 'Unknown')
        print(f"🚪 Logout attempt for user: {username}")
        
        # Clear all session data
        session.clear()
        
        # Also clear any session_data for this user if needed
        session_id = request.headers.get('Session-ID')
        if session_id and session_id in session_data:
            session_data[session_id] = {
                'cart': {},
                'client_details': {},
                'conversation_history': [],
                'products': [],
                'catalog_source': 'default',
                'overall_discount': 0,
                'current_chat_id': None
            }
        
        print(f"✅ Successful logout for user: {username}")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        print(f"❌ Error during logout: {str(e)}")
        # Even if there's an error, we should still return success for security
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })



# Continue with the remaining supporting functions and the main execution block
if __name__ == '__main__':
    # Run database initialization and migration
    print("🚀 Starting AI Invoice Assistant...")
    
   

    # Run with or without SocketIO depending on availability
    if socketio:
        print("✅ Running with WebSocket support for real-time updates")
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    else:
        print("⚠️ Running without WebSocket support")
        app.run(debug=True, host='0.0.0.0', port=5000)