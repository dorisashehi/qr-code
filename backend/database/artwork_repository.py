"""
Database repository for artwork operations.

This module handles all database operations for artworks including
bulk insert, update, and data preparation.
"""
import pandas as pd
from datetime import datetime
from database.database import get_db_session, engine
from database.models import Artwork
from sqlalchemy import text


def check_database_connection():
    """
    Check if we can connect to PostgreSQL database.

    Returns:
        bool: True if connection successful, False otherwise
    """
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


def prepare_artwork_data(row):
    """
    Convert a DataFrame row into a dictionary ready for database insertion.

    This helper function handles all the data conversion and null checking
    so we can reuse it for both inserts and updates.

    Args:
        row: A pandas Series representing one row from the DataFrame

    Returns:
        dict: Dictionary with artwork data ready for database
    """
    return {
        'met_object_id': int(row['met_object_id']),
        'title': row.get('title') if pd.notna(row.get('title')) else None,
        'object_name': row.get('object_name') if pd.notna(row.get('object_name')) else None,
        'object_date': row.get('object_date') if pd.notna(row.get('object_date')) else None,
        'object_begin_date': int(row.get('object_begin_date')) if pd.notna(row.get('object_begin_date')) else None,
        'object_end_date': int(row.get('object_end_date')) if pd.notna(row.get('object_end_date')) else None,
        'artist_display_name': row.get('artist_display_name') if pd.notna(row.get('artist_display_name')) else None,
        'artist_display_bio': row.get('artist_display_bio') if pd.notna(row.get('artist_display_bio')) else None,
        'artist_nationality': row.get('artist_nationality') if pd.notna(row.get('artist_nationality')) else None,
        'artist_gender': row.get('artist_gender') if pd.notna(row.get('artist_gender')) else None,
        'culture': row.get('culture') if pd.notna(row.get('culture')) else None,
        'period': row.get('period') if pd.notna(row.get('period')) else None,
        'dynasty': row.get('dynasty') if pd.notna(row.get('dynasty')) else None,
        'medium': row.get('medium') if pd.notna(row.get('medium')) else None,
        'dimensions': row.get('dimensions') if pd.notna(row.get('dimensions')) else None,
        'department': row.get('department') if pd.notna(row.get('department')) else None,
        'classification': row.get('classification') if pd.notna(row.get('classification')) else None,
        'primary_image': row.get('primary_image') if pd.notna(row.get('primary_image')) else None,
        'is_public_domain': bool(row.get('is_public_domain', False)),
        'constituents': row.get('constituents') if pd.notna(row.get('constituents')) else None,
        'synced_at': datetime.utcnow(),
    }


def process_batch(db, batch, batch_num, operation_type, stats, stats_key):
    """
    Process a single batch of records with error handling.

    This helper function handles the common batch processing pattern
    for both insert and update operations.

    Args:
        db: Database session
        batch (list): List of records to process
        batch_num (int): Batch number (for logging)
        operation_type (str): 'insert' or 'update'
        stats (dict): Statistics dictionary to update
        stats_key (str): Key in stats dict to increment ('inserted' or 'updated')

    Returns:
        bool: True if successful, False if error occurred
    """
    try:
        if operation_type == 'insert':
            db.bulk_insert_mappings(Artwork, batch)
            print(f"  ✓ Inserted batch {batch_num}: {len(batch)} artworks")
        elif operation_type == 'update':
            db.bulk_update_mappings(Artwork, batch)
            print(f"  ✓ Updated batch {batch_num}: {len(batch)} artworks")

        stats[stats_key] += len(batch)
        return True
    except Exception as e:
        stats['errors'] += len(batch)
        operation_name = 'inserting' if operation_type == 'insert' else 'updating'
        print(f"  ✗ Error {operation_name} batch {batch_num}: {e}")
        return False


def save_to_database(df):
    """
    Save artwork data from DataFrame to PostgreSQL database using bulk operations.

    This function is optimized for performance by:
    1. Checking which records already exist in one query
    2. Splitting new records from existing ones
    3. Using bulk insert and bulk update operations
    4. Processing in batches to avoid memory issues

    Args:
        df (pandas.DataFrame): DataFrame containing cleaned artwork data

    Returns:
        dict: Statistics about the save operation (inserted, updated, errors)
    """
    print("\n" + "="*60)
    print("SAVING DATA TO DATABASE")
    print("="*60)

    stats = {
        'inserted': 0,
        'updated': 0,
        'errors': 0,
        'skipped': 0
    }

    if len(df) == 0:
        print("No data to save")
        return stats

    try:
        with get_db_session() as db:
            print(f"\nStep 1: Checking which artworks already exist...")
            met_object_ids = [int(x) for x in df['met_object_id'].tolist()]

            existing_ids = set(
                db.query(Artwork.met_object_id)
                .filter(Artwork.met_object_id.in_(met_object_ids))
                .all()
            )
            existing_ids = {id_tuple[0] for id_tuple in existing_ids}

            print(f"  Found {len(existing_ids)} existing artworks out of {len(met_object_ids)} total")

            print(f"\nStep 2: Preparing data for database...")
            new_records = []
            update_records = []

            for idx, row in df.iterrows():
                try:
                    artwork_data = prepare_artwork_data(row)
                    met_object_id = artwork_data['met_object_id']

                    if met_object_id in existing_ids:
                        artwork_data['updated_at'] = datetime.utcnow()
                        update_records.append(artwork_data)
                    else:
                        artwork_data['created_at'] = datetime.utcnow()
                        artwork_data['updated_at'] = datetime.utcnow()
                        new_records.append(artwork_data)

                except Exception as e:
                    stats['errors'] += 1
                    print(f"  ✗ Error preparing row {idx}: {e}")

            print(f"  Prepared {len(new_records)} new records and {len(update_records)} records to update")

            batch_size = 500

            if new_records:
                print(f"\nStep 3: Bulk inserting {len(new_records)} new artworks...")
                for i in range(0, len(new_records), batch_size):
                    batch = new_records[i:i + batch_size]
                    batch_num = i//batch_size + 1
                    process_batch(db, batch, batch_num, 'insert', stats, 'inserted')

            if update_records:
                print(f"\nStep 4: Bulk updating {len(update_records)} existing artworks...")
                met_id_to_db_id = {
                    met_id: db_id for met_id, db_id in
                    db.query(Artwork.met_object_id, Artwork.id)
                    .filter(Artwork.met_object_id.in_([r['met_object_id'] for r in update_records]))
                    .all()
                }

                for record in update_records:
                    record['id'] = met_id_to_db_id.get(record['met_object_id'])

                for i in range(0, len(update_records), batch_size):
                    batch = update_records[i:i + batch_size]
                    batch_num = i//batch_size + 1
                    process_batch(db, batch, batch_num, 'update', stats, 'updated')

            print(f"\nStep 5: Committing changes to database...")
            db.commit()
            print("  ✓ All changes committed successfully")

        print(f"\n{'='*60}")
        print("DATABASE SAVE COMPLETE")
        print("="*60)
        print(f"Inserted: {stats['inserted']} artworks")
        print(f"Updated: {stats['updated']} artworks")
        print(f"Errors: {stats['errors']} artworks")
        print(f"Total processed: {stats['inserted'] + stats['updated']} artworks")

        return stats

    except Exception as e:
        print(f"\n✗ Failed to save to database: {e}")
        import traceback
        traceback.print_exc()
        stats['errors'] = len(df)
        return stats

