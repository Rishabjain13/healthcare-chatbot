"""
RAG (Retrieval-Augmented Generation) Service for Healthcare Chatbot
Handles retrieval of detailed treatment information from knowledge base
"""

import os
import pickle
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np

# Vector DB - using FAISS for simplicity
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("Warning: FAISS not installed. RAG features will be limited.")

# Embeddings - using sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not installed. RAG features will be limited.")


class RAGService:
    """
    Retrieval-Augmented Generation service for answering detailed questions
    using clinic's knowledge base (treatment protocols, FAQs, etc.)
    """

    def __init__(
        self,
        knowledge_base_dir: str = "knowledge_base",
        index_path: str = "knowledge_base/vector_index.faiss",
        metadata_path: str = "knowledge_base/metadata.pkl",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)

        # Initialize embedding model
        self.embedding_model_name = embedding_model
        self.embedder = None
        self.index = None
        self.metadata = []

        # Create directories if needed
        self.knowledge_base_dir.mkdir(exist_ok=True)

        # Initialize components
        self._initialize_embedder()
        self._load_or_create_index()

    def _initialize_embedder(self):
        """Initialize the sentence embedding model"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("Sentence Transformers not available. RAG will use mock embeddings.")
            return

        try:
            self.embedder = SentenceTransformer(self.embedding_model_name)
            print(f"Loaded embedding model: {self.embedding_model_name}")
        except Exception as e:
            print(f"Error loading embedding model: {e}")

    def _load_or_create_index(self):
        """Load existing index or create new one"""
        if self.index_path.exists() and self.metadata_path.exists():
            self._load_index()
        else:
            self._create_new_index()

    def _load_index(self):
        """Load existing FAISS index and metadata"""
        if not FAISS_AVAILABLE:
            return

        try:
            self.index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
            print(f"Loaded index with {len(self.metadata)} documents")
        except Exception as e:
            print(f"Error loading index: {e}")
            self._create_new_index()

    def _create_new_index(self):
        """Create a new FAISS index"""
        if not FAISS_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("FAISS or sentence-transformers not available. Skipping index creation.")
            return

        # Create a new index (384 dimensions for all-MiniLM-L6-v2)
        embedding_dim = 384
        self.index = faiss.IndexFlatL2(embedding_dim)
        self.metadata = []
        print("Created new FAISS index")

    def add_document(
        self,
        text: str,
        title: str,
        category: str = "general",
        metadata: Optional[Dict] = None
    ):
        """
        Add a document to the knowledge base

        Args:
            text: Document text content
            title: Document title
            category: Document category (e.g., 'treatment', 'lab_tests', 'pricing')
            metadata: Additional metadata
        """
        if not self.embedder or not self.index:
            print("Embedder or index not initialized. Cannot add document.")
            return

        # Split document into chunks (for long documents)
        chunks = self._chunk_text(text, max_chunk_size=500)

        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = self.embedder.encode([chunk])[0]

            # Add to FAISS index
            self.index.add(np.array([embedding], dtype=np.float32))

            # Store metadata
            doc_metadata = {
                'text': chunk,
                'title': title,
                'category': category,
                'chunk_id': i,
                'total_chunks': len(chunks)
            }
            if metadata:
                doc_metadata.update(metadata)

            self.metadata.append(doc_metadata)

        print(f"Added document '{title}' with {len(chunks)} chunks")

    def _chunk_text(self, text: str, max_chunk_size: int = 500) -> List[str]:
        """Split text into chunks for better retrieval"""
        # Simple chunking by sentences/paragraphs
        sentences = text.split('. ')

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            if current_size + sentence_size > max_chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append('. '.join(current_chunk) + '.')
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size

        # Add remaining chunk
        if current_chunk:
            chunks.append('. '.join(current_chunk) + '.')

        return chunks if chunks else [text]

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve relevant documents for a query

        Args:
            query: User's question
            top_k: Number of top results to return
            category_filter: Optional category to filter by

        Returns:
            List of relevant document chunks with metadata
        """
        if not self.embedder or not self.index or len(self.metadata) == 0:
            return self._get_fallback_results(query)

        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query])[0]

            # Search in FAISS index
            distances, indices = self.index.search(
                np.array([query_embedding], dtype=np.float32),
                min(top_k * 2, len(self.metadata))  # Get more results for filtering
            )

            # Retrieve metadata for results
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.metadata):
                    doc = self.metadata[idx].copy()
                    doc['score'] = float(1 / (1 + distance))  # Convert distance to similarity score

                    # Apply category filter if specified
                    if category_filter is None or doc.get('category') == category_filter:
                        results.append(doc)

                    if len(results) >= top_k:
                        break

            return results

        except Exception as e:
            print(f"Error during retrieval: {e}")
            return self._get_fallback_results(query)

    def _get_fallback_results(self, query: str) -> List[Dict]:
        """Fallback results when RAG is not available"""
        return [{
            'text': "I can provide general information about our treatments. For detailed, personalized advice, please book a consultation with our doctor.",
            'title': 'General Information',
            'category': 'fallback',
            'score': 0.5
        }]

    def generate_answer(
        self,
        query: str,
        retrieved_docs: List[Dict],
        max_context_length: int = 1000
    ) -> str:
        """
        Generate an answer based on retrieved documents

        Args:
            query: User's question
            retrieved_docs: Retrieved document chunks
            max_context_length: Maximum context to use

        Returns:
            Generated answer
        """
        if not retrieved_docs:
            return "I don't have specific information about that. Please contact our clinic or book a consultation for personalized advice."

        # Combine retrieved documents into context
        context_parts = []
        total_length = 0

        for doc in retrieved_docs:
            text = doc['text']
            if total_length + len(text) <= max_context_length:
                context_parts.append(f"- {text}")
                total_length += len(text)

        context = '\n'.join(context_parts)

        # Simple template-based generation (can be replaced with LLM)
        answer = f"""Based on our clinic's knowledge base:

{context}

💡 **Note:** This information is general. For personalized treatment recommendations, please book a consultation with our doctor who can assess your specific situation.

Would you like to book an appointment to discuss this further?"""

        return answer

    def save_index(self):
        """Save the FAISS index and metadata to disk"""
        if not self.index or not FAISS_AVAILABLE:
            return

        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            print(f"Saved index with {len(self.metadata)} documents")
        except Exception as e:
            print(f"Error saving index: {e}")

    def load_documents_from_directory(self, directory: Optional[str] = None):
        """
        Load all documents from a directory into the knowledge base

        Args:
            directory: Path to directory with text/markdown files
        """
        if directory is None:
            directory = self.knowledge_base_dir / "documents"

        doc_dir = Path(directory)
        if not doc_dir.exists():
            print(f"Directory {doc_dir} does not exist. Creating sample documents...")
            self._create_sample_documents()
            return

        # Load all .txt and .md files
        for file_path in doc_dir.glob("**/*.txt"):
            self._load_document_file(file_path)

        for file_path in doc_dir.glob("**/*.md"):
            self._load_document_file(file_path)

        # Save the index
        self.save_index()

    def _load_document_file(self, file_path: Path):
        """Load a single document file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract category from directory structure or filename
            category = file_path.parent.name if file_path.parent.name != 'documents' else 'general'

            self.add_document(
                text=content,
                title=file_path.stem,
                category=category
            )
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    def _create_sample_documents(self):
        """Create sample documents for demonstration"""
        sample_docs_dir = self.knowledge_base_dir / "documents"
        sample_docs_dir.mkdir(parents=True, exist_ok=True)

        # Sample treatment protocols
        samples = [
            {
                'filename': 'adrenal_fatigue_treatment.txt',
                'category': 'treatment',
                'content': """Adrenal Fatigue Treatment Protocol

Overview:
Adrenal fatigue is a condition where the adrenal glands are unable to produce adequate amounts of cortisol and other stress hormones. Our comprehensive treatment approach addresses the root causes.

Common Symptoms:
- Chronic fatigue, especially in morning and afternoon
- Difficulty waking up despite adequate sleep
- Salt and sugar cravings
- Decreased stress tolerance
- Brain fog and difficulty concentrating
- Weakened immune system

Treatment Approach:
1. Comprehensive Testing:
   - Salivary cortisol testing (4-point throughout the day)
   - DHEA levels
   - Complete hormone panel
   - Nutrient deficiency testing (B vitamins, vitamin C, magnesium)

2. Nutritional Support:
   - Adaptogenic herbs (Ashwagandha, Rhodiola, Holy Basil)
   - B-complex vitamins
   - Vitamin C (1000-2000mg daily)
   - Magnesium glycinate (300-400mg)
   - Quality protein at each meal

3. Lifestyle Modifications:
   - Stress management techniques (meditation, breathing exercises)
   - Adequate sleep (7-9 hours, consistent schedule)
   - Gentle exercise (avoid overtraining)
   - Blood sugar stabilization (regular meals, avoid refined carbs)

Treatment Timeline:
- Initial improvements: 2-4 weeks (energy, sleep)
- Moderate improvements: 6-8 weeks (stress tolerance)
- Full recovery: 3-6 months depending on severity

Side Effects:
Most supplements are well-tolerated. Potential mild side effects:
- Adaptogenic herbs: Occasional digestive upset (take with food)
- High-dose vitamin C: Loose stools (reduce dose if occurs)
- Magnesium: Loose stools at high doses

When to Seek Immediate Care:
Contact us if you experience severe symptoms like extreme weakness, dizziness, rapid weight loss, or persistent nausea."""
            },
            {
                'filename': 'gut_health_protocols.txt',
                'category': 'treatment',
                'content': """Gut Health and SIBO Treatment Protocols

Understanding Gut Health:
The gut microbiome plays a crucial role in overall health, affecting digestion, immunity, mood, and metabolism. Our functional medicine approach addresses root causes of gut dysfunction.

Common Gut Issues We Treat:
- SIBO (Small Intestinal Bacterial Overgrowth)
- IBS (Irritable Bowel Syndrome)
- Candida overgrowth
- Leaky gut syndrome
- Food sensitivities
- Chronic bloating and gas

SIBO Treatment Protocol:
1. Testing:
   - Breath test (hydrogen/methane)
   - Comprehensive stool analysis
   - Food sensitivity panel (IgG)

2. Treatment Phases:

   Phase 1 - Eradication (2-4 weeks):
   - Antimicrobial herbs (Berberine, Oregano oil, Neem)
   - Or prescription antibiotics (Rifaximin) if severe
   - Low FODMAP diet

   Phase 2 - Restoration (4-8 weeks):
   - Probiotics (specific strains)
   - Prebiotics (gradual introduction)
   - Digestive enzymes
   - L-glutamine for gut lining repair

   Phase 3 - Prevention:
   - Prokinetics (to prevent recurrence)
   - Stress management
   - Dietary modifications

Dietary Recommendations:
- Eliminate: Gluten, dairy, refined sugars, alcohol (initially)
- Include: Bone broth, fermented foods, leafy greens, quality proteins
- Low FODMAP foods during treatment phase

Expected Timeline:
- Symptom improvement: 2-3 weeks
- Complete treatment: 8-12 weeks
- Retest: After 3 months

Maintenance:
- Continued digestive support
- Stress management
- Regular meal timing
- Avoid antibiotics unless necessary"""
            },
            {
                'filename': 'hormone_balancing.txt',
                'category': 'treatment',
                'content': """Hormone Balancing and Thyroid Treatment

Comprehensive Hormone Health:
Hormonal imbalances affect energy, weight, mood, sleep, and overall well-being. We use advanced testing to identify and address root causes.

Thyroid Disorders:
Our approach goes beyond TSH testing to include:
- Free T3 and Free T4
- Reverse T3
- Thyroid antibodies (TPO, TG)
- Nutrients affecting thyroid (iodine, selenium, zinc)

Treatment for Hypothyroidism:
1. Medication optimization:
   - Natural desiccated thyroid or synthetic T4/T3
   - Regular monitoring and dose adjustments

2. Nutritional support:
   - Selenium (200mcg daily)
   - Zinc (15-30mg)
   - Vitamin D
   - Iodine (if deficient, careful dosing)

3. Lifestyle factors:
   - Gluten elimination (especially with Hashimoto's)
   - Stress reduction
   - Adequate sleep
   - Regular exercise

PCOS (Polycystic Ovary Syndrome):
Natural treatment approach:
- Inositol (especially myo-inositol + d-chiro-inositol)
- Berberine or Metformin for insulin resistance
- Anti-inflammatory diet
- Spearmint tea (for hirsutism)
- NAC (N-Acetyl Cysteine)

Menopause Support:
Bio-identical hormone replacement when appropriate:
- Estrogen (various delivery methods)
- Progesterone
- Testosterone (if deficient)

Natural alternatives:
- Black cohosh
- Maca root
- Vitamin E
- Phytoestrogens (flax seeds, soy)

Testing Schedule:
- Initial: Comprehensive hormone panel
- Follow-up: 6-8 weeks after starting treatment
- Maintenance: Every 3-6 months"""
            }
        ]

        for doc in samples:
            file_path = sample_docs_dir / doc['filename']
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(doc['content'])

        print(f"Created {len(samples)} sample documents in {sample_docs_dir}")


# Global instance
_rag_service = None


def get_rag_service() -> RAGService:
    """Get or create global RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
        # Load documents on first initialization
        _rag_service.load_documents_from_directory()
    return _rag_service


if __name__ == "__main__":
    # Test the RAG service
    print("Initializing RAG service...")
    rag = get_rag_service()

    # Test query
    test_query = "What are the side effects of adrenal fatigue treatment?"
    print(f"\nTest Query: {test_query}")

    results = rag.retrieve(test_query, top_k=3)
    print(f"\nRetrieved {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['title']} (Score: {result['score']:.3f})")
        print(f"   {result['text'][:200]}...")

    answer = rag.generate_answer(test_query, results)
    print(f"\nGenerated Answer:\n{answer}")
