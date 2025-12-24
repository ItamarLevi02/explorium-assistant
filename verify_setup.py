#!/usr/bin/env python3
"""
Quick verification script to check if the project is set up correctly for deployment.
Run this before deploying to catch any issues early.
"""
import os
import sys

def check_file_exists(path, description):
    """Check if a file or directory exists."""
    exists = os.path.exists(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists

def main():
    print("Verifying project setup...\n")
    
    all_good = True
    
    # Check main app files
    print("Checking main application files:")
    all_good &= check_file_exists("app/main.py", "Main application file")
    all_good &= check_file_exists("app/agent/graph.py", "Agent graph file")
    all_good &= check_file_exists("app/static/index.html", "Frontend HTML")
    all_good &= check_file_exists("requirements.txt", "Python dependencies")
    
    print("\nChecking MCP server:")
    all_good &= check_file_exists("mcp-explorium", "MCP server directory")
    all_good &= check_file_exists("mcp-explorium/local_dev_server.py", "MCP local dev server")
    all_good &= check_file_exists("mcp-explorium/pyproject.toml", "MCP project config")
    
    print("\nChecking deployment files:")
    all_good &= check_file_exists("Procfile", "Procfile (for Railway/Heroku)")
    all_good &= check_file_exists("DEPLOYMENT.md", "Deployment documentation")
    
    print("\nChecking environment variables:")
    env_vars = [
        "ANTHROPIC_API_KEY",
        "EXPLORIUM_API_KEY", 
        "UV_PATH",
        "MCP_WORKING_DIR"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Don't print the full value for security
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"✓ {var}: {masked}")
        else:
            print(f"✗ {var}: Not set (will need to set in deployment platform)")
            if var in ["ANTHROPIC_API_KEY", "EXPLORIUM_API_KEY"]:
                all_good = False
    
    print("\n" + "="*50)
    if all_good:
        print("✓ All checks passed! Ready for deployment.")
        print("\nNext steps:")
        print("1. Push your code to GitHub")
        print("2. Deploy to Render or Railway")
        print("3. Set environment variables in the deployment platform")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

