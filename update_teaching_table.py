import sqlite3
import os
from pathlib import Path

def update_teaching_table():
    """Add marks_finalized column to teaching table"""
    db_path = os.path.join("database", "intellix.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if marks_finalized column exists
        cursor.execute("PRAGMA table_info(teaching)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "marks_finalized" not in columns:
            print("Adding marks_finalized column to teaching table...")
            
            # Add marks_finalized column
            cursor.execute("""
                ALTER TABLE teaching 
                ADD COLUMN marks_finalized BOOLEAN DEFAULT 0
            """)
            
            # Add finalized_at column
            if "finalized_at" not in columns:
                cursor.execute("""
                    ALTER TABLE teaching 
                    ADD COLUMN finalized_at TIMESTAMP
                """)
            
            conn.commit()
            print("Teaching table updated successfully!")
        else:
            print("marks_finalized column already exists.")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error updating teaching table: {e}")
        return False

if __name__ == "__main__":
    update_teaching_table() 