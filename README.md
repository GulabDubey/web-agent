# Companiesnext Customer Support Agent

FastAPI chatbot that customers embed on their websites with a JavaScript widget.

## Embedding the widget

```html
<script
  src="https://chatbot.example.com/widget/chatbot.js"
  data-site-key="PUBLIC_CUSTOMER_SITE_KEY"
  data-theme-color="#343a40"
  defer
></script>
```

The site key is public. It comes from the Django admin (**Chatbot websites**),
where each key is registered to one domain (`www.` counts as the same site).

## How access is authorized

Payments and subscriptions live in the Django project; this service never
decides eligibility itself.

1. The widget sends `POST /api/v1/widget/session` with `{"site_key": ...}`.
2. The domain is taken from the browser's `Origin` header (never from the
   body) and normalized the same way Django does.
3. FastAPI calls Django's `verify-subscription` endpoint server-to-server with
   `Authorization: Bearer DJANGO_SERVICE_API_KEY`. Django checks the site key,
   the registered domain, and the owner's paid subscription.
4. On success the widget gets a short-lived JWT (`WIDGET_TOKEN_TTL_SECONDS`)
   carrying the site, customer, domain, and a server-generated chat session id.
   The widget only renders after this succeeds.
5. Every chat request verifies the JWT, checks that `Origin` matches the token's
   domain, re-checks the subscription with Django (answers cached in memory for
   `WIDGET_AUTH_CACHE_TTL_SECONDS`), and applies rate limits, all before the
   AI is called.

Any doubt fails closed: Django timeouts, errors, malformed responses, or
missing configuration all deny access.

The `Origin` header only narrows access, because non-browser clients can forge
it. Authorization always comes from the site key or token plus Django's answer.

### Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/v1/widget/session` | site key + Origin | Issue widget token |
| `POST /api/v1/widget/token/refresh` | widget token (may be expired up to `WIDGET_TOKEN_REFRESH_GRACE_SECONDS`) | New token, same chat session |
| `POST /api/v1/contact-us` | widget token | Lead form |
| `POST /api/v1/chat` | widget token | Chat message (AI) |
| `GET/POST /api/v1/users…` | service token | User records |
| `POST /api/v1/internal/widget/invalidate` | service token | Drop cached authorization for a site key (e.g. after cancellation) |
| `GET /widget/*` | public | Widget JS/CSS/HTML (serving the file grants nothing) |

Service-token endpoints expect `Authorization: Bearer <one of INTERNAL_SERVICE_TOKENS>`.

Errors use the standard envelope plus a machine-readable `code`:
`400` malformed · `401` missing/invalid/expired token · `403` invalid key,
domain, disabled site or inactive subscription · `429` rate limited
(`Retry-After` header) · `502`/`503` subscription verification unavailable.

### Tenant isolation

- On every chat the knowledge collection is read from
  `django_app.websites_website.collection_name` for the verified site id
  (set it in Django admin → Chatbot websites). The browser never chooses it;
  a site without one gets `403 no_knowledge_base`.
- Chat sessions and history are keyed by `site_id:session_id`. The session id
  comes from the token, so a `session_id` in a request body is ignored.

## Configuration

See `.env.example` for every variable. To connect the two projects:

| FastAPI (`.env`) | Django (`.env`) |
|---|---|
| `DJANGO_SERVICE_API_KEY` | one entry of `CHATBOT_SERVICE_TOKENS` |
| `INTERNAL_SERVICE_TOKENS` (one entry) | `CRAWLER_API_TOKEN` |
| `DJANGO_SUBSCRIPTION_VERIFY_URL` | `https://<django>/api/internal/chatbot/verify-subscription/` |

`WIDGET_JWT_SECRET` must be at least 32 random characters and must not reuse any
service credential.

**Local development:** set `APP_ENV=development` and
`WIDGET_DEV_DOMAIN=<a domain registered in Django>`. Pages served from
`localhost` / `127.0.0.1` are then verified as that domain. Localhost is never
accepted outside development.

## Deployment notes

- Rate limits, the authorization cache, chat history and the verification
  circuit breaker live in process memory (`app/config/memory_store.py`). They
  are per instance: not shared across workers or serverless instances, and
  reset on restart.
- The deployed app only queries Qdrant. Website crawling is done offline, then
  `scripts/ingest_folder.py` embeds the pages with Voyage AI (`VOYAGE_MODEL`,
  `EMBEDDING_DIMENSION`) and uploads them. Queries use the same model, so
  `VOYAGE_API_KEY` must be set wherever the app runs.
- Behind a reverse proxy, run uvicorn with `--proxy-headers` and
  `--forwarded-allow-ips=<proxy ip>` so per-IP limits see the real client IP.
- Customer sites must use HTTPS in production.

## Tests

```bash
venv/bin/python -m pytest tests
```

The Django API is mocked (`httpx.MockTransport`), and so is the AI
graph. No network access or credentials are needed.
