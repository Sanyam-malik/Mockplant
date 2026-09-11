import json
import urllib
from urllib.parse import urlparse

import requests
from typing import Optional, Dict, Any, Union
from requests.structures import CaseInsensitiveDict

from entity.imposter_model import Imposter, ImposterMetadata, Predicate, ResponseEntry, Response
from services.constant_service import VALID_HTTP_METHODS


def build_url(url: str, variables: Dict[str, str]) -> str:
    """Replaces placeholders in the URL with actual variable values."""
    for key, value in variables.items():
        url = url.replace(f"${key}", value)
    return url


def call_api(
        method: str,
        url: str,
        variables: Dict[str, str] = {},
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Union[Dict[str, Any], str, bytes]] = None,
        body_type: Optional[str] = None
) -> Imposter:
    """Performs an HTTP request and returns a structured response."""
    request_func = getattr(requests, method.lower())
    full_url = build_url(url, variables)

    # Convert headers to CaseInsensitiveDict for consistent handling
    headers = CaseInsensitiveDict(headers) if headers else CaseInsensitiveDict()

    # Prepare request kwargs
    request_kwargs = {
        'headers': headers,
        'params': params
    }

    # Handle different body types
    if body is not None and method in ['POST', 'PUT', 'PATCH']:
        
        if body_type == 'form-data':
            # Handle form-data
            files = {}
            data = {}
            for key, value in body.items():
                if isinstance(value, (str, bytes)):
                    data[key] = value
                else:
                    files[key] = value
            request_kwargs['files'] = files
            request_kwargs['data'] = data
        elif body_type == 'x-www-form-urlencoded':
            # Handle x-www-form-urlencoded
            request_kwargs['data'] = body
        elif body_type == 'raw':
            # Handle raw body
            request_kwargs['data'] = body
        elif body_type == 'binary':
            # Handle binary data
            request_kwargs['data'] = body
        elif body_type == 'graphql':
            # Handle GraphQL
            request_kwargs['json'] = body
        else:
            # Default to JSON
            request_kwargs['json'] = body

    response = request_func(full_url, **request_kwargs)
    url_path = urlparse(url).path
    status_code = response.status_code

    when_data = {}
    if headers:
        when_data["header"] = dict(headers)
    if params:
        when_data["query"] = params
    if body:
        when_data["body"] = body

    response_headers = dict(response.headers)
    content_type = response_headers.get('Content-Type', None).split(";")[0].lower()
    if 'Content-Type' in response_headers:
        response_headers.pop('Content-Type')
    #response_text = json.loads(response.text) if content_type == "application/json" else response.text
    response_text = response.text
    response_entity = ResponseEntry(when=when_data, response=Response(headers=response_headers, code=status_code, content=response_text, content_type=content_type))
    metadata = ImposterMetadata(name=f"Imposter for {url_path}", description=f"Auto-generated imposter for {method} {url_path}", type="HTTP")
    predicates = [Predicate(method=method, path=url_path, responses=[response_entity])]
    return Imposter(imposter=metadata, predicates=predicates)