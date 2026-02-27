import asyncio
import random
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List
import os

# --- Configuration ---
GRID_SIZE = 50
INITIAL_PLANTS = 100
TICK_INTERVAL_SECONDS = 5
PORT = int(os.getenv("PORT", 8000))

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
        for plant in self.plants:
            plant.age += 1
            plant.health -= 1
        self.plants = [p for p in self.plants if p.health > 0]
        while len(self.plants) < INITIAL_PLANTS:
            self.spawn_plant()

world_state = WorldState()

# --- Background Task ---
async def world_tick_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        world_state.tick()
        print(f"Tick! Plants: {len(world_state.plants)}")

# --- FastAPI App ---
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(world_tick_loop())

@app.get("/")
def root():
    return {"message": "Nano-Bot Civilization", "port": PORT}

@app.get("/health")
def health_check():
    return {"status": "alive", "plants": len(world_state.plants)}

@app.get("/api/world/state")
def get_world_state():
    return {
        "grid_size": GRID_SIZE,
        "plant_count": len(world_state.plants),
        "plants": world_state.plants
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)