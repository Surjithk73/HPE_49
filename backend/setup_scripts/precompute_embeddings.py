import os
import sys
import numpy as np
from sentence_transformers import SentenceTransformer

# Ensure we can import from pipeline
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pipeline.schema_loader import load_schema

def main():
    print("Precomputing schema embeddings...")
    base_dir = os.path.dirname(os.path.dirname(__file__))
    schema_path = os.path.join(base_dir, 'schema_store', 'enriched_schema.yaml')
    out_path = os.path.join(base_dir, 'schema_store', 'schema_embeddings.npz')

    loader = load_schema(schema_path)
    schema = loader.get_schema()

    print("Loading BAAI/bge-large-en-v1.5 model...")
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")

    # 1. Table embeddings
    table_names = []
    table_texts = []
    for table_name, table_def in schema.items():
        if not (isinstance(table_def, dict) and 'columns' in table_def):
            continue
        table_names.append(table_name)
        parts = [table_name]
        if 'entity_type' in table_def: parts.append(str(table_def['entity_type']))
        if 'purpose' in table_def: parts.append(str(table_def['purpose']))
        for ident in table_def.get('identity_columns', []) or []:
            parts.append(str(ident))
        for col_name, col_def in table_def.get('columns', {}).items():
            if not isinstance(col_def, dict): continue
            parts.append(col_name.replace('_', ' '))
            desc = col_def.get('description', '')
            if desc: parts.append(desc)
        table_texts.append(' '.join(parts))

    print(f"Embedding {len(table_texts)} tables...")
    table_embeddings = np.asarray(model.encode(table_texts, normalize_embeddings=True))

    save_dict = {
        'table_names': table_names,
        'table_embeddings': table_embeddings,
    }

    print("Embedding columns...")
    for table_name in table_names:
        table_def = schema[table_name]
        columns = table_def.get('columns', {})
        candidates = []
        for col_name, col_def in columns.items():
            if not isinstance(col_def, dict) or not col_def.get('queryable', True):
                continue
            candidates.append((col_name, col_def))
        
        if not candidates:
            continue

        candidate_names = [name for name, _ in candidates]
        docs = []
        for col_name, col_def in candidates:
            parts = [col_name.replace('_', ' ').replace('.', ' ')]
            desc = col_def.get('description', '')
            if desc: parts.append(desc)
            unit = col_def.get('unit')
            if unit: parts.append(str(unit))
            docs.append(' '.join(parts))

        matrix = np.asarray(model.encode(docs, normalize_embeddings=True))
        save_dict[f"{table_name}_col_names"] = candidate_names
        save_dict[f"{table_name}_col_embeddings"] = matrix
        print(f"  - {table_name}: {len(candidates)} columns")

    print(f"Saving to {out_path}...")
    np.savez_compressed(out_path, **save_dict)
    print("Done!")

if __name__ == "__main__":
    main()
