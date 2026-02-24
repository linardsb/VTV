FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy SSL certs (self-signed for dev)
COPY certs/ /etc/nginx/certs/

# SECURITY: Create writable directories for non-root nginx
RUN chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx && \
    chmod -R 755 /var/cache/nginx /var/run /var/log/nginx

# SECURITY: Allow nginx to bind to port 80 as non-root
RUN apk add --no-cache libcap && \
    setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx && \
    apk del libcap

EXPOSE 80

# SECURITY: Run as non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
