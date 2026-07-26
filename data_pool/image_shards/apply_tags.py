import json
from pathlib import Path

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path.home() / "blitz-bird-quiz"

MASTER_FILE = PROJECT_ROOT / "master_species_directory_updated.json"
TAGS_TEMPLATE_FILE = Path.home() / "Downloads" / "species_tags_template.json"
SHARDS_DIR = PROJECT_ROOT / "data_pool" / "image_shards"

SAVE_IN_PLACE = False
OUTPUT_DIR = SHARDS_DIR if SAVE_IN_PLACE else PROJECT_ROOT / "data_pool" / "image_shards_updated"

# ---------------------------------------------------------
# 1. Build Master Code Alias Lookup
# ---------------------------------------------------------

print(f"Loading master taxonomy directory from:\n  {MASTER_FILE}\n")

with open(MASTER_FILE, "r", encoding="utf-8") as f:
    master_data = json.load(f)

# Maps any code (alpha_code, ebird_code, or cname) -> canonical ebird_code
# e.g., "colo" -> "comloo", "comloo" -> "comloo", "dcco" -> "doccor"
alias_to_ebird = {}

for ebird_code, info in master_data.items():
    if isinstance(info, dict):
        e_code = ebird_code.lower().strip()
        alias_to_ebird[e_code] = e_code

        alpha = info.get("alpha_code")
        if alpha:
            alias_to_ebird[str(alpha).lower().strip()] = e_code

        cname = info.get("common_name")
        if cname:
            alias_to_ebird[str(cname).lower().strip()] = e_code

# ---------------------------------------------------------
# 2. Invert Tag Template using Master Taxonomy
# ---------------------------------------------------------

print(f"Loading tags template from:\n  {TAGS_TEMPLATE_FILE}\n")

with open(TAGS_TEMPLATE_FILE, "r", encoding="utf-8") as f:
    tags_template = json.load(f)

# Maps resolved ebird_code -> [list_of_group_tags]
ebird_to_tags = {}

for group_tag, species_list in tags_template.items():
    if isinstance(species_list, list):
        for item in species_list:
            raw_code = item.get("code")
            raw_name = item.get("name")

            # Try resolving code first, then fall back to name lookup
            resolved_code = None
            if raw_code:
                resolved_code = alias_to_ebird.get(str(raw_code).lower().strip())
            
            if not resolved_code and raw_name:
                resolved_code = alias_to_ebird.get(str(raw_name).lower().strip())

            if resolved_code:
                ebird_to_tags.setdefault(resolved_code, set()).add(group_tag)

print(f"Mapped tags for {len(ebird_to_tags):,} unique species codes.")

# ---------------------------------------------------------
# 3. Process All Shard Files
# ---------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
shard_files = list(SHARDS_DIR.glob("*.json"))

print(f"Found {len(shard_files)} shard files in {SHARDS_DIR}\n")

total_species_tagged = 0

for shard_file in shard_files:
    try:
        with open(shard_file, "r", encoding="utf-8") as f:
            shard_json = json.load(f)

        species_data = shard_json.get("data", {})
        file_tagged_count = 0

        for shard_species_code, info in species_data.items():
            # Resolve the shard species key to canonical eBird code
            canonical_code = alias_to_ebird.get(shard_species_code.lower().strip(), shard_species_code.lower().strip())

            if canonical_code in ebird_to_tags:
                new_tags = ebird_to_tags[canonical_code]
                
                existing_tags = info.get("practice_tags", [])
                
                # Merge tags preventing duplicates
                combined_tags = list(existing_tags)
                for tag in new_tags:
                    if tag not in combined_tags:
                        combined_tags.append(tag)
                
                info["practice_tags"] = combined_tags
                file_tagged_count += 1

        total_species_tagged += file_tagged_count

        out_file_path = OUTPUT_DIR / shard_file.name
        with open(out_file_path, "w", encoding="utf-8") as f:
            json.dump(shard_json, f, indent=2, ensure_ascii=False)

        print(f"Updated {shard_file.name}: {file_tagged_count} species tagged.")

    except Exception as e:
        print(f"Error processing {shard_file.name}: {e}")

print()
print("=" * 45)
print(f"Tagging Complete!")
print(f"Total species tagged across all shards: {total_species_tagged:,}")
print(f"Output directory: {OUTPUT_DIR}")
print("=" * 45)