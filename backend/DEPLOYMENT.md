# Deployment Configuration Guide

## Critical Issues Fixed

This application had three hardcoded settings that would break on deployment:

1. **CORS**: Hardcoded to `http://localhost:5173` (dev only)
2. **Cookie Security**: `secure=False` (unsafe for HTTPS)
3. **Cookie SameSite**: `samesite="lax"` (blocks cross-origin cookies)

These are now **environment-configurable**.

## Local Development

No changes needed. The application defaults to:
```
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

Run locally as usual:
```bash
uvicorn main:app --reload
```

## Production Deployment (Render Backend + Vercel Frontend)

### Step 1: Backend Environment Variables (Render Dashboard)

When deploying the backend to Render, add these environment variables:

| Variable | Value | Reason |
|----------|-------|--------|
| `ENVIRONMENT` | `production` | Enables production-mode CORS handling |
| `FRONTEND_URL` | `https://your-app.vercel.app` | Your actual Vercel deployment URL |
| `COOKIE_SECURE` | `true` | Required for HTTPS cookies |
| `COOKIE_SAMESITE` | `none` | Required for cross-origin cookies (vercel.app ↔ render.com) |

### Step 2: Frontend Environment Variables (Vercel)

When deploying the frontend to Vercel, add this environment variable:

| Variable | Value | Reason |
|----------|-------|--------|
| `VITE_API_URL` | `https://your-render-backend.onrender.com` | Your Render backend URL |

**In Vercel Dashboard:**
1. Go to Settings → Environment Variables
2. Add `VITE_API_URL` with your Render backend URL
3. Redeploy to apply changes

### Step 3: Why These Settings Matter

**Cross-Origin Cookies Problem:**
- Frontend: `https://your-app.vercel.app` (Vercel)
- Backend: `https://api.render.app` (Render)
- These are different origins, so cookies are blocked unless:
  - ✅ `secure=true` (HTTPS required)
  - ✅ `samesite=none` (allows cross-origin)
  - ✅ Backend explicitly allows the frontend URL in CORS

**If You Skip This:**
- Frontend sends login request → works ✅
- Backend sets session cookie → fails ❌
- User gets logged out immediately
- "Not authenticated" errors on every request

### Step 4: Verify on Production

Test the login flow:
```bash
curl -X POST https://api.render.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  -v
```

Look for `Set-Cookie` header in the response. If missing or empty, the configuration is wrong.

Also verify the frontend is calling the correct backend URL by checking the Network tab in browser DevTools — all API requests should go to your Render URL, not localhost.

## Troubleshooting

### Issue: "Not authenticated" after login on production
- **Check**: Is `FRONTEND_URL` set correctly in Render dashboard?
- **Check**: Are `COOKIE_SECURE` and `COOKIE_SAMESITE` set correctly?
- **Check**: Is browser sending cookies? (DevTools → Application → Cookies)

### Issue: CORS errors in browser console
- **Solution**: Verify `FRONTEND_URL` matches your deployed URL exactly
- **Solution**: Restart the Render service after changing environment variables

### Issue: It works locally but not on production
- This is 99% of the time a misconfigured `FRONTEND_URL` or missing `COOKIE_SECURE=true`
- Use browser DevTools Network tab to see actual headers

## Files Modified

### Backend
- `backend/main.py` — CORS and cookie configuration now environment-based
- `backend/.env.example` — Environment variables for local development
- `backend/.env.production` — Template for production settings

### Frontend
- `frontend/src/api/client.ts` — API URL now reads from `VITE_API_URL` environment variable
- `frontend/.env.example` — Environment variables for local development
- `frontend/.env.production` — Template for production settings

### Documentation
- `DEPLOYMENT.md` — This guide
