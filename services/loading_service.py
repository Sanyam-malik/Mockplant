import os
from dataclasses import is_dataclass, asdict
import logging

import yaml
from typing import Dict, Any

from services.constant_service import IMPOSTERS_FOLDER

from entity.imposter_model import Imposter, ImposterMetadata, ResponseEntry, Predicate, Response
from services.utility_service import sanitize_content, get_response_content_type, desanitize_content

class LiteralString(str): pass


def literal_str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(LiteralString, literal_str_representer)


class YamlDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(YamlDumper, self).increase_indent(flow, False)


def parse_imposter_yaml(data: Dict[str, Any]) -> Imposter:
    """Parse a YAML dictionary into an Imposter object."""
    # Use the ImposterMetadata dataclass for metadata
    metadata = ImposterMetadata(**data["imposter"])

    predicates = []
    for pred_obj in data["predicates"]:
        pred_data = pred_obj.get("predicate", pred_obj)
        responses = []

        for resp_data in pred_obj.get('responses', []):
            resp = resp_data.get('response', {})
            content_type = get_response_content_type(resp.get('content_type', 'text/plain'))
            content = sanitize_content(resp.get('content', ''), content_type)

            response = Response(
                code=int(resp.get('code', 200)),
                content_type=content_type,
                headers=resp.get('headers', {}),
                content=content
            )

            response_entry = ResponseEntry(
                response=response,
                when=resp_data.get('when', {})
            )
            responses.append(response_entry)

        # Support both a single 'workflow' and a list of 'workflows' in YAML
        # Both are normalized into the 'workflows' list on the Predicate
        single_workflow = pred_data.get("workflow") or {}
        workflows_data = pred_data.get("workflows") or []
        workflows = []
        if isinstance(workflows_data, list):
            workflows = workflows_data
        elif isinstance(workflows_data, dict) and workflows_data:
            workflows = [workflows_data]
        elif isinstance(single_workflow, dict) and single_workflow:
            workflows = [single_workflow]

        predicate = Predicate(
            method=pred_data["method"],
            path=pred_data["path"],
            delay=pred_data.get("delay"),
            force_response=pred_data.get("force_response"),
            responses=responses,
            workflows=workflows
        )
        predicates.append(predicate)

    return Imposter(imposter=metadata, predicates=predicates)


def save_imposter(data: Imposter):
    if not os.path.exists(IMPOSTERS_FOLDER):
        os.makedirs(IMPOSTERS_FOLDER)
    filename = data.imposter.file
    if filename is not None and filename == "":
        return False
    imposter = to_custom_yaml(data)
    file_path = os.path.join(IMPOSTERS_FOLDER, filename)
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            f.write(imposter)
        logging.info(f"✅ Imposter file Updated: {filename}")
        return True
    except Exception as e:
        logging.error(f"❌ Error in updating imposter {filename}: {e}")
        return False


def delete_imposter(data: Imposter):
    filename = data.imposter.file
    file_path = os.path.join(IMPOSTERS_FOLDER, filename)
    if not os.path.exists(file_path):
        return False
    else:
        os.remove(file_path)
        return True


def load_yaml_imposters(folder=IMPOSTERS_FOLDER):
    """Load YAML imposters from disk into the global list."""
    imposters = []

    if not os.path.exists(folder):
        os.makedirs(folder)

    for filename in os.listdir(folder):
        if not filename.endswith((".yaml", ".yml")):
            continue

        file_path = os.path.join(folder, filename)
        with open(file_path, "r") as f:
            try:
                raw = yaml.safe_load(f)
                raw["imposter"]["file"] = filename
                imposter_obj = parse_imposter_yaml(raw)
                imposters.append(imposter_obj)
                logging.info(f"✅ Loaded imposter: {imposter_obj.imposter.name}")
            except Exception as e:
                logging.error(f"❌ Error in {filename}: {e}")

    return sorted(imposters, key=lambda d: d.imposter.file)


def reload_imposters():
    return load_yaml_imposters(IMPOSTERS_FOLDER)

def clean_data(data, exclude_keys=None):
    """
    Recursively remove keys with None or blank string values from a dataclass dictionary.
    Also removes explicitly excluded keys.
    """
    if exclude_keys is None:
        exclude_keys = set()

    if isinstance(data, dict):
        return {
            k: clean_data(v, exclude_keys)
            for k, v in data.items()
            if k not in exclude_keys and v not in (None, "") and v
        }
    elif isinstance(data, list):
        return [clean_data(item, exclude_keys) for item in data if item not in (None, "")]
    else:
        return data


def to_custom_yaml(imposter_instance: Imposter) -> str:
    """
    Convert an Imposter instance to YAML:
    - Exclude 'file'
    - Nest 'predicate' and 'responses' under each predicate entry
    - Remove None or empty string fields
    """
    if not is_dataclass(imposter_instance):
        raise TypeError("Expected a dataclass instance")

    data = asdict(imposter_instance)

    # Clean imposter metadata and remove 'file'
    metadata = clean_data(data['imposter'], exclude_keys={'file'})

    # Restructure predicates as list of {'predicate': ..., 'responses': [...]}
    predicate_entries = []
    for pred in data['predicates']:
        pred_copy = pred.copy()
        responses = pred_copy.pop('responses', [])
        for response in responses:
            response_obj = response['response']
            content_type = get_response_content_type(response_obj.get('content_type', 'text/plain'))
            content = desanitize_content(response_obj.get('content', ''), content_type)
            if isinstance(content, str) and '\n' in content:
                response_obj['content'] = LiteralString(desanitize_content(content, content_type))
            else:
                response_obj['content'] = desanitize_content(content, content_type)
        entry = {
            'predicate': clean_data(pred_copy),
            'responses': [clean_data(r) for r in responses]
        }
        predicate_entries.append(entry)

    # Final structure
    yaml_data = {
        'imposter': metadata,
        'predicates': predicate_entries
    }

    return yaml.dump(
        yaml_data,
        sort_keys=False,
        default_flow_style=False,
        Dumper=YamlDumper
    )
