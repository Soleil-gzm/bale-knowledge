"""只负责 HTTP 校验与序列化的 Flask Adapter。"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

if TYPE_CHECKING:
    from .composition import ServiceContainer

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

vector_bp = Blueprint('vector', __name__, url_prefix='/api/vector')
services: ServiceContainer | None = None

ALLOWED_UPLOAD_EXTENSIONS = {'.txt', '.pdf', '.csv', '.docx', '.doc', '.xlsx', '.xls'}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_vector_system(
    milvus_host: str = None,
    milvus_port: str = None,
    embedding_model: str = None,
    dashscope_api_key: str = None
):
    """保留旧初始化入口，具体依赖仅在 composition 中组装。"""
    global services

    try:
        from .composition import create_services

        services = create_services(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_model=embedding_model,
            dashscope_api_key=dashscope_api_key,
        )
        logger.info("知识库应用服务初始化成功")
        return True
    except Exception as e:
        logger.error(f"知识库应用服务初始化失败: {str(e)}")
        return False


@vector_bp.route('/upload_file', methods=['POST'])
def upload_file():
    """通过 multipart 上传文档，并在处理后清理临时文件。"""

    if not services:
        return jsonify({'success': False, 'message': '向量系统未初始化'}), 400

    if request.content_length is not None and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({'success': False, 'message': '文件超过 20 MiB 限制'}), 413

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未找到文件部分'}), 400

    file = request.files['file']
    collection_name = request.form.get('collection_name', 'agent_rag')

    if not file.filename:
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({'success': False, 'message': '不支持的文件类型'}), 400

    stem = secure_filename(Path(file.filename).stem)
    filename = f"{stem or 'document'}{suffix}"

    try:
        with tempfile.TemporaryDirectory(prefix='bale_knowledge_') as upload_dir:
            file_path = Path(upload_dir) / filename
            file.save(file_path)
            chunk_count = services.ingestion.ingest_file(
                str(file_path),
                namespace=collection_name,
            )
            if not chunk_count:
                return jsonify({'success': False, 'message': '文件处理失败'}), 500

            db_info = services.collections.info(collection_name)

        return jsonify({
            'success': True,
            'message': f'文件上传并处理成功: {filename}',
            'database_info': db_info
        })
    except Exception:
        logger.exception("文件上传API错误")
        return jsonify({'success': False, 'message': '文件处理失败'}), 500


@vector_bp.route('/query', methods=['POST'])
def query_documents():
    """查询文档"""

    if not services:
        return jsonify({
            'success': False,
            'message': '向量系统未初始化'
        }), 400

    try:
        data = request.get_json()
        if not data or 'question' not in data or 'collection_name' not in data:
            return jsonify({
                'success': False,
                'message': '请提供 question 和 collection_name 参数'
            }), 400

        question = data['question']
        collection_name = data['collection_name']
        k = data.get('k', 5)  # 返回结果数量

        # 执行查询
        result = services.generation.answer(
            question,
            top_k=k,
            namespace=collection_name,
            filter_expression=data.get('filter_expression'),
        )

        return jsonify({
            'success': True,
            'question': question,
            'answer': result.answer,
            'question_type': result.question_type,
            'sources': [
                {
                    'content': hit.content,
                    'metadata': hit.metadata,
                    'score': hit.score
                }
                for hit in result.sources
            ]
        })

    except Exception as e:
        logger.error(f"查询API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败: {str(e)}'
        }), 500


@vector_bp.route('/search', methods=['POST'])
def search_similar():
    """相似性搜索"""

    if not services:
        return jsonify({
            'success': False,
            'message': '向量系统未初始化'
        }), 400

    try:
        data = request.get_json()
        if not data or 'query' not in data or 'collection_name' not in data:
            return jsonify({
                'success': False,
                'message': '请提供 query 和 collection_name 参数'
            }), 400

        query = data['query']
        collection_name = data['collection_name']
        k = data.get('k', 5)

        # 执行相似性搜索
        results = services.retrieval.search_sync(
            query,
            top_k=k,
            namespace=collection_name,
            filter_expression=data.get('filter_expression'),
        )

        return jsonify({
            'success': True,
            'query': query,
            'results': [
                {
                    'content': hit.content,
                    'metadata': hit.metadata,
                    'score': hit.score
                }
                for hit in results
            ]
        })

    except Exception as e:
        logger.error(f"搜索API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'搜索失败: {str(e)}'
        }), 500


@vector_bp.route('/collection_info', methods=['GET'])
def get_collection_info():
    """获取集合信息"""

    if not services:
        return jsonify({
            'success': False,
            'message': '向量系统未初始化'
        }), 400

    collection_name = request.args.get('collection_name')
    if not collection_name:
        return jsonify({
            'success': False,
            'message': '请提供 collection_name 参数'
        }), 400

    try:
        db_info = services.collections.info(collection_name)
        return jsonify({
            'success': True,
            'database_info': db_info
        })

    except Exception as e:
        logger.error(f"数据库信息API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取数据库信息失败: {str(e)}'
        }), 500


@vector_bp.route('/clear_collection', methods=['POST'])
def clear_collection():
    """清空集合"""

    if not services:
        return jsonify({
            'success': False,
            'message': '向量系统未初始化'
        }), 400

    data = request.get_json()
    if not data or 'collection_name' not in data:
        return jsonify({
            'success': False,
            'message': '请提供 collection_name 参数'
        }), 400

    collection_name = data['collection_name']

    try:
        cleared = services.collections.clear(collection_name)
        if not cleared:
            return jsonify({
                'success': False,
                'message': f"集合 '{collection_name}' 不存在"
            }), 404

        return jsonify({
            'success': True,
            'message': f"集合 '{collection_name}' 已清空"
        })

    except Exception as e:
        logger.error(f"清空数据库API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'清空数据库失败: {str(e)}'
        }), 500


# 错误处理
@vector_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': '接口不存在'
    }), 404


@vector_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': '服务器内部错误'
    }), 500


def register_vector_routes(app, service_container: ServiceContainer | None = None):
    """注册 Flask 路由，并支持从组合根注入应用服务。"""
    global services

    if service_container is not None:
        services = service_container
    else:
        with app.app_context():
            init_vector_system()

    app.register_blueprint(vector_bp)
    logger.info("知识库 API 路由已注册")
