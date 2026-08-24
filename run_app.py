import os
import sys
import streamlit.web.cli as stcli

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        script_path = os.path.join(bundle_dir, "股票技術指標篩選器_Web.py")
    else:
        script_path = os.path.abspath("股票技術指標篩選器_Web.py")
        
    sys.argv = [
        "streamlit",
        "run",
        script_path,
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.serverAddress=localhost",
        "--server.port=8501",
        "--browser.gatherUsageStats=false"
    ]
    sys.exit(stcli.main())
