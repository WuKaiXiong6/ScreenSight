# 文件路径：backend/tests/conftest.py
# 文件作用：pytest 公共 fixture，提供隔离的临时数据库
# 最后更新时间：2026-06-28-1959
"""pytest 公共 fixture。"""
import pytest

from screensight.db import set_db_path, init_db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """每个测试用独立的临时数据库，避免污染真实数据。"""
    db_path = tmp_path / "test.db"
    set_db_path(db_path)
    init_db(db_path)
    yield
    set_db_path(None)
