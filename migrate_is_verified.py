import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine

def run_migration():
    try:
        with engine.connect() as conn:
            # Check if column exists, if not, create it
            # The IF NOT EXISTS is for Postgres 10+ but it's simpler to just try it
            try:
                # First let's check if the column exists
                result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' and column_name='is_verified';"))
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;"))
                    
                    # Ensure existing users are not blocked
                    conn.execute(text("UPDATE users SET is_verified = TRUE;"))
                    conn.commit()
                    print("Migration successful: added is_verified column and updated existing users.")
                else:
                    print("Column 'is_verified' already exists.")
            except Exception as inner_e:
                print(f"Error executing sql: {inner_e}")
                
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    run_migration()
