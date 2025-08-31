from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)
    name = Column(String, nullable=True)

    role = Column(String, nullable=False, default="BUYER")

    store_name = Column(String, nullable=True)
    market = Column(String, nullable=True)
    stall_no = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="author")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 콘텐츠/파일 경로
    content = Column(String, nullable=True)
    video_path = Column(String, nullable=True)
    ply_path = Column(String, nullable=True)
    traj_path = Column(String, nullable=True)
    points_path = Column(String, nullable=True)

    # 처리 상태/로그
    status = Column(String, nullable=True, default=None)     # "processing" | "done" | "error" | None
    log_path = Column(String, nullable=True)                 # e.g. "logs/abcd.log"

    # AI 요약(소개문) 캐시
    ai_summary = Column(Text, nullable=True)

    author = relationship("User", back_populates="posts")
    reviews = relationship("Review", back_populates="post", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)

    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    kindness = Column(Integer, nullable=False, default=0)
    price = Column(Integer, nullable=False, default=0)
    variety = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_review_post_user"),
    )
