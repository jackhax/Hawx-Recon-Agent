"""
Simple vector DB for storing and retrieving command/summary embeddings for Hawx Recon Agent.

Uses sentence-transformers or OpenAI embeddings if available, otherwise falls back to basic string similarity.
"""

import os
import json
import numpy as np
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    model = None

class VectorDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.data = []
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

    def add(self, command, summary):
        entry = {'command': command, 'summary': summary}
        if model:
            entry['embedding'] = model.encode(command + ' ' + summary).tolist()
        self.data.append(entry)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def search_similar(self, query, top_k=3):
        if not self.data:
            return []
        if model:
            q_emb = model.encode(query)
            sims = [np.dot(q_emb, np.array(e.get('embedding', np.zeros_like(q_emb)))) for e in self.data]
        else:
            # Fallback: simple string overlap
            sims = [len(set(query.split()) & set((e['command'] + ' ' + e['summary']).split())) for e in self.data]
        top_idx = np.argsort(sims)[::-1][:top_k]
        return [self.data[i] for i in top_idx if sims[i] > 0]
