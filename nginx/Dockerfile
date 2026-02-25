# Build stage: compile Brotli dynamic module for nginx
FROM nginx:1.27-alpine AS builder

RUN apk add --no-cache git gcc g++ make pcre-dev zlib-dev linux-headers \
    && git clone --recurse-submodules https://github.com/google/ngx_brotli.git /tmp/ngx_brotli \
    && cd /tmp/ngx_brotli/deps/brotli && mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF .. && make -j$(nproc) \
    && cd /tmp/ngx_brotli \
    && NGINX_VERSION=$(nginx -v 2>&1 | sed 's/.*\///') \
    && wget -qO- "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" | tar xz -C /tmp \
    && cd "/tmp/nginx-${NGINX_VERSION}" \
    && ./configure --with-compat --add-dynamic-module=/tmp/ngx_brotli \
    && make modules \
    && cp objs/ngx_http_brotli_filter_module.so objs/ngx_http_brotli_static_module.so /tmp/

# Runtime stage
FROM nginx:1.27-alpine

# Install Brotli modules from builder
COPY --from=builder /tmp/ngx_http_brotli_filter_module.so /usr/lib/nginx/modules/
COPY --from=builder /tmp/ngx_http_brotli_static_module.so /usr/lib/nginx/modules/

# Brotli modules are loaded via load_module directives in nginx.conf (lines 5-6)

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
