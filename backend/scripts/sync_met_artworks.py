import asyncio
import aiohttp
import pandas as pd
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database.database import get_db_session, init_db, engine
from database.models import Artwork
from datetime import datetime
from sqlalchemy import text

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
MAX_CONCURRENT_REQUESTS = 5
DELAY_BETWEEN_REQUESTS = 0.3


class RateLimiter:
    """
    Rate limiter to control concurrent API requests and prevent API overload.

    Uses a semaphore to limit concurrent requests and enforces a minimum delay
    between requests to respect API rate limits.

    Attributes:
        semaphore (asyncio.Semaphore): Semaphore controlling max concurrent requests
        delay (float): Minimum seconds to wait between requests
        last_request_time (float): Timestamp of the last request
    """
    def __init__(self, max_concurrent, delay):
        """
        Initialize the rate limiter.

        Args:
            max_concurrent (int): Maximum number of concurrent requests allowed
            delay (float): Minimum delay in seconds between requests
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.delay = delay
        self.last_request_time = 0

    async def acquire(self):
        """
        Acquire permission to make a request.

        Waits for semaphore availability and enforces delay between requests.
        Must be called before making an API request.
        """
        await self.semaphore.acquire()

        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            await asyncio.sleep(self.delay - time_since_last)

        self.last_request_time = asyncio.get_event_loop().time()

    def release(self):
        """
        Release the semaphore after a request completes.

        Must be called after an API request finishes to allow the next request.
        """
        self.semaphore.release()


async def get_object_ids(session, department_id, rate_limiter):
    """
    Fetch list of object IDs for a specific department from MET API.

    Retrieves only the object IDs (not full details) for highlighted objects
    in the specified department.

    Args:
        session (aiohttp.ClientSession): HTTP session for making requests
        department_id (int): Department ID to fetch objects from
        rate_limiter (RateLimiter): Rate limiter instance to control request rate

    Returns:
        list: List of object IDs (integers) for highlighted objects in the department.
              Returns empty list on error.
    """
    url = f"{BASE_URL}/objects"
    params = {
        "departmentIds": str(department_id),
        "isHighlight": "true"
    }

    await rate_limiter.acquire()
    try:
        async with session.get(url, params=params) as response:
            data = await response.json()
            object_ids = data.get("objectIDs", [])
            print(f"Department {department_id}: Found {len(object_ids)} highlighted objects")
            return object_ids
    except Exception as e:
        print(f"Error getting object IDs for department {department_id}: {e}")
        return []
    finally:
        rate_limiter.release()


async def get_object_details(session, object_id, rate_limiter):
    """
    Fetch full details for a single artwork object from MET API.

    Retrieves complete metadata for an artwork including title, artist,
    dates, culture, medium, dimensions, and other attributes.

    Args:
        session (aiohttp.ClientSession): HTTP session for making requests
        object_id (int): MET object ID to fetch details for
        rate_limiter (RateLimiter): Rate limiter instance to control request rate

    Returns:
        dict: Complete object data dictionary from API, or None on error
    """
    url = f"{BASE_URL}/objects/{object_id}"

    await rate_limiter.acquire()
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                print(f"Failed to fetch object {object_id}: status {response.status}")
                return None
    except Exception as e:
        print(f"Error fetching object {object_id}: {e}")
        return None
    finally:
        rate_limiter.release()


async def fetch_department_objects(session, department_id, limit, rate_limiter):
    """
    Fetch all objects for a single department in parallel.

    First retrieves object IDs for the department, then fetches full details
    for each object concurrently using asyncio.gather(). Extracts and structures
    the relevant fields from each object's metadata.

    Args:
        session (aiohttp.ClientSession): HTTP session for making requests
        department_id (int): Department ID to fetch objects from
        limit (int): Maximum number of objects to fetch from this department
        rate_limiter (RateLimiter): Rate limiter instance to control request rate

    Returns:
        list: List of dictionaries, each containing extracted artwork data fields
    """
    print(f"\n{'='*60}")
    print(f"Starting to process Department {department_id}")
    print('='*60)

    object_ids = await get_object_ids(session, department_id, rate_limiter)
    object_ids = object_ids[:limit]

    print(f"Will fetch details for {len(object_ids)} objects from department {department_id}")

    tasks = []
    for obj_id in object_ids:
        task = get_object_details(session, obj_id, rate_limiter)
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    objects_data = []
    for obj_details in results:
        if obj_details:
            obj_info = {
                "met_object_id": obj_details.get("objectID"),
                "title": obj_details.get("title"),
                "artist_display_name": obj_details.get("artistDisplayName"),
                "artist_display_bio": obj_details.get("artistDisplayBio"),
                "artist_nationality": obj_details.get("artistNationality"),
                "artist_gender": obj_details.get("artistGender"),
                "object_date": obj_details.get("objectDate"),
                "object_begin_date": obj_details.get("objectBeginDate"),
                "object_end_date": obj_details.get("objectEndDate"),
                "culture": obj_details.get("culture"),
                "period": obj_details.get("period"),
                "dynasty": obj_details.get("dynasty"),
                "medium": obj_details.get("medium"),
                "dimensions": obj_details.get("dimensions"),
                "department": obj_details.get("department"),
                "classification": obj_details.get("classification"),
                "object_name": obj_details.get("objectName"),
                "primary_image": obj_details.get("primaryImage"),
                "is_public_domain": obj_details.get("isPublicDomain", False),
                "constituents": obj_details.get("constituents"),
                "synced_at": pd.Timestamp.now()
            }
            objects_data.append(obj_info)

    print(f"Successfully fetched {len(objects_data)} objects from department {department_id}")
    return objects_data


async def fetch_all_departments(department_ids, limit_per_department):
    """
    Fetch objects from multiple departments concurrently.

    Processes all departments in parallel, with objects within each department
    also fetched in parallel. Uses a shared rate limiter across all requests
    to prevent API overload.

    Args:
        department_ids (list): List of department IDs to fetch objects from
        limit_per_department (int): Maximum number of objects to fetch per department

    Returns:
        list: Combined list of all artwork dictionaries from all departments
    """
    rate_limiter = RateLimiter(MAX_CONCURRENT_REQUESTS, DELAY_BETWEEN_REQUESTS)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for dept_id in department_ids:
            task = fetch_department_objects(session, dept_id, limit_per_department, rate_limiter)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        all_objects = []
        for dept_objects in results:
            all_objects.extend(dept_objects)

        return all_objects


def clean_and_validate_data(df):
    """
    Clean and validate artwork data before saving.

    Performs comprehensive data cleaning including:
    - Deduplication by met_object_id
    - String normalization (trimming, encoding)
    - Null/empty value handling
    - Date field validation
    - Final validation checks

    Args:
        df (pandas.DataFrame): DataFrame containing raw artwork data

    Returns:
        pandas.DataFrame: Cleaned and validated DataFrame ready for storage
    """
    print("\n" + "="*60)
    print("STARTING DATA CLEANING AND VALIDATION")
    print("="*60)

    initial_count = len(df)
    print(f"Initial record count: {initial_count}")

    print("\n1. Checking for duplicates...")
    duplicates = df[df.duplicated(subset=['met_object_id'], keep=False)]
    if len(duplicates) > 0:
        print(f"   WARNING: Found {len(duplicates)} duplicate met_object_id entries")
        print(f"   Duplicate IDs: {duplicates['met_object_id'].unique().tolist()}")
        df = df.drop_duplicates(subset=['met_object_id'], keep='first')
        print(f"   Kept first occurrence, removed {initial_count - len(df)} duplicates")
    else:
        print("   ✓ No duplicates found")

    print("\n2. Normalizing string fields...")
    string_fields = [
        'title', 'artist_display_name', 'artist_display_bio',
        'artist_nationality', 'artist_gender', 'object_date', 'culture', 'period',
        'dynasty', 'medium', 'dimensions', 'department', 'classification',
        'object_name', 'object_url'
    ]

    for field in string_fields:
        if field in df.columns:
            df[field] = df[field].apply(lambda x: None if x == '' else x)
            df[field] = df[field].apply(lambda x: x.strip() if isinstance(x, str) else x)
            df[field] = df[field].apply(
                lambda x: x.encode('utf-8').decode('utf-8') if isinstance(x, str) else x
            )

    print("   ✓ Trimmed whitespace and normalized encoding for all string fields")

    print("\n3. Handling null and empty values...")
    null_counts_before = df.isnull().sum()

    df = df.replace('', None)
    df = df.replace('nan', None)

    null_counts_after = df.isnull().sum()
    fields_with_nulls = null_counts_after[null_counts_after > 0]

    if len(fields_with_nulls) > 0:
        print("   Fields with null values:")
        for field, count in fields_with_nulls.items():
            print(f"   - {field}: {count} nulls ({count/len(df)*100:.1f}%)")
    else:
        print("   ✓ No null values found")

    print("\n4. Validating date fields...")
    date_issues = 0

    for idx, row in df.iterrows():
        begin_date = row['object_begin_date']
        end_date = row['object_end_date']

        if pd.notna(begin_date):
            try:
                begin_date = int(begin_date)
                df.at[idx, 'object_begin_date'] = begin_date
            except (ValueError, TypeError):
                print(f"   WARNING: Invalid begin_date for object {row['met_object_id']}: {begin_date}")
                df.at[idx, 'object_begin_date'] = None
                date_issues += 1

        if pd.notna(end_date):
            try:
                end_date = int(end_date)
                df.at[idx, 'object_end_date'] = end_date
            except (ValueError, TypeError):
                print(f"   WARNING: Invalid end_date for object {row['met_object_id']}: {end_date}")
                df.at[idx, 'object_end_date'] = None
                date_issues += 1

        if pd.notna(begin_date) and pd.notna(end_date):
            if begin_date > end_date:
                print(f"   WARNING: object {row['met_object_id']} has begin_date ({begin_date}) > end_date ({end_date})")
                date_issues += 1

        if begin_date == 0:
            df.at[idx, 'object_begin_date'] = None
        if end_date == 0:
            df.at[idx, 'object_end_date'] = None

    if date_issues == 0:
        print("   ✓ All dates validated successfully")
    else:
        print(f"   Found {date_issues} date validation issues (see warnings above)")

    print("\n6. Final validation...")
    null_ids = df['met_object_id'].isnull().sum()
    if null_ids > 0:
        print(f"   ERROR: Found {null_ids} records with null met_object_id - removing them")
        df = df[df['met_object_id'].notna()]
    else:
        print("   ✓ All records have valid met_object_id")

    df['is_public_domain'] = df['is_public_domain'].fillna(False).astype(bool)

    final_count = len(df)
    print(f"\n{'='*60}")
    print("DATA CLEANING COMPLETE")
    print("="*60)
    print(f"Final record count: {final_count}")
    print(f"Records removed: {initial_count - final_count}")

    return df


def fetch_museum_data(department_ids, limit_per_department=20):
    """
    Main entry point for fetching museum artwork data.

    Orchestrates the async data fetching process, converts results to DataFrame,
    and adds metadata columns (id, created_at, updated_at).

    Args:
        department_ids (list): List of department IDs to fetch objects from
        limit_per_department (int, optional): Maximum objects per department. Defaults to 20.

    Returns:
        pandas.DataFrame: DataFrame containing fetched artwork data with id and timestamp columns
    """
    print("Starting to fetch museum data...")
    print(f"Departments: {department_ids}")
    print(f"Objects per department: {limit_per_department}")
    print(f"Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    print(f"Delay between requests: {DELAY_BETWEEN_REQUESTS} seconds")

    all_objects = asyncio.run(fetch_all_departments(department_ids, limit_per_department))

    df = pd.DataFrame(all_objects)

    current_time = pd.Timestamp.now()
    df['created_at'] = current_time
    df['updated_at'] = current_time

    print(f"\n{'='*60}")
    print(f"ALL DONE! Fetched {len(df)} objects total")
    print('='*60)

    return df


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
            current_time = datetime.utcnow()

            if new_records:
                print(f"\nStep 3: Bulk inserting {len(new_records)} new artworks...")
                for i in range(0, len(new_records), batch_size):
                    batch = new_records[i:i + batch_size]
                    try:
                        db.bulk_insert_mappings(Artwork, batch)
                        stats['inserted'] += len(batch)
                        print(f"  ✓ Inserted batch {i//batch_size + 1}: {len(batch)} artworks")
                    except Exception as e:
                        stats['errors'] += len(batch)
                        print(f"  ✗ Error inserting batch {i//batch_size + 1}: {e}")

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
                    try:
                        db.bulk_update_mappings(Artwork, batch)
                        stats['updated'] += len(batch)
                        print(f"  ✓ Updated batch {i//batch_size + 1}: {len(batch)} artworks")
                    except Exception as e:
                        stats['errors'] += len(batch)
                        print(f"  ✗ Error updating batch {i//batch_size + 1}: {e}")

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
