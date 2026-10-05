from fastapi import FastAPI, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
import os
import tempfile
import uuid

from backend.database import init_db, get_db
from backend.models import ChatSession
from backend.auth import get_current_user
from backend.rag import process_file, generate_rag_response

app = FastAPI(title="StudyAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/sessions")
def create_session(db: Session = Depends(get_db)):
    # Create an anonymous session or link to user if we had full auth
    session_id = str(uuid.uuid4())
    db_session = ChatSession(id=session_id)
    db.add(db_session)
    db.commit()
    return {"session_id": session_id}

@app.post("/upload")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Save file temporarily
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    process_file(file_path, file.filename, session_id, db)
    return {"message": "Document ingestion completed"}

@app.get("/chat")
async def chat(
    query: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    # Skipping get_current_user for simplicity in this endpoints since we use a dummy user
    # Or assuming user is not admin by default
    is_admin = False
    return EventSourceResponse(generate_rag_response(query, session_id, is_admin, db))

# Dummy auth endpoint for demonstration
@app.post("/auth/google")
def auth_google():
    from backend.auth import create_access_token
    return {"access_token": create_access_token({"sub": "user@example.com", "is_admin": False})}

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
