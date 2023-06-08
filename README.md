# fotoware-http-get-by-id-fastapi

Goal: use regular, unauthenticated GET requests to retrieve a Fotoware asset.

Complication: there is no single, archive-independent identifier that can be queries for.
There is an archive-dependent file path and there is an implementation-internal `physicalFileId`.
This service enables GET requests, can assign identifiers and more.

Besides the cache, this service is completely stateless. That allows all configuration to be contained for easy deployment.

## Configuration and usage

- Provide environment variables ([required and optional](app/config.py))
- `$ docker compose up -d --build`
- `$ curl -X GET http://localhost:5001/doc/t3aiii6jyurgaxfcgn43qji3zh4/flower.jpg`

Use a reverse proxy (e.g., Caddy) to serve this app.

## Documentation

Unauthenticated endpoints:

- `GET /id/{identifier}` redirects to `/doc/{identifier}/{filename}`
  - If `Accept: application/json`, this endpoint returns a JSON representation of the asset.
- `GET /-/openapi.json`, `GET /-/docs/swagger`, and `GET /-/docs/redoc` supply OpenAPI documentation on the whole service

Authenticated endpoints, only required if asset is not public:

- `GET /doc/{identifier}/{filename}` renders the original file[¹](#fn1)
- `GET /img/{identifier}/preview/{filename}?size,w,h,square` renders a preview (images and documents)[²](#fn2)
- `GET /img/{identifier}/rendition/{filename}?profile,original,size,w,h` renders a specific rendition (images only)[²](#fn2)

Authenticated endpoints:

- `GET /-/data/jsonld-manifest?archives,limit,since` returns a complete JSON-LD manifest of all files in the repository
- `GET /-/background-worker/assign-metadata?archives,limit,tasks` sets IDs, hashes, etc. for assets that don't have them yet
- `POST /-/webhooks/assign-metadata?tasks` calculates IDs, hashes, etc. for a single asset supplied via webhook

In development mode, unauthenticated endpoints:

- `GET /fotoweb` proxies the entire Fotoware API
- `GET /-/tokens/new` returns new, temporarily valid tokens

The required and optional **environment variables** are listed and documented in [`app/config.py`](app/config.py).
Please check the optionals `FOTOWARE_ARCHIVES`, `FOTOWARE_FIELDNAME_UUID`, `PUBLIC_DOCTYPES` and `RATE_LIMIT` and set them to a reasonable default for your usecase, as well as an adequate cache size.

The value of the **filename path variable** is arbitrary and is passed along the `Content-Disposition` header as a suggestion when files are saved.
If the value is `getfile`, the original filename will be in the `Content-Disposition` header.

The **autogenerated ID** is a 27 character long, lowercase string matching `/^[rjkmtvyz][a-z2-7]+$/`.[³](#fn3)
The service returns HTTP error 422 if the identifier is not a valid identifier.
If there is no file with the supplied identifier, error 404 is returned.
If there are multiple results for the identifier, error 404 is returned and a warning is written to the log.
This ensures that the ID is truly unique and prevents indeterminate, undefined behavior.

**Authentication** or authorization of the service to Fotoware is done by a client-id and secret.
End-user access to files depends on what is configured as public.
If not public, authorization is passed by means of JWTs, that are supplied either via the query parameter `?token=` or with the appropriate HTTP header (Bearer).
Create tokens with the below [generation algorithm](#tokens).[⁴](#fn4)

As this service tries to be stateless, no services that provide token are registerd. Instead, linking services should use the `/id/{identifier}` or `/doc/{identifier}/{filename}` to find a public file OR generate their own tokens.

## Development

- A (VS Code) devcontainer is contained with this repository.
- `$ docker compose up --build`

## Tokens

The JWT token contains three claims, signed with a previously shared secret (`JWT_SECRET`).
The `exp` and `iat` claims are as JWT specifies them.
Ensure that the validity duration does not exceed the value of `TOKEN_MAX_DURATION`.

The `sub` claims concatenates a type (see below), `:`, and the file identifier.[⁵](#fn5)
The audience types and the algorithm for the construction of the token can be verified in [apptoken.py](app/apptoken.py).

| Token audience        | `sub` claim prefix | sep | `sub` claim suffix |
| --------------------- | ------------------ | --- | ------------------ |
| Preview asset         | `pre`              | `:` | _file identifier_  |
| Asset rendition       | `rnd`              | `:` | _file identifier_  |
| Get asset original    | `ori`              | `:` | _file identifier_  |
| JSON-LD manifest      | `jld`              | `:` |                    |
| Update asset metadata | `uid`              | `:` |                    |

## Known issues

Using UNION archives, the same file may appear with the same attributes and filename, yet in different archives.
Ensure that a single asset only appears in a single archive.

---

<small>

<a id="fn1" href="#fn1">1:</a> Unauthenticated only for the public document types configured in `PUBLIC_DOCTYPES` or `PUBLIC_METADATA_KEY_VALUE`. Supply a valid token for non-public assets. Else, a HTML file manifest with a link to Fotoware (HTTP status 401 Unauthorized).  
<a id="fn2" href="#fn2">2:</a> Unauthenticated only for the public document types configured in `PUBLIC_DOCTYPES` or `PUBLIC_METADATA_KEY_VALUE`. Supply a valid token for non-public assets. Else, an empty HTTP 401 Unauthorized is returned.  
<a id="fn3" href="#fn3">3:</a> The value space was chosen to be shorter (27 chars) than a regular UUID (36 chars).
The ID value space was based on the choice of a globally random UUID.
The hex encoding of a UUID is 36 chars long, but with low entropy: only [0-9a-f] are used.
The UUID bytes are instead encoded with case-insensitive Base32 ([a-z2-7]) and then prefixed with a random letter.
That letter satisfies systems that expect a C-style identifier (i.e., not beginning with a number).  
<a id="fn4" href="#fn4">4:</a> During testing, you can use use `/-/tokens/new` to generate access tokens. That does require a shared secret (`JWT_SECRET`) to be set.  
<a id="fn5" href="#fn5">5:</a> Splitting these claims shortens the token by 16 letters.

</small>
