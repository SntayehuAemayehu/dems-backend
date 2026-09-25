#!/bin/bash
echo "🚀 Installing AI libraries (one by one to avoid memory issues)..."

pip install --no-cache-dir torch==2.9.0
pip install --no-cache-dir torchvision==0.24.0
pip install --no-cache-dir torchaudio==2.9.0
pip install --no-cache-dir transformers==4.46.3
pip install --no-cache-dir sentence-transformers==3.3.1
pip install --no-cache-dir opencv-python==4.13.0.90
pip install --no-cache-dir opencv-contrib-python==4.13.0.90
pip install --no-cache-dir mediapipe==0.10.33
pip install --no-cache-dir scikit-learn==1.6.0
pip install --no-cache-dir pandas==2.2.3
pip install --no-cache-dir numpy==2.2.0
pip install --no-cache-dir scipy==1.14.0
pip install --no-cache-dir matplotlib==3.9.3
pip install --no-cache-dir seaborn==0.13.2
pip install --no-cache-dir networkx==3.4.2
pip install --no-cache-dir scikit-image==0.24.0
pip install --no-cache-dir joblib==1.4.2
pip install --no-cache-dir tqdm==4.67.1
pip install --no-cache-dir spacy==3.8.2
pip install --no-cache-dir gensim==4.3.3
pip install --no-cache-dir textblob==0.18.0
pip install --no-cache-dir pytextrank==3.3.1

echo "✅ AI libraries installed!"