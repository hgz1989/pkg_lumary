"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""

from pathlib import Path

from lumary import Lumary

root_dir = Path(__file__).resolve().parent.parent

app = Lumary(debug=True, root_path='/api')

app.mount_sub_apps(root_dir / 'tests' / 'apps')

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000, log_config=None)


