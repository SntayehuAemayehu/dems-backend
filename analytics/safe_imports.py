# backend/analytics/safe_imports.py
# ✅ Central place for optional imports — other files import from here

import logging
logger = logging.getLogger(__name__)

# Numpy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False
    logger.warning("⚠️ numpy not available")

# Pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False
    logger.warning("⚠️ pandas not available")

# Scikit-learn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    import joblib
    SKLEARN_AVAILABLE = True
    ML_AVAILABLE = True
    logger.info("✅ sklearn loaded")
except ImportError:
    TfidfVectorizer = None
    cosine_similarity = None
    RandomForestClassifier = None
    StandardScaler = None
    train_test_split = None
    accuracy_score = None
    precision_score = None
    recall_score = None
    f1_score = None
    joblib = None
    SKLEARN_AVAILABLE = False
    ML_AVAILABLE = False
    logger.warning("⚠️ sklearn not available")

# Python-magic (optional)
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False
    logger.warning("⚠️ python-magic not available")

__all__ = [
    'np', 'pd', 'magic',
    'TfidfVectorizer', 'cosine_similarity',
    'RandomForestClassifier', 'StandardScaler',
    'train_test_split', 'accuracy_score', 'precision_score',
    'recall_score', 'f1_score', 'joblib',
    'NUMPY_AVAILABLE', 'PANDAS_AVAILABLE',
    'SKLEARN_AVAILABLE', 'ML_AVAILABLE', 'MAGIC_AVAILABLE',
]