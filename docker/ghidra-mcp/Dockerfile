FROM eclipse-temurin:21-jre-jammy

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    python3 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Download Ghidra 11.2.1
ENV GHIDRA_VERSION=11.2.1
RUN wget -q "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC.zip" \
    && unzip -q ghidra_*.zip -d /opt/ \
    && mv /opt/ghidra_* /opt/ghidra \
    && rm ghidra_*.zip

# Install ghidra-mcp Python package
RUN pip3 install --no-cache-dir ghidra-mcp || \
    (git clone https://github.com/Maleick/ghidra-mcp.git /opt/ghidra-mcp-src && \
     cd /opt/ghidra-mcp-src && \
     pip3 install --no-cache-dir -r requirements.txt 2>/dev/null || true)

# Set Ghidra install directory
ENV GHIDRA_INSTALL_DIR=/opt/ghidra

# MCP server port
EXPOSE 8765

# Copy and setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
