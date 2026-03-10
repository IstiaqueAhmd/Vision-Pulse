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
            try:
                # First let's check if the column exists
                result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' and column_name='profile_image_url';"))
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_image_url VARCHAR;"))
                    conn.commit()
                    print("Migration successful: added profile_image_url column.")
                else:
                    print("Column 'profile_image_url' already exists.")
            except Exception as inner_e:
                print(f"Error executing sql: {inner_e}")
                
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    run_migration()
