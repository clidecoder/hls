# Archived Nginx Configuration Files

These nginx configuration files were archived when the project migrated to using Nginx Proxy Manager (NPM).

## Why Archived?

The project now uses Nginx Proxy Manager for:
- SSL termination
- Domain routing  
- Proxy configuration
- Header preservation

NPM provides a web UI for managing these settings, making manual nginx config files unnecessary.

## Archived Files

1. **nginx.conf.example** - Original example configuration for manual nginx setup
   - Contains rate limiting, SSL config, security headers
   - Shows upstream backend configuration
   - Useful as reference for advanced nginx features

2. **nginx_update.conf** - Previous production configuration
   - Shows the actual configuration that was used
   - Includes both /webhook and /hooks endpoints
   - Managed by Certbot for SSL

## Current Setup

The current setup uses Nginx Proxy Manager as documented in:
- `/docs/nginx-proxy-manager.md`
- `/docs/nginx-proxy-configuration.md`
- `/docs/nginx-proxy-manager-config.md`

## When to Reference These Files

These archived configs may be useful if you need to:
- Implement advanced rate limiting
- Add custom security headers
- Configure nginx without NPM
- Understand the previous setup