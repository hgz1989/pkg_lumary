import pytest
from pathlib import Path
from lumary.common.utils import paths

def test_paths_types():
    """测试解析出来的路径类型都是 pathlib.Path"""
    assert isinstance(paths.root_dir, Path)
    assert isinstance(paths.apps_dir, Path)
    assert isinstance(paths.logs_dir, Path)

def test_paths_readonly_attributes():
    """测试动态路径属性是否为只读"""
    with pytest.raises(AttributeError, match="不能修改只读属性 'root_dir'"):
        paths.root_dir = Path('/tmp')
        
    with pytest.raises(AttributeError, match="不能修改只读属性 'apps_dir'"):
        paths.apps_dir = Path('/tmp')

    with pytest.raises(AttributeError, match="不能删除只读属性 'logs_dir'"):
        del paths.logs_dir
