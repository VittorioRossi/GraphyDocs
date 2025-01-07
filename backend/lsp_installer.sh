#!/bin/bash
set -e

echo "Installing Language Server Protocols..."

# Update package lists
apt-get update

# Install clangd
apt-get install -y clangd
update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-14 100

# Install Python LSP
pip install 'python-lsp-server[all]'

# Use npm from NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Dockerfile LSP globally using npm from NodeSource
/usr/bin/npm install -g dockerfile-language-server-nodejs
cat > /usr/local/bin/dockerfile-langserver <<EOL
#!/bin/bash
exec docker-langserver --stdio
EOL
chmod +x /usr/local/bin/dockerfile-langserver

echo "LSP Installation Complete"