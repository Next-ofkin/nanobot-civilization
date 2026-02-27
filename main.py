import asyncio
import random
import os
import math
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Set
from datetime import datetime
from external_apis import fetch_species_data, FALLBACK_DATA

# --- Configuration ---
GRID_SIZE = 50
INITIAL_PLANTS = 150
TICK_INTERVAL_SECONDS = 5
PORT = int(os.getenv("PORT", "8000"))
DAY_NIGHT_CYCLE_TICKS = 50 # 50 ticks = Day, 50 ticks = Night

# --- Data Models ---
class Plant(BaseModel):
    id: int
    x: int
    y: int
    age: int
    health: int

class Animal(BaseModel):
    id: int
    species: str
    common_name: str
    scientific_name: Optional[str] = None
    x: int
    y: int
    age: int
    max_age: int
    health: float
    hunger: float
    energy: float
    speed: int
    metabolic_cost: float
    diet_type: str
    is_nocturnal: bool
    is_social: bool
    is_alive: bool = True
    image_url: Optional[str] = None

class Nanobot(BaseModel):
    id: int
    x: int
    y: int
    mode: str = "observe" # observe, admin, learning
    observed_behaviors: Set[str] = set()
    energy: float = 100.0

class EcosystemStats(BaseModel):
    plant_count: int
    fauna_count: int
    nanobot_count: int
    species_breakdown: Dict[str, int]
    is_day: bool
    births: int
    deaths: int
    timestamp: datetime

# --- World State ---
class WorldState:
    def __init__(self):
        self.plants: List[Plant] = []
        self.fauna: List[Animal] = []
        self.nanobots: List[Nanobot] = []
        self.species_traits: Dict[str, Dict] = {}
        self.next_id = 1
        self.tick_count = 0
        self.total_births = 0
        self.total_deaths = 0
        self.is_day = True
        
    async def initialize(self):
        # Fetch initial real data or fallback
        initial_species = ["rabbit", "deer", "wolf"]
        for s in initial_species:
            data = await fetch_species_data(s)
            self.species_traits[s] = data if data else FALLBACK_DATA.get(s)

        # Populate
        for _ in range(INITIAL_PLANTS): self.spawn_plant()
        for s, count in [("rabbit", 20), ("deer", 10), ("wolf", 5)]:
            for _ in range(count): self.spawn_animal(s)
        
        # Initial Nanobots
        for _ in range(3): self.spawn_nanobot()

    def spawn_plant(self):
        plant = Plant(
            id=self.next_id,
            x=random.randint(0, GRID_SIZE - 1),
            y=random.randint(0, GRID_SIZE - 1),
            age=0,
            health=100
        )
        self.plants.append(plant)
        self.next_id += 1

    def spawn_animal(self, species: str, pos: Optional[tuple] = None):
        traits = self.species_traits.get(species, FALLBACK_DATA.get("rabbit"))
        x, y = pos if pos else (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
        
        animal = Animal(
            id=self.next_id,
            species=species,
            common_name=traits.get("common_name", species),
            scientific_name=traits.get("scientific_name"),
            x=x,
            y=y,
            age=0,
            max_age=traits.get("max_age", 100),
            health=100.0,
            hunger=100.0,
            energy=100.0,
            speed=traits.get("speed", 1),
            metabolic_cost=traits.get("metabolic_cost", 1.0),
            diet_type=traits.get("diet_type", "herbivore"),
            is_nocturnal=traits.get("is_nocturnal", False),
            is_social=traits.get("is_social", False),
            image_url=traits.get("image_url")
        )
        self.fauna.append(animal)
        self.next_id += 1
        self.total_births += 1
        return animal

    def spawn_nanobot(self):
        bot = Nanobot(id=self.next_id, x=random.randint(0, GRID_SIZE - 1), y=random.randint(0, GRID_SIZE - 1))
        self.nanobots.append(bot)
        self.next_id += 1

    def get_stats(self):
        breakdown = {}
        for a in self.fauna:
            breakdown[a.species] = breakdown.get(a.species, 0) + 1
        
        return EcosystemStats(
            plant_count=len(self.plants),
            fauna_count=len(self.fauna),
            nanobot_count=len(self.nanobots),
            species_breakdown=breakdown,
            is_day=self.is_day,
            births=self.total_births,
            deaths=self.total_deaths,
            timestamp=datetime.now()
        )

    def _update_cycle(self):
        self.tick_count += 1
        if self.tick_count % DAY_NIGHT_CYCLE_TICKS == 0:
            self.is_day = not self.is_day

    async def tick(self):
        self._update_cycle()
        
        # 1. Plants Grow (Trophic Cascade: grow faster if few herbivores)
        herbivore_count = sum(1 for a in self.fauna if a.diet_type == "herbivore")
        growth_multiplier = 2.0 if herbivore_count < 10 else 1.0
        
        for p in self.plants:
            p.age += 1
            if random.random() < 0.05 * growth_multiplier:
                p.health = min(100, p.health + 5)
        
        self.plants = [p for p in self.plants if p.health > 0]
        if len(self.plants) < INITIAL_PLANTS:
            if random.random() < 0.2: self.spawn_plant()

        # 2. Animals Update (Metabolic Logic + Lotka-Volterra Hunting)
        dead_this_tick = []
        new_births = []
        
        # Pre-calc counts for L-V probabilities
        prey_count = sum(1 for a in self.fauna if a.diet_type == "herbivore")
        target_prey_density = prey_count / (GRID_SIZE * GRID_SIZE)

        for animal in self.fauna:
            if not animal.is_alive: continue
            
            # Metabolism
            is_sleeping = (self.is_day and animal.is_nocturnal) or (not self.is_day and not animal.is_nocturnal)
            cost = animal.metabolic_cost * (0.2 if is_sleeping else 1.0)
            
            animal.hunger -= cost
            animal.energy = min(100, animal.energy + (5 if is_sleeping else -cost * 0.5))
            animal.age += 1

            # Determine Mortality
            if animal.hunger <= 0 or animal.health <= 0 or animal.age >= animal.max_age:
                animal.is_alive = False
                dead_this_tick.append(animal.id)
                self.total_deaths += 1
                continue

            if is_sleeping: continue

            # Behavior Logic (Risk/Reward)
            target = None
            if animal.hunger < 80:
                if animal.diet_type == "herbivore":
                    # Forage
                    if self.plants:
                        target = min(self.plants, key=lambda p: abs(p.x - animal.x) + abs(p.y - animal.y))
                else:
                    # Hunt (L-V probability check before moving)
                    hunt_success_prob = 0.3 * (1 + target_prey_density * 10)
                    if random.random() < hunt_success_prob:
                        prey = [a for a in self.fauna if a.diet_type == "herbivore" and a.is_alive]
                        if prey:
                            target = min(prey, key=lambda p: abs(p.x - animal.x) + abs(p.y - animal.y))

            # Move & Interact
            if target:
                speed = max(1, int(animal.speed * (animal.energy / 100)))
                dx = 1 if target.x > animal.x else -1 if target.x < animal.x else 0
                dy = 1 if target.y > animal.y else -1 if target.y < animal.y else 0
                animal.x = max(0, min(GRID_SIZE-1, animal.x + dx * speed))
                animal.y = max(0, min(GRID_SIZE-1, animal.y + dy * speed))

                if animal.x == target.x and animal.y == target.y:
                    if isinstance(target, Plant):
                        target.health -= 50
                        animal.hunger = min(100, animal.hunger + 40)
                    else:
                        target.is_alive = False
                        animal.hunger = min(100, animal.hunger + 60)
                        self.total_deaths += 1
            else:
                # Wander or Socialize
                if animal.is_social:
                    peers = [a for a in self.fauna if a.species == animal.species and a.id != animal.id]
                    if peers:
                        closest = min(peers, key=lambda p: abs(p.x - animal.x) + abs(p.y - animal.y))
                        dx = 1 if closest.x > animal.x else -1 if closest.x < animal.x else 0
                        animal.x = max(0, min(GRID_SIZE-1, animal.x + dx))
                
                animal.x = max(0, min(GRID_SIZE-1, animal.x + random.randint(-1, 1)))
                animal.y = max(0, min(GRID_SIZE-1, animal.y + random.randint(-1, 1)))

            # Reproduction
            if animal.hunger > 70 and animal.energy > 60 and animal.age > 10:
                mates = [a for a in self.fauna if a.species == animal.species and a.id != animal.id and a.hunger > 60 and a.x == animal.x and a.y == animal.y]
                if mates:
                    new_births.append(animal.species)
                    animal.hunger -= 40
                    animal.energy -= 40

        # 3. Nanobots (Pro-Observers & Admins)
        for bot in self.nanobots:
            # Observation
            nearby_fauna = [a for a in self.fauna if abs(a.x - bot.x) + abs(a.y - bot.y) < 5]
            for a in nearby_fauna:
                if a.hunger < 50: bot.observed_behaviors.add("hunting" if a.diet_type == "carnivore" else "foraging")
                if a.is_social: bot.observed_behaviors.add("farming" if random.random() < 0.01 else "building")

            # Move towards action
            if self.fauna:
                target_a = random.choice(self.fauna)
                bot.x = max(0, min(GRID_SIZE-1, bot.x + (1 if target_a.x > bot.x else -1)))
                bot.y = max(0, min(GRID_SIZE-1, bot.y + (1 if target_a.y > bot.y else -1)))

            # Admin Task: Reseed if extinction imminent
            stats = self.get_stats()
            for species, count in stats.species_breakdown.items():
                if count < 2 and bot.energy > 50:
                    self.spawn_animal(species, pos=(bot.x, bot.y))
                    bot.energy -= 50
            
            bot.energy = min(100, bot.energy + 2)

        # Finalize tick
        self.fauna = [a for a in self.fauna if a.is_alive]
        for s in new_births: self.spawn_animal(s)

world_state = WorldState()

# --- Background Task ---
async def world_tick_loop():
    await world_state.initialize()
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        await world_state.tick()
        s = world_state.get_stats()
        print(f"Tick {world_state.tick_count}: P:{s.plant_count} F:{s.fauna_count} N:{s.nanobot_count} | Births:{s.births} Deaths:{s.deaths}")

# --- FastAPI App ---
app = FastAPI(
    title="Nano-Bot Civilization - Week 3",
    description="🛸 Realistic Living Ecosystem with AI Nanobot Observers.",
    version="3.0.0"
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(world_tick_loop())

@app.get("/", tags=["General"])
def root():
    return {"message": "Protocol 3: Living Ecosystem Active", "world_time": world_state.tick_count, "stats": world_state.get_stats()}

@app.get("/api/world/state", tags=["World"])
def get_world_state():
    return {
        "is_day": world_state.is_day,
        "tick": world_state.tick_count,
        "plants": world_state.plants,
        "fauna": world_state.fauna,
        "nanobots": world_state.nanobots,
        "stats": world_state.get_stats()
    }

@app.get("/api/ecosystem/real-species", tags=["Stats"])
def get_real_species():
    """Returns the scientific data fetched for all species in the world."""
    return world_state.species_traits

@app.post("/api/god/introduce-species", tags=["God Interface"])
async def introduce_species(species: str = Body(..., embed=True), count: int = Body(5, embed=True)):
    """Dynamically fetch and add a new species to the world."""
    data = await fetch_species_data(species)
    if not data:
        raise HTTPException(status_code=404, detail="Could not find realistic data for this species.")
    
    world_state.species_traits[species] = data
    for _ in range(count):
        world_state.spawn_animal(species)
    
    return {"message": f"Successfully introduced {count} {species}.", "traits": data}

@app.get("/api/nanobots", tags=["Nanobots"])
def get_nanobots():
    """Check what the nanobots have learned."""
    return world_state.nanobots

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
