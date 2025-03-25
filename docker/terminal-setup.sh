#!/bin/bash

# This script sets up the terminal environment when container starts

set -e

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print welcome message
echo -e "${GREEN}Terminal Container Starting${NC}"
echo -e "${YELLOW}Setting up development environment...${NC}"

# Fix Docker socket permissions if needed
if [ -e /var/run/docker.sock ]; then
    # Get the group ID of the docker socket
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
    
    # Create the docker group with the same GID
    groupadd -g $DOCKER_GID docker || true
    
    # Add current user to the docker group
    usermod -aG docker root || true
    
    # Set appropriate permissions on the Docker socket
    chmod 666 /var/run/docker.sock || true
    
    echo -e "${GREEN}Docker socket permissions configured${NC}"
fi

# Ensure workspace directory exists and has correct permissions
mkdir -p /workspace
chown -R root:root /workspace

# Set up Python environment
echo -e "${YELLOW}Configuring Python environment...${NC}"
python3 -m venv /workspace/venv || echo "Virtual environment already exists"
echo "source /workspace/venv/bin/activate" >> /root/.bashrc

# Set up basic project structure if it doesn't exist
if [ ! -d "/workspace/src" ]; then
    echo -e "${YELLOW}Creating basic project structure...${NC}"
    mkdir -p /workspace/src
    mkdir -p /workspace/tests
    mkdir -p /workspace/data
    mkdir -p /workspace/scripts
    mkdir -p /workspace/docs
    
    # Create basic README.md
    cat > /workspace/README.md << EOL
# AI Agent Generated Project

This project was created by the AI Agent Terminal Interface.

## Project Structure

- \`src/\`: Source code
- \`tests/\`: Test files
- \`data/\`: Data files
- \`scripts/\`: Utility scripts
- \`docs/\`: Documentation

## Getting Started

1. Navigate to the project directory
2. Install dependencies (if needed)
3. Run the code

EOL

    # Create basic .gitignore
    cat > /workspace/.gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Node.js
node_modules/
npm-debug.log
yarn-debug.log
yarn-error.log
package-lock.json
.env

# Virtual Environment
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS specific
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Project specific
.pytest_cache/
.coverage
htmlcov/
.npm_cache/
.pip_cache/
.yarn_cache/

EOL
fi

# Create helper scripts directory
mkdir -p /usr/local/bin/helpers

# Create a helper script for initializing a Python project
cat > /usr/local/bin/helpers/init-python-project.sh << EOL
#!/bin/bash
# Initialize a Python project

set -e

if [ -z "\$1" ]; then
    echo "Usage: init-python-project <project_name>"
    exit 1
fi

PROJECT_NAME="\$1"
mkdir -p "\$PROJECT_NAME"
cd "\$PROJECT_NAME"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Create basic project structure
mkdir -p "\$PROJECT_NAME"
mkdir -p tests
touch "\$PROJECT_NAME/__init__.py"
touch tests/__init__.py

# Create setup.py
cat > setup.py << EOF
from setuptools import setup, find_packages

setup(
    name="\$PROJECT_NAME",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        # Add your dependencies here
    ],
)
EOF

# Create README.md
cat > README.md << EOF
# \$PROJECT_NAME

Description of your project.

## Installation

\`\`\`
pip install -e .
\`\`\`

## Usage

Example of how to use your project.

## Tests

\`\`\`
pytest
\`\`\`
EOF

# Create requirements.txt
cat > requirements.txt << EOF
pytest
EOF

# Install dev dependencies
pip install -e .
pip install pytest

echo "Python project \$PROJECT_NAME initialized successfully!"
echo "Activate the virtual environment with: source venv/bin/activate"
EOL

# Create a helper script for initializing a JavaScript project
cat > /usr/local/bin/helpers/init-js-project.sh << EOL
#!/bin/bash
# Initialize a JavaScript project

set -e

if [ -z "\$1" ]; then
    echo "Usage: init-js-project <project_name>"
    exit 1
fi

PROJECT_NAME="\$1"
mkdir -p "\$PROJECT_NAME"
cd "\$PROJECT_NAME"

# Initialize npm
npm init -y

# Update package.json
sed -i 's/"name": ".*"/"name": "'\$PROJECT_NAME'"/' package.json

# Create basic project structure
mkdir -p src
mkdir -p tests

# Create main JavaScript file
cat > src/index.js << EOF
// Main entry point for \$PROJECT_NAME

function hello() {
  return 'Hello from \$PROJECT_NAME';
}

module.exports = {
  hello
};
EOF

# Create test file
cat > tests/index.test.js << EOF
const app = require('../src/index');

test('hello function', () => {
  expect(app.hello()).toBe('Hello from \$PROJECT_NAME');
});
EOF

# Update package.json for testing
sed -i 's/"test": ".*"/"test": "jest"/' package.json

# Install dependencies
npm install --save-dev jest

echo "JavaScript project \$PROJECT_NAME initialized successfully!"
EOL

# Create a helper script for initializing a React project
cat > /usr/local/bin/helpers/init-react-project.sh << EOL
#!/bin/bash
# Initialize a React project

set -e

if [ -z "\$1" ]; then
    echo "Usage: init-react-project <project_name>"
    exit 1
fi

PROJECT_NAME="\$1"

# Create React app
npx create-react-app "\$PROJECT_NAME"
cd "\$PROJECT_NAME"

# Install common dependencies
npm install --save \
  react-router-dom \
  styled-components \
  axios

echo "React project \$PROJECT_NAME initialized successfully!"
EOL

# Make helper scripts executable
chmod +x /usr/local/bin/helpers/*.sh

# Create alias commands for the helper scripts
echo 'alias init-python-project="/usr/local/bin/helpers/init-python-project.sh"' >> /root/.bashrc
echo 'alias init-js-project="/usr/local/bin/helpers/init-js-project.sh"' >> /root/.bashrc
echo 'alias init-react-project="/usr/local/bin/helpers/init-react-project.sh"' >> /root/.bashrc

# Print environment information
echo -e "${GREEN}Environment ready!${NC}"
echo -e "${YELLOW}Python: $(python3 --version)${NC}"
echo -e "${YELLOW}Node: $(node --version)${NC}"
echo -e "${YELLOW}NPM: $(npm --version)${NC}"

# Execute the command passed to the script
exec "$@"
