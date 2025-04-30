# RotBot's Web Thumbmaker

A web application for creating YouTube thumbnails with customizable text and backgrounds.

## Features

- Create thumbnails for content
- Save thumbnails and content to Notion
- Image upload and storage
- Static file serving

## Deployment Instructions

### Prerequisites
- Node.js installed
- npm installed
- Python 3.9+ installed (for backend)

### Local Development
1. Install dependencies:
   ```
   npm install
   pip install -r requirements.txt
   ```

2. Run the frontend:
   ```
   npm run build
   ```

3. Run the backend:
   ```
   python app.py
   ```

### Deploying to Netlify

1. Connect your GitHub repository to Netlify
2. Select the repository in the Netlify dashboard
3. Configure build settings:
   - Build command: `npm run build`
   - Publish directory: `dist`
4. Deploy!

Alternatively, deploy from the command line:
```
netlify deploy --prod
```

### Deploying to Render

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Select the repository
4. Configure settings:
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
5. Add environment variables:
   - FLASK_ENV: production
   - NOTION_API_TOKEN: (your-token)
   - NOTION_DATABASE_ID: (your-database-id)
   - PORT: 10000
   - FLASK_APP: app.py

## Project Structure
- `public/` - Static HTML, CSS, and client-side JavaScript
- `src/` - Source files for frontend components
- `app.py` - Flask backend for API endpoints
- `wsgi.py` - WSGI entry point for deployment

## Environment Variables

Make sure to set these environment variables in your Vercel project settings:

- `NOTION_API_TOKEN`
- `NOTION_DATABASE_ID` # Rotbot
