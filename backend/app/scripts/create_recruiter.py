
from getpass import getpass

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Recruiter
from app.auth.security import hash_password


def create_recruiter():
    db: Session = SessionLocal()

    try:
        print("\n===== CREATE RECRUITER ACCOUNT =====\n")

        full_name = input("Recruiter full name: ").strip()
        email = input("Recruiter email: ").strip().lower()

        if not full_name or not email:
            print("Name and email are required.")
            return

        existing = (
            db.query(Recruiter)
            .filter(Recruiter.email == email)
            .first()
        )

        if existing:
            print("A recruiter with this email already exists.")
            return

        password = getpass("Create password: ")
        confirm_password = getpass("Confirm password: ")

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            return

        if password != confirm_password:
            print("Passwords do not match.")
            return

        recruiter = Recruiter(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )

        db.add(recruiter)
        db.commit()
        db.refresh(recruiter)

        print("\nRecruiter created successfully!")
        print(f"Recruiter ID: {recruiter.id}")
        print(f"Email: {recruiter.email}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_recruiter()
