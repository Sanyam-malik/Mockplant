import json

from services.constant_service import FALLBACK_FILE


def save_fallback_responses(data, filename=FALLBACK_FILE):
    """Save fallback responses dictionary to a JSON file."""
    with open(filename, "w") as f:
        json.dump({str(k): v for k, v in data.items()}, f, indent=4)

def load_fallback_responses(filename=FALLBACK_FILE):
    """Load fallback responses dictionary from a JSON file."""
    with open(filename, "r") as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}

fallback_responses = load_fallback_responses()