import os
import time
import pandas as pd
from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import create_engine

# 1. Initialize environments and Database Engine
load_dotenv()
fake = Faker()

# Format the Connection URL safely for SQLAlchemy
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

# MATCHES YOUR FILENAME FROM THE IMAGE EXACTLY
CSV_FILE_PATH = "ecommerce_recommendation_dataset.csv" 

def run_pipeline():
    mock_brands = {
        'Electronics': ['Sony', 'Apple', 'Samsung', 'Logitech', 'Dell', 'Bose'],
        'Fashion': ['Nike', 'Levi\'s', 'Adidas', 'Patagonia', 'Ray-Ban', 'Carhartt'],
        'Beauty': ['L\'Oréal', 'Sephora', 'The Ordinary', 'CeraVe', 'Estée Lauder', 'Mac'],
        'Sports': ['Lululemon', 'Hydro Flask', 'Bowflex', 'Coleman', 'Wilson', 'Under Armour'],
        'Books': ['Penguin Books', 'HarperCollins', 'O\'Reilly Media', 'Random House', 'Simon & Schuster', 'MIT Press'],
        'Grocery': ['Nespresso', 'Kirkland Signature', 'Nature Valley', 'Twinings', 'Heinz', 'Trader Joe\'s']
    }
    mock_names = {
        'Electronics': ['Wireless Noise-Canceling Headphones', 'Mechanical Gaming Keyboard', 'Ultra-Wide 4K Monitor', 'Smart Fitness Watch', 'Bluetooth Portable Speaker', 'Ergonomic Wireless Mouse'],
        'Fashion': ['Classic Leather Jacket', 'Slim-Fit Denim Jeans', 'Breathable Mesh Sneakers', 'Vintage Canvas Backpack', 'Unisex Polarized Sunglasses', 'Premium Cotton Hoodie'],
        'Beauty': ['Hydrating Hyaluronic Serum', 'Matte Long-Wear Lipstick', 'Organic Argan Hair Oil', 'Exfoliating Face Scrub', 'Volumizing Waterproof Mascara', 'Soothing Aloe Cream'],
        'Sports': ['High-Density Yoga Mat', 'Stainless Steel Water Bottle', 'Adjustable Dumbbell Set', 'Waterproof Camping Tent', 'Professional Soccer Ball', 'Lightweight Running Shorts'],
        'Books': ['Sci-Fi Hardcover Novel', 'Mystery Thriller Best-Seller', 'Data Science Complete Guide', 'Modern History Anthology', 'Creative Cooking Cookbook', 'Self-Improvement Journal'],
        'Grocery': ['Organic Medium-Roast Coffee', 'Cold-Pressed Extra Virgin Olive Oil', 'Pure Raw Honey', 'Roasted Almonds Snack Pack', 'Assorted Herbal Tea Box', 'Gluten-Free Granola Bars']
    }

    print(f"⏳ Reading '{CSV_FILE_PATH}' into memory...")
    try:
        df = pd.read_csv(CSV_FILE_PATH)
    except FileNotFoundError:
        print(f"❌ Error: Could not find the file '{CSV_FILE_PATH}' in this directory.")
        return

    # --- PHASE 1: SEED USERS ---
    print("👥 Extracting unique user IDs...")
    unique_user_ids = df['User_ID'].unique()
    
    users_data = []
    for uid in unique_user_ids:
        users_data.append({
            "id": int(uid),
            "name": fake.name(), 
            "email": f"user_{uid}@{fake.free_email_domain()}" # Satisfies EmailStr validation
        })
    
    users_df = pd.DataFrame(users_data)
    print(f"-> Uploading {len(users_df)} unique users to Neon...")
    # if_exists='append' ensures your 1 manual test user doesn't cause a crash
    users_df.to_sql('users', engine, if_exists='append', index=False, chunksize=1000)

    # --- PHASE 2: SEED PRODUCTS ---
    print("📦 Extracting unique product IDs...")
    unique_products = df.drop_duplicates(subset=['Product_ID'])
    
    products_data = []
    for _, row in unique_products.iterrows():
        pid = int(row['Product_ID'])
        cat = str(row.get('Category_Name', 'General'))
        
        # Pull a realistic product name if the category matches our pool matrix
        if cat in mock_names:
            p_name = mock_names[cat][pid % len(mock_names[cat])]
        else:
            p_name = f"{cat} Utility Item #{pid}"

        if cat in mock_brands:
            p_brand = mock_brands[cat][pid % len(mock_brands[cat])]
        else:
            p_brand = "Generic Brand"
        products_data.append({
            "id": pid,
            "name": p_name,
            "category": cat,
            "brand": p_brand,
            "price": round(fake.pyfloat(min_value=10, max_value=499), 2), 
            "description": f"Premium quality {p_name} by {p_brand}, categorized under our curated {cat} collection."
        })

        
    products_df = pd.DataFrame(products_data)
    print(f"-> Uploading {len(products_df)} unique products to Neon...")
    products_df.to_sql('products', engine, if_exists='append', index=False, chunksize=1000)

    # --- PHASE 3: MAP & INGEST INTERACTIONS ---
    print("📊 Formatting interaction layers...")
    
    # Map Kaggle headers directly to your Pydantic properties
    column_mapper = {
        'User_ID': 'user_id',
        'Product_ID': 'product_id',
        'Event_Type': 'event_type'
    }
    
    interactions_df = df[['User_ID', 'Product_ID', 'Event_Type']].rename(columns=column_mapper)
    
    # Ensure all strings conform to your Literal["view", "cart", "purchase"] array rules
    interactions_df['event_type'] = interactions_df['event_type'].str.lower().str.strip()
    
    event_mapping = {
        'product_view': 'view',
        'search_click': 'view',
        'cart_add': 'cart',
        'wishlist_add': 'cart',
        'purchase': 'purchase'
    }
    interactions_df['event_type'] = interactions_df['event_type'].map(event_mapping)
    interactions_df = interactions_df[interactions_df['event_type'].isin(["view", "cart", "purchase"])]
    
    print(f"-> Streaming {len(interactions_df)} interactions to Neon in optimized chunks...")
    interactions_df.to_sql('interactions', engine, if_exists='append', index=False, chunksize=2000)
    
    print("✨ Complete! Your real e-commerce data footprint is fully inside Neon.")

if __name__ == "__main__":
    start_time = time.time()
    run_pipeline()
    print(f"⏱️ Finished in: {round(time.time() - start_time, 2)} seconds")
