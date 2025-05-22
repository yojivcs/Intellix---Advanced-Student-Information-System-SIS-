import sqlite3
from pathlib import Path

def main():
    """Remove all teacher assignments from courses"""
    print("Removing all teacher assignments from courses...")
    
    # Find database file
    db_path = Path("database/intellix.db")
    if not db_path.exists():
        print(f"Database file not found at {db_path}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Delete all records from the teaching table
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teaching")
        
        # Get count of deleted rows
        deleted_count = cursor.rowcount
        
        # Commit changes
        conn.commit()
        
        # Close the connection
        conn.close()
        
        print(f"Successfully removed {deleted_count} teacher assignments")
        return True
    
    except Exception as e:
        print(f"Error removing teacher assignments: {e}")
        return False

if __name__ == "__main__":
    main() 