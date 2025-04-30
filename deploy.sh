#!/bin/bash

echo "🚀 RotBot Web Thumbmaker Deployment Script 🚀"
echo "---------------------------------------------"
echo "Select deployment platform:"
echo "1) Render"
echo "2) Netlify"
echo "3) Both"
echo "4) Local Development"
read -p "Enter choice (1-4): " choice

# Create and activate virtual environment
if [[ "$choice" == "1" || "$choice" == "3" || "$choice" == "4" ]]; then
  echo "Setting up Python environment..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
fi

# Build frontend
if [[ "$choice" == "2" || "$choice" == "3" || "$choice" == "4" ]]; then
  echo "Building frontend..."
  npm run build
fi

case $choice in
  1)
    echo "Deploying to Render..."
    # For Render, you typically deploy via Git push or Render Dashboard
    echo "To deploy to Render:"
    echo "1. Commit and push your changes to Git"
    echo "2. Go to the Render dashboard and deploy your service"
    echo "3. Or use the Render CLI if available"
    ;;
  2)
    echo "Deploying to Netlify..."
    # Check if Netlify CLI is installed
    if ! command -v netlify &> /dev/null; then
      echo "Netlify CLI not found. Installing..."
      npm install -g netlify-cli
    fi
    netlify deploy --prod
    ;;
  3)
    echo "Deploying to both platforms..."
    echo "First, deploying to Netlify..."
    if ! command -v netlify &> /dev/null; then
      echo "Netlify CLI not found. Installing..."
      npm install -g netlify-cli
    fi
    netlify deploy --prod
    
    echo "Now, for Render deployment:"
    echo "1. Commit and push your changes to Git"
    echo "2. Go to the Render dashboard and deploy your service"
    ;;
  4)
    echo "Starting local development environment..."
    export FLASK_APP=app.py
    export FLASK_ENV=development
    export PORT=5001
    
    # Run the application in the background
    python app.py &
    
    echo "Backend running at http://localhost:5001"
    echo "Use CTRL+C to stop the application"
    ;;
  *)
    echo "Invalid option. Exiting."
    exit 1
    ;;
esac

echo "Done!" 