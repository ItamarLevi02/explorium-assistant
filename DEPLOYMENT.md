# Deployment Guide

This FastAPI application can be deployed to Railway, Render, or Fly.io. This guide covers Railway (recommended for quick demos).

## Railway Deployment (Recommended)

### Prerequisites
- GitHub account
- Railway account (sign up at https://railway.app - free tier available)

### Important: Include MCP Server Directory

Before deploying, make sure your `mcp-explorium` directory is included in your repository. You have two options:

**Option 1: Include mcp-explorium as a subdirectory** (Recommended)
- Copy the `mcp-explorium` directory into your `explorium-assistant-video-version` folder
- Or use a git submodule if it's in a separate repo

**Option 2: Use the MCP server as a package** (if available on PyPI)
- Install via pip: `pip install explorium-mcp-server`
- Update the code to use the package instead of local path

### Steps

1. **Prepare your repository**:
   ```bash
   cd explorium-assistant-video-version
   # Make sure mcp-explorium directory is included
   # If it's in a parent directory, copy it:
   # cp -r ../mcp-explorium .
   
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Deploy to Railway**:
   - Go to https://railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will automatically detect it's a Python app

3. **Install uv in Railway**:
   - In Railway dashboard, go to your service → Settings
   - Add a build command (or create a `railway.toml`):
   ```toml
   [build]
   builder = "NIXPACKS"
   
   [deploy]
   startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
   ```
   - Or add to build command: `curl -LsSf https://astral.sh/uv/install.sh | sh && pip install -r requirements.txt`

4. **Set Environment Variables**:
   In Railway dashboard, go to your service → Variables tab and add:
   - `ANTHROPIC_API_KEY` - Your Anthropic API key (starts with `sk-ant-api...`)
   - `EXPLORIUM_API_KEY` - Your Explorium API key
   - `UV_PATH` - Set to `/root/.cargo/bin/uv` (or check where uv installs: `which uv` in Railway logs)
   - `MCP_WORKING_DIR` - Set to `/app/mcp-explorium` (since mcp-explorium is now in your repo root)
   - `PORT` - Railway sets this automatically, but you can verify it's set

5. **Configure Build**:
   - Railway should auto-detect Python 3.11+
   - The Procfile will handle the start command

6. **Deploy**:
   - Railway will automatically deploy
   - Check the logs to verify uv path: Look for "uv is installed at: ..."
   - Once deployed, you'll get a public URL like `https://your-app.railway.app`

### Quick Railway Setup (Alternative - Using Railway CLI)

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Link to existing project or create new one
railway link

# Set environment variables
railway variables set ANTHROPIC_API_KEY=your_key_here
railway variables set EXPLORIUM_API_KEY=your_key_here
railway variables set UV_PATH=/root/.cargo/bin/uv
railway variables set MCP_WORKING_DIR=/app/mcp-explorium

# Deploy
railway up
```

## Alternative: Render Deployment (Easier Setup)

Render is often simpler for Python apps. Follow these steps:

1. **Prepare your repository** (same as Railway - include mcp-explorium directory)

2. **Go to Render**:
   - Sign up at https://render.com (free tier available)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

3. **Configure the service**:
   - **Name**: `explorium-assistant` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free (or paid for better performance)

4. **Set Environment Variables** (in Render dashboard):
   - `ANTHROPIC_API_KEY` - Your Anthropic API key
   - `EXPLORIUM_API_KEY` - Your Explorium API key  
   - `UV_PATH` - Set to `/root/.cargo/bin/uv` (check logs after first deploy)
   - `MCP_WORKING_DIR` - Set to `/opt/render/project/src/mcp-explorium`

5. **Deploy**:
   - Click "Create Web Service"
   - Render will build and deploy automatically
   - Your app will be available at `https://your-app.onrender.com`

**Note**: Render free tier spins down after 15 minutes of inactivity. First request may take ~30 seconds to wake up.

## Alternative: Fly.io Deployment

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Initialize: `fly launch` (in project directory)
4. Set secrets: `fly secrets set ANTHROPIC_API_KEY=xxx EXPLORIUM_API_KEY=xxx`
5. Deploy: `fly deploy`

## Important Notes

- **WebSocket Support**: All platforms above support WebSockets
- **Environment Variables**: Never commit `.env` file to Git
- **MCP Server**: Make sure your MCP server directory is included in the repository or configure the path correctly
- **Port**: The app will use `$PORT` environment variable (automatically set by hosting platforms)

## 🔐 Security: How Environment Variables Work

**Your API keys stay private and secure:**

1. **You set environment variables in the hosting platform's dashboard** (Render/Railway)
   - These are stored encrypted and only accessible to your application
   - They are NOT visible in your code or to users visiting your site

2. **When someone visits your deployed app:**
   - They only see the public URL (e.g., `https://your-app.onrender.com`)
   - They can use the app normally
   - They CANNOT see or access your API keys
   - Your keys remain secure in the platform's environment

3. **To share your demo with a company:**
   - Deploy the app and set your API keys in the platform dashboard
   - Share only the public URL with them
   - They can test the app - your keys stay private

**Your API keys are safe!** The hosting platform handles encryption and security. You're only sharing the public URL, not your credentials.

## Troubleshooting

- If WebSockets don't work, check that your hosting platform supports persistent connections
- Ensure all environment variables are set correctly
- Check logs in the hosting platform's dashboard for errors

