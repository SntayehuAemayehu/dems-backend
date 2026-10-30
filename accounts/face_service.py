# backend/accounts/face_service.py
import cv2
import numpy as np
import base64
import logging
from uniface import FaceAnalyzer
from uniface import RetinaFace
retina = RetinaFace()

logger = logging.getLogger(__name__)

# Initialize UniFace — no args needed in v4.x
try:
    analyzer = FaceAnalyzer()
    logger.info("✅ UniFace FaceAnalyzer initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize UniFace: {e}")
    analyzer = None


def decode_base64_image(image_data):
    try:
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Decode error: {e}")
        return None


def extract_embedding(image_data):
    if analyzer is None:
        return {'success': False, 'error': 'Face analyzer not initialized'}

    img = decode_base64_image(image_data)
    if img is None:
        return {'success': False, 'error': 'Invalid image'}

    try:
        faces = analyzer.analyze(img)
        if len(faces) == 0:
            return {'success': False, 'face_count': 0, 'error': 'No face detected'}
        
        # UniFace returns a list of Face objects, each with .embedding
        emb = faces[0].embedding
        if hasattr(emb, 'tolist'):
            emb = emb.tolist()
        
        return {
            'success': True,
            'face_count': len(faces),
            'embedding': emb,
        }
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return {'success': False, 'error': str(e)}


def compare_embeddings(emb1, emb2):
    """
    Compare two embeddings using cosine similarity.
    Returns {match, similarity, distance, error}
    """
    try:
        a = np.array(emb1, dtype=np.float64)
        b = np.array(emb2, dtype=np.float64)

        if a.shape != b.shape:
            return {
                'match': False,
                'similarity': 0.0,
                'distance': 1.0,
                'error': f'Dimension mismatch ({a.shape} vs {b.shape})',
            }

        # Cosine similarity
        norm_a = a / np.linalg.norm(a)
        norm_b = b / np.linalg.norm(b)
        similarity = float(np.dot(norm_a, norm_b))
        distance = float(1.0 - similarity)

        # ArcFace threshold: similarity > 0.6 = same person
        match = similarity > 0.6

        return {
            'match': bool(match),
            'similarity': round(similarity, 4),
            'distance': round(distance, 4),
            'error': None,
        }
    except Exception as e:
        logger.error(f"compare error: {e}")
        return {
            'match': False,
            'similarity': 0.0,
            'distance': 1.0,
            'error': str(e),
        }



def count_faces_in_image(image_data):
    """Returns the number of faces detected in a base64 image."""
    try:
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        np_arr = np.frombuffer(base64.b64decode(image_data), np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            return 0
        
        # Detect faces using RetinaFace
        faces = retina.detect(img)
        return len(faces)
    except Exception as e:
        print(f"Count faces error: {e}")
        return 0
def verify_against_reference(image_data, reference_embedding):
    result = extract_embedding(image_data)

    if not result['success']:
        return {
            'verified': False,
            'error': result.get('error'),
            'face_detected': False,
            'multiple_faces': result.get('face_count', 0) > 1,
        }

    if result['face_count'] > 1:
        return {
            'verified': False,
            'error': 'Multiple faces detected. Only one person allowed.',
            'face_detected': True,
            'multiple_faces': True,
        }

    cmp = compare_embeddings(result['embedding'], reference_embedding)

    return {
        'verified': bool(cmp['match']),
        'confidence': cmp['similarity'],
        'face_detected': True,
        'multiple_faces': False,
        'error': (
            None
            if cmp['match']
            else f"Your face does not match the enrolled student (similarity: {cmp['similarity']:.2f})"
        ),
    }


# Aliases for backward compatibility
extract_face_embedding = extract_embedding