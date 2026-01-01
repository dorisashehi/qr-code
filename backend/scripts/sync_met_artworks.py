import requests
import pandas as pd
import time

# API base URL
BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

def get_object_ids(department_ids, is_highlight=True):
    """
    Get object IDs filtered by department and highlight status
    """
    # Convert department_ids list to pipe-separated string
    dept_param = "|".join(map(str, department_ids))

    url = f"{BASE_URL}/objects"
    params = {
        "departmentIds": dept_param,
        "isHighlight": str(is_highlight).lower()
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    return data.get("objectIDs", [])

def get_object_details(object_id):
    """
    Get detailed information for a specific object
    """
    url = f"{BASE_URL}/objects/{object_id}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching object {object_id}: {e}")
        return None

def fetch_museum_data(department_ids, limit_per_department=20):
    """
    Fetch highlighted objects from specified departments

    Parameters:
    - department_ids: list of department IDs (e.g., [1, 11])
    - limit_per_department: maximum number of objects to fetch PER department

    Returns:
    - DataFrame with object details
    """
    all_objects_data = []

    for dept_id in department_ids:
        print(f"\n{'='*60}")
        print(f"Processing Department ID: {dept_id}")
        print('='*60)

        print(f"Fetching object IDs for department {dept_id}...")
        object_ids = get_object_ids([dept_id], is_highlight=True)

        # Limit the number of objects to fetch for this department
        object_ids = object_ids[:limit_per_department]

        print(f"Found {len(object_ids)} highlighted objects. Fetching details...")

        for idx, obj_id in enumerate(object_ids, 1):
            print(f"  Fetching object {idx}/{len(object_ids)}: ID {obj_id}")

            obj_details = get_object_details(obj_id)

            if obj_details:
                # Extract all requested fields
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
                    "constituents": obj_details.get("constituents"),  # Will store as list
                    "synced_at": pd.Timestamp.now()
                }
                all_objects_data.append(obj_info)

            # Be respectful to the API - add a small delay
            time.sleep(0.5)

    # Create DataFrame
    df = pd.DataFrame(all_objects_data)

    # Add auto-increment id as index + 1
    df.insert(0, 'id', range(1, len(df) + 1))

    # Add created_at and updated_at timestamps
    current_time = pd.Timestamp.now()
    df['created_at'] = current_time
    df['updated_at'] = current_time

    print(f"\n{'='*60}")
    print(f"Successfully fetched {len(df)} objects total!")
    print('='*60)
    return df

# Example usage
if __name__ == "__main__":
    # Department IDs:
    # 1 = American Decorative Arts
    # 11 = European Paintings

    department_ids = [1, 11]

    # Fetch data - 20 objects PER department
    df = fetch_museum_data(department_ids, limit_per_department=20)

    # Display basic info
    print("\n" + "="*50)
    print("DATASET OVERVIEW")
    print("="*50)
    print(f"Total objects: {len(df)}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nDepartments represented:")
    print(df["department"].value_counts())

    # Display first few rows
    print("\n" + "="*50)
    print("SAMPLE DATA")
    print("="*50)
    print(df[["id", "met_object_id", "title", "artist_display_name", "object_date", "department"]].head(10))

    # Display data types
    print("\n" + "="*50)
    print("DATA TYPES")
    print("="*50)
    print(df.dtypes)

    # Save to CSV (optional)
    df.to_csv("../data/met_museum_highlights.csv", index=False)
    print("\nData saved to 'met_museum_highlights.csv'")
