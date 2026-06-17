import sys
import os
import yaml

# Add backend to path so we can import pipeline
sys.path.append(os.path.abspath('c:/Users/surji/HPE_CPP49/backend'))

from pipeline.schema_loader import load_schema
from pipeline.validator import SQLValidator

def validate_all_examples():
    schema_loader = load_schema("c:/Users/surji/HPE_CPP49/backend/schema_store/enriched_schema.yaml")
    schema = schema_loader.get_schema()
    validator = SQLValidator(schema)
    
    with open('c:/Users/surji/HPE_CPP49/backend/few_shots/examples.yaml', 'r') as f:
        examples = yaml.safe_load(f)['examples']
        
    errors_found = {}
    
    for i, ex in enumerate(examples):
        sql = ex['sql'].replace('%db%', 'machd500')
        result = validator.validate(sql)
        if not result.valid:
            errors_found[i+1] = {
                'query': ex['query'],
                'errors': [result.error] if result.error else ["Unknown error"]
            }
            
    if errors_found:
        print(f"Found errors in {len(errors_found)} examples:")
        for idx, details in errors_found.items():
            print(f"\nExample {idx}: {details['query']}")
            for err in details['errors']:
                print(f"  - {err}")
    else:
        print("All examples perfectly match the current schema!")

if __name__ == "__main__":
    validate_all_examples()
