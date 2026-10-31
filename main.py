# -*- coding: utf-8 -*-
"""
格式转换工厂 (Format Conversion Factory) v2.5
================================================
轻量级桌面文件格式转换工具

功能：
  1. 图片：jpg / png / bmp / webp / gif / tiff 相互转换，支持自定义尺寸、压缩
  2. 文档：docx <-> txt <-> pdf 相互转换，支持可选压缩
  3. 音频：mp3 / wav / ogg / flac / m4a / aac / wma / opus 互转（依赖 ffmpeg）
     输入额外支持 ape（仅解码），以及音乐软件专属加密格式自动解密：
        ncm(网易云) / qmc0/qmc2/qmc3/qmcflac/qmcogg(QQ音乐 QMCv1) /
        kgm/kgma(酷狗) / kgg(酷狗 KGMv2) / kwm(酷我)
     反向转换：普通音频/解密后的音频可封装为音乐软件专属格式：
        kgm/kgma/kgg(酷狗) / ncm(网易云) / qmc0/qmc2/qmc3/qmcflac/qmcogg(QQ音乐) /
        kwm(酷我)
     限制：mflac/mgg(QMCv2 新版) 暂不支持解密、也无法作为输出目标；
           APE 无法作为输出格式；kgg 完整 KGMv2 解密需 kgm.v2.mask 掩码表；
           反向生成的专属格式文件结构完整、本工具可逆解密，但因缺少平台
           真实密钥，官方播放器可能无法识别（仅支持技术学习/个人备份）
  4. 主界面左侧大上传框（点击上传 / 拖拽上传），右侧转换设置区
  5. 输出目录默认系统下载文件夹，更改后自动持久化到配置文件
  6. 界面丝滑动画：按钮悬停渐变、上传框悬停描边高亮、完成提示过渡、
     设置区显隐过渡
  7. 滚动条等控件使用统一主题配色（圆角滑块、与界面主色一致）
  8. 输出文件已存在时自动追加序号（a_1.ext），后缀始终等于目标格式

依赖：Pillow / python-docx / pypdf / reportlab / pydub
外部依赖：ffmpeg（自动使用 imageio-ffmpeg 内置二进制，也可用系统 PATH 中的 ffmpeg）
可选依赖：tkinterdnd2（启用拖拽上传）、pycryptodome（ncm 解密）
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import queue
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import scrolledtext
from pathlib import Path

# 确保同目录模块可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from audio_decrypt import (CRYPTO_FORMATS, CRYPTO_TARGETS,
                               decrypt_crypto_audio, encrypt_crypto_audio,
                               DecryptError, QmcV2Unsupported)
except Exception:  # pragma: no cover
    CRYPTO_FORMATS = set()
    CRYPTO_TARGETS = []
    decrypt_crypto_audio = None
    encrypt_crypto_audio = None
    DecryptError = Exception
    QmcV2Unsupported = Exception

# 中间产物目录（解密后的临时明文音频等；使用系统临时目录，避免硬编码路径导致最简环境不可用）
TEMP_DIR = os.path.join(tempfile.gettempdir(), "FormatConverterFactory_tmp")

# ---------------------------------------------------------------------------
# 可选拖拽支持（tkinterdnd2 未安装时自动降级为点击上传）
# ---------------------------------------------------------------------------
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_OK = True
except Exception:
    _DND_OK = False

# ---------------------------------------------------------------------------
# 第三方库导入（全部可选降级：缺失时对应功能给出提示，不阻止程序启动）
# ---------------------------------------------------------------------------
try:
    from PIL import Image
except Exception:                       # pragma: no cover
    Image = None

try:
    from docx import Document
except Exception:                       # pragma: no cover
    Document = None

try:
    import pypdf
except Exception:                       # pragma: no cover
    pypdf = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    _REPORTLAB_OK = True
except Exception:                       # pragma: no cover
    A4 = None
    pdfmetrics = None
    TTFont = None
    canvas = None
    _REPORTLAB_OK = False

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

# 音频转换基于 ffmpeg（subprocess 直调），不依赖 pydub；
# _AUDIO_OK 仅表示 pydub 可用（用于注入 ffmpeg 路径），缺失时优雅降级
_AUDIO_OK = AudioSegment is not None

# ffmpeg：优先系统 PATH，其次 imageio-ffmpeg 内置二进制
try:
    import imageio_ffmpeg
    _IIO_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _IIO_FFMPEG = None

APP_VERSION = "2.5.0"
APP_TITLE = "格式转换工厂"

# ---------------------------------------------------------------------------
# 格式定义
# ---------------------------------------------------------------------------
IMAGE_TARGETS = ["jpg", "png", "bmp", "webp", "gif", "tiff"]
DOC_TARGETS = ["docx", "txt", "pdf"]
AUDIO_TARGETS = ["mp3", "wav", "ogg", "flac", "m4a", "aac", "wma", "opus"]
# 可作为输入、但不能作为输出目标的音频格式（APE 无编码器）
AUDIO_INPUT_ONLY = ["ape"]
# 音频输出目标全集：普通格式 + 音乐软件专属格式（反向封装）
AUDIO_TARGETS_ALL = AUDIO_TARGETS + list(CRYPTO_TARGETS)
ALL_AUDIO_INPUT = AUDIO_TARGETS + AUDIO_INPUT_ONLY + sorted(CRYPTO_FORMATS)

IMAGE_ALIAS = {"jpg": "jpeg", "jpeg": "jpg"}

AUDIO_CODECS = {
    "mp3":  {"format": "mp3",  "codec": "libmp3lame"},
    "wav":  {"format": "wav",  "codec": "pcm_s16le"},
    "ogg":  {"format": "ogg",  "codec": "libvorbis"},
    "flac": {"format": "flac", "codec": "flac"},
    "m4a":  {"format": "ipod", "codec": "aac"},
    "aac":  {"format": "adts", "codec": "aac"},
    "wma":  {"format": "asf",  "codec": "wmav2"},
    "opus": {"format": "opus", "codec": "libopus"},
}

FORMAT_LABEL = {
    "jpg": "JPEG 图片", "jpeg": "JPEG 图片", "png": "PNG 图片",
    "bmp": "BMP 位图", "webp": "WebP 图片", "gif": "GIF 图片",
    "tiff": "TIFF 图片", "docx": "Word 文档", "txt": "纯文本",
    "pdf": "PDF 文档", "mp3": "MP3 音频", "wav": "WAV 音频",
    "ogg": "OGG 音频", "flac": "FLAC 音频", "m4a": "M4A 音频",
    "aac": "AAC 音频", "wma": "WMA 音频", "opus": "OPUS 音频",
    "ape": "APE 音频", "ncm": "NCM(网易云)", "qmc0": "QMC0(QQ音乐)",
    "qmc2": "QMC2(QQ音乐)", "qmc3": "QMC3(QQ音乐)",
    "qmcflac": "QMCFLAC(QQ音乐)", "qmcogg": "QMCOGG(QQ音乐)",
    "mflac": "MFLAC(QQ音乐)", "mgg": "MGG(QQ音乐)",
    "kgm": "KGM(酷狗)", "kgma": "KGMA(酷狗)", "kgg": "KGG(酷狗KGMv2)", "kwm": "KWM(酷我)",
}

# 上传对话框文件过滤器
PICK_FILETYPES = [
    ("支持的文件", "*.jpg;*.jpeg;*.png;*.bmp;*.webp;*.gif;*.tiff;*.docx;*.txt;*.pdf;"
                  "*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac;*.wma;*.ape;*.opus;"
                  "*.ncm;*.qmc0;*.qmc2;*.qmc3;*.qmcflac;*.qmcogg;*.mflac;*.mgg;*.kgm;*.kgma;*.kgg;*.kwm"),
    ("图片", "*.jpg;*.jpeg;*.png;*.bmp;*.webp;*.gif;*.tiff"),
    ("文档", "*.docx;*.txt;*.pdf"),
    ("音频(含专属加密)", "*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac;*.wma;*.ape;*.opus;"
                      "*.ncm;*.qmc0;*.qmc2;*.qmc3;*.qmcflac;*.qmcogg;*.mflac;*.mgg;*.kgm;*.kgma;*.kgg;*.kwm"),
    ("所有文件", "*.*"),
]


def detect_type(ext):
    """根据扩展名判断文件大类：image / doc / audio / unknown"""
    ext = (ext or "").lstrip(".").lower()
    if ext in IMAGE_TARGETS or ext in ("jpeg", "ico"):
        return "image"
    if ext in DOC_TARGETS:
        return "doc"
    if ext in ALL_AUDIO_INPUT:
        return "audio"
    return "unknown"


# ---------------------------------------------------------------------------
# 配置持久化
# ---------------------------------------------------------------------------
def _config_dir():
    base = os.environ.get("APPDATA") or str(Path.home())
    d = os.path.join(base, "FormatConverterFactory")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def config_path():
    return os.path.join(_config_dir(), "config.json")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def default_output_dir():
    """默认输出目录：%USERPROFILE%\\Downloads"""
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(d):
        return d
    return str(Path.home())


# ---------------------------------------------------------------------------
# 颜色工具（动画）
# ---------------------------------------------------------------------------
def _hex_to_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def _lerp_color(a, b, t):
    ra, ga, ba = _hex_to_rgb(a)
    rb, gb, bb = _hex_to_rgb(b)
    return _rgb_to_hex((ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t))


# ---------------------------------------------------------------------------
# 字体注册（docx/txt -> pdf 中文排版）
# ---------------------------------------------------------------------------
_CJK_FONT = None


def get_cjk_font():
    """注册并返回可用的 CJK 字体名；找不到则回退 Helvetica"""
    global _CJK_FONT
    if _CJK_FONT:
        return _CJK_FONT
    candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", 0),       # 微软雅黑
        (r"C:\Windows\Fonts\msyhbd.ttc", 0),
        (r"C:\Windows\Fonts\simsun.ttc", 0),     # 宋体
        (r"C:\Windows\Fonts\simhei.ttf", -1),    # 黑体
        (r"C:\Windows\Fonts\Deng.ttf", -1),      # 等线
        ("/System/Library/Fonts/PingFang.ttc", 0),   # macOS 苹方
        ("/System/Library/Fonts/STHeiti Light.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),  # Linux 文泉驿
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ]
    for path, idx in candidates:
        if os.path.exists(path):
            try:
                if idx >= 0:
                    pdfmetrics.registerFont(TTFont("CJKFont", path, subfontIndex=idx))
                else:
                    pdfmetrics.registerFont(TTFont("CJKFont", path))
                _CJK_FONT = "CJKFont"
                return _CJK_FONT
            except Exception:
                continue
    _CJK_FONT = "Helvetica"
    return _CJK_FONT


def _wrap_text(text, font_name, font_size, max_width):
    """按 reportlab 字符宽度折行（支持中文逐字折行）"""
    lines = []
    for raw in text.split("\n"):
        if not raw.strip():
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if pdfmetrics.stringWidth(cur + ch, font_name, font_size) > max_width:
                if cur:
                    lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# 文本编码自动识别
# ---------------------------------------------------------------------------
def read_text_auto(src):
    raw = Path(src).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def write_text_utf8(dst, text):
    Path(dst).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 图片转换
# ---------------------------------------------------------------------------
def convert_image(src, dst, fmt, size=None, compress=False, quality=90):
    """fmt: 目标扩展名；size: (w,h) 或 None；compress: 是否压缩"""
    if Image is None:
        raise RuntimeError("缺少 Pillow 依赖，无法进行图片转换。请执行：pip install Pillow")
    im = Image.open(src)
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    if size:
        iw, ih = im.size
        w, h = size
        if w is None and h is None:
            pass
        elif w is None:
            w = max(1, int(iw * h / ih))
        elif h is None:
            h = max(1, int(ih * w / iw))
        else:
            ratio = min(w / iw, h / ih)
            w = max(1, int(iw * ratio))
            h = max(1, int(ih * ratio))
        im = im.resize((w, h), Image.LANCZOS)
    fmt = fmt.lower()
    if fmt in ("jpg", "jpeg"):
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")
        im.save(dst, "JPEG", quality=quality, optimize=compress, progressive=True)
    elif fmt == "png":
        im.save(dst, "PNG", optimize=compress)
    elif fmt == "bmp":
        im.save(dst, "BMP")
    elif fmt == "webp":
        im.save(dst, "WEBP", quality=quality, lossless=not compress, method=6)
    elif fmt == "gif":
        if im.mode != "P":
            im = im.convert("P", palette=Image.ADAPTIVE)
        im.save(dst, "GIF", optimize=compress)
    elif fmt == "tiff":
        try:
            im.save(dst, "TIFF", compression="tiff_lzw" if compress else None)
        except Exception:
            im.save(dst, "TIFF")
    else:
        raise ValueError("不支持的图片目标格式: %s" % fmt)
    return dst


# ---------------------------------------------------------------------------
# 文档转换
# ---------------------------------------------------------------------------
def docx_to_txt(src, dst):
    doc = Document(src)
    lines = []
    for para in doc.paragraphs:
        lines.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            lines.append("\t".join(cell.text for cell in row.cells))
    write_text_utf8(dst, "\n".join(lines))
    return dst


def txt_to_docx(src, dst):
    text = read_text_auto(src)
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(dst)
    return dst


def pdf_to_txt(src, dst):
    reader = pypdf.PdfReader(src)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    write_text_utf8(dst, "\n".join(parts))
    return dst


def pdf_to_docx(src, dst):
    reader = pypdf.PdfReader(src)
    doc = Document()
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            if line.strip():
                doc.add_paragraph(line)
    doc.save(dst)
    return dst


def _text_to_pdf_lines(text):
    font = get_cjk_font()
    return font, 12, _wrap_text(text, font, 12, A4[0] - 144)


def txt_to_pdf(src, dst):
    text = read_text_auto(src)
    font, font_size, lines = _text_to_pdf_lines(text)
    c = canvas.Canvas(dst, pagesize=A4)
    y = A4[1] - 72
    c.setFont(font, font_size)
    for line in lines:
        if y < 72:
            c.showPage()
            y = A4[1] - 72
            c.setFont(font, font_size)
        c.drawString(72, y, line)
        y -= 16
    c.save()
    return dst


def docx_to_pdf(src, dst):
    doc = Document(src)
    font = get_cjk_font()
    font_size = 12
    max_width = A4[0] - 144
    c = canvas.Canvas(dst, pagesize=A4)
    y = A4[1] - 72
    c.setFont(font, font_size)

    def emit_line(text):
        nonlocal y
        if y < 72:
            c.showPage()
            y = A4[1] - 72
            c.setFont(font, font_size)
        c.drawString(72, y, text)
        y -= 16

    def emit_paragraph(text):
        nonlocal y
        for line in _wrap_text(text, font, font_size, max_width):
            emit_line(line)
        y -= 4

    for para in doc.paragraphs:
        emit_paragraph(para.text or "")
    for table in doc.tables:
        for row in table.rows:
            emit_paragraph(" | ".join(cell.text for cell in row.cells))
    c.save()
    return dst


def compress_docx(path):
    tmp = path + ".tmp"
    try:
        with zipfile.ZipFile(path, "r") as zin:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
                for item in zin.infolist():
                    zout.writestr(item, zin.read(item.filename))
        _safe_replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def compress_pdf(path):
    reader = pypdf.PdfReader(path)
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    try:
        writer.compress_content_streams()
    except Exception:
        pass
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        writer.write(f)
    writer.close()
    try:
        _safe_replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def _safe_replace(src, dst):
    try:
        os.replace(src, dst)
    except OSError:
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)


def _unique_dst_path(out_dir, stem, target):
    """输出路径唯一化：目标文件已存在时自动追加序号（a_1.ext / a_2.ext ...）。
    序号只插入 stem 与扩展名之间，最终后缀始终严格等于目标格式 target。"""
    cand = os.path.join(out_dir, "%s.%s" % (stem, target))
    if not os.path.exists(cand):
        return cand
    i = 1
    while True:
        cand = os.path.join(out_dir, "%s_%d.%s" % (stem, i, target))
        if not os.path.exists(cand):
            return cand
        i += 1


def convert_doc(src, dst, fmt, compress=False):
    src_ext = Path(src).suffix.lower().lstrip(".")
    fmt = fmt.lower()
    if src_ext == "docx" and Document is None:
        raise RuntimeError("缺少 python-docx 依赖，无法处理 Word 文档。请执行：pip install python-docx")
    if src_ext == "pdf" and pypdf is None:
        raise RuntimeError("缺少 pypdf 依赖，无法处理 PDF 文档。请执行：pip install pypdf")
    if fmt == "pdf" and not _REPORTLAB_OK:
        raise RuntimeError("缺少 reportlab 依赖，无法生成 PDF。请执行：pip install reportlab")
    if src_ext == "docx" and fmt == "txt":
        docx_to_txt(src, dst)
    elif src_ext == "docx" and fmt == "pdf":
        docx_to_pdf(src, dst)
    elif src_ext == "txt" and fmt == "docx":
        txt_to_docx(src, dst)
    elif src_ext == "txt" and fmt == "pdf":
        txt_to_pdf(src, dst)
    elif src_ext == "pdf" and fmt == "txt":
        pdf_to_txt(src, dst)
    elif src_ext == "pdf" and fmt == "docx":
        pdf_to_docx(src, dst)
    else:
        raise ValueError("不支持的文档转换: %s -> %s" % (src_ext, fmt))
    if compress:
        if fmt == "docx":
            compress_docx(dst)
        elif fmt == "pdf":
            try:
                compress_pdf(dst)
            except Exception:
                pass
    return dst


# ---------------------------------------------------------------------------
# ffmpeg 发现
# ---------------------------------------------------------------------------
def _candidate_ffmpeg_paths():
    """返回候选 ffmpeg 可执行文件路径列表（不判存在性，供统一探测）"""
    cands = []
    p = shutil.which("ffmpeg")
    if p:
        cands.append(p)
    # 环境变量：FFMPEG_BIN / FFMPEG_PATH / FFMPEG 可指向可执行文件或所在目录
    for env in ("FFMPEG_BIN", "FFMPEG_PATH", "FFMPEG"):
        v = os.environ.get(env)
        if not v:
            continue
        cands.append(v)
        # 若指向目录，补充目录下的 ffmpeg.exe / ffmpeg
        for name in ("ffmpeg.exe", "ffmpeg"):
            if os.path.isdir(v):
                cands.append(os.path.join(v, name))
    # 常见安装路径（Windows）
    for base in (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin",
                 r"C:\Program Files (x86)\ffmpeg\bin",
                 r"D:\ffmpeg\bin", r"E:\ffmpeg\bin",
                 r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"):
        cands.append(os.path.join(base, "ffmpeg.exe") if os.path.isdir(base) else base)
    # imageio-ffmpeg 内置二进制（随 pip 包分发，离线可用）
    if _IIO_FFMPEG:
        cands.append(_IIO_FFMPEG)
    return cands


def find_ffmpeg():
    """探测可用的 ffmpeg 可执行文件路径。

    探测顺序：系统 PATH -> 环境变量 FFMPEG_BIN/FFMPEG_PATH/FFMPEG
    （可指向可执行文件或所在目录）-> 常见安装路径 -> imageio-ffmpeg 内置二进制。
    返回 None 表示未找到。
    """
    seen = set()
    for cand in _candidate_ffmpeg_paths():
        if not cand:
            continue
        try:
            key = os.path.normcase(os.path.abspath(cand))
        except Exception:
            key = cand
        if key in seen:
            continue
        seen.add(key)
        if os.path.isfile(cand):
            return cand
    return None


def ffmpeg_hint():
    """检测失败时给用户的操作指引（清晰、可执行）"""
    env_block = "\n".join(
        "   set %s=%%cd%%\\ffmpeg\\bin   （示例：放在程序目录下 ffmpeg\\bin 时）" % e
        for e in ("FFMPEG_BIN", "FFMPEG_PATH")
    )
    return (
        "未检测到 ffmpeg，无法进行音频转换。\n\n"
        "可任选以下一种方式解决：\n"
        "1. 安装 ffmpeg 并加入系统 PATH：\n"
        "   从 https://www.gyan.dev/ffmpeg/builds/ 下载 ffmpeg-release-full.7z，\n"
        "   解压后把其中 bin 目录加入系统环境变量 PATH，重启本程序；\n"
        "2. 设置环境变量指向 ffmpeg 可执行文件（或所在目录）：\n"
        + env_block + "\n"
        "3. 将 ffmpeg.exe 放到以下任意目录：\n"
        "   C:\\ffmpeg\\bin\\、C:\\Program Files\\ffmpeg\\bin\\ 等\n"
        "4. 安装自带 ffmpeg 的 Python 包（推荐）：\n"
        "   pip install imageio-ffmpeg\n"
        "   该包内置 ffmpeg.exe，本程序会自动使用，无需额外安装。"
    )


def _set_pydub_ffmpeg():
    """将发现的 ffmpeg 路径注入 pydub（不覆盖用户显式设置）"""
    if AudioSegment is None or not _AUDIO_OK:
        return
    if AudioSegment.converter not in (None, "", "ffmpeg") and AudioSegment.converter != "ffmpeg":
        return
    fp = find_ffmpeg()
    if fp:
        AudioSegment.converter = fp
        probe = os.path.join(os.path.dirname(fp), "ffprobe.exe")
        if os.path.exists(probe):
            AudioSegment.ffprobe = probe


# ---------------------------------------------------------------------------
# 音频转换（直接调用 ffmpeg，无需 ffprobe）
# ---------------------------------------------------------------------------
def convert_audio(src, dst, fmt, compress=False, bitrate=256):
    """音频转换。wav/flac 恒为无损；有损格式开启压缩时使用指定码率。
    编码器码率上限：libvorbis(ogg) 约 192k，libopus 256k。"""
    fmt = fmt.lower()
    cfg = AUDIO_CODECS[fmt]
    ff = find_ffmpeg()
    if not ff:
        raise RuntimeError(ffmpeg_hint())
    br = bitrate if compress else 320  # 无损优先：最高码率
    cap = {"ogg": 192, "opus": 256}.get(fmt)
    if cap:
        br = min(br, cap)
    cmd = [ff, "-y", "-i", src]
    if fmt == "wav":
        cmd += ["-c:a", "pcm_s16le"]
    else:
        cmd += ["-c:a", cfg["codec"], "-b:a", "%dk" % br]
    cmd += ["-f", cfg["format"], dst]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise RuntimeError("转换超时（ffmpeg 执行超过 15 分钟）")
    if r.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError("ffmpeg 转换失败：%s" % (r.stderr or r.stdout)[-400:])
    return dst


def prepare_audio_source(src):
    """若源为专属加密格式，先解密为临时明文音频。
    返回 (可交给 pydub 的路径, 是否需要在用完后清理)。"""
    ext = Path(src).suffix.lower().lstrip(".")
    if ext not in CRYPTO_FORMATS:
        return src, False
    if decrypt_crypto_audio is None:
        raise DecryptError("缺少 audio_decrypt 模块")
    data, real_fmt = decrypt_crypto_audio(src)
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
    except Exception as e:
        raise RuntimeError("无法创建临时目录 %s：%s" % (TEMP_DIR, e))
    tmp = os.path.join(TEMP_DIR, "decrypted_%s.%s" % (Path(src).stem, real_fmt))
    with open(tmp, "wb") as f:
        f.write(data)
    return tmp, True


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------
class FormatConverterApp:
    BG = "#f4f6fb"
    PANEL = "#ffffff"
    ACCENT = "#4e7cf2"
    ACCENT_DARK = "#3a63d8"
    ACCENT_HOVER = "#6f9bff"
    TEXT_DARK = "#1f2d3d"
    TEXT_GRAY = "#7a8699"
    BORDER = "#d6dce8"
    BUTTON_NORMAL = "#ffffff"
    BUTTON_NORMAL_HOVER = "#e8edf7"
    SUCCESS = "#27ae60"

    # 动画参数
    ANIM_STEPS = 10
    ANIM_INTERVAL = 16

    def __init__(self, root):
        self.root = root
        root.title("%s v%s" % (APP_TITLE, APP_VERSION))
        root.geometry("1000x700")
        root.minsize(920, 620)
        root.configure(bg=self.BG)

        self.files = []
        self._msg_q = queue.Queue()
        self._running = False
        self._anims = {}          # 动画任务注册表（key -> state）
        self._mode = None
        self._targets = []
        self._drop_rect = None
        self._img_target_h = 118   # 设置区显隐动画目标高度

        # 输出目录：持久化配置优先，否则默认下载文件夹
        cfg = load_config()
        saved = (cfg.get("output_dir") or "").strip()
        if not (saved and os.path.isdir(saved)):
            saved = default_output_dir()

        _set_pydub_ffmpeg()

        self._setup_style()
        self._build_ui(saved)
        self._update_compress_hint()
        self.root.after(120, self._poll_queue)

    # ------------------------------------------------------------------
    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 10), background=self.BG)
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT_DARK)
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.TEXT_DARK)
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.TEXT_GRAY)
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT_DARK,
                        font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("TEntry", fieldbackground="#ffffff", bordercolor=self.BORDER,
                        lightcolor="#ffffff", darkcolor="#ffffff", padding=4)
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff",
                        bordercolor=self.BORDER, padding=4)
        style.configure("Horizontal.TProgressbar", background=self.ACCENT,
                        troughcolor="#e6eaf3", bordercolor=self.BORDER, thickness=10)
        # ---- 统一滚动条样式：滑块主色、悬停高亮、浅色轨道，与界面主题一致 ----
        for orient in ("Vertical", "Horizontal"):
            style.configure("App.%s.TScrollbar" % orient,
                            background=self.ACCENT, troughcolor="#e6eaf3",
                            bordercolor=self.BORDER, lightcolor=self.ACCENT_HOVER,
                            darkcolor=self.ACCENT_DARK, arrowcolor="#ffffff",
                            relief="flat", borderwidth=0)
            style.map("App.%s.TScrollbar" % orient,
                      background=[("active", self.ACCENT_HOVER),
                                  ("pressed", self.ACCENT_DARK)])
            style.configure("App.%s.TScrollbar" % orient, width=14)

        # ---- 输入框：白底 + 聚焦/悬停主色描边 ----
        style.configure("App.TEntry", fieldbackground="#ffffff",
                        bordercolor=self.BORDER, lightcolor="#ffffff",
                        darkcolor="#ffffff", padding=4)
        style.map("App.TEntry",
                  bordercolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)],
                  lightcolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)],
                  darkcolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)])

        # ---- 下拉框：主色箭头 + 白底 + 聚焦/悬停描边 + 下拉列表项统一 ----
        style.configure("App.TCombobox", fieldbackground="#ffffff",
                        background=self.ACCENT, foreground="#ffffff",
                        bordercolor=self.BORDER, arrowcolor="#ffffff",
                        lightcolor=self.ACCENT_HOVER, darkcolor=self.ACCENT_DARK,
                        padding=4)
        style.map("App.TCombobox",
                  bordercolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)],
                  lightcolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)],
                  darkcolor=[("focus", self.ACCENT), ("hover", self.ACCENT_HOVER)],
                  fieldbackground=[("readonly", "#ffffff")],
                  foreground=[("readonly", self.TEXT_DARK)],
                  background=[("readonly", self.ACCENT), ("active", self.ACCENT_HOVER)])
        style.configure("App.TCombobox.Listbox", background="#ffffff",
                        foreground=self.TEXT_DARK, bordercolor=self.BORDER,
                        selectbackground="#e2eaff", selectforeground=self.TEXT_DARK,
                        font=("Microsoft YaHei UI", 10))
        style.map("App.TCombobox.Listbox",
                  selectbackground=[("focus", "#e2eaff"), ("!focus", "#e2eaff")])

        # ---- 滑条：主色渐变滑块 + 浅色轨道 + 悬停高亮 ----
        style.configure("App.Horizontal.TScale", background=self.BG,
                        troughcolor="#e6eaf3", bordercolor=self.BORDER,
                        lightcolor=self.ACCENT_HOVER, darkcolor=self.ACCENT_DARK,
                        sliderlength=24)
        style.map("App.Horizontal.TScale",
                  background=[("active", self.ACCENT_HOVER)],
                  lightcolor=[("active", self.ACCENT)],
                  darkcolor=[("active", self.ACCENT_DARK)])

    # ------------------------------------------------------------------
    # 动画基础设施
    # ------------------------------------------------------------------
    def _cancel_anim(self, key):
        st = self._anims.pop(key, None)
        if st and st.get("job"):
            try:
                self.root.after_cancel(st["job"])
            except Exception:
                pass

    def _run_anim(self, key, step_cb, total=None, interval=None, end_cb=None):
        """通用逐帧动画：step_cb(t) t 从 0->1 平滑调用；end_cb 结束时调用。"""
        total = total if total is not None else self.ANIM_STEPS
        interval = interval if interval is not None else self.ANIM_INTERVAL
        self._cancel_anim(key)
        state = {"i": 0, "job": None}
        self._anims[key] = state

        def tick():
            state["i"] += 1
            t = state["i"] / total
            try:
                step_cb(t)
            except Exception:
                pass
            if state["i"] < total:
                state["job"] = self.root.after(interval, tick)
            else:
                self._anims.pop(key, None)
                if end_cb:
                    try:
                        end_cb()
                    except Exception:
                        pass

        tick()

    # ------------------------------------------------------------------
    # 自定义控件
    # ------------------------------------------------------------------
    def _make_button(self, parent, text, command, accent=False, padx=14, pady=6):
        """tk.Button + 悬停渐变动画"""
        base = self.ACCENT if accent else self.BUTTON_NORMAL
        hover = self.ACCENT_HOVER if accent else self.BUTTON_NORMAL_HOVER
        fg = "#ffffff" if accent else self.TEXT_DARK
        key = id(object())  # 用唯一 key 区分多个按钮动画

        btn = tk.Button(parent, text=text, command=command,
                        bg=base, fg=fg, activebackground=hover,
                        activeforeground=fg, relief="flat", bd=0,
                        highlightthickness=0, cursor="hand2",
                        font=("Microsoft YaHei UI", 10, "bold" if accent else "normal"),
                        padx=padx, pady=pady)

        def enter(_):
            self._cancel_anim("btn_%s_out" % key)
            self._run_anim("btn_%s_in" % key,
                           lambda t: btn.configure(bg=_lerp_color(base, hover, t)))

        def leave(_):
            self._cancel_anim("btn_%s_in" % key)
            self._run_anim("btn_%s_out" % key,
                           lambda t: btn.configure(bg=_lerp_color(hover, base, t)))

        btn.bind("<Enter>", enter)
        btn.bind("<Leave>", leave)
        btn._anim_key = key
        return btn

    def _style_combo_popdown(self):
        """统一目标格式下拉列表内部滚动条为主题样式。

        ttk Combobox 的下拉列表（popdown）惰性创建，内部自带一个默认样式
        滚动条；此处主动实例化 popdown 并为其滚动条应用 App 滚动条样式，
        保证下拉列表滚动条与整体蓝色主题一致。"""
        try:
            combo = self.target_combo
            pd = combo.tk.call("ttk::combobox::PopdownWindow", combo._w)
            sb = pd + ".f.sb"
            if combo.tk.call("winfo", "exists", sb):
                combo.tk.call(sb, "configure", "-style", "App.Vertical.TScrollbar")
        except Exception:
            pass

    def _make_checkbox(self, parent, text, var, command=None):
        """自定义复选框：勾选显示 ✓（蓝色），未勾选显示 □。
        使用 indicatoron=0 + 文本前缀，避免系统主题画叉号。"""
        cb = tk.Checkbutton(parent, variable=var, indicatoron=False,
                            bg=self.PANEL, fg=self.TEXT_DARK,
                            activebackground=self.PANEL, activeforeground=self.TEXT_DARK,
                            selectcolor=self.PANEL, relief="flat", bd=0,
                            highlightthickness=0, anchor="w", justify="left",
                            font=("Microsoft YaHei UI", 10), padx=2, pady=2,
                            command=command)

        def update(*_):
            if var.get():
                cb.configure(text="\u2713 " + text, fg=self.ACCENT)
            else:
                cb.configure(text="\u25a1 " + text, fg=self.TEXT_DARK)

        var.trace_add("write", update)
        update()
        return cb

    # ------------------------------------------------------------------
    def _build_ui(self, default_out_dir):
        root = self.root
        # 顶部标题
        header = tk.Frame(root, bg=self.BG)
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text=APP_TITLE, bg=self.BG, fg=self.TEXT_DARK,
                 font=("Microsoft YaHei UI", 17, "bold")).pack(side="left")
        tk.Label(header, text="图片 / 文档 / 音频 无损互转 · 支持音乐加密格式解密",
                 bg=self.BG, fg=self.TEXT_GRAY,
                 font=("Microsoft YaHei UI", 10)).pack(side="left", padx=12, pady=(6, 0))

        body = tk.Frame(root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=24, pady=(4, 10))

        # ---------------- 左侧：上传区 ----------------
        self.left_panel = tk.Frame(body, bg=self.PANEL, highlightbackground=self.BORDER,
                                   highlightthickness=1)
        self.left_panel.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(self.left_panel, text="上传文件", bg=self.PANEL, fg=self.TEXT_DARK,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        # 上传大方框（Canvas）
        self.upload_canvas = tk.Canvas(self.left_panel, width=440, height=210, bg="#fafbfe",
                                       highlightthickness=0)
        self.upload_canvas.pack(fill="x", padx=16, pady=4)
        self._draw_upload_box()
        self.upload_canvas.bind("<Button-1>", lambda e: self._pick_files())
        # 悬停描边高亮动画
        self.upload_canvas.bind("<Enter>", lambda e: self._anim_upload_box(True))
        self.upload_canvas.bind("<Leave>", lambda e: self._anim_upload_box(False))

        # 文件列表
        list_row = tk.Frame(self.left_panel, bg=self.PANEL)
        list_row.pack(fill="both", expand=True, padx=16, pady=(10, 4))
        self.file_list = tk.Listbox(list_row, bg="#ffffff", fg=self.TEXT_DARK,
                                    selectbackground="#e2eaff", selectforeground=self.TEXT_DARK,
                                    selectborderwidth=0, activestyle="none",
                                    relief="flat", highlightthickness=1,
                                    highlightbackground=self.BORDER,
                                    highlightcolor=self.ACCENT,
                                    font=("Microsoft YaHei UI", 10))
        self.file_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_row, orient="vertical", command=self.file_list.yview,
                           style="App.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self.file_list.configure(yscrollcommand=sb.set)

        btns = tk.Frame(self.left_panel, bg=self.PANEL)
        btns.pack(fill="x", padx=16, pady=(4, 14))
        self._make_button(btns, "添加文件", self._pick_files).pack(side="left")
        self._make_button(btns, "移除选中", self._remove_selected).pack(side="left", padx=8)
        self._make_button(btns, "清空列表", self._clear_files).pack(side="left")

        # 拖拽：注册到整个左侧面板 + 上传框（扩大命中区域）
        if _DND_OK:
            try:
                for w in (self.upload_canvas, self.left_panel):
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # ---------------- 右侧：转换设置 ----------------
        right = tk.Frame(body, bg=self.PANEL, highlightbackground=self.BORDER,
                         highlightthickness=1, width=400)
        right.pack(side="right", fill="y", padx=(0, 0))
        right.pack_propagate(False)
        tk.Label(right, text="转换设置", bg=self.PANEL, fg=self.TEXT_DARK,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 10))

        # 目标格式
        ttk.Label(right, text="目标格式", style="Panel.TLabel").pack(anchor="w", padx=16)
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(right, textvariable=self.target_var,
                                         state="readonly", width=30,
                                         style="App.TCombobox")
        self.target_combo.pack(fill="x", padx=16, pady=(4, 8))
        self.target_combo.bind("<<ComboboxSelected>>", lambda e: self._update_hints())
        # 下拉列表内部滚动条统一为主题样式（popdown 惰性创建，此处主动实例化一次）
        self._style_combo_popdown()

        # 图片尺寸设置（动态显隐 + 高度过渡动画）
        self.img_frame = tk.Frame(right, bg=self.PANEL, height=0)
        self.img_frame.pack_propagate(False)
        ttk.Label(self.img_frame, text="转换后尺寸（留空为原尺寸）",
                  style="Panel.TLabel").pack(anchor="w", padx=16, pady=(2, 4))
        size_row = tk.Frame(self.img_frame, bg=self.PANEL)
        size_row.pack(fill="x", padx=16)
        ttk.Label(size_row, text="宽度", style="Panel.TLabel").pack(side="left")
        self.width_var = tk.StringVar()
        ttk.Entry(size_row, textvariable=self.width_var, width=9,
                  style="App.TEntry").pack(side="left", padx=(4, 10))
        ttk.Label(size_row, text="高度", style="Panel.TLabel").pack(side="left")
        self.height_var = tk.StringVar()
        ttk.Entry(size_row, textvariable=self.height_var, width=9,
                  style="App.TEntry").pack(side="left", padx=(4, 0))
        self.ratio_var = tk.BooleanVar(value=True)
        self._make_checkbox(self.img_frame, "保持纵横比", self.ratio_var).pack(anchor="w", padx=16, pady=(4, 4))

        # 压缩设置
        ttk.Label(right, text="压缩选项", style="Panel.TLabel").pack(anchor="w", padx=16, pady=(10, 2))
        self.compress_var = tk.BooleanVar(value=False)
        self._make_checkbox(right, "启用压缩（默认关闭 = 无损优先）", self.compress_var,
                            command=self._update_compress_hint).pack(anchor="w", padx=16, pady=2)
        self.quality_row = tk.Frame(right, bg=self.PANEL)
        self.quality_label = ttk.Label(self.quality_row, text="质量", style="Panel.TLabel")
        self.quality_label.pack(side="left", padx=16)
        self.quality_var = tk.IntVar(value=90)
        self.quality_scale = ttk.Scale(self.quality_row, from_=5, to=100,
                                       variable=self.quality_var, length=170,
                                       style="App.Horizontal.TScale")
        self.quality_scale.pack(side="left", padx=8)
        self.quality_value = ttk.Label(self.quality_row, text="90%", style="Panel.TLabel")
        self.quality_value.pack(side="left")
        self.quality_row.pack(fill="x", pady=(4, 2))
        self.quality_var.trace_add("write", lambda *a: self.quality_value.configure(
            text=self._quality_text()))
        self.compress_hint = ttk.Label(right, text="", style="Muted.TLabel",
                                       wraplength=350, justify="left")
        self.compress_hint.pack(anchor="w", padx=16, pady=(0, 4))

        # 输出目录
        ttk.Label(right, text="输出目录", style="Panel.TLabel").pack(anchor="w", padx=16, pady=(10, 2))
        out_row = tk.Frame(right, bg=self.PANEL)
        out_row.pack(fill="x", padx=16)
        self.out_var = tk.StringVar(value=default_out_dir)
        ttk.Entry(out_row, textvariable=self.out_var,
                  style="App.TEntry").pack(side="left", fill="x", expand=True)
        self._make_button(out_row, "浏览", self._pick_out_dir, padx=10, pady=3).pack(side="left", padx=(6, 0))
        # 持久化：输出目录变化即写配置
        self.out_var.trace_add("write", lambda *a: self._persist_out_dir())

        # 开始按钮
        self.start_btn = self._make_button(right, "开始转换", self._start_convert,
                                           accent=True, padx=20, pady=8)
        self.start_btn.pack(fill="x", padx=16, pady=(16, 6))

        self.mode_hint = ttk.Label(right, text="请先添加文件", style="Muted.TLabel",
                                   wraplength=350, justify="left")
        self.mode_hint.pack(anchor="w", padx=16, pady=(0, 12))

        # ---------------- 底部进度与日志 ----------------
        bottom = tk.Frame(root, bg=self.BG)
        bottom.pack(fill="x", padx=24, pady=(0, 12))
        self.progress = ttk.Progressbar(bottom, mode="determinate",
                                        style="Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = tk.Label(bottom, textvariable=self.status_var, bg=self.BG,
                                     fg=self.TEXT_GRAY, font=("Microsoft YaHei UI", 10))
        self.status_label.pack(anchor="w", pady=(6, 0))
        self.log = scrolledtext.ScrolledText(bottom, height=9, bg="#ffffff",
                                             fg=self.TEXT_DARK, relief="flat",
                                             highlightthickness=1,
                                             highlightbackground=self.BORDER,
                                             font=("Consolas", 9))
        # 日志区内部滚动条：与界面主题统一（滑块主色、浅色轨道）
        try:
            self.log.vbar.configure(bg=self.BG, activebackground=self.ACCENT,
                                    troughcolor="#e6eaf3", relief="flat", bd=0,
                                    highlightthickness=0, width=12)
        except Exception:
            pass
        self.log.pack(fill="x", pady=(6, 0))
        self.log.configure(state="disabled")

        self._update_compress_hint()

    # ------------------------------------------------------------------
    def _quality_text(self):
        if self._mode == "image":
            return "%d%%" % self.quality_var.get()
        if self._mode == "audio":
            return "%dkbps" % self.quality_var.get()
        return str(self.quality_var.get())

    def _draw_upload_box(self):
        c = self.upload_canvas
        c.delete("all")
        w = int(c.cget("width")); h = int(c.cget("height"))
        self._drop_rect = c.create_rectangle(8, 8, w - 8, h - 8, outline=self.ACCENT,
                                             width=2, dash=(6, 4), fill="#fafbfe")
        c.create_text(w / 2, h / 2 - 34, text="点击上传 或 拖拽文件到此处",
                      fill=self.ACCENT, font=("Microsoft YaHei UI", 14, "bold"))
        c.create_text(w / 2, h / 2 + 2,
                      text="支持图片 / 文档 / 音频文件，可一次选择多个",
                      fill=self.TEXT_GRAY, font=("Microsoft YaHei UI", 10))
        # 使用 width 参数自动换行，保证多行文字不溢出框外
        c.create_text(w / 2, h / 2 + 34, width=w - 56, justify="center",
                      text="图片(jpg/png/bmp/webp/gif/tiff)  文档(docx/txt/pdf)\n"
                           "音频(mp3/wav/ogg/flac/m4a/aac/wma/ape/opus)\n"
                           "加密格式可自动解密(ncm/qmc/kgm/kgg/kwm等)",
                      fill=self.TEXT_GRAY, font=("Microsoft YaHei UI", 8))

    def _anim_upload_box(self, hover):
        if self._drop_rect is None:
            return
        c = self.upload_canvas
        target = self.ACCENT_HOVER if hover else self.ACCENT
        start = self.ACCENT if hover else self.ACCENT_HOVER

        def step(t):
            try:
                c.itemconfig(self._drop_rect, outline=_lerp_color(start, target, t),
                             width=2 + t if hover else 3 - t)
            except Exception:
                pass
        self._run_anim("upload_box" if hover else "upload_box_out", step)

    # ------------------------------------------------------------------
    def _pick_files(self):
        paths = filedialog.askopenfilenames(title="选择要转换的文件",
                                            filetypes=PICK_FILETYPES)
        if paths:
            self._add_files(list(paths))

    def _add_files(self, paths):
        added = 0
        for p in paths:
            p = str(p).strip()
            if not p:
                continue
            ext = Path(p).suffix.lower().lstrip(".")
            if detect_type(ext) == "unknown":
                self._log("跳过不支持的文件: %s (%s)" % (p, ext or "无扩展名"))
                continue
            if p not in self.files:
                self.files.append(p)
                self.file_list.insert("end", p)
                added += 1
        if added:
            self._sync_targets()
            self._log("已添加 %d 个文件" % added)

    def _remove_selected(self):
        sel = self.file_list.curselection()
        for i in reversed(sel):
            self.files.pop(i)
            self.file_list.delete(i)
        self._sync_targets()

    def _clear_files(self):
        self.files.clear()
        self.file_list.delete(0, "end")
        self._sync_targets()

    def _on_drop(self, event):
        raw = event.data or ""
        tokens = re.findall(r"\{([^}]*)\}|(\S+)", raw)
        files = [a or b for a, b in tokens if (a or b)]
        if files:
            self._add_files(files)

    # ------------------------------------------------------------------
    def _sync_targets(self):
        """根据文件列表自动确定目标格式列表与默认值"""
        if not self.files:
            self._mode = None
            self._targets = []
            self.target_combo.configure(values=[])
            self.target_var.set("")
            self.mode_hint.configure(text="请先添加文件")
            self._toggle_img_frame(False)
            self._update_compress_hint()
            return

        first = Path(self.files[0])
        ext0 = first.suffix.lower().lstrip(".")
        mode0 = detect_type(ext0)

        mixed = False
        for f in self.files:
            if detect_type(Path(f).suffix.lower().lstrip(".")) != mode0:
                mixed = True
                break

        if mode0 == "image":
            self._targets = IMAGE_TARGETS
        elif mode0 == "doc":
            self._targets = DOC_TARGETS
        elif mode0 == "audio":
            self._targets = AUDIO_TARGETS_ALL
        else:
            self._targets = []

        self._mode = mode0
        self.target_combo.configure(values=[x.upper() for x in self._targets])
        default = None
        for x in self._targets:
            if not self._same_format(ext0, x):
                default = x
                break
        self.target_var.set(default.upper() if default else "")
        self._toggle_img_frame(mode0 == "image")
        name = "图片" if mode0 == "image" else ("文档" if mode0 == "doc" else "音频")
        hint = "已添加 %d 个%s文件。目标格式已自动设置，可直接开始转换。" % (len(self.files), name)
        if mode0 == "audio" and ext0 in CRYPTO_FORMATS:
            hint = ("检测到音乐加密格式(%s)，转换前将自动解密，再输出为目标格式。\n" % FORMAT_LABEL.get(ext0, ext0)) + hint
        if mixed:
            hint += "\n注意：当前为混合类型文件，将统一按上述目标格式处理（不匹配的文件会被跳过）。"
        self.mode_hint.configure(text=hint)
        self._update_compress_hint()

    @staticmethod
    def _same_format(a, b):
        a = a.lower(); b = b.lower()
        # 音乐加密格式（kgg/kgm/ncm/qmc 等）必须先解密重编码，
        # 即使目标文本恰好等于输入扩展名也不算"已是目标格式"
        if a in CRYPTO_FORMATS or b in CRYPTO_FORMATS:
            return False
        if a == b:
            return True
        return IMAGE_ALIAS.get(a) == b or IMAGE_ALIAS.get(b) == a

    def _toggle_img_frame(self, show):
        """设置区显隐：高度过渡动画"""
        self._cancel_anim("img_h")
        if show:
            self.img_frame.pack(fill="x", pady=2)
            self._run_anim("img_h",
                           lambda t: self.img_frame.configure(height=int(self._img_target_h * t)))
        else:
            cur = self.img_frame.winfo_height()
            if cur <= 0:
                self.img_frame.pack_forget()
                return

            def end():
                self.img_frame.pack_forget()

            self._run_anim("img_h",
                           lambda t: self.img_frame.configure(height=int(cur * (1 - t))),
                           end_cb=end)

    # ------------------------------------------------------------------
    def _update_compress_hint(self):
        if self._mode == "image":
            self.quality_label.configure(text="质量")
            self.quality_scale.configure(from_=5, to=100)
            self.quality_var.set(90)
            self.quality_value.configure(text="90%")
            if self.compress_var.get():
                self.compress_hint.configure(
                    text="压缩开启：JPEG/WebP 按质量压缩；PNG/BMP 无损优化；TIFF 使用 LZW 压缩。")
            else:
                self.compress_hint.configure(
                    text="无损优先：PNG/BMP 无损保存；WebP 无损编码；JPEG 高质量(95)。")
        elif self._mode == "audio":
            self.quality_label.configure(text="码率")
            self.quality_scale.configure(from_=64, to=320)
            self.quality_var.set(256)
            self.quality_value.configure(text="256kbps")
            if self.compress_var.get():
                self.compress_hint.configure(
                    text="压缩开启：有损格式按所选码率编码（默认256kbps）；WAV/FLAC 始终无损。")
            else:
                self.compress_hint.configure(
                    text="无损优先：WAV(PCM)/FLAC 无损编码；MP3/OGG/M4A/AAC/WMA/OPUS 使用最高码率320kbps。")
        else:
            self.quality_label.configure(text="压缩级别")
            self.quality_scale.configure(from_=1, to=9)
            self.quality_var.set(9)
            self.quality_value.configure(text="9")
            if self.compress_var.get():
                self.compress_hint.configure(
                    text="压缩开启：DOCX 以最大压缩级别重打包；PDF 压缩内容流（文本类压缩收益有限）。")
            else:
                self.compress_hint.configure(
                    text="文档无损优先：不额外压缩。注意 DOCX->PDF 为纯文本重排版，图片/复杂样式不保留。")

    def _update_hints(self):
        self._update_compress_hint()
        t = (self.target_var.get() or "").lower()
        if self._mode == "audio" and t in CRYPTO_TARGETS:
            self.compress_hint.configure(
                text="提示：%s 为音乐软件专属加密格式。生成文件结构完整、本工具可逆解密；"
                     "因缺少平台私钥，官方播放器可能无法识别（仅支持技术学习/个人备份用途）。" % t.upper())

    # ------------------------------------------------------------------
    def _persist_out_dir(self):
        d = self.out_var.get().strip()
        if not d or not os.path.isdir(d):
            return
        try:
            cfg = load_config()
            cfg["output_dir"] = d
            save_config(cfg)
        except Exception:
            pass

    def _pick_out_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.out_var.set(d)   # trace 自动持久化

    # ------------------------------------------------------------------
    def _start_convert(self):
        if self._running:
            return
        if not self.files:
            messagebox.showwarning("提示", "请先上传文件")
            return
        target = (self.target_var.get() or "").lower()
        if not target:
            messagebox.showwarning("提示", "请选择目标格式")
            return

        same_all = all(self._same_format(Path(f).suffix.lower().lstrip("."), target)
                       for f in self.files)
        if same_all:
            messagebox.showwarning("提示", "所选文件已是目标格式，无需转换。")
            return

        if self._mode == "audio" and not find_ffmpeg():
            messagebox.showerror("缺少依赖", ffmpeg_hint())
            return
        if self._mode == "doc" and (Document is None or pypdf is None):
            messagebox.showerror("缺少依赖", "缺少 python-docx 或 pypdf 库。\n"
                                  "请执行: pip install python-docx pypdf reportlab")
            return

        out_dir = self.out_var.get().strip()
        if not out_dir:
            out_dir = str(Path(self.files[0]).parent)
        else:
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("输出目录错误", "无法创建输出目录：%s" % e)
                return

        width = self.width_var.get().strip()
        height = self.height_var.get().strip()
        try:
            w = int(width) if width else None
            h = int(height) if height else None
        except ValueError:
            messagebox.showwarning("提示", "尺寸必须是整数（留空表示保持原尺寸）")
            return

        compress = self.compress_var.get()
        quality = self.quality_var.get()

        self._running = True
        self.start_btn.configure(state="disabled", cursor="arrow")
        self.progress.configure(maximum=len(self.files), value=0)
        self.status_var.set("转换中...")

        threading.Thread(target=self._worker,
                         args=(list(self.files), target, out_dir,
                               (w, h), self.ratio_var.get(), compress, quality),
                         daemon=True).start()

    def _worker(self, files, target, out_dir, size, keep_ratio, compress, quality):
        ok = 0
        for i, f in enumerate(files, 1):
            self._msg_q.put(("progress", i))
            name = Path(f).name
            self._msg_q.put(("log", "[%d/%d] %s" % (i, len(files), name)))
            try:
                out = self._convert_one(f, target, out_dir, size, keep_ratio,
                                        compress, quality)
                if out is None:
                    self._msg_q.put(("log", "    跳过（已是目标格式或类型不匹配）"))
                    continue
                self._msg_q.put(("log", "    -> %s" % out))
                ok += 1
            except QmcV2Unsupported as e:
                self._msg_q.put(("log", "    失败: %s" % e))
            except DecryptError as e:
                self._msg_q.put(("log", "    解密失败: %s" % e))
            except Exception as e:
                self._msg_q.put(("log", "    失败: %s" % e))
        self._msg_q.put(("done", ok, len(files)))

    def _convert_one(self, src, target, out_dir, size, keep_ratio, compress, quality):
        ext = Path(src).suffix.lower().lstrip(".")
        mode = detect_type(ext)
        if self._same_format(ext, target):
            return None
        if mode != self._mode or mode == "unknown":
            return None
        if mode == "doc" and target not in DOC_TARGETS:
            return None
        if mode == "audio" and target not in AUDIO_TARGETS_ALL:
            return None
        if mode == "image" and target not in IMAGE_TARGETS:
            return None

        stem = Path(src).stem
        dst = _unique_dst_path(out_dir, stem, target)
        if os.path.abspath(dst) == os.path.abspath(src):
            return None

        if mode == "image":
            if not (size and (size[0] or size[1])):
                size = None
            convert_image(src, dst, target, size=size, compress=compress,
                          quality=quality)
        elif mode == "doc":
            convert_doc(src, dst, target, compress=compress)
        elif mode == "audio":
            if target in CRYPTO_TARGETS:
                self._convert_to_crypto(src, dst, target, compress=compress,
                                        bitrate=quality)
            else:
                work_src, need_clean = prepare_audio_source(src)
                try:
                    convert_audio(work_src, dst, target, compress=compress,
                                  bitrate=quality)
                finally:
                    if need_clean:
                        try:
                            os.remove(work_src)
                        except Exception:
                            pass
        return dst

    def _convert_to_crypto(self, src, dst, target, compress=False, bitrate=256):
        """明文/加密音频 -> 音乐软件专属格式（反向封装）。

        流程：解密源（若源本身为加密格式）-> 按目标专属格式的容器要求转码为
        中间明文（qmcflac 用 flac、qmcogg 用 ogg，其余用 wav）-> 加密封装写入
        dst。中间明文一律写入临时目录并在用完后立即清理，交付文件后缀恒为
        目标格式 target。"""
        if encrypt_crypto_audio is None:
            raise DecryptError("缺少 audio_decrypt 模块，无法生成 %s" % target)
        mid_fmt = {"qmcflac": "flac", "qmcogg": "ogg"}.get(target, "wav")
        work_src, need_clean = prepare_audio_source(src)
        mid = work_src
        mid_clean = False
        try:
            if Path(mid).suffix.lower().lstrip(".") != mid_fmt:
                mid = os.path.join(TEMP_DIR, "encrypt_mid_%s.%s" % (Path(src).stem, mid_fmt))
                convert_audio(work_src, mid, mid_fmt, compress=compress, bitrate=bitrate)
                mid_clean = True
            data = Path(mid).read_bytes()
            enc = encrypt_crypto_audio(data, target)
            Path(dst).write_bytes(enc)
        finally:
            if mid_clean:
                try:
                    os.remove(mid)
                except Exception:
                    pass
            if need_clean:
                try:
                    os.remove(work_src)
                except Exception:
                    pass
        return dst

    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                item = self._msg_q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "progress":
                    self.progress.configure(value=item[1])
                elif kind == "done":
                    ok, total = item[1], item[2]
                    self._running = False
                    self.start_btn.configure(state="normal", cursor="hand2")
                    self.progress.configure(value=total)
                    self.status_var.set("完成：成功 %d / 共 %d" % (ok, total))
                    # 完成提示过渡：绿色高亮渐隐
                    self._cancel_anim("done_status")
                    self._run_anim("done_status",
                                   lambda t: self.status_label.configure(
                                       fg=_lerp_color(self.SUCCESS, self.TEXT_GRAY, t)))
                    messagebox.showinfo("转换完成",
                                        "成功转换 %d 个文件（共 %d 个）。\n详细结果见下方日志。" % (ok, total))
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", "%s\n" % msg)
        self.log.see("end")
        self.log.configure(state="disabled")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
_set_pydub_ffmpeg()   # 顶层即注入 ffmpeg，保证非 GUI 上下文（测试/命令行）也可用


def main():
    if _DND_OK:
        try:
            root = TkinterDnD.Tk()
        except Exception:
            root = tk.Tk()
    else:
        root = tk.Tk()
    try:
        FormatConverterApp(root)
    except Exception as e:          # 兜底：初始化异常时给出明确提示，避免静默闪退
        import traceback as _tb
        _tb.print_exc()
        try:
            messagebox.showerror(
                "启动失败",
                "程序初始化时发生错误，无法启动：\n\n%s\n\n"
                "请检查是否缺少必需依赖（见 README「安装与运行」/「启动排障」）。\n"
                "提示：程序不依赖可选功能（拖拽、音频）也能正常启动。" % e)
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
        return
    root.mainloop()


if __name__ == "__main__":
    main()
