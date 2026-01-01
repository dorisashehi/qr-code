import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import json

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

    df.insert(0, 'id', range(1, len(df) + 1))

    current_time = pd.Timestamp.now()
    df['created_at'] = current_time
    df['updated_at'] = current_time

    print(f"\n{'='*60}")
    print(f"ALL DONE! Fetched {len(df)} objects total")
    print('='*60)

    return df


if __name__ == "__main__":
    department_ids = [1, 11]

    df = fetch_museum_data(department_ids, limit_per_department=20)

    df = clean_and_validate_data(df)

    print("\n" + "="*60)
    print("DATASET OVERVIEW")
    print("="*60)
    print(f"Total objects: {len(df)}")
    print(f"\nDepartments represented:")
    print(df["department"].value_counts())

    print("\n" + "="*60)
    print("SAMPLE DATA")
    print("="*60)

    df.to_csv("../data/met_museum_highlights.csv", index=False)
    print("\nData saved to 'met_museum_highlights.csv'")
