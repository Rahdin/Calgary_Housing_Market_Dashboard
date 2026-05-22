"""
feature_engineering.py
----------------------
Transform the raw Calgary residential listings export into a clean, modeled
dataset ready for Power BI / analytics.

Raw fields are unstructured (full address strings, an embedded country/province/
postal-code blob, free-text brokerage names). This script derives the analytical
dimensions used by the dashboard and writes a tidy CSV.

Usage:
    python feature_engineering.py \
        --input  Homes_for_Sale_and_Real_Estate.xlsx \
        --output Calgary_Listings_Modeled.csv

Requires: pandas, numpy, openpyxl
"""

from __future__ import annotations

import argparse
import re
import sys

import numpy as np
import pandas as pd

# Output column order (matches the Power BI semantic model)
COLUMN_ORDER = [
    "Address", "Price", "Neighbourhood", "Quadrant", "PostalArea", "Province",
    "PropertyType", "Beds", "Baths", "SqFt", "PricePerSqFt", "PriceTier",
    "BedBand", "Brokerage",
]

# Calgary postal codes start with T; the quadrant lives in the address suffix.
QUADRANT_RE = re.compile(r"\b(SW|SE|NW|NE)\b")
# Forward Sortation Area = first three chars of a Canadian postal code (e.g. T3E).
FSA_RE = re.compile(r"([A-Z]\d[A-Z])")


def derive_quadrant(address: str) -> str:
    """Extract the Calgary quadrant (SW/NW/SE/NE) from the address suffix."""
    match = QUADRANT_RE.search(str(address))
    return match.group(1) if match else "Other"


def derive_fsa(description: str) -> str:
    """Pull the postal Forward Sortation Area (e.g. 'T3E') from the geo blob."""
    match = FSA_RE.search(str(description))
    return match.group(1) if match else "Unknown"


def derive_property_type(address: str) -> str:
    """A unit number ('#') in the address indicates a condo/apartment."""
    return "Condo/Apt" if "#" in str(address) else "House/Town"


def derive_price_tier(price: float) -> str:
    """Bucket asking price into investment-friendly bands."""
    if price < 300_000:
        return "< $300K"
    if price < 500_000:
        return "$300K-500K"
    if price < 750_000:
        return "$500K-750K"
    if price < 1_000_000:
        return "$750K-1M"
    if price < 2_000_000:
        return "$1M-2M"
    return "$2M+"


def derive_bed_band(beds: int) -> str:
    """Collapse bedroom counts into a clean categorical axis."""
    if beds <= 1:
        return "1"
    if beds <= 4:
        return str(int(beds))
    return "5+"


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all cleaning and feature-engineering steps to the raw frame."""
    # Drop rows without a usable floor area (can't compute $/sq.ft).
    df = df[df["Sq.Ft"] > 0].copy()

    out = pd.DataFrame({
        "Address": df["Address"].astype(str),
        "Price": df["Price"].astype(int),
        "Neighbourhood": df["Place"].fillna("Unknown").astype(str).str.strip(),
        "Quadrant": df["Address"].apply(derive_quadrant),
        "PostalArea": df["Description"].apply(derive_fsa),
        "Province": "AB",
        "PropertyType": df["Address"].apply(derive_property_type),
        "Beds": df["Beds"].astype(int),
        "Baths": df["Bath"].astype(float),
        "SqFt": df["Sq.Ft"].astype(int),
        "Brokerage": df["Website"].fillna("Unknown").astype(str).str.strip(),
    })

    # Derived numeric / categorical features.
    out["PricePerSqFt"] = (out["Price"] / out["SqFt"]).round(0).astype(int)
    out["PriceTier"] = out["Price"].apply(derive_price_tier)
    out["BedBand"] = out["Beds"].apply(derive_bed_band)

    return out[COLUMN_ORDER]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", "-i", default="Homes_for_Sale_and_Real_Estate.xlsx",
                        help="Path to the raw Excel/CSV listings file.")
    parser.add_argument("--output", "-o", default="Calgary_Listings_Modeled.csv",
                        help="Path for the cleaned output CSV.")
    parser.add_argument("--sheet", default=0, help="Sheet name/index for Excel input.")
    args = parser.parse_args(argv)

    # Read raw data (supports .xlsx or .csv).
    if str(args.input).lower().endswith(".csv"):
        raw = pd.read_csv(args.input)
    else:
        raw = pd.read_excel(args.input, sheet_name=args.sheet)

    required = {"Address", "Price", "Description", "Place", "Beds", "Bath", "Sq.Ft", "Website"}
    missing = required - set(raw.columns)
    if missing:
        print(f"ERROR: input is missing expected columns: {sorted(missing)}", file=sys.stderr)
        return 1

    modeled = transform(raw)
    modeled.to_csv(args.output, index=False, encoding="utf-8")

    print(f"Wrote {len(modeled):,} rows x {modeled.shape[1]} columns -> {args.output}")
    print(f"  Neighbourhoods: {modeled['Neighbourhood'].nunique()} | "
          f"Brokerages: {modeled['Brokerage'].nunique()} | "
          f"Postal areas: {modeled['PostalArea'].nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
