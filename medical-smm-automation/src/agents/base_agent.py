class MyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "Ты медицинский редактор..."
    
    async def execute(self, **kwargs) -> Dict:
        result = await self.generate(user_prompt="...")
        return result

# Использование
agent = MyAgent(name="MyAgent", openrouter=openrouter_service)
result = await agent.execute(param1="value")
stats = agent.get_stats()  # Статистика выполнения
