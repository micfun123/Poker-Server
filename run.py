# run.py
"""
Application runner script
"""

import uvicorn
from app.config import server_settings

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 🃏 POKER BOT TOURNAMENT 🃏                    ║
╠══════════════════════════════════════════════════════════════╣
║  Server starting on http://{server_settings.host}:{server_settings.port}                    ║
║                                                              ║
║  Endpoints:                                                  ║
║    • Viewer:  http://localhost:{server_settings.port}/static/viewer.html    ║
║    • Admin:   http://localhost:{server_settings.port}/static/admin.html     ║
║    • API Docs: http://localhost:{server_settings.port}/docs                  ║
║                                                              ║
║  Admin Password: {server_settings.admin_password}                                 ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=server_settings.host,
        port=server_settings.port,
        reload=server_settings.debug,
        log_level="info"
    )
    