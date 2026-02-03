"""Generic response schemas"""
from pydantic import BaseModel, Field
from typing import Any, Optional


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class SuccessResponse(BaseModel):
    """Schema for success responses"""
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Additional data")
