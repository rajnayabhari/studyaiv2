import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.models import Base, User, ChatSession, DocumentChunk
from backend.auth import create_access_token, get_current_user

# Test Database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db_session():
    # Since sqlite doesn't support pgvector, we skip full pgvector extension creation 
    # but we can test the relationships and basic queries.
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_jwt_authentication():
    # Test token creation and validation
    token = create_access_token({"sub": "test@example.com", "is_admin": True})
    user_data = get_current_user(token)
    assert user_data["email"] == "test@example.com"
    assert user_data["is_admin"] == True

def test_on_delete_cascade_sync(db_session):
    # Create user
    user = User(email="test@cascade.com", is_admin=False)
    db_session.add(user)
    db_session.commit()
    
    # Create session
    session = ChatSession(id="session-123", user_id=user.id)
    db_session.add(session)
    db_session.commit()
    
    # Create chunk
    chunk = DocumentChunk(
        session_id="session-123",
        filename="test.pdf",
        page_number=1,
        content="Test content",
        # Mocking embedding for sqlite
        embedding=[0.1] * 768 
    )
    db_session.add(chunk)
    db_session.commit()
    
    assert db_session.query(DocumentChunk).count() == 1
    
    # Delete session - should cascade to chunk
    db_session.delete(session)
    db_session.commit()
    
    assert db_session.query(DocumentChunk).count() == 0

def test_multi_tenant_metadata_filtering(db_session):
    """
    Test that queries would correctly filter by session_id or is_admin.
    We test the logic by verifying the generated SQL or utilizing basic SQLAlchemy filters.
    """
    session1 = ChatSession(id="session-A")
    session2 = ChatSession(id="session-B")
    db_session.add_all([session1, session2])
    db_session.commit()
    
    chunk1 = DocumentChunk(session_id="session-A", filename="A.pdf", page_number=1, content="A", embedding=[0.1]*768)
    chunk2 = DocumentChunk(session_id="session-B", filename="B.pdf", page_number=1, content="B", embedding=[0.2]*768)
    db_session.add_all([chunk1, chunk2])
    db_session.commit()
    
    # Simulating the query logic from rag.py
    # User A can only see session A
    current_session = "session-A"
    is_admin = False
    
    results = db_session.query(DocumentChunk).filter(
        (DocumentChunk.session_id == current_session) | (is_admin == True)
    ).all()
    
    assert len(results) == 1
    assert results[0].session_id == "session-A"
    
    # Admin can see all (if we filter using OR is_admin=True)
    is_admin = True
    results_admin = db_session.query(DocumentChunk).filter(
        (DocumentChunk.session_id == current_session) | (is_admin == True)
    ).all()
    
    assert len(results_admin) == 2

