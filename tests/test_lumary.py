"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
import logging
from pathlib import Path

from lumary import Lumary

logging.basicConfig(level=logging.DEBUG)

root_dir = Path(__file__).resolve().parent.parent

app = Lumary(debug=True, root_path='/api',enable_health_check=True)

app.mount_sub_apps(root_dir / 'apps')

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
