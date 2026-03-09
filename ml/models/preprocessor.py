"""
Ticket Preprocessor Module

Handles data preprocessing and feature extraction for ticket classification
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder, StandardScaler
from typing import Dict, List, Any, Tuple


class TicketPreprocessor:
    """
    Preprocessor for ticket data
    
    Handles:
    - Text vectorization (TF-IDF)
    - Categorical encoding
    - Feature scaling
    - Missing value imputation
    """
    
    def __init__(self):
        """Initialize preprocessor with default settings"""
        self.tfidf = TfidfVectorizer(
            max_features=100,
            min_df=2,
            max_df=0.8,
            ngram_range=(1, 2),
            stop_words='english'
        )
        
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.is_fitted = False
        
        # Define expected features
        self.categorical_features = ['queue', 'priority', 'language']
        self.text_features = ['subject', 'body']
    
    def fit(self, df: pd.DataFrame) -> 'TicketPreprocessor':
        """
        Fit preprocessor on training data
        
        Args:
            df: Training dataframe
            
        Returns:
            Self for method chaining
        """
        # Create combined text
        df['text_combined'] = (
            df['subject'].fillna('') + ' ' + df['body'].fillna('')
        ).str.strip()
        
        # Fit TF-IDF
        self.tfidf.fit(df['text_combined'])
        
        # Fit label encoders for categorical features
        for col in self.categorical_features:
            if col in df.columns:
                self.label_encoders[col] = LabelEncoder()
                df[col] = df[col].fillna('unknown')
                self.label_encoders[col].fit(df[col])
        
        # Fit scaler (on full feature set)
        X_sample = self._extract_features(df)
        self.scaler.fit(X_sample)
        
        self.is_fitted = True
        return self
    
    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform data using fitted preprocessor
        
        Args:
            df: Dataframe to transform
            
        Returns:
            Numpy array of features
        """
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted before transform!")
        
        return self._extract_features(df)
    
    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Fit and transform in one call
        
        Args:
            df: Training dataframe
            
        Returns:
            Numpy array of features
        """
        self.fit(df)
        return self.transform(df)
    
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract and combine all features"""
        # Text features
        df['text_combined'] = (
            df['subject'].fillna('') + ' ' + df['body'].fillna('')
        ).str.strip()
        
        text_features = self.tfidf.transform(df['text_combined'])
        
        # Length features
        df['subject_length'] = df['subject'].fillna('').astype(str).apply(len)
        df['body_length'] = df['body'].fillna('').astype(str).apply(len)
        df['text_length'] = df['text_combined'].apply(len)
        df['word_count'] = df['text_combined'].apply(lambda x: len(str(x).split()))
        
        length_features = df[['subject_length', 'body_length', 'text_length', 'word_count']].values
        
        # Categorical features
        categorical_features = []
        for col in self.categorical_features:
            if col in df.columns and col in self.label_encoders:
                df[col] = df[col].fillna('unknown')
                # Handle unseen categories
                le = self.label_encoders[col]
                encoded = df[col].map(lambda x: le.transform([x])[0] if x in le.classes_ else -1)
                categorical_features.append(encoded.values.reshape(-1, 1))
        
        if categorical_features:
            categorical_features = np.hstack(categorical_features)
        else:
            categorical_features = np.array([]).reshape(len(df), 0)
        
        # Combine all features
        X = np.hstack([
            categorical_features,
            length_features,
            text_features.toarray()
        ])
        
        return X
    
    def preprocess_single(self, ticket: Dict[str, Any]) -> np.ndarray:
        """
        Preprocess a single ticket
        
        Args:
            ticket: Dictionary with ticket data
            
        Returns:
            Feature array for single ticket
        """
        # Convert to dataframe with one row
        df = pd.DataFrame([ticket])
        return self.transform(df)
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names"""
        feature_names = []
        
        # Categorical
        feature_names.extend([f"{col}_encoded" for col in self.categorical_features 
                            if col in self.label_encoders])
        
        # Length features
        feature_names.extend(['subject_length', 'body_length', 'text_length', 'word_count'])
        
        # TF-IDF
        feature_names.extend(self.tfidf.get_feature_names_out())
        
        return feature_names


# Example usage
if __name__ == "__main__":
    # Example data
    data = {
        'subject': ['Cannot login', 'Need access', 'System down'],
        'body': ['I cannot login to my account', 'I need access to the system', 'The system is not responding'],
        'queue': ['support', 'access', 'technical'],
        'priority': ['high', 'medium', 'high'],
        'language': ['en', 'en', 'en']
    }
    
    df = pd.DataFrame(data)
    
    # Fit and transform
    preprocessor = TicketPreprocessor()
    X = preprocessor.fit_transform(df)
    
    print(f"✅ Features extracted: {X.shape}")
    print(f"✅ Feature names: {len(preprocessor.get_feature_names())}")
