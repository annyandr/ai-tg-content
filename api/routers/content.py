"""Content generation API endpoints"""
from fastapi import APIRouter, Depends, HTTPException

from api.schemas.content import ContentGenerateRequest, ContentGenerateResponse
from api.dependencies import get_content_generator
from src.services.content_generator import ContentGeneratorService

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/generate", response_model=ContentGenerateResponse)
async def generate_content(
    request: ContentGenerateRequest,
    generator: ContentGeneratorService = Depends(get_content_generator)
):
    """Generate post content using AI"""
    try:
        result = await generator.generate_from_topic(
            topic=request.topic,
            specialty=request.specialty,
            post_type=request.post_type,
            max_length=request.max_length
        )

        return ContentGenerateResponse(
            content=result["content"],
            specialty=request.specialty,
            post_type=request.post_type,
            topic=request.topic
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")
