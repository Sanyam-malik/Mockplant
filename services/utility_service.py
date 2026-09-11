import base64
import html
import json
import logging
import re
from string import Template
from typing import Any

import yaml


def yaml_to_json(yaml_str: str) -> str:
    """Converts a YAML string to a formatted JSON string."""
    data = yaml.safe_load(yaml_str)
    return json.dumps(data, indent=2)

def json_to_yaml(json_str: str) -> str:
    """Converts a JSON string to a YAML string."""
    data = json.loads(json_str)
    return yaml.dump(data, sort_keys=False, indent=2)


def get_response_content_type(content_type: str) -> str:
    """Get the appropriate content type for the response"""
    content_type = content_type.lower()

    # Map common content types
    content_type_map = {
        'json': 'application/json',
        'xml': 'application/xml',
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'javascript': 'application/javascript',
        'text': 'text/plain',
        'binary': 'application/octet-stream'
    }

    # Check if the content type is already a full MIME type
    if '/' in content_type:
        return content_type

    # Return mapped content type or default to text/plain
    return content_type_map.get(content_type, 'text/plain')

def get_content_type_headers(content_type):
    """Get appropriate headers based on content type"""
    headers = {}
    if content_type:
        headers['Content-Type'] = get_response_content_type(content_type)
    return headers


def sanitize_content(content, content_type):
    if not content:
        return content
    else:
        content_type = get_response_content_type(content_type)

    if content_type in ['text/html', 'application/xml', 'text/html']:
        # HTML encode the content to prevent rendering
        return html.escape(content)
    elif content_type == 'application/javascript':
        # Encode JavaScript content
        return f"{html.escape(content)}"
    elif content_type == 'text/css':
        # Encode CSS content
        return f"{html.escape(content)}"
    elif content_type == 'application/octet-stream':
        # For binary content, show as base64
        try:
            return f"{html.escape(base64.b64encode(content.encode('utf-8')).decode('utf-8'))}"
        except:
            return "Binary content (unable to encode)"
    return content

def desanitize_content(content, content_type):
    if not content:
        return content
    else:
        content_type = get_response_content_type(content_type)

    if content_type in ['text/html', 'application/xml', 'text/html']:
        # Unescape HTML entities
        return html.unescape(content)
    elif content_type == 'application/javascript':
        # JavaScript was HTML escaped – unescape it
        return html.unescape(content)
    elif content_type == 'text/css':
        # CSS was HTML escaped – unescape it
        return html.unescape(content)
    elif content_type == 'application/octet-stream':
        # Assume base64 encoded string; try to decode
        try:
            return base64.b64decode(html.unescape(content)).decode('utf-8')
        except Exception:
            return "Binary content (unable to decode)"
    return content

def match_conditions(source: dict, condition: dict) -> bool:
    if not isinstance(condition, dict):
        logging.error(f"Expected a dictionary but got {type(condition)}: {condition}")
        return False
    """ Match a dictionary (`source`) against `condition` rules. """
    for key, expected in condition.items():
        actual = source.get(key)

        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            if not match_conditions(actual, expected):
                return False

        elif expected == "*":
            if actual is None or actual == "":
                return False

        elif actual != expected:
            return False

    return True


def match_path_conditions(paths: dict, condition: dict):
    """Match path conditions with special handling"""
    if not isinstance(condition, dict):
        logging.error(f"Expected a dictionary but got {type(condition)}: {condition}")
        return False

    return match_conditions(paths, {key: str(value) for key, value in condition.items()})

def match_header_conditions(headers: dict, condition: dict):
    """Match header conditions with special handling"""
    if not isinstance(condition, dict):
        logging.error(f"Expected a dictionary but got {type(condition)}: {condition}")
        return False

    for key, value in headers.items():
        headers[key] = str(value).split(";")[0]

    return match_conditions({key.title(): value for key, value in headers.items()}, {key.title(): value for key, value in condition.items()})


def match_body_conditions(body: Any, condition: dict) -> bool:
    """Match body conditions with special handling for raw text bodies."""
    if not isinstance(condition, dict):
        logging.error(f"Expected a dictionary but got {type(condition)}: {condition}")
        return False

    # If body is a dictionary (JSON), use regular matching
    if isinstance(body, dict):
        return match_conditions(body, condition)

    # For non-dict bodies (raw text, XML, etc.)
    body_str = str(body)
    for key, expected in condition.items():
        if key == "search":
            # Search for text within the body
            if expected not in body_str:
                return False
        elif key == "compare":
            # Compare entire body with expected text
            if body_str != expected:
                return False
        else:
            # For other keys, treat as regular matching
            if expected == "*":
                if not body_str:
                    return False
            elif body_str != expected:
                return False
    return True


def match_path(pattern, actual_path):
    """
    Match a path pattern with $variable-style variables, e.g., /users/$id.
    Returns a tuple: (matched: bool, variables: dict)
    """
    # Convert $var to named regex group (?P<var>[^/]+)
    pattern_regex = re.sub(r"\$(\w+)", r"(?P<\1>[^/]+)", pattern)
    pattern_regex = f"^{pattern_regex}$"

    match = re.match(pattern_regex, actual_path)
    return (True, match.groupdict()) if match else (False, {})


def apply_template(content, variables):
    """ Substitute path variables and file variables in the response content string using Python's string.Template. """
    # First, handle file variables if they exist in variables
    if 'files' in variables:
        for file_key, file_data in variables['files'].items():
            # Add file-specific variables
            variables[f'{file_key}_name'] = file_data['name']
            variables[f'{file_key}_type'] = file_data['type']
            variables[f'{file_key}_content'] = file_data['content']
            variables[f'{file_key}_size'] = file_data['size']
        # Remove the files key after adding the variables
        del variables['files']

    return Template(content).safe_substitute(variables)


def parse_request_body(request_data):
    """Parse request body based on content type"""
    content_type = request_data.headers.get('Content-Type', '').lower()

    # Handle form data
    if 'multipart/form-data' in content_type:
        form_data = request_data.form.to_dict()
        # Add files to the form data
        files_data = {}
        for key, file in request_data.files.items():
            if file.filename:  # Only include files that were actually uploaded
                # Get file size by seeking to end and getting position
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()  # Get position (size)
                file.seek(0)  # Reset to beginning

                files_data[key] = {
                    'name': file.filename,
                    'type': file.content_type,
                    'content': file.read(),
                    'size': file_size
                }
        form_data["files"] = files_data
        return form_data

    # Handle URL-encoded form data
    elif 'application/x-www-form-urlencoded' in content_type:
        return request_data.form.to_dict()

    # Handle JSON
    elif 'application/json' in content_type:
        try:
            return request_data.get_json(force=True, silent=True) or {}
        except:
            return {}

    # Handle XML
    elif 'application/xml' in content_type or 'text/xml' in content_type:
        return request_data.get_data(as_text=True)

    # Handle HTML
    elif 'text/html' in content_type:
        return request_data.get_data(as_text=True)

    # Handle CSS
    elif 'text/css' in content_type:
        return request_data.get_data(as_text=True)

    # Handle JavaScript
    elif 'application/javascript' in content_type or 'text/javascript' in content_type:
        return request_data.get_data(as_text=True)

    # Handle raw text
    elif 'text/plain' in content_type:
        return request_data.get_data(as_text=True)

    # Handle binary data
    elif 'application/octet-stream' in content_type:
        return request_data.get_data()

    elif request_data.files:
        files_data = {}
        for key, file in request_data.files.items():
            if file.filename:  # Only include files that were actually uploaded
                # Get file size by seeking to end and getting position
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()  # Get position (size)
                file.seek(0)  # Reset to beginning

                files_data[key] = {
                    'name': file.filename,
                    'type': file.content_type,
                    'content': file.read(),
                    'size': file_size
                }
        return {
            "files": files_data
        }

    # Default to empty dict
    return {}