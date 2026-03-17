import asyncio
import logging
from src.db.session import async_session_maker
from src.rag.indexer import index_documents
from src.rag.embeddings import index_knowledge_base

logging.basicConfig(level=logging.INFO)

async def main():
    async with async_session_maker() as db:
        docs = await index_documents(db)
        print(f"Indexed docs: {docs}")
        emb = await index_knowledge_base(db)
        print(f"Generated embeddings for: {emb}")

if __name__ == "__main__":
    asyncio.run(main())
