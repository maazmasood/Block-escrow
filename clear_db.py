from app import app
from database import db
import os

def clear_database():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Recreating all tables with fresh schema...")
        db.create_all()
        print("Database cleared successfully.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to CLEAR the entire database? (y/n): ")
    if confirm.lower() == 'y':
        clear_database()
    else:
        print("Operation cancelled.")
