import os
import random
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. Initialize environments and Database Engine
load_dotenv()

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

def inject_return_anomalies():
    print("⏳ Scanning Neon database for completed purchases...")
    
    with engine.begin() as conn:
        # Fetch all successful purchases from the interaction logs
        result = conn.execute(text("SELECT id, product_id FROM interactions WHERE event_type = 'purchase';"))
        purchases = [dict(row) for row in result.mappings()]
        
        if not purchases:
            print("❌ Error: No purchase interactions found in Neon. Run 'ingest_pipeline.py' first!")
            return
            
        print(f"📊 Found {len(purchases)} purchase rows to analyze.")

        # Extract unique product IDs that have been bought
        product_ids = list(set(p['product_id'] for p in purchases))
        
        # 2. Designate "Bad Actor" Products (High-Risk Anomalies)
        # We select 5 random products to artificially flood with returns
        bad_actors = random.sample(product_ids, min(5, len(product_ids)))
        print(f"🛑 Injecting extreme return rates (>50%) into target products: {bad_actors}")

        return_count = 0
        update_ids = []

        # 3. Process the return injection matrix
        for p in purchases:
            pid = p['product_id']
            row_id = p['id']

            if pid in bad_actors:
                # 55% chance of returning this item if it's a bad actor product
                if random.random() < 0.55:
                    update_ids.append(row_id)
            else:
                # Standard retail baseline: ~10% chance of a return for ordinary items
                if random.random() < 0.10:
                    update_ids.append(row_id)

        # 4. Bulk update changed rows to 'return' in Neon using chunks to protect database buffer
        chunk_size = 500
        for i in range(0, len(update_ids), chunk_size):
            chunk = update_ids[i:i + chunk_size]
            conn.execute(
                text("UPDATE interactions SET event_type = 'return' WHERE id = ANY(:ids);"),
                {"ids": chunk}
            )
            return_count += len(chunk)

        print(f"✨ Successfully injected {return_count} total 'return' events into Neon!")

if __name__ == "__main__":
    inject_return_anomalies()
