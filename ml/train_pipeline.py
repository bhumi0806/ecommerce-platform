import os
import pickle
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sklearn.decomposition import TruncatedSVD
from scipy.sparse import csr_matrix

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(db_url)

# Matrix Weight Constants
WEIGHTS = {'view': 1, 'cart': 3, 'purchase': 5, 'return': -15}

def run_training_pipeline():
    print("⏳ Loading raw interaction vectors from Neon...")
    with engine.connect() as conn:
        query = text("SELECT user_id, product_id, event_type FROM interactions;")
        df = pd.read_sql(query, conn)
        
    if df.empty:
        print("❌ Ingestion pipeline aborting: No data found inside Neon.")
        return

    print("📊 Compressing data footprint using Sparse Structural Matrices...")
    # Map event action strings to point weights
    df['weight'] = df['event_type'].map(WEIGHTS).fillna(0)
    
    # Compress matrix using category codes instead of raw labels
    df['user_code'] = df['user_id'].astype('category').cat.codes
    df['product_code'] = df['product_id'].astype('category').cat.codes
    
    # Store dynamic mapping lookups to match indexes later
    user_map = dict(enumerate(df['user_id'].astype('category').cat.categories))
    product_map = dict(enumerate(df['product_id'].astype('category').cat.categories))
    reverse_product_map = {v: k for k, v in product_map.items()}

    # Construct Scipy CSR Matrix (Prevents memory bloom completely)
    interaction_matrix = csr_matrix(
        (df['weight'], (df['user_code'], df['product_code'])),
        shape=(len(user_map), len(product_map))
    )

    print("🤖 Training Latent Factor Matrix Decomposition (SVD)...")
    # n_components sets the dimensionality of hidden item behavioral patterns
    svd = TruncatedSVD(n_components=min(12, interaction_matrix.shape[1] - 1), random_state=42)
    user_embeddings = svd.fit_transform(interaction_matrix)
    item_embeddings = svd.components_.T

    print("💾 Caching calculation weights locally...")
    model_artifacts = {
        "user_embeddings": user_embeddings,
        "item_embeddings": item_embeddings,
        "user_map": user_map,
        "reverse_user_map": {v: k for k, v in user_map.items()},
        "product_map": product_map,
        "reverse_product_map": reverse_product_map
    }
    
    # Serializing model weights to disk to serve recommendations instantly
    with open("rec_model.pkl", "wb") as f:
        pickle.dump(model_artifacts, f)
        
    print("✨ ML Model pipeline complete! System parameters exported to 'rec_model.pkl'.")

    print("💾 Caching calculation weights dynamically...")
    model_artifacts = {
        "user_embeddings": user_embeddings,
        "item_embeddings": item_embeddings,
        "user_map": user_map,
        "reverse_user_map": {v: k for k, v in user_map.items()},
        "product_map": product_map,
        "reverse_product_map": reverse_product_map
    }
    
    # 🚀 DYNAMIC ABSOLUTE PATH CALCULATOR:
    # 1. Finds where train_pipeline.py is located (D:\ecommerce-recommender-new\ml)
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. Steps up one directory level to the project root (D:\ecommerce-recommender-new)
    project_root = os.path.abspath(os.path.join(current_script_dir, os.pardir))
    # 3. Targets the backend destination folder exactly
    backend_target_dir = os.path.join(project_root, "backend", "app")
    
    # Create the folder path structure safely if it doesn't exist yet
    os.makedirs(backend_target_dir, exist_ok=True)
    
    output_path = os.path.join(backend_target_dir, "rec_model.pkl")
    
    with open(output_path, "wb") as f:
        pickle.dump(model_artifacts, f)
        
    print(f"✨ ML Model pipeline complete! System parameters exported to: {output_path}")


if __name__ == "__main__":
    run_training_pipeline()
