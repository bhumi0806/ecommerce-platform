from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models


# How strongly each interaction indicates user interest
EVENT_WEIGHTS = {
    "view": 1,
    "cart": 3,
    "purchase": 5,
}


def get_recommendations(
    user_id: int,
    db: Session,
    limit: int = 5
):
    # Get all interactions made by this user
    interactions = (
        db.query(models.Interaction)
        .filter(models.Interaction.user_id == user_id)
        .all()
    )

    if not interactions:
        return []

    # --------------------------------------------------
    # STEP 1: Calculate category preferences
    # --------------------------------------------------

    category_scores = {}

    for interaction in interactions:

        product = (
            db.query(models.Product)
            .filter(models.Product.id == interaction.product_id)
            .first()
        )

        if not product:
            continue

        weight = EVENT_WEIGHTS.get(interaction.event_type, 0)

        category_scores[product.category] = (
            category_scores.get(product.category, 0) + weight
        )

    # --------------------------------------------------
    # STEP 2: Find products already purchased
    # --------------------------------------------------

    purchased_products = {
        interaction.product_id
        for interaction in interactions
        if interaction.event_type == "purchase"
    }

    # --------------------------------------------------
    # STEP 3: Score candidate products
    # --------------------------------------------------

    products = (
        db.query(models.Product)
        .all()
    )

    scored_products = []

    for product in products:

        # Don't recommend something the user already purchased
        if product.id in purchased_products:
            continue

        category_score = category_scores.get(
            product.category,
            0
        )

        if category_score == 0:
            continue

        scored_products.append(
            {
                "product": product,
                "score": category_score
            }
        )

    # --------------------------------------------------
    # STEP 4: Sort by recommendation score
    # --------------------------------------------------

    scored_products.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return scored_products[:limit]