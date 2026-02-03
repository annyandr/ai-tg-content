"""API Client for Medical SMM Bot Backend"""
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime


class MedicalSMMAPIClient:
    """Client for Medical SMM Bot API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # Tasks API
    async def create_task(self, task_data: Dict[str, Any]) -> Dict:
        """Create new publish task"""
        async with self.session.post(
            f"{self.base_url}/api/v1/tasks",
            json=task_data
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get list of tasks"""
        params = {"limit": limit}
        if status:
            params["status"] = status

        async with self.session.get(
            f"{self.base_url}/api/v1/tasks",
            params=params
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_task(self, task_id: str) -> Dict:
        """Get task details"""
        async with self.session.get(
            f"{self.base_url}/api/v1/tasks/{task_id}"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def cancel_task(self, task_id: str) -> Dict:
        """Cancel task"""
        async with self.session.delete(
            f"{self.base_url}/api/v1/tasks/{task_id}"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_stats(self) -> Dict:
        """Get task statistics"""
        async with self.session.get(
            f"{self.base_url}/api/v1/tasks/stats"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Content API
    async def generate_content(
        self,
        topic: str,
        specialty: str,
        post_type: str = "клинрекомендации",
        max_length: int = 2000
    ) -> Dict:
        """Generate post content"""
        async with self.session.post(
            f"{self.base_url}/api/v1/content/generate",
            json={
                "topic": topic,
                "specialty": specialty,
                "post_type": post_type,
                "max_length": max_length
            }
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Channels API
    async def list_channels(self) -> List[Dict]:
        """Get list of channels"""
        async with self.session.get(
            f"{self.base_url}/api/v1/channels"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_specialties(self) -> List[Dict]:
        """Get list of specialties"""
        async with self.session.get(
            f"{self.base_url}/api/v1/specialties"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # System API
    async def health_check(self) -> Dict:
        """Check API health"""
        async with self.session.get(
            f"{self.base_url}/api/v1/system/health"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def system_stats(self) -> Dict:
        """Get system statistics"""
        async with self.session.get(
            f"{self.base_url}/api/v1/system/stats"
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
