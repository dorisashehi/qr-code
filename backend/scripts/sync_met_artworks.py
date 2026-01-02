"""
Main script for syncing MET Museum artwork data to PostgreSQL database.

This script orchestrates the complete data pipeline:
1. Database setup and connection check
2. Fetching data from MET API
3. Cleaning and validating data
4. Saving to database using bulk operations
"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database.database import init_db
from database.artwork_repository import check_database_connection, save_to_database
from api.met_client import fetch_museum_data
from data.cleaners import clean_and_validate_data


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SETTING UP DATABASE")
    print("="*60)

    if not check_database_connection():
        print("\n⚠️  Cannot connect to database. Please check your DATABASE_URL and try again.")
        sys.exit(1)

    print("\nCreating database tables if they don't exist...")
    try:
        init_db()
        print("✓ Database tables ready")
    except Exception as e:
        print(f"✗ Failed to create database tables: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("STARTING DATA SYNC")
    print("="*60)

    department_ids = [1, 11]

    df = fetch_museum_data(department_ids, limit_per_department=20)

    df = clean_and_validate_data(df)

    print("\n" + "="*60)
    print("DATASET OVERVIEW")
    print("="*60)
    print(f"Total objects: {len(df)}")
    print(f"\nDepartments represented:")
    print(df["department"].value_counts())

    save_to_database(df)
