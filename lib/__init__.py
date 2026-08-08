"""
親亡き後支援データベース - 共通ライブラリ
"""

from lib.db_new_operations import (
    get_driver,
    run_query,
    register_to_database,
    register_support_log,
    get_clients_list,
    get_client_stats,
    get_support_logs,
    discover_care_patterns,
    search_support_logs,
    validate_client_uniqueness
)
from lib.ai_extractor import get_agent, extract_from_text, parse_json_from_response, EXTRACTION_PROMPT
from lib.utils import safe_date_parse, init_session_state
from lib.file_readers import read_uploaded_file, get_supported_extensions

__all__ = [
    # db_operations
    'get_driver',
    'run_query',
    'register_to_database',
    'register_support_log',
    'get_clients_list',
    'get_client_stats',
    'get_support_logs',
    'discover_care_patterns',
    'search_support_logs',
    'validate_client_uniqueness',
    # ai_extractor
    'get_agent',
    'extract_from_text',
    'parse_json_from_response',
    'EXTRACTION_PROMPT',
    # utils
    'safe_date_parse',
    'init_session_state',
    # file_readers
    'read_uploaded_file',
    'get_supported_extensions',
]
