import numpy as np
from ..models import FaceTemplate, Student
from ..extensions import db

class InMemoryGallery:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InMemoryGallery, cls).__new__(cls)
            cls._instance._loaded = False
            cls._instance.embeddings = None
            cls._instance.student_ids = None
        return cls._instance
        
    def refresh(self):
        """Load all active face templates into numpy arrays for fast matching"""
        templates = FaceTemplate.query.join(Student).filter(
            FaceTemplate.is_active == True,
            Student.is_active == True
        ).all()
        
        if not templates:
            self.embeddings = np.array([])
            self.student_ids = np.array([])
            self._loaded = True
            return
            
        emb_list = []
        id_list = []
        
        for t in templates:
            # Convert bytes back to numpy array (512 float32)
            emb = np.frombuffer(t.embedding, dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            emb_list.append(emb)
            id_list.append(t.student_id)
            
        self.embeddings = np.vstack(emb_list)
        self.student_ids = np.array(id_list)
        self._loaded = True
        
    def match(self, query_embedding, config, enforce_margin=True):
        """
        Match a query embedding against the gallery.
        Returns: (student_id, best_score, second_best_score) or (None, best_score, second_best_score)
        """
        if not self._loaded:
            self.refresh()
            
        if self.embeddings is None or len(self.embeddings) == 0:
            return None, 0.0, 0.0
            
        # Normalize query embedding
        query_embedding = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm
            
        # Cosine similarity
        similarities = np.dot(self.embeddings, query_embedding)
        
        # We need the max similarity PER STUDENT
        unique_students = np.unique(self.student_ids)
        student_scores = []
        
        for sid in unique_students:
            # Find indices for this student
            idx = np.where(self.student_ids == sid)[0]
            # Max score among their templates
            max_sim = np.max(similarities[idx])
            student_scores.append((int(sid), float(max_sim)))
            
        # Sort by score descending
        student_scores.sort(key=lambda x: x[1], reverse=True)
        
        best_sid, best_score = student_scores[0]
        second_best_score = student_scores[1][1] if len(student_scores) > 1 else 0.0
        
        t_accept = float(config.get('T_ACCEPT', 0.60))
        t_margin = float(config.get('T_MARGIN', 0.10))
        
        # Accept rule
        if best_score >= t_accept:
            if not enforce_margin or (best_score - second_best_score >= t_margin):
                return best_sid, best_score, second_best_score
                
        return None, best_score, second_best_score

def get_gallery():
    return InMemoryGallery()
