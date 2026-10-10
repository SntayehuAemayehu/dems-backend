# backend/accounts/face_service.py
"""
Face verification using face_recognition (dlib backend).
Fully functional on Python 3.14 — no OpenCV, no TensorFlow.
"""

import base64
import logging
import numpy as np
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

_face_recognition = None


def _get_fr():
    global _face_recognition
    if _face_recognition is None:
        import face_recognition
        _face_recognition = face_recognition
        logger.info("✅ face_recognition loaded")
    return _face_recognition


def decode_base64_image(image_data):
    """Decode base64 → numpy RGB uint8 array."""
    try:
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        pil = Image.open(BytesIO(image_bytes)).convert('RGB')
        return np.array(pil, dtype=np.uint8)
    except Exception as e:
        logger.error(f"decode failed: {e}")
        return None


def extract_embedding(image_data):
    """
    Extract 128-dim face embedding using face_recognition (dlib).
    Returns {success, embedding, face_count, face_detected, error}
    """
    try:
        np_image = decode_base64_image(image_data)
        if np_image is None:
            return {
                'success': False,
                'face_detected': False,
                'face_count': 0,
                'error': 'Invalid image data'
            }

        fr = _get_fr()

        # Detect faces (HOG model - fast, no GPU needed)
        face_locations = fr.face_locations(np_image, model='hog')

        if len(face_locations) == 0:
            return {
                'success': False,
                'face_detected': False,
                'face_count': 0,
                'error': 'No face detected. Ensure good lighting and one face visible.'
            }

        if len(face_locations) > 1:
            return {
                'success': False,
                'face_detected': True,
                'face_count': len(face_locations),
                'error': f'{len(face_locations)} faces detected. Only one person allowed.'
            }

        # Extract 128-dim embedding
        encodings = fr.face_encodings(np_image, face_locations)

        if not encodings:
            return {
                'success': False,
                'face_detected': True,
                'face_count': 1,
                'error': 'Could not extract face embedding — try better lighting.'
            }

        embedding = encodings[0].tolist()  # 128 floats

        return {
            'success': True,
            'face_detected': True,
            'face_count': 1,
            'embedding': embedding,
            'error': None,
        }
    except Exception as e:
        logger.error(f"extract_embedding error: {e}")
        return {
            'success': False,
            'face_detected': False,
            'face_count': 0,
            'error': str(e)
        }


def compare_embeddings(emb1, emb2):
    """
    Compare two 128-dim face_recognition embeddings.
    Uses Euclidean distance. Threshold: 0.6 = same person (dlib standard).
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
                'error': f'Dimension mismatch ({a.shape} vs {b.shape})'
            }

        distance = float(np.linalg.norm(a - b))
        similarity = max(0.0, 1.0 - distance)
        match = distance < 0.6

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
            'error': str(e)
        }


def verify_against_reference(image_data, reference_embedding):
    """Verify live image against stored embedding."""
    result = extract_embedding(image_data)

    if not result['success']:
        return {
            'verified': False,
            'confidence': 0.0,
            'face_detected': result.get('face_detected', False),
            'multiple_faces': result.get('face_count', 0) > 1,
            'error': result.get('error', 'Verification failed'),
        }

    cmp = compare_embeddings(result['embedding'], reference_embedding)

    return {
        'verified': cmp['match'],
        'confidence': cmp['similarity'],
        'face_detected': True,
        'multiple_faces': False,
        'error': None if cmp['match'] else f"Identity mismatch (distance: {cmp['distance']}, threshold: 0.6)",
    }


# Aliases for backward compatibility
extract_face_embedding = extract_embedding