"""
Data cleaning and validation utilities for artwork data.

This module provides functions to clean, validate, and normalize
artwork data before saving to the database.
"""
import pandas as pd


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

