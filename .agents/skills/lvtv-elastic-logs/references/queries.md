# LVTV Elasticsearch Query Templates

Use these JSON objects as templates with:

```bash
python3 scripts/mcp_call.py --profile main search '<json>'
```

Run commands from the `lvtv-elastic-logs` skill directory, or adjust the script path relative to the current checkout or installed skill location. Replace `INDEX`, field names, and time windows after sampling documents.

## Profiles

| Profile | URL | Typical index families |
|---|---|---|
| `main` | `http://127.0.0.1:32022/mcp` | `k8s-core`: `fbyc-gateway`, `fbyc-web-gateway`, `fbyc-rails`, `fbyc-nginx`, `fbyc-nextjs`, `fbyc-sidekiq-*`, `fbyc-seo`, `fbyc-tourparser`, app/staging/jobs logs |
| `integrations` | `http://127.0.0.1:32012/mcp` | `k8s-integrations`: `fbyc-actualizer`, `fbyc-actualization-cache`, `fbyc-booker`, `fbyc-currency`, `fbyc-ghe`, `fbyc-go-tour`, `fbyc-search-calendar`, `fbyc-search-generator`, `fbyc-searcher`, `fbyc-stats-updater`, `fbyc-storage` |
| `dynamics` | `http://127.0.0.1:32002/mcp` | `k8s-dynamic`: `fbyc-dynamic` |

## List Indices

```bash
python3 scripts/mcp_call.py --profile main list_indices '{"index_pattern":"*SERVICE_FRAGMENT*"}'
python3 scripts/mcp_call.py --profile all find_index '{"index_pattern":"*SERVICE_FRAGMENT*"}'
```

## Latest Documents

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 3,
    "sort": [{ "@timestamp": { "order": "desc" } }],
    "query": {
      "range": {
        "@timestamp": { "gte": "now-10m", "lte": "now" }
      }
    }
  }
}
```

## Freshness Check

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 0,
    "query": { "match_all": {} },
    "aggs": {
      "min_ts": { "min": { "field": "@timestamp" } },
      "max_ts": { "max": { "field": "@timestamp" } }
    }
  }
}
```

## Sample Fields With Narrow Source

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 5,
    "sort": [{ "@timestamp": { "order": "desc" } }],
    "_source": [
      "@timestamp",
      "json",
      "message",
      "kubernetes.pod.name",
      "container.image.name"
    ],
    "query": {
      "range": {
        "@timestamp": { "gte": "now-15m", "lte": "now" }
      }
    }
  }
}
```

## Field Probe

Run this for a candidate field, then try `FIELD.keyword` if it returns empty.

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 0,
    "query": {
      "range": {
        "@timestamp": { "gte": "now-15m", "lte": "now" }
      }
    },
    "aggs": {
      "values": { "terms": { "field": "FIELD", "size": 20 } }
    }
  }
}
```

## Generic Status/Error Overview

Replace optional fields after discovery. Remove aggregations for fields that do not exist.

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 0,
    "track_total_hits": true,
    "query": {
      "range": {
        "@timestamp": { "gte": "now-5m", "lte": "now" }
      }
    },
    "aggs": {
      "status": { "terms": { "field": "STATUS_FIELD", "size": 20 } },
      "errors": { "terms": { "field": "ERROR_FIELD", "size": 20 } },
      "routes": { "terms": { "field": "ROUTE_FIELD", "size": 30 } },
      "uas": { "terms": { "field": "USER_AGENT_FIELD", "size": 30 } },
      "ips": { "terms": { "field": "IP_FIELD", "size": 30 } },
      "pods": { "terms": { "field": "kubernetes.pod.name", "size": 30 } },
      "images": { "terms": { "field": "container.image.name", "size": 10 } }
    }
  }
}
```

## Status Timeline By Minute

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 0,
    "query": {
      "range": {
        "@timestamp": { "gte": "now-30m", "lte": "now" }
      }
    },
    "aggs": {
      "latest": { "max": { "field": "@timestamp" } },
      "per_min": {
        "date_histogram": { "field": "@timestamp", "fixed_interval": "1m" },
        "aggs": {
          "status": { "terms": { "field": "STATUS_FIELD", "size": 10 } },
          "errors": { "terms": { "field": "ERROR_FIELD", "size": 5 } },
          "message_filter": { "filter": { "match_phrase": { "message": "MESSAGE_PHRASE" } } }
        }
      }
    }
  }
}
```

## Failed Request Samples

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 10,
    "sort": [{ "@timestamp": { "order": "desc" } }],
    "_source": [
      "@timestamp",
      "json",
      "message",
      "kubernetes.pod.name",
      "container.image.name"
    ],
    "query": {
      "bool": {
        "filter": [
          { "range": { "@timestamp": { "gte": "now-5m", "lte": "now" } } },
          { "term": { "STATUS_FIELD": 403 } }
        ]
      }
    }
  }
}
```

## Suspicious User Agents

Use for crawler/parser analysis after confirming the user-agent and route fields.

```json
{
  "index": "INDEX",
  "query_body": {
    "size": 0,
    "query": {
      "range": {
        "@timestamp": { "gte": "now-24h", "lte": "now" }
      }
    },
    "aggs": {
      "ua": {
        "terms": {
          "field": "USER_AGENT_FIELD",
          "size": 30,
          "include": ".*(Go-http-client|aiohttp|Typhoeus|python-requests|TravelataCA|rest-client|Symfony HttpClient|Swagger-Codegen|curl|httpx|Scrapy|okhttp|Java/|Apache-HttpClient|requests|urllib).*"
        },
        "aggs": {
          "ips": { "terms": { "field": "IP_FIELD", "size": 8 } },
          "routes": { "terms": { "field": "ROUTE_FIELD", "size": 12 } },
          "status": { "terms": { "field": "STATUS_FIELD", "size": 8 } },
          "last": { "max": { "field": "@timestamp" } }
        }
      }
    }
  }
}
```

## LVTV Field Substitutions

Use these substitutions only after a sample confirms the index shape.

| Profile / index | Status | Error | Route/action | UA | IP |
|---|---|---|---|---|---|
| `main/fbyc-gateway` | `json.status_int` | `json.error_message.keyword` | `json.incoming_path.keyword` | `json.user_agent` | `json.remote_ip` |
| `main/fbyc-web-gateway` | `json.status_int` | `json.error_message.keyword` | `json.incoming_path.keyword` | `json.user_agent` | `json.remote_ip` |
| `main/fbyc-rails` | `json.status` | sample first | `json.controller_action.keyword` | `json.user_agent` | `json.remote_ip` |
| `main/fbyc-nginx` | `json.status` | sample first | `json.uri` | `json.http_user_agent` | `json.remote_addr` |
| `integrations/fbyc-searcher` | sample first | sample first | `json.event` / `json.msg` | none typical | none typical |
| `integrations/fbyc-go-tour` | `json.status` / `json.success` | sample first | `json.event` / `json.module` | none typical | none typical |
| `integrations/fbyc-storage` | `json.grpc.code` | sample first | `json.grpc.service` / `json.grpc.method` | none typical | none typical |
| `integrations/fbyc-booker` | `json.success` | sample first | `json.event` / `json.path` | none typical | none typical |
| `dynamics/fbyc-dynamic` | sample first | sample first | `json.grpc.service` / `json.grpc.method` / `json.incoming_request_path` | none typical | none typical |

## Past-Incident Examples

Gateway 403 plus MySQL bad connection:

- `INDEX`: `fbyc-gateway`
- `PROFILE`: `main`
- `STATUS_FIELD`: `json.status_int`
- `ERROR_FIELD`: `json.error_message.keyword`
- `ROUTE_FIELD`: `json.incoming_path.keyword`
- `USER_AGENT_FIELD`: `json.user_agent`
- `IP_FIELD`: `json.remote_ip`
- `MESSAGE_PHRASE`: `bad connection`

Rails parser traffic:

- `INDEX`: `fbyc-rails`
- `PROFILE`: `main`
- `STATUS_FIELD`: `json.status`
- `ROUTE_FIELD`: `json.controller_action.keyword`
- `USER_AGENT_FIELD`: `json.user_agent`
- `IP_FIELD`: `json.remote_ip`

Integration service health:

- `INDEX`: `fbyc-searcher`, `fbyc-go-tour`, `fbyc-storage`, or related.
- `PROFILE`: `integrations`
- Start with `json.level`, `json.success`, `json.event`, `json.msg`, `json.duration`.
- For gRPC logs, use `json.grpc.service`, `json.grpc.method`, `json.grpc.code`, `json.grpc.time_ms`.

Dynamic service investigation:

- `INDEX`: `fbyc-dynamic`
- `PROFILE`: `dynamics`
- Start with `json.grpc.service`, `json.grpc.method`, `json.incoming_request_path`, `json.search_job_id`, `json.search_scope`, `json.search_type`, `json.supplier_name`.
