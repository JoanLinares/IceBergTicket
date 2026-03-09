"""
Snowflake Schema Generator

Generates appropriate SQL DDL statements for Snowflake Data Warehouse
based on the complexity level (BASIC/MEDIUM/PRO)
"""

import os
from typing import Dict, List, Optional
from datetime import datetime


class SnowflakeSchemaGenerator:
    """
    Generates Snowflake DW schemas based on complexity level
    """
    
    def __init__(self, schema_templates_path: Optional[str] = None):
        """
        Initialize the schema generator
        
        Args:
            schema_templates_path: Path to schema template files (markdown)
        """
        self.schema_templates_path = schema_templates_path or '../'
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load schema templates from markdown files"""
        levels = ['Basic', 'Medium', 'Pro']
        
        for level in levels:
            filename = f'snowflake{level}.md'
            filepath = os.path.join(self.schema_templates_path, filename)
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.templates[level.upper()] = f.read()
                print(f"✅ Loaded {level} schema template")
            else:
                print(f"⚠️  Template not found: {filepath}")
    
    def generate_schema(self, level: str, dataset_info: Optional[Dict] = None) -> str:
        """
        Generate SQL schema for the specified level
        
        Args:
            level: Complexity level (BASIC/MEDIUM/PRO)
            dataset_info: Optional dataset information for customization
            
        Returns:
            SQL DDL statements as string
        """
        level = level.upper()
        
        if level not in self.templates:
            raise ValueError(f"Unknown level: {level}. Must be one of: BASIC, MEDIUM, PRO")
        
        # Get base template
        schema = self.templates[level]
        
        # Add header
        header = f"""
-- ============================================================================
-- ESQUEMA DATA WAREHOUSE SNOWFLAKE - NIVEL {level}
-- Generado automáticamente por IceBergTicket ML System
-- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- ============================================================================

"""
        
        # Customize based on dataset info if provided
        if dataset_info:
            header += self._generate_dataset_info(dataset_info)
        
        return header + schema
    
    def _generate_dataset_info(self, dataset_info: Dict) -> str:
        """Generate dataset information section"""
        info = "\n-- INFORMACIÓN DEL DATASET ANALIZADO\n"
        info += "-- " + "="*76 + "\n"
        
        if 'num_rows' in dataset_info:
            info += f"-- Total de registros: {dataset_info['num_rows']:,}\n"
        
        if 'num_columns' in dataset_info:
            info += f"-- Total de columnas: {dataset_info['num_columns']}\n"
        
        if 'languages' in dataset_info:
            info += f"-- Idiomas: {', '.join(dataset_info['languages'])}\n"
        
        if 'has_tags' in dataset_info:
            info += f"-- Tags: {'Sí' if dataset_info['has_tags'] else 'No'}\n"
        
        info += "-- " + "="*76 + "\n\n"
        
        return info
    
    def save_schema(self, schema: str, output_path: str, level: str):
        """
        Save generated schema to file
        
        Args:
            schema: SQL schema string
            output_path: Directory to save the file
            level: Complexity level (for filename)
        """
        os.makedirs(output_path, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'snowflake_schema_{level.lower()}_{timestamp}.sql'
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(schema)
        
        print(f"✅ Schema saved to: {filepath}")
        return filepath
    
    def generate_and_save(self, level: str, output_path: str, 
                         dataset_info: Optional[Dict] = None) -> str:
        """
        Generate and save schema in one call
        
        Args:
            level: Complexity level
            output_path: Output directory
            dataset_info: Optional dataset information
            
        Returns:
            Path to saved schema file
        """
        schema = self.generate_schema(level, dataset_info)
        return self.save_schema(schema, output_path, level)


# Example usage
if __name__ == "__main__":
    generator = SnowflakeSchemaGenerator()
    
    dataset_info = {
        'num_rows': 28591,
        'num_columns': 15,
        'languages': ['en', 'es', 'de', 'fr', 'pt'],
        'has_tags': True
    }
    
    # Generate MEDIUM level schema
    schema = generator.generate_schema('MEDIUM', dataset_info)
    
    print("\n" + "="*80)
    print("GENERATED SCHEMA PREVIEW (first 50 lines)")
    print("="*80 + "\n")
    print('\n'.join(schema.split('\n')[:50]))
