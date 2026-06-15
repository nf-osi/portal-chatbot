"""Unit tests for the nfGraphRag Lambda function.

All SPARQL network calls are mocked so no endpoint is needed.
"""

import json
import socket
import urllib.error
from unittest.mock import patch

import pytest

from lambda_function import (
    _make_response,
    extract_params,
    lambda_handler,
    sparql_request,
    SPARQL_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_event(api_path, properties=None, http_method="POST"):
    """Build a Bedrock action-group event using the apiPath style."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "nfGraphRag",
        "apiPath": api_path,
        "httpMethod": http_method,
        "requestBody": {
            "content": {
                "application/json": {
                    "properties": properties or [],
                }
            }
        },
    }


def _function_event(function, parameters=None):
    """Build a Bedrock action-group event using the function style."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "nfGraphRag",
        "function": function,
        "parameters": parameters or [],
    }


def _body(response):
    """Extract the parsed JSON body from a Lambda response dict."""
    return json.loads(
        response["response"]["responseBody"]["application/json"]["body"]
    )


# ---------------------------------------------------------------------------
# _make_response
# ---------------------------------------------------------------------------

class TestMakeResponse:
    def test_normal_body(self):
        resp = _make_response("ag", "/path", "POST", 200, {"ok": True})
        assert resp["response"]["httpStatusCode"] == 200
        assert json.loads(resp["response"]["responseBody"]["application/json"]["body"]) == {"ok": True}

    def test_non_serializable_body(self):
        resp = _make_response("ag", "/path", "POST", 200, {"bad": object()})
        body = json.loads(resp["response"]["responseBody"]["application/json"]["body"])
        assert "error" in body
        assert "serialized" in body["error"]


# ---------------------------------------------------------------------------
# extract_params
# ---------------------------------------------------------------------------

class TestExtractParams:
    def test_from_request_body(self):
        event = _api_event("/sparql-query", [
            {"name": "query", "type": "string", "value": "SELECT 1"},
        ])
        assert extract_params(event) == {"query": "SELECT 1"}

    def test_from_parameters_list(self):
        event = _function_event("sparqlQuery", [
            {"name": "query", "type": "string", "value": "SELECT 1"},
        ])
        assert extract_params(event) == {"query": "SELECT 1"}

    def test_empty_event(self):
        assert extract_params({}) == {}

    def test_malformed_property_raises(self):
        event = _api_event("/sparql-query", [{"wrong_key": "oops"}])
        with pytest.raises(KeyError):
            extract_params(event)


# ---------------------------------------------------------------------------
# sparql_request – network layer
# ---------------------------------------------------------------------------

class TestSparqlRequest:
    @patch("lambda_function.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda *a: None
        mock_urlopen.return_value.read.return_value = b"col1\tval1\n"

        result = sparql_request("SELECT 1")
        assert result == "col1\tval1\n"

    @patch("lambda_function.urllib.request.urlopen")
    def test_timeout_raises_timeout_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(reason=socket.timeout("timed out"))
        with pytest.raises(TimeoutError, match=f"timed out after {SPARQL_TIMEOUT}s"):
            sparql_request("SELECT 1")

    @patch("lambda_function.urllib.request.urlopen")
    def test_socket_timeout_raises_timeout_error(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout("timed out")
        with pytest.raises(TimeoutError, match=f"timed out after {SPARQL_TIMEOUT}s"):
            sparql_request("SELECT 1")

    @patch("lambda_function.urllib.request.urlopen")
    def test_http_error_re_raises(self, mock_urlopen):
        err = urllib.error.HTTPError(
            url="http://x", code=400, msg="Bad", hdrs={}, fp=None,
        )
        err.read = lambda: b"bad query"
        mock_urlopen.side_effect = err
        with pytest.raises(Exception, match="SPARQL error 400"):
            sparql_request("SELECT BAD")

    @patch("lambda_function.urllib.request.urlopen")
    def test_url_error_non_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(reason="connection refused")
        with pytest.raises(Exception, match="Request failed"):
            sparql_request("SELECT 1")


# ---------------------------------------------------------------------------
# lambda_handler – routing
# ---------------------------------------------------------------------------

TSV_STUB = "col1\nval1\n"


class TestHandlerRouting:
    """Each function is reached via both apiPath and function-name dispatch."""

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_sparql_query_api_path(self, _mock):
        event = _api_event("/sparql-query", [
            {"name": "query", "value": "SELECT 1"},
        ])
        resp = lambda_handler(event, None)
        assert _body(resp) == {"resultTsv": TSV_STUB}

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_sparql_query_function(self, _mock):
        event = _function_event("sparqlQuery", [
            {"name": "query", "value": "SELECT 1"},
        ])
        resp = lambda_handler(event, None)
        assert _body(resp) == {"resultTsv": TSV_STUB}

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_get_schema_api_path(self, _mock):
        resp = lambda_handler(_api_event("/schema"), None)
        assert "resultTsv" in _body(resp)

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_get_schema_function(self, _mock):
        resp = lambda_handler(_function_event("getSchema"), None)
        assert "resultTsv" in _body(resp)

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_get_shape_api_path(self, _mock):
        event = _api_event("/shape", [
            {"name": "className", "value": "CellLine"},
        ])
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert body["className"] == "CellLine"
        assert body["resultTsv"] == TSV_STUB

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_get_shape_function_with_prefix(self, _mock):
        event = _function_event("getShape", [
            {"name": "className", "value": "nf:AnimalModel"},
        ])
        resp = lambda_handler(event, None)
        assert _body(resp)["className"] == "AnimalModel"

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_count_by_type_api_path(self, _mock):
        resp = lambda_handler(_api_event("/count-by-type"), None)
        assert "resultTsv" in _body(resp)

    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_count_by_type_function(self, _mock):
        resp = lambda_handler(_function_event("countByType"), None)
        assert "resultTsv" in _body(resp)

    def test_unknown_function(self):
        event = _function_event("noSuchFunction")
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert "error" in body
        assert "Unknown function" in body["error"]
        assert resp["response"]["httpStatusCode"] == 200


# ---------------------------------------------------------------------------
# lambda_handler – error handling (424-prevention)
# ---------------------------------------------------------------------------

class TestHandlerErrorPaths:
    """Verify the handler always returns a well-formed response."""

    @patch("lambda_function.sparql_request", side_effect=TimeoutError("timed out"))
    def test_timeout_returns_200_with_error(self, _mock):
        event = _api_event("/schema")
        resp = lambda_handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        assert "timed out" in _body(resp)["error"]

    @patch("lambda_function.sparql_request", side_effect=RuntimeError("boom"))
    def test_generic_exception_returns_200_with_error(self, _mock):
        event = _api_event("/schema")
        resp = lambda_handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        assert "boom" in _body(resp)["error"]

    def test_malformed_event_does_not_crash(self):
        """A property dict missing 'name' would previously crash the Lambda."""
        event = _api_event("/sparql-query", [{"wrong": "data"}])
        resp = lambda_handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        body = _body(resp)
        assert "error" in body

    def test_completely_empty_event(self):
        resp = lambda_handler({}, None)
        assert "response" in resp
        assert resp["response"]["httpStatusCode"] == 200

    def test_missing_query_returns_validation_error(self):
        event = _api_event("/sparql-query")
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert body == {"error": "query is required"}

    def test_missing_classname_returns_validation_error(self):
        event = _api_event("/shape")
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert body == {"error": "className is required"}

    @pytest.mark.parametrize("bad_name", [
        "Animal Model",       # space
        "Foo.Bar",            # dot
        "A}B",                # closing brace
        "x; DROP",            # semicolon
        "nf:Bad>Name",        # angle bracket (after prefix strip)
    ])
    def test_invalid_classname_rejected(self, bad_name):
        event = _api_event("/shape", [{"name": "className", "value": bad_name}])
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert "Invalid className" in body.get("error", "")

    @pytest.mark.parametrize("good_name", [
        "CellLine",
        "AnimalModel",
        "nf:CellLine",
        "_Private",
        "Type2",
    ])
    @patch("lambda_function.sparql_request", return_value=TSV_STUB)
    def test_valid_classname_accepted(self, _mock, good_name):
        event = _api_event("/shape", [{"name": "className", "value": good_name}])
        resp = lambda_handler(event, None)
        body = _body(resp)
        assert "resultTsv" in body

    def test_response_always_has_required_keys(self):
        """Even with a garbage event the response has the Bedrock-required shape."""
        resp = lambda_handler({"garbage": True}, None)
        r = resp["response"]
        assert "actionGroup" in r
        assert "httpStatusCode" in r
        assert "responseBody" in r
        # body should be valid JSON
        json.loads(r["responseBody"]["application/json"]["body"])
