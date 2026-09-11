import os

from dotenv import load_dotenv

load_dotenv()

VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
FALLBACK_FILE = "./fallback.json"
IMPOSTERS_FOLDER = 'imposters/'
TESTS_FILE = "./test_suite.json"
TEST_RESULTS_FILE = "./test_results.json"
LOCALHOST_URL = f"http://127.0.0.1"
HTTP_PORT = int(os.getenv("HTTP_PORT", "80"))
AUTO_CREATE_TESTS = True if os.getenv("AUTO_CREATE_TESTS", "true").lower() == "true" else False
BASE_URL = {
    "HTTP": f"{LOCALHOST_URL}:{HTTP_PORT}"
}
