import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import json

# API base URL
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

# Rate limiting settings
MAX_CONCURRENT_REQUESTS = 5  # how many requests at the same time
DELAY_BETWEEN_REQUESTS = 0.3  # seconds to wait between requests


class RateLimiter:
    """
    Simple rate limiter to avoid overwhelming the API
    This makes sure we don't send too many requests at once
    """
    def __init__(self, max_concurrent, delay):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.delay = delay
        self.last_request_time = 0

    async def acquire(self):
        """Wait until we're allowed to make another request"""
        await self.semaphore.acquire()

        # make sure we wait enough time since last request
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            await asyncio.sleep(self.delay - time_since_last)

        self.last_request_time = asyncio.get_event_loop().time()

    def release(self):
        """Release the semaphore so another request can go"""
        self.semaphore.release()


async def get_object_ids(session, department_id, rate_limiter):
    """
    Get list of object IDs for a specific department
    This only gets the IDs, not the full details yet
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
    Get full details for a single object
    This is where we get all the info about the artwork
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
    Fetch objects for one department
    This gets the IDs first, then fetches all the details in parallel
    """
    print(f"\n{'='*60}")
    print(f"Starting to process Department {department_id}")
    print('='*60)

    # step 1: get the list of object IDs
    object_ids = await get_object_ids(session, department_id, rate_limiter)

    # limit how many we fetch
    object_ids = object_ids[:limit]

    print(f"Will fetch details for {len(object_ids)} objects from department {department_id}")

    # step 2: fetch all object details in parallel
    # this is the magic part - we fetch multiple objects at the same time!
    tasks = []
    for obj_id in object_ids:
        task = get_object_details(session, obj_id, rate_limiter)
        tasks.append(task)

    # wait for all the tasks to complete
    results = await asyncio.gather(*tasks)

    # step 3: extract the data we want from each object
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
    Main function that fetches objects from all departments in parallel
    Each department is processed at the same time for maximum speed
    """
    # create a rate limiter that all requests will share
    rate_limiter = RateLimiter(MAX_CONCURRENT_REQUESTS, DELAY_BETWEEN_REQUESTS)

    # create an HTTP session that will be reused for all requests
    async with aiohttp.ClientSession() as session:
        # create a task for each department
        # these will all run at the same time!
        tasks = []
        for dept_id in department_ids:
            task = fetch_department_objects(session, dept_id, limit_per_department, rate_limiter)
            tasks.append(task)

        # wait for all departments to finish
        results = await asyncio.gather(*tasks)

        # combine all the objects from all departments into one list
        all_objects = []
        for dept_objects in results:
            all_objects.extend(dept_objects)

        return all_objects


def fetch_museum_data(department_ids, limit_per_department=20):
    """
    This is the main function you call to get the data
    It sets up everything and runs the async code
    """
    print("Starting to fetch museum data...")
    print(f"Departments: {department_ids}")
    print(f"Objects per department: {limit_per_department}")
    print(f"Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    print(f"Delay between requests: {DELAY_BETWEEN_REQUESTS} seconds")

    # run the async code
    # this is the special syntax needed to start async functions
    all_objects = asyncio.run(fetch_all_departments(department_ids, limit_per_department))

    # convert to dataframe
    df = pd.DataFrame(all_objects)

    # add id column
    df.insert(0, 'id', range(1, len(df) + 1))

    # add timestamps
    current_time = pd.Timestamp.now()
    df['created_at'] = current_time
    df['updated_at'] = current_time

    print(f"\n{'='*60}")
    print(f"ALL DONE! Fetched {len(df)} objects total")
    print('='*60)

    return df


# main code that runs when you execute the script
if __name__ == "__main__":
    # Department IDs:
    # 1 = American Decorative Arts
    # 11 = European Paintings

    department_ids = [1, 11]

    # fetch the data - this will get 20 objects from EACH department
    df = fetch_museum_data(department_ids, limit_per_department=20)

    # show some stats
    print("\n" + "="*60)
    print("DATASET OVERVIEW")
    print("="*60)
    print(f"Total objects: {len(df)}")
    print(f"\nDepartments represented:")
    print(df["department"].value_counts())

    # show first few rows
    print("\n" + "="*60)
    print("SAMPLE DATA")
    print("="*60)
    print(df[["id", "met_object_id", "title", "artist_display_name", "object_date", "department"]].head(10))

    # save to CSV
    df.to_csv("../data/met_museum_highlights.csv", index=False)
    print("\nData saved to 'met_museum_highlights.csv'")
