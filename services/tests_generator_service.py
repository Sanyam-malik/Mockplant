import os
import json
import re
import logging

from services.constant_service import BASE_URL, TESTS_FILE
from services.fallback_service import fallback_responses
from services.loading_service import reload_imposters
from services.time_service import TimeConverterService
from services.utility_service import get_content_type_headers, apply_template


def substitute_path_variables(path, path_vars=None):
    if path_vars:
        for key, value in path_vars.items():
            path = path.replace(str("$"+key), str(value))
    """Convert $param-style variables to test values (e.g., $id → 123)."""
    return re.sub(r'\$(\w+)', lambda m: "123", path)

def extract_path_params(path, path_vars=None):
    """Extract $param variables from path and map them to test values like {'id': '123'}."""
    vars_dict = {match[1:]: "123" for match in re.findall(r"\$\w+", path)}
    if path_vars:
        for key, value in path_vars.items():
            vars_dict[key] = str(value)
    return vars_dict

def build_url(path, imposter_type, path_vars=None, query=None):
    base = f"{BASE_URL[imposter_type]}{substitute_path_variables(path, path_vars)}"
    if query:
        q = "&".join(f"{k}={v}" for k, v in query.items())
        return f"{base}?{q}"
    return base

def collect_test_cases(imposters):
    test_cases = []

    for imposter in imposters:
        imposter_name = imposter.imposter.name
        imposter_type = imposter.imposter.type

        for predicate in imposter.predicates:
            if predicate.force_response is not None:
                forced_test = create_tests_for_forced_responses(imposter_name, imposter_type, predicate, predicate.force_response)
                test_cases.extend(forced_test)
            else:
                dynamic_tests = create_tests_for_dynamic_responses(imposter_name, imposter_type, predicate)
                test_cases.extend(dynamic_tests)

    test_index = 0
    for test in test_cases:
        test_index = test_index + 1
        test["name"] = f"test_{test_index}"
    return test_cases

def create_tests_for_forced_responses(imposter_name, imposter_type, predicate, force_response):
    test_cases = []
    method = predicate.method
    path = predicate.path
    delay = TimeConverterService.to_seconds(predicate.delay) if predicate.delay else None

    for resp in predicate.responses:
        when = resp.when
        response = resp.response
        code = int(response.code)

        if code != force_response:
            continue

        path_vars = extract_path_params(path, when.get("path"))
        # Replace all $params in expected content
        expected_text = apply_template(response.content, path_vars)

        test_case = {
            "imposter": {
                "type": imposter_type,
                "name": imposter_name
            },
            "request": {
                "url": build_url(path, imposter_type, when.get("path"), when.get("query")),
                "type": method,
                "headers": when.get("header", {}),
                "body": when.get("body", {})
            },
            "response": {
                "delay": delay,
                "headers": get_content_type_headers(response.content_type),
                "code": code,
                "content-type": response.content_type,
                "content": expected_text
            }
        }
        test_cases.append(test_case)

    if len(test_cases) == 0:
        response = fallback_responses.get(force_response)
        test_case = {
            "imposter": {
                "type": imposter_type,
                "name": imposter_name
            },
            "request": {
                "url": build_url(path, imposter_type),
                "type": method,
                "headers": {},
                "body": {}
            },
            "response": {
                "delay": delay,
                "headers": get_content_type_headers('json'),
                "code": force_response,
                "content-type": 'application/json',
                "content": json.dumps(response, indent=2) if isinstance(response, dict) else response
            }
        }
        test_cases.append(test_case)
    return test_cases

def create_tests_for_dynamic_responses(imposter_name, imposter_type, predicate):
    test_cases = []
    method = predicate.method
    path = predicate.path
    delay = TimeConverterService.to_seconds(predicate.delay) if predicate.delay else None

    for resp in predicate.responses:
        when = resp.when
        response = resp.response
        code = int(response.code)

        path_vars = extract_path_params(path, when.get("path"))
        # Replace all $params in expected content
        expected_text = apply_template(response.content, path_vars)
        for var, val in path_vars.items():
            expected_text = expected_text.replace(f"${var}", val)

        test_case = {
            "imposter": {
                "type": imposter_type,
                "name": imposter_name
            },
            "request": {
                "url": build_url(path, imposter_type, when.get("path"), when.get("query")),
                "type": method,
                "headers": when.get("header", {}),
                "body": when.get("body", {})
            },
            "response": {
                "delay": delay,
                "headers": get_content_type_headers(response.content_type),
                "code": code,
                "content-type": response.content_type,
                "content": expected_text
            }
        }
        test_cases.append(test_case)
    return test_cases

def generate_tests():
    imposters = reload_imposters()
    logging.info("🔄 Starting test generation...")
    cases = collect_test_cases(imposters)
    output_file = os.path.join(TESTS_FILE)
    with open(output_file, "w") as f:
        json.dump(cases, f, indent=2)
    
    logging.info(f"✅ Generated {len(cases)} test cases to {output_file}")
    logging.info(f"📊 Test cases breakdown:")
    for imposter in imposters:
        imposter_cases = [case for case in cases if case["imposter"]["name"] == imposter.imposter.name]
        logging.info(f"  • {imposter.imposter.name}: {len(imposter_cases)} test cases")
    return cases

def get_tests():
    output_file = os.path.join(TESTS_FILE)
    if not os.path.exists(output_file):
        with open(output_file, "w") as f:
            json.dump({}, f, indent=2)
    with open(output_file, "r") as f:
        return json.load(f)