# ruff: noqa
# mypy: ignore-errors
# Source: WebRPA@5ccb900e backend/app/services/file_share.py
# License: LICENSE.WebRPA
"""文件网络共享服务 - 提供局域网文件共享功能"""
import asyncio
import os
import socket
import threading
import mimetypes
import shutil
import subprocess
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote, unquote, urlparse
import json
import html

from .paths import ShareDirectory


def generate_video_thumbnail(video_path: Path, thumb_path: Path) -> Optional[Path]:
    """使用 ffmpeg 生成视频缩略图"""
    try:
        # 查找 ffmpeg
        ffmpeg_path = "ffmpeg"
        # 检查 backend 目录是否有 ffmpeg.exe
        backend_ffmpeg = Path(__file__).resolve().parent.parent.parent / "ffmpeg.exe"
        if backend_ffmpeg.exists():
            ffmpeg_path = str(backend_ffmpeg)

        # 使用 ffmpeg 生成缩略图
        cmd = [
            ffmpeg_path,
            "-i", str(video_path),
            "-ss", "00:00:01",  # 跳到1秒位置
            "-vframes", "1",
            "-vf", "scale=96:96:force_original_aspect_ratio=increase,crop=96:96",
            "-y",
            str(thumb_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        if thumb_path.exists():
            return thumb_path
        return None
    except Exception:
        return None


def get_local_ip() -> str:
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class FileShareHandler(SimpleHTTPRequestHandler):
    """自定义文件共享处理器"""

    # 类变量，用于存储共享配置
    share_config: Dict[str, Any] = {}
    allow_write: bool = True

    def __init__(self, *args, **kwargs):
        # 设置共享目录
        self.share_path = self.share_config.get('path', '.')
        self.share_type = self.share_config.get('type', 'folder')  # folder 或 file
        self.share_name = self.share_config.get('name', '共享')
        super().__init__(*args, directory=self.share_path if self.share_type == 'folder' else str(Path(self.share_path).parent), **kwargs)

    @property
    def files(self):
        return self.server.shared_directory

    def _write_body(self, content):
        if self.command != 'HEAD':
            self.wfile.write(content)

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, format, *args):
        """静默日志"""
        pass

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """处理 POST 请求（上传文件、创建文件夹）"""
        path = unquote(urlparse(self.path).path)

        if not self.allow_write or self.share_type != 'folder':
            self._send_json({'success': False, 'error': '此共享不允许写操作'}, 403)
            return

        if path == '/api/upload':
            self._handle_upload()
        elif path == '/api/mkdir':
            self._handle_mkdir()
        else:
            self.send_error(404, "Not found")

    def do_DELETE(self):
        """处理 DELETE 请求（删除文件/文件夹）"""
        path = unquote(urlparse(self.path).path)

        if not self.allow_write or self.share_type != 'folder':
            self._send_json({'success': False, 'error': '此共享不允许写操作'}, 403)
            return

        if path.startswith('/api/delete/'):
            file_path = path[12:]
            self._handle_delete(file_path)
        else:
            self.send_error(404, "Not found")

    def _send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        response = json.dumps(data, ensure_ascii=False)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self._write_body(response.encode('utf-8'))

    # 单次上传请求体最大值（默认 500MB），防止 OOM
    MAX_UPLOAD_BODY_SIZE = 500 * 1024 * 1024

    def _handle_upload(self):
        """处理文件上传"""
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))

            if content_length <= 0:
                self._send_json({'success': False, 'error': '无效的请求长度'}, 400)
                return
            # 拒绝过大请求体
            if content_length > self.MAX_UPLOAD_BODY_SIZE:
                self._send_json({
                    'success': False,
                    'error': f'文件过大（最大允许 {self.MAX_UPLOAD_BODY_SIZE // (1024*1024)} MB）'
                }, 413)
                return

            if 'multipart/form-data' not in content_type:
                self._send_json({'success': False, 'error': '无效的 Content-Type'}, 400)
                return

            # 解析 boundary
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip('"')
                    break

            if not boundary:
                self._send_json({'success': False, 'error': '无法解析 boundary'}, 400)
                return

            # 读取请求体
            body = self.rfile.read(content_length)
            if len(body) != content_length:
                self._send_json({'success': False, 'error': '上传请求未完整接收'}, 400)
                return
            boundary_bytes = ('--' + boundary).encode()
            if not body.rstrip(b'\r\n').endswith(boundary_bytes + b'--'):
                self._send_json({'success': False, 'error': '上传请求未完整接收'}, 400)
                return
            parts = body.split(boundary_bytes)

            upload_path = '/'
            uploaded_files = []

            for part in parts:
                if not part or part == b'--\r\n' or part == b'--':
                    continue

                if b'\r\n\r\n' not in part:
                    continue

                header_end = part.index(b'\r\n\r\n')
                headers_raw = part[:header_end].decode('utf-8', errors='ignore')
                content = part[header_end + 4:]

                if content.endswith(b'\r\n'):
                    content = content[:-2]

                # 解析 Content-Disposition
                filename = None
                field_name = None

                for line in headers_raw.split('\r\n'):
                    if line.lower().startswith('content-disposition:'):
                        for item in line.split(';'):
                            item = item.strip()
                            if item.startswith('name="'):
                                field_name = item[6:-1]
                            elif item.startswith('filename="'):
                                filename = item[10:-1]

                if field_name == 'path':
                    upload_path = content.decode('utf-8')
                elif field_name == 'file' and filename:
                    # 安全：filename 强制只取最终的文件名部分，并清理非法字符
                    import os as _os
                    filename = _os.path.basename(filename.replace('\\', '/'))
                    # 过滤 Windows 非法字符与空文件名
                    filename = ''.join(c for c in filename if c not in '\\/:*?"<>|').strip()
                    if not filename:
                        self._send_json({'success': False, 'error': '文件名无效'}, 400)
                        return

                    saved_name = self.files.upload(upload_path, filename, content)
                    uploaded_files.append(saved_name)

            if uploaded_files:
                self._send_json({
                    'success': True,
                    'message': f'成功上传 {len(uploaded_files)} 个文件',
                    'files': uploaded_files
                })
            else:
                self._send_json({'success': False, 'error': '没有找到要上传的文件'}, 400)

        except PermissionError:
            self._send_json({'success': False, 'error': '共享路径访问被拒绝'}, 403)
        except (ValueError, UnicodeError):
            self._send_json({'success': False, 'error': '上传参数无效'}, 400)
        except Exception as e:
            self._send_json({'success': False, 'error': f'上传失败: {str(e)}'}, 500)

    def _handle_mkdir(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 1 or length > 65536:
                self._send_json({'success': False, 'error': '无效的请求长度'}, 400)
                return
            data = json.loads(self.rfile.read(length))
            self.files.mkdir(data.get('path', '/'), data.get('name', ''))
            self._send_json({'success': True, 'message': '文件夹创建成功'})
        except PermissionError:
            self._send_json({'success': False, 'error': '共享路径访问被拒绝'}, 403)
        except (ValueError, TypeError, FileExistsError):
            self._send_json({'success': False, 'error': '目录参数无效或已存在'}, 400)
        except FileNotFoundError:
            self._send_json({'success': False, 'error': '父目录不存在'}, 404)

    def _handle_delete(self, file_path: str):
        try:
            self.files.delete(file_path)
            self._send_json({'success': True, 'message': '删除成功'})
        except PermissionError:
            self._send_json({'success': False, 'error': '共享路径访问被拒绝'}, 403)
        except FileNotFoundError:
            self._send_json({'success': False, 'error': '文件或目录不存在'}, 404)

    def do_GET(self):
        """处理GET请求"""
        # 解码URL路径
        path = unquote(urlparse(self.path).path)

        # 如果是单文件共享
        if self.share_type == 'file':
            file_path = Path(self.share_config.get('path', ''))
            if path == '/' or path == '':
                # 返回文件下载页面
                self.send_file_download_page(file_path)
                return
            elif path in ('/download', '/' + file_path.name):
                # 直接下载文件
                self.send_file(file_path)
                return
            else:
                self.send_error(404, "File not found")
                return

        # 文件夹共享
        if path == '/api/list' or path == '/api/list/':
            # API: 获取文件列表（根目录）
            self.send_file_list('/')
            return
        elif path.startswith('/api/list/'):
            # API: 获取子目录文件列表
            sub_path = path[10:]  # 移除 '/api/list/'
            if not sub_path or sub_path == '/':
                self.send_file_list('/')
            else:
                self.send_file_list(sub_path)
            return
        elif path.startswith('/thumb/'):
            # 视频缩略图
            file_path = path[7:]  # 移除 '/thumb/'
            self.send_video_thumbnail(file_path)
            return
        elif path.startswith('/download/'):
            # 下载文件
            file_path = path[10:]  # 移除 '/download/'
            self.send_file_download(file_path)
            return
        elif path.startswith('/preview/'):
            # 文档预览（Excel、Word、PPT）
            file_path = path[9:]  # 移除 '/preview/'
            self.send_document_preview(file_path)
            return
        elif path == '/' or path == '':
            # 返回文件浏览器页面
            self.send_browser_page()
            return
        else:
            # 尝试作为静态文件处理
            self.send_file_download(path.lstrip('/'))

    def send_video_thumbnail(self, file_path: str):
        """ffmpeg receives a private snapshot, never a mutable shared pathname."""
        try:
            with self.files.open_file(file_path) as source:
                with tempfile.TemporaryDirectory(prefix='autoflow-thumb-') as temporary:
                    snapshot = Path(temporary) / ('source' + Path(file_path).suffix)
                    with snapshot.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    thumb = generate_video_thumbnail(snapshot, Path(temporary) / "thumbnail.jpg")
                    if thumb is None:
                        self.send_error(404, 'Thumbnail not available')
                        return
                    try:
                        content = thumb.read_bytes()
                    finally:
                        thumb.unlink(missing_ok=True)
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self._write_body(content)
        except PermissionError:
            self.send_error(403, 'Access denied')
        except FileNotFoundError:
            self.send_error(404, 'File not found')
        except (ConnectionError, BrokenPipeError):
            pass

    def send_file_list(self, sub_path: str):
        try:
            items = self.files.entries(sub_path)
            self._send_json({'success': True, 'path': sub_path, 'items': items, 'shareName': self.share_name})
        except PermissionError:
            self.send_error(403, 'Access denied')
        except FileNotFoundError:
            self.send_error(404, 'Directory not found')

    def send_file_download(self, file_path: str):
        self.send_file(file_path, force_download=False)

    def send_document_preview(self, file_path: str):
        # No document renderer has been migrated. Preserve file download and the
        # browser's existing image/audio/video/text previews; do not fake success.
        try:
            with self.files.open_file(file_path):
                self._send_json({'success': False, 'error': '此文件暂不支持在线文档预览，请下载后打开'}, 415)
        except PermissionError:
            self.send_error(403, 'Access denied')
        except FileNotFoundError:
            self.send_error(404, 'File not found')

    def send_file(self, file_path, force_download: bool = True):
        relative = Path(file_path).name if self.share_type == 'file' else str(file_path)
        try:
            with self.files.open_file(relative) as stream:
                size = os.fstat(stream.fileno()).st_size
                mime_type = mimetypes.guess_type(relative)[0] or 'application/octet-stream'
                start, end, status = 0, size - 1, 200
                requested = self.headers.get('Range')
                if requested:
                    try:
                        if not requested.startswith('bytes=') or ',' in requested:
                            raise ValueError
                        first, last = requested[6:].split('-')
                        if first:
                            start = int(first)
                            end = min(int(last), size - 1) if last else size - 1
                        else:
                            length = int(last)
                            if length <= 0:
                                raise ValueError
                            start = max(0, size - length)
                        if start < 0 or start > end or start >= size:
                            raise ValueError
                    except ValueError:
                        self.send_error(416, 'Range Not Satisfiable')
                        return
                    status = 206
                self.send_response(status)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(max(0, end - start + 1)))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if status == 206:
                    self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                if force_download:
                    self.send_header('Content-Disposition', f'attachment; filename="{quote(Path(relative).name)}"')
                self.end_headers()
                if self.command == 'HEAD':
                    return
                stream.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = stream.read(min(8192, remaining))
                    if not chunk:
                        break
                    self._write_body(chunk)
                    remaining -= len(chunk)
        except PermissionError:
            self.send_error(403, 'Access denied')
        except FileNotFoundError:
            self.send_error(404, 'File not found')
        except (ConnectionError, BrokenPipeError):
            pass

    def send_file_download_page(self, file_path: Path):
        """发送单文件下载页面"""
        with self.files.open_file(file_path.name) as stream:
            file_size = os.fstat(stream.fileno()).st_size
        size_str = format_size(file_size)

        html_content = get_single_file_page(file_path.name, size_str)

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self._write_body(html_content.encode('utf-8'))

    def send_browser_page(self):
        """发送文件浏览器页面"""
        html_content = get_browser_page(self.share_name, self.share_config.get('allow_write', True))

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self._write_body(html_content.encode('utf-8'))

    @staticmethod
    def format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != 'B' else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


def get_single_file_page(filename: str, size: str) -> str:
    """获取单文件下载页面HTML - 使用新模板"""
    from .file_share_page import get_single_file_page as _get_single_file_page
    return _get_single_file_page(filename, size)


def get_browser_page(share_name: str, allow_write: bool = True) -> str:
    """获取文件浏览器页面HTML - 使用新模板"""
    from .file_share_page import get_browser_page as _get_browser_page
    return _get_browser_page(share_name, allow_write)


# 全局共享服务管理
_share_servers: Dict[int, tuple] = {}  # port -> (server, thread, config)


class ThreadedHTTPServer(HTTPServer):
    """支持多线程的 HTTP 服务器，允许多个客户端同时访问"""
    allow_reuse_address = True

    def __init__(self, address, handler):
        config = handler.share_config
        path = Path(config['path'])
        self.shared_directory = ShareDirectory(path if config.get('type', 'folder') == 'folder' else path.parent)
        try:
            super().__init__(address, handler)
        except BaseException:
            self.shared_directory.close()
            raise

    def server_close(self):
        super().server_close()
        self.shared_directory.close()

    def process_request(self, request, client_address):
        """为每个请求创建新线程"""
        thread = threading.Thread(target=self.process_request_thread, args=(request, client_address))
        thread.daemon = True
        thread.start()

    def process_request_thread(self, request, client_address):
        """在线程中处理请求"""
        try:
            self.finish_request(request, client_address)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # 客户端断开连接，静默处理
            pass
        except Exception:
            try:
                self.handle_error(request, client_address)
            except Exception:
                pass
        finally:
            try:
                self.shutdown_request(request)
            except Exception:
                pass


def start_file_share(path: str, port: int, share_type: str = 'folder', name: str = '共享', allow_write: bool = True) -> dict:
    """启动文件共享服务"""
    global _share_servers

    if port in _share_servers:
        stop_file_share(port)

    path_obj = Path(path)
    if not path_obj.exists():
        return {'success': False, 'error': f'路径不存在: {path}'}

    if share_type == 'file' and not path_obj.is_file():
        return {'success': False, 'error': f'不是文件: {path}'}

    if share_type == 'folder' and not path_obj.is_dir():
        return {'success': False, 'error': f'不是文件夹: {path}'}

    try:
        config = {
            'path': str(path_obj.resolve()),
            'type': share_type,
            'name': name,
            'allow_write': allow_write
        }

        handler = type(
            f"FileShareHandler_{port}",
            (FileShareHandler,),
            {"share_config": config, "allow_write": allow_write},
        )

        # 使用多线程服务器，支持多个客户端同时访问
        server = ThreadedHTTPServer(('0.0.0.0', port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _share_servers[port] = (server, thread, config)

        local_ip = get_local_ip()
        return {
            'success': True,
            'port': port,
            'ip': local_ip,
            'url': f'http://{local_ip}:{port}',
            'message': f'共享服务已启动，同局域网设备可访问: http://{local_ip}:{port}'
        }

    except OSError as e:
        if 'Address already in use' in str(e) or '10048' in str(e):
            return {'success': False, 'error': f'端口 {port} 已被占用，请更换端口'}
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def stop_file_share(port: int) -> dict:
    """停止文件共享服务"""
    global _share_servers

    if port not in _share_servers:
        return {'success': False, 'error': f'端口 {port} 没有运行共享服务'}

    try:
        server, thread, config = _share_servers[port]
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        del _share_servers[port]
        return {'success': True, 'message': f'端口 {port} 的共享服务已停止'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_active_shares() -> list:
    """获取所有活动的共享服务"""
    return [{'port': port, 'config': config} for port, (_, _, config) in _share_servers.items()]


def stop_all_file_shares():
    for port in list(_share_servers):
        stop_file_share(port)
