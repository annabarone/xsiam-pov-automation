import re
import json
import sys
from pathlib import Path
import argparse

KNOWN_FUNCTIONS = {
    "concat", "to_string", "to_integer", "to_float", "to_boolean",
    "lowercase", "upper", "coalesce", "if_else", "substring",
    "format_time", "strlen", "round"
}

def infer_type(expr, field):
    if re.search(rf'to_integer\s*\(\s*{re.escape(field)}\s*\)', expr):
        return "int"
    return "string"

def parse_xif(content):
    dataset_match = re.search(r'dataset\s*=\s*"([^"]+)"', content)
    dataset = dataset_match.group(1) if dataset_match else None
    if not dataset:
        raise ValueError("No dataset found in XIF file.")

    content_clean = re.sub(r'"[^"]*"', '', content)

    filter_fields = set()
    filter_match = re.search(r'filter\s+(.+?)\|', content_clean, re.DOTALL)
    if filter_match:
        filter_text = filter_match.group(1)
        tokens = re.findall(r'\b[\w]+\b|\b\w+\s*->\s*\w+', filter_text)
        for token in tokens:
            token = token.strip()
            if '->' in token:
                parent = token.split('->')[0].strip()
                filter_fields.add((parent, "json", False))
            elif token and token not in KNOWN_FUNCTIONS:
                filter_fields.add((token, "string", False))

    fields = {}
    sugar_parents = set()
    alter_match = re.search(r'alter\s+(.*?);', content_clean, re.DOTALL)
    if not alter_match:
        raise ValueError("No alter clause found in XIF file.")

    alter_body = alter_match.group(1)
    assignments = [a.strip() for a in re.split(r',\s*(?=\w)', alter_body) if a.strip()]

    for assignment in assignments:
        if '=' not in assignment:
            continue
        _, rhs = assignment.split('=', 1)
        rhs = rhs.strip()

        tokens = re.findall(r'\b[\w]+\[\]?\b|\b\w+\s*->\s*\w+|\b\w+', rhs)
        for token in tokens:
            token = token.strip()
            if token in KNOWN_FUNCTIONS:
                continue
            if '->' in token:
                parent = token.split('->')[0].strip()
                sugar_parents.add(parent)
                if parent not in fields:
                    fields[parent] = {"type": "json", "is_array": False}
            elif token.endswith('[]'):
                base_field = token[:-2]
                if base_field in sugar_parents:
                    continue
                fields[base_field] = {"type": infer_type(rhs, base_field), "is_array": True}
            else:
                if any(token == p for p in sugar_parents):
                    continue
                if any(token.startswith(p + '->') for p in sugar_parents):
                    continue
                if token not in fields:
                    fields[token] = {"type": infer_type(rhs, token), "is_array": False}

    for (fname, ftype, farray) in filter_fields:
        if fname not in fields:
            fields[fname] = {"type": ftype, "is_array": farray}

    return dataset, fields

def validate_schema(xif_dataset, xif_fields, json_dataset, json_fields):
    errors = []

    if xif_dataset != json_dataset:
        errors.append(f"Dataset mismatch: XIF dataset='{xif_dataset}' vs JSON dataset='{json_dataset}'")

    xif_keys = set(xif_fields.keys())
    json_keys = set(json_fields.keys())

    missing_in_json = xif_keys - json_keys
    extra_in_json = json_keys - xif_keys

    if missing_in_json:
        errors.append(f"Fields missing in JSON: {sorted(missing_in_json)}")
    if extra_in_json:
        errors.append(f"Extra fields in JSON not in XIF: {sorted(extra_in_json)}")

    for key in xif_keys & json_keys:
        if xif_fields[key]['type'] != json_fields[key]['type'] or xif_fields[key]['is_array'] != json_fields[key]['is_array']:
            errors.append(f"Type or array mismatch for field '{key}': XIF={xif_fields[key]} vs JSON={json_fields[key]}")

    return errors

def process_modelingrules_folder(path):
    path = Path(path)
    if not path.is_dir():
        raise ValueError(f"Path {path} is not a directory")

    for xif_path in path.rglob("*.xif"):
        print(f"Processing {xif_path}")
        with xif_path.open() as f:
            xif_content = f.read()
        try:
            xif_dataset, xif_fields = parse_xif(xif_content)
        except Exception as e:
            print(f"ERROR parsing XIF: {e}")
            continue

        schema_path = xif_path.with_name(xif_path.stem + "_schema.json")

        if schema_path.exists():
            # Validate against existing schema json
            with schema_path.open() as jf:
                try:
                    json_schema = json.load(jf)
                    json_dataset = next(iter(json_schema.keys()))
                    json_fields = json_schema[json_dataset]
                except Exception as e:
                    print(f"ERROR loading JSON schema {schema_path}: {e}")
                    continue

            errors = validate_schema(xif_dataset, xif_fields, json_dataset, json_fields)
            if errors:
                print(f"Validation errors for {schema_path}:")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"{schema_path} is valid against XIF.")
        else:
            # Generate and save schema
            schema = {xif_dataset: xif_fields}
            with schema_path.open("w") as out_file:
                json.dump(schema, out_file, indent=2)
            print(f"Generated schema saved to {schema_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate or validate Cortex XSIAM XDM schemas from .xif ModelingRules files.\n\n"
                    "For each .xif file under the given ModelingRules folder:\n"
                    "- If the corresponding _schema.json file does not exist, it is generated from the .xif.\n"
                    "- If the _schema.json file exists, the script validates that it matches the .xif fields.\n\n"
                    "Usage:\n"
                    "  python generate_xdm_schema.py <path_to_ModelingRules_folder>\n"
    )
    parser.add_argument('folder', help="Path to the ModelingRules folder")

    args = parser.parse_args()
    process_modelingrules_folder(args.folder)

if __name__ == "__main__":
    main()
