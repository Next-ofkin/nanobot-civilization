import httpx
import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from external_apis import FALLBACK_DATA

CACHE_FILE = "species_cache.json"
USER_AGENT = "NanoBotCivilization/1.0 (https://github.com/Next-ofkin/nanobot-civilization)"

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

async def search_species(query: str) -> List[Dict[str, Any]]:
    """
    Searches for species across GBIF and iNaturalist.
    """
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # GBIF Search
        gbif_url = f"https://api.gbif.org/v1/species/search?q={query}&rank=SPECIES&limit=10"
        try:
            gbif_resp = await client.get(gbif_url)
            gbif_results = gbif_resp.json().get("results", [])
        except Exception as e:
            print(f"GBIF search error: {e}")
            gbif_results = []

        results = []
        for r in gbif_results:
            results.append({
                "scientific_name": r.get("scientificName"),
                "common_names": [r.get("vernacularName")] if r.get("vernacularName") else [],
                "kingdom": r.get("kingdom"),
                "phylum": r.get("phylum"),
                "class": r.get("class"),
                "order": r.get("order"),
                "family": r.get("family"),
                "genus": r.get("genus"),
                "species": r.get("species"),
                "gbif_id": r.get("key")
            })
        
        return results

async def get_species_details(scientific_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetches comprehensive data from GBIF, iNaturalist, Wikipedia, and Catalogue of Life.
    """
    if scientific_name in species_cache:
        return species_cache[scientific_name]

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            # 1. iNaturalist for image and preferred common name
            inat_url = f"https://api.inaturalist.org/v1/taxa?q={scientific_name}&rank=species"
            inat_resp = await client.get(inat_url)
            inat_data = inat_resp.json().get("results", [])
            taxon = inat_data[0] if inat_data else {}
            
            common_name = taxon.get("preferred_common_name", scientific_name)
            image_url = taxon.get("default_photo", {}).get("medium_url")
            inat_id = taxon.get("id")

            # 2. Wikipedia for behavior and description
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{scientific_name.replace(' ', '_')}"
            wiki_resp = await client.get(wiki_url)
            wiki_data = wiki_resp.json() if wiki_resp.status_code == 200 else {}
            extract = wiki_data.get("extract", "").lower()

            # 3. GBIF for taxonomic details and conservation
            gbif_match_url = f"https://api.gbif.org/v1/species/match?name={scientific_name}"
            gbif_resp = await client.get(gbif_match_url)
            gbif_match = gbif_resp.json()
            gbif_id = gbif_match.get("usageKey")

            # 4. Catalogue of Life (Checklist Bank) for Hierarchy
            col_url = f"https://api.checklistbank.org/dataset/2340/taxon/match?name={scientific_name}"
            col_resp = await client.get(col_url)
            col_data = col_resp.json() if col_resp.status_code == 200 else {}
            
            # --- Taxonomy-Based Fallbacks ---
            gbif_class = str(gbif_match.get("class", "")).lower()
            gbif_order = str(gbif_match.get("order", "")).lower()
            
            # --- Better Behavioral Extraction ---
            is_social = any(word in extract for word in ["social", "gregarious", "pack", "herd", "colony", "group", "pride", "troop"])
            if "solitary" in extract: is_social = False
            
            is_territorial = any(word in extract for word in ["territorial", "defends territory", "home range"])
            is_nocturnal = any(word in extract for word in ["nocturnal", "active at night"])
            if "diurnal" in extract: is_nocturnal = False
            
            # Diet Detection
            is_carnivore = any(word in extract for word in ["carnivore", "predator", "hunts", "eats meat", "scavenger", "piscivore", "apex predator"])
            is_herbivore = any(word in extract for word in ["herbivore", "eats plants", "frugivore", "folivore", "grazing", "browser"])
            
            # Taxonomic Enforcement
            if "carnivora" in gbif_order or "cetacea" in gbif_order:
                is_carnivore = True
                is_herbivore = False
            elif any(w in gbif_order for w in ["artiodactyla", "perissodactyla", "proboscidea", "rodentia"]):
                is_herbivore = True
                is_carnivore = False
            
            diet = "Carnivore"
            if is_herbivore and not is_carnivore: diet = "Herbivore"
            elif is_carnivore and is_herbivore: diet = "Omnivore"
            elif is_herbivore: diet = "Herbivore"

            # Attempt to find prey/predators in extract
            potential_prey = ["zebra", "buffalo", "wildebeest", "rabbit", "deer", "mouse", "fish", "insect"]
            prey_found = [p.capitalize() for p in potential_prey if p in extract]
            if diet == "Herbivore": prey_found = ["Plants"]
            
            # Mass & Lifespan Scaling based on Taxonomy
            base_mass = 50.0
            if "mammalia" in gbif_class:
                base_mass = 100.0
                if any(w in gbif_order for w in ["proboscidea", "cetacea"]): base_mass = 3000.0
                elif any(w in gbif_order for w in ["carnivora", "artiodactyla"]): base_mass = 200.0
            elif "aves" in gbif_class:
                base_mass = 2.0
            
            details = {
                "scientific_name": scientific_name,
                "common_names": [common_name],
                "diet": diet,
                "lifespan_years": 15 if "mammalia" in gbif_class else 5,
                "mass_kg": base_mass,
                "speed_kmh": 60 if diet == "Carnivore" else 40,
                "habitat": ["Savanna", "Grassland"] if any(w in extract for w in ["savanna", "grassland", "plains"]) else ["Terrestrial"],
                "behavior": [b for b, v in {"Social": is_social, "Nocturnal": is_nocturnal, "Territorial": is_territorial}.items() if v],
                "social_structure": "Pack/Pride" if is_social else "Solitary",
                "predators": ["Humans"],
                "prey": prey_found,
                "activity_pattern": "Nocturnal" if is_nocturnal else "Diurnal",
                "conservation_status": "Unknown",
                "description": wiki_data.get("extract", "No description available."),
                "image_url": image_url,
                "gbif_id": gbif_id,
                "inaturalist_id": inat_id,
                "col_id": col_data.get("usageKey")
            }

            species_cache[scientific_name] = details
            save_cache(species_cache)
            return details

        except Exception as e:
            print(f"Error fetching details for {scientific_name}: {e}")
            return None

async def browse_species(kingdom: str = "Animalia", class_name: Optional[str] = None, order: Optional[str] = None, family: Optional[str] = None, offset: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Browses species using GBIF search for better taxonomic filtering.
    """
    headers = {"User-Agent": USER_AGENT}
    url = "https://api.gbif.org/v1/species/search"
    params = {
        "rank": "SPECIES",
        "status": "ACCEPTED",
        "offset": offset,
        "limit": limit,
        "q": kingdom
    }
    if class_name: params["class"] = class_name
    if order: params["order"] = order
    if family: params["family"] = family

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        try:
            resp = await client.get(url, params=params)
            results = resp.json().get("results", [])
            return results
        except Exception as e:
            print(f"Browse error: {e}")
            return []
