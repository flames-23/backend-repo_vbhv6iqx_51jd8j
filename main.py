import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema

app = FastAPI(title="Electronics Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image: Optional[str] = Field(None, description="Image URL")


class ProductOut(ProductIn):
    id: str


# Helpers

def serialize_product(doc) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        description=doc.get("description"),
        price=doc.get("price"),
        category=doc.get("category"),
        in_stock=doc.get("in_stock", True),
        image=doc.get("image"),
    )


@app.get("/")
def read_root():
    return {"message": "Electronics Store Backend is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# Seed sample products if collection empty
@app.on_event("startup")
async def seed_products():
    if db is None:
        return
    try:
        count = db["product"].count_documents({})
        if count == 0:
            samples: List[dict] = [
                {
                    "title": "Smartphone X200",
                    "description": "6.5\" OLED, 128GB, Dual Camera",
                    "price": 699.0,
                    "category": "Phones",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?q=80&w=800&auto=format&fit=crop"
                },
                {
                    "title": "Noise-Canceling Headphones",
                    "description": "Over-ear, 30h battery, Bluetooth 5.2",
                    "price": 199.0,
                    "category": "Audio",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1518441902119-52ab42fb52fb?q=80&w=800&auto=format&fit=crop"
                },
                {
                    "title": "4K Ultra HD TV 55\"",
                    "description": "55-inch, HDR10+, Smart TV",
                    "price": 499.0,
                    "category": "TVs",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1593359677879-74010a5d13b6?q=80&w=800&auto=format&fit=crop"
                },
                {
                    "title": "Gaming Laptop G15",
                    "description": "RTX 4060, 16GB RAM, 1TB SSD",
                    "price": 1499.0,
                    "category": "Computers",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?q=80&w=800&auto=format&fit=crop"
                }
            ]
            for s in samples:
                create_document("product", s)
    except Exception:
        # Silently ignore seeding errors
        pass


@app.get("/api/products", response_model=List[ProductOut])
def list_products(q: Optional[str] = None, category: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None):
    if db is None:
        return []
    filt: dict = {}
    if q:
        filt["title"] = {"$regex": q, "$options": "i"}
    if category:
        filt["category"] = category
    if min_price is not None or max_price is not None:
        price = {}
        if min_price is not None:
            price["$gte"] = float(min_price)
        if max_price is not None:
            price["$lte"] = float(max_price)
        filt["price"] = price

    docs = get_documents("product", filt)
    return [serialize_product(d) for d in docs]


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = db["product"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(doc)


@app.post("/api/products", response_model=str)
def create_product(payload: ProductIn):
    # Validate with schema
    _ = ProductSchema(**payload.model_dump())
    inserted_id = create_document("product", payload.model_dump())
    return inserted_id


@app.get("/api/categories", response_model=List[str])
def list_categories():
    if db is None:
        return []
    cats = db["product"].distinct("category")
    return sorted([c for c in cats if c])


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
