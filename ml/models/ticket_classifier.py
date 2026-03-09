"""
Ticket Classifier Module

Multi-objective classifier that predicts:
1. Ticket type (Incident/Request/Problem)
2. Language (en/es/de/fr/pt)
3. Snowflake DW level (BASIC/MEDIUM/PRO)
"""

import os
import joblib
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class TicketClassifier:
    """
    Multi-objective ticket classifier
    
    This class handles three simultaneous classification tasks:
    - Ticket type classification
    - Language detection
    - Snowflake Data Warehouse level determination
    """
    
    def __init__(self, model_path: str, timestamp: Optional[str] = None):
        """
        Initialize the TicketClassifier
        
        Args:
            model_path: Path to the directory containing trained models
            timestamp: Specific model timestamp to load (optional)
        """
        self.model_path = model_path
        self.timestamp = timestamp
        
        # Load models
        self.model_type = None
        self.model_language = None
        self.model_snowflake = None
        self.scaler = None
        self.label_encoders = None
        self.metadata = None
        
        self._load_models()
    
    def _load_models(self):
        """Load all trained models from disk"""
        try:
            # Find model files
            if self.timestamp:
                pattern = f"*_{self.timestamp}.pkl"
            else:
                # Load most recent models
                pattern = "*.pkl"
            
            model_files = [f for f in os.listdir(self.model_path) if f.endswith('.pkl')]
            
            # Load each model
            for file in model_files:
                filepath = os.path.join(self.model_path, file)
                
                if 'model_type' in file:
                    self.model_type = joblib.load(filepath)
                    print(f"✅ Loaded type classifier: {file}")
                    
                elif 'model_language' in file:
                    self.model_language = joblib.load(filepath)
                    print(f"✅ Loaded language classifier: {file}")
                    
                elif 'model_snowflake' in file:
                    self.model_snowflake = joblib.load(filepath)
                    print(f"✅ Loaded snowflake classifier: {file}")
                    
                elif 'scaler' in file:
                    self.scaler = joblib.load(filepath)
                    print(f"✅ Loaded scaler: {file}")
                    
                elif 'label_encoders' in file:
                    self.label_encoders = joblib.load(filepath)
                    print(f"✅ Loaded label encoders: {file}")
                    
                elif 'metadata' in file:
                    with open(filepath, 'rb') as f:
                        self.metadata = pickle.load(f)
                    print(f"✅ Loaded metadata: {file}")
            
            # Verify all models loaded
            if not all([self.model_type, self.model_language, self.model_snowflake, self.scaler]):
                raise ValueError("Not all required models were loaded!")
                
        except Exception as e:
            raise RuntimeError(f"Error loading models: {str(e)}")
    
    def preprocess(self, ticket_data: Dict[str, Any]) -> np.ndarray:
        """
        Preprocess raw ticket data into model input format
        
        Args:
            ticket_data: Dictionary containing ticket information
            
        Returns:
            Preprocessed feature array
        """
        # TODO: Implement preprocessing pipeline
        # This should include:
        # - Text feature extraction (TF-IDF)
        # - Categorical encoding
        # - Feature scaling
        pass
    
    def predict(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict all three objectives for a given ticket
        
        Args:
            ticket_data: Dictionary containing ticket information
            
        Returns:
            Dictionary with predictions and confidence scores
        """
        # Preprocess input
        X = self.preprocess(ticket_data)
        
        # Scale features if needed
        X_scaled = self.scaler.transform(X.reshape(1, -1))
        
        # Make predictions
        type_pred = self.model_type.predict(X_scaled)[0]
        language_pred = self.model_language.predict(X_scaled)[0]
        snowflake_pred = self.model_snowflake.predict(X_scaled)[0]
        
        # Get confidence scores (if available)
        type_proba = None
        language_proba = None
        snowflake_proba = None
        
        if hasattr(self.model_type, 'predict_proba'):
            type_proba = self.model_type.predict_proba(X_scaled)[0].tolist()
            language_proba = self.model_language.predict_proba(X_scaled)[0].tolist()
            snowflake_proba = self.model_snowflake.predict_proba(X_scaled)[0].tolist()
        
        return {
            'type': type_pred,
            'language': language_pred,
            'snowflake_level': snowflake_pred,
            'confidence_scores': {
                'type': type_proba,
                'language': language_proba,
                'snowflake': snowflake_proba
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def predict_batch(self, tickets: list) -> list:
        """
        Predict for multiple tickets at once
        
        Args:
            tickets: List of ticket dictionaries
            
        Returns:
            List of prediction dictionaries
        """
        return [self.predict(ticket) for ticket in tickets]
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about loaded models
        
        Returns:
            Dictionary with model metadata
        """
        return self.metadata if self.metadata else {
            'type_model': str(type(self.model_type).__name__),
            'language_model': str(type(self.model_language).__name__),
            'snowflake_model': str(type(self.model_snowflake).__name__),
            'loaded_at': datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Example of how to use the classifier
    classifier = TicketClassifier(
        model_path='../model_artifacts/',
        timestamp=None  # Use most recent models
    )
    
    # Example ticket
    ticket = {
        'subject': 'Cannot access my account',
        'body': 'I am unable to log in to my account. I get an error message.',
        'priority': 'high',
        'queue': 'technical_support',
        'tags': ['login', 'authentication']
    }
    
    # Make prediction
    result = classifier.predict(ticket)
    
    print("\n" + "="*80)
    print("PREDICTION RESULTS")
    print("="*80)
    print(f"\nTicket Type: {result['type']}")
    print(f"Language: {result['language']}")
    print(f"Snowflake Level: {result['snowflake_level']}")
    print(f"\nConfidence Scores: {result['confidence_scores']}")
