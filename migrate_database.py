"""
Final Database Migration Script for AI Invoice Assistant
Fixed SQLite compatibility issues with non-constant defaults.
"""

import sqlite3
import os
import shutil
import json
from datetime import datetime

def backup_database():
    """Create a backup of the existing database"""
    if os.path.exists('invoices.db'):
        backup_name = f"invoices_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2('invoices.db', backup_name)
        print(f"✅ Database backed up to: {backup_name}")
        return backup_name
    else:
        print("ℹ️ No existing database found")
        return None

def migrate_database():
    """Perform the actual database migration"""
    conn = sqlite3.connect('invoices.db')
    cursor = conn.cursor()
    
    try:
        print("🔄 Starting database migration...")
        
        # Step 1: Check current schema
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(chat_history)")
        chat_columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(invoices)")
        invoice_columns = [column[1] for column in cursor.fetchall()]
        
        print(f"📋 Current users columns: {users_columns}")
        print(f"📋 Current chat_history columns: {chat_columns}")
        print(f"📋 Current invoices columns: {invoice_columns}")
        
        # Step 2: Migrate users table
        if 'created_at' not in users_columns:
            print("🔄 Adding created_at column to users table...")
            # Use NULL as default, then update with actual timestamp
            cursor.execute('ALTER TABLE users ADD COLUMN created_at TIMESTAMP')
            cursor.execute('UPDATE users SET created_at = ? WHERE created_at IS NULL', (datetime.now().isoformat(),))
        
        if 'last_login' not in users_columns:
            print("🔄 Adding last_login column to users table...")
            cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
        
        # Step 3: Migrate invoices table
        if 'username' not in invoice_columns:
            print("🔄 Adding username column to invoices table...")
            cursor.execute('ALTER TABLE invoices ADD COLUMN username TEXT')
        
        if 'created_at' not in invoice_columns:
            print("🔄 Adding created_at column to invoices table...")
            cursor.execute('ALTER TABLE invoices ADD COLUMN created_at TIMESTAMP')
            cursor.execute('UPDATE invoices SET created_at = date WHERE created_at IS NULL')
        
        # Step 4: Handle chat_history table migration (complex)
        if 'messages' in chat_columns and 'created_at' not in chat_columns:
            print("🔄 Migrating chat_history table with old schema...")
            migrate_chat_history_table(cursor)
        elif 'created_at' not in chat_columns:
            print("🔄 Adding missing columns to chat_history table...")
            cursor.execute('ALTER TABLE chat_history ADD COLUMN created_at TIMESTAMP')
            cursor.execute('ALTER TABLE chat_history ADD COLUMN updated_at TIMESTAMP')
            cursor.execute('ALTER TABLE chat_history ADD COLUMN is_active INTEGER DEFAULT 1')
            # Update timestamps from existing timestamp column
            cursor.execute('UPDATE chat_history SET created_at = timestamp, updated_at = timestamp WHERE created_at IS NULL')
        
        # Step 5: Create messages table if it doesn't exist
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
                    timestamp TIMESTAMP,
                    metadata TEXT
                )
            ''')
        
        # Step 6: Create indexes (skip if they cause errors)
        print("🔄 Creating database indexes...")
        indexes = [
            ('idx_chat_username', 'CREATE INDEX IF NOT EXISTS idx_chat_username ON chat_history (username)'),
            ('idx_messages_chat', 'CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id)'),
            ('idx_invoices_username', 'CREATE INDEX IF NOT EXISTS idx_invoices_username ON invoices (username)')
        ]
        
        for index_name, index_sql in indexes:
            try:
                cursor.execute(index_sql)
                print(f"   ✅ Created index: {index_name}")
            except Exception as e:
                print(f"   ⚠️ Could not create index {index_name}: {e}")
        
        conn.commit()
        print("✅ Database migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()

def migrate_chat_history_table(cursor):
    """Migrate chat_history table from old schema to new schema"""
    print("🔄 Performing complex chat_history migration...")
    
    # Step 1: Get all existing data
    cursor.execute('SELECT id, chat_id, username, title, timestamp, messages FROM chat_history')
    old_data = cursor.fetchall()
    
    print(f"📊 Found {len(old_data)} chats to migrate")
    
    # Step 2: Create new table with correct schema
    cursor.execute('''
        CREATE TABLE chat_history_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Step 3: Create messages table if not exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                username TEXT NOT NULL,
                message_type TEXT NOT NULL CHECK(message_type IN ('user', 'ai')),
                content TEXT NOT NULL,
                timestamp TIMESTAMP,
                metadata TEXT
            )
        ''')
    
    # Step 4: Migrate data
    migrated_chats = 0
    migrated_messages = 0
    current_time = datetime.now().isoformat()
    
    for row in old_data:
        try:
            old_id, chat_id, username, title, timestamp, messages_json = row
            
            # Use existing timestamp or current time
            use_timestamp = timestamp if timestamp else current_time
            
            # Generate chat_id if missing
            use_chat_id = chat_id if chat_id else f"chat_{old_id}_{int(datetime.now().timestamp())}"
            
            # Insert chat record
            cursor.execute('''
                INSERT INTO chat_history_new (chat_id, username, title, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                use_chat_id,
                username or 'unknown',
                title or f"Chat {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                use_timestamp,
                use_timestamp,
                1
            ))
            migrated_chats += 1
            
            # Migrate messages if they exist
            if messages_json:
                try:
                    messages_data = json.loads(messages_json)
                    for msg in messages_data:
                        message_type = msg.get('role', 'ai')
                        if message_type == 'assistant':
                            message_type = 'ai'
                        
                        cursor.execute('''
                            INSERT INTO messages (chat_id, username, message_type, content, timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            use_chat_id,
                            username or 'unknown',
                            message_type,
                            msg.get('content', ''),
                            msg.get('timestamp', current_time)
                        ))
                        migrated_messages += 1
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"   ⚠️ Could not migrate messages for chat {use_chat_id}: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Error migrating chat {chat_id}: {e}")
            continue
    
    # Step 5: Replace old table with new one
    cursor.execute('DROP TABLE chat_history')
    cursor.execute('ALTER TABLE chat_history_new RENAME TO chat_history')
    
    print(f"✅ Migrated {migrated_chats} chats and {migrated_messages} messages")

def verify_migration():
    """Verify that the migration was successful"""
    print("🔍 Verifying migration...")
    
    conn = sqlite3.connect('invoices.db')
    cursor = conn.cursor()
    
    try:
        # Check chat_history schema
        cursor.execute("PRAGMA table_info(chat_history)")
        chat_columns = [column[1] for column in cursor.fetchall()]
        
        required_columns = ['chat_id', 'username', 'title', 'created_at', 'updated_at', 'is_active']
        missing_columns = [col for col in required_columns if col not in chat_columns]
        
        if missing_columns:
            print(f"❌ Missing columns in chat_history: {missing_columns}")
            return False
        
        # Check messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
        if not cursor.fetchone():
            print("❌ Messages table not found")
            return False
        
        # Check users table has new columns
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]
        if 'created_at' not in user_columns:
            print("❌ Users table missing created_at column")
            return False
        
        # Check data counts
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        chat_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        message_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM invoices")
        invoice_count = cursor.fetchone()[0]
        
        print(f"✅ Verification successful:")
        print(f"   📊 Chats: {chat_count}")
        print(f"   💬 Messages: {message_count}")
        print(f"   👥 Users: {user_count}")
        print(f"   📄 Invoices: {invoice_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False
    finally:
        conn.close()

def main():
    print("🚀 AI Invoice Assistant Database Migration Tool (Fixed)")
    print("=" * 55)
    
    if not os.path.exists('invoices.db'):
        print("❌ No database file found (invoices.db)")
        return
    
    # Step 1: Create backup
    print("\n💾 Creating backup...")
    backup_file = backup_database()
    
    # Step 2: Ask for confirmation
    print(f"\n🔄 Ready to migrate database to new schema.")
    print(f"💾 Backup created: {backup_file}")
    print("🔧 This version fixes SQLite compatibility issues.")
    response = input("\nProceed with migration? (y/n): ").lower().strip()
    
    if response != 'y':
        print("❌ Migration cancelled.")
        return
    
    # Step 3: Migrate
    try:
        migrate_database()
        
        # Step 4: Verify
        if verify_migration():
            print("\n🎉 Migration completed successfully!")
            print("✨ You can now run your application:")
            print("   python app0.py")
        else:
            print(f"\n❌ Migration verification failed!")
            print(f"💡 You can restore from backup: {backup_file}")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"💡 You can restore from backup: {backup_file}")

if __name__ == "__main__":
    main()