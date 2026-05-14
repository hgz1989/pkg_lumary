"""
@Author     : zarkhan
@CreateDate : 2026/5/14
@Description: 
"""
from importlib import import_module
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

# 👇 忽略的目录
_IGNORE_DIRS = {'__pycache__', 'tests', 'test', 'utils'}


def auto_load_subapp_models(apps_path: str | Path) -> None:
    """自动扫描并加载所有子应用中的 models 包

    适用于模块化多应用结构（每个子应用独立 models 包）
    注意：复杂关联模型建议使用显式导入
    Args:
        apps_path: 子应用路径
    """
    apps_path = Path(apps_path)

    if not apps_path.exists():
        logger.warning(f'{apps_path} 目录不存在，跳过模型加载')
        return

    for path in apps_path.iterdir():
        if not path.is_dir():
            continue

        # 👇 获取文件夹名称
        folder_name = path.name

        # 跳过以下划线/点开头 或 在忽略列表中的目录
        if folder_name.startswith(('_', '.')) or (folder_name in _IGNORE_DIRS):
            continue

        model_path = path / 'models'

        # 👇 检查 models 目录是否存在
        if model_path.exists():
            try:
                import_module(str(model_path))
                logger.debug(f'Loaded models: {model_path}')
            except Exception as e:
                logger.error(f'Load model failed: {model_path},exception info: {str(e)}')
