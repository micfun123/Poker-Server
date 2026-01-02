from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from .routes import admin, bot, viewer
from .config import server_settings, tournament_settings

# Create FastAPI app
app = FastAPI(
    title="University Poker Bot Tournament",
    description="Backend API for hosting poker bot competitions",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bot.router)
app.include_router(admin.router)
app.include_router(viewer.router)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with links to all interfaces"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Poker Bot Tournament</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .section { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
            a { color: #3498db; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code { background: #e9ecef; padding: 2px 6px; border-radius: 3px; }
            .endpoint { margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🃏 University Poker Bot Tournament</h1>
        
        <div class="section">
            <h2>📺 Interfaces</h2>
            <p><a href="/static/viewer.html">Tournament Viewer</a> - Watch games live</p>
            <p><a href="/static/admin.html">Admin Panel</a> - Manage tournament</p>
        </div>
        
        <div class="section">
            <h2>🤖 Bot API Endpoints</h2>
            <div class="endpoint"><code>POST /bot/register</code> - Register your bot</div>
            <div class="endpoint"><code>POST /bot/action</code> - Submit an action</div>
            <div class="endpoint"><code>GET /bot/state</code> - Get game state</div>
            <div class="endpoint"><code>WS /bot/ws/{player_id}</code> - WebSocket connection</div>
        </div>
        
        <div class="section">
            <h2>📖 Documentation</h2>
            <p><a href="/docs">Swagger UI</a> - Interactive API documentation</p>
            <p><a href="/redoc">ReDoc</a> - Alternative documentation</p>
        </div>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from .managers.tournament import tournament_manager
    from .managers.connection import connection_manager
    
    return {
        "status": "healthy",
        "tournament_status": tournament_manager.status.value,
        "connected_players": connection_manager.get_connected_player_count(),
        "connected_viewers": connection_manager.get_viewer_count()
    }