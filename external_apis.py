import httpx
import json
import os
import asyncio
from typing import Dict, Any, Optional

CACHE_FILE = "species_cache.json"

def load_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, Any]):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)

species_cache = load_cache()

async def fetch_species_data(species_name: str) -> Optional[Dict[str, Any]]:
    """
    Chains iNaturalist, GBIF, and Wikipedia to get realistic species data.
    """
    if species_name.lower() in species_cache:
        return species_cache[species_name.lower()]

    headers = {"User-Agent": "NanoBotCivilization/1.0 (https://github.com/Next-ofkin/nanobot-civilization)"}

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        try:
            # 1. iNaturalist: Identify and get Scientific Name
            inat_url = f"https://api.inaturalist.org/v1/taxa?q={species_name}&rank=species"
            inat_resp = await client.get(inat_url)
            
            if inat_resp.status_code != 200:
                print(f"iNaturalist error {inat_resp.status_code} for {species_name}")
                return None
                
            inat_data = inat_resp.json()
            if not inat_data.get("results"):
                return None

            taxon = inat_data["results"][0]
            scientific_name = taxon["name"]
            common_name = taxon.get("preferred_common_name", species_name)
            taxon_id = taxon["id"]
            image_url = taxon.get("default_photo", {}).get("medium_url")

            # 2. Wikipedia: Behavioral Traits
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{scientific_name.replace(' ', '_')}"
            wiki_resp = await client.get(wiki_url)
            if wiki_resp.status_code == 200:
                wiki_data = wiki_resp.json()
                extract = wiki_data.get("extract", "").lower()
            else:
                extract = ""

            # 3. GBIF: Traits and Habitat
            gbif_match_url = f"https://api.gbif.org/v1/species/match?name={scientific_name}"
            gbif_match_resp = await client.get(gbif_match_url)
            gbif_match = gbif_match_resp.json()
            usage_key = gbif_match.get("usageKey")

            is_terrestrial = True
            if usage_key:
                gbif_profile_url = f"https://api.gbif.org/v1/species/{usage_key}/speciesProfiles"
                gbif_profile_resp = await client.get(gbif_profile_url)
                if gbif_profile_resp.status_code == 200:
                    gbif_profiles = gbif_profile_resp.json().get("results", [])
                    if gbif_profiles:
                        is_terrestrial = gbif_profiles[0].get("terrestrial", True)

            # --- Logic Extraction ---
            is_carnivore = any(word in extract for word in ["carnivore", "predator", "hunt", "eats meat", "scavenger"])
            if "herbivore" in extract or "eats plants" in extract:
                is_carnivore = False
            
            is_nocturnal = "nocturnal" in extract
            is_social = any(word in extract for word in ["pack", "social", "herd", "colony", "group"])
            
            # Simple scaling based on rank/ancestry (fallback stats)
            ancestors = [a.get("name").lower() for a in taxon.get("ancestors", [])]
            base_mass = 1.0 # arbitrary units
            if "mammalia" in ancestors: base_mass = 10.0
            if "aves" in ancestors: base_mass = 2.0
            if "reptilia" in ancestors: base_mass = 5.0
            
            traits = {
                "species": species_name.lower(),
                "common_name": common_name,
                "scientific_name": scientific_name,
                "taxon_id": taxon_id,
                "image_url": image_url,
                "diet_type": "carnivore" if is_carnivore else "herbivore",
                "is_nocturnal": is_nocturnal,
                "is_social": is_social,
                "is_terrestrial": is_terrestrial,
                "metabolic_cost": 0.5 + (base_mass * 0.1), # Larger animals burn more energy
                "max_age": 100 if "mammalia" in ancestors else 50,
                "speed": 2 if is_carnivore else 1,
                "predators": [], # Future enhancement
                "prey": ["rabbit", "deer", "mouse"] if is_carnivore else ["plant"]
            }

            species_cache[species_name.lower()] = traits
            save_cache(species_cache)
            return traits

        except Exception as e:
            print(f"Error fetching data for {species_name}: {e}")
            return None

# Fallback species data for initial world setup
FALLBACK_DATA = {
    "rabbit": {"diet_type": "herbivore", "metabolic_cost": 1.0, "max_age": 50, "speed": 2, "is_nocturnal": False, "is_social": True},
    "wolf": {"diet_type": "carnivore", "metabolic_cost": 2.5, "max_age": 80, "speed": 2, "is_nocturnal": True, "is_social": True},
    "deer": {"diet_type": "herbivore", "metabolic_cost": 2.0, "max_age": 100, "speed": 1, "is_nocturnal": False, "is_social": True},
}
