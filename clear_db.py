from app import app
from database import db
from models import Order, AuditLog, User, Notification, AISummary, OrderDocument

def clear_database():
    with app.app_context():
        print("Clearing database...")
        db.session.query(OrderDocument).delete()
        db.session.query(Order).delete()
        db.session.query(AuditLog).delete()
        db.session.query(Notification).delete()
        db.session.query(AISummary).delete()
        db.session.commit()
        print("Database cleared (Users preserved)!")

if __name__ == "__main__":
    confirm = input("Are you sure you want to CLEAR the entire database? (y/n): ")
    if confirm.lower() == 'y':
        clear_database()
    else:
        print("Operation cancelled.")
