class PublishTask(BaseModel):
    """Задача на публикацию поста"""
    task_id: str
    channel_id: str              # @profgynecologist
    text: str                    # Markdown текст
    scheduled_time: datetime     # Когда публиковать
    status: TaskStatus           # pending/scheduled/completed/failed
    message_id: Optional[int]    # ID опубликованного сообщения
    
    # Медиа
    photo_url: Optional[str]
    video_url: Optional[str]
    buttons: Optional[List[Dict]]
    
    # Повторные попытки
    retry_count: int = 0
    max_retries: int = 3
