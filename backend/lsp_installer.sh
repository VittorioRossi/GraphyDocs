#!/bin/bash
set -e

# Check if running in GitHub Actions
if [ -n "$GITHUB_ACTIONS" ]; then
    SUDO="sudo"
else
    SUDO=""
fi

echo "Installing Language Server Protocols..."

# Update package lists
$SUDO apt-get update

# Install clangd
$SUDO apt-get install -y clangd
$SUDO update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-14 100

# Install Python LSP
pip install 'python-lsp-server[all]'

# Use npm from NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO bash -
$SUDO apt-get install -y nodejs

# Install Dockerfile LSP globally using npm from NodeSource
/usr/bin/npm install -g dockerfile-language-server-nodejs
cat > /usr/local/bin/dockerfile-langserver <<EOL
#!/bin/bash
exec docker-langserver --stdio
EOL
chmod +x /usr/local/bin/dockerfile-langserver

echo "LSP Installation Complete"