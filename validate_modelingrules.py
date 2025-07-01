import os
import json
import re
import yaml

FUNCTION_NAMES = {
    'concat', 'to_integer', 'to_boolean', 'to_float',
    'json_extract_scalar', 'if_else', 'lowercase', 'coalesce'
}

def find_model_files(pack_path):
    modeling_path = os.path.join(pack_path, "ModelingRules")
    models = []
    for root, _, files in os.walk(modeling_path):
        xif = next((f for f in files if f.endswith(".xif")), None)
        json_file = next((f for f in files if f.endswith(".json")), None)
        yml_file = next((f for f in files if f.endswith((".yml", ".yaml"))), None)

        if xif and json_file:
            models.append({
                'path': root,
                'xif': os.path.join(root, xif),
                'json': os.path.join(root, json_file),
                'yml': os.path.join(root, yml_file) if yml_file else None
            })
    return models

def load_schema(schema_path):
    with open(schema_path, 'r') as f:
        return json.load(f)

def extract_schema_fields(schema, parent_key=''):
    fields = set()
    for key, value in schema.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        fields.add(full_key)
        if value.get("type") == "json":
            fields.add(f"{full_key}.*")
    return fields

def extract_xdm_fields(xdm_path):
    with open(xdm_path, 'r') as f:
        content = f.read()
    alter_lines = re.findall(r'alter\s+[\w\.]+\s*=\s*(.+?);', content, flags=re.IGNORECASE)
    fields = set()
    for expr in alter_lines:
        tokens = re.split(r'[\s\(\),+*/\-]', expr)
        for token in tokens:
            token = token.strip()
            if token and token not in FUNCTION_NAMES and not token.isdigit() and not token.startswith('"'):
                fields.add(token)
    return fields

def validate_fields(xdm_fields, schema_fields):
    missing = []
    for field in xdm_fields:
        if not any(field == s or (s.endswith('.*') and field.startswith(s[:-2])) for s in schema_fields):
            missing.append(field)
    return missing

def validate_model(model):
    schema = load_schema(model['json'])
    schema_fields = extract_schema_fields(schema)
    xdm_fields = extract_xdm_fields(model['xif'])
    return validate_fields(xdm_fields, schema_fields)

def main():
    pack_path = input("Enter the top-level pack path (e.g. Packs/soc-crowdstrike-falcon): ").strip()
    if not os.path.isdir(pack_path):
        print("❌ Invalid pack path.")
        return

    all_models = find_model_files(pack_path)
    if not all_models:
        print("⚠️ No modeling rules found in this pack.")
        return

    for model in all_models:
        model_name = os.path.basename(model['path'])
        missing = validate_model(model)
        if missing:
            print(f"\n❌ Missing schema fields in model '{model_name}':")
            for field in missing:
                print(f"  - {field}")
        else:
            print(f"✅ Model '{model_name}' passed schema validation.")

if __name__ == "__main__":
    main()
