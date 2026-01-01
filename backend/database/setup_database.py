"""
Complete database setup script
Run this to set up your database from scratch
"""
import os
import sys
from sqlalchemy import text
from database import init_db, engine, get_db_session
from models import Artwork, GeneratedContent


def check_postgresql_connection():
    """Check if we can connect to PostgreSQL"""
    print("\n" + "="*60)
    print("STEP 1: Checking PostgreSQL Connection")
    print("="*60)

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print("✓ Successfully connected to PostgreSQL!")
            print(f"  Version: {version.split(',')[0]}")
            return True
    except Exception as e:
        print(f"✗ Failed to connect to PostgreSQL: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is installed and running")
        print("2. Check your DATABASE_URL in .env file")
        print("3. Verify database credentials")
        return False


def create_tables():
    """Create all database tables"""
    print("\n" + "="*60)
    print("STEP 2: Creating Database Tables")
    print("="*60)

    try:
        init_db()
        print("\nTables created:")
        print("  ✓ artworks")
        print("  ✓ generated_content")
        return True
    except Exception as e:
        print(f"✗ Failed to create tables: {e}")
        return False


def verify_tables():
    """Verify that tables were created correctly"""
    print("\n" + "="*60)
    print("STEP 3: Verifying Table Structure")
    print("="*60)

    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)

        # Check artworks table
        if 'artworks' in inspector.get_table_names():
            columns = inspector.get_columns('artworks')
            print(f"\n✓ artworks table: {len(columns)} columns")

            # Verify key columns exist
            column_names = [col['name'] for col in columns]
            required_columns = ['id', 'met_object_id', 'title', 'artist_display_name']
            missing = [col for col in required_columns if col not in column_names]

            if missing:
                print(f"  ⚠ Missing columns: {missing}")
            else:
                print("  ✓ All required columns present")

            # Check indexes
            indexes = inspector.get_indexes('artworks')
            print(f"  ✓ {len(indexes)} indexes created")

        # Check generated_content table
        if 'generated_content' in inspector.get_table_names():
            columns = inspector.get_columns('generated_content')
            print(f"\n✓ generated_content table: {len(columns)} columns")

            # Check foreign key
            foreign_keys = inspector.get_foreign_keys('generated_content')
            if foreign_keys:
                print(f"  ✓ Foreign key to artworks table configured")

        return True
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False


def create_sample_data():
    """Create some sample data to test the database"""
    print("\n" + "="*60)
    print("STEP 4: Creating Sample Data (Optional)")
    print("="*60)

    response = input("\nDo you want to create sample test data? (y/n): ")
    if response.lower() != 'y':
        print("Skipping sample data creation")
        return True

    try:
        with get_db_session() as db:
            test_met_id = 999999

            existing_artwork = db.query(Artwork).filter(
                Artwork.met_object_id == test_met_id
            ).first()

            if existing_artwork:
                print(f"✓ Sample data already exists (MET ID: {test_met_id})")
                print(f"  - Artwork ID: {existing_artwork.id}")
                print(f"  - Title: {existing_artwork.title}")

                existing_content = db.query(GeneratedContent).filter(
                    GeneratedContent.artwork_id == existing_artwork.id
                ).first()

                if existing_content:
                    print(f"  - Generated content already exists")
                else:
                    sample_content = GeneratedContent(
                        artwork_id=existing_artwork.id,
                        content="This is a test description of the artwork.",
                        image_analysis="Test image analysis",
                        qa_status="pending"
                    )
                    db.add(sample_content)
                    print(f"  - Created generated content for existing artwork")

                return True

            sample_artwork = Artwork(
                met_object_id=test_met_id,
                title="Test Artwork",
                artist_display_name="Test Artist",
                artist_nationality="American",
                object_date="2024",
                object_begin_date=2024,
                object_end_date=2024,
                department="Test Department",
                medium="Oil on canvas",
                is_public_domain=True,
                metadata={"test": True}
            )
            db.add(sample_artwork)
            db.flush()

            sample_content = GeneratedContent(
                artwork_id=sample_artwork.id,
                content="This is a test description of the artwork.",
                image_analysis="Test image analysis",
                qa_status="pending"
            )
            db.add(sample_content)

        print("✓ Sample data created successfully!")
        print(f"  - Created 1 test artwork (ID: {sample_artwork.id})")
        print(f"  - Created 1 generated content record")
        return True
    except Exception as e:
        print(f"✗ Failed to create sample data: {e}")
        return False


def show_database_stats():
    """Show statistics about the database"""
    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)

    try:
        with get_db_session() as db:
            artwork_count = db.query(Artwork).count()
            content_count = db.query(GeneratedContent).count()

            print(f"Artworks: {artwork_count}")
            print(f"Generated Content: {content_count}")

            if artwork_count > 0:
                print("\nSample artwork:")
                sample = db.query(Artwork).first()
                print(f"  ID: {sample.id}")
                print(f"  MET ID: {sample.met_object_id}")
                print(f"  Title: {sample.title}")
                print(f"  Artist: {sample.artist_display_name}")
    except Exception as e:
        print(f"Error retrieving stats: {e}")


def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("DATABASE SETUP")
    print("="*60)
    print("\nThis script will set up your PostgreSQL database with all required tables.")

    # Check connection
    if not check_postgresql_connection():
        print("\n⚠️  Setup failed at connection step")
        print("Please fix the connection issues and try again.")
        sys.exit(1)

    # Create tables
    if not create_tables():
        print("\n⚠️  Setup failed at table creation step")
        sys.exit(1)

    # Verify tables
    if not verify_tables():
        print("\n⚠️  Setup completed but verification failed")
        print("Tables were created but may not be correct")

    # Optional: Create sample data
    create_sample_data()

    # Show stats
    show_database_stats()

    print("\n" + "="*60)
    print("✓ DATABASE SETUP COMPLETE!")
    print("="*60)

    print("\n")


if __name__ == "__main__":
    main()