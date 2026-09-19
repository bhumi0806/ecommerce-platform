from pydantic import BaseModel, EmailStr
from typing import Optional, Literal


class UserCreate(BaseModel):
    name: str
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    category: str
    brand: Optional[str] = None
    price: float
    description: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    category: str
    brand: Optional[str]
    price: float
    description: Optional[str]

    class Config:
        from_attributes = True


class InteractionCreate(BaseModel):
    user_id: int
    product_id: int
    event_type: Literal["view", "cart", "purchase", "return"]


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    event_type: str

    class Config:
        from_attributes = True
class RecommendationResponse(BaseModel):
    product_id: int
    name: str
    category: str
    brand: Optional[str]
    price: float
    score: int