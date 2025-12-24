# Environment Variables Guide

## How Environment Variables Work in Deployment

When you deploy to Render, Railway, or any hosting platform:

1. **You set the environment variables in the platform's dashboard** (not in your code)
2. **The variables are only accessible to your running application** - visitors to your site cannot see them
3. **The company testing your app will only see the public URL** - they never see your API keys

## Setting Environment Variables

### On Render:
1. Go to your service dashboard
2. Click on "Environment" tab
3. Add each variable:
   - `ANTHROPIC_API_KEY` = `sk-ant-api03-...` (your full key)
   - `EXPLORIUM_API_KEY` = `your-explorium-key`
   - `UV_PATH` = `/root/.cargo/bin/uv`
   - `MCP_WORKING_DIR` = `/opt/render/project/src/mcp-explorium`

### On Railway:
1. Go to your service dashboard
2. Click on "Variables" tab
3. Add each variable (same as above)

## Security Notes

✅ **Safe:**
- Setting variables in the hosting platform dashboard
- Variables are encrypted and only accessible to your app
- Visitors cannot see or access your API keys

❌ **Never:**
- Commit `.env` file to Git (it's in `.gitignore`)
- Hardcode API keys in your source code
- Share your API keys in emails or messages

## Cost Management (Optional)

If you're concerned about API usage costs, you can:

1. **Monitor usage** in your hosting platform's dashboard
2. **Set up usage alerts** in Anthropic/Explorium dashboards
3. **Add rate limiting** (see below)
4. **Use demo/test keys** if available from the API providers

## Adding Rate Limiting (Optional)

If you want to limit how many requests can be made, you can add rate limiting to your FastAPI app. This is optional but recommended for public demos.

