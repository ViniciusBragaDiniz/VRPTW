"""Student data preprocessing for the VRPTW.

Responsible for loading, cleaning, enriching, and geocoding student data.
The pipeline includes:

1. Loading student CSVs (technical and undergraduate levels).
2. Filtering valid zip codes (state of Rio de Janeiro).
3. Address enrichment via ViaCEP API.
4. Geocoding via Google Maps Geocoding API.
5. City/neighborhood name standardization.
6. Merge with shift data by course.

.. note::
    This module **does not write to disk**. The main function returns the
    processed DataFrames and persistence is the caller's responsibility
    (``run_pipeline.py`` or ``src/01_preprocess_data.py``), ensuring
    pipeline idempotency.

Prerequisites:
    - A ``secrets`` file at the project root with ``GOOGLEMAPS_APIKEY=<key>``.
    - Input files in ``data/raw/``.

Usage example:
    >>> from data.preprocessing import preprocess_student_data
    >>> results = preprocess_student_data()
    >>> results["info_students"].head()
"""

import logging
import os
import unicodedata
from time import sleep

import googlemaps
import pandas as pd
import requests
import glob

from vrptw.config import DATA_PROCESSED_DIR, DATA_RAW_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_full_address(row: pd.Series) -> str:
    """Build a full address from individual fields.

    Concatenates non-empty fields and appends "Rio de Janeiro, Brasil".

    Args:
        row: Series with address fields (STREET_NAME, NEIGHBORHOOD, CITY, etc.).

    Returns:
        Formatted full address as a string.
    """
    parts = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
    parts.extend(["Rio de Janeiro", "Brasil"])
    return ", ".join(parts)


def _remove_accents(text: str) -> str:
    """Remove accents from text using Unicode NFD decomposition.

    Args:
        text: Text with possible accents.

    Returns:
        Text without accents.
    """
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _load_api_key() -> str:
    """Load the Google Maps API key from the ``secrets`` file.

    The file must have the format ``KEY=VALUE`` (one per line).

    Returns:
        Google Maps API key.

    Raises:
        FileNotFoundError: If the ``secrets`` file does not exist.
        KeyError: If ``GOOGLEMAPS_APIKEY`` is not defined.
    """
    secrets_path = PROJECT_ROOT / "secrets"
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Secrets file not found: {secrets_path}. "
            "Create a 'secrets' file with the line GOOGLEMAPS_APIKEY=<your_key>."
        )

    with open(secrets_path, "r") as f:
        for line in f.read().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

    api_key = os.getenv("GOOGLEMAPS_APIKEY")
    if not api_key:
        raise KeyError("GOOGLEMAPS_APIKEY not found in the 'secrets' file.")
    return api_key


# ---------------------------------------------------------------------------
# Address enrichment via ViaCEP
# ---------------------------------------------------------------------------

def _enrich_addresses_viacep(df: pd.DataFrame) -> int:
    """Fill missing STREET_NAME and ADDRESS_COMPLEMENT using the ViaCEP API.

    Args:
        df: Student DataFrame (modified in-place).

    Returns:
        Number of zip codes not found.
    """
    missing_idx = df.loc[df["STREET_NAME"] == ""].index
    not_found = 0

    for idx in missing_idx:
        POSTAL_CODE = df.loc[idx, "POSTAL_CODE"]
        url = f"https://viacep.com.br/ws/{POSTAL_CODE}/json/"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                df.loc[idx, "STREET_NAME"] = data.get("logradouro", "").upper()
                df.loc[idx, "ADDRESS_COMPLEMENT"] = data.get("complemento", "").upper()
            else:
                logger.warning("Zip code %s: HTTP %d", POSTAL_CODE, response.status_code)
                not_found += 1
        except Exception as e:
            logger.error("Error querying zip code %s: %s", POSTAL_CODE, e)
            not_found += 1
        sleep(2)

    return not_found


# ---------------------------------------------------------------------------
# Recover coordinates from previous runs
# ---------------------------------------------------------------------------

def _load_existing_coordinates(df: pd.DataFrame) -> int:
    """Pre-fill LATITUDE/LONGITUDE from previously processed output files.

    Scans ``data/processed/info/info_*.csv`` for already-geocoded students
    and copies their coordinates into *df*, keyed by ``STUDENT_ID``.
    This avoids redundant Google Maps API calls on re-runs.

    Args:
        df: Student DataFrame (modified in-place).

    Returns:
        Number of students whose coordinates were recovered.
    """
    processed_info_dir = DATA_PROCESSED_DIR / "info"
    if not processed_info_dir.exists():
        return 0

    parts: list[pd.DataFrame] = []
    for path in processed_info_dir.glob("info_*.csv"):
        try:
            parts.append(
                pd.read_csv(path, usecols=["STUDENT_ID", "LATITUDE", "LONGITUDE"])
            )
        except (ValueError, KeyError):
            continue

    if not parts:
        return 0

    existing = pd.concat(parts, ignore_index=True).drop_duplicates(subset="STUDENT_ID")
    valid = (existing["LATITUDE"] != 0) & (existing["LONGITUDE"] != 0)
    lookup = existing.loc[valid].set_index("STUDENT_ID")

    needs_geocoding = df["LATITUDE"] == 0
    known = needs_geocoding & df["STUDENT_ID"].isin(lookup.index)
    if known.sum() == 0:
        return 0

    sids = df.loc[known, "STUDENT_ID"]
    df.loc[known, "LATITUDE"] = sids.map(lookup["LATITUDE"]).values
    df.loc[known, "LONGITUDE"] = sids.map(lookup["LONGITUDE"]).values

    return int(known.sum())


# ---------------------------------------------------------------------------
# Geocoding via Google Maps
# ---------------------------------------------------------------------------

def _geocode_students(df: pd.DataFrame, gmaps_client: googlemaps.Client) -> None:
    """Obtain latitude/longitude for students still without geolocation.

    Only students whose ``LATITUDE`` is 0 (i.e. not recovered from a
    previous run) will trigger an API request.

    Args:
        df: Student DataFrame (modified in-place). Must contain the column
            ``FULL_ADDRESS`` and the columns ``LATITUDE`` / ``LONGITUDE``.
        gmaps_client: Authenticated Google Maps API client.
    """
    missing_idx = df[df["LATITUDE"] == 0].index
    api_calls = 0

    for i in missing_idx:
        address = df.loc[i, "FULL_ADDRESS"]

        try:
            result = gmaps_client.geocode(address)
            if result:
                location = result[0]["geometry"]["location"]
                df.loc[i, "LATITUDE"] = location["lat"]
                df.loc[i, "LONGITUDE"] = location["lng"]
            else:
                logger.warning("Geocoding returned no result for: %s", address)
        except Exception as e:
            logger.error("Geocoding error at index %d: %s", i, e)

        api_calls += 1
        if api_calls % 50 == 0:
            logger.info("Geocoding API calls so far: %d", api_calls)

    logger.info("Geocoding done — %d API calls made", api_calls)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def preprocess_student_data() -> dict[str, pd.DataFrame]:
    """Execute the full student data preprocessing pipeline.

    Loads raw data, enriches addresses, geocodes, standardizes names
    and returns the results. **Does not write to disk** — persistence
    is the caller's responsibility, ensuring pipeline idempotency.

    Returns:
        Dictionary with three DataFrames:
            - ``"info_students"``: all processed students;
            - ``"info_tec"``: technical-level students only;
            - ``"info_undergrad"``: undergraduate students only.
    """
    logger.info("Starting student data preprocessing")

    shift_files = glob.glob(str(DATA_RAW_DIR / "shifts" / "*.csv"))
    df_shifts_list = [pd.read_csv(f) for f in shift_files]
    df_shifts = pd.concat(df_shifts_list, ignore_index=True)

    shift_map_path = DATA_RAW_DIR / "aux" / "shift_map.csv"
    df_shift_map = pd.read_csv(shift_map_path)
    df_shifts = df_shifts.merge(df_shift_map, how="left", on=["COURSE","CURRENT_PERIOD","DAYOFTHEWEEK","ENTRY_SHIFT"])

    # --- Load and unify student data ---
    df_tec = pd.read_csv(DATA_RAW_DIR / "info" / "info_tec.csv")
    df_tec["STUDENT_ID"] = "tec_" + df_tec.index.astype(str)

    df_undergrad = pd.read_csv(DATA_RAW_DIR / "info" / "info_undergrad.csv")
    df_undergrad["STUDENT_ID"] = "undergrad_" + df_undergrad.index.astype(str)

    df = pd.concat([df_tec, df_undergrad], ignore_index=True)

    # --- Filter Rio de Janeiro zip codes (start with '2') ---
    valid_ceps = df["POSTAL_CODE"].apply(lambda x: str(x)[0] == "2")
    logger.info("Invalid zip codes (outside RJ): %d", len(df) - valid_ceps.sum())
    df = df.loc[valid_ceps].reset_index(drop=True)

    # --- Initialize columns to avoid errors on reprocessing ---
    for col, default in [("ADDRESS_COMPLEMENT", ""), ("STREET_NAME", ""),
                         ("LONGITUDE", 0.0), ("LATITUDE", 0.0)]:
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default)

    # --- Recover coordinates from previous output files ---
    recovered = _load_existing_coordinates(df)
    logger.info("Coordinates recovered from previous runs: %d students", recovered)

    # --- Enrich addresses via ViaCEP ---
    not_found = _enrich_addresses_viacep(df)
    logger.info("Zip codes not found in ViaCEP: %d", not_found)

    # --- Geocoding (only students still without coordinates) ---
    address_cols = ["STREET_NAME", "NEIGHBORHOOD", "CITY", "POSTAL_CODE", "ADDRESS_COMPLEMENT"]
    df["FULL_ADDRESS"] = df[address_cols].apply(_build_full_address, axis=1)

    still_missing = (df["LATITUDE"] == 0).sum()
    if still_missing > 0:
        logger.info("Students still needing geocoding: %d", still_missing)
        api_key = _load_api_key()
        gmaps_client = googlemaps.Client(key=api_key)
        _geocode_students(df, gmaps_client)
    else:
        logger.info("All students already geocoded — skipping Google Maps API")

    # --- Name standardization ---
    df["CITY"] = df["CITY"].apply(lambda x: _remove_accents(x).title())
    df["NEIGHBORHOOD"] = df["NEIGHBORHOOD"].apply(lambda x: _remove_accents(x).title())

    # --- Merge with shifts ---
    df = df_shifts.merge(df, how="left", on=["COURSE", "CURRENT_PERIOD"])

    # Split by level
    df_tec = df[df["STUDENT_ID"].str.contains("tec")].drop_duplicates(subset="STUDENT_ID")
    df_undergrad = df[df["STUDENT_ID"].str.contains("undergrad")].drop_duplicates(subset="STUDENT_ID")

    logger.info("Preprocessing complete. %d students processed.", len(df))
    return {
        "info_students": df,
        "info_tec": df_tec,
        "info_undergrad": df_undergrad,
    }
