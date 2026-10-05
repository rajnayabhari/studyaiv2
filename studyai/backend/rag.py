import json
import pymupdf
import chromadb
from typing import List, Dict, AsyncGenerator
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from flashrank import Ranker, RerankRequest
from backend.models import DocumentChunk

embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = ChatOllama(model="llama3.2")
ranker = Ranker()

# Initialize local ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
vectorstore = Chroma(client=chroma_client, collection_name="studyai_docs", embedding_function=embeddings)

def process_file(file_path: str, filename: str, session_id: str, db):
    doc = pymupdf.open(file_path)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    
    chunks = []
    texts_to_embed = []
    metadatas = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_content = page.get_text()
        if not text_content.strip():
            continue
        
        splits = text_splitter.split_text(text_content)
        for split in splits:
            texts_to_embed.append(split)
            metadatas.append({
                "session_id": session_id,
                "filename": filename,
                "page_number": page_num + 1
            })
            
    if not texts_to_embed:
        return
        
    # Store in ChromaDB (batched to prevent Ollama memory crashes)
    batch_size = 5
    for i in range(0, len(texts_to_embed), batch_size):
        batch_texts = texts_to_embed[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        vectorstore.add_texts(texts=batch_texts, metadatas=batch_metas)
    
    # Store metadata in SQLite for relational tracking
    for i, text_chunk in enumerate(texts_to_embed):
        db_chunk = DocumentChunk(
            session_id=session_id,
            filename=filename,
            page_number=metadatas[i]["page_number"],
            content=text_chunk
        )
        db.add(db_chunk)
    db.commit()

async def generate_rag_response(query: str, session_id: str, is_admin: bool, db) -> AsyncGenerator[str, None]:
    # 1. Vector Search using ChromaDB with metadata filtering
    filter_dict = {"session_id": session_id} if not is_admin else None
    
    # Retrieve top 25 candidates
    candidates = vectorstore.similarity_search(query, k=25, filter=filter_dict)
    
    if not candidates:
        yield {"event": "token", "data": json.dumps("No relevant documents found.")}
        yield {"event": "done", "data": "{}"}
        return

    # 2. Reranking using FlashRank
    passages = []
    for i, doc in enumerate(candidates):
        passages.append({
            "id": str(i),
            "text": doc.page_content,
            "meta": doc.metadata
        })
        
    rerankrequest = RerankRequest(query=query, passages=passages)
    reranked = ranker.rerank(rerankrequest)
    
    # Top 6 chunks
    top_chunks = reranked[:6]
    
    # Emit citations
    for chunk in top_chunks:
        meta = chunk["meta"]
        citation_data = json.dumps({"filename": meta["filename"], "page_number": meta["page_number"]})
        yield {"event": "citation", "data": citation_data}
        
    # 3. Generative Inference
    context_text = "\n\n".join([c["text"] for c in top_chunks])
    
    prompt = ChatPromptTemplate.from_template(
        "You are an Intelligent Study Assistant. Use the following context to answer the user's question.\n"
        "If you don't know the answer based on the context, say so. Keep your answer concise.\n\n"
        "Context:\n{context}\n\n"
        "Question:\n{question}"
    )
    
    chain = prompt | llm
    
    async for chunk in chain.astream({"context": context_text, "question": query}):
        content = chunk.content
        if content:
            # Escape newlines for SSE
            clean_content = json.dumps(content)
            yield {"event": "token", "data": clean_content}
            
    yield {"event": "done", "data": "{}"}
