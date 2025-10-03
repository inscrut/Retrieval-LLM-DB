# Retrieval API на основе ChromaDB

Это API на базе FastAPI для управления и поиска векторизованных документов с использованием ChromaDB. Поддерживает добавление документов с опциональными метаданными, поиск по векторным эмбеддингам и удаление документов по идентификатору. API интегрируется с [Ollama](https://ollama.com/) для генерации эмбеддингов и использует метрику косинусного сходства для векторного поиска.

## Возможности
- **Добавление документов**: Сохранение текстов с опциональными метаданными, автоматическая генерация уникальных идентификаторов с использованием SHA-256, если `id` не указан.
- **Поиск документов**: Выполнение векторного поиска с опциональной фильтрацией по метаданным.
- **Удаление документов**: Удаление документов по их идентификаторам из метаданных.
- **Проверка состояния**: Проверка доступности API.
- **Постоянное хранение**: Использует ChromaDB с постоянной директорией (`/app/chroma_db`).

## Требования
- Docker и Docker Compose
- Python 3.12 (используется в контейнере Docker)
- Сервер Ollama, работающий по адресу `http://192.168.28.8:11434` с моделью `nomic-embed-text`
- Зависимости, указанные в `requirements.txt`

## Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd chromadb-retrieval
```

### 2. Подготовка директории для хранения
Создайте директорию для хранения данных ChromaDB:
```bash
mkdir -p chroma_db
chmod -R 777 chroma_db
```

### 3. Настройка окружения
API использует переменные окружения, заданные в `docker-compose.yml`:
- `PERSIST_DIRECTORY`: Путь к хранилищу ChromaDB (`/app/chroma_db`).
- `OLLAMA_BASE_URL`: URL сервера Ollama (`http://192.168.28.8:11434`).
- `OLLAMA_EMBED_MODEL`: Модель эмбеддингов (`nomic-embed-text`).

Убедитесь, что сервер Ollama работает:
```bash
curl http://192.168.28.8:11434
# Должно вернуть: Ollama is running
```

### 4. Сборка и запуск
```bash
docker-compose up --build -d
```

Проверьте логи, чтобы убедиться, что API запущено:
```bash
docker logs $(docker ps -q --filter "ancestor=chromadb-retrieval")
```

API будет доступно по адресу `http://192.168.28.5:8000`.

### 5. Тестирование API
Проверьте, что API работает:
```bash
curl http://192.168.28.5:8000/health
# Ожидаемый ответ: {"status": "healthy"}
```

## Эндпоинты API

### 1. Проверка состояния
- **Эндпоинт**: `GET /health`
- **Описание**: Проверяет, работает ли API.
- **Ответ**:
  ```json
  {"status": "healthy"}
  ```

**Пример**:
```bash
curl http://192.168.28.5:8000/health
```

### 2. Добавление данных
- **Эндпоинт**: `POST /add_data`
- **Описание**: Добавляет список текстов в ChromaDB, опционально с метаданными. Для каждого текста автоматически генерируется уникальный `id` (SHA-256 хеш текста), если он не указан в метаданных. Длинные тексты разбиваются на чанки (1000 символов, перекрытие 200 символов).
- **Тело запроса**:
  ```json
  {
    "texts": ["строка"],
    "metadatas": [{"ключ": "значение"}] | null
  }
  ```
  - `texts`: Список текстов для сохранения.
  - `metadatas`: Опциональный список словарей метаданных. Если указан, должен соответствовать количеству текстов. Если `id` не указан, генерируется SHA-256.
- **Ответ**:
  ```json
  {
    "status": "added",
    "count": число
  }
  ```
- **Ошибки**:
  - `400`: Если количество метаданных не совпадает с количеством текстов.
  - `500`: Для внутренних ошибок (например, Ollama недоступен).

**Пример**:
```bash
curl -X 'POST' \
  'http://192.168.28.5:8000/add_data' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "texts": [
      "Неодим - это проект, нацеленный на создание бесконтактных систем зажигания на базе старых распределителей зажигания с контактной системой зажигания",
      "БСЗ - бесконтактная система зажигания"
    ],
    "metadatas": [
      {"source": "project_description", "category": "ignition_systems"},
      {"source": "glossary", "category": "ignition_systems"}
    ]
  }'
```
**Ответ**:
```json
{"status": "added", "count": 2}
```

### 3. Поиск документов
- **Эндпоинт**: `POST /query`
- **Описание**: Выполняет поиск по векторному сходству с использованием переданного эмбеддинга, с опциональной фильтрацией по метаданным. Возвращает топ `k` документов, их дистанции и метаданные.
- **Тело запроса**:
  ```json
  {
    "query_embedding": [число],
    "k": число,
    "filter": {"ключ": "значение"} | null
  }
  ```
  - `query_embedding`: Список чисел с плавающей точкой, представляющий вектор запроса (генерируется Ollama).
  - `k`: Количество возвращаемых результатов (по умолчанию: 20).
  - `filter`: Опциональный словарь для фильтрации по метаданным (например, `{"category": "ignition_systems"}`).
- **Ответ**:
  ```json
  {
    "documents": ["строка"],
    "distances": [число],
    "metadatas": [{"ключ": "значение"}]
  }
  ```
- **Ошибки**:
  - `500`: Для внутренних ошибок (например, Ollama недоступен).

**Пример**:
```bash
curl -X 'POST' \
  'http://192.168.28.5:8000/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "query_embedding": [0.08556647598743439, 0.04794132336974144, -2.4628958702087402, ..., -0.9685643315315247],
    "k": 5,
    "filter": {"category": "ignition_systems"}
  }'
```
**Ответ** (пример):
```json
{
  "documents": [
    "БСЗ - бесконтактная система зажигания",
    "Неодим - это проект..."
  ],
  "distances": [
    0.12,
    0.15
  ],
  "metadatas": [
    {"source": "glossary", "category": "ignition_systems", "id": "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"},
    {"source": "project_description", "category": "ignition_systems", "id": "b948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a448"}
  ]
}
```

### 4. Удаление документов
- **Эндпоинт**: `POST /delete`
- **Описание**: Удаляет документы по их идентификаторам из метаданных.
- **Тело запроса**:
  ```json
  {
    "ids": ["строка"]
  }
  ```
  - `ids`: Список идентификаторов документов для удаления (из метаданных).
- **Ответ**:
  ```json
  {
    "status": "deleted",
    "ids": ["строка"]
  }
  ```
- **Ошибки**:
  - `500`: Для внутренних ошибок.

**Пример**:
```bash
curl -X 'POST' \
  'http://192.168.28.5:8000/delete' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "ids": ["a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"]
  }'
```
**Ответ**:
```json
{
  "status": "deleted",
  "ids": ["a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"]
}
```

## Наполнение базы данных
Для наполнения базы используйте эндпоинт `/add_data`. Вы можете:
1. **Вручную через cURL**: Отправляйте отдельные запросы, как показано выше.
2. **Использовать скрипт**: Напишите Python-скрипт для отправки пакетов данных (см. `populate_db.py` ниже).
3. **Использовать n8n**: Создайте workflow для чтения данных из файла и отправки в `/add_data` (см. `n8n_populate_db.json`).

### Пример: Python-скрипт для наполнения
Создайте файл `populate_db.py`:
```python
import json
import requests

ADD_DATA_URL = "http://192.168.28.5:8000/add_data"

data = [
    {
        "text": "Неодим - это проект, нацеленный на создание бесконтактных систем зажигания на базе старых распределителей зажигания с контактной системой зажигания",
        "metadata": {"source": "project_description", "category": "ignition_systems"}
    },
    {
        "text": "БСЗ - бесконтактная система зажигания",
        "metadata": {"source": "glossary", "category": "ignition_systems"}
    }
]

def add_data_batch(texts, metadatas=None):
    payload = {"texts": texts}
    if metadatas:
        payload["metadatas"] = metadatas
    response = requests.post(ADD_DATA_URL, json=payload, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    return response.json()

def populate_db(data, batch_size=100):
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        texts = [item["text"] for item in batch]
        metadatas = [item["metadata"] for item in batch]
        try:
            result = add_data_batch(texts, metadatas)
            print(f"Добавлен пакет {i//batch_size + 1}: {result}")
        except Exception as e:
            print(f"Ошибка при добавлении пакета {i//batch_size + 1}: {e}")

if __name__ == "__main__":
    populate_db(data)
```
Запустите:
```bash
python populate_db.py
```

### Пример: Файл данных
Создайте файл `data.json`:
```json
[
    {
        "text": "Неодим - это проект...",
        "metadata": {"source": "project_description", "category": "ignition_systems"}
    },
    {
        "text": "БСЗ - бесконтактная система зажигания",
        "metadata": {"source": "glossary", "category": "ignition_systems"}
    }
]
```

## Примечания
- **Метаданные**: Каждый документ может содержать метаданные (например, `source`, `category`). Если `id` не указан, он генерируется как SHA-256 хеш текста.
- **Дистанции**: API использует косинусное сходство (`hnsw:space: cosine`), поэтому дистанции обычно в диапазоне [0, 2].
- **Чанки**: Тексты длиннее 1000 символов разбиваются на чанки с перекрытием 200 символов.
- **Обработка ошибок**: Проверяйте логи при сбоях:
  ```bash
  docker logs $(docker ps -q --filter "ancestor=chromadb-retrieval")
  ```

## Устранение неполадок
- **Ollama недоступен**: Убедитесь, что сервер Ollama работает по адресу `http://192.168.28.8:11434`.
- **Большие дистанции**: Если дистанции в `/query` не в диапазоне [0, 2], попробуйте модель `mxbai-embed-large`, изменив `OLLAMA_EMBED_MODEL=mxbai-embed-large` в `docker-compose.yml`.
- **Сброс базы**: Данные хранятся в `./chroma_db`. Для очистки:
  ```bash
  rm -rf chroma_db
  mkdir -p chroma_db
  chmod -R 777 chroma_db
  docker-compose down
  docker-compose up --build -d
  ```

## Будущие улучшения
- Добавить эндпоинт `/update` для изменения существующих документов по `id`.
- Интеграция с n8n для автоматизированных процессов (например, RAG: Webhook → Embedding → Retrieval → Rerank → Generation).
- Переход на `pgvector` для хранения векторов в PostgreSQL.
