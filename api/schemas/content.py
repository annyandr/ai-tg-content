"""Content generation schemas"""
from pydantic import BaseModel, Field
from typing import Optional


class ContentGenerateRequest(BaseModel):
    """Schema for content generation request"""
    topic: str = Field(..., description="Topic for content generation")
    specialty: str = Field(..., description="Medical specialty")
    post_type: str = Field(default="клинрекомендации", description="Type of post")
    max_length: int = Field(default=2000, description="Maximum content length", ge=100, le=4096)


class ContentGenerateResponse(BaseModel):
    """Schema for content generation response"""
    content: str = Field(..., description="Generated content")
    specialty: str = Field(..., description="Medical specialty used")
    post_type: str = Field(..., description="Post type")
    topic: str = Field(..., description="Original topic")
