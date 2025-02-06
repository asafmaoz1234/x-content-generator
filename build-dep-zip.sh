#!/bin/bash

# Remove existing deployment package and zip
rm -rf deployment-package
rm -f function.zip

# Create fresh deployment directory structure
mkdir -p deployment-package/prompts

# Install dependencies
cd deployment-package
pip install --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --target . \
    openai tweepy python-json-logger

# Copy function files
cp ../main.py .
cp ../prompt_builder.py .
cp ../x_poster.py .
cp ../logger_util.py .
cp ../prompts/social_media_prompt.txt ./prompts/

# Create zip file
zip -r ../function.zip .

# Go back to original directory
cd ..

# Remove deployment package
rm -r deployment-package

echo "Deployment package created: function.zip"