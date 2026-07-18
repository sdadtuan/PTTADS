# Keycloak OIDC for Client Portal (Phase 3.1)

## Local dev

```bash
docker compose -f docker-compose.keycloak.yml up -d
# Admin: http://127.0.0.1:8080/admin (admin / admin)
# Realm: ptt-portal
```

Obtain token (password grant — dev only):

```bash
curl -s -X POST 'http://127.0.0.1:8080/realms/ptt-portal/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=ptt-portal' \
  -d 'grant_type=password' \
  -d 'username=approver@demo.local' \
  -d 'password=demo123' | jq -r .access_token
```

## Nest CRM API

```bash
PTT_PORTAL_AUTH_MODE=keycloak   # or dual (Keycloak + Nest JWT)
PTT_KEYCLOAK_ISSUER=http://127.0.0.1:8080/realms/ptt-portal
PTT_KEYCLOAK_AUDIENCE=ptt-portal
PTT_KEYCLOAK_CLIENT_ID_CLAIM=client_id
```

Portal routes validate Bearer via JWKS (`/protocol/openid-connect/certs`).

## Prod

1. Deploy Keycloak HA (or managed IdP) with TLS
2. Import `deploy/keycloak/realm-ptt-portal.json` — rotate demo passwords
3. Map `client_id` user attribute per pilot client
4. Set `PTT_PORTAL_AUTH_MODE=keycloak` on Nest; disable `PTT_PORTAL_STUB_USERS`
5. Portal Next.js: optional OIDC redirect (Phase 3.1 UI) — until then AM distributes Keycloak login URL

## Rollback

Set `PTT_PORTAL_AUTH_MODE=nest-jwt` and restart `ptt-crm-api` — Nest HS256 login restored.
