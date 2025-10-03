from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import os
import hashlib
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Настройки (из env vars в Docker)
PERSIST_DIRECTORY = os.getenv("PERSIST_DIRECTORY", "./chroma_db")
COLLECTION_NAME = "documents"
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.28.8:11434")

# Инициализация embeddings
embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Инициализация векторной БД (persistent) с метрикой cosine
def get_vectorstore():
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIRECTORY,
        collection_metadata={"hnsw:space": "cosine"}  # Используем cosine для дистанций
    )

# Модели для API
class AddDataRequest(BaseModel):
    texts: list[str]
    metadatas: list[dict] | None = None  # Метаданные для каждого текста (опционально)

class QueryRequest(BaseModel):
    query_embedding: list[float]  # Вектор как список чисел
    k: int = 20  # Топ-K
    filter: dict | None = None  # Фильтр по метаданным (опционально)

class QueryResponse(BaseModel):
    documents: list[str]
    distances: list[float]
    metadatas: list[dict]

class DeleteRequest(BaseModel):
    ids: list[str]  # Список ID для удаления

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/add_data")
async def add_data(request: AddDataRequest):
    try:
        # Проверка соответствия количества метаданных и текстов
        if request.metadatas and len(request.metadatas) != len(request.texts):
            raise HTTPException(status_code=400, detail="Количество метаданных должно совпадать с количеством текстов")
        
        # Создаём документы с метаданными, добавляя id на основе SHA-256, если не указан
        documents = []
        for i, text in enumerate(request.texts):
            metadata = request.metadatas[i].copy() if request.metadatas else {}
            # Генерируем id как SHA-256 от текста, если id не указан
            if "id" not in metadata:
                metadata["id"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            documents.append(Document(page_content=text, metadata=metadata))
        
        # Разбиваем на чанки (если текст длинный)
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunked_docs = splitter.split_documents(documents)
        
        # Добавляем в ChromaDB
        vectorstore = get_vectorstore()
        vectorstore.add_documents(chunked_docs)
        vectorstore.persist()  # Сохранить изменения
        return {"status": "added", "count": len(chunked_docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        vectorstore = get_vectorstore()
        # Используем низкоуровневый API Chroma для поиска с фильтрацией
        results = vectorstore._collection.query(
            query_embeddings=[request.query_embedding],
            n_results=request.k,
            include=["documents", "distances", "metadatas"],
            where=request.filter
        )
        documents = results["documents"][0]
        distances = results["distances"][0]
        # Заменяем None в metadatas на пустой словарь
        metadatas = [meta if meta is not None else {} for meta in results["metadatas"][0]]
        return QueryResponse(documents=documents, distances=distances, metadatas=metadatas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete")
async def delete(request: DeleteRequest):
    try:
        vectorstore = get_vectorstore()
        # Удаляем документы по id из метаданных
        vectorstore._collection.delete(where={"id": {"$in": request.ids}})
        vectorstore.persist()  # Сохранить изменения
        return {"status": "deleted", "ids": request.ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
