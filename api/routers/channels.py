"""Channels and specialties API endpoints"""
from fastapi import APIRouter
from typing import List, Dict
import json
from pathlib import Path

from src.agents.specialty_loader import SPECIALTY_MAP

router = APIRouter(prefix="/api/v1", tags=["channels"])


@router.get("/channels")
async def list_channels() -> List[Dict]:
    """Get list of all channels"""
    channels_file = Path("data/channels.json")

    if not channels_file.exists():
        return []

    with open(channels_file, "r", encoding="utf-8") as f:
        channels = json.load(f)

    return channels


@router.get("/specialties")
async def list_specialties() -> List[Dict]:
    """Get list of all medical specialties"""
    specialties = []

    for key, config in SPECIALTY_MAP.items():
        specialties.append({
            "key": key,
            "name": config["name"],
            "emoji": config.get("emoji", ""),
            "available": True
        })

    return specialties
