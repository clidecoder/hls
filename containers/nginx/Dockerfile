FROM nginx:alpine

# Install certbot and dependencies
RUN apk add --no-cache certbot certbot-nginx bash

# Create directory for Let's Encrypt
RUN mkdir -p /etc/letsencrypt

# Copy nginx configuration template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Create a script to handle certificate renewal
RUN echo '#!/bin/bash\n\
while :; do\n\
    sleep 12h\n\
    certbot renew --nginx --non-interactive --quiet\n\
done' > /usr/local/bin/renew-certificates.sh && \
    chmod +x /usr/local/bin/renew-certificates.sh

# Expose ports
EXPOSE 80 443

# Start nginx and certificate renewal in background
CMD ["sh", "-c", "/usr/local/bin/renew-certificates.sh & nginx -g 'daemon off;'"]