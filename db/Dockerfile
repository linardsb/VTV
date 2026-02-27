FROM pgvector/pgvector:pg18

# Install PostGIS extension (available in Debian Bookworm PG18 repos)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-postgis-3-scripts && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
