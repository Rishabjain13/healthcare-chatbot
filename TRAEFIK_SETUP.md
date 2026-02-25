# Traefik HTTPS Setup Guide

This guide explains how to deploy your healthcare chatbot with HTTPS using Traefik as a reverse proxy.

## Architecture Overview

```
Internet
   |
   v
Traefik (Port 80/443)
   |
   +---> https://healthcare.maglabs.ai --> Frontend (Port 80)
   |
   +---> https://api.healthcare.maglabs.ai --> Backend (Port 3000)
```

## Prerequisites

1. **Domain Setup**: You already have `healthcare.maglabs.ai` pointing to your server IP `35.226.43.225`
2. **DNS Configuration**: You need to add a subdomain for the API

## Step 1: Configure DNS Records

Add the following DNS record to your domain provider (same provider managing healthcare.maglabs.ai):

```
Type: A
Name: api.healthcare.maglabs.ai
Value: 35.226.43.225
TTL: Auto or 3600
```

Alternatively, you can use a CNAME:
```
Type: CNAME
Name: api
Value: healthcare.maglabs.ai
TTL: Auto or 3600
```

## Step 2: Build and Push Updated Frontend Image

The frontend needs to be rebuilt with the new HTTPS API URL:

```bash
cd frontend

# Build with HTTPS API URL
docker build --build-arg VITE_API_URL=https://api.healthcare.maglabs.ai -t magureme/healthcare-frontend:v2 .

# Push to Docker Hub
docker push magureme/healthcare-frontend:v2
```

## Step 3: Deploy with Docker Compose

On your server (35.226.43.225):

```bash
# Pull the latest images
docker-compose pull

# Stop existing services
docker-compose down

# Start services with Traefik
docker-compose up -d

# Check logs
docker-compose logs -f traefik
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Step 4: Verify SSL Certificates

Traefik will automatically request SSL certificates from Let's Encrypt. This process takes a few minutes.

Check the Traefik logs:
```bash
docker-compose logs -f traefik
```

You should see messages about ACME certificate requests.

## Step 5: Test the Setup

1. **Frontend**: Visit https://healthcare.maglabs.ai
   - Should redirect HTTP to HTTPS automatically
   - Should show a valid SSL certificate

2. **Backend API**: Test with curl
   ```bash
   curl https://api.healthcare.maglabs.ai/health
   ```

3. **Check the chatbot**: Open the frontend and send a message to verify the backend communication works over HTTPS

## Traefik Dashboard (Optional)

The Traefik dashboard is available at:
- http://35.226.43.225:8080 (insecure, for debugging only)
- https://traefik.healthcare.maglabs.ai (if you add DNS record for traefik subdomain)

**Security Note**: For production, you should secure the dashboard with authentication or disable it.

## Troubleshooting

### Certificate Not Issued

If Let's Encrypt certificates aren't issued:

1. Verify DNS records are propagating:
   ```bash
   nslookup healthcare.maglabs.ai
   nslookup api.healthcare.maglabs.ai
   ```

2. Check ports 80 and 443 are accessible from the internet:
   ```bash
   curl -I http://healthcare.maglabs.ai
   curl -I http://api.healthcare.maglabs.ai
   ```

3. Check Traefik logs for ACME errors:
   ```bash
   docker-compose logs traefik | grep -i acme
   ```

### CORS Issues

If the frontend can't connect to the backend, check:

1. Browser console for CORS errors
2. Traefik CORS middleware is configured correctly (already set in docker-compose.yml)
3. The backend is accessible:
   ```bash
   curl https://api.healthcare.maglabs.ai/health
   ```

### Mixed Content Errors

If you see mixed content warnings in the browser:
- Verify the frontend is using `https://api.healthcare.maglabs.ai` (not HTTP)
- Rebuild the frontend image if needed

## Configuration Files Modified

1. **docker-compose.yml**:
   - Added Traefik service
   - Updated backend with Traefik labels
   - Updated frontend with Traefik labels
   - Changed ports from `ports` to `expose` for backend and frontend

2. **frontend/Dockerfile**:
   - Updated default VITE_API_URL to use HTTPS

## Security Recommendations

1. **Remove Cloudflare Tunnel**: Since you're using Traefik with Let's Encrypt, you may want to remove the cloudflared service from docker-compose.yml

2. **Secure Traefik Dashboard**: Add authentication or disable the dashboard in production

3. **Firewall**: Ensure only ports 80 and 443 are open to the internet (close port 3000 if it's exposed)

4. **Rate Limiting**: Consider adding rate limiting middleware to Traefik for the backend API

## Next Steps

- Monitor SSL certificate renewal (Let's Encrypt certificates expire every 90 days, but Traefik handles auto-renewal)
- Set up monitoring and alerting for your services
- Configure backup for the Traefik Let's Encrypt storage (`traefik/letsencrypt/acme.json`)
