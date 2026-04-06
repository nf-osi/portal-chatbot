import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict


SPARQL_ENDPOINT = os.environ.get("SPARQL_ENDPOINT", "http://localhost:7001")

DEFAULT_PREFIXES = """\
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX nf: <http://nf-osi.github.com/terms#>
PREFIX efo: <http://www.ebi.ac.uk/efo/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""


def lambda_handler(event, context):
    """
    Lambda handler for exposing the nf_rag SPARQL helper functions to an agent.
    """
    print(f"Received event: {json.dumps(event)}")

    action_group = event.get("actionGroup")
    api_path = event.get("apiPath", "")
    function = map_api_path_to_function(api_path) or event.get("function")
    params = extract_params(event)

    print(f"API path: {api_path}, function: {function}, params: {params}")

    try:
        if function == "sparqlQuery":
            response_body = sparql_query(params)
        elif function == "getSchema":
            response_body = get_schema(params)
        elif function == "getShape":
            response_body = get_shape(params)
        elif function == "countByType":
            response_body = count_by_type(params)
        else:
            response_body = {
                "error": f"Unknown function: {function}",
                "apiPath": api_path,
                "eventKeys": list(event.keys()),
            }
    except Exception as e:
        print(f"Error processing request: {e}")
        response_body = {"error": f"Failed to process request: {e}"}

    response = {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": 200,
            "responseBody": {
                "application/json": {
                    "body": json.dumps(response_body)
                }
            },
        },
    }

    print(f"Returning response: {json.dumps(response)}")
    return response


def map_api_path_to_function(api_path: str) -> str | None:
    mapping = {
        "/sparql-query": "sparqlQuery",
        "/schema": "getSchema",
        "/shape": "getShape",
        "/count-by-type": "countByType",
    }
    return mapping.get(api_path)


def extract_params(event: Dict[str, Any]) -> Dict[str, Any]:
    request_body = event.get("requestBody", {})
    content = request_body.get("content", {})
    application_json = content.get("application/json", {})
    properties = application_json.get("properties", [])

    params: Dict[str, Any] = {}
    for prop in properties:
        params[prop["name"]] = prop["value"]

    for item in event.get("parameters", []):
        if "name" in item and "value" in item:
            params[item["name"]] = item["value"]

    return params


def sparql_request(query: str, include_default_prefixes: bool = True) -> str:
    full_query = f"{DEFAULT_PREFIXES}\n{query}" if include_default_prefixes else query
    data = urllib.parse.urlencode(
        {"query": full_query, "action": "tsv_export"}
    ).encode("utf-8")
    req = urllib.request.Request(
        SPARQL_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"SPARQL error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise Exception(f"Request failed: {e}")


def sparql_query(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get("query")
    if not query:
        return {"error": "query is required"}

    return {"resultTsv": sparql_request(query, include_default_prefixes=True)}


def get_schema(params: Dict[str, Any]) -> Dict[str, Any]:
    query = """\
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?term ?kind ?label ?comment ?domain ?range WHERE {
  {
    ?term a owl:Class .
    BIND("Class" AS ?kind)
  } UNION {
    ?term a owl:ObjectProperty .
    BIND("ObjectProperty" AS ?kind)
  } UNION {
    ?term a owl:DatatypeProperty .
    BIND("DatatypeProperty" AS ?kind)
  }
  OPTIONAL { ?term rdfs:label ?label }
  OPTIONAL { ?term rdfs:comment ?comment }
  OPTIONAL { ?term rdfs:domain ?domain }
  OPTIONAL { ?term rdfs:range ?range }
} ORDER BY ?kind ?term"""
    return {"resultTsv": sparql_request(query, include_default_prefixes=False)}


def get_shape(params: Dict[str, Any]) -> Dict[str, Any]:
    class_name = params.get("className", "").strip()
    if not class_name:
        return {"error": "className is required"}

    if ":" in class_name:
        class_name = class_name.split(":", 1)[1]

    query = f"""\
PREFIX sh: <http://www.w3.org/ns/shacl#>

SELECT ?shape ?label ?comment ?path ?datatype ?nodeKind ?class ?minCount ?maxCount
WHERE {{
  ?shape a sh:NodeShape ;
         sh:targetClass nf:{class_name} .
  OPTIONAL {{ ?shape rdfs:label ?label }}
  OPTIONAL {{ ?shape rdfs:comment ?comment }}
  OPTIONAL {{
    ?shape sh:property ?prop .
    OPTIONAL {{ ?prop sh:path ?path }}
    OPTIONAL {{ ?prop sh:datatype ?datatype }}
    OPTIONAL {{ ?prop sh:nodeKind ?nodeKind }}
    OPTIONAL {{ ?prop sh:class ?class }}
    OPTIONAL {{ ?prop sh:minCount ?minCount }}
    OPTIONAL {{ ?prop sh:maxCount ?maxCount }}
  }}
}}
ORDER BY ?path
"""
    return {"className": class_name, "resultTsv": sparql_request(query, include_default_prefixes=True)}


def count_by_type(params: Dict[str, Any]) -> Dict[str, Any]:
    query = """\
SELECT ?type (COUNT(?s) AS ?count) WHERE {
  ?s a ?type
} GROUP BY ?type ORDER BY DESC(?count)"""
    return {"resultTsv": sparql_request(query, include_default_prefixes=False)}
