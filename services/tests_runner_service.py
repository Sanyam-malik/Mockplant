import os
import json
import re
import time
import unittest
import requests
from io import StringIO
import base64
import difflib
import logging

from services import utility_service
from services.constant_service import TESTS_FILE, TEST_RESULTS_FILE
from services.utility_service import get_response_content_type


class DynamicImposterTests(unittest.TestCase):
    pass

    def _format_diff(self, expected, actual):
        """Format the difference between expected and actual content"""
        try:
            diff = difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                lineterm='',
                n=3
            )
            return '\n'.join(diff)
        except:
            return f"Expected: {expected}\nActual: {actual}"

class TestRunnerService:
    def __init__(self, suite_path=TESTS_FILE, results_path=TEST_RESULTS_FILE):
        self.suite_path = suite_path
        self.results_path = results_path

    def _load_test_cases(self):
        if not os.path.exists(self.suite_path):
            raise FileNotFoundError(f"❌ Test suite file not found: {self.suite_path}")
        with open(self.suite_path, "r") as f:
            return json.load(f)


    def _create_test_function(self, test_case):

        def _desanitize_content(self, content, content_type):
            return utility_service.desanitize_content(content, content_type)

        def _make_request(self, url, method, headers, body):
            start_time = time.time()
            response = None
            try:
                if method == "GET":
                    response = requests.get(url, headers=headers)
                elif method == "POST":
                    if "multipart/form-data" in headers.get("Content-Type", ""):
                        response = requests.post(url, headers=headers, files=body)
                    elif "application/x-www-form-urlencoded" in headers.get("Content-Type", ""):
                        response = requests.post(url, headers=headers, data=body)
                    elif "application/json" in headers.get("Content-Type", ""):
                        response = requests.post(url, headers=headers, json=body)
                    else:
                        response = requests.post(url, headers=headers, data=body)
                elif method == "PUT":
                    if "multipart/form-data" in headers.get("Content-Type", ""):
                        response = requests.put(url, headers=headers, files=body)
                    elif "application/x-www-form-urlencoded" in headers.get("Content-Type", ""):
                        response = requests.put(url, headers=headers, data=body)
                    elif "application/json" in headers.get("Content-Type", ""):
                        response = requests.put(url, headers=headers, json=body)
                    else:
                        response = requests.put(url, headers=headers, data=body)
                elif method == "DELETE":
                    response = requests.delete(url, headers=headers)
                else:
                    self.fail(f"Unsupported HTTP method: {method}")
            except requests.RequestException as e:
                self.fail(f"Request failed: {str(e)}")
            end_time = time.time()
            response_time = end_time - start_time
            return response, response_time

        def test(self):
            test._test_meta_name = test_case["name"]
            method = test_case["request"]["type"]
            url = test_case["request"]["url"]
            headers = test_case["request"]["headers"] if test_case["request"]["headers"] else {}
            body = test_case["request"]["body"] if test_case["request"]["body"] else {}
            expected_headers = test_case["response"]["headers"]
            expected_delay = test_case["response"]["delay"]
            expected_code = test_case["response"]["code"]
            expected_content_type = test_case["response"]["content-type"] if test_case["response"]["content-type"] else"text/plain"
            expected_text = _desanitize_content(self, test_case["response"]["content"], expected_content_type)

            response, response_time = _make_request(self, url, method, headers, body)
            if response is None:
                return

            # Compare status code
            if response.status_code != expected_code:
                self.fail(
                    f"Status code mismatch:\n"
                    f"Expected: {expected_code}\n"
                    f"Actual: {response.status_code}\n"
                    f"Response: {response.text}"
                )

            # Compare content based on content type
            if expected_content_type == get_response_content_type("binary"):
                # For binary content, compare raw bytes
                expected_bytes = expected_text.encode('utf-8')
                if response.content != expected_bytes:
                    self.fail(
                        f"Binary content mismatch:\n"
                        f"Expected (base64): {base64.b64encode(expected_bytes).decode('utf-8')}\n"
                        f"Actual (base64): {base64.b64encode(response.content).decode('utf-8')}"
                    )
            else:
                # For text-based content, compare text
                if response.text != expected_text:
                    diff = self._format_diff(expected_text, response.text)
                    self.fail(
                        f"Content mismatch:\n"
                        f"Expected:\n{expected_text}\n"
                        f"Actual:\n{response.text}\n"
                        f"Diff:\n{diff}"
                    )

            # Verify content type header if specified
            if expected_content_type:
                expected_content_type = expected_headers.get('Content-Type', expected_content_type)
                actual_content_type = response.headers.get('Content-Type', '')
                if actual_content_type != expected_content_type:
                    self.fail(
                        f"Content-Type header mismatch:\n"
                        f"Expected: {expected_content_type}\n"
                        f"Actual: {actual_content_type}"
                    )

            if expected_delay is not None and expected_delay > 0:
                # Adding 10ms Overhead
                delay = expected_delay + 0.01
                if response_time > delay:
                    self.fail(
                        f"Response time exceeded delay:\n"
                        f"Expected: <= {delay:.3f}s\n"
                        f"Actual: {response_time:.3f}s"
                    )
        return test

    def _inject_tests(self, cases):
        for attr in list(DynamicImposterTests.__dict__):
            if attr.startswith("test_"):
                delattr(DynamicImposterTests, attr)
        for case in cases:
            func = self._create_test_function(case)
            setattr(DynamicImposterTests, case["name"], func)

    def run_tests(self):
        cases = self._load_test_cases()
        self._inject_tests(cases)

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(DynamicImposterTests)
        result_stream = StringIO()
        runner = _JSONTestRunner(resultclass=_JSONTestResult, stream=result_stream, verbosity=2)
        result = runner.run(suite)

        if hasattr(result, "test_results"):
            # Encode content for display in results
            for test_result in result.test_results:
                if "error" in test_result:
                    test_result["error"] = self._encode_content_for_display(
                        test_result["error"], 
                        "text"
                    )
            
            result.test_results = sorted(result.test_results, key=lambda x: extract_number(x['name']))
            with open(self.results_path, "w") as f:
                json.dump(result.test_results, f, indent=2, sort_keys=False)

        # Log results
        logging.info("✅ Test Results:\n%s", json.dumps(result.test_results, indent=2))

        return result.test_results

    def _encode_content_for_display(self, param, param1):
        return utility_service.sanitize_content(param, param1)


def extract_number(name):
    match = re.search(r'\d+', name)
    return int(match.group()) if match else 0

class _JSONTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_results = []

    def addSuccess(self, test):
        self.test_results.append({"name": str(test).split(" ")[0], "status": "Pass"})

    def addFailure(self, test, err):
        self.test_results.append({
            "name": str(test).split(" ")[0],
            "status": "Fail",
            "error": self._exc_info_to_string(err, test)
        })

    def addError(self, test, err):
        self.test_results.append({
            "name": str(test).split(" ")[0],
            "status": "Error",
            "error": self._exc_info_to_string(err, test)
        })

class _JSONTestRunner(unittest.TextTestRunner):
    def run(self, test):
        return super().run(test)

if __name__ == "__main__":
    service = TestRunnerService()
    results = service.run_tests()
    print(json.dumps(results, indent=2))