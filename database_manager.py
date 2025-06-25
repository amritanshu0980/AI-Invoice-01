import sqlite3
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash
import json
import os

class DatabaseManager:
    def __init__(self, db_path='invoices.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection with row factory for dict-like access"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database with all required tables and indexes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            print("🔄 Initializing database...")
            
            # Check if this is an existing database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            users_table_exists = cursor.fetchone() is not None
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history';")
            chat_table_exists = cursor.fetchone() is not None
            
            if users_table_exists or chat_table_exists:
                print("📂 Existing database detected, performing migration...")
                self._migrate_existing_database(cursor)
            else:
                print("🆕 Creating new database...")
                self._create_fresh_database(cursor)
            
            conn.commit()
            print("✅ Database initialized successfully")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error initializing database: {e}")
            raise
        finally:
            conn.close()
    
    def _create_fresh_database(self, cursor):
        """Create fresh database with new schema"""
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Enhanced chat_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # New messages table for better performance
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                username TEXT NOT NULL,
                message_type TEXT NOT NULL CHECK(message_type IN ('user', 'ai')),
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT, -- JSON for additional data
                FOREIGN KEY (chat_id) REFERENCES chat_history (chat_id) ON DELETE CASCADE,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Invoices table (existing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE,
                client_name TEXT,
                amount REAL,
                date TEXT,
                pdf_path TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')
        
        # Create indexes
        self._create_indexes(cursor)
        
        # Seed default users
        self._seed_default_users(cursor)
    
    def _migrate_existing_database(self, cursor):
        """Migrate existing database to new schema"""
        # First, let's check what columns exist in existing tables
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(chat_history)")
        chat_columns = [column[1] for column in cursor.fetchall()]
        
        # Migrate users table
        if 'created_at' not in users_columns:
            print("🔄 Adding missing columns to users table...")
            cursor.execute('ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        if 'last_login' not in users_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
        
        # Handle chat_history table migration
        if 'created_at' not in chat_columns:
            print("🔄 Migrating chat_history table...")
            
            # Check if old messages column exists (needs complex migration)
            if 'messages' in chat_columns:
                # This is the old schema with JSON messages
                self._migrate_chat_history_with_messages(cursor)
            else:
                # This is a partial new schema, just add missing columns
                cursor.execute('ALTER TABLE chat_history ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                cursor.execute('ALTER TABLE chat_history ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                cursor.execute('ALTER TABLE chat_history ADD COLUMN is_active BOOLEAN DEFAULT 1')
        
        # Create messages table if it doesn't exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
        if not cursor.fetchone():
            print("🔄 Creating messages table...")
            cursor.execute('''
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    message_type TEXT NOT NULL CHECK(message_type IN ('user', 'ai')),
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (chat_id) REFERENCES chat_history (chat_id) ON DELETE CASCADE,
                    FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
                )
            ''')
        
        # Update invoices table if needed
        cursor.execute("PRAGMA table_info(invoices)")
        invoice_columns = [column[1] for column in cursor.fetchall()]
        if 'username' not in invoice_columns:
            cursor.execute('ALTER TABLE invoices ADD COLUMN username TEXT')
        if 'created_at' not in invoice_columns:
            cursor.execute('ALTER TABLE invoices ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        
        # Create indexes (they will be ignored if they already exist)
        self._create_indexes(cursor)
        
        # Seed default users if none exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            self._seed_default_users(cursor)
    
    def _migrate_chat_history_with_messages(self, cursor):
        """Complex migration for chat_history table with old messages column"""
        print("🔄 Performing complex chat_history migration...")
        
        # Step 1: Create new chat_history table with new schema
        cursor.execute('''
            CREATE TABLE chat_history_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Step 2: Create messages table
        cursor.execute('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                username TEXT NOT NULL,
                message_type TEXT NOT NULL CHECK(message_type IN ('user', 'ai')),
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (chat_id) REFERENCES chat_history (chat_id) ON DELETE CASCADE,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Step 3: Migrate data from old table
        cursor.execute('SELECT chat_id, username, title, timestamp, messages FROM chat_history')
        old_chats = cursor.fetchall()
        
        migrated_count = 0
        for chat in old_chats:
            try:
                # Insert into new chat_history table
                cursor.execute('''
                    INSERT INTO chat_history_new (chat_id, username, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    chat['chat_id'],
                    chat['username'],
                    chat['title'],
                    chat['timestamp'] or datetime.now().isoformat(),
                    chat['timestamp'] or datetime.now().isoformat()
                ))
                
                # Migrate messages if they exist
                if chat['messages']:
                    try:
                        messages_data = json.loads(chat['messages'])
                        for msg in messages_data:
                            cursor.execute('''
                                INSERT INTO messages (chat_id, username, message_type, content, timestamp)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (
                                chat['chat_id'],
                                chat['username'],
                                msg.get('role', 'ai') if msg.get('role') != 'assistant' else 'ai',
                                msg.get('content', ''),
                                msg.get('timestamp', datetime.now().isoformat())
                            ))
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"⚠️ Could not migrate messages for chat {chat['chat_id']}: {e}")
                
                migrated_count += 1
            except Exception as e:
                print(f"⚠️ Error migrating chat {chat['chat_id']}: {e}")
                continue
        
        # Step 4: Replace old table with new one
        cursor.execute('DROP TABLE chat_history')
        cursor.execute('ALTER TABLE chat_history_new RENAME TO chat_history')
        
        print(f"✅ Migrated {migrated_count} chats successfully")
    
    def _create_indexes(self, cursor):
        """Create database indexes for better performance"""
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_username ON chat_history (username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_history (created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_updated ON chat_history (updated_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoices_username ON invoices (username)')
        except Exception as e:
            print(f"⚠️ Warning: Could not create some indexes: {e}")
    
    def _seed_default_users(self, cursor):
        """Create default admin and user accounts"""
        try:
            # Check if users already exist
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                # Create default admin
                cursor.execute('''
                    INSERT INTO users (username, password, role) 
                    VALUES (?, ?, ?)
                ''', ('admin', generate_password_hash('admin123'), 'admin'))
                
                # Create default user
                cursor.execute('''
                    INSERT INTO users (username, password, role) 
                    VALUES (?, ?, ?)
                ''', ('user1', generate_password_hash('user123'), 'user'))
                
                print("✅ Default users created (admin/admin123, user1/user123)")
        except Exception as e:
            print(f"⚠️ Error seeding default users: {e}")
    
    def generate_chat_id(self):
        """Generate unique chat ID"""
        return f"chat_{uuid.uuid4()}"
    
    def generate_chat_title(self):
        """Generate chat title with DD/MM/YYYY HH:MM format"""
        now = datetime.now()
        return now.strftime("%d/%m/%Y %H:%M")
    
    # Chat Management Methods
    def create_new_chat(self, username):
        """Create a new chat for user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            chat_id = self.generate_chat_id()
            title = self.generate_chat_title()
            
            cursor.execute('''
                INSERT INTO chat_history (chat_id, username, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, username, title, datetime.now(), datetime.now()))
            
            conn.commit()
            return chat_id, title
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating chat: {e}")
        finally:
            conn.close()
    
    def get_user_chats(self, username, limit=50):
        """Get user's chats ordered by creation date (most recent first)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT chat_id, title, created_at, updated_at,
                       (SELECT COUNT(*) FROM messages WHERE messages.chat_id = chat_history.chat_id) as message_count
                FROM chat_history 
                WHERE username = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT ?
            ''', (username, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            raise Exception(f"Error fetching chats: {e}")
        finally:
            conn.close()
    
    def get_chat_messages(self, chat_id, username):
        """Get all messages for a specific chat"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify chat belongs to user
            cursor.execute('''
                SELECT 1 FROM chat_history 
                WHERE chat_id = ? AND username = ? AND is_active = 1
            ''', (chat_id, username))
            
            if not cursor.fetchone():
                raise Exception("Chat not found or access denied")
            
            # Get messages
            cursor.execute('''
                SELECT message_type, content, timestamp, metadata
                FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp ASC
            ''', (chat_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            raise Exception(f"Error fetching messages: {e}")
        finally:
            conn.close()
    
    def save_message(self, chat_id, username, message_type, content, metadata=None):
        """Save a single message to database with duplicate prevention"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify chat exists and belongs to user
            cursor.execute('''
                SELECT 1 FROM chat_history 
                WHERE chat_id = ? AND username = ? AND is_active = 1
            ''', (chat_id, username))
            
            if not cursor.fetchone():
                raise Exception("Chat not found or access denied")
            
            # Check if this exact message already exists (duplicate prevention)
            cursor.execute('''
                SELECT id FROM messages 
                WHERE chat_id = ? AND username = ? AND message_type = ? AND content = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (chat_id, username, message_type, content))
            
            existing_message = cursor.fetchone()
            if existing_message:
                print(f"⚠️ Duplicate message detected, skipping save: {content[:50]}...")
                return True  # Return success but don't save duplicate
            
            # Save message if it's not a duplicate
            cursor.execute('''
                INSERT INTO messages (chat_id, username, message_type, content, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, username, message_type, content, 
                json.dumps(metadata) if metadata else None, datetime.now()))
            
            # Update chat's updated_at timestamp
            cursor.execute('''
                UPDATE chat_history 
                SET updated_at = ? 
                WHERE chat_id = ?
            ''', (datetime.now(), chat_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error saving message: {e}")
        finally:
            conn.close()
    
    def delete_chat(self, chat_id, username):
        """Delete a chat (soft delete by setting is_active = 0)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify chat belongs to user
            cursor.execute('''
                SELECT 1 FROM chat_history 
                WHERE chat_id = ? AND username = ? AND is_active = 1
            ''', (chat_id, username))
            
            if not cursor.fetchone():
                raise Exception("Chat not found or access denied")
            
            # Soft delete chat
            cursor.execute('''
                UPDATE chat_history 
                SET is_active = 0, updated_at = ?
                WHERE chat_id = ?
            ''', (datetime.now(), chat_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error deleting chat: {e}")
        finally:
            conn.close()
    
    def rename_chat(self, chat_id, username, new_title):
        """Rename a chat"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify chat belongs to user
            cursor.execute('''
                SELECT 1 FROM chat_history 
                WHERE chat_id = ? AND username = ? AND is_active = 1
            ''', (chat_id, username))
            
            if not cursor.fetchone():
                raise Exception("Chat not found or access denied")
            
            # Update title
            cursor.execute('''
                UPDATE chat_history 
                SET title = ?, updated_at = ?
                WHERE chat_id = ?
            ''', (new_title.strip(), datetime.now(), chat_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error renaming chat: {e}")
        finally:
            conn.close()
    
    def update_user_login(self, username):
        """Update user's last login timestamp"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET last_login = ? 
                WHERE username = ?
            ''', (datetime.now(), username))
            conn.commit()
        except Exception as e:
            print(f"Error updating login time: {e}")
        finally:
            conn.close()