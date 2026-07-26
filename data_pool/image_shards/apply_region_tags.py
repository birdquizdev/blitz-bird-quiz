import json
import time
from pathlib import Path
import urllib.request
import urllib.error
import ssl

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Replace with your actual eBird API key
EBIRD_API_KEY = "20etk6q5ol1a"

PROJECT_ROOT = Path.home() / "blitz-bird-quiz"
SHARDS_DIR = PROJECT_ROOT / "data_pool" / "image_shards_updated"
MASTER_FILE = PROJECT_ROOT / "master_species_directory_updated.json"

# Local region index file
REGION_INDEX_FILE = Path.home() / "Downloads" / "region_index.json"

# Headers required for eBird API v2
HEADERS = {
    "X-eBirdApiToken": EBIRD_API_KEY,
    "User-Agent": "BlitzBirdQuizApp/1.0"
}

# ---------------------------------------------------------
# 1. Load Local Region Index & Master Code Aliases
# ---------------------------------------------------------

print(f"Loading region index from:\n  {REGION_INDEX_FILE}\n")
with open(REGION_INDEX_FILE, "r", encoding="utf-8") as f:
    region_index = json.load(f)

# Ensure California is in our targets dictionary even if not explicitly top-level in region_index
targets = dict(region_index)
if "US-CA" not in targets:
    targets["US-CA"] = {
        "code": "US-CA",
        "display_name": "California",
        "hierarchy": ["United States", "California"]
    }

# Load Master taxonomy to translate 4-letter alpha codes / common names to canonical eBird keys
alias_to_ebird = {}
if MASTER_FILE.exists():
    print(f"Loading master taxonomy directory from:\n  {MASTER_FILE}\n")
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master_data = json.load(f)
    for ebird_code, info in master_data.items():
        if isinstance(info, dict):
            e_code = ebird_code.lower().strip()
            alias_to_ebird[e_code] = e_code
            alpha = info.get("alpha_code")
            if alpha:
                alias_to_ebird[str(alpha).lower().strip()] = e_code

# ---------------------------------------------------------
# 2. Fetch Species Lists from eBird API
# ---------------------------------------------------------
# Create an SSL context that ignores certificate verification issues
ssl_context = ssl._create_unverified_context()
def get_region_species_list(region_code):
    """Fetches species code array for a given eBird region code (e.g. 'US', 'US-CA', 'CA')."""
    url = f"https://api.ebird.org/v2/product/spplist/{region_code}"
    req = urllib.request.Request(url, headers=HEADERS)
    
    try:
        # Pass context=ssl_context to urlopen
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] Failed for {region_code}")
        return []
    except Exception as e:
        print(f"  Error for {region_code}: {e}")
        return []

# Map: canonical_ebird_code -> set of region display names
species_region_map = {}

total_regions = len(targets)
print(f"Pulling species lists for {total_regions} regions (including California)...\n")

for i, (code, info) in enumerate(targets.items(), start=1):
    display_name = info.get("display_name", code)
    print(f"[{i}/{total_regions}] Fetching species for {display_name} ({code})...")
    
    spp_list = get_region_species_list(code)

    for raw_code in spp_list:
        clean_code = str(raw_code).lower().strip()
        # Resolve to canonical eBird code using master taxonomy alias table
        canonical_code = alias_to_ebird.get(clean_code, clean_code)
        
        species_region_map.setdefault(canonical_code, set()).add(display_name)

    # Polite delay between API calls
    time.sleep(0.1)

print(f"\nCompleted API calls! Mapped region tags for {len(species_region_map):,} unique species.\n")

# ---------------------------------------------------------
# 3. Apply Region Tags to Image Shards
# ---------------------------------------------------------

shard_files = list(SHARDS_DIR.glob("*.json"))
print(f"Applying region tags to {len(shard_files)} shard files in {SHARDS_DIR}...\n")

total_species_tagged = 0

for shard_file in shard_files:
    try:
        with open(shard_file, "r", encoding="utf-8") as f:
            shard_json = json.load(f)

        species_data = shard_json.get("data", {})
        file_updated = False

        for shard_species_code, info in species_data.items():
            canonical_code = alias_to_ebird.get(
                shard_species_code.lower().strip(),
                shard_species_code.lower().strip()
            )

            region_tags = species_region_map.get(canonical_code)

            if region_tags:
                existing_tags = info.get("practice_tags", [])
                combined_tags = list(existing_tags)

                for tag_name in sorted(region_tags):
                    if tag_name not in combined_tags:
                        combined_tags.append(tag_name)

                info["practice_tags"] = combined_tags
                file_updated = True
                total_species_tagged += 1

        if file_updated:
            with open(shard_file, "w", encoding="utf-8") as f:
                json.dump(shard_json, f, indent=2, ensure_ascii=False)
            print(f"Updated {shard_file.name}")

    except Exception as e:
        print(f"Error updating {shard_file.name}: {e}")

print()
print("=" * 45)
print("Region Tagging Complete!")
print(f"Total species updated across all shards: {total_species_tagged:,}")
print("=" * 45)