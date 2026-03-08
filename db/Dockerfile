FROM pgvector/pgvector:pg18

# Install PostGIS and TimescaleDB extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-postgis-3-scripts \
        gnupg lsb-release wget && \
    echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/timescaledb.list && \
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg && \
    apt-get update && \
    apt-get install -y --no-install-recommends timescaledb-2-postgresql-18 && \
    apt-get purge -y gnupg lsb-release wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Enable TimescaleDB in PostgreSQL shared_preload_libraries
RUN echo "shared_preload_libraries = 'timescaledb'" >> /usr/share/postgresql/postgresql.conf.sample
