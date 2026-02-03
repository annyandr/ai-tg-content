validator = PostValidator()

# Полная валидация
result = validator.validate(content="🍑 **Пост**...", specialty="гинекология")
print(result.is_valid)  # True/False
print(result.issues)    # ['Проблема 1', 'Проблема 2']

# Быстрая проверка
is_ok = validator.quick_check(content)

# Оценка качества (0.0 - 1.0)
score = validator.get_validation_score(content, specialty)
