# ruff: noqa
# mypy: ignore-errors
# Source: WebRPA@5ccb900e backend/app/services/file_share_page.py
# License: LICENSE.WebRPA
"""文件共享页面模板 - 支持本地预览、缩略图、返回按钮、手机端优化"""
import html


def get_browser_page(share_name: str, allow_write: bool = True) -> str:
    """获取文件浏览器页面HTML - 完整功能版本"""
    allow_write_js = 'true' if allow_write else 'false'
    escaped_name = html.escape(share_name)

    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>''' + escaped_name + ''' - 文件共享</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect fill='%233b82f6' rx='4' width='24' height='24'/><path fill='white' d='M10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6H12L10,4Z'/></svg>">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fafafa; min-height: 100vh; min-height: 100dvh; }
        .header { background: #18181b; border-bottom: 1px solid #27272a; padding: 12px 16px; position: sticky; top: 0; z-index: 100; }
        .header-top { display: flex; align-items: center; gap: 12px; }
        .back-btn { width: 36px; height: 36px; border-radius: 8px; background: #27272a; border: none; color: #fafafa; cursor: pointer; display: none; align-items: center; justify-content: center; flex-shrink: 0; }
        .back-btn:hover { background: #3f3f46; }
        .back-btn:active { background: #52525b; }
        .back-btn.show { display: flex; }
        .back-btn svg { width: 20px; height: 20px; fill: currentColor; }
        .header h1 { font-size: 16px; font-weight: 600; color: #fafafa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .breadcrumb { margin-top: 8px; font-size: 12px; color: #a1a1aa; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
        .breadcrumb a { color: #3b82f6; text-decoration: none; cursor: pointer; }
        .breadcrumb span { color: #52525b; }
        .container { max-width: 1200px; margin: 0 auto; padding: 12px; }
        .toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
        .btn { padding: 8px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-danger { background: transparent; color: #ef4444; border: 1px solid #ef4444; padding: 6px 10px; font-size: 12px; }
        .btn-danger:hover { background: #ef4444; color: white; }
        .btn-ghost { background: #27272a; color: #fafafa; }
        .btn-ghost:hover { background: #3f3f46; }
        .file-list { background: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden; }
        .file-item { display: flex; align-items: center; padding: 10px 12px; border-bottom: 1px solid #27272a; cursor: pointer; transition: background 0.15s; gap: 10px; }
        .file-item:last-child { border-bottom: none; }
        .file-item:hover { background: #27272a; }
        .file-item:active { background: #3f3f46; }
        .file-thumb { width: 48px; height: 48px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; background: #27272a; }
        .file-thumb.folder { background: #854d0e; }
        .file-thumb.image, .file-thumb.video { background: #000; }
        .file-thumb img, .file-thumb video { width: 100%; height: 100%; object-fit: cover; }
        .file-thumb svg { width: 22px; height: 22px; fill: white; }
        .file-thumb.audio { background: #7c3aed; }
        .file-thumb.pdf { background: #dc2626; }
        .file-thumb.doc { background: #2563eb; }
        .file-thumb.xls { background: #16a34a; }
        .file-thumb.ppt { background: #ea580c; }
        .file-thumb.zip { background: #ca8a04; }
        .file-thumb.code { background: #0891b2; }
        .file-thumb.text { background: #64748b; }
        .file-info { flex: 1; min-width: 0; }
        .file-name { font-size: 14px; font-weight: 500; color: #fafafa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .file-meta { font-size: 11px; color: #71717a; margin-top: 2px; }
        .file-actions { flex-shrink: 0; display: flex; gap: 6px; opacity: 0; transition: opacity 0.15s; }
        .file-item:hover .file-actions { opacity: 1; }
        .empty { text-align: center; padding: 48px 20px; color: #71717a; }
        .empty-icon { font-size: 40px; margin-bottom: 8px; }
        .modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); z-index: 1000; align-items: center; justify-content: center; padding: 16px; }
        .modal.show { display: flex; }
        .modal-content { background: #18181b; border: 1px solid #27272a; padding: 16px; border-radius: 12px; width: 100%; max-width: 400px; max-height: 90vh; overflow-y: auto; }
        .modal-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #fafafa; }
        .modal-input { width: 100%; padding: 10px 12px; background: #27272a; border: 1px solid #3f3f46; border-radius: 6px; margin-bottom: 12px; font-size: 14px; color: #fafafa; }
        .modal-input:focus { outline: none; border-color: #3b82f6; }
        .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
        .preview-modal { padding: 0; background: rgba(0,0,0,0.95); }
        .preview-container { width: 100%; height: 100%; display: flex; flex-direction: column; }
        .preview-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: #18181b; border-bottom: 1px solid #27272a; flex-shrink: 0; }
        .preview-title { font-size: 14px; font-weight: 500; color: #fafafa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; margin-right: 12px; }
        .preview-actions { display: flex; gap: 8px; }
        .preview-body { flex: 1; overflow: auto; display: flex; align-items: center; justify-content: center; padding: 16px; min-height: 0; }
        .preview-body img { max-width: 100%; max-height: 100%; object-fit: contain; }
        .preview-body video { width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; background: #000; }
        .preview-body audio { max-width: 100%; }
        .preview-body iframe { width: 100%; height: 100%; border: none; background: white; }
        .preview-body pre { background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 8px; overflow: auto; width: 100%; max-height: 100%; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
        .preview-body .unsupported { text-align: center; color: #71717a; }
        .preview-body .unsupported svg { width: 64px; height: 64px; fill: #52525b; margin-bottom: 16px; }
        .upload-area { border: 2px dashed #3f3f46; border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 12px; transition: all 0.2s; }
        .upload-area.dragover { border-color: #3b82f6; background: rgba(59,130,246,0.1); }
        .upload-area input { display: none; }
        .upload-label { cursor: pointer; color: #a1a1aa; }
        @media (max-width: 640px) {
            .header { padding: 10px 12px; }
            .header h1 { font-size: 15px; }
            .container { padding: 10px; }
            .toolbar { gap: 6px; }
            .btn { padding: 8px 10px; font-size: 12px; }
            .file-item { padding: 10px; }
            .file-thumb { width: 44px; height: 44px; }
            .file-name { font-size: 13px; }
            .file-actions { opacity: 1; }
            .btn-danger { padding: 5px 8px; font-size: 11px; }
            .preview-header { padding: 10px 12px; }
            .preview-body { padding: 8px; }
        }
    </style></head>
<body>
    <div class="header">
        <div class="header-top">
            <button class="back-btn" id="backBtn" onclick="goBack()" title="返回上一层">
                <svg viewBox="0 0 24 24"><path d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z"/></svg>
            </button>
            <h1>📂 ''' + escaped_name + '''</h1>
        </div>
        <div class="breadcrumb" id="breadcrumb"></div>
    </div>
    <div class="container">
        <div class="toolbar" id="toolbar">
            <button class="btn btn-primary" onclick="showUploadModal()">📤 上传</button>
            <button class="btn btn-ghost" onclick="showMkdirModal()">📁 新建文件夹</button>
        </div>
        <div class="file-list" id="fileList"><div class="empty"><div class="empty-icon">⏳</div>加载中...</div></div>
    </div>
    <div class="modal" id="mkdirModal" onclick="if(event.target===this)closeMkdirModal()">
        <div class="modal-content">
            <div class="modal-title">新建文件夹</div>
            <input type="text" class="modal-input" id="folderName" placeholder="请输入文件夹名称">
            <div class="modal-actions">
                <button class="btn btn-ghost" onclick="closeMkdirModal()">取消</button>
                <button class="btn btn-primary" onclick="createFolder()">创建</button>
            </div>
        </div>
    </div>
    <div class="modal" id="uploadModal" onclick="if(event.target===this)closeUploadModal()">
        <div class="modal-content">
            <div class="modal-title">上传文件</div>
            <div class="upload-area" id="uploadArea">
                <input type="file" id="fileInput" multiple>
                <label class="upload-label" for="fileInput">
                    <div style="font-size:32px;margin-bottom:8px;">📁</div>
                    <div>点击选择或拖拽文件</div>
                </label>
            </div>
            <div id="uploadList" style="margin-bottom:12px;font-size:13px;color:#a1a1aa;"></div>
            <div class="modal-actions">
                <button class="btn btn-ghost" onclick="closeUploadModal()">取消</button>
                <button class="btn btn-primary" id="uploadBtn" onclick="uploadFiles()">上传</button>
            </div>
        </div>
    </div>
    <div class="modal preview-modal" id="previewModal" onclick="if(event.target===this)closePreview()">
        <div class="preview-container">
            <div class="preview-header">
                <span class="preview-title" id="previewTitle"></span>
                <div class="preview-actions">
                    <button class="btn btn-ghost" onclick="downloadCurrent()">📥 下载</button>
                    <button class="btn btn-ghost" onclick="closePreview()">✕</button>
                </div>
            </div>
            <div class="preview-body" id="previewBody"></div>
        </div>
    </div>
    <script>
        var allowWrite = ''' + allow_write_js + ''';
        var currentPath = "/";
        var currentPreviewPath = "";

        function getFileType(name) {
            var ext = name.split('.').pop().toLowerCase();
            var types = {
                image: ['jpg','jpeg','png','gif','webp','bmp','svg','ico'],
                video: ['mp4','webm','mov','avi','mkv','m4v','flv','wmv','3gp'],
                audio: ['mp3','wav','ogg','m4a','flac','aac','wma'],
                pdf: ['pdf'],
                doc: ['doc','docx'],
                xls: ['xls','xlsx','csv'],
                ppt: ['ppt','pptx'],
                zip: ['zip','rar','7z','tar','gz'],
                code: ['js','ts','py','java','c','cpp','h','css','html','xml','json','md','sql','sh','bat','yml','yaml'],
                text: ['txt','log','ini','cfg','conf']
            };
            for (var type in types) {
                if (types[type].indexOf(ext) >= 0) return type;
            }
            return 'file';
        }

        function getFileIcon(type) {
            var icons = {
                folder: '<svg viewBox="0 0 24 24"><path d="M10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6H12L10,4Z"/></svg>',
                image: '<svg viewBox="0 0 24 24"><path d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5C21,3.89 20.1,3 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z"/></svg>',
                video: '<svg viewBox="0 0 24 24"><path d="M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z"/></svg>',
                audio: '<svg viewBox="0 0 24 24"><path d="M12,3V12.26C11.5,12.09 11,12 10.5,12C8,12 6,14 6,16.5C6,19 8,21 10.5,21C13,21 15,19 15,16.5V6H19V3H12Z"/></svg>',
                pdf: '<svg viewBox="0 0 24 24"><path d="M19,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3M9.5,11.5C9.5,12.3 8.8,13 8,13H7V15H5.5V9H8C8.8,9 9.5,9.7 9.5,10.5V11.5M14.5,13.5C14.5,14.3 13.8,15 13,15H10.5V9H13C13.8,9 14.5,9.7 14.5,10.5V13.5M18.5,10.5H17V11.5H18.5V13H17V15H15.5V9H18.5V10.5M7,10.5H8V11.5H7V10.5M12,10.5H13V13.5H12V10.5Z"/></svg>',
                doc: '<svg viewBox="0 0 24 24"><path d="M6,2H14L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2M13,3.5V9H18.5L13,3.5M7,13L8.5,18H10L11.5,13H10L9.25,16L8.5,13H7Z"/></svg>',
                xls: '<svg viewBox="0 0 24 24"><path d="M6,2H14L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2M13,3.5V9H18.5L13,3.5M8,11V13H10V11H8M12,11V13H14V11H12M8,15V17H10V15H8M12,15V17H14V15H12Z"/></svg>',
                ppt: '<svg viewBox="0 0 24 24"><path d="M6,2H14L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2M13,3.5V9H18.5L13,3.5M8,11V17H10V15H11A2,2 0 0,0 13,13V12A2,2 0 0,0 11,10H8V11M10,11H11V13H10V11Z"/></svg>',
                zip: '<svg viewBox="0 0 24 24"><path d="M14,17H12V15H10V13H12V15H14M14,9H12V11H14V13H12V11H10V9H12V7H10V5H12V7H14M19,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3Z"/></svg>',
                code: '<svg viewBox="0 0 24 24"><path d="M14.6,16.6L19.2,12L14.6,7.4L16,6L22,12L16,18L14.6,16.6M9.4,16.6L4.8,12L9.4,7.4L8,6L2,12L8,18L9.4,16.6Z"/></svg>',
                text: '<svg viewBox="0 0 24 24"><path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20M9,13V15H15V13H9M9,17V19H13V17H9Z"/></svg>',
                file: '<svg viewBox="0 0 24 24"><path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/></svg>'
            };
            return icons[type] || icons.file;
        }

        function formatSize(bytes) {
            if (bytes < 1024) return bytes + " B";
            if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + " KB";
            if (bytes < 1024*1024*1024) return (bytes/1024/1024).toFixed(1) + " MB";
            return (bytes/1024/1024/1024).toFixed(1) + " GB";
        }

        function escapeHtml(text) {
            var div = document.createElement("div");
            div.textContent = text;
            return div.innerHTML;
        }

        function goBack() {
            var parts = currentPath.split("/").filter(function(p) { return p; });
            parts.pop();
            currentPath = "/" + parts.join("/");
            loadFiles();
        }

        function updateBackBtn() {
            var btn = document.getElementById("backBtn");
            if (currentPath === "/" || currentPath === "") {
                btn.classList.remove("show");
            } else {
                btn.classList.add("show");
            }
        }

        function updateBreadcrumb() {
            var parts = currentPath.split("/").filter(function(p) { return p; });
            var bc = document.getElementById("breadcrumb");
            bc.innerHTML = "";
            var a = document.createElement("a");
            a.textContent = "根目录";
            a.onclick = function() { currentPath = "/"; loadFiles(); };
            bc.appendChild(a);
            var path = "";
            parts.forEach(function(part) {
                path += "/" + part;
                var span = document.createElement("span");
                span.textContent = " / ";
                bc.appendChild(span);
                var link = document.createElement("a");
                link.textContent = part;
                (function(p) { link.onclick = function() { currentPath = p; loadFiles(); }; })(path);
                bc.appendChild(link);
            });
        }

        function loadFiles() {
            updateBreadcrumb();
            updateBackBtn();
            fetch("/api/list" + currentPath)
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    var list = document.getElementById("fileList");
                    if (!data.success) {
                        list.innerHTML = '<div class="empty"><div class="empty-icon">❌</div>' + escapeHtml(data.error || "加载失败") + '</div>';
                        return;
                    }
                    if (data.items.length === 0) {
                        list.innerHTML = '<div class="empty"><div class="empty-icon">📂</div>空文件夹</div>';
                        return;
                    }
                    var html = "";
                    data.items.forEach(function(item) {
                        var isFolder = item.type === "folder";
                        var fileType = isFolder ? "folder" : getFileType(item.name);
                        var thumbHtml = "";
                        var encodedPath = encodeURIComponent(item.path);

                        if (fileType === "image") {
                            thumbHtml = '<div class="file-thumb image"><img src="/download/' + encodedPath + '" loading="lazy" onerror="this.style.display=\\'none\\'"></div>';
                        } else if (fileType === "video") {
                            thumbHtml = '<div class="file-thumb video"><img src="/thumb/' + encodedPath + '" loading="lazy" onerror="this.style.display=\\'none\\'"></div>';
                        } else {
                            thumbHtml = '<div class="file-thumb ' + fileType + '">' + getFileIcon(fileType) + '</div>';
                        }

                        var escapedPath = item.path.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
                        var escapedName = item.name.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
                        html += '<div class="file-item" onclick="itemClick(event,' + isFolder + ',\\'' + escapedPath + '\\',\\'' + escapedName + '\\')">';
                        html += thumbHtml;
                        html += '<div class="file-info">';
                        html += '<div class="file-name">' + escapeHtml(item.name) + '</div>';
                        html += '<div class="file-meta">' + (isFolder ? "文件夹" : formatSize(item.size)) + '</div>';
                        html += '</div>';
                        if (allowWrite) {
                            html += '<div class="file-actions"><button class="btn btn-danger" onclick="deleteItem(event,\\'' + escapedPath + '\\')">删除</button></div>';
                        }
                        html += '</div>';
                    });
                    list.innerHTML = html;
                })
                .catch(function(err) {
                    document.getElementById("fileList").innerHTML = '<div class="empty"><div class="empty-icon">❌</div>' + escapeHtml(err && err.message ? err.message : '请求失败') + '</div>';
                });
        }

        function itemClick(event, isFolder, path, name) {
            if (event.target.tagName === "BUTTON") return;
            if (isFolder) {
                currentPath = "/" + path;
                loadFiles();
            } else {
                openPreview(path, name);
            }
        }

        function openPreview(path, name) {
            currentPreviewPath = path;
            document.getElementById("previewTitle").textContent = name;
            var body = document.getElementById("previewBody");
            var fileType = getFileType(name);
            var url = "/download/" + encodeURIComponent(path);
            var previewUrl = "/preview/" + encodeURIComponent(path);

            if (fileType === "image") {
                body.innerHTML = '<img src="' + url + '">';
            } else if (fileType === "video") {
                body.innerHTML = '<video src="' + url + '" controls autoplay playsinline></video>';
            } else if (fileType === "audio") {
                body.innerHTML = '<div style="text-align:center;width:100%;"><div style="font-size:80px;margin-bottom:20px;">🎵</div><audio src="' + url + '" controls autoplay style="width:100%;max-width:400px;"></audio><div style="margin-top:16px;color:#a1a1aa;">' + escapeHtml(name) + '</div></div>';
            } else if (fileType === "pdf") {
                body.innerHTML = '<iframe src="' + url + '"></iframe>';
            } else if (fileType === "doc" || fileType === "xls" || fileType === "ppt") {
                // Office 文档使用 iframe 加载预览页面
                body.innerHTML = '<iframe src="' + previewUrl + '"></iframe>';
            } else if (fileType === "text" || fileType === "code") {
                fetch(url).then(function(res) { return res.text(); }).then(function(text) {
                    body.innerHTML = '<pre>' + escapeHtml(text) + '</pre>';
                }).catch(function() {
                    body.innerHTML = '<div class="unsupported">无法加载文件</div>';
                });
            } else {
                body.innerHTML = '<div class="unsupported"><svg viewBox="0 0 24 24"><path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/></svg><div style="margin-bottom:20px;">' + escapeHtml(name) + '</div><button class="btn btn-primary" onclick="downloadCurrent()">📥 下载文件</button></div>';
            }
            document.getElementById("previewModal").classList.add("show");
            document.body.style.overflow = "hidden";
        }

        function closePreview() {
            document.getElementById("previewModal").classList.remove("show");
            document.getElementById("previewBody").innerHTML = "";
            document.body.style.overflow = "";
        }

        function downloadCurrent() {
            if (currentPreviewPath) {
                window.location.href = "/download/" + encodeURIComponent(currentPreviewPath);
            }
        }

        function deleteItem(event, path) {
            event.stopPropagation();
            if (!confirm("确定要删除吗？")) return;
            fetch("/api/delete/" + encodeURIComponent(path), { method: "DELETE" })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.success) { loadFiles(); } else { alert(data.error || "删除失败"); }
                })
                .catch(function(err) { alert("删除失败: " + err.message); });
        }

        function showMkdirModal() {
            document.getElementById("mkdirModal").classList.add("show");
            document.getElementById("folderName").value = "";
            document.getElementById("folderName").focus();
        }
        function closeMkdirModal() { document.getElementById("mkdirModal").classList.remove("show"); }
        function showUploadModal() {
            document.getElementById("uploadModal").classList.add("show");
            document.getElementById("fileInput").value = "";
            document.getElementById("uploadList").innerHTML = "";
        }
        function closeUploadModal() { document.getElementById("uploadModal").classList.remove("show"); }

        function createFolder() {
            var name = document.getElementById("folderName").value.trim();
            if (!name) { alert("请输入文件夹名称"); return; }
            fetch("/api/mkdir", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({path: currentPath, name: name})
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.success) { closeMkdirModal(); loadFiles(); } else { alert(data.error || "创建失败"); }
            })
            .catch(function(err) { alert("创建失败: " + err.message); });
        }

        var uploadArea = document.getElementById("uploadArea");
        var fileInput = document.getElementById("fileInput");

        uploadArea.addEventListener("dragover", function(e) {
            e.preventDefault();
            uploadArea.classList.add("dragover");
        });
        uploadArea.addEventListener("dragleave", function() {
            uploadArea.classList.remove("dragover");
        });
        uploadArea.addEventListener("drop", function(e) {
            e.preventDefault();
            uploadArea.classList.remove("dragover");
            fileInput.files = e.dataTransfer.files;
            updateUploadList();
        });
        fileInput.addEventListener("change", updateUploadList);

        function updateUploadList() {
            var files = fileInput.files;
            var list = document.getElementById("uploadList");
            if (files.length === 0) { list.innerHTML = ""; return; }
            var html = "已选择 " + files.length + " 个文件";
            list.innerHTML = html;
        }

        function uploadFiles() {
            var files = fileInput.files;
            if (files.length === 0) { alert("请选择文件"); return; }
            var formData = new FormData();
            formData.append("path", currentPath);
            for (var i = 0; i < files.length; i++) { formData.append("file", files[i]); }

            var btn = document.getElementById("uploadBtn");
            btn.disabled = true;
            btn.textContent = "上传中...";

            fetch("/api/upload", { method: "POST", body: formData })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    btn.disabled = false;
                    btn.textContent = "上传";
                    if (data.success) { closeUploadModal(); loadFiles(); } else { alert(data.error || "上传失败"); }
                })
                .catch(function(err) {
                    btn.disabled = false;
                    btn.textContent = "上传";
                    alert("上传失败: " + err.message);
                });
        }

        document.getElementById("folderName").addEventListener("keypress", function(e) {
            if (e.key === "Enter") createFolder();
        });

        document.addEventListener("keydown", function(e) {
            if (e.key === "Escape") {
                closePreview();
                closeMkdirModal();
                closeUploadModal();
            }
            if (e.key === "Backspace" && !document.querySelector(".modal.show") && currentPath !== "/") {
                e.preventDefault();
                goBack();
            }
        });

        if (!allowWrite) {
            document.getElementById("toolbar").style.display = "none";
        }

        loadFiles();
    </script>
</body>
</html>'''


def get_single_file_page(filename: str, size: str) -> str:
    """获取单文件下载页面HTML"""
    escaped_filename = html.escape(filename)
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件下载 - ''' + escaped_filename + '''</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 32px; max-width: 400px; width: 100%; text-align: center; }
        .icon { width: 64px; height: 64px; background: #1e40af; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
        .icon svg { width: 32px; height: 32px; fill: white; }
        h1 { font-size: 16px; color: #fafafa; margin-bottom: 6px; word-break: break-all; font-weight: 600; }
        .size { color: #71717a; font-size: 13px; margin-bottom: 24px; }
        .download-btn { display: inline-flex; align-items: center; gap: 8px; background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 500; }
        .download-btn:hover { background: #2563eb; }
        .footer { margin-top: 24px; color: #52525b; font-size: 11px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon"><svg viewBox="0 0 24 24"><path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/></svg></div>
        <h1>''' + escaped_filename + '''</h1>
        <p class="size">文件大小: ''' + size + '''</p>
        <a href="/download" class="download-btn">📥 下载文件</a>
        <p class="footer">AutoFlow 文件共享</p>
    </div>
</body>
</html>'''
