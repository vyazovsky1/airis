from fastapi import FastAPI, HTTPException
import logging

app = FastAPI(title="Inventory Backend Service")

# Simulate a business logic endpoint that might have memory spikes during intensive processing
@app.get("/api/v1/inventory/summary")
async def get_summary():
    # In a real app, this would perform complex joins and data aggregation
    # which leads to the memory spikes observed in the morning/afternoon hours.
    return {
        "status": "ready",
        "total_sku": 1250,
        "active_warehouses": 5,
        "low_stock_alerts": 12
    }

@app.get("/api/v1/inventory/recalculate-all")
async def recalculate_all():
    # Simulated CPU-heavy operation (Recursive Fibonacci)
    # This represents a maintenance task that causes a CPU spike.
    def fib(n):
        if n <= 1: return n
        return fib(n-1) + fib(n-2)
    
    # We run a small one to respond quickly but the intent is clear
    result = fib(10) 
    return {"status": "recalculated", "load_type": "CPU_INTENSIVE", "result": result}

@app.post("/api/v1/inventory/update")
async def update_stock(sku_id: str, quantity: int):
    # Transactional logic
    return {"status": "updated", "sku": sku_id}
