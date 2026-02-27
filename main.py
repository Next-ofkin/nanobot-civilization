import asyncio
import random
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

# --- Configuration ---
GRID_SIZE = 50
INITIAL_PLANTS = 100
TICK_INTERVAL_SECONDS = 5
PORT = int(os.getenv("PORT", "8000"))

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

# --- FastAPI App with Enhanced Swagger ---
app = FastAPI(
    title="Nano-Bot Civilization API",
    description="""
    🌱 A self-sustaining digital ecosystem where plants grow, age, and die.
    
    ## Features
    - **100 Plants** living on a 50x50 grid
    - **Real-time updates** every 5 seconds
    - **Lifecycle simulation**: Plants age and lose health over time
    - **Auto-respawn**: Dead plants are replaced with new ones
    
    ## Endpoints
    - Check system health
    - View current world state with all plants
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Nano-Bot Civilization",
        "url": "https://github.com/Next-ofkin/nanobot-civilization"
    }
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(world_tick_loop())

@app.get(
    "/",
    tags=["General"],
    summary="Root endpoint",
    response_description="Basic API information"
)
def root():
    """
    Returns basic information about the Nano-Bot Civilization API.
    
    Use this to verify the API is running.
    """
    return {
        "message": "Nano-Bot Civilization",
        "version": "1.0.0",
        "port": PORT,
        "plants": len(world_state.plants),
        "grid_size": GRID_SIZE
    }

@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_description="System status and plant count"
)
def health_check():
    """
    Check if the API is running and get current ecosystem status.
    
    Returns:
    - **status**: "alive" if running
    - **plants**: Current number of living plants
    """
    return {
        "status": "alive",
        "plants": len(world_state.plants),
        "grid_size": GRID_SIZE
    }

@app.get(
    "/api/world/state",
    tags=["World"],
    summary="Get complete world state",
    response_description="Full ecosystem data including all plants"
)
def get_world_state():
    """
    Returns the current state of the entire ecosystem.
    
    Includes:
    - **grid_size**: Size of the world grid (50x50)
    - **plant_count**: Total number of living plants
    - **plants**: Array of all plants with their:
        - id: Unique identifier
        - x, y: Position on grid
        - age: How many ticks old
        - health: Current health (0-100)
    
    Plants update every 5 seconds. Refresh to see changes!
    """
    return {
        "grid_size": GRID_SIZE,
        "plant_count": len(world_state.plants),
        "plants": world_state.plants
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)