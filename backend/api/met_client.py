"""
MET Museum API client for fetching artwork data.

This module handles all interactions with the MET Museum Collection API,
including rate limiting, parallel fetching, and data extraction.
"""
import asyncio
import aiohttp
import pandas as pd

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


def fetch_museum_data(department_ids, limit_per_department=20):
    """
    Main entry point for fetching museum artwork data.

    Orchestrates the async data fetching process, converts results to DataFrame,
    and adds metadata columns (created_at, updated_at).

    Args:
        department_ids (list): List of department IDs to fetch objects from
        limit_per_department (int, optional): Maximum objects per department. Defaults to 20.

    Returns:
        pandas.DataFrame: DataFrame containing fetched artwork data with timestamp columns
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

