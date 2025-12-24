# Quick Deployment Guide

## 🚀 Fastest Way to Deploy (Render - Recommended for Demos)

### Step 1: Verify Setup
```bash
cd explorium-assistant-video-version

# Verify mcp-explorium is in the directory (you already did this!)
ls mcp-explorium  # Should show the directory

# Run verification script (optional)
python3 verify_setup.py
```

### Step 2: Prepare for Git
```bash
# Initialize git if not already
git init
git add .
git commit -m "Ready for deployment"
```

### Step 3: Push to GitHub
```bash
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 4: Deploy on Render
1. Go to https://render.com and sign up/login
2. Click "New +" → "Web Service"
3. Connect your GitHub repo
4. Configure:
   - **Name**: `explorium-assistant`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables:
   - `ANTHROPIC_API_KEY` = (your key)
   - `EXPLORIUM_API_KEY` = (your key)
   - `UV_PATH` = `/root/.cargo/bin/uv`
   - `MCP_WORKING_DIR` = `/opt/render/project/src/mcp-explorium`
6. Click "Create Web Service"
7. Wait ~5 minutes for first deployment
8. Your app will be live at `https://your-app.onrender.com`

### Step 5: Test
- Open your Render URL in a browser
- Try sending a test message
- Check logs in Render dashboard if there are issues

## ⚠️ Important Notes

1. **MCP Server Directory**: The `mcp-explorium` directory MUST be included in your repository
2. **Environment Variables**: Never commit your `.env` file (it's in `.gitignore`)
3. **Free Tier**: Render free tier spins down after 15 min inactivity (first request may be slow)
4. **UV Path**: After first deploy, check Render logs to confirm uv installation path, then update `UV_PATH` if needed

## 🔐 How Environment Variables Work (IMPORTANT!)

**Your API keys are secure and private:**
- You set environment variables in Render/Railway dashboard (not in your code)
- These variables are **ONLY accessible to your running application**
- **Users who visit your site CANNOT see your API keys**
- The company testing your app just needs the public URL - they never see your keys

**To share with the company:**
1. Deploy your app (follow steps above)
2. Set your API keys in Render/Railway dashboard (they're hidden from everyone)
3. Share the public URL (e.g., `https://your-app.onrender.com`) with the company
4. They can test the app - your API keys remain secure in the platform

**Your keys are safe!** The hosting platform encrypts and protects them. Only your application can access them.

## 🔧 Troubleshooting

**Issue**: "UV_PATH not found"
- Check Render build logs to see where uv installed
- Update `UV_PATH` environment variable accordingly

**Issue**: "MCP_WORKING_DIR not found"  
- Since `mcp-explorium` is in your repo root, set `MCP_WORKING_DIR` to `/opt/render/project/src/mcp-explorium` (or `/app/mcp-explorium` on Railway)

**Issue**: WebSocket connection fails
- Render supports WebSockets, but check that your URL uses `https://` not `http://`

## 📝 Alternative: Railway

Railway is also great and often faster. See `DEPLOYMENT.md` for detailed Railway instructions.

