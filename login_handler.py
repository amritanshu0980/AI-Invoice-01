from flask import Blueprint, render_template, request, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

login_bp = Blueprint('login', __name__)

def setup_login_routes(app):
    app.register_blueprint(login_bp)

def init_users_db():
    conn = sqlite3.connect('invoices.db')
    cursor = conn.cursor()
    
    # Existing users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin'))
        )
    ''')
    
    # New chat_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            username TEXT NOT NULL,
            title TEXT,
            timestamp TEXT,
            messages TEXT,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    
    # Seed default users
    try:
        cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
                      ('admin', generate_password_hash('admin123'), 'admin'))
        cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
                      ('user1', generate_password_hash('user123'), 'user'))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

init_users_db()

@login_bp.route('/api/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = sqlite3.connect('invoices.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[0], password):
            session['username'] = username
            session['role'] = user[1]
            return jsonify({'success': True, 'role': user[1]})
        else:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
    
    return render_template('login.html')

@login_bp.route('/api/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@login_bp.route('/api/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = 'user'  # New users are 'user' by default
        
        try:
            conn = sqlite3.connect('invoices.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                         (username, generate_password_hash(password), role))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'error': 'Username already exists'}), 400
    
    return render_template('register.html')