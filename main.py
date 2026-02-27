import asyncio
import random
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

# --- Configuration ---
GRID_SIZE = 50
INITIAL_PLANTS = 100
TICK_INTERVAL_SECONDS = 5

# --- Data Models ---
class Plant(BaseModel):
    id: int
    x: int
    y: int
    age: int
    health: int

# --- World State ---
class WorldState:
    def __init__(self):
        self.plants: List[Plant] = []
        self.next_id = 1
        self._initialize_world()

    def _initialize_world(self):
        for _ in range(INITIAL_PLANTS):
            self.spawn_plant()

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

    def tick(self):
        # Update all plants
        for plant in self.plants:
            plant.age += 1
            plant.health -= 1

        # Remove dead plants (health <= 0)
        self.plants = [p for p in self.plants if p.health > 0]

        # Respawn to maintain INITIAL_PLANTS
        while len(self.plants) < INITIAL_PLANTS:
            self.spawn_plant()

world_state = WorldState()

# --- Background Task ---
async def world_tick_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        world_state.tick()
        print(f"World Ticked. Current plants: {len(world_state.plants)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background tick loop
    tick_task = asyncio.create_task(world_tick_loop())
    yield
    # Clean up
    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "alive"}

@app.get("/api/world/state")
def get_world_state():
    return {
        "grid_size": GRID_SIZE,
        "plant_count": len(world_state.plants),
        "plants": world_state.plants
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
