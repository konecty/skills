# Konecty REST API — Language-Agnostic Reference

Use this file when writing code in a language without an official SDK (Go, Java, PHP, etc.) or
when an SDK lacks a feature. All examples use `curl` and are complete and runnable.

For filter syntax see [filters.md](filters.md).
For obtaining and securing the token see [auth-for-code.md](auth-for-code.md).

---

## 1. Base URL and Headers

```
Base URL:  $KONECTY_URL          # e.g. https://app.example.konecty.com
```

Every authenticated request must carry:

```
Authorization: <authId>
Content-Type:  application/json   # on POST/PUT bodies
```

The `authId` value is the token returned by `POST /rest/auth/login` (or the OTP flow). Pass it
verbatim — no `Bearer` prefix. See [auth-for-code.md](auth-for-code.md) for the full auth flow.

> **`/rest/auth/*` strict-CORS note**: Auth endpoints enforce `Sec-Fetch-Site: none`, so they can
> only be called from non-browser contexts (server-side code, curl, SDKs). Never call them from a
> browser frontend.

---

## 2. Response Envelope

### Success

```json
{ "success": true, "data": <record-or-array>, "total": 42 }
```

`data` is a single object on by-id and create/update calls; an array on find/query.
`total` appears on paginated endpoints.

### Error

```json
{ "success": false, "errors": [{ "message": "...", "code": "..." }] }
```

### Status Codes

| Code | Meaning |
|------|---------|
| 200  | OK |
| 400  | Bad request (validation error, invalid filter/config) |
| 401  | Authentication failed (missing or expired token) |
| 403  | Forbidden (no read/write permission on document or field) |
| 404  | Record or file not found |
| 429  | Rate limit exceeded (auth endpoints: 5 req/min per email/phone) |
| 500  | Internal server error |

---

## 3. Data Endpoints

### 3.1 Find Records (GET)

```
GET /rest/data/:document/find
```

Query parameters (all optional except the path):

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `filter`  | JSON string | — | URL-encoded KonFilter; see [filters.md](filters.md) |
| `start`   | int | 0 | Offset for pagination |
| `limit`   | int | 25 | Max records returned |
| `sort`    | JSON string | — | `[{"property":"code","direction":"DESC"}]` |
| `fields`  | string | — | Comma-separated field names, e.g. `code,name,status` |

```bash
curl -G "$KONECTY_URL/rest/data/Contact/find" \
  -H "Authorization: $KONECTY_TOKEN" \
  --data-urlencode 'filter={"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}' \
  --data-urlencode 'sort=[{"property":"code","direction":"DESC"}]' \
  -d 'start=0' \
  -d 'limit=25' \
  -d 'fields=code,name,status'
```

### 3.2 Find Records (POST — body as filter)

Send the KonFilter JSON directly as the request body. All query parameters (`sort`, `start`,
`limit`, `fields`) still go in the query string.

```bash
curl -X POST "$KONECTY_URL/rest/data/Contact/find?start=0&limit=25" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}'
```

### 3.3 Get Record by ID {#by-id}

```
GET /rest/data/:document/:dataId
```

Optional query params: `fields` (comma list), `withDetailFields` (boolean).

```bash
curl "$KONECTY_URL/rest/data/Contact/aAbBcCdDeEfF" \
  -H "Authorization: $KONECTY_TOKEN"
```

Response: `{ "success": true, "data": { "_id": "aAbBcCdDeEfF", ... } }`

### 3.4 Create Record

```
POST /rest/data/:document
```

Body is the record object. `_id` is assigned by the server.

```bash
curl -X POST "$KONECTY_URL/rest/data/Contact" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":{"first":"Alice","last":"Santos"},"email":[{"address":"alice@example.com"}],"status":"active"}'
```

Response: `{ "success": true, "data": [{ "_id": "...", "_updatedAt": "...", ... }] }`

### 3.5 Update Record

```
PUT /rest/data/:document
```

The body **must** include `_id` and `_updatedAt` (fetch-first requirement — the server rejects
updates where `_updatedAt` does not match the stored value, preventing lost updates).

```bash
# 1. Fetch to get current _updatedAt
RECORD=$(curl -s "$KONECTY_URL/rest/data/Contact/aAbBcCdDeEfF" \
  -H "Authorization: $KONECTY_TOKEN")

# 2. Update — include _id and _updatedAt from the fetched record
curl -X PUT "$KONECTY_URL/rest/data/Contact" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"_id":"aAbBcCdDeEfF","_updatedAt":{"$date":"2026-06-17T10:00:00.000Z"},"status":"inactive"}'
```

Response: `{ "success": true, "data": [{ "_id": "...", "_updatedAt": "...", ... }] }`

### 3.6 Delete Record

```
DELETE /rest/data/:document
```

Body must include `_id`.

```bash
curl -X DELETE "$KONECTY_URL/rest/data/Contact" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"_id":"aAbBcCdDeEfF"}'
```

Response: `{ "success": true, "data": [{ "_id": "aAbBcCdDeEfF" }] }`

### 3.7 Record History {#history}

Returns the change-log entries for a single record.

```
GET /rest/data/:document/:dataId/history
```

Optional query param: `fields` (comma list to limit history fields returned).

```bash
curl "$KONECTY_URL/rest/data/Contact/aAbBcCdDeEfF/history" \
  -H "Authorization: $KONECTY_TOKEN"
```

Response: `{ "success": true, "data": [{ "_updatedAt": "...", "_updatedBy": {...}, "data": {...} }, ...] }`

### 3.8 Lookup Field Search {#lookup}

Searches the valid values for a lookup-typed field (type-ahead / autocomplete).

```
GET /rest/data/:document/lookup/:field
```

Query params: `search` (free-text), `filter` (extra KonFilter JSON), `start`, `limit`.

```bash
curl -G "$KONECTY_URL/rest/data/Opportunity/lookup/contact" \
  -H "Authorization: $KONECTY_TOKEN" \
  -d 'search=alice' \
  -d 'limit=10'
```

Response: `{ "success": true, "data": [{ "_id": "...", "name": {...}, ... }] }`

---

## 4. Pagination and Sorting

All paginated endpoints use the same parameters:

| Parameter | Meaning |
|-----------|---------|
| `start`   | Zero-based offset of the first record to return |
| `limit`   | Maximum records per page |
| `total`   | Returned in the response envelope; use it for `ceil(total/limit)` page count |
| `sort`    | JSON array: `[{"property":"<field>","direction":"ASC"|"DESC"}]` |
| `fields`  | Comma-separated projection (reduces payload size) |

Iterate pages by incrementing `start` by `limit` until `data.length < limit` or `start >= total`.

---

## 5. Query Endpoints (Cross-Module)

Both endpoints return **NDJSON** (`Content-Type: application/x-ndjson`). Each line is a complete
JSON object. When `includeMeta` is true the **first** line is a `{"_meta":{...}}` header; all
subsequent lines are data records.

### 5.1 JSON Query {#query-json}

```
POST /rest/query/json
```

Structured cross-module query. The body is a standard find call (same field names: `document`,
`filter`, `fields`, `sort`, `limit`, `start`) plus a required `relations` array. Each relation
specifies the linked document, the lookup field that forms the join, optional sub-filters, and
one or more aggregators.

```bash
curl -X POST "$KONECTY_URL/rest/query/json" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document": "Contact",
    "fields": "code,name",
    "sort": [{"property":"name.full","direction":"ASC"}],
    "limit": 100,
    "includeMeta": true,
    "includeTotal": true,
    "relations": [
      {
        "document": "Opportunity",
        "lookup": "contact",
        "filter": {
          "match": "and",
          "conditions": [{"term":"status","operator":"in","value":["active","new"]}]
        },
        "aggregators": {
          "activeOpportunities": {"aggregator":"count"},
          "opportunities":       {"aggregator":"push"}
        }
      }
    ]
  }'
```

**NDJSON response** (one JSON object per line):

```
{"_meta":{"document":"Contact","relations":["Opportunity"],"warnings":[]}}
{"code":1001,"name":{"full":"Alice Santos"},"activeOpportunities":3,"opportunities":[...]}
{"code":1002,"name":{"full":"Bruno Silva"},"activeOpportunities":1,"opportunities":[...]}
```

Supported aggregators: `count`, `sum`, `avg`, `min`, `max`, `first`, `last`, `push`, `addToSet`.
Relations can nest recursively (up to 2 levels in Phase 1). If a user lacks access to a relation's
document the aggregator fields are returned as `null` (graceful degradation) and a warning is
added to `_meta.warnings`.

The `X-Total-Count` response header is set when `includeTotal` is `true`.

### 5.2 SQL Query {#query-sql}

```
POST /rest/query/sql
```

Translates an ANSI SQL SELECT (with JOIN, WHERE, GROUP BY, ORDER BY, LIMIT) into the same
cross-module engine. DDL and DML are rejected. Read-only.

```bash
curl -X POST "$KONECTY_URL/rest/query/sql" \
  -H "Authorization: $KONECTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT c.code, c.name, COUNT(o._id) AS activeOpportunities FROM Contact c INNER JOIN Opportunity o ON c._id = o.contact._id WHERE o.status IN ('"'"'active'"'"','"'"'new'"'"') GROUP BY c.code, c.name ORDER BY c.name ASC LIMIT 100",
    "includeTotal": true,
    "includeMeta": false
  }'
```

Body fields: `sql` (required string), `includeTotal` (boolean, default `true`), `includeMeta`
(boolean, default `false`).

Response format is identical to the JSON query endpoint (NDJSON).

---

## 6. File Endpoints

### 6.1 Upload {#file-upload}

```
POST /rest/file/upload/:document/:recordId/:fieldName
```

Multipart form upload. The server automatically generates thumbnails for JPEG images and resizes
images beyond the namespace maximum dimensions.

```bash
curl -X POST \
  "$KONECTY_URL/rest/file/upload/Contact/aAbBcCdDeEfF/photo" \
  -H "Authorization: $KONECTY_TOKEN" \
  -F "file=@/path/to/photo.jpg"
```

Success response:

```json
{
  "success": true,
  "key": "Contact/aAbBcCdDeEfF/photo/<md5>.jpg",
  "kind": "image/jpeg",
  "size": 204800,
  "name": "photo.jpg",
  "_id": "<record-id>",
  "_updatedAt": { "$date": "2026-06-17T10:00:00.000Z" }
}
```

### 6.2 Download

```
GET /rest/file/:document/:code/:fieldName/:fileName
```

No `Authorization` header is required if the file is publicly accessible; for protected files the
token is still needed. The server returns the file with the appropriate `Content-Type`.

```bash
curl -O "$KONECTY_URL/rest/file/Contact/aAbBcCdDeEfF/photo/photo.jpg" \
  -H "Authorization: $KONECTY_TOKEN"
```

### 6.3 Delete

```
DELETE /rest/file/delete/:document/:recordId/:fieldName/:fileName
```

```bash
curl -X DELETE \
  "$KONECTY_URL/rest/file/delete/Contact/aAbBcCdDeEfF/photo/photo.jpg" \
  -H "Authorization: $KONECTY_TOKEN"
```

Response: `{ "success": true }`

---

## 7. Streaming Endpoint

For large result sets (1 000+ records) prefer the streaming endpoint over `/find`:

```
GET /rest/stream/:document/findStream
```

Accepts the same query parameters as `GET /rest/data/:document/find`. Returns plain NDJSON
(one record per line, no `_meta` header, no envelope). Process line-by-line to avoid buffering
the entire result set in memory.

```bash
curl -N -G "$KONECTY_URL/rest/stream/Opportunity/findStream" \
  -H "Authorization: $KONECTY_TOKEN" \
  --data-urlencode 'filter={"match":"and","conditions":[]}' \
  -d 'limit=10000'
```

---

## 8. SDK Gap Index

The following anchors exist so SDK reference docs can link directly to REST fallback sections:

| Feature | Anchor / Section |
|---------|-----------------|
| Record history (change-log) | [§ 3.7 Record History](#history) |
| Lookup field search (type-ahead) | [§ 3.8 Lookup Field Search](#lookup) |
| Cross-module JSON query | [§ 5.1 JSON Query](#query-json) |
| Cross-module SQL query | [§ 5.2 SQL Query](#query-sql) |
| File upload | [§ 6.1 Upload](#file-upload) |
| Streaming large result sets | [§ 7 Streaming Endpoint](#streaming-endpoint) |

> Menu, form, and list-view metadata (`/api/admin/meta/*`) are admin-level operations documented
> in `konecty-meta`; link to that skill when the developer needs schema rather than data.
