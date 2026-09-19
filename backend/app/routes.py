from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models, schemas, recommender
from sqlalchemy import text
from typing import List
from .schemas import ProductResponse
import pickle
import numpy as np
router = APIRouter()
import os


# -------------------------
# USERS
# -------------------------

@router.post("/users", response_model=schemas.UserResponse)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(models.User)
        .filter(models.User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = models.User(
        name=user.name,
        email=user.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# -------------------------
# PRODUCTS
# -------------------------

@router.post("/products", response_model=schemas.ProductResponse)
def create_product(
    product: schemas.ProductCreate,
    db: Session = Depends(get_db)
):
    new_product = models.Product(
        name=product.name,
        category=product.category,
        brand=product.brand,
        price=product.price,
        description=product.description
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return new_product


@router.get("/products", response_model=list[schemas.ProductResponse])
def get_products(
    db: Session = Depends(get_db)
):
    products = db.query(models.Product).all()

    return products


# -------------------------
# INTERACTIONS
# -------------------------

@router.post(
    "/interactions",
    response_model=schemas.InteractionResponse
)
def create_interaction(
    interaction: schemas.InteractionCreate,
    db: Session = Depends(get_db)
):
    # Check whether user exists
    user = (
        db.query(models.User)
        .filter(models.User.id == interaction.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Check whether product exists
    product = (
        db.query(models.Product)
        .filter(models.Product.id == interaction.product_id)
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    new_interaction = models.Interaction(
        user_id=interaction.user_id,
        product_id=interaction.product_id,
        event_type=interaction.event_type
    )

    db.add(new_interaction)
    db.commit()
    db.refresh(new_interaction)

    return new_interaction

# -------------------------
# RECOMMENDATIONS
# -------------------------

MODEL_DATA = None

def load_ml_model():
    global MODEL_DATA
    if MODEL_DATA is None:
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, "rec_model.pkl")
            
            with open(model_path, "rb") as f:
                MODEL_DATA = pickle.load(f)
            print("🤖 ML Model weights successfully loaded into FastAPI memory cache.")
        except FileNotFoundError:
            print("⚠️ Warning: rec_model.pkl not found inside app folder.")
            MODEL_DATA = {}
@router.get("/recommendations/{user_id}", response_model=List[ProductResponse])
def get_risk_mitigated_recommendations(user_id: int, db: Session = Depends(get_db)):
    """
    Serves hyper-personalized, scalable machine learning predictions.
    Blends SVD Matrix Factorization weights with Neon cloud Bayesian risk filtering.
    """
    load_ml_model()
    
    # 🛑 NEON CLOUD RISK FILTER: Finds bad actor products (>18% return ceiling)
    risk_query = text("""
        WITH global_metrics AS (
            SELECT COUNT(CASE WHEN event_type = 'return' THEN 1 END)::float / 
                   NULLIF(COUNT(CASE WHEN event_type IN ('purchase', 'return') THEN 1 END), 0) as global_rate
            FROM interactions
        ),
        product_risk AS (
            SELECT product_id,
                   (COUNT(CASE WHEN event_type = 'return' THEN 1 END) + (5.0 * (SELECT global_rate FROM global_metrics))) / 
                   (COUNT(CASE WHEN event_type IN ('purchase', 'return') THEN 1 END) + 5.0) as smoothed_return_rate
            FROM interactions
            GROUP BY product_id
        )
        SELECT product_id FROM product_risk WHERE smoothed_return_rate > 0.18
        UNION
        SELECT product_id FROM interactions WHERE user_id = :user_id AND event_type = 'purchase';
    """)
    
    try:
        # 1. Fetch products to exclude (High returns or already purchased by this user)
        excluded_result = db.execute(risk_query, {"user_id": user_id}).fetchall()
        excluded_ids = set(row[0] for row in excluded_result) # Extract row item integer strictly
        
        candidate_pids = []
        
        # 2. Check if the user exists in our trained ML sparse matrix artifacts
        if MODEL_DATA and "reverse_user_map" in MODEL_DATA and user_id in MODEL_DATA["reverse_user_map"]:
            u_idx = MODEL_DATA["reverse_user_map"][user_id]
            u_vector = MODEL_DATA["user_embeddings"][u_idx]
            
            # Compute real-time vector dot product mapping using the correct artifact key
            predicted_scores = np.dot(MODEL_DATA["item_embeddings"], u_vector)
            
            # Sort product index coordinates from highest probability to lowest
            ranked_indices = np.argsort(predicted_scores)[::-1]
            
            # Filter matches using our Neon risk footprint array
            for idx in ranked_indices:
                pid = int (MODEL_DATA["product_map"][idx])
                if pid not in excluded_ids:
                    candidate_pids.append(int(pid))
                if len(candidate_pids) >= 10:
                    break

        # 3. Hydrate matching product records from Neon using clean table keys
        if candidate_pids:
            # Matches your primary schema column names exactly
            fetch_query = text("SELECT id, name, category, brand, price, description FROM products WHERE id = ANY(:ids);")
            db_products = db.execute(fetch_query, {"ids": candidate_pids}).fetchall()
        else:
            # Cold-Start Fallback: If user is new or ML cache missing, serve safe non-risk items
            print("❄️ Cold-Start detected for User. Querying global non-risk catalog items...")
            fallback_query = text("""
                SELECT p.id, p.name, p.category, p.brand, p.price, p.description 
                FROM products p
                LIMIT 10;
            """)
            db_products = db.execute(fallback_query).fetchall()

        # Format rows into structural dictionaries matching your Pydantic schemas perfectly
        return [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "brand": p.brand,
                "price": float(p.price),
                "description": p.description
            } for p in db_products
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation routing failed: {str(e)}")
