from pydantic import BaseModel
from typing import Optional, List, Literal, Dict
from datetime import datetime

class LoginRequest(BaseModel):
    id_token: str

class SignupRequest(BaseModel):
    id_token: str
    role: Literal["SELLER", "BUYER"]
    store_name: Optional[str] = None
    market: Optional[str] = None
    stall_no: Optional[str] = None

class SimpleOK(BaseModel):
    ok: bool = True

class UserOut(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    role: str
    store_name: Optional[str]
    market: Optional[str]
    stall_no: Optional[str]
    class Config:
        from_attributes = True

class ReviewCreate(BaseModel):
    kindness: int
    price: int
    variety: int

class ReviewStats(BaseModel):
    total: int
    kindness: Dict[str, int]
    price: Dict[str, int]
    variety: Dict[str, int]

class ProductItem(BaseModel):
    name: str
    price: Optional[str] = None
    time_min: int
    time_sec: int
    time_ms: int
    image_url: Optional[str] = None  # ← 호버 미리보기용 이미지 경로

class PostOut(BaseModel):
    id: int
    created_at: datetime
    content: Optional[str] = None
    video_url: Optional[str] = None
    ply_url: Optional[str] = None
    traj_url: Optional[str] = None
    points_url: Optional[str] = None
    status: Optional[str] = None
    log_url: Optional[str] = None
    store_name: Optional[str] = None
    market: Optional[str] = None
    stall_no: Optional[str] = None
    review_stats: Optional[ReviewStats] = None
    ai_summary: Optional[str] = None
    products: Optional[List[ProductItem]] = None
