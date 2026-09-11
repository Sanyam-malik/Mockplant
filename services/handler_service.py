import json
import time
from typing import Any, Dict, Optional

import requests
from flask import Response

from services.fallback_service import fallback_responses
from services.time_service import TimeConverterService
from services.utility_service import (
    get_response_content_type,
    desanitize_content,
    apply_template,
    match_conditions,
    parse_request_body,
    match_body_conditions,
    match_path_conditions,
    match_path,
    match_header_conditions,
)


def get_forced_response(path_vars, forced_code, responses):
    for entry in responses:
        code = int(entry.response.code)
        if code == forced_code:
            response_content = apply_template(entry.response.content, path_vars)
            headers = entry.response.headers or {}
            content_type = entry.response.content_type
            return Response(
                response=desanitize_content(response_content, content_type),
                status=code,
                content_type=content_type,
                headers=headers
            )

    response = fallback_responses.get(forced_code)
    return Response(
        response=json.dumps(response, indent=2) if isinstance(response, dict) else response,
        status=forced_code,
        content_type='application/json'
    )

def get_dynamic_response(request_data, path_vars, responses):
    headers = dict(request_data.headers)
    query = request_data.args.to_dict()
    body = parse_request_body(request_data)

    for entry in responses:
        when = entry.when
        match = True

        if "query" in when:
            match &= match_conditions(query, when["query"])
        if match and "header" in when:
            match &= match_header_conditions(headers, when["header"])
        if match and "body" in when:
            match &= match_body_conditions(body, when["body"])
        if match and "path" in when:
            match &= match_path_conditions(path_vars, when["path"])

        if "files" in body and len(body['files']) > 0:
            path_vars['files'] = body['files']

        if match:
            # Apply dynamic templating for content
            response_content = apply_template(entry.response.content, path_vars)
            headers = entry.response.headers or {}
            content_type = get_response_content_type(entry.response.content_type)
            return Response(
                response=desanitize_content(response_content, content_type),
                status=int(entry.response.code),
                content_type=content_type,
                headers=headers
            )

    response = fallback_responses.get(200)
    return Response(
        response=json.dumps(response, indent=2) if isinstance(response, dict) else response,
        status=200,
        content_type='application/json'
    )


def _execute_forward_workflow(
    workflow: Dict[str, Any],
    request_data,
    path_vars: Dict[str, Any],
) -> Optional[Response]:
    """
    Execute a simple 'forward' workflow:
    - Build target URL from workflow config (supports $vars from path_vars)
    - Optionally copy headers/query/body from incoming request
    - Perform HTTP call and forward upstream response back to the client
    """
    if not workflow:
        return None

    if workflow.get("type") != "forward":
        return None

    target_url_template = workflow.get("url") or workflow.get("endpoint")
    if not target_url_template:
        return None

    # Build URL with templating support for path variables
    target_url = apply_template(str(target_url_template), dict(path_vars))

    method = str(workflow.get("method", request_data.method)).upper()

    # Headers handling: always start from incoming headers, then apply overrides
    headers_cfg = workflow.get("headers", {})
    src_headers = dict(request_data.headers)
    # Remove hop-by-hop headers that should not be forwarded
    for h in list(src_headers.keys()):
        if h.lower() in {"host", "content-length"}:
            src_headers.pop(h, None)

    outgoing_headers: Dict[str, str] = {}
    outgoing_headers.update(src_headers)

    # Merge/override with explicitly configured headers
    if isinstance(headers_cfg, dict):
        outgoing_headers.update({str(k): str(v) for k, v in headers_cfg.items()})

    # Query parameters: always start from incoming query, then apply overrides
    outgoing_params: Dict[str, Any] = {}
    outgoing_params.update(request_data.args.to_dict())
    extra_query = workflow.get("query")
    if isinstance(extra_query, dict):
        outgoing_params.update(extra_query)

    # Body: default is incoming body; explicit 'body' in workflow overrides it
    outgoing_body: Any = None
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        explicit_body = workflow.get("body", None)
        if explicit_body is not None:
            outgoing_body = explicit_body
        else:
            # Use raw body to preserve original content type
            outgoing_body = request_data.get_data()

    timeout = float(workflow.get("timeout", 10))

    resp = requests.request(
        method=method,
        url=target_url,
        headers=outgoing_headers or None,
        params=outgoing_params or None,
        data=outgoing_body,
        timeout=timeout,
    )

    upstream_headers = dict(resp.headers)
    content_type = upstream_headers.get("Content-Type", "application/octet-stream").split(";")[0]
    # Remove content-type from headers so Flask's Response can manage it via `content_type` arg
    upstream_headers.pop("Content-Type", None)

    return Response(
        response=resp.content,
        status=resp.status_code,
        content_type=content_type,
        headers=upstream_headers,
    )


def _execute_trigger_workflow(
    workflow: Dict[str, Any],
    request_data,
    path_vars: Dict[str, Any],
) -> None:
    """
    Execute a 'trigger' workflow:
    - Sends an HTTP request to a configured endpoint
    - Does not affect the main mock response (fire-and-forget style)
    """
    if not workflow:
        return

    if workflow.get("type") != "trigger":
        return

    target_url_template = workflow.get("url") or workflow.get("endpoint")
    if not target_url_template:
        return

    target_url = apply_template(str(target_url_template), dict(path_vars))
    method = str(workflow.get("method", request_data.method)).upper()

    headers_cfg = workflow.get("headers", {})
    copy_headers_cfg = workflow.get("copy_headers", False)
    outgoing_headers: Dict[str, str] = {}

    if copy_headers_cfg:
        src_headers = dict(request_data.headers)
        for h in list(src_headers.keys()):
            if h.lower() in {"host", "content-length"}:
                src_headers.pop(h, None)

        if isinstance(copy_headers_cfg, list):
            for h in copy_headers_cfg:
                if h in src_headers:
                    outgoing_headers[h] = src_headers[h]
        else:
            outgoing_headers.update(src_headers)

    if isinstance(headers_cfg, dict):
        outgoing_headers.update({str(k): str(v) for k, v in headers_cfg.items()})

    outgoing_params: Dict[str, Any] = {}
    if workflow.get("copy_query", True):
        outgoing_params.update(request_data.args.to_dict())
    extra_query = workflow.get("query")
    if isinstance(extra_query, dict):
        outgoing_params.update(extra_query)

    outgoing_body: Any = None
    if method in {"POST", "PUT", "PATCH", "DELETE"} and workflow.get("copy_body", True):
        outgoing_body = request_data.get_data()

    timeout = float(workflow.get("timeout", 10))

    try:
        requests.request(
            method=method,
            url=target_url,
            headers=outgoing_headers or None,
            params=outgoing_params or None,
            data=outgoing_body,
            timeout=timeout,
        )
    except Exception:
        # Intentionally ignore trigger errors so main flow is unaffected
        return


def handle_request(imposters, path, request_data, imposter_type="HTTP"):
    """ Handle incoming requests, match them with imposters, and return appropriate responses. """
    req_method = request_data.method
    req_path = f"/{path}"
    delay = None
    response = None

    # Use the globally imported `imposters` list
    for imposter in imposters:
        if imposter.imposter.type != imposter_type:
            continue

        for predicate in imposter.predicates:
            if predicate.method != req_method:
                continue

            # Path matching with dynamic variables
            path_match, path_vars = match_path(predicate.path, req_path)
            if not path_match:
                continue

            delay = predicate.delay

            # Collect all workflows for this predicate
            all_workflows = list(getattr(predicate, "workflows", []) or [])

            # Optional: allow selecting a single workflow by index via header
            selected_workflow_index = None
            header_index = request_data.headers.get("X-Mockplant-Workflow-Index")
            if header_index is not None:
                try:
                    idx_val = int(str(header_index).strip())
                    if 0 <= idx_val < len(all_workflows):
                        selected_workflow_index = idx_val
                except (ValueError, TypeError):
                    selected_workflow_index = None

            # Execute workflows in order:
            # - 'trigger' workflows fire side-effect calls
            # - first 'forward' workflow that returns a response will short-circuit
            for wf_idx, wf in enumerate(all_workflows):
                if selected_workflow_index is not None and wf_idx != selected_workflow_index:
                    continue

                wf_type = (wf.get("type") or "").lower()
                if wf_type == "trigger":
                    _execute_trigger_workflow(wf, request_data, path_vars)
                elif wf_type == "forward":
                    response = _execute_forward_workflow(wf, request_data, path_vars)
                    if response is not None:
                        return response

            if predicate.force_response:
                response = get_forced_response(path_vars, int(predicate.force_response), predicate.responses)
                return response
            else:
                response = get_dynamic_response(request_data, path_vars, predicate.responses)
                return response

    if delay:
        time.sleep(TimeConverterService.to_seconds(delay))

    if response:
        return response
    return Response(
        response=json.dumps({"error": "No matching imposter found"}),
        status=404,
        content_type='application/json'
    )
