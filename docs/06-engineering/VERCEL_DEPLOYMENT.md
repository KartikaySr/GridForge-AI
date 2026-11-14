# Vercel Services deployment proposal

Pending user confirmation of service names and public routes. This replaces the earlier frontend-only external-backend configuration.

Root Directory: repository root. Application Preset: Services. Project name: gridforge-ai. Use Node 22.x for the web workspace. Do not import the detected services individually: desktop and src-tauri are native desktop artifacts, apps/api is a legacy scaffold, and the root app auto-detection does not identify the portal factory correctly.

The root vercel.json defines web (Vite built from the repository root to retain workspace dependencies) and portal (FastAPI, explicit cloud.vercel_portal:app ASGI entrypoint). /api/* targets portal; all other paths target web. The existing /api/v1 routes, including /api/v1/mobile/*, and relative browser calls agree with this public routing.

No service bindings are needed: the web is static browser code, not a server-side caller. The portal reads PostgreSQL directly. Browser requests use the public same-origin /api route; runtime binding URLs must never be embedded in Vite bundles. The desktop sync receiver remains outside this deployment and uses the same provisioned central database.

Before deployment set GRIDFORGE_CLOUD_DATABASE_URL privately to managed PostgreSQL and GRIDFORGE_WEB_ORIGIN to the exact intended HTTPS frontend origin, with no trailing slash. Apply sync/portal migrations including 0007_mobile.sql and provision a user/membership using the administrative scripts before serving traffic. The Vercel entrypoint intentionally does not migrate on request or cold start. PostgreSQL must be separately provisioned; Vercel Services does not create it from this config.

The simulator, SQLite desktop runtime and mobile app are not hosted services. Populate the central database through an enrolled simulation edge; the temporary local web demo is not a persistent production database.

Use `vercel dev` to test service routing with a configured development database/origin. The production entrypoint enforces HTTPS secure cookies, so local HTTP development uses the existing `npm run portal:demo` plus `npm run web` workflow, or an HTTPS development origin. Validate hosted sign-in/logout, cookie forwarding, tenant isolation and all seven streams after deployment. No hosted or vercel dev validation is claimed yet.

The old scripts/configure_vercel.mjs now rejects Services mode rather than overwriting its routing.

References: https://vercel.com/docs/services and https://vercel.com/docs/services/config-reference
