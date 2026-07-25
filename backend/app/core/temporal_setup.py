from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings


async def get_temporal_client() -> Client:
    return await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )


async def create_worker(task_queue: str, activities: list, workflows: list) -> Worker:
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=workflows,
        activities=activities,
    )
    return worker
