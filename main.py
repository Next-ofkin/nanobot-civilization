import asyncio
import random
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

# --- Configuration ---
GRID_SIZE = 50
INITIAL_PLANTS = 100
TICK_INTERVAL_SECONDS = 5
PORT = int(os.getenv("PORT", "8000"))

# Species Config
SPECIES_CONFIG = {
    "rabbit": {"max_age": 50, "speed": 2, "diet": "plant", "health": 60, "energy": 80, "hunger_decay": 3},
    "deer": {"max_age": 100, "speed": 1, "diet": "plant", "health": 100, "energy": 100, "hunger_decay": 2},
    "wolf": {"max_age": 80, "speed": 2, "diet": "animal", "health": 120, "energy": 90, "hunger_decay": 4}
}

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
    x: int
    y: int
    age: int
    max_age: int
    health: int
    hunger: int
    energy: int
    speed: int
    is_alive: bool = True

class EcosystemStats(BaseModel):
    plant_count: int
    fauna_count: int
    rabbits: int
    deer: int
    wolves: int
    births: int
    deaths: int
    timestamp: datetime

# --- World State ---
class WorldState:
    def __init__(self):
        self.plants: List[Plant] = []
        self.fauna: List[Animal] = []
        self.next_id = 1
        self.total_births = 0
        self.total_deaths = 0
        self._initialize_world()

    def _initialize_world(self):
        for _ in range(INITIAL_PLANTS):
            self.spawn_plant()
        
        # Initial Population: 20 Rabbits, 10 Deer, 5 Wolves
        for _ in range(20): self.spawn_animal("rabbit")
        for _ in range(10): self.spawn_animal("deer")
        for _ in range(5): self.spawn_animal("wolf")

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

    def spawn_animal(self, species: str, parent: Optional[Animal] = None):
        config = SPECIES_CONFIG[species]
        x, y = (parent.x, parent.y) if parent else (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
        
        animal = Animal(
            id=self.next_id,
            species=species,
            x=x,
            y=y,
            age=0,
            max_age=config["max_age"],
            health=config["health"] if not parent else config["health"] // 2,
            hunger=100,
            energy=config["energy"] if not parent else config["energy"] // 2,
            speed=config["speed"],
            is_alive=True
        )
        self.fauna.append(animal)
        self.next_id += 1
        self.total_births += 1
        return animal

    def get_stats(self):
        species_counts = {"rabbit": 0, "deer": 0, "wolf": 0}
        for a in self.fauna:
            if a.species in species_counts:
                species_counts[a.species] += 1
        
        return EcosystemStats(
            plant_count=len(self.plants),
            fauna_count=len(self.fauna),
            rabbits=species_counts["rabbit"],
            deer=species_counts["deer"],
            wolves=species_counts["wolf"],
            births=self.total_births,
            deaths=self.total_deaths,
            timestamp=datetime.now()
        )

    def _find_target(self, animal: Animal):
        # Simplistic AI: Find closest food/mate
        config = SPECIES_CONFIG[animal.species]
        target_pos = None

        if animal.hunger < 70:
            if config["diet"] == "plant":
                # Find closest plant
                if self.plants:
                    best_plant = min(self.plants, key=lambda p: abs(p.x - animal.x) + abs(p.y - animal.y))
                    target_pos = (best_plant.x, best_plant.y)
            else:
                # Find closest rabbit/deer
                prey = [a for a in self.fauna if a.species in ["rabbit", "deer"] and a.is_alive]
                if prey:
                    best_prey = min(prey, key=lambda a: abs(a.x - animal.x) + abs(a.y - animal.y))
                    target_pos = (best_prey.x, best_prey.y)
        
        elif animal.energy > 50 and animal.hunger > 50 and animal.age > 10:
            # Find mate
            mates = [a for a in self.fauna if a.species == animal.species and a.id != animal.id and a.age > 10 and a.is_alive]
            if mates:
                best_mate = min(mates, key=lambda a: abs(a.x - animal.x) + abs(a.y - animal.y))
                target_pos = (best_mate.x, best_mate.y)

        return target_pos

    def tick(self):
        # 1. Update Plants
        for p in self.plants:
            p.age += 1
            p.health -= 1
        self.plants = [p for p in self.plants if p.health > 0]
        while len(self.plants) < INITIAL_PLANTS // 2: # Minimum threshold
            self.spawn_plant()

        # 2. Update Animals
        new_babies = []
        dead_ids = set()

        for animal in self.fauna:
            if not animal.is_alive: continue

            config = SPECIES_CONFIG[animal.species]
            
            # Decay
            animal.age += 1
            animal.hunger -= config["hunger_decay"]
            animal.energy -= 1

            # Check Death
            if animal.hunger <= 0 or animal.health <= 0 or animal.age >= animal.max_age:
                animal.is_alive = False
                dead_ids.add(animal.id)
                self.total_deaths += 1
                continue

            # Action Decision
            if animal.energy < 20: # Rest
                animal.energy += 10
                continue

            target_pos = self._find_target(animal)
            
            if target_pos:
                # Move towards target
                dx = 1 if target_pos[0] > animal.x else -1 if target_pos[0] < animal.x else 0
                dy = 1 if target_pos[1] > animal.y else -1 if target_pos[1] < animal.y else 0
                animal.x = max(0, min(GRID_SIZE - 1, animal.x + dx * animal.speed))
                animal.y = max(0, min(GRID_SIZE - 1, animal.y + dy * animal.speed))

                # If on target, interact
                if animal.x == target_pos[0] and animal.y == target_pos[1]:
                    if config["diet"] == "plant":
                        # Eat plant
                        eaten = [p for p in self.plants if p.x == animal.x and p.y == animal.y]
                        if eaten:
                            self.plants.remove(eaten[0])
                            animal.hunger = min(100, animal.hunger + 30)
                    else:
                        # Hunt animal
                        prey = [a for a in self.fauna if a.x == animal.x and a.y == animal.y and a.species in ["rabbit", "deer"] and a.is_alive]
                        if prey:
                            prey[0].is_alive = False
                            dead_ids.add(prey[0].id)
                            self.total_deaths += 1
                            animal.hunger = min(100, animal.hunger + 50)
                    
                    # Reproduction check if on mate
                    mate = [a for a in self.fauna if a.x == animal.x and a.y == animal.y and a.species == animal.species and a.id != animal.id and a.is_alive]
                    if mate and animal.hunger > 60 and animal.energy > 60:
                        new_babies.append(animal.species)
                        animal.hunger -= 30
                        animal.energy -= 30
            else:
                # Random wander
                animal.x = max(0, min(GRID_SIZE - 1, animal.x + random.randint(-1, 1)))
                animal.y = max(0, min(GRID_SIZE - 1, animal.y + random.randint(-1, 1)))

        # Cleanup corpses
        self.fauna = [a for a in self.fauna if a.is_alive]
        
        # Add new babies
        for species in new_babies:
            self.spawn_animal(species)

        # Ensure minimal population to prevent extinction in MVP
        counts = self.get_stats()
        if counts.rabbits < 5: self.spawn_animal("rabbit")
        if counts.wolves < 2: self.spawn_animal("wolf")

world_state = WorldState()

# --- Background Task ---
async def world_tick_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        world_state.tick()
        stats = world_state.get_stats()
        print(f"Tick! R:{stats.rabbits} D:{stats.deer} W:{stats.wolves} P:{stats.plant_count}")

# --- FastAPI App ---
app = FastAPI(
    title="Nano-Bot Civilization API - Week 2",
    description="🌱 Week 2: Fauna System. Predators, prey, and reproduction.",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(world_tick_loop())

@app.get("/", tags=["General"])
def root():
    return {"message": "Nano-Bot Civilization - Week 2 Live", "stats": world_state.get_stats()}

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "alive", "world_time": datetime.now()}

@app.get("/api/world/state", tags=["World"])
def get_world_state():
    return {
        "grid_size": GRID_SIZE,
        "plants": world_state.plants,
        "fauna": world_state.fauna,
        "stats": world_state.get_stats()
    }

@app.get("/api/fauna", tags=["Fauna"])
def list_fauna(species: Optional[str] = None):
    """List all living animals, optionally filtered by species."""
    if species:
        return [a for a in world_state.fauna if a.species == species]
    return world_state.fauna

@app.get("/api/fauna/{animal_id}", tags=["Fauna"])
def get_animal(animal_id: int):
    """Get details of a specific animal."""
    for animal in world_state.fauna:
        if animal.id == animal_id:
            return animal
    raise HTTPException(status_code=404, detail="Animal not found")

@app.get("/api/ecosystem/stats", tags=["Stats"])
def get_ecosystem_stats():
    """Get high-level statistics of the ecosystem."""
    return world_state.get_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
