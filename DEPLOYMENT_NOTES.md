# Deployment notes — Daphne, Channels, Redis, Brevo, and M-Pesa

Summary
- Use Daphne (ASGI) to serve HTTP + WebSocket routes.
- Use Redis (channels_redis) for channel layers in production.
- Provide Brevo SMTP/API keys and M-Pesa credentials via environment variables.

Quick checklist
- Install runtime deps (example):
  - `pip install daphne channels channels_redis`
  - Ensure `daphne` is added to your production requirements.
- Set environment variables (see `.env.example`).
- Run Redis (e.g., managed Redis service or `redis-server`).
- Start the web process via Daphne (Procfile updated to use Daphne):

```bash
# On Render / Heroku-like platforms this is handled by Procfile.
# Locally for testing:
redis-server &
python manage.py migrate
python manage.py collectstatic --noinput
daphne -b 0.0.0.0 -p 8000 airbnb_manager.asgi:application
```

Why this fixes WebSocket 404
- The previous Procfile used Gunicorn + WSGI which does not serve WebSocket connections, resulting in 404s for `ws://.../ws/...` routes. Daphne runs the ASGI application which exposes both HTTP and WebSocket protocols.

Channels configuration notes
- `airbnb_manager/settings.py` already supports channels when `channels` is installed and will use `REDIS_URL` if present. Ensure `REDIS_URL` environment variable is set to a reachable Redis instance for production to avoid using InMemoryChannelLayer.

Brevo (email & SMS)
- For SMTP: set `BREVO_SMTP_LOGIN` and `BREVO_SMTP_KEY` (or `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`) and `DEFAULT_FROM_EMAIL`.
- For SMS: set `BREVO_SMS_API_KEY` and `BREVO_SMS_SENDER`.

M-Pesa
- Set `MPESA_*` variables and point `MPESA_CALLBACK_URL` to the publicly reachable callback path: `/bookings/payments/mpesa/callback/`.
- In sandbox, `MPESA_SIMULATE=true` keeps payout code in simulation mode.

Additional recommendations
- Add `daphne` and `channels_redis` to `requirements.txt` or your deployment manifest.
- Use a process manager or container for Daphne in production and scale workers/processes appropriately.
- If using multiple app instances, ensure Redis is configured so channel layers work across instances.

Render specific
- `render.yaml` updated to use Daphne start command. Ensure you set these Env Vars in Render dashboard or in `render.yaml`:
  - `REDIS_URL` (managed Redis instance URL)
  - `DATABASE_URL`
  - `BREVO_SMTP_LOGIN`, `BREVO_SMTP_KEY`, `BREVO_SMS_API_KEY`
  - `MPESA_*` credentials and `MPESA_CALLBACK_URL`

Railway specific
- Railway respects `Procfile` and will use the `start` command from `railway.json` if present. A sample `railway.json` is included. Add environment variables in the Railway project settings for the same keys as above. Railway provides managed Postgres/Redis add-ons you can attach and then set `DATABASE_URL`/`REDIS_URL` to the provided values.

Files added/changed
- `procfile` — switched to Daphne: [procfile](procfile)
- `render.yaml` — start command switched to Daphne and env placeholders: [render.yaml](render.yaml)
- `railway.json` — sample railway manifest: [railway.json](railway.json)
- `requirements-extra.txt` — lists `daphne`, `channels`, and `channels_redis` to add to production requirements: [requirements-extra.txt](requirements-extra.txt)

