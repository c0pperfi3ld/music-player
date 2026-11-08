#!/usr/bin/env python3
"""
Audio Player Pro — Studio Grade Desktop Audio & Video Workstation
================================================================
Features:
- Edge-to-Edge Panoramic Visualizer with Beat-Reactive Multi-Wave Synthesis
- Audio Track Waveform Overview Bar directly below the Main Slider
- Battery-Style Vertical Glow Volume Gauge beside the Visualizer
- Multi-Handle Interactive Song Slider with Draggable [A] & [B] Loop Pins
- Fine 0.01x Granular Playback Speed Slider (0.25x - 2.50x) with Quick Presets
- Fully Resizable Panels via Drag Splitters with Persistent Layout State
- Multi-Folder Music Library Manager (Add/Remove Folders, Rescan, Persistent)
- High-Density Compact Songs Table with Rich Metadata (Codec, Bitrate, Format Pills, Size)
- Isolated Per-Song Settings Persistence (Clean Track Switching with Zero Loop Carryover)
- 7-Band Parametric EQ with 0.1 dB Resolution, Analog Bass Boost & Studio Presets
- Glassmorphism Aesthetics with 5 Vivid Neon Themes & Fluid 60 FPS Spring Physics
- Video Playback View via QVideoWidget + Asynchronous YouTube Downloader
"""

import sys
import os
import json
import math
import random
import time
import shutil
import struct
import glob
import hashlib
import subprocess
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QPlainTextEdit, QFileDialog, QProgressBar, QComboBox, QGroupBox, QFrame,
    QSplitter, QSplitterHandle, QTabWidget, QSizePolicy, QToolTip, QMenu, QAbstractItemView,
    QGraphicsDropShadowEffect, QScrollArea, QCheckBox, QGridLayout
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QThread, QProcess, pyqtSignal, QSize, QSettings, QRect,
    QRectF, QPoint, QPointF, QEvent, QEasingCurve, QVariantAnimation
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import (
    QPainter, QLinearGradient, QRadialGradient, QConicalGradient, QColor, QPen, QPainterPath,
    QShortcut, QKeySequence, QBrush, QFont, QIcon, QCursor, QPalette, QPixmap, QPolygonF,
    QFontMetrics
)
import mutagen
import yt_dlp
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Ensure on Windows that NO child process (ffmpeg, ffprobe, yt-dlp) spawns a visible terminal console
if sys.platform == 'win32':
    _orig_popen = subprocess.Popen
    def _silent_popen(*args, **kwargs):
        cf = kwargs.get('creationflags', 0)
        kwargs['creationflags'] = cf | getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
        return _orig_popen(*args, **kwargs)
    subprocess.Popen = _silent_popen

# ─────────────────────────────────────────────────────────────────────────────
# SHARED DATA DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────
# This build may live in a sub-folder (e.g. ./updated/).  The music library,
# per-song A:B loop profiles, metadata cache, waveform cache and app settings
# are resolved back to the project root so this build shares the exact same
# state as the original app instead of starting from an empty library.
def _resolve_data_dir():
    here = Path(__file__).resolve().parent
    for cand in (here, here.parent, here.parent.parent):
        try:
            if any((cand / f).exists() for f in
                   ('song_profiles.json', 'app_settings.json', 'metadata_cache.json')):
                return cand
        except OSError:
            continue
    return here


DATA_DIR = _resolve_data_dir()

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

def _find_ffmpeg_dir():
    exe = shutil.which('ffmpeg')
    if exe:
        return str(Path(exe).parent)
    for base in [
        Path.home() / 'AppData/Local/hermes/tools',
        Path('C:/ffmpeg/bin'),
        Path('C:/Program Files/ffmpeg/bin'),
    ]:
        if base.is_dir():
            if 'hermes' in base.as_posix():
                for d in sorted(base.glob('ffmpeg-*/bin'), reverse=True):
                    if (d / 'ffmpeg.exe').exists():
                        return str(d)
            elif (base / 'ffmpeg.exe').exists():
                return str(base)
    return None

FFMPEG_DIR = _find_ffmpeg_dir()

AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac', '.opus', '.aiff', '.alac'}
VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v', '.mpg', '.mpeg'}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

# 12 Vivid Glassmorphism Themes
THEMES = {
    'midnight': {
        'name': 'Midnight Cyber',
        'bg': '#070a13', 'bg_card': 'rgba(13, 17, 28, 0.88)',
        'text': '#f1f5f9', 'text_dim': '#8b949e', 'text_sub': '#545d6e',
        'accent': '#00f0ff', 'accent2': '#ff007f', 'accent3': '#7c3aed',
        'accent_glow': 'rgba(0, 240, 255, 0.35)',
        'btn': 'rgba(24, 30, 48, 0.9)', 'btn_hover': 'rgba(36, 46, 72, 0.95)',
        'border': 'rgba(0, 240, 255, 0.25)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#161c2b', 'radius': '12px'
    },
    'synthwave': {
        'name': 'Synthwave 80s',
        'bg': '#0c071e', 'bg_card': 'rgba(22, 13, 44, 0.88)',
        'text': '#fdf2f8', 'text_dim': '#d8b4fe', 'text_sub': '#9333ea',
        'accent': '#ff007f', 'accent2': '#a855f7', 'accent3': '#00f0ff',
        'accent_glow': 'rgba(255, 0, 127, 0.40)',
        'btn': 'rgba(40, 18, 72, 0.9)', 'btn_hover': 'rgba(64, 28, 112, 0.95)',
        'border': 'rgba(255, 0, 127, 0.35)', 'border_dim': 'rgba(255, 255, 255, 0.10)',
        'track': '#1c0e35', 'radius': '12px'
    },
    'emerald': {
        'name': 'Emerald Matrix',
        'bg': '#04130d', 'bg_card': 'rgba(8, 28, 20, 0.88)',
        'text': '#ecfdf5', 'text_dim': '#6ee7b7', 'text_sub': '#059669',
        'accent': '#00ff9d', 'accent2': '#10b981', 'accent3': '#06b6d4',
        'accent_glow': 'rgba(0, 255, 157, 0.35)',
        'btn': 'rgba(12, 42, 30, 0.9)', 'btn_hover': 'rgba(18, 62, 45, 0.95)',
        'border': 'rgba(0, 255, 157, 0.30)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0b241a', 'radius': '12px'
    },
    'crimson': {
        'name': 'Crimson Nebula',
        'bg': '#14060b', 'bg_card': 'rgba(32, 12, 20, 0.88)',
        'text': '#fff1f2', 'text_dim': '#fda4af', 'text_sub': '#e11d48',
        'accent': '#ff1744', 'accent2': '#ff6d00', 'accent3': '#f43f5e',
        'accent_glow': 'rgba(255, 23, 68, 0.40)',
        'btn': 'rgba(48, 16, 28, 0.9)', 'btn_hover': 'rgba(74, 24, 42, 0.95)',
        'border': 'rgba(255, 23, 68, 0.32)', 'border_dim': 'rgba(255, 255, 255, 0.09)',
        'track': '#260d17', 'radius': '12px'
    },
    'tokyo': {
        'name': 'Tokyo Violet',
        'bg': '#0b0e1b', 'bg_card': 'rgba(17, 21, 40, 0.88)',
        'text': '#f5f3ff', 'text_dim': '#c4b5fd', 'text_sub': '#7c3aed',
        'accent': '#8b5cf6', 'accent2': '#38bdf8', 'accent3': '#ec4899',
        'accent_glow': 'rgba(139, 92, 246, 0.38)',
        'btn': 'rgba(28, 34, 64, 0.9)', 'btn_hover': 'rgba(42, 52, 98, 0.95)',
        'border': 'rgba(139, 92, 246, 0.30)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#151930', 'radius': '12px'
    },
    'solarpunk': {
        'name': 'Solar Flare',
        'bg': '#140e05', 'bg_card': 'rgba(30, 20, 8, 0.88)',
        'text': '#fffbeb', 'text_dim': '#fcd34d', 'text_sub': '#d97706',
        'accent': '#fbbf24', 'accent2': '#f97316', 'accent3': '#ef4444',
        'accent_glow': 'rgba(251, 191, 36, 0.38)',
        'btn': 'rgba(46, 32, 14, 0.9)', 'btn_hover': 'rgba(68, 48, 20, 0.95)',
        'border': 'rgba(251, 191, 36, 0.30)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#26190a', 'radius': '12px'
    },
    'arctic': {
        'name': 'Frost Aurora',
        'bg': '#05131a', 'bg_card': 'rgba(10, 28, 38, 0.88)',
        'text': '#f0fdfa', 'text_dim': '#99f6e4', 'text_sub': '#0d9488',
        'accent': '#38ef7d', 'accent2': '#00c6ff', 'accent3': '#11998e',
        'accent_glow': 'rgba(56, 239, 125, 0.35)',
        'btn': 'rgba(14, 40, 52, 0.9)', 'btn_hover': 'rgba(22, 60, 80, 0.95)',
        'border': 'rgba(56, 239, 125, 0.30)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0b202c', 'radius': '12px'
    },
    'luxe_oled': {
        'name': 'OLED Diamond',
        'bg': '#000000', 'bg_card': 'rgba(16, 16, 18, 0.94)',
        'text': '#ffffff', 'text_dim': '#94a3b8', 'text_sub': '#64748b',
        'accent': '#00e5ff', 'accent2': '#ffffff', 'accent3': '#70a1ff',
        'accent_glow': 'rgba(0, 229, 255, 0.40)',
        'btn': 'rgba(28, 28, 32, 0.95)', 'btn_hover': 'rgba(45, 45, 52, 0.98)',
        'border': 'rgba(0, 229, 255, 0.32)', 'border_dim': 'rgba(255, 255, 255, 0.12)',
        'track': '#121214', 'radius': '12px'
    },
    'dark': {
        'name': 'Dark Pro',
        'bg': '#0d1117', 'bg_card': 'rgba(19, 24, 35, 0.88)',
        'text': '#f8fafc', 'text_dim': '#94a3b8', 'text_sub': '#475569',
        'accent': '#00e676', 'accent2': '#00b0ff', 'accent3': '#ff9100',
        'accent_glow': 'rgba(0, 230, 118, 0.35)',
        'btn': 'rgba(27, 34, 48, 0.9)', 'btn_hover': 'rgba(38, 48, 68, 0.95)',
        'border': 'rgba(0, 230, 118, 0.25)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#18202e', 'radius': '12px'
    },
    'ocean': {
        'name': 'Ocean Deep',
        'bg': '#07131e', 'bg_card': 'rgba(12, 31, 49, 0.88)',
        'text': '#e2f1ff', 'text_dim': '#7ba2c7', 'text_sub': '#3d6085',
        'accent': '#00d2ff', 'accent2': '#3a7bd5', 'accent3': '#00f2fe',
        'accent_glow': 'rgba(0, 210, 255, 0.35)',
        'btn': 'rgba(16, 42, 68, 0.9)', 'btn_hover': 'rgba(24, 60, 96, 0.95)',
        'border': 'rgba(0, 210, 255, 0.25)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0e2439', 'radius': '12px'
    },
    'amber': {
        'name': 'Cyber Amber',
        'bg': '#0f0e0c', 'bg_card': 'rgba(24, 20, 16, 0.88)',
        'text': '#fff9ed', 'text_dim': '#bfa882', 'text_sub': '#6b5c43',
        'accent': '#ffb300', 'accent2': '#ff5722', 'accent3': '#ff007f',
        'accent_glow': 'rgba(255, 179, 0, 0.35)',
        'btn': 'rgba(38, 30, 22, 0.9)', 'btn_hover': 'rgba(56, 44, 30, 0.95)',
        'border': 'rgba(255, 179, 0, 0.25)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#211a12', 'radius': '12px'
    },
    'light': {
        'name': 'Minimal Studio',
        'bg': '#f3f5f9', 'bg_card': 'rgba(255, 255, 255, 0.92)',
        'text': '#0f172a', 'text_dim': '#475569', 'text_sub': '#94a3b8',
        'accent': '#0284c7', 'accent2': '#6366f1', 'accent3': '#0d9488',
        'accent_glow': 'rgba(2, 132, 199, 0.25)',
        'btn': 'rgba(241, 245, 249, 0.95)', 'btn_hover': 'rgba(226, 232, 240, 0.98)',
        'border': 'rgba(2, 132, 199, 0.3)', 'border_dim': 'rgba(0, 0, 0, 0.08)',
        'track': '#e2e8f0', 'radius': '12px'
    },
    'black_oled': {
        'name': '⚫ OLED Pure Black (Zero Light)',
        'bg': '#000000', 'bg_card': 'rgba(10, 10, 10, 0.95)',
        'text': '#ffffff', 'text_dim': '#a1a1aa', 'text_sub': '#71717a',
        'accent': '#ffffff', 'accent2': '#94a3b8', 'accent3': '#38bdf8',
        'accent_glow': 'rgba(255, 255, 255, 0.40)',
        'btn': 'rgba(20, 20, 20, 0.95)', 'btn_hover': 'rgba(38, 38, 38, 0.98)',
        'border': 'rgba(255, 255, 255, 0.28)', 'border_dim': 'rgba(255, 255, 255, 0.10)',
        'track': '#0d0d0d', 'radius': '12px'
    },
    'black_cyan': {
        'name': '⚡ Obsidian Cyber Cyan',
        'bg': '#000000', 'bg_card': 'rgba(2, 8, 14, 0.95)',
        'text': '#f0fdf4', 'text_dim': '#67e8f9', 'text_sub': '#06b6d4',
        'accent': '#00f3ff', 'accent2': '#0284c7', 'accent3': '#38bdf8',
        'accent_glow': 'rgba(0, 243, 255, 0.45)',
        'btn': 'rgba(4, 18, 30, 0.95)', 'btn_hover': 'rgba(8, 32, 54, 0.98)',
        'border': 'rgba(0, 243, 255, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#05101a', 'radius': '12px'
    },
    'black_gold': {
        'name': '👑 Royal Onyx & Gold',
        'bg': '#000000', 'bg_card': 'rgba(14, 11, 4, 0.95)',
        'text': '#fefce8', 'text_dim': '#fde047', 'text_sub': '#ca8a04',
        'accent': '#fbbf24', 'accent2': '#f59e0b', 'accent3': '#fef08a',
        'accent_glow': 'rgba(251, 191, 36, 0.42)',
        'btn': 'rgba(26, 20, 6, 0.95)', 'btn_hover': 'rgba(44, 34, 10, 0.98)',
        'border': 'rgba(251, 191, 36, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#161105', 'radius': '12px'
    },
    'black_crimson': {
        'name': '🩸 Blood Moon OLED',
        'bg': '#000000', 'bg_card': 'rgba(16, 2, 5, 0.95)',
        'text': '#fff1f2', 'text_dim': '#fda4af', 'text_sub': '#e11d48',
        'accent': '#ff003c', 'accent2': '#ff3366', 'accent3': '#f43f5e',
        'accent_glow': 'rgba(255, 0, 60, 0.48)',
        'btn': 'rgba(30, 6, 12, 0.95)', 'btn_hover': 'rgba(52, 10, 20, 0.98)',
        'border': 'rgba(255, 0, 60, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#1c0408', 'radius': '12px'
    },
    'black_emerald': {
        'name': '🧪 Toxic Acid Emerald',
        'bg': '#000000', 'bg_card': 'rgba(2, 14, 6, 0.95)',
        'text': '#ecfdf5', 'text_dim': '#6ee7b7', 'text_sub': '#059669',
        'accent': '#00ff66', 'accent2': '#10b981', 'accent3': '#34d399',
        'accent_glow': 'rgba(0, 255, 102, 0.42)',
        'btn': 'rgba(6, 26, 12, 0.95)', 'btn_hover': 'rgba(10, 44, 20, 0.98)',
        'border': 'rgba(0, 255, 102, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#05180c', 'radius': '12px'
    },
    'black_purple': {
        'name': '🔮 Deep Abyss Violet',
        'bg': '#000000', 'bg_card': 'rgba(12, 4, 20, 0.95)',
        'text': '#faf5ff', 'text_dim': '#d8b4fe', 'text_sub': '#9333ea',
        'accent': '#a855f7', 'accent2': '#8b5cf6', 'accent3': '#c084fc',
        'accent_glow': 'rgba(168, 85, 247, 0.45)',
        'btn': 'rgba(24, 8, 40, 0.95)', 'btn_hover': 'rgba(42, 14, 70, 0.98)',
        'border': 'rgba(168, 85, 247, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#140822', 'radius': '12px'
    },
    'black_orange': {
        'name': '🔥 Carbon Magma Orange',
        'bg': '#000000', 'bg_card': 'rgba(16, 6, 2, 0.95)',
        'text': '#fff7ed', 'text_dim': '#fdba74', 'text_sub': '#ea580c',
        'accent': '#ff6b00', 'accent2': '#f97316', 'accent3': '#fb923c',
        'accent_glow': 'rgba(255, 107, 0, 0.48)',
        'btn': 'rgba(30, 12, 4, 0.95)', 'btn_hover': 'rgba(54, 22, 8, 0.98)',
        'border': 'rgba(255, 107, 0, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#1c0b03', 'radius': '12px'
    },
    'black_pink': {
        'name': '🌸 Cyber Tokyo Pink',
        'bg': '#000000', 'bg_card': 'rgba(16, 2, 10, 0.95)',
        'text': '#fdf2f8', 'text_dim': '#f472b6', 'text_sub': '#db2777',
        'accent': '#ff1493', 'accent2': '#f43f5e', 'accent3': '#fb7185',
        'accent_glow': 'rgba(255, 20, 147, 0.48)',
        'btn': 'rgba(30, 6, 20, 0.95)', 'btn_hover': 'rgba(54, 10, 36, 0.98)',
        'border': 'rgba(255, 20, 147, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#1c0414', 'radius': '12px'
    },
    'black_frost': {
        'name': '❄️ Absolute Zero Frost',
        'bg': '#000000', 'bg_card': 'rgba(2, 8, 16, 0.95)',
        'text': '#f0f9ff', 'text_dim': '#7dd3fc', 'text_sub': '#0284c7',
        'accent': '#38bdf8', 'accent2': '#0ea5e9', 'accent3': '#bae6fd',
        'accent_glow': 'rgba(56, 189, 248, 0.45)',
        'btn': 'rgba(6, 20, 34, 0.95)', 'btn_hover': 'rgba(10, 38, 62, 0.98)',
        'border': 'rgba(56, 189, 248, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#051420', 'radius': '12px'
    },
    'black_lime': {
        'name': '⚡ Stealth Neon Lime',
        'bg': '#000000', 'bg_card': 'rgba(6, 12, 2, 0.95)',
        'text': '#f7fee7', 'text_dim': '#bef264', 'text_sub': '#65a30d',
        'accent': '#a3e635', 'accent2': '#84cc16', 'accent3': '#d9f99d',
        'accent_glow': 'rgba(163, 230, 53, 0.42)',
        'btn': 'rgba(16, 26, 6, 0.95)', 'btn_hover': 'rgba(30, 46, 10, 0.98)',
        'border': 'rgba(163, 230, 53, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#101804', 'radius': '12px'
    },
    'black_silver': {
        'name': '⚔️ Dark Titanium Chrome',
        'bg': '#000000', 'bg_card': 'rgba(12, 12, 14, 0.95)',
        'text': '#ffffff', 'text_dim': '#cbd5e1', 'text_sub': '#64748b',
        'accent': '#e2e8f0', 'accent2': '#94a3b8', 'accent3': '#f8fafc',
        'accent_glow': 'rgba(226, 232, 240, 0.35)',
        'btn': 'rgba(22, 24, 28, 0.95)', 'btn_hover': 'rgba(38, 42, 48, 0.98)',
        'border': 'rgba(226, 232, 240, 0.30)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#14161a', 'radius': '12px'
    },
    'black_sun': {
        'name': '☀️ Total Eclipse Sun',
        'bg': '#000000', 'bg_card': 'rgba(14, 11, 2, 0.95)',
        'text': '#fefce8', 'text_dim': '#fef08a', 'text_sub': '#eab308',
        'accent': '#facc15', 'accent2': '#ca8a04', 'accent3': '#fde047',
        'accent_glow': 'rgba(250, 204, 21, 0.45)',
        'btn': 'rgba(28, 22, 4, 0.95)', 'btn_hover': 'rgba(48, 38, 8, 0.98)',
        'border': 'rgba(250, 204, 21, 0.38)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#181203', 'radius': '12px'
    },
    'abyss_teal': {
        'name': 'Abyss Teal',
        'bg': '#030d12', 'bg_card': 'rgba(7, 24, 31, 0.90)',
        'text': '#e6fbff', 'text_dim': '#7dd3fc', 'text_sub': '#0e7490',
        'accent': '#22d3ee', 'accent2': '#0ea5e9', 'accent3': '#14b8a6',
        'accent_glow': 'rgba(34, 211, 238, 0.35)',
        'btn': 'rgba(9, 34, 43, 0.92)', 'btn_hover': 'rgba(14, 50, 63, 0.96)',
        'border': 'rgba(34, 211, 238, 0.28)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#08202a', 'radius': '12px'
    },
    'plum_noir': {
        'name': 'Plum Noir',
        'bg': '#0b0710', 'bg_card': 'rgba(24, 14, 32, 0.90)',
        'text': '#f5e9ff', 'text_dim': '#c4a3e0', 'text_sub': '#6b21a8',
        'accent': '#c084fc', 'accent2': '#f472b6', 'accent3': '#8b5cf6',
        'accent_glow': 'rgba(192, 132, 252, 0.35)',
        'btn': 'rgba(34, 20, 46, 0.92)', 'btn_hover': 'rgba(48, 28, 64, 0.96)',
        'border': 'rgba(192, 132, 252, 0.28)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#1a0f26', 'radius': '12px'
    },
    'rust_dark': {
        'name': 'Rust Furnace',
        'bg': '#100806', 'bg_card': 'rgba(32, 17, 12, 0.90)',
        'text': '#fff1e6', 'text_dim': '#fdba74', 'text_sub': '#9a3412',
        'accent': '#f97316', 'accent2': '#dc2626', 'accent3': '#fbbf24',
        'accent_glow': 'rgba(249, 115, 22, 0.35)',
        'btn': 'rgba(44, 22, 15, 0.92)', 'btn_hover': 'rgba(62, 31, 21, 0.96)',
        'border': 'rgba(249, 115, 22, 0.28)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#23120c', 'radius': '12px'
    },
    'forest_deep': {
        'name': 'Deep Forest',
        'bg': '#050c07', 'bg_card': 'rgba(11, 26, 16, 0.90)',
        'text': '#ecfdf5', 'text_dim': '#86efac', 'text_sub': '#15803d',
        'accent': '#4ade80', 'accent2': '#22c55e', 'accent3': '#a3e635',
        'accent_glow': 'rgba(74, 222, 128, 0.32)',
        'btn': 'rgba(15, 34, 22, 0.92)', 'btn_hover': 'rgba(22, 48, 31, 0.96)',
        'border': 'rgba(74, 222, 128, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0d2114', 'radius': '12px'
    },
    'ice_night': {
        'name': 'Ice Night',
        'bg': '#060a14', 'bg_card': 'rgba(12, 20, 34, 0.90)',
        'text': '#eff6ff', 'text_dim': '#93c5fd', 'text_sub': '#1d4ed8',
        'accent': '#60a5fa', 'accent2': '#a5b4fc', 'accent3': '#38bdf8',
        'accent_glow': 'rgba(96, 165, 250, 0.35)',
        'btn': 'rgba(16, 27, 46, 0.92)', 'btn_hover': 'rgba(24, 39, 66, 0.96)',
        'border': 'rgba(96, 165, 250, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0d1728', 'radius': '12px'
    },
    'sakura_night': {
        'name': 'Sakura Night',
        'bg': '#100810', 'bg_card': 'rgba(30, 16, 28, 0.90)',
        'text': '#fff0f6', 'text_dim': '#f9a8d4', 'text_sub': '#9d174d',
        'accent': '#f472b6', 'accent2': '#fb7185', 'accent3': '#e879f9',
        'accent_glow': 'rgba(244, 114, 182, 0.33)',
        'btn': 'rgba(40, 20, 36, 0.92)', 'btn_hover': 'rgba(56, 28, 50, 0.96)',
        'border': 'rgba(244, 114, 182, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#241222', 'radius': '12px'
    },
    'voltage': {
        'name': 'Voltage',
        'bg': '#0a0b04', 'bg_card': 'rgba(24, 26, 10, 0.90)',
        'text': '#fefce8', 'text_dim': '#d9f99d', 'text_sub': '#4d7c0f',
        'accent': '#a3e635', 'accent2': '#facc15', 'accent3': '#22d3ee',
        'accent_glow': 'rgba(163, 230, 53, 0.35)',
        'btn': 'rgba(30, 33, 13, 0.92)', 'btn_hover': 'rgba(44, 48, 19, 0.96)',
        'border': 'rgba(163, 230, 53, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#1a1c0b', 'radius': '12px'
    },
    'mono_ink': {
        'name': 'Mono Ink',
        'bg': '#070708', 'bg_card': 'rgba(18, 18, 21, 0.92)',
        'text': '#f4f4f5', 'text_dim': '#a1a1aa', 'text_sub': '#52525b',
        'accent': '#e4e4e7', 'accent2': '#a1a1aa', 'accent3': '#71717a',
        'accent_glow': 'rgba(228, 228, 231, 0.22)',
        'btn': 'rgba(26, 26, 30, 0.92)', 'btn_hover': 'rgba(38, 38, 43, 0.96)',
        'border': 'rgba(228, 228, 231, 0.18)', 'border_dim': 'rgba(255, 255, 255, 0.07)',
        'track': '#151518', 'radius': '12px'
    },
    'desert_night': {
        'name': 'Desert Night',
        'bg': '#0d0904', 'bg_card': 'rgba(30, 22, 12, 0.90)',
        'text': '#fffbeb', 'text_dim': '#fcd34d', 'text_sub': '#a16207',
        'accent': '#fbbf24', 'accent2': '#fb923c', 'accent3': '#fde68a',
        'accent_glow': 'rgba(251, 191, 36, 0.30)',
        'btn': 'rgba(38, 28, 15, 0.92)', 'btn_hover': 'rgba(52, 38, 20, 0.96)',
        'border': 'rgba(251, 191, 36, 0.24)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#221a0e', 'radius': '12px'
    },
    'galaxy_blue': {
        'name': 'Galaxy Blue',
        'bg': '#050816', 'bg_card': 'rgba(11, 17, 42, 0.92)',
        'text': '#eef2ff', 'text_dim': '#a5b4fc', 'text_sub': '#3730a3',
        'accent': '#6366f1', 'accent2': '#22d3ee', 'accent3': '#a855f7',
        'accent_glow': 'rgba(99, 102, 241, 0.38)',
        'btn': 'rgba(16, 23, 52, 0.92)', 'btn_hover': 'rgba(24, 34, 74, 0.96)',
        'border': 'rgba(99, 102, 241, 0.28)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#0c1230', 'radius': '12px'
    },
    'carbon_red': {
        'name': 'Carbon Red',
        'bg': '#08090a', 'bg_card': 'rgba(20, 22, 24, 0.94)',
        'text': '#f8fafc', 'text_dim': '#fca5a5', 'text_sub': '#7f1d1d',
        'accent': '#ef4444', 'accent2': '#b91c1c', 'accent3': '#f97316',
        'accent_glow': 'rgba(239, 68, 68, 0.32)',
        'btn': 'rgba(26, 28, 31, 0.94)', 'btn_hover': 'rgba(38, 40, 44, 0.97)',
        'border': 'rgba(239, 68, 68, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.07)',
        'track': '#141618', 'radius': '12px'
    },
    'underwater': {
        'name': 'Underwater',
        'bg': '#030f14', 'bg_card': 'rgba(7, 26, 34, 0.90)',
        'text': '#e0f2fe', 'text_dim': '#67e8f9', 'text_sub': '#155e75',
        'accent': '#06b6d4', 'accent2': '#3b82f6', 'accent3': '#2dd4bf',
        'accent_glow': 'rgba(6, 182, 212, 0.34)',
        'btn': 'rgba(9, 32, 42, 0.92)', 'btn_hover': 'rgba(13, 46, 60, 0.96)',
        'border': 'rgba(6, 182, 212, 0.26)', 'border_dim': 'rgba(255, 255, 255, 0.08)',
        'track': '#07222c', 'radius': '12px'
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SPRING PHYSICS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class Spring:
    """Second-order damped harmonic spring for fluid animations."""
    def __init__(self, stiffness=240.0, damping=15.0, precision=0.0005):
        self.stiffness = stiffness
        self.damping = damping
        self.precision = precision
        self.value = 0.0
        self.target = 0.0
        self.velocity = 0.0
        self.settled = True

    def set_target(self, target):
        if abs(self.target - target) > self.precision:
            self.settled = False
        self.target = target

    def step(self, dt):
        """Advance by dt using the closed-form solution of the spring ODE.

        Explicit Euler (v += a*dt; x += v*dt) is only accurate while k*dt^2 is
        small, so the same bar reacted differently at 24 FPS and at 120 FPS —
        and could even ring at coarse frame rates. The exact solution makes the
        motion frame-rate independent, which is what "precise" needs.
        """
        dt = max(0.0, min(float(dt), 0.5))
        if dt <= 0.0:
            return self.value
        w0 = math.sqrt(max(0.0, self.stiffness))
        if w0 < 1e-6:
            self.value = self.target
            self.velocity = 0.0
            self.settled = True
            return self.value
        disp = self.value - self.target
        vel = self.velocity
        zeta = self.damping / (2.0 * w0)
        if zeta < 0.999:
            wd = w0 * math.sqrt(1.0 - zeta * zeta)
            e = math.exp(-zeta * w0 * dt)
            c, sn = math.cos(wd * dt), math.sin(wd * dt)
            a = disp
            b = (vel + zeta * w0 * disp) / wd
            self.value = self.target + e * (a * c + b * sn)
            self.velocity = e * ((b * wd - zeta * w0 * a) * c - (a * wd + zeta * w0 * b) * sn)
        elif zeta < 1.001:                      # critically damped
            e = math.exp(-w0 * dt)
            a = disp
            b = vel + w0 * disp
            self.value = self.target + e * (a + b * dt)
            self.velocity = e * (b - w0 * (a + b * dt))
        else:                                   # overdamped
            root = w0 * math.sqrt(zeta * zeta - 1.0)
            r1 = -w0 * zeta + root
            r2 = -w0 * zeta - root
            c1 = (vel - r2 * disp) / (r1 - r2)
            c2 = disp - c1
            e1, e2 = math.exp(r1 * dt), math.exp(r2 * dt)
            self.value = self.target + c1 * e1 + c2 * e2
            self.velocity = c1 * r1 * e1 + c2 * r2 * e2
        if abs(self.value - self.target) < self.precision and abs(self.velocity) < self.precision:
            self.settled = True
            self.value = self.target
            self.velocity = 0.0
            self.velocity = 0.0
        return self.value


# ─────────────────────────────────────────────────────────────────────────────
# SMOOTH ADJUSTABLE SPLITTER WITH TACTILE GRIP
# ─────────────────────────────────────────────────────────────────────────────

class SmoothSplitterHandle(QSplitterHandle):
    """Refined splitter handle with glowing centered pill grip and smooth feedback."""
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        is_hover = self.underMouse()
        if self.orientation() == Qt.Orientation.Horizontal:
            gw, gh = 4.0, 32.0
            gx = (rect.width() - gw) / 2.0
            gy = (rect.height() - gh) / 2.0
            grip_rect = QRectF(gx, gy, gw, gh)
        else:
            gw, gh = 38.0, 4.0
            gx = (rect.width() - gw) / 2.0
            gy = (rect.height() - gh) / 2.0
            grip_rect = QRectF(gx, gy, gw, gh)

        if is_hover:
            painter.setBrush(QBrush(QColor('#00f0ff')))
        else:
            painter.setBrush(QBrush(QColor(255, 255, 255, 45)))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(grip_rect, 2.0, 2.0)


class SmoothSplitter(QSplitter):
    """QSplitter configured for smooth adjustable panel resizing and custom grips."""
    def __init__(self, orientation=Qt.Orientation.Vertical, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(8)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return SmoothSplitterHandle(self.orientation(), self)


# ─────────────────────────────────────────────────────────────────────────────
# REAL-TIME AUDIO BUFFER & SPECTRUM EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

ANALYSIS_RATE = 32000          # Nyquist 16 kHz: hi-hats/air survive
ANALYSIS_BANDS = 128           # log-spaced bands, 25 Hz .. 15.5 kHz
ANALYSIS_FFT = 2048            # 64 ms window @32k -> 15.6 Hz bins
ANALYSIS_HOP = 512             # 16 ms hop -> 62.5 analysis frames/s
BEAT_THRESHOLD = 0.42          # onset envelope is per-track normalised
BEAT_REFRACTORY = 0.115        # seconds: caps the reaction at ~8.7 beats/s
BEAT_WINDOW = 0.11             # how long a beat keeps the visuals "hit"


class AudioBuffer:
    """Decoded PCM audio buffer providing microsecond-accurate FFT spectrum and beat flux."""
    def __init__(self, raw_bytes, sample_rate=16000):
        self.sample_rate = sample_rate
        if HAS_NUMPY:
            self.samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            count = len(raw_bytes) // 2
            ints = struct.unpack(f"<{count}h", raw_bytes[:count * 2])
            self.samples = [v / 32768.0 for v in ints]
        self.total_samples = len(self.samples)
        self.duration_sec = (self.total_samples / sample_rate) if sample_rate > 0 else 0.0
        # Precomputed analysis table (filled by build_analysis()).
        self._spec = None
        self._rms = None
        self._flux = None
        self._hop_sec = 0.016
        self._beats = None
        self._beat_strength = None

    def build_analysis(self):
        """Precompute a log-band spectrogram + onset envelope for the whole track.

        One single 64 ms FFT grabbed at the playhead is a poor spectrum: it is
        windowed arbitrarily, ignores everything above 8 kHz (the old decode
        rate), and its band means under-read the wide high bands. Analysing the
        whole file once, off the UI thread, gives the visualizer an exact,
        AGC'd, frame-interpolatable spectrum at any repaint rate.
        """
        if not HAS_NUMPY or self.total_samples < ANALYSIS_FFT * 2:
            return False
        try:
            n_fft = ANALYSIS_FFT
            hop = ANALYSIS_HOP
            sr = float(self.sample_rate)
            frames = 1 + (self.total_samples - n_fft) // hop
            if frames < 2:
                return False

            # log-spaced band edges -> FFT bin starts (strictly increasing)
            top = min(sr * 0.48, 15600.0)
            edges = np.geomspace(25.0, top, ANALYSIS_BANDS + 1)
            bins = np.rint(edges / (sr / n_fft)).astype(np.int32)
            starts, last = [], 0
            for b in bins[:-1]:
                b = int(max(b, last + 1))
                if b >= n_fft // 2:
                    break
                starts.append(b)
                last = b
            if len(starts) < 8:
                return False
            starts = np.asarray(starts, dtype=np.intp)

            win = np.hanning(n_fft).astype(np.float32)
            buf = np.ascontiguousarray(self.samples, dtype=np.float32)
            stride = buf.strides[0]
            view = np.lib.stride_tricks.as_strided(
                buf, shape=(frames, n_fft), strides=(hop * stride, stride), writeable=False)

            spec = np.empty((frames, starts.size), dtype=np.float32)
            rms = np.empty(frames, dtype=np.float32)
            chunk = 1024
            for k in range(0, frames, chunk):
                block = view[k:k + chunk]
                mag = np.abs(np.fft.rfft(block * win, axis=1))
                spec[k:k + block.shape[0]] = np.maximum.reduceat(mag, starts, axis=1)
                rms[k:k + block.shape[0]] = np.sqrt(np.mean(block * block, axis=1))

            # dB compression so quiet detail is visible, then gentle AGC so a
            # quiet band still moves without flattening the true tonal balance
            db = 20.0 * np.log10(spec + 1e-7)
            db -= float(db.max())
            v = np.clip((db + 58.0) / 58.0, 0.0, 1.0)
            # Partial AGC. Dividing by `ref` before the clip (the old form)
            # boosted loud bands *further* and saturated them against the 0-1
            # ceiling while burying quiet ones -- the opposite of gain control.
            # Pull both ends toward the middle instead: the tonal shape stays
            # visible, the bass stops pinning a solid wall of spokes at full
            # length, and the top of the spectrum still has something to say.
            band_top = np.percentile(v, 95.0, axis=0)
            ref = float(np.median(band_top)) or 1.0
            gain = np.clip((band_top / max(1e-6, ref)) ** -0.40, 0.70, 1.60).astype(np.float32)
            spec = np.clip(v * gain, 0.0, 1.0) ** 0.88

            peak_rms = float(np.percentile(rms, 95.0)) or 1.0
            rms = np.clip(rms / peak_rms, 0.0, 1.0)
            # Onset envelope: half-wave rectified rise of the *log* band values.
            # Magnitude flux on 20 raw bins is dominated by decay tails and
            # loudness; this fires on the attack of a kick, snare or pluck.
            # Smooth first: dB-domain noise flickers several dB frame to frame,
            # which would otherwise look like an onset on a quiet passage.
            sm = db.copy()
            sm[1:-1] = (db[:-2] + db[1:-1] * 2.0 + db[2:]) * 0.25
            dv = np.diff(np.vstack([sm[:1], sm]), axis=0)
            weight = np.linspace(1.0, 0.45, db.shape[1]).astype(np.float32)
            dv = np.maximum(dv - 6.0, 0.0)          # 6 dB deadzone: attacks only
            flux = dv @ weight / float(db.shape[1])
            peak_flux = float(np.percentile(flux, 99.0)) or 1.0
            flux = np.clip(flux / peak_flux, 0.0, 1.0) ** 0.85

            # Beat grid: local maxima of the onset envelope with a 115 ms
            # refractory. Deciding this once, per track, makes the reaction
            # identical at any repaint rate — a per-frame threshold fires a
            # different number of times depending on how often you look.
            hop_sec = hop / sr
            if flux.size > 2:
                mid = flux[1:-1]
                is_peak = (mid > BEAT_THRESHOLD) & (mid >= flux[:-2]) & (mid >= flux[2:])
                cand = np.flatnonzero(is_peak) + 1
                keep, strengths, last_t = [], [], -1e9
                for idx in cand:
                    t = float(idx) * hop_sec
                    if t - last_t >= BEAT_REFRACTORY:
                        keep.append(t)
                        strengths.append(float(flux[idx]))
                        last_t = t
                self._beats = np.asarray(keep, dtype=np.float32)
                self._beat_strength = np.asarray(strengths, dtype=np.float32)

            self._spec = spec.astype(np.float32)
            self._rms = rms.astype(np.float32)
            self._flux = flux.astype(np.float32)
            self._hop_sec = hop / sr
            return True
        except Exception as exc:      # never break track loading over visuals
            print('[visualizer] analysis failed:', exc)
            self._spec = None
            return False

    def last_beat(self, pos_sec):
        """(time, strength) of the most recent beat at this playhead, or None."""
        if self._beats is None or self._beats.size == 0:
            return None
        idx = int(np.searchsorted(self._beats, pos_sec, side='right')) - 1
        if idx < 0:
            return None
        return float(self._beats[idx]), float(self._beat_strength[idx])

    def analysis_frame(self, pos_sec):
        """(bands[128], bass, rms, onset) sampled at the exact playhead."""
        if self._spec is None:
            bands, bass, rms = self._spectrum_live(pos_sec, ANALYSIS_BANDS)
            return bands, bass, rms, 0.0
        n = self._spec.shape[0]
        f = max(0.0, float(pos_sec)) / max(1e-6, self._hop_sec)
        i0 = int(f)
        if i0 >= n - 1:
            i0 = n - 1
            i1, a = i0, 0.0
        else:
            a = f - i0
            i1 = i0 + 1
        row = self._spec[i0] * (1.0 - a) + self._spec[i1] * a
        rms = float(self._rms[i0] * (1.0 - a) + self._rms[i1] * a)
        onset = float(self._flux[i0] * (1.0 - a) + self._flux[i1] * a)
        bass = float(np.mean(row[:max(4, ANALYSIS_BANDS // 12)]))
        return row, bass, rms, onset

    def get_spectrum_and_energy(self, pos_sec, num_bands=64):
        """Bands resampled to num_bands (table path when analysis is ready)."""
        if self._spec is not None:
            row, bass, rms, _onset = self.analysis_frame(pos_sec)
            if num_bands and num_bands > 0 and num_bands != row.shape[0]:
                src = np.linspace(0.0, row.shape[0] - 1.0, int(num_bands))
                lo = np.floor(src).astype(np.intp)
                hi = np.minimum(lo + 1, row.shape[0] - 1)
                frac = (src - lo).astype(np.float32)
                row = row[lo] * (1.0 - frac) + row[hi] * frac
            return [float(x) for x in row], bass, rms
        return self._spectrum_live(pos_sec, num_bands)

    def _spectrum_live(self, pos_sec, num_bands=64):
        if self.total_samples == 0:
            return [0.0] * num_bands, 0.0, 0.0

        idx = int(pos_sec * self.sample_rate)
        if idx < 0 or idx >= self.total_samples:
            return [0.0] * num_bands, 0.0, 0.0

        N = 2048
        if HAS_NUMPY:
            chunk = self.samples[idx: idx + N]
            if len(chunk) < N:
                chunk = np.pad(chunk, (0, N - len(chunk)))
            w = np.hanning(len(chunk))
            fft = np.abs(np.fft.rfft(chunk * w))
            fft_len = len(fft)
            bands = []
            for b in range(num_bands):
                f_start = int((b / num_bands) ** 2.2 * (fft_len - 1))
                f_end = int(((b + 1) / num_bands) ** 2.2 * (fft_len - 1))
                f_end = max(f_start + 1, f_end)
                slice_data = fft[f_start:f_end]
                band_val = float(np.max(slice_data)) if len(slice_data) > 0 else 0.0
                bands.append(math.tanh(band_val * 0.14))

            bass_cnt = max(4, num_bands // 10)
            bass_energy = float(np.mean(bands[:bass_cnt]))
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            return bands, bass_energy, rms
        else:
            chunk = self.samples[idx: idx + min(512, self.total_samples - idx)]
            if not chunk:
                return [0.0] * num_bands, 0.0, 0.0
            rms = math.sqrt(sum(v * v for v in chunk) / len(chunk))
            bands = [min(1.0, rms * (1.0 - (b / num_bands) * 0.35) * random.uniform(0.85, 1.15)) for b in range(num_bands)]
            return bands, rms, rms


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO VISUALIZER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class AudioVisualizerEngine:
    """High-density frequency analyzer with spring physics, live EQ coupling & real audio analysis."""
    def __init__(self, max_bands=128):
        self.max_bands = max_bands
        self.levels = [0.0] * max_bands
        self.peaks = [0.0] * max_bands
        self.bass_energy = 0.0
        self.mid_energy = 0.0
        self.treble_energy = 0.0
        self.raw_rms = 0.0
        self.springs = [Spring(stiffness=430.0, damping=25.0) for _ in range(max_bands)]
        self.beat = False
        self.beat_strength = 0.0
        self.beat_history = []      # [(t, bass)] — time based, so FPS cannot bias it
        self.onset_history = []
        self._last_beat_t = -1.0
        self._beat_armed = True
        self.time = 0.0
        self.playing = False
        self.active_bands = 0       # how many slots update() last filled
        self.eq_multipliers = [1.0] * 7
        self.sensitivity = 1.0

    def set_eq_gains(self, eq_dict):
        keys = ['eq_60', 'eq_150', 'eq_400', 'eq_1000', 'eq_2500', 'eq_6000', 'eq_14000']
        for i, k in enumerate(keys):
            db = eq_dict.get(k, 0.0)
            self.eq_multipliers[i] = max(0.1, min(2.5, 1.0 + (db / 15.0) * 0.75))

    def update(self, dt, playing=False, active_bands=64, audio_bands=None,
               bass_energy=None, raw_rms=0.0, onset=None, beat_age=None, beat_peak=None):
        self.time += dt
        self.playing = playing
        n = min(active_bands, self.max_bands)
        self.active_bands = n

        if not playing:
            for i in range(n):
                self.springs[i].set_target(0.0)
                self.levels[i] = self.springs[i].step(dt)
                self.peaks[i] = max(0.0, self.peaks[i] - 1.2 * dt)
            self.beat = False
            self.beat_strength = max(0.0, self.beat_strength - 4.0 * dt)
            return

        if audio_bands is not None and len(audio_bands) >= n:
            # ── Genuine Audio Spectrum & Dynamic Coupling ──
            for i in range(n):
                freq = i / max(1, n - 1)
                eq_idx = min(6, int(freq * 7))
                eq_boost = self.eq_multipliers[eq_idx]
                target = min(1.0, max(0.02, audio_bands[i] * eq_boost * self.sensitivity * 1.35))
                self.springs[i].set_target(target)
                self.levels[i] = max(0.0, min(1.0, self.springs[i].step(dt)))

                if self.levels[i] >= self.peaks[i]:
                    self.peaks[i] = self.levels[i]
                else:
                    self.peaks[i] = max(0.0, self.peaks[i] - 0.75 * dt)

            cur_bass = bass_energy if bass_energy is not None else (sum(self.levels[:max(4, n // 10)]) / max(4, n // 10))
            # Time-windowed history: a fixed *frame* count would change meaning
            # with the repaint rate (30 frames = 0.7 s at 42 fps, 0.2 s at 144).
            self.beat_history.append((self.time, cur_bass))
            while self.beat_history and self.beat_history[0][0] < self.time - 0.55:
                self.beat_history.pop(0)
            vals = [v for _t, v in self.beat_history]
            avg_bass = sum(vals) / max(1, len(vals))

            if beat_age is not None:
                # ── Authoritative path: the track's beat grid says a hit
                # happened beat_age seconds ago. Pure function of the
                # playhead, so 24 FPS and 240 FPS agree exactly.
                if 0.0 <= beat_age < BEAT_WINDOW:
                    self.beat = True
                    hit = min(1.0, 0.30 + (beat_peak or 0.5) * 0.9)
                    self.beat_strength = max(
                        self.beat_strength,
                        hit * (1.0 - 0.55 * (beat_age / BEAT_WINDOW)))
                    self._last_beat_t = self.time
                else:
                    self.beat = False
                    self.beat_strength = max(0.0, self.beat_strength - 4.0 * dt)
            else:
                # ── Fallback when the track has no usable beat grid: onset
                # envelope, then plain bass energy above its own average.
                fired = False
                strength = 0.0
                if onset is not None:
                    self.onset_history.append((self.time, onset))
                    while self.onset_history and self.onset_history[0][0] < self.time - 1.0:
                        self.onset_history.pop(0)
                    if onset > 0.42 and self._beat_armed:
                        if self.time - self._last_beat_t > BEAT_REFRACTORY:
                            fired = True
                            strength = min(1.0, 0.30 + onset * 0.9)
                        self._beat_armed = False
                    elif onset < 0.26:
                        self._beat_armed = True
                if not fired and cur_bass > avg_bass * 1.30 and cur_bass > 0.08:
                    fired = True
                    strength = min(1.0, (cur_bass / max(0.01, avg_bass) - 1.0) * 2.0)

                if fired:
                    self.beat = True
                    self.beat_strength = max(self.beat_strength * 0.6, strength)
                    self._last_beat_t = self.time
                else:
                    self.beat = False
                    self.beat_strength = max(0.0, self.beat_strength - 4.0 * dt)
        else:
            # ── Acoustic Fallback ──
            for i in range(n):
                freq = i / max(1, n - 1)
                eq_idx = min(6, int(freq * 7))
                eq_boost = self.eq_multipliers[eq_idx]

                bass_hit = 0.45 * math.sin(self.time * 3.2) * math.exp(-freq * 3.5)
                mid_groove = 0.30 * math.sin(self.time * 5.1 + i * 0.28) * (1.0 - abs(freq - 0.4) * 1.5)
                high_air = 0.20 * math.cos(self.time * 8.4 + i * 0.45) * (freq ** 0.8)
                sparkle = 0.12 * random.random() * (1.0 - freq * 0.4)
                raw = (bass_hit + mid_groove + high_air + sparkle) * eq_boost * self.sensitivity

                target = max(0.02, min(0.98, abs(raw)))
                self.springs[i].set_target(target)
                self.levels[i] = self.springs[i].step(dt)

                if self.levels[i] > self.peaks[i]:
                    self.peaks[i] = self.levels[i]
                else:
                    self.peaks[i] = max(0.0, self.peaks[i] - 0.7 * dt)

            bass_val = self.levels[0]
            self.beat_history.append((self.time, bass_val))
            while self.beat_history and self.beat_history[0][0] < self.time - 0.55:
                self.beat_history.pop(0)
            avg_bass = sum(v for _t, v in self.beat_history) / max(1, len(self.beat_history))

            if bass_val > avg_bass * 1.35 and bass_val > 0.35:
                self.beat = True
                self.beat_strength = min(1.0, (bass_val - avg_bass) * 2.5)
            else:
                self.beat = False
                self.beat_strength = max(0.0, self.beat_strength - 3.5 * dt)

        # ── Clamp the spring state to [0, 1] ──
        # Under-damped springs overshoot on transients and can dip below zero.
        # Painters assume 0..1 and a negative base with a fractional exponent
        # (lvl ** 0.5) yields a complex number, which crashes QPainterPath.
        for _i, _lv in enumerate(self.levels):
            # also catches NaN/inf coming out of the FFT on digital silence —
            # NaN survives arithmetic and then explodes inside int()/QColor()
            if not math.isfinite(_lv) or _lv < 0.0:
                self.levels[_i] = 0.0
            elif _lv > 1.0:
                self.levels[_i] = 1.0

        # ── Derived band energies (consumed by the spectrum painters) ──
        # Several visualizer modes reference engine.bass_energy / mid / treble;
        # keep them materialised every tick so painters never hit AttributeError.
        n_bands = max(1, min(len(self.levels), self.max_bands))
        third = max(1, n_bands // 3)
        self.bass_energy = sum(self.levels[:third]) / third
        self.mid_energy = sum(self.levels[third:2 * third]) / max(1, len(self.levels[third:2 * third]))
        self.treble_energy = sum(self.levels[2 * third:n_bands]) / max(1, len(self.levels[2 * third:n_bands]))
        self.raw_rms = raw_rms if raw_rms else self.bass_energy


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND AUDIO WAVEFORM EXTRACTION WORKER
# ─────────────────────────────────────────────────────────────────────────────

class WaveformExtractorThread(QThread):
    waveformReady = pyqtSignal(str, list, object)  # filepath, points, audio_buffer

    def __init__(self, filepath, num_points=1000):
        super().__init__()
        self.filepath = filepath
        self.num_points = num_points
        self._cancel = threading.Event()
        self._proc = None
        self._proc_lock = threading.Lock()

    # ── cooperative cancellation ─────────────────────────────────────────────
    # QThread.terminate() must never be used on this worker. It kills the thread
    # wherever it happens to be with TerminateThread() — typically inside
    # subprocess.Popen → _execute_child while ffmpeg is being spawned — leaving
    # the interpreter with a half-built process object. The NEXT spawn then dies
    # with an access violation inside python314.dll and takes the whole app down.
    # Instead: flag the worker and kill its ffmpeg child, so communicate() returns
    # immediately and run() unwinds on its own.
    def request_cancel(self):
        self._cancel.set()
        self._kill_child()

    def _cancelled(self):
        return self._cancel.is_set()

    def _kill_child(self):
        with self._proc_lock:
            proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass

    def run(self):
        try:
            if self._cancelled():
                return
            if not FFMPEG_DIR or not os.path.exists(self.filepath):
                self._emit_synthetic()
                return

            cmd = [
                f"{FFMPEG_DIR}/ffmpeg.exe", '-i', self.filepath,
                '-ac', '1', '-filter:a', 'aresample=%d' % ANALYSIS_RATE,
                '-map', '0:a:0', '-c:a', 'pcm_s16le', '-f', 's16le', '-'
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            with self._proc_lock:
                self._proc = proc
            if self._cancelled():            # cancelled while the child was spawning
                self._kill_child()
            raw_data, _ = proc.communicate(timeout=10)

            if self._cancelled():
                return
            if not raw_data or len(raw_data) < 200:
                self._emit_synthetic()
                return

            audio_buf = AudioBuffer(raw_data, sample_rate=ANALYSIS_RATE)
            audio_buf.build_analysis()
            samples = audio_buf.samples
            total_samples = len(samples)
            step = max(1, total_samples // self.num_points)
            points = []

            if HAS_NUMPY:
                for i in range(self.num_points):
                    start = i * step
                    chunk = samples[start: start + step]
                    if len(chunk) > 0:
                        peak = float(np.max(np.abs(chunk)))
                        rms = float(np.sqrt(np.mean(chunk ** 2)))
                        val = (peak * 0.72 + rms * 0.28) ** 1.25
                        points.append(val)
                    else:
                        points.append(0.0)
            else:
                for i in range(self.num_points):
                    start = i * step
                    chunk = samples[start: start + step]
                    if chunk:
                        peak = max(abs(v) for v in chunk)
                        rms = math.sqrt(sum(v * v for v in chunk) / len(chunk))
                        val = (peak * 0.72 + rms * 0.28) ** 1.25
                        points.append(val)
                    else:
                        points.append(0.0)

            max_pk = max(points) if points else 1.0
            if max_pk > 0.02:
                norm_scale = min(3.0, 0.94 / max_pk)
                points = [min(1.0, round(p * norm_scale, 4)) for p in points]

            if self._cancelled():
                return
            self.waveformReady.emit(self.filepath, points, audio_buf)

        except Exception:
            self._emit_synthetic()

    def _emit_synthetic(self):
        if self._cancelled():
            return
        points = []
        for i in range(self.num_points):
            f = i / float(self.num_points)
            val = (0.28 * math.sin(f * 24.0) + 0.38 * math.sin(f * 6.5) + 0.18 * random.random()) ** 1.2
            points.append(round(max(0.05, min(0.95, abs(val))), 4))
        self.waveformReady.emit(self.filepath, points, None)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO TRACK WAVEFORM OVERVIEW BAR (Below the main slider)
# ─────────────────────────────────────────────────────────────────────────────

class AudioWaveformTrackBar(QWidget):
    """
    Overview waveform mini-map displaying mirror amplitude peaks across
    the full track length, played/unplayed gradients, A/B loop highlights,
    slender playhead line, and direct click/drag scrub seeking.
    """
    seekRequested = pyqtSignal(int)
    audioBufferReady = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        # Live shimmer / playhead-pulse repaint driver (only while visible)
        self._fx_timer = QTimer(self)
        self._fx_timer.timeout.connect(self._on_fx_tick)
        self._fx_timer.start(50)

        self.current_filepath = None
        self.waveform_data = []
        self.duration_ms = 0
        self.current_pos = 0

        self.loop_a = None
        self.loop_b = None
        self.is_dragging = False
        self.hover_x = None

        # Aurora-ridge static layer cache (rebuilt only on resize / data / theme change)
        self._aurora_key = None
        self._aurora_peaks = []
        self._aurora_beats = []
        self._aurora_base = None
        self._aurora_live = None
        self.track_bg = '#161c2b'
        self.accent = QColor('#00f0ff')
        self.accent2 = QColor('#ff007f')

        self.worker = None
        self._retired_workers = []
        self.waveform_cache = {}
        self.cache_file = DATA_DIR / 'waveform_cache.json'
        self._load_cache()

    def _on_fx_tick(self):
        if self.isVisible() and self.waveform_data:
            self.update()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.waveform_cache = json.load(f)
            except Exception:
                self.waveform_cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.waveform_cache, f)
        except Exception:
            pass

    def set_theme_colors(self, track_bg, accent_hex, accent2_hex):
        self.track_bg = track_bg
        self.accent = QColor(accent_hex)
        self.accent2 = QColor(accent2_hex)
        self.update()

    def _interpolate_color(self, c1, c2, frac):
        frac = max(0.0, min(1.0, frac))
        r = int(c1.red() + (c2.red() - c1.red()) * frac)
        g = int(c1.green() + (c2.green() - c1.green()) * frac)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * frac)
        a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * frac)
        return QColor(r, g, b, a)

    def load_track(self, filepath):
        self.current_filepath = filepath
        if filepath in self.waveform_cache and len(self.waveform_cache[filepath]) >= 800:
            self.waveform_data = self.waveform_cache[filepath]
            self.update()
        else:
            self.waveform_data = []
            self.update()

        old = self.worker
        if old is not None and old.isRunning():
            # Ask the worker to stop and kill its ffmpeg child; it unwinds on its
            # own within a few ms. Never QThread.terminate() — see request_cancel().
            old.request_cancel()
            self._retired_workers.append(old)
            old.finished.connect(lambda w=old: self._forget_worker(w))
        self._reap_workers()

        self.worker = WaveformExtractorThread(filepath, num_points=1000)
        self.worker.waveformReady.connect(self._on_waveform_extracted)
        self.worker.start()

    # ── retired-worker bookkeeping ───────────────────────────────────────────
    # A QThread whose Python reference disappears while the OS thread is still
    # alive gets its C++ object destroyed mid-run. Keep cancelled workers here
    # until they report finished, then drop them.
    def _reap_workers(self):
        alive = []
        for w in self._retired_workers:
            try:
                done = w.isFinished()
            except RuntimeError:
                done = True
            if done:
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
            else:
                alive.append(w)
        self._retired_workers = alive

    def _forget_worker(self, worker):
        try:
            self._retired_workers.remove(worker)
        except ValueError:
            pass
        try:
            worker.deleteLater()
        except RuntimeError:
            pass

    def _on_waveform_extracted(self, path, points, audio_buf):
        if path == self.current_filepath:
            self.waveform_data = points
            self.waveform_cache[path] = points
            self._save_cache()
            self.update()
            if audio_buf is not None:
                self.audioBufferReady.emit(path, audio_buf)

    def set_duration(self, ms):
        self.duration_ms = max(0, ms)
        self.update()

    def set_position(self, ms):
        self.current_pos = max(0, ms)
        self.update()

    def set_loop_points(self, a_ms, b_ms):
        self.loop_a = a_ms
        self.loop_b = b_ms
        self.update()

    def clear_loop(self):
        self.loop_a = None
        self.loop_b = None
        self.update()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_x = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._seek_from_x(event.position().x())
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        self.hover_x = x
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._seek_from_x(x)

        if self.duration_ms > 0:
            frac = max(0.0, min(1.0, x / max(1.0, float(self.width()))))
            hover_ms = int(frac * self.duration_ms)
            s = hover_ms // 1000
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            QToolTip.showText(self.mapToGlobal(QPoint(int(x), -22)), f"Waveform Seek: {time_str}", self)

        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
        super().mouseReleaseEvent(event)

    def _seek_from_x(self, x):
        if self.duration_ms > 0:
            w = max(1.0, float(self.width()))
            frac = max(0.0, min(1.0, x / w))
            target_ms = int(frac * self.duration_ms)
            self.current_pos = target_ms
            self.seekRequested.emit(target_ms)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h / 2.0
        max_amp_h = (h - 6) / 2.0

        # Background track frame
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), 6, 6)
        painter.setClipPath(clip_path)

        bg_card = QColor(self.track_bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_card)
        painter.drawRect(self.rect())

        # Shaded A/B Loop zone on waveform bar
        if self.loop_a is not None and self.duration_ms > 0:
            xa = max(0.0, min(w, (self.loop_a / self.duration_ms) * w))
            xb = max(0.0, min(w, (self.loop_b / self.duration_ms) * w)) if self.loop_b is not None else xa
            left_x = min(xa, xb)
            right_x = max(xa, xb)

            if right_x > left_x:
                loop_c = QColor(0, 240, 255, 55)
                painter.setBrush(loop_c)
                painter.drawRect(QRectF(left_x, 0, right_x - left_x, h))

            painter.setPen(QPen(QColor(0, 240, 255, 230), 1.5))
            painter.drawLine(int(xa), 0, int(xa), h)
            if self.loop_b is not None:
                painter.setPen(QPen(QColor(255, 0, 127, 230), 1.5))
                painter.drawLine(int(xb), 0, int(xb), h)

        # ── NEW STYLE: "AURORA RIDGE" ──
        # Smooth mirrored envelope + tapered rounded capsule columns + luminous
        # ridge stroke + beat glints + volumetric pulsing playhead beam.
        num_bars = len(self.waveform_data)
        if num_bars > 0:
            progress_frac = (self.current_pos / self.duration_ms) if self.duration_ms > 0 else 0.0
            playhead_x = max(0.0, min(float(w), progress_frac * w))

            t_now = time.time()
            shimmer = 0.5 + 0.5 * math.sin(t_now * 2.4)
            pulse = 0.5 + 0.5 * math.sin(t_now * 7.5)

            c_a = QColor(self.accent)
            c_b = QColor(self.accent2)

            # Resample to ~1.8 columns per pixel: crisp yet cheap for 1000-pt sources
            step = max(1, int(math.ceil(num_bars / max(1.0, w * 3.4))))

            # ── Layers 1-4 are STATIC: rasterise once per (size, data, theme) ──
            # Drawing ~700 rounded capsules plus two long envelope paths on every
            # 66 ms tick was the dominant repaint cost in the whole app. They are
            # now cached into two pixmaps (unplayed + played); per-frame work is a
            # single blit, a clipped blit, and the animated playhead overlay.
            cache_key = (num_bars, w, h, step, self.accent.rgb(), self.accent2.rgb())
            if self._aurora_key != cache_key:
                peaks = []
                i = 0
                while i < num_bars:
                    hi = min(num_bars, i + step)
                    peaks.append(max(self.waveform_data[i:hi]))
                    i = hi
                if not peaks:
                    peaks = [0.0]
                self._aurora_peaks = peaks
                self._aurora_beats = [ix for ix, pk in enumerate(peaks) if pk > 0.60]
                self._aurora_base = self._build_aurora_pixmap(w, h, peaks, played=False)
                self._aurora_live = self._build_aurora_pixmap(w, h, peaks, played=True)
                self._aurora_key = cache_key

            peaks = self._aurora_peaks
            n = len(peaks)
            col_w = w / float(n)

            painter.save()
            painth = QPainter.RenderHint
            painter.setRenderHint(painth.Antialiasing, False)
            if self._aurora_base is not None:
                painter.drawPixmap(0, 0, self._aurora_base)
            if playhead_x > 0.5 and self._aurora_live is not None:
                painter.save()
                painter.setClipRect(QRectF(0, 0, playhead_x, float(h)),
                                    Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(0, 0, self._aurora_live)
                painter.restore()
            painter.restore()

            # ── Live beat glints (cheap: loudest columns only, capped) ──
            painter.setPen(Qt.PenStyle.NoPen)
            for ix in self._aurora_beats[:220]:
                x = ix * col_w + col_w * 0.5
                amp = max(0.9, (min(1.0, max(0.0, peaks[ix])) ** 0.78) * max_amp_h)
                painter.setBrush(QColor(255, 255, 255, int(
                    120 + 110 * (0.5 + 0.5 * math.sin(t_now * 5.0 + ix * 0.7)))))
                painter.drawEllipse(QPointF(x, mid_y - amp - 1.6), 1.15, 1.15)

            # ── Layer 5: volumetric pulsing playhead beam + halo ──
            beam = QLinearGradient(playhead_x - 7.0, 0.0, playhead_x + 7.0, 0.0)
            beam.setColorAt(0.0, QColor(255, 255, 255, 0))
            beam.setColorAt(0.5, QColor(255, 255, 255, 155))
            beam.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(beam)
            painter.drawRect(QRectF(playhead_x - 7.0, 0.0, 14.0, float(h)))

            painter.setPen(QPen(QColor('#ffffff'), 1.6))
            painter.drawLine(QPointF(playhead_x, 0.0), QPointF(playhead_x, float(h)))

            halo_r = 4.0 + pulse * 3.0
            halo = QRadialGradient(playhead_x, mid_y, halo_r * 2.2)
            halo.setColorAt(0.0, QColor(255, 255, 255, 215))
            halo.setColorAt(0.40, QColor(c_b.red(), c_b.green(), c_b.blue(), 155))
            halo.setColorAt(1.0, QColor(c_b.red(), c_b.green(), c_b.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(QPointF(playhead_x, mid_y), halo_r * 2.2, halo_r * 2.2)

            painter.setBrush(QColor('#ffffff'))
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            painter.drawEllipse(QPointF(playhead_x, mid_y), 2.6, 2.6)
        else:
            font = QFont('Segoe UI', 8)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 60))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "AUDIO WAVEFORM OVERVIEW")

        # Hover guide crosshair
        if self.hover_x is not None and not self.is_dragging:
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(self.hover_x), 0, int(self.hover_x), h)


    def _build_aurora_pixmap(self, w, h, peaks, played):
        """
        Rasterise the static Aurora Ridge layers (envelope fill + tapered capsules
        + luminous ridge) into a pixmap. Built twice — once for the dim unplayed
        state, once for the live played state — so each paint is a cheap blit.
        """
        dpr = self.devicePixelRatioF() or 1.0
        pix = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        if w <= 0 or h <= 0 or not peaks:
            return pix

        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        mid_y = h / 2.0
        max_amp_h = (h - 6) / 2.0
        c_a, c_b = self.accent, self.accent2
        n = len(peaks)
        col_w = w / float(n)

        # Curve shaping: compress quiet detail, dramatize loud transients
        amps = [max(0.9, (min(1.0, max(0.0, pk)) ** 0.78) * max_amp_h) for pk in peaks]
        xs = [i * col_w + col_w * 0.5 for i in range(n)]

        top = [QPointF(xs[i], mid_y - amps[i]) for i in range(n)]
        bot = [QPointF(xs[i], mid_y + amps[i]) for i in range(n)]

        # ── Layer 1: soft aurora envelope fill (ghost backdrop) ──
        env = QPainterPath()
        env.moveTo(0.0, top[0].y())
        for pt in top[1:]:
            env.lineTo(pt)
        env.lineTo(float(w), top[-1].y())
        env.lineTo(float(w), bot[-1].y())
        for pt in reversed(bot[:-1]):
            env.lineTo(pt)
        env.lineTo(0.0, bot[0].y())
        env.closeSubpath()

        if played:
            env_grad = QLinearGradient(0, 0, w, 0)
            env_grad.setColorAt(0.0, QColor(c_a.red(), c_a.green(), c_a.blue(), 84))
            env_grad.setColorAt(1.0, QColor(c_b.red(), c_b.green(), c_b.blue(), 168))
        else:
            env_grad = QLinearGradient(0, 0, 0, h)
            env_grad.setColorAt(0.0, QColor(c_a.red(), c_a.green(), c_a.blue(), 26))
            env_grad.setColorAt(0.5, QColor(c_b.red(), c_b.green(), c_b.blue(), 52))
            env_grad.setColorAt(1.0, QColor(c_a.red(), c_a.green(), c_a.blue(), 26))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(env_grad)
        p.drawPath(env)

        # ── Layer 3: tapered rounded capsule columns (crisp foreground) ──
        cap_w = max(1.05, col_w * 0.62)
        radius = cap_w / 2.0
        rects_hot = []
        rects_cold = []
        for i in range(n):
            r = QRectF(xs[i] - cap_w / 2.0, mid_y - amps[i], cap_w, amps[i] * 2.0)
            (rects_hot if peaks[i] > 0.60 else rects_cold).append(r)

        if played:
            hot = QColor(c_b.red(), c_b.green(), c_b.blue(), 250)
            cold_c = QColor(c_a.red(), c_a.green(), c_a.blue(), 210)
        else:
            hot = QColor(255, 255, 255, 165)
            cold_c = QColor(255, 255, 255, 58)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cold_c)
        for r in rects_cold:
            p.drawRoundedRect(r, radius, radius)
        if played:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(c_a.red(), c_a.green(), c_a.blue(), 235))
            grad.setColorAt(1.0, QColor(c_b.red(), c_b.green(), c_b.blue(), 255))
            p.setBrush(grad)
        else:
            p.setBrush(hot)
        for r in rects_hot:
            p.drawRoundedRect(r, radius, radius)

        # ── Layer 4: luminous ridge stroke riding the top envelope ──
        ridge = QPainterPath()
        ridge.moveTo(0.0, top[0].y())
        for pt in top[1:]:
            ridge.lineTo(pt)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if played:
            p.setPen(QPen(QColor(255, 255, 255, 150), 1.0))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
        p.drawPath(ridge)

        p.end()
        return pix



# ─────────────────────────────────────────────────────────────────────────────
# ANIMATED NEON SLIDER (remix rack)
# ─────────────────────────────────────────────────────────────────────────────

class NeonSlider(QSlider):
    """
    Self-painted horizontal slider with eased motion.

    QSS can style a QSlider but cannot animate it, and a 6 px handle inside a
    14 px widget is impossible to grab — which is why the rack sliders felt
    broken. This paints its own groove / fill / knob and animates:
      * hover  -> groove thickens, glow ramps in (OutCubic, 170 ms)
      * change -> an expanding halo "kick" decays over 420 ms
      * drag   -> halo stays lit after the pointer leaves the widget
    It only repaints while one of those animations is running.
    """

    def __init__(self, lo=0, hi=100, val=0, c1='#00f0ff', c2='#ff007f', parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(lo, hi)
        self.setValue(val)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._c1 = QColor(c1)
        self._c2 = QColor(c2)
        self._glow = 0.0
        self._kick = 0.0

        self._glow_anim = QVariantAnimation(self)
        self._glow_anim.setDuration(170)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._glow_anim.valueChanged.connect(self._set_glow)

        self._kick_anim = QVariantAnimation(self)
        self._kick_anim.setDuration(420)
        self._kick_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._kick_anim.valueChanged.connect(self._set_kick)
        self.valueChanged.connect(self._pulse)

    def _set_glow(self, v):
        self._glow = float(v)
        self.update()

    def _set_kick(self, v):
        self._kick = float(v)
        self.update()

    def _pulse(self, *_):
        self._kick_anim.stop()
        self._kick_anim.setStartValue(1.0)
        self._kick_anim.setEndValue(0.0)
        self._kick_anim.start()

    def _animate_glow(self, target):
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow)
        self._glow_anim.setEndValue(float(target))
        self._glow_anim.start()

    def enterEvent(self, e):
        self._animate_glow(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_glow(0.30 if self.isSliderDown() else 0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self._pulse()
        self._animate_glow(1.0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        cy = h / 2.0
        margin = 7.0
        groove_h = 5.0 + 1.6 * self._glow
        rad = groove_h / 2.0
        x0, x1 = margin, w - margin
        span = max(1.0, x1 - x0)
        rng = max(1, self.maximum() - self.minimum())
        frac = (self.value() - self.minimum()) / float(rng)
        frac = max(0.0, min(1.0, frac))
        xv = x0 + span * frac

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 24))
        p.drawRoundedRect(QRectF(x0, cy - groove_h / 2, span, groove_h), rad, rad)

        if xv - x0 > 0.5:
            g = QLinearGradient(x0, 0, max(xv, x0 + 1.0), 0)
            g.setColorAt(0.0, QColor(self._c1.red(), self._c1.green(), self._c1.blue(), 205))
            g.setColorAt(1.0, QColor(self._c2.red(), self._c2.green(), self._c2.blue(), 235))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(x0, cy - groove_h / 2, max(2.0, xv - x0), groove_h), rad, rad)

        knob_r = 5.4 + 1.3 * self._glow
        halo = 8.5 + 7.0 * self._glow + 10.0 * self._kick
        if halo > knob_r + 0.5:
            hg = QRadialGradient(QPointF(xv, cy), halo)
            a = int(55 + 70 * self._glow + 130 * self._kick)
            hg.setColorAt(0.0, QColor(self._c1.red(), self._c1.green(), self._c1.blue(),
                                     max(0, min(255, a))))
            hg.setColorAt(1.0, QColor(self._c2.red(), self._c2.green(), self._c2.blue(), 0))
            p.setBrush(hg)
            p.drawEllipse(QPointF(xv, cy), halo, halo)

        p.setBrush(QColor('#ffffff'))
        p.setPen(QPen(QColor(self._c1.red(), self._c1.green(), self._c1.blue(), 210), 1.4))
        p.drawEllipse(QPointF(xv, cy), knob_r, knob_r)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# STICKY COMBO BOX — list stays open so several options can be tried in a row
# ─────────────────────────────────────────────────────────────────────────────

class StickyComboBox(QComboBox):
    """
    A dropdown that does NOT collapse the moment you pick an item.

    Picking inside the list re-opens it on the next event-loop turn, so you can
    run through themes / visualizer modes while watching the result. Clicking
    outside the list (or pressing Escape) closes it and emits popupClosed, which
    is when expensive restyling is applied.
    """

    popupClosed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close = False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._allow_close = True
        super().keyPressEvent(event)

    def hidePopup(self):
        if not self._allow_close:
            try:
                vp = self.view().window()
                if vp.isVisible() and vp.geometry().contains(QCursor.pos()):
                    # The click landed inside the list -> it was a selection.
                    QTimer.singleShot(0, self._reopen)
                    return
            except Exception:
                pass
        self._allow_close = False
        super().hidePopup()
        self.popupClosed.emit()

    def _reopen(self):
        try:
            if self.isVisible():
                self.showPopup()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# VERTICAL BATTERY-STYLE VOLUME GAUGE WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class BatteryVolumeWidget(QWidget):
    """
    Vertical Glowing Cyberpunk Battery-Style Volume Slider with segmented plasma levels,
    multi-layer undulating liquid waves, rising energy bubbles, charging shimmer sweep,
    interactive fluid slosh spring physics, anode spark corona, and hover feedback.
    Supports selectable animation styles via right-click catalogue.
    """
    volumeChanged = pyqtSignal(int)
    muteToggled = pyqtSignal()

    # ── Animation Style Catalogue ──
    ANIM_STYLES = [
        ('plasma',     '🔮 Plasma Liquid',     'Rising bubbles, waves & shimmer sweep'),
        ('lava',       '🌋 Lava Lamp',         'Slow, smooth lava blobs rising'),
        ('matrix',     '💚 Matrix Rain',        'Green digit rain falling through fill'),
        ('heartbeat',  '💓 Heartbeat Pulse',    'Rhythmic cardiac pulse wave'),
        ('lightning',  '⚡ Lightning Storm',    'Random electric arcs across fill'),
        ('aurora',     '🌌 Aurora Borealis',    'Shimmering curtain of Northern Lights'),
        ('fire',       '🔥 Fire Blaze',         'Flickering flame tongues rising'),
        ('neon',       '🕹 Neon Grid Pulse',    'Scanlines + travelling electric pulse'),
        ('rainbow',    '🌈 Rainbow Ripple',     'Hue-cycling fill with concentric ripples'),
        ('nebula',     '✨ Nebula Vortex',      'Orbiting star motes in a swirl'),
        ('sonic',      '🔊 Sonic Boom',         'Expanding shockwave rings from the surface'),
        ('none',       '⬜ Static (no anim)',   'Clean static fill, no animation'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(44)
        self.setMaximumWidth(140)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self.volume = 70
        self.muted = False
        self.is_dragging = False
        self.is_hovered = False
        self.anim_style = 'plasma'  # default animation style

        self.track_bg = '#161c2b'
        self.accent = QColor('#00f0ff')
        self.accent2 = QColor('#7c3aed')
        self.border_color = QColor('rgba(0, 240, 255, 0.3)')

        # Continuous animation parameters
        self.anim_phase = 0.0
        self.sweep_phase = 0.0
        self.splash_offset = 0.0
        self.splash_vel = 0.0

        # Lava lamp blobs
        self.lava_blobs = []
        for _ in range(6):
            self.lava_blobs.append({
                'x': random.uniform(0.2, 0.8), 'y': random.uniform(0.1, 0.9),
                'r': random.uniform(4, 10), 'vx': random.uniform(-0.003, 0.003),
                'vy': random.uniform(-0.008, -0.003), 'phase': random.uniform(0, 6.28)
            })

        # Matrix rain columns
        self.matrix_drops = []
        for i in range(8):
            self.matrix_drops.append({
                'x_pct': (i + 0.5) / 8.0, 'y_pct': random.uniform(-0.5, 1.0),
                'speed': random.uniform(0.02, 0.05), 'char': chr(random.randint(0x30A0, 0x30FF)),
                'brightness': random.randint(150, 255)
            })

        # Heartbeat state
        self.hb_phase = 0.0

        # Lightning arcs
        self.lightning_arcs = []
        self.lightning_cooldown = 0

        # Aurora bands
        self.aurora_offset = 0.0

        # Fire particles
        self.fire_particles = []
        for _ in range(20):
            self.fire_particles.append({
                'x': random.uniform(0.1, 0.9), 'y': random.uniform(0.0, 0.3),
                'vx': random.uniform(-0.01, 0.01), 'vy': random.uniform(-0.02, -0.008),
                'life': random.uniform(0.3, 1.0), 'size': random.uniform(1.5, 3.5)
            })

        # Micro energy particles / bubbles rising through liquid
        self.bubbles = []
        for _ in range(16):
            self.bubbles.append({
                'x_pct': random.uniform(0.15, 0.85),
                'y_pct': random.uniform(0.05, 0.95),
                'speed': random.uniform(0.012, 0.026),
                'size': random.uniform(1.2, 2.8),
                'wobble': random.uniform(0.0, 6.28),
                'alpha': random.randint(110, 220)
            })

        # ── Neon Grid Pulse state ──
        self.neon_scan = 0.0            # travelling scanline position 0..1
        self.neon_grid_phase = 0.0
        self.neon_nodes = [
            {'x': random.uniform(0.1, 0.9), 'y': random.uniform(0.05, 0.95),
             'phase': random.uniform(0, 6.283), 'rate': random.uniform(1.4, 3.4)}
            for _ in range(9)
        ]

        # ── Rainbow Ripple state ──
        self.rainbow_hue = 0.0
        self.ripple_rings = []          # [{'t': 0..1, 'seed': int}]

        # ── Nebula Vortex state ──
        self.nebula_spin = 0.0
        self.nebula_motes = [
            {'r': random.uniform(0.15, 1.0), 'a': random.uniform(0, 6.283),
             'speed': random.uniform(0.018, 0.055), 'size': random.uniform(0.8, 2.4),
             'hue_off': random.randint(-40, 60)}
            for _ in range(28)
        ]

        # ── Sonic Boom state ──
        self.sonic_rings = []           # [{'t': 0..1, 'power': 0..1}]
        self.sonic_cooldown = 0

        # ── Universal motion state (all styles) ──
        self.aura_phase = 0.0           # outer aura rotation / breathing
        self.shock_burst = 0.0          # volume-change shockwave 0..1
        self.hover_lift = 0.0           # smoothed hover intensity 0..1
        self.beam_pos = 0.0             # border light sweep position 0..1

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start(24)  # ~42 FPS — smooth motion, small widget, cheap repaint

    def _on_anim_tick(self):
        # ── Universal motion layer (applies to EVERY style, incl. static) ──
        # Keeps the gauge alive: aura breathing, hover lift, shock bursts and a
        # travelling border light sweep.
        self.aura_phase = (self.aura_phase + 0.038) % (2.0 * math.pi)
        self.beam_pos = (self.beam_pos + 0.011) % 1.0
        tgt_lift = 1.0 if self.is_hovered else 0.0
        self.hover_lift += (tgt_lift - self.hover_lift) * 0.18
        if self.shock_burst > 0.0:
            self.shock_burst = max(0.0, self.shock_burst - 0.030)

        if self.anim_style == 'none':
            self.update()
            return

        self.anim_phase += 0.055
        if self.anim_phase > 2.0 * math.pi:
            self.anim_phase -= 2.0 * math.pi

        self.sweep_phase = (self.sweep_phase + 0.016) % 1.0

        # Fluid slosh spring dampening (all styles)
        if abs(self.splash_vel) > 0.01 or abs(self.splash_offset) > 0.01:
            self.splash_offset += self.splash_vel
            self.splash_vel -= self.splash_offset * 0.20
            self.splash_vel *= 0.86
        else:
            self.splash_offset = 0.0
            self.splash_vel = 0.0

        # Style-specific tick updates
        if self.anim_style == 'plasma':
            for p in self.bubbles:
                p['y_pct'] -= p['speed']
                if p['y_pct'] <= 0.0:
                    p['y_pct'] = 1.0
                    p['x_pct'] = random.uniform(0.15, 0.85)
                    p['speed'] = random.uniform(0.012, 0.026)
                    p['size'] = random.uniform(1.2, 2.8)
        elif self.anim_style == 'lava':
            for b in self.lava_blobs:
                b['y'] += b['vy']
                b['x'] += b['vx']
                b['r'] = max(3, min(12, b['r'] + math.sin(self.anim_phase + b['phase']) * 0.15))
                if b['y'] < -0.1:
                    b['y'] = 1.1
                    b['x'] = random.uniform(0.2, 0.8)
                    b['vy'] = random.uniform(-0.008, -0.003)
                b['x'] = max(0.1, min(0.9, b['x']))
        elif self.anim_style == 'matrix':
            for d in self.matrix_drops:
                d['y_pct'] += d['speed']
                if d['y_pct'] > 1.2:
                    d['y_pct'] = random.uniform(-0.5, -0.1)
                    d['speed'] = random.uniform(0.02, 0.05)
                    d['char'] = chr(random.randint(0x30A0, 0x30FF))
                    d['brightness'] = random.randint(150, 255)
        elif self.anim_style == 'heartbeat':
            self.hb_phase = (self.hb_phase + 0.08) % (2.0 * math.pi)
        elif self.anim_style == 'lightning':
            self.lightning_cooldown = max(0, self.lightning_cooldown - 1)
            if self.lightning_cooldown == 0 and random.random() < 0.06:
                # Spawn a lightning arc
                arc_pts = []
                y_start = random.uniform(0.1, 0.5)
                x = random.uniform(0.2, 0.8)
                for _ in range(random.randint(3, 6)):
                    arc_pts.append((x, y_start))
                    x += random.uniform(-0.15, 0.15)
                    y_start += random.uniform(0.05, 0.15)
                self.lightning_arcs = [{'pts': arc_pts, 'life': 6, 'alpha': 255}]
                self.lightning_cooldown = random.randint(8, 20)
            new_arcs = []
            for arc in self.lightning_arcs:
                arc['life'] -= 1
                arc['alpha'] = max(0, arc['alpha'] - 40)
                if arc['life'] > 0:
                    new_arcs.append(arc)
            self.lightning_arcs = new_arcs
        elif self.anim_style == 'aurora':
            self.aurora_offset += 0.02
        elif self.anim_style == 'fire':
            for fp in self.fire_particles:
                fp['y'] += fp['vy']
                fp['x'] += fp['vx']
                fp['life'] -= 0.02
                if fp['life'] <= 0 or fp['y'] < -0.1:
                    fp['x'] = random.uniform(0.1, 0.9)
                    fp['y'] = random.uniform(0.7, 1.0)
                    fp['vx'] = random.uniform(-0.01, 0.01)
                    fp['vy'] = random.uniform(-0.02, -0.008)
                    fp['life'] = random.uniform(0.5, 1.0)
                    fp['size'] = random.uniform(1.5, 3.5)
        elif self.anim_style == 'neon':
            self.neon_scan = (self.neon_scan + 0.013) % 1.0
            self.neon_grid_phase = (self.neon_grid_phase + 0.05) % (2.0 * math.pi)
            for nd in self.neon_nodes:
                nd['phase'] = (nd['phase'] + 0.02 * nd['rate']) % (2.0 * math.pi)
        elif self.anim_style == 'rainbow':
            self.rainbow_hue = (self.rainbow_hue + 2.4) % 360.0
            for r in self.ripple_rings:
                r['t'] += 0.022
            self.ripple_rings = [r for r in self.ripple_rings if r['t'] < 1.0]
            if len(self.ripple_rings) < 3 and random.random() < 0.05:
                self.ripple_rings.append({'t': 0.0, 'seed': random.randint(0, 999)})
        elif self.anim_style == 'nebula':
            self.nebula_spin = (self.nebula_spin + 0.03) % (2.0 * math.pi)
            for m in self.nebula_motes:
                m['a'] += m['speed']
                m['r'] -= 0.0022
                if m['r'] <= 0.06:
                    m['r'] = random.uniform(0.75, 1.05)
                    m['a'] = random.uniform(0, 6.283)
        elif self.anim_style == 'sonic':
            for ring in self.sonic_rings:
                ring['t'] += 0.045
            self.sonic_rings = [r for r in self.sonic_rings if r['t'] < 1.0]
            self.sonic_cooldown = max(0, self.sonic_cooldown - 1)
            if self.sonic_cooldown == 0 and random.random() < 0.14:
                self.sonic_rings.append({'t': 0.0, 'power': random.uniform(0.45, 1.0)})
                self.sonic_cooldown = random.randint(4, 14)

        self.update()

    def set_theme_colors(self, track_bg, accent_hex, accent2_hex, border_hex):
        self.track_bg = track_bg
        self.accent = QColor(accent_hex)
        self.accent2 = QColor(accent2_hex)
        self.border_color = QColor(border_hex)
        self.update()

    def set_volume(self, val):
        old_vol = self.volume
        self.volume = max(0, min(100, int(val)))
        diff = self.volume - old_vol
        if abs(diff) > 0:
            # Trigger fluid slosh splash + a shockwave burst on the chamber
            self.splash_vel += max(-9.0, min(9.0, diff * 0.35))
            self.shock_burst = min(1.0, self.shock_burst + 0.12 + abs(diff) * 0.05)
        self.update()

    def set_muted(self, muted):
        self.muted = muted
        self.update()

    def set_anim_style(self, style_key):
        """Switch battery animation style by key."""
        valid_keys = [s[0] for s in self.ANIM_STYLES]
        if style_key in valid_keys:
            self.anim_style = style_key
            self.update()

    def contextMenuEvent(self, event):
        """Right-click catalogue to select battery animation style."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1a1e2e; color: #e0e0e0; border: 1px solid #333; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 18px; border-radius: 4px; }
            QMenu::item:selected { background: #2d3250; }
            QMenu::item:checked { color: #00f0ff; font-weight: bold; }
            QMenu::separator { height: 1px; background: #333; margin: 4px 8px; }
        """)
        menu.addAction("⚡ Battery Animation Style").setEnabled(False)
        menu.addSeparator()
        for key, label, tooltip in self.ANIM_STYLES:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.anim_style == key)
            act.setToolTip(tooltip)
            act.triggered.connect(lambda checked, k=key: self._on_anim_style_selected(k))
        menu.exec(event.globalPos())

    def _on_anim_style_selected(self, key):
        self.set_anim_style(key)
        # Bubble up to main window to persist setting
        p = self.parent()
        while p:
            if hasattr(p, '_schedule_save_settings'):
                p._schedule_save_settings()
                break
            p = p.parent()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() >= self.height() - 28:
                self.muteToggled.emit()
            else:
                self.is_dragging = True
                self._update_val_from_y(event.position().y())
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._update_val_from_y(event.position().y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = 2 if event.angleDelta().y() > 0 else -2
        new_vol = max(0, min(100, self.volume + delta))
        self.set_volume(new_vol)
        self.volumeChanged.emit(new_vol)
        event.accept()

    def _update_val_from_y(self, y):
        body_top = 22
        body_bottom = self.height() - 34
        body_h = max(1, body_bottom - body_top)

        clamped_y = max(body_top, min(body_bottom, y))
        frac = 1.0 - ((clamped_y - body_top) / body_h)
        new_vol = int(round(frac * 100))
        self.set_volume(new_vol)
        self.volumeChanged.emit(new_vol)

    # ─────────────────────────────────────────────────────────────────────
    # BATTERY ANIMATION EFFECTS (called by paintEvent per-style)
    # ─────────────────────────────────────────────────────────────────────

    def _paint_battery_effects(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, fill_pct, breath):
        style = self.anim_style
        if style == 'none':
            return

        if style == 'plasma':
            self._paint_plasma(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'lava':
            self._paint_lava(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'matrix':
            self._paint_matrix(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'heartbeat':
            self._paint_heartbeat(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'lightning':
            self._paint_lightning(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'aurora':
            self._paint_aurora(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'fire':
            self._paint_fire(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'neon':
            self._paint_neon(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'rainbow':
            self._paint_rainbow(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'nebula':
            self._paint_nebula(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)
        elif style == 'sonic':
            self._paint_sonic(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath)

    # ── NEW ANIMATION STYLES ────────────────────────────────────────────────

    def _paint_neon(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Neon Grid Pulse: animated scanlines, a travelling electric pulse and glowing nodes."""
        if fill_h <= 1:
            return
        right = body_x + body_w - 2
        left = body_x + 2

        # 1. Horizontal neon scanlines rippling through the liquid
        lines = max(4, int(fill_h / 7.0))
        for i in range(lines):
            fy = fill_y + (i + 0.5) / lines * fill_h
            wob = math.sin(self.neon_grid_phase + i * 0.55) * 1.6
            a = int(38 + 46 * (0.5 + 0.5 * math.sin(self.neon_scan * 6.283 + i * 0.7)))
            painter.setPen(QPen(QColor(120, 255, 255, a), 1.0))
            painter.drawLine(QPointF(left, fy + wob), QPointF(right, fy + wob))

        # 2. Travelling bright pulse sweeping downward
        py = fill_y + (1.0 - self.neon_scan) * fill_h
        beam = QLinearGradient(0, py - 7, 0, py + 7)
        beam.setColorAt(0.0, QColor(180, 255, 255, 0))
        beam.setColorAt(0.5, QColor(200, 255, 255, int(120 + 90 * breath)))
        beam.setColorAt(1.0, QColor(180, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(beam)
        painter.drawRect(QRectF(left, py - 7, right - left, 14.0))

        # 3. Pulsing neon nodes
        for nd in self.neon_nodes:
            ny = fill_y + nd['y'] * fill_h
            if not (fill_y - 2 <= ny <= body_y + body_h):
                continue
            nx = left + nd['x'] * (right - left)
            glow = 0.5 + 0.5 * math.sin(nd['phase'] * 6.283)
            rad = 1.4 + glow * 1.9
            halo = QRadialGradient(nx, ny, rad * 3.4)
            halo.setColorAt(0.0, QColor(180, 255, 255, int(170 * glow)))
            halo.setColorAt(1.0, QColor(0, 240, 255, 0))
            painter.setBrush(halo)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(nx, ny), rad * 3.4, rad * 3.4)
            painter.setBrush(QColor(235, 255, 255, int(190 + 60 * glow)))
            painter.drawEllipse(QPointF(nx, ny), rad, rad)

    def _paint_rainbow(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Rainbow Ripple: hue-cycled vertical spectrum plus expanding concentric ripples."""
        if fill_h <= 1:
            return
        left = body_x + 2
        right = body_x + body_w - 2
        bottom = body_y + body_h - 2

        # 1. Hue-cycling spectrum wash over the liquid
        spec = QLinearGradient(0, fill_y, 0, bottom)
        for i in range(6):
            stop = i / 5.0
            hue = (self.rainbow_hue + stop * 180.0) % 360.0
            col = QColor.fromHsvF(hue / 360.0, 0.85, 1.0)
            spec.setColorAt(stop, QColor(col.red(), col.green(), col.blue(), 96))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(spec)
        painter.drawRoundedRect(QRectF(left, fill_y, right - left, fill_h), 6, 6)

        # 2. Expanding concentric ripples radiating from the liquid surface
        cx = body_x + body_w * 0.5
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in self.ripple_rings:
            t = min(1.0, ring['t'])
            rad = 3.0 + t * (body_w * 0.95)
            hue = (self.rainbow_hue + ring['seed'] * 0.37) % 360.0
            col = QColor.fromHsvF(hue / 360.0, 0.75, 1.0)
            col.setAlpha(int(200 * (1.0 - t)))
            painter.setPen(QPen(col, 1.6 * (1.0 - t) + 0.5))
            cy = fill_y + (0.25 + 0.5 * ((ring['seed'] % 7) / 7.0)) * max(1.0, fill_h)
            painter.drawEllipse(QPointF(cx, cy), rad * 0.42, rad * 0.30)

        # 3. Bright hue-shifted surface line
        surf = QColor.fromHsvF(((self.rainbow_hue + 40.0) % 360.0) / 360.0, 0.55, 1.0)
        surf.setAlpha(int(150 + 100 * breath))
        painter.setPen(QPen(surf, 1.6))
        painter.drawLine(QPointF(left, fill_y), QPointF(right, fill_y))

    def _paint_nebula(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Nebula Vortex: orbital star motes spiralling into a swirling core."""
        if fill_h <= 1:
            return
        cx = body_x + body_w * 0.5
        cy = fill_y + fill_h * 0.42
        max_r = min(body_w * 0.62, fill_h * 0.72) + 2.0

        # 1. Swirling arm nebulosity
        for arm in range(3):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            span = 26
            prev = None
            for k in range(span + 1):
                f = k / float(span)
                ang = self.nebula_spin + arm * (2.094) + f * 3.1
                r = max_r * (0.18 + f * 0.86)
                px = cx + math.cos(ang) * r * 0.62
                py = cy + math.sin(ang) * r * 0.52
                if prev is None:
                    prev = (px, py)
                    continue
                a = int(70 * (1.0 - f) + 12 + 28 * breath)
                painter.setPen(QPen(QColor(190, 150, 255, a), 2.2 * (1.0 - f) + 0.6))
                painter.drawLine(QPointF(prev[0], prev[1]), QPointF(px, py))
                prev = (px, py)

        # 2. Star motes
        painter.setPen(Qt.PenStyle.NoPen)
        for m in self.nebula_motes:
            ang = m['a'] + self.nebula_spin * 0.55
            r = m['r'] * max_r
            px = cx + math.cos(ang) * r * 0.68
            py = cy + math.sin(ang) * r * 0.55
            if not (fill_y - 3 <= py <= body_y + body_h + 3):
                continue
            twinkle = 0.5 + 0.5 * math.sin(m['a'] * 3.1)
            col = QColor.fromHsvF(((275 + m['hue_off']) % 360) / 360.0, 0.42, 1.0)
            col.setAlpha(int(120 + 130 * twinkle))
            painter.setBrush(col)
            painter.drawEllipse(QPointF(px, py), m['size'], m['size'])

        # 3. Hot core
        core_r = 4.0 + 2.6 * breath
        core = QRadialGradient(cx, cy, core_r * 3.0)
        core.setColorAt(0.0, QColor(255, 255, 255, int(190 + 60 * breath)))
        core.setColorAt(0.35, QColor(200, 160, 255, 130))
        core.setColorAt(1.0, QColor(124, 58, 237, 0))
        painter.setBrush(core)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r * 3.0, core_r * 3.0)

    def _paint_sonic(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Sonic Boom: expanding elliptical shockwave rings bursting from the surface."""
        if fill_h <= 1:
            return
        cx = body_x + body_w * 0.5
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for ring in self.sonic_rings:
            t = min(1.0, ring['t'])
            fade = (1.0 - t) ** 1.5
            rad_x = (2.0 + t * body_w * 1.35) * (0.7 + 0.3 * ring['power'])
            rad_y = rad_x * (0.55 + 0.25 * ring['power'])
            cy = fill_y + fill_h * (0.18 + 0.22 * ring['power'])
            col = QColor(120, 235, 255, int(210 * fade))
            painter.setPen(QPen(col, 2.4 * fade + 0.4))
            painter.drawEllipse(QPointF(cx, cy), rad_x, rad_y)
            col2 = QColor(255, 255, 255, int(120 * fade))
            painter.setPen(QPen(col2, 1.0 * fade + 0.3))
            painter.drawEllipse(QPointF(cx, cy), rad_x * 0.80, rad_y * 0.80)

        # Booming surface crest
        crest = QLinearGradient(0, fill_y - 9, 0, fill_y + 3)
        crest.setColorAt(0.0, QColor(190, 250, 255, 0))
        crest.setColorAt(0.5, QColor(210, 250, 255, int(90 + 130 * breath)))
        crest.setColorAt(1.0, QColor(190, 250, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(crest)
        painter.drawRect(QRectF(body_x + 2, fill_y - 9, body_w - 4, 12.0))

        # Periodic vertical concussive beams
        for i in range(3):
            ph = (self.anim_phase * 0.7 + i * 2.094) % 6.283
            intensity = max(0.0, math.sin(ph)) ** 3
            if intensity <= 0.02:
                continue
            bx = body_x + 6 + ((i * 0.37 + 0.18) % 0.7) * (body_w - 12)
            beam = QLinearGradient(0, fill_y, 0, body_y + body_h)
            beam.setColorAt(0.0, QColor(255, 255, 255, int(120 * intensity)))
            beam.setColorAt(1.0, QColor(120, 235, 255, 0))
            painter.setBrush(beam)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(bx - 1.6, fill_y, 3.2, fill_h * 0.85))


    def _paint_plasma(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Original plasma: rising bubbles, shimmer beam, dual waves, overcharge sparks."""
        # 1. Rising Plasma Energy Bubbles
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.bubbles:
            by = fill_y + p['y_pct'] * fill_h
            if fill_y <= by <= (body_y + body_h - 2):
                bx = body_x + 3 + p['x_pct'] * (body_w - 6) + math.sin(self.anim_phase * 2.2 + p['wobble']) * 2.0
                b_rad = p['size']
                b_color = QColor(255, 255, 255, min(240, int(p['alpha'] * (0.6 + 0.4 * breath))))
                painter.setBrush(b_color)
                painter.drawEllipse(QPointF(bx, by), b_rad, b_rad)

        # 2. Vertical Charging Shimmer Light Beam
        beam_y = fill_y + fill_h * (1.0 - self.sweep_phase)
        if fill_y <= beam_y <= (body_y + body_h - 2):
            shimmer = QLinearGradient(0, beam_y - 7, 0, beam_y + 7)
            shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
            shimmer.setColorAt(0.5, QColor(255, 255, 255, int(75 + breath * 65)))
            shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(shimmer)
            painter.drawRect(QRectF(body_x + 2, beam_y - 7, body_w - 4, 14))

        # 3. Dual-Phase Undulating Surface Waves with Spring Slosh
        num_w_pts = 12
        wave_path2 = QPainterPath()
        wave_path2.moveTo(body_x + 2, fill_y)
        for wi in range(num_w_pts + 1):
            wx = body_x + 2 + (wi / float(num_w_pts)) * (body_w - 4)
            w_disp2 = math.cos(-self.anim_phase * 1.8 + (wi / float(num_w_pts)) * 3.14 * 2.0) * (1.8 * breath) + self.splash_offset * 0.6
            wave_path2.lineTo(wx, max(body_y + 2, fill_y + w_disp2))
        painter.setPen(QPen(QColor(255, 255, 255, int(90 + breath * 40)), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(wave_path2)

        wave_path = QPainterPath()
        wave_path.moveTo(body_x + 2, fill_y)
        for wi in range(num_w_pts + 1):
            wx = body_x + 2 + (wi / float(num_w_pts)) * (body_w - 4)
            w_disp = math.sin(self.anim_phase * 2.4 + (wi / float(num_w_pts)) * 3.14 * 2.0) * (2.4 * breath) + self.splash_offset
            wave_path.lineTo(wx, max(body_y + 2, fill_y + w_disp))
        painter.setPen(QPen(QColor(255, 255, 255, int(195 + breath * 60)), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(wave_path)

        # 4. High-Charge Overcharge Spark Effect (>80% Volume)
        if self.volume > 80:
            spark_x = body_x + 4 + (math.sin(self.anim_phase * 6.0) * 0.5 + 0.5) * (body_w - 8)
            spark_y = fill_y + math.sin(self.anim_phase * 8.0) * 2.0
            painter.setPen(QPen(QColor(255, 255, 200, int(160 + breath * 90)), 1.5))
            painter.drawLine(int(spark_x - 3), int(spark_y), int(spark_x + 3), int(spark_y))
            painter.drawLine(int(spark_x), int(spark_y - 3), int(spark_x), int(spark_y + 3))

    def _paint_lava(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Slow floating lava blobs with glow."""
        painter.setPen(Qt.PenStyle.NoPen)
        for b in self.lava_blobs:
            bx = body_x + 2 + b['x'] * (body_w - 4)
            by = fill_y + b['y'] * fill_h
            if fill_y <= by <= (body_y + body_h - 2):
                r = b['r'] + math.sin(self.anim_phase + b['phase']) * 2
                # Outer glow
                glow = QRadialGradient(bx, by, r * 2.2)
                glow.setColorAt(0.0, QColor(255, 80, 20, int(120 * breath)))
                glow.setColorAt(0.5, QColor(255, 160, 0, int(60 * breath)))
                glow.setColorAt(1.0, QColor(255, 100, 0, 0))
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(bx, by), r * 2.2, r * 2.2)
                # Inner core
                core = QRadialGradient(bx, by, r)
                core.setColorAt(0.0, QColor(255, 220, 100, 220))
                core.setColorAt(0.6, QColor(255, 120, 30, 180))
                core.setColorAt(1.0, QColor(200, 60, 0, 80))
                painter.setBrush(core)
                painter.drawEllipse(QPointF(bx, by), r, r * 0.85)
        # Surface heat shimmer
        wave = QPainterPath()
        wave.moveTo(body_x + 2, fill_y)
        for wi in range(13):
            wx = body_x + 2 + (wi / 12.0) * (body_w - 4)
            wd = math.sin(self.anim_phase * 1.5 + wi * 0.7) * 2.5 * breath + self.splash_offset * 0.4
            wave.lineTo(wx, max(body_y + 2, fill_y + wd))
        painter.setPen(QPen(QColor(255, 180, 50, int(130 + breath * 80)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(wave)

    def _paint_matrix(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Cascading green digital rain characters."""
        font = QFont('Consolas', 7)
        font.setBold(True)
        painter.setFont(font)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for d in self.matrix_drops:
            dx = body_x + 3 + d['x_pct'] * (body_w - 6)
            dy = fill_y + d['y_pct'] * fill_h
            if fill_y <= dy <= (body_y + body_h - 2):
                alpha = int(d['brightness'] * (0.5 + 0.5 * breath))
                painter.setPen(QColor(0, 255, 70, min(255, alpha)))
                painter.drawText(QPointF(dx, dy), d['char'])
                # Trail
                for t in range(1, 4):
                    trail_y = dy + t * 8
                    if trail_y <= (body_y + body_h - 2):
                        trail_alpha = max(0, alpha - t * 60)
                        painter.setPen(QColor(0, 200, 50, trail_alpha))
                        painter.drawText(QPointF(dx, trail_y), chr(random.randint(0x30A0, 0x30FF)))
        # Glowing top edge
        painter.setPen(QPen(QColor(0, 255, 100, int(60 + breath * 60)), 1.5))
        painter.drawLine(int(body_x + 4), int(fill_y + 1), int(body_x + body_w - 4), int(fill_y + 1))

    def _paint_heartbeat(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Rhythmic ECG/cardiac pulse with glow pulses."""
        # Pulse brightness
        pulse = abs(math.sin(self.hb_phase * 2.0))
        strong = abs(math.sin(self.hb_phase))
        # Full-fill pulse glow
        if strong > 0.7:
            glow = QColor(255, 50, 80, int(40 * strong))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawRoundedRect(QRectF(body_x + 2, fill_y, body_w - 4, fill_h), 6, 6)
        # ECG wave across the fill
        ecg = QPainterPath()
        mid_y = fill_y + fill_h * 0.5
        ecg.moveTo(body_x + 2, mid_y)
        for i in range(20):
            frac = i / 19.0
            ex = body_x + 2 + frac * (body_w - 4)
            phase = (frac * 4.0 * math.pi + self.hb_phase * 3.0)
            # Sharp QRS-like spike
            spike = 0
            p_mod = phase % (2.0 * math.pi)
            if 1.2 < p_mod < 1.8:
                spike = math.sin((p_mod - 1.2) / 0.6 * math.pi) * 12.0 * pulse
            elif 2.0 < p_mod < 2.3:
                spike = -math.sin((p_mod - 2.0) / 0.3 * math.pi) * 5.0 * pulse
            ey = mid_y - spike
            ey = max(fill_y + 2, min(body_y + body_h - 4, ey))
            ecg.lineTo(ex, ey)
        painter.setPen(QPen(QColor(255, 60, 90, int(180 + pulse * 75)), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(ecg)
        # Heartbeat dot
        dot_x = body_x + body_w * 0.5
        dot_y = mid_y - 8 * pulse
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 80, 100, int(200 * pulse)))
        painter.drawEllipse(QPointF(dot_x, dot_y), 3 + pulse * 2, 3 + pulse * 2)

    def _paint_lightning(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Random electric arcs flickering across the fill."""
        for arc in self.lightning_arcs:
            if len(arc['pts']) < 2:
                continue
            alpha = arc['alpha']
            pen = QPen(QColor(180, 220, 255, alpha), 2.0)
            painter.setPen(pen)
            for i in range(len(arc['pts']) - 1):
                x1 = body_x + 2 + arc['pts'][i][0] * (body_w - 4)
                y1 = fill_y + arc['pts'][i][1] * fill_h
                x2 = body_x + 2 + arc['pts'][i + 1][0] * (body_w - 4)
                y2 = fill_y + arc['pts'][i + 1][1] * fill_h
                if fill_y <= y1 <= (body_y + body_h - 2) and fill_y <= y2 <= (body_y + body_h - 2):
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                    # Glow
                    painter.setPen(QPen(QColor(200, 240, 255, alpha // 3), 5.0))
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                    painter.setPen(pen)
        # Ambient flicker
        if random.random() < 0.15:
            fx = body_x + 4 + random.random() * (body_w - 8)
            fy = fill_y + random.random() * fill_h
            if fill_y <= fy <= (body_y + body_h - 2):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(200, 230, 255, int(60 + breath * 80)))
                painter.drawEllipse(QPointF(fx, fy), 2, 2)

    def _paint_aurora(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Shimmering curtain bands of Northern Lights."""
        painter.setPen(Qt.PenStyle.NoPen)
        colors = [
            QColor(0, 255, 120), QColor(0, 200, 255), QColor(100, 0, 255),
            QColor(255, 0, 200), QColor(0, 255, 200),
        ]
        band_count = 5
        for i in range(band_count):
            color = colors[i % len(colors)]
            y_frac = (i / band_count + self.aurora_offset * (0.5 + i * 0.1)) % 1.0
            band_y = fill_y + y_frac * fill_h
            if fill_y <= band_y <= (body_y + body_h - 8):
                band_h = 6 + math.sin(self.anim_phase + i) * 3
                wave_x_offset = math.sin(self.anim_phase * 1.3 + i * 1.5) * 3
                alpha = int((50 + breath * 60) * (0.5 + 0.5 * math.sin(self.anim_phase * 0.8 + i * 0.9)))
                grad = QLinearGradient(body_x, band_y, body_x + body_w, band_y)
                grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 0))
                grad.setColorAt(0.3, QColor(color.red(), color.green(), color.blue(), alpha))
                grad.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(), alpha))
                grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
                painter.setBrush(grad)
                painter.drawRoundedRect(QRectF(body_x + 3 + wave_x_offset, band_y, body_w - 6, band_h), 3, 3)
        # Subtle surface shimmer
        shimmer_y = fill_y + 1
        painter.setPen(QPen(QColor(150, 255, 200, int(40 + breath * 50)), 1.0))
        painter.drawLine(int(body_x + 4), int(shimmer_y), int(body_x + body_w - 4), int(shimmer_y))

    def _paint_fire(self, painter, body_x, body_y, body_w, body_h, fill_y, fill_h, breath):
        """Flickering flame tongues rising from below."""
        painter.setPen(Qt.PenStyle.NoPen)
        for fp in self.fire_particles:
            fx = body_x + 2 + fp['x'] * (body_w - 4)
            fy = fill_y + fp['y'] * fill_h
            if fill_y <= fy <= (body_y + body_h - 2):
                life = fp['life']
                size = fp['size'] * life
                # Core: bright yellow/white
                core_alpha = int(220 * life)
                painter.setBrush(QColor(255, 220, 80, core_alpha))
                painter.drawEllipse(QPointF(fx, fy), size * 0.6, size)
                # Middle: orange
                painter.setBrush(QColor(255, 120, 20, int(150 * life)))
                painter.drawEllipse(QPointF(fx, fy), size, size * 1.4)
                # Outer glow: red
                painter.setBrush(QColor(200, 30, 0, int(60 * life)))
                painter.drawEllipse(QPointF(fx, fy), size * 1.8, size * 2.2)
        # Flickering base glow
        base_glow = QLinearGradient(0, body_y + body_h - 10, 0, body_y + body_h)
        flicker = 0.6 + 0.4 * math.sin(self.anim_phase * 5.0)
        base_glow.setColorAt(0.0, QColor(255, 100, 0, int(80 * flicker)))
        base_glow.setColorAt(1.0, QColor(255, 50, 0, 0))
        painter.setBrush(base_glow)
        painter.drawRect(QRectF(body_x + 2, body_y + body_h - 10, body_w - 4, 10))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        bg_card = QColor(self.track_bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_card)
        painter.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 10, 10)

        # ── Animated Top Terminal Anode with Corona Glow ──
        breath = 0.5 + 0.5 * math.sin(self.anim_phase)
        term_w, term_h = 20, 7
        term_x = (w - term_w) / 2.0
        term_y = 8

        # Corona aura around terminal
        corona = QRadialGradient(w / 2.0, term_y + term_h / 2.0, 16)
        if self.muted:
            corona.setColorAt(0.0, QColor(100, 116, 139, 70))
            corona.setColorAt(1.0, QColor(100, 116, 139, 0))
        else:
            c_term = self.accent if self.volume <= 75 else QColor('#ff007f')
            corona.setColorAt(0.0, QColor(c_term.red(), c_term.green(), c_term.blue(), int(90 + breath * 130)))
            corona.setColorAt(1.0, QColor(c_term.red(), c_term.green(), c_term.blue(), 0))
        painter.setBrush(corona)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(w / 2.0, term_y + term_h / 2.0), 16, 10)

        # Terminal cap body
        term_grad = QLinearGradient(term_x, term_y, term_x + term_w, term_y + term_h)
        if self.muted:
            term_grad.setColorAt(0.0, QColor(148, 163, 184, 180))
            term_grad.setColorAt(1.0, QColor(71, 85, 105, 180))
        else:
            term_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
            term_grad.setColorAt(0.4, QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 230))
            term_grad.setColorAt(1.0, QColor(self.accent2.red(), self.accent2.green(), self.accent2.blue(), 200))
        painter.setBrush(term_grad)
        painter.drawRoundedRect(QRectF(term_x, term_y, term_w, term_h), 3, 3)

        # ── Battery Chamber Glass & Breathing Glow Border ──
        body_x = 8
        body_y = 18
        body_w = w - 16
        body_bottom = h - 32
        body_h = body_bottom - body_y

        # ── UNIVERSAL LAYER 1: Breathing outer aura halo (hover-reactive) ──
        if not self.muted:
            aura_pulse = 0.5 + 0.5 * math.sin(self.aura_phase)
            aura_spread = 5.0 + aura_pulse * 5.0 + self.hover_lift * 7.0
            aura_alpha = int(38 + 58 * aura_pulse + 62 * self.hover_lift)
            acol = self.accent2 if self.volume > 75 else self.accent
            aura = QRadialGradient(w / 2.0, h / 2.0, max(body_w, body_h) * 0.78 + aura_spread)
            aura.setColorAt(0.0, QColor(acol.red(), acol.green(), acol.blue(), 0))
            aura.setColorAt(0.62, QColor(acol.red(), acol.green(), acol.blue(), 0))
            aura.setColorAt(0.86, QColor(acol.red(), acol.green(), acol.blue(), aura_alpha // 2))
            aura.setColorAt(1.0, QColor(acol.red(), acol.green(), acol.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(aura)
            painter.drawRoundedRect(QRectF(-2, -2, w + 4, h + 4), 14, 14)

        border_glow = QColor(self.border_color)
        border_glow.setAlpha(int(70 + breath * 140))
        painter.setPen(QPen(border_glow, 1.5 + breath * 0.8))
        painter.setBrush(QColor(10, 14, 22, 225))
        painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 8, 8)

        # ── UNIVERSAL LAYER 2: Travelling border light sweep ──
        if not self.muted:
            sweep_c = QColor(255, 255, 255, int(70 + 90 * self.hover_lift))
            sweep_y = body_y + self.beam_pos * body_h
            painter.setPen(QPen(sweep_c, 1.4))
            painter.drawLine(QPointF(body_x + 1.5, sweep_y), QPointF(body_x + 1.5, sweep_y + body_h * 0.16))
            painter.drawLine(QPointF(body_x + body_w - 1.5, sweep_y),
                             QPointF(body_x + body_w - 1.5, sweep_y + body_h * 0.16))

        # ── Liquid Fill Volume ──
        fill_pct = 0.0 if self.muted else (self.volume / 100.0)
        fill_h = max(0.0, (body_h - 4) * fill_pct)
        fill_y = (body_y + body_h - 2) - fill_h

        if fill_h > 0:
            # Multi-tone liquid plasma gradient
            grad = QLinearGradient(0, fill_y, 0, body_y + body_h)
            if self.volume <= 35:
                grad.setColorAt(0.0, QColor('#00e676'))
                grad.setColorAt(1.0, QColor('#00b0ff'))
            elif self.volume <= 75:
                grad.setColorAt(0.0, QColor(self.accent))
                grad.setColorAt(0.65, QColor(self.accent2))
                grad.setColorAt(1.0, QColor('#4f46e5'))
            else:
                grad.setColorAt(0.0, QColor('#ff007f'))
                grad.setColorAt(0.45, QColor('#ff9100'))
                grad.setColorAt(1.0, QColor(self.accent))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(body_x + 2, fill_y, body_w - 4, fill_h), 6, 6)

            # ── Style-Specific Animated Overlay Effects ──
            self._paint_battery_effects(painter, body_x, body_y, body_w, body_h, fill_y, fill_h, fill_pct, breath)

            # ── UNIVERSAL LAYER 3: Live liquid surface shimmer (all styles) ──
            surf_wob = math.sin(self.anim_phase * 1.7) * 1.8 + self.splash_offset * 0.6
            surf_y = fill_y + surf_wob
            surface = QLinearGradient(0, surf_y - 5, 0, surf_y + 3)
            sc = QColor(255, 255, 255, int(120 + 110 * breath))
            surface.setColorAt(0.0, QColor(sc.red(), sc.green(), sc.blue(), 0))
            surface.setColorAt(0.45, sc)
            surface.setColorAt(1.0, QColor(sc.red(), sc.green(), sc.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(surface)
            painter.drawRect(QRectF(body_x + 2, surf_y - 5, body_w - 4, 8.0))

            # ── UNIVERSAL LAYER 4: Volume-change shockwave ring ──
            if self.shock_burst > 0.001:
                sb = self.shock_burst
                ring_rad = (1.0 - sb) * (body_w * 0.95) + 4.0
                ring_col = QColor(255, 255, 255, int(190 * sb))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(ring_col, 2.4 * sb + 0.5))
                painter.drawRoundedRect(
                    QRectF(body_x + body_w / 2.0 - ring_rad / 1.4,
                           body_y + body_h / 2.0 - ring_rad / 1.1,
                           ring_rad * 1.42, ring_rad * 2.2),
                    10, 10)

        # ── Segmented Laser-Etched Ticks with Glowing Neon Side Indicators ──
        for tick_i, step in enumerate([0.2, 0.4, 0.6, 0.8]):
            sy = (body_y + body_h - 2) - (body_h - 4) * step
            is_lit = (fill_pct >= step) and not self.muted
            if is_lit:
                # Animated travelling gleam across lit tick rails
                pulse_a = 0.5 + 0.5 * math.sin(self.aura_phase * 1.6 + tick_i * 1.3)
                painter.setPen(QPen(QColor(255, 255, 255, int(60 + 95 * pulse_a)), 1))
                painter.drawLine(int(body_x + 4), int(sy), int(body_x + body_w - 4), int(sy))
                # Side LED indicator dots with breathing halo
                halo_r = 3.4 + pulse_a * 2.2
                for dx in (body_x + 3, body_x + body_w - 3):
                    halo = QRadialGradient(dx, sy, halo_r)
                    halo.setColorAt(0.0, QColor(self.accent.red(), self.accent.green(),
                                                self.accent.blue(), int(150 * pulse_a) + 40))
                    halo.setColorAt(1.0, QColor(self.accent.red(), self.accent.green(),
                                                self.accent.blue(), 0))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(halo)
                    painter.drawEllipse(QPointF(dx, sy), halo_r, halo_r)
                    painter.setBrush(QColor(self.accent))
                    painter.drawEllipse(QPointF(dx, sy), 1.5, 1.5)
            else:
                painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
                painter.drawLine(int(body_x + 6), int(sy), int(body_x + body_w - 6), int(sy))

        # ── Volume / Mute Readout Text ──
        font = QFont('Segoe UI', 9)
        font.setBold(True)
        painter.setFont(font)
        text_str = 'MUTE' if self.muted else f"{self.volume}%"
        # Shadow for contrast
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(QRectF(body_x + 1, body_y + 1, body_w, body_h), Qt.AlignmentFlag.AlignCenter, text_str)
        # Main text
        painter.setPen(QColor('#ffffff') if not self.muted else QColor('#ff4757'))
        painter.drawText(QRectF(body_x, body_y, body_w, body_h), Qt.AlignmentFlag.AlignCenter, text_str)

        # ── Interactive Speaker Icon at Bottom ──
        speaker_icon = '🔇' if self.muted else ('🔉' if self.volume < 50 else '🔊')
        font_icon = QFont('Segoe UI Emoji', 10)
        painter.setFont(font_icon)
        painter.setPen(QColor('#ffffff'))
        painter.drawText(QRectF(0, h - 30, w, 26), Qt.AlignmentFlag.AlignCenter, speaker_icon)


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-HANDLE HIGH-PRECISION SONG TIMELINE SLIDER
# ─────────────────────────────────────────────────────────────────────────────

class TimelineSlider(QSlider):
    """
    Multi-Handle Interactive Timeline Slider with draggable Point A & Point B
    Loop Pins directly on the song slider, live time scrub tooltips, and
    shaded loop region visualization.
    """
    seekRequested = pyqtSignal(int)
    loopChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setMouseTracking(True)
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.track_bg = '#161c2b'
        self.accent_color = QColor('#00f0ff')
        self.accent2_color = QColor('#7c3aed')
        self.loop_a = None
        self.loop_b = None
        self.duration_ms = 0

        self._dragging_target = None
        self._hover_target = None
        self._hover_x = None

    def set_theme_colors(self, track_bg, accent_hex, accent2_hex):
        self.track_bg = track_bg
        self.accent_color = QColor(accent_hex)
        self.accent2_color = QColor(accent2_hex)
        self.update()

    def set_duration(self, ms):
        self.duration_ms = max(0, ms)

    def set_loop_points(self, a_ms, b_ms):
        self.loop_a = a_ms
        self.loop_b = b_ms
        self.update()

    def clear_loop(self):
        self.loop_a = None
        self.loop_b = None
        self.update()

    def _ms_to_x(self, ms):
        if self.duration_ms <= 0:
            return 0.0
        w = max(1.0, float(self.width()))
        return max(0.0, min(w, (ms / self.duration_ms) * w))

    def _x_to_ms(self, x):
        if self.duration_ms <= 0:
            return 0
        w = max(1.0, float(self.width()))
        frac = max(0.0, min(1.0, x / w))
        return int(frac * self.duration_ms)

    def _val_to_x(self, val):
        w = max(1.0, float(self.width()))
        span = max(1, self.maximum() - self.minimum())
        return ((val - self.minimum()) / span) * w

    def _x_to_val(self, x):
        w = max(1.0, float(self.width()))
        frac = max(0.0, min(1.0, x / w))
        span = self.maximum() - self.minimum()
        return int(self.minimum() + frac * span)

    def _format_time_ms(self, ms):
        s = ms // 1000
        tenth = (ms % 1000) // 100
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        base = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        return f"{base}.{tenth}"

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_target = None
        self._hover_x = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            xa = self._ms_to_x(self.loop_a) if self.loop_a is not None else None
            xb = self._ms_to_x(self.loop_b) if self.loop_b is not None else None

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.loop_a = self._x_to_ms(x)
                self._dragging_target = 'loop_a'
                self.loopChanged.emit(self.loop_a, self.loop_b or -1)
            elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.loop_b = self._x_to_ms(x)
                self._dragging_target = 'loop_b'
                self.loopChanged.emit(self.loop_a or -1, self.loop_b)
            elif xa is not None and abs(x - xa) <= 10:
                self._dragging_target = 'loop_a'
            elif xb is not None and abs(x - xb) <= 10:
                self._dragging_target = 'loop_b'
            else:
                self._dragging_target = 'playhead'
                val = self._x_to_val(x)
                self.setValue(val)
                self.seekRequested.emit(val)

            self.update()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        self._hover_x = x
        xa = self._ms_to_x(self.loop_a) if self.loop_a is not None else None
        xb = self._ms_to_x(self.loop_b) if self.loop_b is not None else None

        if self._dragging_target == 'loop_a':
            new_a = self._x_to_ms(x)
            if self.loop_b is not None:
                new_a = min(new_a, self.loop_b - 300)
            self.loop_a = max(0, new_a)
            self.loopChanged.emit(int(self.loop_a), int(self.loop_b) if self.loop_b else -1)
            QToolTip.showText(self.mapToGlobal(QPoint(int(x), -24)), f"Loop [A]: {self._format_time_ms(self.loop_a)}", self)
        elif self._dragging_target == 'loop_b':
            new_b = self._x_to_ms(x)
            if self.loop_a is not None:
                new_b = max(new_b, self.loop_a + 300)
            self.loop_b = min(self.duration_ms, new_b)
            self.loopChanged.emit(int(self.loop_a) if self.loop_a else -1, int(self.loop_b))
            QToolTip.showText(self.mapToGlobal(QPoint(int(x), -24)), f"Loop [B]: {self._format_time_ms(self.loop_b)}", self)
        elif self._dragging_target == 'playhead' and (event.buttons() & Qt.MouseButton.LeftButton):
            val = self._x_to_val(x)
            self.setValue(val)
            self.seekRequested.emit(val)
        else:
            if xa is not None and abs(x - xa) <= 10:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self._hover_target = 'loop_a'
                QToolTip.showText(self.mapToGlobal(QPoint(int(x), -24)), f"Drag Loop [A]: {self._format_time_ms(self.loop_a)}", self)
            elif xb is not None and abs(x - xb) <= 10:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self._hover_target = 'loop_b'
                QToolTip.showText(self.mapToGlobal(QPoint(int(x), -24)), f"Drag Loop [B]: {self._format_time_ms(self.loop_b)}", self)
            else:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._hover_target = None
                hover_ms = self._x_to_ms(x)
                QToolTip.showText(self.mapToGlobal(QPoint(int(x), -24)), self._format_time_ms(hover_ms), self)

        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_target = None
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h / 2.0
        track_h = 7.0
        track_y = mid_y - track_h / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.track_bg))
        painter.drawRoundedRect(QRectF(0, track_y, w, track_h), 3, 3)

        if self.loop_a is not None and self.duration_ms > 0:
            xa = self._ms_to_x(self.loop_a)
            xb = self._ms_to_x(self.loop_b) if self.loop_b is not None else xa
            left_x = min(xa, xb)
            right_x = max(xa, xb)

            if right_x > left_x:
                loop_grad = QLinearGradient(left_x, 0, right_x, 0)
                loop_grad.setColorAt(0.0, QColor(0, 240, 255, 75))
                loop_grad.setColorAt(1.0, QColor(255, 0, 127, 75))
                painter.setBrush(loop_grad)
                painter.drawRoundedRect(QRectF(left_x, track_y - 3, right_x - left_x, track_h + 6), 4, 4)

            painter.setPen(QPen(QColor(0, 240, 255, 240), 2))
            painter.drawLine(int(xa), int(track_y - 7), int(xa), int(track_y + track_h + 7))

            flag_a = QRectF(xa - 8, track_y - 12, 16, 12)
            painter.setBrush(QColor(0, 240, 255, 230))
            painter.drawRoundedRect(flag_a, 3, 3)
            font_flag = QFont('Segoe UI', 8)
            font_flag.setBold(True)
            painter.setFont(font_flag)
            painter.setPen(QColor('#070a13'))
            painter.drawText(flag_a, Qt.AlignmentFlag.AlignCenter, 'A')

            if self.loop_b is not None:
                painter.setPen(QPen(QColor(255, 0, 127, 240), 2))
                painter.drawLine(int(xb), int(track_y - 7), int(xb), int(track_y + track_h + 7))

                flag_b = QRectF(xb - 8, track_y - 12, 16, 12)
                painter.setBrush(QColor(255, 0, 127, 230))
                painter.drawRoundedRect(flag_b, 3, 3)
                painter.setPen(QColor('#ffffff'))
                painter.drawText(flag_b, Qt.AlignmentFlag.AlignCenter, 'B')

        progress_w = self._val_to_x(self.value())
        if progress_w > 0:
            grad = QLinearGradient(0, 0, progress_w, 0)
            grad.setColorAt(0.0, self.accent_color)
            grad.setColorAt(1.0, self.accent2_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(0, track_y, progress_w, track_h), 3, 3)

        thumb_r = 7.0 if self._dragging_target == 'playhead' else 5.5
        thumb_x = max(thumb_r, min(w - thumb_r, progress_w))

        halo_c = QColor(self.accent_color.red(), self.accent_color.green(), self.accent_color.blue(), 60)
        painter.setBrush(halo_c)
        painter.drawEllipse(QPointF(thumb_x, mid_y), thumb_r + 4.0, thumb_r + 4.0)

        painter.setPen(QPen(QColor(255, 255, 255, 240), 2))
        painter.setBrush(self.accent_color)
        painter.drawEllipse(QPointF(thumb_x, mid_y), thumb_r, thumb_r)

        if self._hover_x is not None and self._dragging_target is None:
            painter.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(self._hover_x), int(track_y - 4), int(self._hover_x), int(track_y + track_h + 4))


# ─────────────────────────────────────────────────────────────────────────────
# PANORAMIC MODERN VISUALIZER (Beat-Reactive Wave Synthesis)
# ─────────────────────────────────────────────────────────────────────────────

class ModernVisualizer(QFrame):
    """Panoramic Studio Visualizer supporting 8 render modes spanning 100% width."""
    modeChanged = pyqtSignal(str)

    MODES = [
        'bars', 'wave', 'radial', 'particles', 'mirror_wave', 'circular_bars', 'dna_helix', 'plasma_grid',
        'neon_oscilloscope', 'cyber_tunnel', 'hologram_rings', 'laser_strobe', 'quantum_matrix', 'hex_hive',
        'waterfall', 'stereo_scope', 'sound_aurora', 'retro_synth_grid', 'starburst_galaxy', 'fractal_kaleidoscope'
    ]
    MODE_LABELS = {
        'bars': '📊 SPECTRUM BARS',
        'wave': '🌊 LIQUID WAVE',
        'radial': '🌀 RADIAL HALO',
        'particles': '✨ AUDIO NEBULA',
        'mirror_wave': '🪞 DUAL MIRROR WAVE',
        'circular_bars': '💫 CIRCULAR SPECTRUM',
        'dna_helix': '🧬 DUAL DNA HELIX',
        'plasma_grid': '🌌 NEON PLASMA GRID',
        'neon_oscilloscope': '⚡ NEON OSCILLOSCOPE',
        'cyber_tunnel': '🚀 CYBER VORTEX TUNNEL',
        'hologram_rings': '🪐 HOLOGRAPHIC RINGS',
        'laser_strobe': '⚡ CONCERT LASER SHOW',
        'quantum_matrix': '🔮 QUANTUM WAVE FIELD',
        'hex_hive': '⬡ CYBERNETIC HEX HIVE',
        'waterfall': '🌊 SPECTRAL WATERFALL',
        'stereo_scope': '🎯 LISSAJOUS PHASE VECTOR',
        'sound_aurora': '🌌 BOREALIS SOUND AURORA',
        'retro_synth_grid': '🌆 80s SYNTH HORIZON',
        'starburst_galaxy': '🌠 AUDIO STARBURST GALAXY',
        'fractal_kaleidoscope': '💠 FRACTAL KALEIDOSCOPE'
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.engine = AudioVisualizerEngine(max_bands=128)
        self.mode = 'bars'
        self.theme_key = 'midnight'
        self.show_hud = True          # gadget hosts set this False in tight panes
        self.transparent_bg = False   # gadget paints the bars onto the desktop
        self.t = THEMES[self.theme_key]
        self._color_override = None   # (accent, accent2, accent3) or None = follow the theme
        self.audio_buffer = None
        self.player = None

        self.particles = []
        self._init_particles(120)

        # Beat-reactive wave sparks
        self.wave_sparks = []
        self._init_wave_sparks(60)

        # Multi-mode animation states
        self.anim_phase = 0.0
        self.waterfall_history = []
        self.starburst_stars = []
        for _ in range(80):
            self.starburst_stars.append({
                'angle': random.uniform(0, math.pi * 2),
                'dist': random.uniform(0.1, 1.0),
                'speed': random.uniform(0.04, 0.16),
                'size': random.uniform(1.5, 4.0),
                'color_idx': random.randint(0, 2)
            })

        self.last_time = time.perf_counter()
        self.fps = 60.0
        self.fps_counter = 0
        self.fps_timer = time.perf_counter()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._render_tick)
        # Repaint as fast as the panel can actually show it: ask the screen for
        # its refresh rate and pace to that with a precise timer. The old fixed
        # 24 ms interval was ~41 FPS on any display, and a coarse timer adds up
        # to 15 ms of jitter on top.
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        try:
            hz = float(QApplication.primaryScreen().refreshRate() or 60.0)
        except Exception:
            hz = 60.0
        self.refresh_hz = hz if 30.0 <= hz <= 360.0 else 60.0
        self.frame_budget_ms = max(4.0, 1000.0 / self.refresh_hz)
        self._paint_ms = 0.0
        self._tick_ms = 0.0
        self._pace_ticks = 0
        self._vpos_anchor = None
        self._vpos_last = None
        self._visual_rate = 1.0
        self.timer.start(max(4, int(round(self.frame_budget_ms))))

    def set_player(self, player):
        self.player = player

    def set_audio_buffer(self, audio_buf):
        self.audio_buffer = audio_buf

    def clear_audio_buffer(self):
        self.audio_buffer = None

    def _init_particles(self, count):
        self.particles.clear()
        for _ in range(count):
            self.particles.append({
                'x': random.random(),
                'y': random.random(),
                'vx': (random.random() - 0.5) * 0.15,
                'vy': (random.random() - 0.5) * 0.15,
                'size': random.uniform(2.0, 5.0),
                'alpha': random.uniform(0.3, 0.9),
                'color_idx': random.randint(0, 2)
            })

    def _init_wave_sparks(self, count):
        self.wave_sparks.clear()
        for _ in range(count):
            self.wave_sparks.append({
                'x': random.random(),
                'y_rel': 0.0,
                'vy': -random.uniform(0.1, 0.4),
                'size': random.uniform(1.5, 3.5),
                'life': random.random()
            })

    def set_theme(self, theme_key):
        self.theme_key = theme_key
        self._rebuild_colours()
        self.update()

    def set_color_override(self, accent=None, accent2=None, accent3=None):
        """Repaint the visuals from a host-local palette instead of the theme.

        A host (the floating gadget) keeps its own colour set, separate from
        the app: it hands over three hex colours here and the visuals use them
        for every render mode. Passing None for *accent* puts the visuals back
        on the app theme. Only the accent triplet is swapped — backgrounds,
        text and borders keep using their theme keys.
        """
        if not accent:
            self._color_override = None
        else:
            self._color_override = (str(accent), str(accent2 or accent),
                                    str(accent3 or accent2 or accent))
        self._rebuild_colours()
        self.update()

    def _rebuild_colours(self):
        """Re-resolve self.t: the theme, or the theme plus the colour override."""
        base = THEMES.get(self.theme_key, THEMES['midnight'])
        ov = getattr(self, '_color_override', None)
        if not ov:
            self.t = base
            return
        t = dict(base)
        t['accent'], t['accent2'], t['accent3'] = ov
        self.t = t

    def set_mode(self, mode):
        if mode in self.MODES:
            self.mode = mode
            self.modeChanged.emit(mode)
            self.update()

    def cycle_mode(self):
        idx = (self.MODES.index(self.mode) + 1) % len(self.MODES)
        self.set_mode(self.MODES[idx])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.cycle_mode()
        super().mousePressEvent(event)

    def _visual_pos(self):
        """Playhead for the visuals, smooth between the player's position polls.

        QMediaPlayer reports position in ~50-100 ms steps, so at 60-144 FPS the
        old code fed the same instant to five or ten frames in a row — the
        spectrum visibly stepped. Keep a local clock anchored to each report and
        run it forward at the playback rate; interpolated analysis frames then
        make the motion continuous.
        """
        if not self.player:
            return 0.0
        try:
            reported = self.player.position() / 1000.0
            playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            self._visual_rate = float(self.player.playbackRate() or 1.0)
        except Exception:
            return 0.0
        now = time.perf_counter()
        if not playing or self._vpos_anchor is None or reported != self._vpos_last:
            self._vpos_last = reported
            self._vpos_anchor = (reported, now)
            return reported
        anchor_pos, anchor_t = self._vpos_anchor
        est = anchor_pos + (now - anchor_t) * self._visual_rate
        try:
            dur = self.player.duration() / 1000.0
            if dur > 0:
                est = min(est, dur)
        except Exception:
            pass
        return max(0.0, est)

    def _pace_frames(self):
        """Adapt the interval so painting never becomes the bottleneck.

        Targets the display's refresh, and backs off only when a frame really
        costs more than the budget (heavy modes on weak GPUs) so the UI stays
        responsive instead of queueing repaints.
        """
        self._pace_ticks += 1
        if self._pace_ticks < 30:
            return
        self._pace_ticks = 0
        cost = self._tick_ms + self._paint_ms
        target = self.frame_budget_ms
        if cost > target * 0.92:
            target = min(40.0, cost * 1.28)
        interval = int(round(max(4.0, target)))
        if abs(interval - self.timer.interval()) >= 2:
            self.timer.setInterval(interval)

    def _render_tick(self):
        now = time.perf_counter()
        dt = max(0.001, min(0.05, now - self.last_time))
        self.last_time = now

        self.fps_counter += 1
        if now - self.fps_timer >= 1.0:
            self.fps = self.fps_counter / (now - self.fps_timer)
            self.fps_counter = 0
            self.fps_timer = now

        w = max(100, self.width())
        active_bands = max(48, min(128, w // 9))

        is_playing = (self.player is not None and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        pos_sec = self._visual_pos()

        bands = None
        bass_energy = None
        raw_rms = 0.0
        onset = None
        if is_playing and self.audio_buffer:
            try:
                bands, bass_energy, raw_rms, onset = self.audio_buffer.analysis_frame(pos_sec)
            except Exception:
                bands, bass_energy, raw_rms, onset = None, None, 0.0, None
                try:
                    bands, bass_energy, raw_rms = self.audio_buffer.get_spectrum_and_energy(
                        pos_sec, active_bands)
                except Exception:
                    bands = None

        beat_age = beat_peak = None
        if is_playing and self.audio_buffer is not None and bands is not None:
            try:
                nb = self.audio_buffer.last_beat(pos_sec)
                if nb is not None:
                    beat_age = max(0.0, pos_sec - nb[0])
                    beat_peak = nb[1]
            except Exception:
                beat_age = beat_peak = None

        self.engine.update(dt, playing=is_playing, active_bands=active_bands,
                           audio_bands=bands, bass_energy=bass_energy,
                           raw_rms=raw_rms, onset=onset,
                           beat_age=beat_age, beat_peak=beat_peak)

        if self.mode == 'particles':
            beat_boost = 3.0 if self.engine.beat else 1.0
            for p in self.particles:
                p['x'] += p['vx'] * dt * beat_boost
                p['y'] += p['vy'] * dt * beat_boost
                if p['x'] < 0: p['x'] = 1.0
                elif p['x'] > 1.0: p['x'] = 0.0
                if p['y'] < 0: p['y'] = 1.0
                elif p['y'] > 1.0: p['y'] = 0.0
        elif self.mode == 'wave':
            beat_boost = 2.5 if self.engine.beat else 1.0
            for sp in self.wave_sparks:
                sp['life'] -= dt * 0.8
                sp['y_rel'] += sp['vy'] * dt * beat_boost
                if sp['life'] <= 0:
                    sp['x'] = random.random()
                    sp['y_rel'] = 0.0
                    sp['life'] = 1.0
        elif self.mode == 'waterfall':
            # Snapshot live levels for the scrolling thermal waterfall
            if len(self.engine.levels) > 0:
                self.waterfall_history.insert(0, list(self.engine.levels[:min(48, len(self.engine.levels))]))
                if len(self.waterfall_history) > 36:
                    self.waterfall_history.pop()
        elif self.mode == 'starburst_galaxy':
            rot_speed = 0.03 + (0.09 if self.engine.beat else 0.0)
            for s in self.starburst_stars:
                s['angle'] = (s['angle'] + s['speed'] * rot_speed) % (math.pi * 2)

        self.anim_phase += dt * (3.0 if self.engine.beat else 1.2)
        self._tick_ms = (time.perf_counter() - now) * 1000.0
        # This is the frame request: the timer ticks the model, update() asks for
        # the paint. Omitting it freezes the visualizer after one frame.
        # Paint now instead of asking for a deferred repaint: update() waits
        # for WM_PAINT, and Windows services that on the 15.6 ms system
        # quantum, which caps the visualizer near 64 fps no matter how fast the
        # timer runs. paintEvent costs 2-3 ms here, and _pace_frames() backs off
        # if a mode ever gets heavier than the frame budget.
        self.repaint()
        self._pace_frames()

    def paintEvent(self, event):
        t_paint = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        clip_path = QPainterPath()
        if not getattr(self, 'transparent_bg', False):
            clip_path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
            painter.setClipPath(clip_path)

            bg_grad = QLinearGradient(0, 0, w, h)
            bg_grad.setColorAt(0.0, _qcolor(self.t['bg'], 1.0))
            bg_grad.setColorAt(1.0, _qcolor(self.t['bg_card'], 1.0))
            painter.fillRect(self.rect(), bg_grad)

        if self.mode == 'bars':
            self._paint_bars(painter, w, h)
        elif self.mode == 'wave':
            self._paint_wave(painter, w, h)
        elif self.mode == 'radial':
            self._paint_radial(painter, w, h)
        elif self.mode == 'particles':
            self._paint_particles(painter, w, h)
        elif self.mode == 'mirror_wave':
            self._paint_mirror_wave(painter, w, h)
        elif self.mode == 'circular_bars':
            self._paint_circular_bars(painter, w, h)
        elif self.mode == 'dna_helix':
            self._paint_dna_helix(painter, w, h)
        elif self.mode == 'plasma_grid':
            self._paint_plasma_grid(painter, w, h)
        elif self.mode == 'neon_oscilloscope':
            self._paint_neon_oscilloscope(painter, w, h)
        elif self.mode == 'cyber_tunnel':
            self._paint_cyber_tunnel(painter, w, h)
        elif self.mode == 'hologram_rings':
            self._paint_hologram_rings(painter, w, h)
        elif self.mode == 'laser_strobe':
            self._paint_laser_strobe(painter, w, h)
        elif self.mode == 'quantum_matrix':
            self._paint_quantum_matrix(painter, w, h)
        elif self.mode == 'hex_hive':
            self._paint_hex_hive(painter, w, h)
        elif self.mode == 'waterfall':
            self._paint_waterfall(painter, w, h)
        elif self.mode == 'stereo_scope':
            self._paint_stereo_scope(painter, w, h)
        elif self.mode == 'sound_aurora':
            self._paint_sound_aurora(painter, w, h)
        elif self.mode == 'retro_synth_grid':
            self._paint_retro_synth_grid(painter, w, h)
        elif self.mode == 'starburst_galaxy':
            self._paint_starburst_galaxy(painter, w, h)
        elif self.mode == 'fractal_kaleidoscope':
            self._paint_fractal_kaleidoscope(painter, w, h)

        self._paint_hud(painter, w, h)
        painter.end()
        self._paint_ms = self._paint_ms * 0.85 + (time.perf_counter() - t_paint) * 1000.0 * 0.15

    def _paint_bars(self, painter, w, h):
        num_bars = max(48, min(128, int(w / 10)))
        base_y = h - 26
        max_bar_h = max(20, h - 60)

        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t['accent3'])

        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawLine(0, base_y, w, base_y)

        for i in range(num_bars):
            x0 = int(round(i * w / num_bars))
            x1 = int(round((i + 1) * w / num_bars))
            gap = 2 if (x1 - x0) >= 6 else 1
            bw = max(1, (x1 - x0) - gap)
            if i == num_bars - 1:
                bw = max(1, w - x0)

            level = self.engine.levels[i] if i < len(self.engine.levels) else 0.0
            peak = self.engine.peaks[i] if i < len(self.engine.peaks) else 0.0

            bh = int(level * max_bar_h)
            by = base_y - bh

            grad = QLinearGradient(x0, by, x0, base_y)
            grad.setColorAt(0.0, c_accent3)
            grad.setColorAt(0.45, c_accent2)
            grad.setColorAt(1.0, c_accent)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(x0, by, bw, bh), 2, 2)

            if bh > 4:
                ref_h = min(14, bh // 3)
                ref_grad = QLinearGradient(x0, base_y, x0, base_y + ref_h)
                ref_c = QColor(c_accent)
                ref_c.setAlpha(60)
                ref_grad.setColorAt(0.0, ref_c)
                ref_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                painter.setBrush(ref_grad)
                painter.drawRect(QRectF(x0, base_y + 1, bw, ref_h))

            if peak > 0.02:
                pk_y = base_y - int(peak * max_bar_h) - 3
                painter.setBrush(QColor(255, 255, 255, 230))
                painter.drawRect(QRectF(x0, pk_y, bw, 2))

    def _paint_wave(self, painter, w, h):
        """
        Advanced Multi-Layered Oscilloscope Synthesis:
        Reacts vividly to beat pulses with dynamic amplitude surges, neon glow blooms,
        harmonic counter-waves, high-frequency cyber ripples, and crest spark particles.
        """
        mid_y = (h - 26) / 2.0 + 10.0
        base_amp = max(24.0, (h - 70) * 0.42)
        beat_surge = 1.0 + (self.engine.beat_strength * 0.90 if self.engine.playing else 0.0)
        amp = base_amp * beat_surge
        t = self.engine.time

        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t.get('accent3', '#ffffff'))

        # Wave Paths
        path1 = QPainterPath()  # Primary Cyber Neon Wave
        path2 = QPainterPath()  # Harmonic Counter-Wave
        path3 = QPainterPath()  # High-Frequency Starlight Ripple

        path1.moveTo(0, mid_y)
        path2.moveTo(0, mid_y)
        path3.moveTo(0, mid_y)

        # Performance-optimized sampling (140 points across full panel width)
        step = max(2, w // 140)
        xs = list(range(0, w + 1, step))
        if xs[-1] != w:
            xs.append(w)

        num_levels = max(1, len(self.engine.levels))

        for x in xs:
            rel = x / float(w)
            band_idx = min(num_levels - 1, int(rel * num_levels))
            # clamp: a negative level would make lvl ** 0.5 complex
            lvl = max(0.0, min(1.0, self.engine.levels[band_idx]))

            # Primary neon curve (dual harmonic sinusoids)
            y1 = mid_y + (
                math.sin(rel * 14.0 + t * 4.6) * 0.65 +
                math.sin(rel * 30.0 - t * 3.2) * 0.35
            ) * amp * lvl

            # Harmonic counter-wave (inverted phase & counter-shifted)
            y2 = mid_y + (
                math.cos(rel * 18.0 - t * 3.8 + 1.2) * 0.70 +
                math.sin(rel * 42.0 + t * 5.2) * 0.30
            ) * amp * (lvl * 0.82)

            # High-frequency micro-ripple
            y3 = mid_y + (
                math.sin(rel * 65.0 + t * 9.0) * 0.22 * (lvl ** 0.5)
            ) * amp

            path1.lineTo(x, y1)
            path2.lineTo(x, y2)
            path3.lineTo(x, y3)

        # 1. Translucent Plasma Aurora Under-Glow
        fill_path = QPainterPath(path1)
        fill_path.lineTo(w, h - 26)
        fill_path.lineTo(0, h - 26)
        fill_path.closeSubpath()

        fill_grad = QLinearGradient(0, 0, 0, h)
        aurora_alpha = int(35 + self.engine.beat_strength * 115)
        c_aurora = QColor(c_accent)
        c_aurora.setAlpha(aurora_alpha)
        fill_grad.setColorAt(0.0, c_aurora)
        fill_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_grad)
        painter.drawPath(fill_path)

        # 2. Beat Shockwave Glow Bloom on Bass Hits
        if self.engine.beat:
            bloom_grad = QRadialGradient(w / 2.0, mid_y, w * 0.40)
            c_bloom = QColor(c_accent2)
            c_bloom.setAlpha(int(self.engine.beat_strength * 90))
            bloom_grad.setColorAt(0.0, c_bloom)
            bloom_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(bloom_grad)
            painter.drawRect(self.rect())

        # 3. Harmonic Counter-Wave (Secondary Accent)
        c_accent2_pen = QColor(c_accent2)
        c_accent2_pen.setAlpha(int(160 + self.engine.beat_strength * 80))
        painter.setPen(QPen(c_accent2_pen, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path2)

        # 4. High-Frequency Starlight Ripple (Tertiary Starlight Accent)
        c_accent3_pen = QColor(c_accent3)
        c_accent3_pen.setAlpha(120)
        painter.setPen(QPen(c_accent3_pen, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path3)

        # 5. Primary Cyber Neon Wave (Thick, Glowing, Beat-Reactive)
        neon_width = 3.5 + (2.0 if self.engine.beat else 0.0)
        painter.setPen(QPen(c_accent, neon_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path1)

        # 6. Floating Beat Sparks Along Wave Crests
        painter.setPen(Qt.PenStyle.NoPen)
        for sp in self.wave_sparks:
            sx = sp['x'] * w
            band_idx = min(num_levels - 1, int(sp['x'] * num_levels))
            lvl = self.engine.levels[band_idx]
            sy_base = mid_y + math.sin(sp['x'] * 14.0 + t * 4.6) * amp * lvl
            sy = sy_base + sp['y_rel'] * 40.0
            spark_c = QColor(255, 255, 255, int(sp['life'] * 200))
            painter.setBrush(spark_c)
            painter.drawEllipse(QPointF(sx, sy), sp['size'], sp['size'])

    def _paint_radial(self, painter, w, h):
        cx = w / 2.0
        cy = (h - 26) / 2.0 + 10.0
        base_r = min(w, h) * 0.18
        max_spike = min(w, h) * 0.22

        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(16):
            frac = i / 16.0
            rx = frac * w
            lvl = self.engine.levels[i * 2] if (i * 2) < len(self.engine.levels) else 0.1
            rh = lvl * (h * 0.35)
            rib_c = QColor(c_accent2)
            rib_c.setAlpha(int(lvl * 55))
            painter.setBrush(rib_c)
            painter.drawRect(QRectF(rx, cy - rh / 2.0, w / 16.0, rh))

        num_rays = 48
        for i in range(num_rays):
            angle = (i / num_rays) * 2.0 * math.pi
            lvl_idx = int((i / num_rays) * (len(self.engine.levels) // 2))
            lvl = self.engine.levels[lvl_idx] if lvl_idx < len(self.engine.levels) else 0.1

            r1 = base_r
            r2 = base_r + lvl * max_spike + (10.0 if self.engine.beat else 0.0)

            x1 = cx + math.cos(angle) * r1
            y1 = cy + math.sin(angle) * r1
            x2 = cx + math.cos(angle) * r2
            y2 = cy + math.sin(angle) * r2

            ray_color = c_accent if i % 2 == 0 else c_accent2
            painter.setPen(QPen(ray_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        center_r = base_r * (1.15 if self.engine.beat else 0.95)
        rad_grad = QRadialGradient(cx, cy, center_r)
        c_core = QColor(self.t['accent'])
        c_core.setAlpha(190)
        rad_grad.setColorAt(0.0, c_core)
        rad_grad.setColorAt(0.8, QColor(self.t['bg_card']))
        rad_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(rad_grad)
        painter.drawEllipse(QPointF(cx, cy), center_r, center_r)

    def _paint_particles(self, painter, w, h):
        c_palette = [
            QColor(self.t['accent']),
            QColor(self.t['accent2']),
            QColor(self.t['accent3'])
        ]

        painter.setPen(Qt.PenStyle.NoPen)
        beat_scale = 1.6 if self.engine.beat else 1.0

        for p in self.particles:
            px = p['x'] * w
            py = p['y'] * (h - 30) + 10
            color = QColor(c_palette[p['color_idx']])
            color.setAlpha(int(p['alpha'] * 255))
            r = p['size'] * beat_scale
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), r, r)

        aurora_grad = QLinearGradient(0, h - 60, 0, h - 26)
        c_aur = QColor(self.t['accent'])
        c_aur.setAlpha(int(self.engine.beat_strength * 100 + 30))
        aurora_grad.setColorAt(0.0, c_aur)
        aurora_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(aurora_grad)
        painter.drawRect(QRectF(0, h - 60, w, 34))

    def _paint_mirror_wave(self, painter, w, h):
        """Dual symmetrical mirror waveforms surging with beat dynamics."""
        mid_y = (h - 26) / 2.0 + 10.0
        base_amp = max(20.0, (h - 70) * 0.40)
        beat_surge = 1.0 + (self.engine.beat_strength * 0.85 if self.engine.playing else 0.0)
        amp = base_amp * beat_surge
        t = self.engine.time

        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        step = max(3, w // 120)
        xs = list(range(0, w + 1, step))
        if xs[-1] != w: xs.append(w)
        num_levels = max(1, len(self.engine.levels))

        top_path = QPainterPath()
        bot_path = QPainterPath()
        top_path.moveTo(0, mid_y)
        bot_path.moveTo(0, mid_y)

        for x in xs:
            rel = x / float(w)
            band_idx = min(num_levels - 1, int(rel * num_levels))
            # clamp: a negative level would make lvl ** 0.5 complex
            lvl = max(0.0, min(1.0, self.engine.levels[band_idx]))
            disp = (math.sin(rel * 16.0 + t * 4.2) * 0.65 + math.sin(rel * 28.0 - t * 3.5) * 0.35) * amp * lvl
            top_path.lineTo(x, mid_y - abs(disp))
            bot_path.lineTo(x, mid_y + abs(disp))

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, c_accent)
        grad.setColorAt(1.0, c_accent2)
        painter.setPen(QPen(QBrush(grad), 2.2))
        painter.drawPath(top_path)
        painter.drawPath(bot_path)

    def _paint_circular_bars(self, painter, w, h):
        """Pulsing 360-degree radial spectrum bars emanating from audio center."""
        cx = w / 2.0
        cy = (h - 26) / 2.0 + 10.0
        r_base = min(cx, cy) * 0.45
        beat_scale = 1.0 + (self.engine.beat_strength * 0.40 if self.engine.playing else 0.0)
        r_inner = r_base * beat_scale

        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        num_spokes = 64
        for i in range(num_spokes):
            angle = (i / float(num_spokes)) * 2.0 * math.pi
            lvl = self.engine.levels[i % len(self.engine.levels)]
            bar_len = 8.0 + lvl * (min(cx, cy) * 0.45)
            x1 = cx + math.cos(angle) * r_inner
            y1 = cy + math.sin(angle) * r_inner
            x2 = cx + math.cos(angle) * (r_inner + bar_len)
            y2 = cy + math.sin(angle) * (r_inner + bar_len)

            frac = i / float(num_spokes)
            c = QColor(
                int(c_accent.red() * (1 - frac) + c_accent2.red() * frac),
                int(c_accent.green() * (1 - frac) + c_accent2.green() * frac),
                int(c_accent.blue() * (1 - frac) + c_accent2.blue() * frac)
            )
            painter.setPen(QPen(c, 2.0))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _paint_dna_helix(self, painter, w, h):
        """Intertwined neon DNA strands linked by spectrum rungs."""
        mid_y = (h - 26) / 2.0 + 10.0
        t = self.engine.time
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        step = max(4, w // 80)
        xs = list(range(0, w + 1, step))
        num_levels = max(1, len(self.engine.levels))

        for idx, x in enumerate(xs):
            rel = x / float(w)
            band_idx = min(num_levels - 1, int(rel * num_levels))
            # clamp: a negative level would make lvl ** 0.5 complex
            lvl = max(0.0, min(1.0, self.engine.levels[band_idx]))
            amp = 30.0 + lvl * 40.0
            phase = rel * 18.0 + t * 4.0

            y_strand1 = mid_y + math.sin(phase) * amp
            y_strand2 = mid_y - math.sin(phase) * amp

            # Connecting rung
            painter.setPen(QPen(QColor(255, 255, 255, int(lvl * 180 + 30)), 1.2))
            painter.drawLine(QPointF(x, y_strand1), QPointF(x, y_strand2))

            # Nodes
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c_accent)
            painter.drawEllipse(QPointF(x, y_strand1), 2.5, 2.5)
            painter.setBrush(c_accent2)
            painter.drawEllipse(QPointF(x, y_strand2), 2.5, 2.5)

    def _paint_plasma_grid(self, painter, w, h):
        """Matrix plasma grid dancing to live frequency energy."""
        cols = 36
        rows = 12
        cell_w = w / float(cols)
        cell_h = (h - 36) / float(rows)
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        for c in range(cols):
            lvl = self.engine.levels[c % len(self.engine.levels)]
            for r in range(rows):
                frac_r = (rows - 1 - r) / float(rows)
                if lvl >= frac_r:
                    color = QColor(
                        int(c_accent.red() * (1 - frac_r) + c_accent2.red() * frac_r),
                        int(c_accent.green() * (1 - frac_r) + c_accent2.green() * frac_r),
                        int(c_accent.blue() * (1 - frac_r) + c_accent2.blue() * frac_r),
                        int(180 + frac_r * 75)
                    )
                    painter.setBrush(color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    x = c * cell_w + 1.5
                    y = r * cell_h + 12
                    painter.drawRoundedRect(QRectF(x, y, max(1.0, cell_w - 3.0), max(1.0, cell_h - 2.5)), 2, 2)

    def _paint_neon_oscilloscope(self, painter, w, h):
        """Electric phosphor oscilloscope with CRT grid and luminous glow beam."""
        mid_y = (h - 26) / 2.0 + 10.0
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        # CRT Background Grid
        grid_pen = QPen(QColor(255, 255, 255, 16), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for gx in range(0, w, 40):
            painter.drawLine(gx, 10, gx, h - 16)
        for gy in range(int(mid_y - 80), int(mid_y + 90), 25):
            painter.drawLine(0, gy, w, gy)

        # Center line
        painter.setPen(QPen(QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 45), 1))
        painter.drawLine(0, int(mid_y), w, int(mid_y))

        # Build beam path
        amp = max(25.0, (h - 60) * 0.45) * (1.2 if self.engine.beat else 0.85)
        step = max(2, w // 160)
        xs = list(range(0, w + 1, step))
        if xs[-1] != w: xs.append(w)
        num_levels = max(1, len(self.engine.levels))
        t = self.engine.time

        beam_path = QPainterPath()
        beam_path.moveTo(0, mid_y)
        for x in xs:
            rel = x / float(w)
            band_idx = min(num_levels - 1, int(rel * num_levels))
            # clamp: a negative level would make lvl ** 0.5 complex
            lvl = max(0.0, min(1.0, self.engine.levels[band_idx]))
            wave1 = math.sin(rel * 14.0 - t * 6.5) * 0.65
            wave2 = math.sin(rel * 32.0 + t * 4.8) * 0.35
            disp = (wave1 + wave2) * amp * lvl
            beam_path.lineTo(x, mid_y + disp)

        # Glow layer (outer)
        glow_col = QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 70)
        painter.setPen(QPen(glow_col, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(beam_path)

        # Mid beam
        mid_col = QColor(c_accent2.red(), c_accent2.green(), c_accent2.blue(), 180)
        painter.setPen(QPen(mid_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(beam_path)

        # Core sharp beam
        painter.setPen(QPen(QColor(255, 255, 255, 240), 1.0, Qt.PenStyle.SolidLine))
        painter.drawPath(beam_path)

    def _paint_cyber_tunnel(self, painter, w, h):
        """Hyperspace 3D cyber vortex tunnel rushing toward vanishing point."""
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        max_r = math.hypot(cx, cy) * 0.95
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        beat_boost = 1.35 if self.engine.beat else 1.0
        t = self.anim_phase * 0.8

        # 10 radial perspective guide rails
        painter.setPen(QPen(QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 40), 1))
        for i in range(12):
            angle = i * (math.pi / 6.0) + t * 0.15
            rx = cx + math.cos(angle) * max_r
            ry = cy + math.sin(angle) * max_r
            painter.drawLine(int(cx), int(cy), int(rx), int(ry))

        # Concentric polygonal warp rings
        rings = 14
        for r_idx in range(rings):
            phase = (r_idx / float(rings) + t * 0.25) % 1.0
            r = (phase ** 2.2) * max_r * beat_boost
            if r < 4.0:
                continue
            alpha = int(min(240, phase * 255))
            color = QColor(
                int(c_accent.red() * (1 - phase) + c_accent2.red() * phase),
                int(c_accent.green() * (1 - phase) + c_accent2.green() * phase),
                int(c_accent.blue() * (1 - phase) + c_accent2.blue() * phase),
                alpha
            )
            pen_w = max(1.0, 2.8 * phase)
            painter.setPen(QPen(color, pen_w))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Draw octagon ring
            ring_path = QPainterPath()
            sides = 8
            for s in range(sides + 1):
                ang = s * (math.pi * 2 / sides) + t * (0.2 if r_idx % 2 == 0 else -0.2)
                # Jitter ring vertices slightly with audio levels
                band_idx = (r_idx + s) % len(self.engine.levels)
                lvl = self.engine.levels[band_idx]
                rad = r * (1.0 + lvl * 0.25)
                px = cx + math.cos(ang) * rad
                py = cy + math.sin(ang) * rad
                if s == 0:
                    ring_path.moveTo(px, py)
                else:
                    ring_path.lineTo(px, py)
            painter.drawPath(ring_path)

    def _paint_hologram_rings(self, painter, w, h):
        """Planetary celestial holographic orbital rings with rotating nodes."""
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t['accent3'])

        # Central pulsating core orb
        core_r = 18.0 + (self.engine.beat_strength * 22.0 if self.engine.playing else 4.0)
        core_grad = QRadialGradient(cx, cy, core_r)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 250))
        core_grad.setColorAt(0.4, QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 200))
        core_grad.setColorAt(1.0, QColor(c_accent2.red(), c_accent2.green(), c_accent2.blue(), 0))
        painter.setBrush(core_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

        # 6 Tilted 3D holographic orbital rings
        ring_counts = 6
        for i in range(ring_counts):
            frac = (i + 1) / float(ring_counts)
            rx = 40.0 + frac * (w * 0.40)
            ry = 15.0 + frac * ((h - 40) * 0.38)
            tilt_deg = -25.0 + i * 10.0

            painter.save()
            painter.translate(cx, cy)
            painter.rotate(tilt_deg)

            lvl = self.engine.levels[(i * 4) % len(self.engine.levels)]
            ring_col = QColor(c_accent if i % 2 == 0 else c_accent2)
            ring_col.setAlpha(int(60 + lvl * 180))
            painter.setPen(QPen(ring_col, 1.5 + lvl * 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), rx * (1.0 + lvl * 0.2), ry * (1.0 + lvl * 0.2))

            # Orbital beacon node
            node_ang = self.anim_phase * (0.8 + i * 0.3)
            nx = math.cos(node_ang) * rx
            ny = math.sin(node_ang) * ry
            painter.setBrush(QColor(255, 255, 255, 240))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(nx, ny), 3.5, 3.5)
            painter.restore()

    def _paint_laser_strobe(self, painter, w, h):
        """Concert stage apex laser fan with stroboscopic beat bursts."""
        apex_x, apex_y = w / 2.0, 10.0
        num_lasers = 22
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        sweep = math.sin(self.anim_phase * 1.2) * (w * 0.25)
        floor_y = h - 16.0

        # Stage floor glow
        floor_grad = QLinearGradient(0, floor_y - 40, 0, floor_y)
        c_fl = QColor(c_accent.red(), c_accent.green(), c_accent.blue(), int(40 + self.engine.beat_strength * 70))
        floor_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        floor_grad.setColorAt(1.0, c_fl)
        painter.fillRect(QRectF(0, floor_y - 40, w, 40), floor_grad)

        # Draw sweeping laser beams
        for i in range(num_lasers):
            rel = (i / float(num_lasers - 1)) - 0.5
            target_x = (w / 2.0) + (rel * w * 1.1) + sweep * (1.0 - abs(rel))
            target_y = floor_y

            lvl = self.engine.levels[i % len(self.engine.levels)]
            strobe_alpha = int(80 + lvl * 160 + (80 if self.engine.beat else 0))
            color = c_accent if i % 2 == 0 else c_accent2
            laser_col = QColor(color.red(), color.green(), color.blue(), min(255, strobe_alpha))

            # Laser beam line
            painter.setPen(QPen(laser_col, 1.6 + lvl * 2.0))
            painter.drawLine(int(apex_x), int(apex_y), int(target_x), int(target_y))

            # Beam hit sparkle on floor
            painter.setBrush(QColor(255, 255, 255, strobe_alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(target_x, target_y), 2.5 + lvl * 3.0, 1.5 + lvl * 1.5)

        # Apex emitter diode glow
        painter.setBrush(QColor(255, 255, 255, 240))
        painter.drawEllipse(QPointF(apex_x, apex_y), 5.0, 5.0)

    def _paint_quantum_matrix(self, painter, w, h):
        """Lattice of quantum particles undulating with dynamic entanglement vectors."""
        cols = 20
        rows = 8
        spacing_x = w / float(cols + 1)
        spacing_y = (h - 40) / float(rows + 1)
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        t = self.anim_phase

        pts = []
        for r in range(rows):
            for c in range(cols):
                bx = (c + 1) * spacing_x
                by = (r + 1) * spacing_y + 12
                dist_c = math.hypot(bx - cx, by - cy)
                band_idx = int((dist_c / (w * 0.5)) * len(self.engine.levels)) % len(self.engine.levels)
                lvl = self.engine.levels[band_idx]

                # Wave displacement
                wave = math.sin(dist_c * 0.05 - t * 4.0) * (lvl * 18.0)
                px = bx + math.cos(t * 2.0 + r) * (lvl * 6.0)
                py = by + wave
                pts.append((px, py, lvl))

        # Interconnecting quantum vector strings
        for i in range(len(pts)):
            px, py, lvl = pts[i]
            # Connect right neighbor
            if (i + 1) % cols != 0:
                nx, ny, nlvl = pts[i + 1]
                avg_lvl = (lvl + nlvl) * 0.5
                painter.setPen(QPen(QColor(c_accent.red(), c_accent.green(), c_accent.blue(), int(30 + avg_lvl * 180)), 1))
                painter.drawLine(int(px), int(py), int(nx), int(ny))
            # Connect bottom neighbor
            if i + cols < len(pts):
                bx, by, blvl = pts[i + cols]
                avg_lvl = (lvl + blvl) * 0.5
                painter.setPen(QPen(QColor(c_accent2.red(), c_accent2.green(), c_accent2.blue(), int(25 + avg_lvl * 160)), 1))
                painter.drawLine(int(px), int(py), int(bx), int(by))

            # Dot node
            painter.setBrush(QColor(255, 255, 255, int(120 + lvl * 135)))
            painter.setPen(Qt.PenStyle.NoPen)
            r_dot = 2.0 + lvl * 3.0
            painter.drawEllipse(QPointF(px, py), r_dot, r_dot)

    def _paint_hex_hive(self, painter, w, h):
        """Cybernetic honeycomb matrix pulsating from center outward."""
        hex_r = 17.0
        dx = hex_r * 1.5
        dy = hex_r * math.sqrt(3)
        cols = int(w / dx) + 2
        rows = int((h - 30) / dy) + 2
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        for row in range(rows):
            for col in range(cols):
                hx = col * dx
                hy = row * dy + (dy / 2.0 if col % 2 == 1 else 0.0) + 14.0
                dist_c = math.hypot(hx - cx, hy - cy)
                max_d = math.hypot(cx, cy)
                rel_d = min(1.0, dist_c / max(1.0, max_d))
                band_idx = int(rel_d * len(self.engine.levels)) % len(self.engine.levels)
                lvl = self.engine.levels[band_idx]

                if lvl < 0.08:
                    continue

                r_curr = hex_r * (0.45 + lvl * 0.55)
                alpha = int(40 + lvl * 190)
                color = QColor(
                    int(c_accent.red() * (1 - rel_d) + c_accent2.red() * rel_d),
                    int(c_accent.green() * (1 - rel_d) + c_accent2.green() * rel_d),
                    int(c_accent.blue() * (1 - rel_d) + c_accent2.blue() * rel_d),
                    alpha
                )
                painter.setPen(QPen(color, 1.2))
                fill_col = QColor(color)
                fill_col.setAlpha(int(alpha * 0.35))
                painter.setBrush(fill_col)

                # Hexagon path
                hex_path = QPainterPath()
                for i in range(6):
                    ang = i * (math.pi / 3.0)
                    px = hx + math.cos(ang) * r_curr
                    py = hy + math.sin(ang) * r_curr
                    if i == 0:
                        hex_path.moveTo(px, py)
                    else:
                        hex_path.lineTo(px, py)
                hex_path.closeSubpath()
                painter.drawPath(hex_path)

    def _paint_waterfall(self, painter, w, h):
        """Cascading spectral thermal waterfall spectrogram."""
        if not self.waterfall_history:
            return
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t['accent3'])
        top_y = 36.0
        bot_y = h - 16.0
        tot_h = bot_y - top_y
        row_h = tot_h / max(1.0, float(len(self.waterfall_history)))

        for r_idx, snapshot in enumerate(self.waterfall_history):
            y = top_y + r_idx * row_h
            n_bands = len(snapshot)
            if n_bands == 0:
                continue
            col_w = w / float(n_bands)
            age_fade = 1.0 - (r_idx / float(len(self.waterfall_history)))

            for b_idx, lvl in enumerate(snapshot):
                if lvl < 0.02:
                    continue
                x = b_idx * col_w
                val = min(1.0, lvl * 1.2)
                alpha = int(val * 240 * age_fade)
                if val < 0.5:
                    f = val * 2.0
                    col = QColor(
                        int(c_accent.red() * (1 - f) + c_accent2.red() * f),
                        int(c_accent.green() * (1 - f) + c_accent2.green() * f),
                        int(c_accent.blue() * (1 - f) + c_accent2.blue() * f),
                        alpha
                    )
                else:
                    f = (val - 0.5) * 2.0
                    col = QColor(
                        int(c_accent2.red() * (1 - f) + c_accent3.red() * f),
                        int(c_accent2.green() * (1 - f) + c_accent3.green() * f),
                        int(c_accent2.blue() * (1 - f) + c_accent3.blue() * f),
                        alpha
                    )
                painter.fillRect(QRectF(x, y, max(1.0, col_w - 0.5), max(1.0, row_h)), col)

    def _paint_stereo_scope(self, painter, w, h):
        """Lissajous stereo phase vector showing mono/stereo soundstage."""
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        radius = min(w * 0.40, (h - 60) * 0.45)
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        # Crosshair polar scope
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Lissajous curve
        num_pts = 240
        t = self.engine.time * 2.5
        bass = self.engine.bass_energy * 0.4
        pts_path = QPainterPath()

        for i in range(num_pts):
            th = (i / float(num_pts)) * math.pi * 2.0
            band_l = self.engine.levels[i % len(self.engine.levels)]
            band_r = self.engine.levels[(i * 3) % len(self.engine.levels)]
            x_val = math.sin(th * 2.0 + t + bass) * (0.6 + band_l * 0.4)
            y_val = math.sin(th * 3.0 - t * 0.8) * (0.6 + band_r * 0.4)
            px = cx + x_val * radius * (1.0 + self.engine.beat_strength * 0.3)
            py = cy + y_val * radius * (1.0 + self.engine.beat_strength * 0.3)
            if i == 0:
                pts_path.moveTo(px, py)
            else:
                pts_path.lineTo(px, py)

        # Glow layer
        painter.setPen(QPen(QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 80), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(pts_path)

        # Inner beam
        painter.setPen(QPen(QColor(c_accent2.red(), c_accent2.green(), c_accent2.blue(), 230), 1.6))
        painter.drawPath(pts_path)

    def _paint_sound_aurora(self, painter, w, h):
        """Ethereal polar borealis sound curtains undulating across the horizon."""
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t['accent3'])
        bot_y = h - 20.0
        t = self.anim_phase * 0.5
        num_layers = 4

        for l_idx in range(num_layers):
            layer_frac = l_idx / float(num_layers)
            path = QPainterPath()
            path.moveTo(0, bot_y)

            step = max(4, w // 90)
            xs = list(range(0, w + 1, step))
            if xs[-1] != w: xs.append(w)

            for x in xs:
                rel = x / float(w)
                band = min(len(self.engine.levels) - 1, int(rel * len(self.engine.levels)))
                lvl = self.engine.levels[band]
                wave1 = math.sin(rel * 6.0 + t * (1.2 + l_idx * 0.3)) * 30.0
                wave2 = math.cos(rel * 12.0 - t * 0.8) * 18.0
                peak_h = (50.0 + lvl * 90.0 + wave1 + wave2) * (1.0 - layer_frac * 0.25)
                path.lineTo(x, max(15.0, bot_y - peak_h))

            path.lineTo(w, bot_y)
            path.closeSubpath()

            grad = QLinearGradient(0, 15, 0, bot_y)
            color_top = c_accent if l_idx % 2 == 0 else c_accent2
            alpha = int(45 + (1.0 - layer_frac) * 65 + (35 if self.engine.beat else 0))
            grad.setColorAt(0.0, QColor(color_top.red(), color_top.green(), color_top.blue(), alpha))
            grad.setColorAt(0.6, QColor(c_accent3.red(), c_accent3.green(), c_accent3.blue(), int(alpha * 0.6)))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

    def _paint_retro_synth_grid(self, painter, w, h):
        """80s Outrun Synthwave rolling perspective horizon with reactive sun."""
        cx = w / 2.0
        horizon_y = h * 0.44
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])

        # Neon Retrowave Sun on horizon
        sun_r = min(w * 0.16, h * 0.26) * (1.15 if self.engine.beat else 1.0)
        sun_grad = QLinearGradient(cx, horizon_y - sun_r, cx, horizon_y)
        sun_grad.setColorAt(0.0, QColor('#ff007f'))
        sun_grad.setColorAt(0.5, QColor('#ff8800'))
        sun_grad.setColorAt(1.0, QColor('#ffee00'))
        painter.setBrush(sun_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawChord(QRectF(cx - sun_r, horizon_y - sun_r, sun_r * 2, sun_r * 2), 0, 180 * 16)

        # Sun blinds horizontal slices
        painter.setPen(QPen(QColor(self.t['bg']), 2))
        for s in range(5):
            sy = horizon_y - (s + 1) * (sun_r * 0.16)
            painter.drawLine(int(cx - sun_r), int(sy), int(cx + sun_r), int(sy))

        # Perspective ground lines
        ground_pen = QPen(QColor(c_accent.red(), c_accent.green(), c_accent.blue(), 140), 1.2)
        painter.setPen(ground_pen)

        # Vanishing rails
        rails = 18
        for i in range(rails):
            rel = (i / float(rails - 1)) - 0.5
            bx = cx + rel * w * 1.8
            painter.drawLine(int(cx), int(horizon_y), int(bx), int(h - 14))

        # Forward-rolling horizontal lines
        t = (self.anim_phase * 0.7) % 1.0
        for i in range(10):
            p = ((i / 10.0) + t * 0.1) % 1.0
            y = horizon_y + (p ** 2.2) * (h - 14 - horizon_y)
            alpha = int(p * 220)
            painter.setPen(QPen(QColor(c_accent2.red(), c_accent2.green(), c_accent2.blue(), alpha), 1.2))
            painter.drawLine(0, int(y), w, int(y))

    def _paint_starburst_galaxy(self, painter, w, h):
        """Swirling galactic spiral arms with audio shockwave bursts."""
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        c_accent3 = QColor(self.t['accent3'])
        max_r = min(cx, cy) * 0.95

        # Shockwave ring on beat
        if self.engine.beat_strength > 0.3:
            sw_r = max_r * self.engine.beat_strength
            sw_col = QColor(c_accent.red(), c_accent.green(), c_accent.blue(), int(self.engine.beat_strength * 160))
            painter.setPen(QPen(sw_col, 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), sw_r, sw_r)

        # Star field spiral
        for star in self.starburst_stars:
            r = star['dist'] * max_r
            lvl = self.engine.levels[int(star['dist'] * len(self.engine.levels)) % len(self.engine.levels)]
            ang = star['angle'] + (r * 0.02)
            sx = cx + math.cos(ang) * (r + lvl * 15.0)
            sy = cy + math.sin(ang) * (r + lvl * 15.0)

            col = [c_accent, c_accent2, c_accent3][star['color_idx']]
            painter.setBrush(QColor(col.red(), col.green(), col.blue(), int(160 + lvl * 95)))
            painter.setPen(Qt.PenStyle.NoPen)
            sz = star['size'] * (1.0 + lvl * 0.8)
            painter.drawEllipse(QPointF(sx, sy), sz, sz)

        # Core Pulsar
        core_r = 14.0 + self.engine.bass_energy * 18.0
        core_grad = QRadialGradient(cx, cy, core_r)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.5, c_accent)
        core_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(core_grad)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

    def _paint_fractal_kaleidoscope(self, painter, w, h):
        """8-fold symmetrical kaleidoscope reflecting melodic petals in 2D."""
        cx, cy = w / 2.0, (h - 26) / 2.0 + 10.0
        c_accent = QColor(self.t['accent'])
        c_accent2 = QColor(self.t['accent2'])
        r_scale = min(cx, cy) * 0.85
        petals = 8
        t = self.anim_phase * 0.5

        painter.save()
        painter.translate(cx, cy)

        for p_idx in range(petals):
            painter.save()
            painter.rotate(p_idx * (360.0 / petals))

            path = QPainterPath()
            path.moveTo(0, 0)
            pts = 20
            for i in range(1, pts):
                frac = i / float(pts)
                band = (i * 2) % len(self.engine.levels)
                lvl = self.engine.levels[band]
                ang = frac * (math.pi / 4.0)
                r = frac * r_scale * (0.6 + lvl * 0.6)
                disp = math.sin(frac * 8.0 + t * 3.0) * (lvl * 25.0)
                px = math.cos(ang) * r + disp
                py = math.sin(ang) * r
                path.lineTo(px, py)
            path.closeSubpath()

            col = c_accent if p_idx % 2 == 0 else c_accent2
            fill_col = QColor(col.red(), col.green(), col.blue(), int(40 + self.engine.bass_energy * 60))
            painter.setBrush(fill_col)
            painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 180), 1.2))
            painter.drawPath(path)
            painter.restore()

        painter.restore()

    def _paint_hud(self, painter, w, h):
        if not getattr(self, 'show_hud', True):
            return
        painter.setPen(Qt.PenStyle.NoPen)
        hud_bg = QColor(0, 0, 0, 110)
        painter.setBrush(hud_bg)
        painter.drawRoundedRect(QRectF(10, 8, w - 20, 26), 6, 6)

        font = QFont('Segoe UI', 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(self.t['accent']))
        mode_text = f"{self.MODE_LABELS.get(self.mode, 'SPECTRUM')} (CLICK TO CYCLE)"
        painter.drawText(22, 25, mode_text)

        led_x = w - 105
        led_y = 21
        led_color = QColor('#00ff88') if self.engine.beat else QColor(255, 255, 255, 60)
        painter.setBrush(led_color)
        painter.drawEllipse(QPointF(led_x, led_y), 4.0, 4.0)

        font_sub = QFont('Segoe UI', 8)
        painter.setFont(font_sub)
        painter.setPen(QColor(self.t['text_dim']))
        painter.drawText(led_x + 12, 25, f"{int(self.fps)} FPS")


# ─────────────────────────────────────────────────────────────────────────────
# BULK & SINGLE YOUTUBE DOWNLOADER
# ─────────────────────────────────────────────────────────────────────────────

class YouTubeBulkDownloader(QThread):
    queueProgress = pyqtSignal(int, int, str)      # current_idx (1-based), total_urls, url_or_title
    itemProgress = pyqtSignal(int, str)            # pct, speed
    itemFinished = pyqtSignal(int, str, dict)      # item_idx, file_path, metadata
    itemError = pyqtSignal(int, str, str)          # item_idx, url, error_msg
    allFinished = pyqtSignal(int, int)             # success_count, fail_count

    def __init__(self, urls, quality='FLAC', output_dir=None):
        super().__init__()
        if isinstance(urls, str):
            self.urls = [urls.strip()]
        else:
            self.urls = [u.strip() for u in urls if u and u.strip()]
        self.quality = quality
        self.output_dir = Path(output_dir) if output_dir else Path.home() / 'Music' / 'AudioPlayerDownloads'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        q_lower = str(self.quality).lower()
        if 'flac' in q_lower or 'lossless' in q_lower:
            codec = 'flac'
            kbps = '0'
        elif 'mp3' in q_lower:
            codec = 'mp3'
            if '320' in q_lower:
                kbps = '320'
            elif '256' in q_lower:
                kbps = '256'
            elif '192' in q_lower:
                kbps = '192'
            else:
                kbps = '320'
        else:
            codec = 'flac'
            kbps = '0'

        success_cnt = 0
        fail_cnt = 0

        for idx, url in enumerate(self.urls):
            if self.is_cancelled:
                break
            self.queueProgress.emit(idx + 1, len(self.urls), url)

            def _hook(d):
                if self.is_cancelled:
                    raise Exception("Download cancelled by user.")
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('_speed_str', '')
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        self.itemProgress.emit(pct, speed)

            opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(self.output_dir / '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [_hook],
            }
            if 'original' not in q_lower:
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': codec,
                    'preferredquality': kbps,
                }]

            if FFMPEG_DIR:
                opts['ffmpeg_location'] = FFMPEG_DIR

            cookie_path = DATA_DIR / 'cookies.txt'
            if cookie_path.exists():
                opts['cookiefile'] = str(cookie_path)

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'Unknown')
                    expected_ext = f".{codec}"
                    target_file = None

                    # Check exact requested title matches
                    for f in sorted(self.output_dir.glob(f"*{expected_ext}"), key=os.path.getmtime, reverse=True):
                        if (title[:12].lower() in f.stem.lower()) or (f.stat().st_mtime > time.time() - 30):
                            target_file = str(f)
                            break
                    if not target_file:
                        # Fallback scan for any newly written audio/media file
                        candidates = sorted(self.output_dir.glob("*.*"), key=os.path.getmtime, reverse=True)
                        for cand in candidates:
                            if cand.suffix.lower() in MEDIA_EXTS and cand.stat().st_mtime > time.time() - 60:
                                target_file = str(cand)
                                break
                    if not target_file:
                        target_file = str(self.output_dir / f"{title}.{codec}")

                    meta = {
                        'title': title,
                        'uploader': info.get('uploader', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'codec': codec
                    }
                    self.itemFinished.emit(idx, target_file, meta)
                    success_cnt += 1
            except Exception as e:
                if self.is_cancelled:
                    break
                self.itemError.emit(idx, url, str(e))
                fail_cnt += 1

        self.allFinished.emit(success_cnt, fail_cnt)


class YouTubeDownloader(YouTubeBulkDownloader):
    """Single-item backward compatibility wrapper."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, dict)
    error = pyqtSignal(str)

    def __init__(self, url, quality='FLAC', output_dir=None):
        super().__init__([url], quality, output_dir)
        self.itemProgress.connect(self.progress.emit)
        self.itemFinished.connect(lambda idx, f, m: self.finished.emit(f, m))
        self.itemError.connect(lambda idx, u, err: self.error.emit(err))


# ─────────────────────────────────────────────────────────────────────────────
# REORDERABLE PLAYLIST TABLE WIDGET (DRAG-AND-DROP & KEYBOARD REORDERING)
# ─────────────────────────────────────────────────────────────────────────────

class ReorderablePlaylistTable(QTableWidget):
    """High-performance playlist table supporting drag-and-drop song reordering."""
    rowReordered = pyqtSignal(int, int)  # (from_row, to_row)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._drag_start_row = -1

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                self._drag_start_row = item.row()
            else:
                self._drag_start_row = -1
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.source() == self:
            if self._drag_start_row < 0:
                self._drag_start_row = self.currentRow()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() == self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.source() == self:
            pos = event.position().toPoint()
            target_item = self.itemAt(pos)
            if target_item:
                target_row = target_item.row()
            else:
                target_row = max(0, self.rowCount() - 1)

            source_row = self._drag_start_row
            if source_row < 0 or source_row >= self.rowCount():
                source_row = self.currentRow()

            if 0 <= source_row < self.rowCount() and 0 <= target_row < self.rowCount() and source_row != target_row:
                event.accept()
                self.rowReordered.emit(source_row, target_row)
                return
        event.ignore()

    def keyPressEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ControlModifier):
            if event.key() == Qt.Key.Key_Up:
                curr = self.currentRow()
                if curr > 0:
                    self.rowReordered.emit(curr, curr - 1)
                    return
            elif event.key() == Qt.Key.Key_Down:
                curr = self.currentRow()
                if 0 <= curr < self.rowCount() - 1:
                    self.rowReordered.emit(curr, curr + 1)
                    return
        super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN STUDIO APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedWorkspacePanel(QWidget):
    """
    Single merged workspace panel — Songs & Library, 7-Band EQ / DSP,
    YouTube Downloader and the Shortcuts guide all live in ONE pane
    (no tabs), arranged as a two-column splitter so everything is visible
    at the same time.

    Exposes the thin slice of the QTabWidget API the settings-persistence
    layer touches so layout state keeps round-tripping unchanged.
    """
    currentChanged = pyqtSignal(int)

    def currentIndex(self):
        return 0

    def count(self):
        return 1

    def setCurrentIndex(self, idx):
        pass

    def widget(self, idx):
        return self


# ═════════════════════════════════════════════════════════════════════════════
#  REMIX RACK ENGINE — real, audible DSP
#
#  Qt's QMediaPlayer exposes no insert-effect chain, which is exactly why the
#  previous rack's reverb/echo/width/drive knobs moved pixels but never the
#  sound. The rack is now realised for real: the track is rendered through an
#  ffmpeg filter graph into a cached WAV and the player is pointed at that.
#  Renders are debounced, content-hashed, cached, pruned and run off-thread;
#  if ffmpeg is missing the player simply keeps the untouched original.
# ═════════════════════════════════════════════════════════════════════════════

FX_CACHE_DIR = DATA_DIR / 'fx_cache'
FX_CACHE_KEEP = 6
FX_RENDER_WAV_ARGS = ['-c:a', 'pcm_s16le', '-ac', '2']
FX_DEFAULT_RATE = 48000
FX_LAST_RENDER = {'seconds': 0.0, 'error': '', 'ffmpeg': '', 'graph': ''}

# key -> (caption, group, lo, hi, default, divisor)
FX_RACK_SPEC = [
    ('reverb',   'REVERB',         'space',    0,  100,   0,  1.0),
    ('echo',     'ECHO / DELAY',   'space',    0,  100,   0,  1.0),
    ('width',    'STEREO WIDTH',   'space',    0,  200, 100,  1.0),
    ('mix',      'DRY / WET',      'space',    0,  100, 100,  1.0),
    ('sub',      'SUB BASS',       'tone',     0,  100,   0,  1.0),
    ('bass',     'BASS SHELF',     'tone',   -12,   12,   0,  1.0),
    ('treble',   'TREBLE SHELF',   'tone',   -12,   12,   0,  1.0),
    ('presence', 'PRESENCE',       'tone',     0,  100,   0,  1.0),
    ('gain',     'OUT GAIN',       'tone',   -12,   12,   0,  1.0),
    ('chorus',   'CHORUS',         'motion',   0,  100,   0,  1.0),
    ('vibrato',  'VIBRATO',        'motion',   0,  100,   0,  1.0),
    ('phaser',   'PHASER',         'motion',   0,  100,   0,  1.0),
    ('tone',     'TONE / FILTER',  'motion',-100,  100,   0,  1.0),
    ('drive',    'DRIVE',          'char',     0,  100,   0,  1.0),
    ('lofi',     'LO-FI CRUSH',    'char',     0,  100,   0,  1.0),
]
FX_RACK_GROUPS = [('space', 'SPACE & DEPTH'), ('tone', 'TONE'),
                  ('motion', 'MOTION'), ('char', 'CHARACTER')]

FX_PRESETS = {
    'Flat / Dry':    {},
    'Small Room':    {'reverb': 26, 'width': 112},
    'Cathedral':     {'reverb': 80, 'echo': 24, 'width': 136, 'mix': 86},
    'Slowed + Verb': {'reverb': 58, 'echo': 20, 'tone': -38, 'bass': 2},
    'Club':          {'sub': 58, 'bass': 4, 'treble': 3, 'drive': 36, 'width': 122},
    'Wide Cinema':   {'width': 158, 'bass': 3, 'presence': 18},
    'Lo-Fi Tape':    {'lofi': 46, 'tone': -42, 'bass': 2, 'vibrato': 9, 'drive': 22},
    'Telephone':     {'tone': 62, 'gain': 3, 'drive': 14},
    'Vocal Booth':   {'presence': 46, 'treble': 3, 'reverb': 14},
    'Dreamy':        {'chorus': 46, 'reverb': 46, 'phaser': 20, 'width': 140},
    'Night Drive':   {'sub': 40, 'drive': 28, 'width': 120, 'treble': 2, 'reverb': 18},
    '8-Bit Game':    {'lofi': 72, 'tone': 24, 'drive': 40},
}


def fx_format(key, value):
    if key in ('bass', 'treble', 'gain'):
        if abs(value) < 0.05:
            return '0 dB'
        return ('+%0.1f dB' % value) if value > 0 else ('%0.1f dB' % value)
    if key == 'reverb' and value < 0.5:
        return 'dry'
    return '%d%%' % int(round(value))


def fx_defaults():
    base = {_k: float(d) for (_k, _c, _g, _lo, _hi, d, _s) in FX_RACK_SPEC}
    base['pitch'] = 0.0          # owned by its own slider, still part of the render
    return base


def fx_rack_is_neutral(values):
    """True when no rack control would change the sound at all."""
    for key, default in fx_defaults().items():
        if abs(float(values.get(key, default)) - default) > 0.001:
            return False
    return True


def _fx_dsp_filters(v, rate=FX_DEFAULT_RATE):
    """Ordered ffmpeg filters for the rack values: motion, then tone, then space/colour."""
    out = ['aformat=channel_layouts=stereo']
    rate = int(rate or FX_DEFAULT_RATE)

    # ── PITCH ── (transpose only: the atempo below restores the length, so the
    # song keeps its speed. Previously pitch was folded into setPlaybackRate,
    # which made the whole track speed up whenever you raised it.)
    pitch = float(v.get('pitch', 0.0))
    if abs(pitch) > 0.01:
        ratio = 2.0 ** (pitch / 12.0)
        out.append('asetrate=%d' % int(rate * ratio))
        out.append('aresample=%d' % rate)
        out.append('atempo=%0.6f' % (1.0 / ratio))

    # ── MOTION ──
    ch = float(v.get('chorus', 0.0)) / 100.0
    if ch > 0.01:
        out.append('chorus=0.6:0.9:%d:0.4:0.3:2' % int(40 + 30 * ch))
    vib = float(v.get('vibrato', 0.0)) / 100.0
    if vib > 0.01:
        out.append('vibrato=f=%0.2f:d=%0.3f' % (1.5 + 8.5 * vib, min(1.0, 0.1 + 0.9 * vib)))
    ph = float(v.get('phaser', 0.0)) / 100.0
    if ph > 0.01:
        out.append('aphaser=in_gain=0.4:out_gain=0.74:delay=%0.1f:decay=%0.2f:speed=%0.2f:type=t'
                   % (2.0 + 2.0 * ph, 0.2 + 0.4 * ph, 0.2 + 1.6 * ph))
    tone = float(v.get('tone', 0.0))
    if tone < -1.0:
        out.append('lowpass=f=%d:poles=2' % int(400 * (50.0 ** ((tone + 100.0) / 100.0))))
    elif tone > 1.0:
        out.append('highpass=f=%d:poles=2' % int(20 + (tone / 100.0) * 2980))

    # ── TONE ──
    sub = float(v.get('sub', 0.0)) / 100.0
    if sub > 0.01:
        out.append('asubboost=dry=0.9:wet=%0.2f:boost=%0.1f:decay=0.6:cutoff=110:slope=0.6'
                   % (sub, 1.0 + 5.0 * sub))
    bass = float(v.get('bass', 0.0))
    if abs(bass) > 0.1:
        out.append('bass=g=%0.1f:f=110:w=0.7' % bass)
    treble = float(v.get('treble', 0.0))
    if abs(treble) > 0.1:
        out.append('treble=g=%0.1f:f=5500:w=0.7' % treble)
    pres = float(v.get('presence', 0.0)) / 100.0
    if pres > 0.01:
        # a high shelf instead of aexciter: same "air/clarity" intent, and it
        # removes the single most expensive filter from the render pass.
        out.append('treble=g=%0.1f:f=8500:w=0.55' % (0.5 + 5.5 * pres))
    gain = float(v.get('gain', 0.0))
    if abs(gain) > 0.1:
        out.append('volume=%0.1fdB' % gain)

    # ── SPACE ──
    rev = float(v.get('reverb', 0.0)) / 100.0
    if rev > 0.01:
        out.append('aecho=0.85:0.9:%d|%d|%d:%0.2f|%0.2f|%0.2f'
                   % (int(40 + 90 * rev), int(95 + 165 * rev), int(170 + 260 * rev),
                      0.5 * rev, 0.34 * rev, 0.22 * rev))
    ech = float(v.get('echo', 0.0)) / 100.0
    if ech > 0.01:
        out.append('aecho=0.9:0.9:%d:%0.2f' % (int(120 + 480 * ech), min(0.85, 0.2 + 0.55 * ech)))
    w = float(v.get('width', 100.0)) / 100.0
    if abs(w - 1.0) > 0.02:
        # mid/side matrix: M + w*S on the left, M - w*S on the right.
        # (aeval rejects per-channel 'a1=' option names on this build; pan= is stable.)
        # expanded mid/side matrix — pan's grammar rejects parenthesised
        # subexpressions after a coefficient, so multiply out by hand:
        #   L' = (0.5 + w/2)*L + (0.5 - w/2)*R      R' = (0.5 - w/2)*L + (0.5 + w/2)*R
        a = 0.5 + 0.5 * w
        b = 0.5 - 0.5 * w
        out.append('pan=stereo|c0=%f*c0%+f*c1|c1=%f*c0%+f*c1' % (a, b, b, a))

    # ── CHARACTER ──
    dr = float(v.get('drive', 0.0)) / 100.0
    if dr > 0.01:
        out.append('acompressor=threshold=%0.1fdB:ratio=%0.1f:attack=5:release=140:makeup=%0.1f'
                   % (-12.0 - 12.0 * dr, 1.5 + 9.0 * dr, 2.0 + 10.0 * dr))
        out.append('alimiter=limit=0.97:level=disabled')
    lo = float(v.get('lofi', 0.0)) / 100.0
    if lo > 0.01:
        out.append('acrusher=bits=%d:mix=%0.2f:mode=lin:aa=0.4'
                   % (max(4, int(16 - 12 * lo)), min(0.95, 0.25 + 0.75 * lo)))
    return out


def fx_filtergraph(values, rate=FX_DEFAULT_RATE):
    """ffmpeg -filter_complex graph for these rack values, or None when neutral."""
    if fx_rack_is_neutral(values):
        return None
    chain = ','.join(_fx_dsp_filters(values, rate))
    mix = max(0.0, min(100.0, float(values.get('mix', 100.0)))) / 100.0
    head = '[0:a]aformat=channel_layouts=stereo,'
    if mix >= 0.995:
        body = '%sasplit=2[wet0][ref];[wet0]%s[fx]' % (head, chain)
    else:
        wet = max(0.03, mix)
        dry = max(0.03, 1.0 - mix)
        body = ('%sasplit=3[dry][wet0][ref];[wet0]%s[fxw];[dry][fxw]'
                'amix=inputs=2:weights=%0.3f %0.3f:normalize=0[fx]'
                % (head, chain, dry, wet))
    # [ref] is a second *branch of the same decode*: mixed in at weight 0 with
    # duration=shortest it pins the output to the true decoded length, so
    # aecho's tail cannot stretch the rendered file and shift A:B loop points.
    # apad makes the wet branch infinite so the ref branch always sets the end,
    # which also repairs atempo losing a frame at the very end.
    return body + (';[fx]apad[fxpad];'
                   '[fxpad][ref]amix=inputs=2:weights=1 0:duration=shortest[out]')


def fx_signature(src_path, values):
    """Cache key: source identity (path/mtime/size) + every rack value."""
    try:
        st = os.stat(src_path)
        ident = [os.path.abspath(src_path), int(st.st_mtime), st.st_size]
    except OSError:
        ident = [str(src_path), 0, 0]
    payload = json.dumps([ident, {k: round(float(x), 3) for k, x in sorted(values.items())}],
                         sort_keys=True)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]


def fx_find_ffmpeg():
    """Locate ffmpeg: PATH first, then the usual install spots (globs, not guesses)."""
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    patterns = [
        '~/AppData/Local/hermes/tools/ffmpeg*/bin/ffmpeg.exe',
        '~/AppData/Local/hermes/tools/*/bin/ffmpeg.exe',
        '~/AppData/Local/Microsoft/WinGet/Packages/*/bin/ffmpeg.exe',
        'C:/ffmpeg*/bin/ffmpeg.exe',
        'C:/Program Files/ffmpeg*/bin/ffmpeg.exe',
        'C:/ProgramData/chocolatey/bin/ffmpeg.exe',
        '~/scoop/apps/ffmpeg/current/bin/ffmpeg.exe',
        '~/scoop/shims/ffmpeg.exe',
        '/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg',
    ]
    for pat in patterns:
        try:
            hits = sorted(glob.glob(os.path.expanduser(pat)))
        except Exception:
            hits = []
        if hits:
            return hits[-1]
    # last resort: anything called ffmpeg next to the script or in a tools dir
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in ('ffmpeg.exe', 'bin/ffmpeg.exe', '../ffmpeg/bin/ffmpeg.exe'):
        cand = os.path.normpath(os.path.join(here, pat))
        if os.path.isfile(cand):
            return cand
    return None


def fx_log_error(message):
    """Keep the last render failure on disk so a broken pass is diagnosable."""
    FX_LAST_RENDER['error'] = message
    try:
        FX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(FX_CACHE_DIR / 'render_error.log', 'a', encoding='utf-8') as fh:
            fh.write('\n[%s] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    except Exception:
        pass


def fx_source_duration(path):
    """Exact source duration in seconds, or None when it cannot be determined."""
    try:
        info = mutagen.File(str(path))
        if info is not None and getattr(info, 'info', None) is not None:
            length = float(info.info.length)
            if length > 0:
                return length
    except Exception:
        pass
    if str(path).lower().endswith('.wav'):
        try:
            import wave
            with wave.open(str(path), 'rb') as wf:
                return wf.getnframes() / float(wf.getframerate() or 1)
        except Exception:
            pass
    return None


def fx_render_args(ffmpeg, src_path, graph, out_path, rate=FX_DEFAULT_RATE):
    """Full argv for the render stage: one decode, output argon at the source rate."""
    return ([ffmpeg, '-hide_banner', '-nostdin', '-v', 'error',
             '-i', str(src_path),
             '-filter_complex', graph, '-map', '[out]']
            + list(FX_RENDER_WAV_ARGS) + ['-ar', str(int(rate or FX_DEFAULT_RATE)),
                                          '-f', 'wav', '-y', str(out_path)])


def fx_source_rate(path, default=FX_DEFAULT_RATE):
    """Source sample rate, so pitch work never resamples for no reason."""
    try:
        info = mutagen.File(str(path))
        rate = int(getattr(getattr(info, 'info', None), 'sample_rate', 0) or 0)
        if rate >= 8000:
            return rate
    except Exception:
        pass
    return default

def fx_prune_cache(keep=FX_CACHE_KEEP):
    try:
        files = sorted(FX_CACHE_DIR.glob('*.wav'),
                       key=lambda q: q.stat().st_mtime, reverse=True)
        for f in files[keep:]:
            try:
                f.unlink()
            except OSError:
                pass
    except Exception:
        pass


class StarRating(QWidget):
    """
    Five real stars, click to rate.

    The Rating column used to hold a slider painted with a star-ish handle,
    which read as "a slider" and was almost impossible to hit at 54x18. This
    paints actual star glyphs, previews on hover, and clears when you click the
    star that is already set.
    """

    rated = pyqtSignal(int)

    def __init__(self, value=0, accent='#fbbf24', parent=None):
        super().__init__(parent)
        self._value = max(0, min(5, int(value)))
        self._hover = -1
        self._accent = QColor(accent)
        self.setFixedSize(64, 17)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('Click a star to rate this track · click the same star to clear')

    def value(self):
        return self._value

    def set_value(self, value):
        value = max(0, min(5, int(value)))
        if value != self._value:
            self._value = value
            self.update()

    def _star_at(self, x):
        step = max(1.0, self.width() / 5.0)
        return min(5, max(1, int(x // step) + 1))

    def mouseMoveEvent(self, event):
        hover = self._star_at(event.position().x())
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        value = self._star_at(event.position().x())
        if value == self._value:
            value = 0                     # clicking the same star clears it
        self._value = value
        self._hover = -1
        self.update()
        self.rated.emit(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setBold(False)
        painter.setFont(font)
        step = self.width() / 5.0
        shown = self._hover if self._hover > 0 else self._value
        empty = QColor(255, 255, 255, 46)
        for i in range(5):
            painter.setPen(self._accent if i < shown else empty)
            painter.drawText(QRectF(i * step, 0, step, self.height()),
                             Qt.AlignmentFlag.AlignCenter, '\u2605')
        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
#  MINI PLAYER GADGET  —  the floating "gadget" the app minimises into
# ─────────────────────────────────────────────────────────────────────────────
#  GADGET PALETTES  —  the floating gadget's OWN visualizer colours
# ─────────────────────────────────────────────────────────────────────────────
# The gadget is a separate surface from the app, so it keeps a separate colour
# set: (key, label, accent, accent2, accent3).  A key with no colours follows
# the app theme instead.  The dial ring sweep and the visualizer pane both read
# this, so a single choice recolours the whole gadget.
GADGET_PALETTES = (
    ('theme',   'Follow app theme',      None,      None,      None),
    ('violet',  'Violet · Rose · Amber', '#7b2ff7', '#f43f5e', '#ff7a18'),
    ('cyan',    'Electric Cyan',         '#00f0ff', '#00b0ff', '#7c4dff'),
    ('emerald', 'Emerald Aurora',        '#00e676', '#00ffa3', '#00bcd4'),
    ('amber',   'Ember & Gold',          '#ffb300', '#ff7a18', '#f43f5e'),
    ('magenta', 'Neon Magenta',          '#ff2fd0', '#c026d3', '#7b2ff7'),
    ('ice',     'Glacier Ice',           '#9be7ff', '#4fc3f7', '#e1f5fe'),
    ('sunset',  'Sunset Pop',            '#ff5e7e', '#ff9a3c', '#ffe066'),
    ('matrix',  'Terminal Green',        '#39ff14', '#00e676', '#b2ff59'),
    ('ruby',    'Ruby Pulse',            '#ff1744', '#ff5252', '#ff8a80'),
    ('mono',    'Mono White',            '#ffffff', '#dbe3ee', '#9aa7bd'),
)
GADGET_PALETTE_LABELS = {entry[0]: entry[1] for entry in GADGET_PALETTES}


def gadget_palette(key):
    """Look a gadget palette up by key; unknown keys fall back to the theme."""
    for entry in GADGET_PALETTES:
        if entry[0] == key:
            return entry
    return GADGET_PALETTES[0]


def _qcolor(value, alpha=1.0):
    """Parse a THEMES colour ('#rrggbb' or 'rgba(r, g, b, a)') into a QColor.

    QColor cannot parse CSS rgba() strings, and most THEMES entries store
    bg_card / border / accent_glow in exactly that form.  Everything the gadget
    paints goes through here so the translucency in the theme actually survives
    instead of collapsing to black.
    """
    try:
        v = str(value).strip()
        low = v.lower()
        if low.startswith('rgb'):
            inner = v[v.find('(') + 1:v.rfind(')')]
            parts = [p.strip() for p in inner.split(',')]
            if len(parts) < 3:
                return QColor(0, 0, 0, 0)
            r = int(float(parts[0]))
            g = int(float(parts[1]))
            b = int(float(parts[2]))
            a = float(parts[3]) if len(parts) > 3 else 1.0
            c = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
            c.setAlphaF(max(0.0, min(1.0, a * alpha)))
            return c
        c = QColor(v)
        if not c.isValid():
            return QColor(0, 0, 0, 0)
        c.setAlphaF(max(0.0, min(1.0, alpha)))
        return c
    except Exception:
        return QColor(0, 0, 0, 0)


# ── gadget skins ─────────────────────────────────────────────────────────────
# One star row plus one control treatment, five interchangeable looks. The
# design gate ships all five as data so picking a different direction after
# seeing the renders is a one-key change, not a repaint of the code:
#
#   nightshift  soft glass plates, amber stars, filled gradient play key
#   vitals      hairline telemetry, accent stars, mono digits
#   vinyl       editorial, gold foil stars, embossed key, no plates
#   arcade      toy: chunky candy stars, fat key, springy overshoot
#   prism       aurora glass, prismatic star fill, heavy bloom
#
# Every knob is read at paint time by MiniPlayerGadget._skin(); nothing here
# depends on the theme, so a skin survives a theme switch.
GADGET_SKINS = (
    ('nightshift', dict(label='Nightshift', star='rounded', fill='amber', glow=0.55,
                        plate='glass', key='circle', chip=True, pop=1.22,
                        star_on='#ffce6a', star_off='#8b93a1')),
    ('vitals', dict(label='Vitals', star='sharp', fill='accent', glow=0.32,
                    plate='hairline', key='ring', chip=True, mono=True, pop=1.16,
                    star_on='#00e676', star_off='#5b6b7a')),
    ('vinyl', dict(label='Vinyl', star='rounded', fill='gold', glow=0.22,
                   plate='none', key='squircle', chip=False, pop=1.12,
                   star_on='#e8c37a', star_off='#7d7468')),
    ('arcade', dict(label='Arcade', star='chunky', fill='candy', glow=0.78,
                    plate='glass', key='circle', chip=False, bounce=True, pop=1.42,
                    star_on='#ff5d8f', star_off='#6b5b7a')),
    ('prism', dict(label='Prism', star='facet', fill='prism', glow=0.92,
                   plate='glass', key='circle', chip=True, pop=1.26, orbit=True,
                   star_on='#b388ff', star_off='#6f6b86')),
    ('aurora', dict(label='Aurora', star='sparkle', fill='aurora', glow=0.72,
                    plate='glass', key='circle', chip=True, pop=1.30, orbit=True,
                    star_on='#5eead4', star_off='#5f7a86')),
    ('ember', dict(label='Ember', star='sharp', fill='ember', glow=0.62,
                   plate='hairline', key='squircle', chip=False, pop=1.24,
                   star_on='#ff9147', star_off='#7d6a5f')),
    ('mono', dict(label='Mono', star='facet', fill='mono', glow=0.14,
                  plate='glass', key='ring', chip=True, pop=1.10,
                  star_on='#e8edf5', star_off='#5a6270')),
)
GADGET_SKIN_KEYS = tuple(k for k, _ in GADGET_SKINS)
GADGET_SKIN_LABELS = {k: v['label'] for k, v in GADGET_SKINS}


def _star_path(r, kind='rounded'):
    """Five-point star centred on the origin, sized to circumradius r.

    Inner radius is the only geometric knob: a fat inner radius reads as a
    sticker (arcade), a thin one as a sparkle (vitals). Tips get rounded by
    stroking the same path with round joins, which costs nothing and avoids
    hand-tuning twelve corner curves.
    """
    inner = {'sharp': 0.36, 'rounded': 0.46, 'chunky': 0.58,
             'facet': 0.50, 'sparkle': 0.17}.get(kind, 0.46)
    path = QPainterPath()
    for i in range(10):
        rad = r if i % 2 == 0 else r * inner
        a = math.radians(-90.0 + i * 36.0)
        pt = QPointF(math.cos(a) * rad, math.sin(a) * rad)
        if i == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


class MiniPlayerGadget(QFrame):
    """Always-on-top mini player that appears when the main window minimises.

    Deliberately transparent: no card, no panel, no border box — only the
    visualizer pane, the type and the controls are painted, each with its own
    soft shadow so it stays legible over any wallpaper. Everything is drawn in
    paintEvent (icons included, as vector paths) so the widget carries no child
    chrome and the whole surface stays one cheap surface.

    The single child is a ModernVisualizer driven by this widget's 30 FPS tick;
    its own timer is stopped on creation so the app never runs two clocks.
    """

    # key, label, width, height
    SIZES = (('s', 'SMALL', 268, 132), ('m', 'MEDIUM', 348, 168), ('l', 'LARGE', 452, 216))
    PANES = ('vis', 'art', 'auto')
    VIS_MODES = ('bars', 'wave', 'radial', 'mirror_wave', 'circular_bars', 'sound_aurora')
    TICK_MS = 33
    SNAP_PX = 26
    AUTO_ART_SECS = 6.0
    RING_DRIVE = 1.35           # display gain for the dial's spectrum spokes
    MIN_W, MIN_H = 244, 120
    MAX_W, MAX_H = 780, 470
    GRIP = 20

    def __init__(self, main):
        super().__init__(None,
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.main = main
        self.setWindowTitle('Mini Player')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.setMaximumSize(self.MAX_W, self.MAX_H)

        # ── persisted state ──
        self.size_key = 'm'
        self.pane_mode = 'vis'              # visualiser is the default view
        self.opacity_val = 1.0                  # fully opaque window by default
        self.border_w = 0.0                 # no frame by default (menu: Border)
        self.bg_mode = 'opaque'             # opaque card | glass | clear
        self.pinned = True
        self.snap_edges = True
        self.vis_mode = self.VIS_MODES[0]
        self.suppress_restore = False
        self._custom_wh = None
        self.shape = 'circle'                # 'circle' dial or 'card' panel
        self.ring_palette = 'reference'      # reference violet->red, or theme
        self.vis_palette = 'theme'           # gadget-only colour set (GADGET_PALETTES)
        self.rotate = True                   # spokes orbit the dial
        self.rot_speed = 14.0                # degrees per second
        self._rot_phase = 0.0

        # ── star rating of the playing track (mirrors song_profiles) ──
        # Read-only mirror: the gadget never owns the value, it re-reads the
        # profile of whatever main.current_playing_track points at, so a rating
        # set in the playlist column shows up here and vice versa.
        self.skin_key = 'nightshift'         # star + control treatment (GADGET_SKINS)
        self._rating = 0
        self._rating_path = None
        self._rating_total = 0               # tracks carrying a rating, for the rank chip
        self._rank = 0                       # 1-based rank of this track among rated ones
        self._hover_star = None              # index under the pointer, for the preview fill
        self._star_scale = [Spring(stiffness=560.0, damping=17.0) for _ in range(5)]
        self._rating_poll = 0.0
        self._star_row = QRectF()
        for _sp in self._star_scale:
            _sp.value = 1.0

        self.theme_key = getattr(main, 'theme_key', 'midnight')
        self.t = THEMES.get(self.theme_key, THEMES['midnight'])

        # ── runtime state ──
        self._track_path = None
        self._track_t0 = 0.0
        self._title = 'No media loaded'
        self._artist = 'Load a track to begin'
        self._art = None
        self._art_scaled = None
        self._art_scaled_for = None
        self._art_cache = {}
        self.playing = False
        self.position_ms = 0
        self.duration_ms = 0
        self.buffered = 0.0
        self._hover = False
        self._hover_hit = None
        self._active_hit = None
        self._drag_from = None
        self._resize_from = None
        self._anim_t = 0.0
        self._last_tick = time.perf_counter()
        self._pane_rect = QRectF()
        self._info_rect = QRectF()
        self._seek_rect = QRectF()
        self._grip_rect = QRectF()
        self._hits = {}
        self._snap_from = (0, 0)
        self._snap_to = (0, 0)
        self._placed_once = False
        self._user_positioned = False

        # ── animation springs ──
        self._lv = [0.0] * 320          # per-spoke displayed level
        self._pk = [0.0] * 320          # per-spoke running peak
        self._pk_hold = [0.0] * 320     # peak hold timers
        self._track_h = Spring(stiffness=420.0, damping=30.0)  # seek bar thickness
        self._thumb = Spring(stiffness=380.0, damping=28.0)    # seek knob size
        self._vol_h = Spring(stiffness=420.0, damping=30.0)
        self._grip_a = Spring(stiffness=540.0, damping=31.0)  # resize grip fade
        self._btn_scale = {k: Spring(stiffness=460.0, damping=26.0)
                           for k in ('prev', 'play', 'next', 'pin', 'size', 'pane', 'restore', 'gear')}
        self._track_h.value = 3.6
        self._thumb.value = 3.4
        self._vol_h.value = 3.0
        self._fade = None

        # ── visualizer child (frame clock owned by this gadget) ──
        self.vis = ModernVisualizer(self)
        self.vis.timer.stop()
        self.vis.setMinimumSize(0, 0)
        self.vis.setMaximumSize(16777215, 16777215)
        self.vis.set_player(main.player)
        self.vis.set_audio_buffer(getattr(getattr(main, 'visualizer', None), 'audio_buffer', None))
        self.vis.set_theme(self.theme_key)
        self.vis.set_mode(self.vis_mode)
        self.vis.show_hud = False
        self.vis.transparent_bg = True    # no pane background: only the bars
        self.vis.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._apply_vis_palette()         # gadget keeps its own colour set
        self.vis.hide()

        # ── clocks ──
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.setInterval(self.TICK_MS)
        self._tick_timer.timeout.connect(self._tick)

        self._snap_anim = QVariantAnimation(self)
        self._snap_anim.setDuration(150)
        self._snap_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._snap_anim.valueChanged.connect(self._on_snap_step)

        self._place()
        self.setWindowOpacity(self.opacity_val)

        # the HUD is a full-window surface, so it owns the same mode shortcuts
        # the header switch uses — otherwise Ctrl+2/3 would die the moment the
        # main window hands the desk over to the gadget.
        for seq, mode in (('Ctrl+1', 'full'), ('Ctrl+2', 'card'), ('Ctrl+3', 'dial')):
            try:
                sc = QShortcut(QKeySequence(seq), self)
                sc.activated.connect(lambda m=mode: self.main.set_view_mode(m))
            except Exception:
                pass

    # ── persisted state ──────────────────────────────────────────────────────
    def state(self):
        w, h = self.width(), self.height()
        return {
            'enabled': bool(getattr(self.main, 'gadget_enabled', True)),
            'hide_taskbar': bool(getattr(self.main, 'gadget_hide_taskbar', False)),
            'active': bool(getattr(self.main, '_gadget_active', False)),
            'size': self.size_key,
            'pane': self.pane_mode,
            'opacity': round(float(self.opacity_val), 3),
            'border_w': round(float(self.border_w), 2),
            'bg_mode': self.bg_mode,
            'shape': self.shape,
            'skin': self.skin_key,
            'ring_palette': self.ring_palette,
            'vis_palette': self.vis_palette,
            'rotate': bool(self.rotate),
            'rot_speed': round(float(self.rot_speed), 1),
            'pin': bool(self.pinned),
            'snap': bool(self.snap_edges),
            'vis_mode': self.vis_mode,
            'w': int(w),
            'h': int(h),
            'x': int(self.x()),
            'y': int(self.y()),
        }

    def apply_state(self, d):
        d = d or {}
        if d.get('size') in [s[0] for s in self.SIZES] or d.get('size') == 'custom':
            self.size_key = d['size']
        if d.get('pane') in self.PANES:
            self.pane_mode = d['pane']
        if 'opacity' in d:
            try:
                self.opacity_val = max(0.35, min(1.0, float(d['opacity'])))
            except Exception:
                pass
        if d.get('bg_mode') in ('opaque', 'glass', 'clear'):
            self.bg_mode = d['bg_mode']
        if d.get('shape') in ('circle', 'card'):
            self.shape = d['shape']
        if d.get('skin') in GADGET_SKIN_KEYS:
            self.skin_key = d['skin']
        if d.get('ring_palette') in ('reference', 'theme'):
            self.ring_palette = d['ring_palette']
        if d.get('vis_palette') in GADGET_PALETTE_LABELS:
            self.vis_palette = d['vis_palette']
        if 'rotate' in d:
            self.rotate = bool(d['rotate'])
        if 'rot_speed' in d:
            try:
                self.rot_speed = max(0.0, min(120.0, float(d['rot_speed'])))
            except Exception:
                pass
        if 'border_w' in d:
            try:
                self.border_w = max(0.0, min(6.0, float(d['border_w'])))
            except Exception:
                pass
        if 'pin' in d:
            self.pinned = bool(d['pin'])
        if 'snap' in d:
            self.snap_edges = bool(d['snap'])
        if d.get('vis_mode') in self.VIS_MODES:
            self.vis_mode = d['vis_mode']
            self.vis.set_mode(self.vis_mode)
        w, h = d.get('w'), d.get('h')
        if self.shape == 'circle' and self._custom_wh:
            side = min(self._custom_wh)
            self._custom_wh = (side, side)
        if isinstance(w, int) and isinstance(h, int) and w >= self.MIN_W and h >= self.MIN_H:
            self._custom_wh = (w, h)
            if self.size_key == 'custom':
                self.resize(w, h)
        self.setWindowOpacity(self.opacity_val)
        self._apply_pin()
        x, y = d.get('x'), d.get('y')
        if isinstance(x, int) and isinstance(y, int) and (x or y):
            self._place(x, y)
        else:
            self._place()
        self._apply_vis_palette()
        self.update()

    # ── controls (gadget itself + SettingsWindow) ────────────────────────────
    def set_theme_key(self, key):
        self.theme_key = key
        self.t = THEMES.get(key, THEMES['midnight'])
        self.vis.set_theme(key)
        self._apply_vis_palette()          # re-assert the gadget's own colours
        self.update()

    def set_vis_palette(self, key):
        """Recolour the gadget's visualizer — its own setting, not the app's.

        'theme' follows the app theme; every other key is a self-contained
        accent triplet that drives both the visualizer pane and the dial ring.
        """
        if key not in GADGET_PALETTE_LABELS:
            key = 'theme'
        self.vis_palette = key
        self._apply_vis_palette()
        self.update()
        self._save()

    def _apply_vis_palette(self):
        _, _label, a1, a2, a3 = gadget_palette(self.vis_palette)
        try:
            self.vis.set_color_override(a1, a2, a3)
        except Exception:
            pass

    def set_vis_mode(self, mode):
        """Gadget visualizer mode — independent of the app's visualizer."""
        if mode in self.VIS_MODES:
            self.vis_mode = mode
            try:
                self.vis.set_mode(mode)
            except Exception:
                pass
            self.update()
            self._save()

    def set_ring_rotate(self, on):
        """Rotating spokes vs. a fixed (still) ring."""
        self.rotate = bool(on)
        if self.rotate and self.rot_speed <= 0.0:
            self.rot_speed = 14.0
        self.update()
        self._save()

    def set_rot_speed(self, dps):
        try:
            self.rot_speed = max(0.0, min(120.0, float(dps)))
        except Exception:
            return
        self.rotate = self.rot_speed > 0.0
        self.update()
        self._save()

    def open_settings(self):
        """Open the app settings (its MINI GADGET section) from the gadget."""
        try:
            self.main._open_settings_window()
        except Exception:
            pass
        sw = getattr(self.main, 'settings_window', None)
        if sw is None:
            return
        # the gadget floats above everything: keep its settings on top of it
        try:
            sw.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            sw._ontop_for_gadget = True   # cleared when the gadget goes away
            sw.show()
            sw.raise_()
            sw.activateWindow()
        except Exception:
            pass

    def set_size_key(self, key):
        if key in [s[0] for s in self.SIZES] or key == 'custom':
            self.size_key = key
            if key != 'custom':
                self._custom_wh = None
            self._place()
            self.update()

    def set_pane_mode(self, mode):
        if mode in self.PANES:
            self.pane_mode = mode
            self.update()

    def cycle_pane(self):
        idx = (self.PANES.index(self.pane_mode) + 1) % len(self.PANES)
        self.set_pane_mode(self.PANES[idx])
        self._save()

    def cycle_size(self):
        if self.shape == 'circle':
            # the dial is square, so the card's S/M/L boxes are meaningless here:
            # cycle the diameter instead. Without this the SIZE key on the dial was
            # a dead control — it accepted the click and changed nothing visible.
            keys = ['s', 'm', 'l']
            cur = self.size_key if self.size_key in keys else 'm'
            nxt = keys[(keys.index(cur) + 1) % len(keys)]
            d = {'s': 300, 'm': 372, 'l': 440}[nxt]
            self.size_key = nxt
            self._custom_wh = (d, d)
            self.resize(d, d)
            self._layout_pane()
            self.update()
            self._save()
            return
        keys = [s[0] for s in self.SIZES]
        if self.size_key in keys:
            nxt = keys[(keys.index(self.size_key) + 1) % len(keys)]
            self.set_size_key(nxt)
        else:
            self.set_size_key('m')
        self._save()

    def toggle_pin(self):
        self.pinned = not self.pinned
        self._apply_pin()
        self._save()

    def _save(self):
        try:
            self.main._schedule_save_settings()
        except Exception:
            pass

    def _apply_pin(self):
        try:
            pos = self.pos()
            was_visible = self.isVisible()
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.pinned)
            self.move(pos)        # re-creating the window handle resets geometry
            if was_visible:
                self.show()       # changing a window flag hides it on Windows
                self.raise_()
        except Exception:
            pass

    # ── geometry ─────────────────────────────────────────────────────────────
    def _size_wh(self):
        if self.size_key == 'custom' and self._custom_wh:
            if self.shape == 'circle':
                side = min(self._custom_wh)
                return side, side
            return self._custom_wh
        if self.shape == 'circle':
            side = {'s': 296, 'm': 372, 'l': 468}.get(self.size_key, 372)
            return side, side
        for key, _label, w, h in self.SIZES:
            if key == self.size_key:
                return w, h
        return 348, 168

    def _roomy(self):
        return self.width() >= 320

    def _place(self, x=None, y=None):
        if self.shape == 'circle' or self.size_key != 'custom' or not self._custom_wh:
            w, h = self._size_wh()
            self.resize(w, h)
        explicit = isinstance(x, int) and isinstance(y, int)
        if explicit:
            self.move(x, y)
            self._user_positioned = True
        elif not getattr(self, '_user_positioned', False):
            scr = self.screen() or QApplication.primaryScreen()
            if scr is not None:
                a = scr.availableGeometry()
                self.move(a.right() - self.width() - 22, a.bottom() - self.height() - 22)
        self._placed_once = True
        if explicit or not self.isVisible():
            self._clamp()
        self._layout_pane()

    def _clamp(self):
        scr = self.screen() or QApplication.primaryScreen()
        if scr is None:
            return
        try:
            a = scr.availableGeometry()
        except Exception:
            return
        x = max(a.left(), min(self.x(), a.right() - self.width() + 1))
        y = max(a.top(), min(self.y(), a.bottom() - self.height() + 1))
        self.move(int(x), int(y))

    def _layout_pane(self):
        pane, info, seek, grip, hits = self._compute_layout()
        self._pane_rect, self._info_rect, self._seek_rect = pane, info, seek
        self._grip_rect, self._hits = grip, hits
        if hasattr(self, 'vis'):
            if self.shape == 'circle':
                # on the dial the pane role becomes a centre strip inside the ring,
                # so the PANE key has something real to switch on the dial too
                R = self._circle_r()
                cx, cy = self.width() / 2.0, self.height() / 2.0
                vw, vh = R * 0.66, R * 0.30
                self.vis.setGeometry(int(cx - vw / 2.0), int(cy - vh * 0.32),
                                     int(vw), int(vh))
            else:
                self.vis.setGeometry(int(pane.x()), int(pane.y()),
                                     int(pane.width()), int(pane.height()))

    def _compute_layout(self):
        if self.shape == 'circle':
            return self._compute_circle_layout()
        w, h = max(1, self.width()), max(1, self.height())
        m = 10.0
        pane_h = max(1.0, h - m * 2)
        pane_w = max(1.0, min(pane_h, int(w * 0.52)))
        pane = QRectF(m, m, pane_w, pane_h)

        rx = m + pane_w + 13
        rw = max(60.0, w - rx - m - 20)      # keep a 20 px lane for the icon rail

        # bottom-up: transport band, then the seek row above it. The band grew
        # from 22 to 30 px so the play key can be a real filled target instead
        # of a glyph exactly the same size as its neighbours.
        band = 30.0 if h >= 150.0 else 24.0
        ty = h - m - band
        seek_row_h = 16.0
        seek_y = ty - 6.0 - seek_row_h
        seek = QRectF(rx, seek_y, rw, seek_row_h)

        hits = {}
        # transport: key + two side plates, left aligned, volume to their right
        side = band * 0.82
        gap = 6.0 if band >= 30.0 else 4.0
        tx = rx
        hits['prev'] = QRectF(tx, ty + (band - side) / 2.0, side, side)
        tx += side + gap
        hits['play'] = QRectF(tx, ty, band, band)
        tx += band + gap
        hits['next'] = QRectF(tx, ty + (band - side) / 2.0, side, side)
        tx += side + gap + 2.0
        vol_w = max(24.0, min(84.0, rx + rw - tx - 6.0))
        hits['vol'] = QRectF(tx, ty + band / 2.0 - 7.0, vol_w, 14.0)

        # vertical icon rail on the right edge
        rs = 17.0
        rgap = 3.0
        cx = w - m - rs
        cy = m + 1.0
        for name in ('restore', 'pin', 'pane', 'size', 'gear'):
            hits[name] = QRectF(cx, cy, rs, rs)
            cy += rs + rgap

        info_top = m + 1.0
        info = QRectF(rx, info_top, rw, max(10.0, seek_y - info_top - 4))

        # rating row: docked just above the seek + transport cluster. It shares a
        # job with those controls, so it sits with them instead of floating under
        # the artist line — one hit target per star, no shared row rect.
        star_h = 15.0 if h >= 190.0 else (13.0 if h >= 150.0 else 11.0)
        star_y = max(info_top + 2.0, seek_y - star_h - 5.0)
        self._star_row = QRectF(rx, star_y, rw, star_h)
        sgap = max(1.8, star_h * 0.24)
        star_total = 5 * star_h + 4 * sgap
        sk = self._skin()
        show_chip = bool(sk.get('chip') and self._rank > 0 and (rw >= star_total + 52))
        tw = 0.0
        if show_chip:
            label = '#%d/%d' % (self._rank, self._rating_total)
            f = QFont('Consolas', 7 if star_h < 15 else 8)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
            tw = QFontMetrics(f).horizontalAdvance(label) + 12.0
        group_w = star_total + (8.0 + tw if show_chip else 0.0)
        star_x0 = rx + max(0.0, (rw - group_w) / 2.0)
        for i in range(5):
            hits['star%d' % i] = QRectF(star_x0 + i * (star_h + sgap) - 2.0, star_y - 2.0,
                                        star_h + 4.0, star_h + 4.0)

        grip = QRectF(w - self.GRIP - 2, h - self.GRIP - 2, self.GRIP, self.GRIP)
        return pane, info, seek, grip, hits

    def _snap(self):
        scr = self.screen() or QApplication.primaryScreen()
        if scr is None:
            return
        try:
            a = scr.availableGeometry()
        except Exception:
            return
        x, y = self.x(), self.y()
        tx, ty = x, y
        if abs(x - a.left()) <= self.SNAP_PX:
            tx = a.left()
        elif abs(a.right() - (x + self.width())) <= self.SNAP_PX:
            tx = a.right() - self.width() + 1
        if abs(y - a.top()) <= self.SNAP_PX:
            ty = a.top()
        elif abs(a.bottom() - (y + self.height())) <= self.SNAP_PX:
            ty = a.bottom() - self.height() + 1
        if (tx, ty) == (x, y):
            return
        self._snap_from = (x, y)
        self._snap_to = (tx, ty)
        self._snap_anim.stop()
        self._snap_anim.setStartValue(0.0)
        self._snap_anim.setEndValue(1.0)
        self._snap_anim.start()

    def _on_snap_step(self, v):
        try:
            f = float(v)
        except Exception:
            return
        x = self._snap_from[0] + (self._snap_to[0] - self._snap_from[0]) * f
        y = self._snap_from[1] + (self._snap_to[1] - self._snap_from[1]) * f
        self.move(int(round(x)), int(round(y)))

    # ── track / artwork ──────────────────────────────────────────────────────
    def refresh_track(self, force=False):
        path = getattr(self.main, 'current_playing_track', None)
        if path == self._track_path and not force:
            return
        self._track_path = path
        self._track_t0 = self._anim_t
        if not path:
            self._title = 'No media loaded'
            self._artist = 'Load a track to begin'
            self._art = None
        else:
            self._title = self._title_for(path)
            self._artist = self._artist_for(path)
            self._art = self._load_art(path)
        self._art_scaled = None
        self._art_scaled_for = None
        self._refresh_rating(force=True, pop=bool(path))
        self.update()

    def _title_for(self, path):
        try:
            t = self.main._get_song_title(path)
            if t:
                return str(t)
        except Exception:
            pass
        try:
            return Path(path).stem
        except Exception:
            return 'Unknown track'

    def _artist_for(self, path):
        try:
            a = self.main._get_song_artist(path)
            if a and str(a).strip().lower() not in ('unknown', 'unknown artist', '-', ''):
                return str(a)
        except Exception:
            pass
        return 'Unknown artist'

    def _load_art(self, path):
        try:
            st = os.stat(path)
            key = (str(path), int(st.st_mtime), int(st.st_size))
        except Exception:
            key = (str(path), 0, 0)
        if key in self._art_cache:
            return self._art_cache[key]

        pix = None
        data = None
        try:
            af = mutagen.File(path)
            if af is not None:
                tags = getattr(af, 'tags', None)
                if tags is not None and hasattr(tags, 'getall'):
                    for k in ('APIC:', 'APIC'):
                        try:
                            frames = tags.getall(k)
                        except Exception:
                            frames = []
                        if frames:
                            data = frames[0].data
                            break
                if data is None:
                    pics = getattr(af, 'pictures', None)
                    if pics:
                        data = pics[0].data
                if data is None and tags is not None:
                    try:
                        covr = tags.get('covr')
                        if covr:
                            data = bytes(covr[0])
                    except Exception:
                        pass
            if data:
                pix = QPixmap()
                if not pix.loadFromData(bytes(data)):
                    pix = None
        except Exception:
            pix = None

        if len(self._art_cache) > 16:
            self._art_cache.clear()
        self._art_cache[key] = pix
        return pix

    def _pane_is_vis(self):
        if self.pane_mode == 'vis':
            return True
        if self.pane_mode == 'art':
            return False
        if not self.playing:
            return False
        return (self._anim_t - self._track_t0) > self.AUTO_ART_SECS

    # ── frame driver ─────────────────────────────────────────────────────────
    def _tick(self):
        if not self.isVisible():
            return
        now = time.perf_counter()
        dt = min(0.12, max(0.001, now - self._last_tick))
        self._last_tick = now
        self._anim_t += dt

        m = self.main
        try:
            self.playing = m.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            self.position_ms = int(m.player.position())
            self.duration_ms = int(m.player.duration())
            try:
                self.buffered = float(m.player.bufferProgress() or 0.0)
            except Exception:
                self.buffered = 0.0
        except Exception:
            pass

        self.refresh_track()

        src = getattr(getattr(m, 'visualizer', None), 'audio_buffer', None)
        if src is not self.vis.audio_buffer:
            self.vis.set_audio_buffer(src)

        # ── control springs ──
        hot_seek = self._hover and (self._hover_hit == 'seek' or self._active_hit == 'seek')
        self._track_h.target = 5.6 if hot_seek else 3.6
        self._track_h.step(dt)
        self._thumb.target = 6.0 if hot_seek else 3.4
        self._thumb.step(dt)
        self._vol_h.target = 4.4 if (self._hover_hit == 'vol' or self._active_hit == 'vol') else 3.0
        self._vol_h.step(dt)
        for name, sp in self._btn_scale.items():
            sp.target = 1.16 if self._hover_hit == name else 1.0
            sp.step(dt)
        for sp in self._star_scale:
            sp.target = 1.0
            sp.step(dt)
        # the playlist column can rate a track at any moment: re-read the profile
        # twice a second so the gadget never shows a stale rank
        self._rating_poll += dt
        if self._rating_poll >= 0.5:
            self._rating_poll = 0.0
            self._refresh_rating()

        # the resize grip lives on hover only, and fades instead of popping
        want_grip = (self._hover_hit == 'grip' or self._resize_from is not None
                     or self._is_hovered())
        self._grip_a.target = 1.0 if want_grip else 0.0
        self._grip_a.step(dt)

        want = self._pane_is_vis() and (self.shape != 'circle' or self.pane_mode == 'vis')
        if self.shape == 'circle':
            # the dial draws its own spokes; the hidden visualizer is only
            # advanced so the level/peak engine stays in sync with the audio
            try:
                self.vis._render_tick()
            except Exception:
                pass
            self._update_ring_levels(dt)
            if self.rotate:
                self._rot_phase = (self._rot_phase + self.rot_speed * dt) % 360.0
        if want:
            if not self.vis.isVisible():
                self.vis.show()
                self._layout_pane()
            try:
                self.vis._render_tick()
            except Exception:
                pass
        elif self.vis.isVisible():
            self.vis.hide()

        self.update()

    # ── painting helpers ─────────────────────────────────────────────────────
    def _styled_text(self, p, x, y, text, color, outline=None):
        """Type with a dark outline so it reads over any wallpaper."""
        if outline is None:
            # scale with the type so small sizes stay crisp instead of chunky
            outline = max(1.25, min(2.3, p.fontMetrics().height() * 0.115))
        path = QPainterPath()
        path.addText(QPointF(x, y), p.font(), text)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 205), outline, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    def _paint_icon(self, p, kind, r, color, scale=1.0, filled=False):
        p.save()
        p.translate(round(r.center().x()), round(r.center().y()))
        s = min(r.width(), r.height()) * 0.5 * scale
        pen_w = max(1.3, s * 0.26)
        p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)

        stroke = QPen(color, max(1.1, s * 0.22), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        if kind == 'play':
            # soft triangle: the same path filled and stroked with round joins, so
            # the tips are rounded without hand-authoring twelve corner curves
            path = QPainterPath()
            path.moveTo(-s * 0.34, -s * 0.56)
            path.lineTo(s * 0.60, 0.0)
            path.lineTo(-s * 0.34, s * 0.56)
            path.closeSubpath()
            p.setPen(QPen(color, s * 0.30, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(color)
            p.drawPath(path)
        elif kind == 'pause':
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            bw, bh = s * 0.30, s * 1.12
            p.drawRoundedRect(QRectF(-s * 0.46, -bh / 2.0, bw, bh), bw / 2.0, bw / 2.0)
            p.drawRoundedRect(QRectF(s * 0.16, -bh / 2.0, bw, bh), bw / 2.0, bw / 2.0)
        elif kind in ('prev', 'next'):
            # chevron + pill bar: prev points left (|<), next points right (>|)
            dir = 1.0 if kind == 'next' else -1.0
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, max(1.3, s * 0.24), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            ch = QPainterPath()
            ch.moveTo(-dir * s * 0.26, -s * 0.50)
            ch.lineTo(dir * s * 0.26, 0.0)
            ch.lineTo(-dir * s * 0.26, s * 0.50)
            p.drawPath(ch)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            bx = dir * s * 0.48 - s * 0.08
            p.drawRoundedRect(QRectF(bx, -s * 0.54, s * 0.16, s * 1.08), s * 0.08, s * 0.08)
        elif kind == 'gear':
            # 6-tooth industrial cogwheel with center axle hole
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            gp = QPainterPath()
            gp.setFillRule(Qt.FillRule.OddEvenFill)
            r_out = s * 0.62
            r_in = s * 0.44
            r_hole = s * 0.20
            for i in range(6):
                a_mid = i * 60.0
                a1 = math.radians(a_mid - 11.5)
                a2 = math.radians(a_mid - 7.5)
                a3 = math.radians(a_mid + 7.5)
                a4 = math.radians(a_mid + 11.5)
                p1 = QPointF(math.cos(a1) * r_in, math.sin(a1) * r_in)
                p2 = QPointF(math.cos(a2) * r_out, math.sin(a2) * r_out)
                p3 = QPointF(math.cos(a3) * r_out, math.sin(a3) * r_out)
                p4 = QPointF(math.cos(a4) * r_in, math.sin(a4) * r_in)
                if i == 0:
                    gp.moveTo(p1)
                else:
                    gp.lineTo(p1)
                gp.lineTo(p2)
                gp.lineTo(p3)
                gp.lineTo(p4)
            gp.closeSubpath()
            gp.addEllipse(QPointF(0.0, 0.0), r_hole, r_hole)
            p.drawPath(gp)
        elif kind == 'close':
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, max(1.3, s * 0.20), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-s * 0.38, -s * 0.38), QPointF(s * 0.38, s * 0.38))
            p.drawLine(QPointF(s * 0.38, -s * 0.38), QPointF(-s * 0.38, s * 0.38))
        elif kind == 'pin':
            # modern pushpin: head cap, tapered waist, collar bar, sharp needle
            if filled:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(-s * 0.32, -s * 0.52, s * 0.64, s * 0.16), s * 0.08, s * 0.08)
                body = QPainterPath()
                body.moveTo(-s * 0.20, -s * 0.36)
                body.lineTo(s * 0.20, -s * 0.36)
                body.lineTo(s * 0.28, s * 0.08)
                body.lineTo(-s * 0.28, s * 0.08)
                body.closeSubpath()
                p.drawPath(body)
                p.drawRoundedRect(QRectF(-s * 0.34, s * 0.08, s * 0.68, s * 0.12), s * 0.06, s * 0.06)
                p.setPen(QPen(color, max(1.2, s * 0.18), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(0.0, s * 0.20), QPointF(0.0, s * 0.58))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(color, max(1.1, s * 0.17), Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawRoundedRect(QRectF(-s * 0.32, -s * 0.52, s * 0.64, s * 0.16), s * 0.08, s * 0.08)
                body = QPainterPath()
                body.moveTo(-s * 0.20, -s * 0.36)
                body.lineTo(s * 0.20, -s * 0.36)
                body.lineTo(s * 0.28, s * 0.08)
                body.lineTo(-s * 0.28, s * 0.08)
                body.closeSubpath()
                p.drawPath(body)
                p.drawLine(QPointF(-s * 0.34, s * 0.14), QPointF(s * 0.34, s * 0.14))
                p.drawLine(QPointF(0.0, s * 0.14), QPointF(0.0, s * 0.58))
        elif kind == 'pane':
            # split view: window frame + active right sidebar panel
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, max(1.1, s * 0.18), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawRoundedRect(QRectF(-s * 0.58, -s * 0.46, s * 1.16, s * 0.92),
                              s * 0.20, s * 0.20)
            p.drawLine(QPointF(s * 0.06, -s * 0.46), QPointF(s * 0.06, s * 0.46))
            if filled:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                sb = QPainterPath()
                sb.addRoundedRect(QRectF(-s * 0.58, -s * 0.46, s * 1.16, s * 0.92), s * 0.20, s * 0.20)
                clip = QPainterPath()
                clip.addRect(QRectF(s * 0.06, -s * 0.50, s * 0.60, s * 1.00))
                p.drawPath(sb.intersected(clip))
            else:
                p.drawLine(QPointF(-s * 0.40, -s * 0.12), QPointF(-s * 0.12, -s * 0.12))
                p.drawLine(QPointF(-s * 0.40, s * 0.14), QPointF(-s * 0.20, s * 0.14))
        elif kind == 'size':
            # four corner expand brackets with rounded joins & caps
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, max(1.2, s * 0.20), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            arm = s * 0.26
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    x0, y0 = sx * s * 0.48, sy * s * 0.48
                    cp = QPainterPath()
                    cp.moveTo(x0 - sx * arm, y0)
                    cp.lineTo(x0, y0)
                    cp.lineTo(x0, y0 - sy * arm)
                    p.drawPath(cp)
        elif kind == 'volume':
            # speaker body + one wave — used beside the volume rail
            body = QPainterPath()
            body.moveTo(-s * 0.60, -s * 0.20)
            body.lineTo(-s * 0.26, -s * 0.20)
            body.lineTo(s * 0.06, -s * 0.54)
            body.lineTo(s * 0.06, s * 0.54)
            body.lineTo(-s * 0.26, s * 0.20)
            body.lineTo(-s * 0.60, s * 0.20)
            body.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawPath(body)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, max(1.0, s * 0.16), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(s * 0.02, -s * 0.44, s * 0.70, s * 0.88), -58 * 16, 116 * 16)
        p.restore()

    def _pill(self, p, r, alpha=0.16):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_qcolor(self.t.get('accent', '#00e676'), alpha))
        p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), r.height() / 2 + 1, r.height() / 2 + 1)

    # ── rating (stars) ───────────────────────────────────────────────────────
    def _skin(self):
        for key, spec in GADGET_SKINS:
            if key == self.skin_key:
                return spec
        return GADGET_SKINS[0][1]

    def _star_brush(self, rect, sk, acc):
        fill = sk.get('fill', 'amber')
        if fill == 'prism':
            grad = QConicalGradient(rect.center(), 90.0)
            grad.setColorAt(0.00, QColor('#b388ff'))
            grad.setColorAt(0.35, QColor('#22d3ee'))
            grad.setColorAt(0.65, QColor('#f472b6'))
            grad.setColorAt(1.00, QColor('#b388ff'))
            return QBrush(grad)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if fill == 'accent':
            base = QColor(acc)
            grad.setColorAt(0.0, base.lighter(132))
            grad.setColorAt(1.0, base.darker(112))
        elif fill == 'gold':
            grad.setColorAt(0.0, QColor('#fbe9b8'))
            grad.setColorAt(0.55, QColor('#e8c37a'))
            grad.setColorAt(1.0, QColor('#b3894a'))
        elif fill == 'candy':
            grad.setColorAt(0.0, QColor('#ffa3bd'))
            grad.setColorAt(0.5, QColor('#ff5d8f'))
            grad.setColorAt(1.0, QColor('#a855f7'))
        elif fill == 'aurora':
            grad.setColorAt(0.0, QColor('#7df9d0'))
            grad.setColorAt(0.5, QColor('#38bdf8'))
            grad.setColorAt(1.0, QColor('#a78bfa'))
        elif fill == 'ember':
            grad.setColorAt(0.0, QColor('#ffd08a'))
            grad.setColorAt(0.5, QColor('#ff9147'))
            grad.setColorAt(1.0, QColor('#d92d20'))
        elif fill == 'mono':
            grad.setColorAt(0.0, QColor('#ffffff'))
            grad.setColorAt(0.55, QColor('#c9d2df'))
            grad.setColorAt(1.0, QColor('#8b95a5'))
        else:
            grad.setColorAt(0.0, QColor('#ffe9bb'))
            grad.setColorAt(0.5, QColor(sk.get('star_on', '#ffce6a')))
            grad.setColorAt(1.0, QColor('#e39b2e'))
        return QBrush(grad)

    def _hover_star_index(self):
        hk = self._hover_hit or ''
        if hk.startswith('star') and hk[4:].isdigit():
            return int(hk[4:])
        return self._hover_star

    def _star_index_at(self, pos):
        for i in range(5):
            r = self._hits.get('star%d' % i)
            if r is not None and r.contains(pos):
                return i
        return None

    def _paint_stars(self, p, rect, acc, acc2, dim, chip=True):
        """Five vector stars plus a rank chip for the playing track.

        Filled up to the stored rating; hovering a star previews that value, so
        the row is both readout and control. The value is never owned here —
        _refresh_rating() mirrors the playlist profile, which keeps the gadget
        and the Rating column in agreement without a signal round-trip.
        """
        if rect is None or rect.height() <= 1 or rect.width() <= 8:
            return
        sk = self._skin()
        size = float(min(rect.height(), 18.0))
        gap = max(1.8, size * 0.24)
        total = 5 * size + 4 * gap
        show_chip = bool(chip and sk.get('chip') and self._rank > 0 and (rect.width() >= total + 52))
        tw = 0.0
        label = ''
        if show_chip:
            label = '#%d/%d' % (self._rank, self._rating_total)
            f = QFont('Consolas', 7 if size < 15 else 8)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(label) + 12.0
        group_w = total + (8.0 + tw if show_chip else 0.0)
        x0 = rect.left() + max(0.0, (rect.width() - group_w) / 2.0)
        cyc = rect.center().y()
        rating = max(0, min(5, int(self._rating)))
        hover = self._hover_star_index()
        on_count = (hover + 1) if hover is not None else rating
        brush = self._star_brush(rect, sk, acc)
        glow = float(sk.get('glow', 0.4))
        pop = float(sk.get('pop', 1.2))
        on_col = QColor(sk.get('star_on', '#ffce6a'))
        for i in range(5):
            cx = x0 + size / 2.0 + i * (size + gap)
            r = size * 0.5 * max(0.6, min(pop, float(self._star_scale[i].value)))
            path = _star_path(r, sk.get('star', 'rounded'))
            path.translate(cx, cyc)
            if i < on_count:
                if glow > 0.05:
                    halo = QRadialGradient(QPointF(cx, cyc), r * 2.3)
                    h0 = QColor(on_col)
                    h0.setAlphaF(0.26 * glow)
                    h1 = QColor(on_col)
                    h1.setAlphaF(0.0)
                    halo.setColorAt(0.0, h0)
                    halo.setColorAt(1.0, h1)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(halo))
                    p.drawEllipse(QPointF(cx, cyc), r * 2.3, r * 2.3)
                p.setPen(QPen(QColor(255, 255, 255, 40 + int(80 * glow)), max(0.6, r * 0.16)))
                p.setBrush(brush)
                p.drawPath(path)
                if self.playing:
                    # a slow specular band travelling across each star: the row
                    # reads as "live" while something is playing, static when paused
                    ph = ((self._anim_t * 0.55) + i * 0.12) % 1.0
                    a0, a1, a2 = max(0.0, ph - 0.22), ph, min(1.0, ph + 0.22)
                    if a0 < a1 < a2:
                        band = QLinearGradient(cx - r, cyc - r, cx + r, cyc + r)
                        band.setColorAt(a0, QColor(255, 255, 255, 0))
                        band.setColorAt(a1, QColor(255, 255, 255, 86))
                        band.setColorAt(a2, QColor(255, 255, 255, 0))
                        p.save()
                        p.setClipPath(path)
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QBrush(band))
                        p.drawRect(QRectF(cx - r, cyc - r, r * 2, r * 2))
                        p.restore()
            else:
                p.setPen(QPen(QColor(sk.get('star_off', '#8b93a1')), max(0.8, r * 0.20)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)

        if not show_chip:
            return
        cr = QRectF(x0 + total + 8.0, cyc - size * 0.52, tw, size * 1.04)
        p.setPen(Qt.PenStyle.NoPen)
        chip_fill = QColor(on_col) if rating >= 5 else QColor(255, 255, 255)
        chip_fill.setAlphaF(0.24 if rating >= 5 else 0.07)
        p.setBrush(chip_fill)
        p.drawRoundedRect(cr, cr.height() / 2.0, cr.height() / 2.0)
        p.setPen(QPen(QColor(255, 255, 255, 46), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(cr, cr.height() / 2.0, cr.height() / 2.0)
        p.setPen(QColor(255, 255, 255, 170))
        p.drawText(cr, int(Qt.AlignmentFlag.AlignCenter), label)

    def _refresh_rating(self, force=False, pop=False):
        """Mirror the playing track's rating + its rank among rated tracks."""
        path = self._track_path
        rating = 0
        total = 0
        rank = 0
        try:
            if path:
                rating = int(self.main._get_song_rating(path) or 0)
            profs = getattr(self.main, 'song_profiles', None) or {}
            vals = []
            for prof in profs.values():
                try:
                    v = int(prof.get('rating', 0) or 0)
                except Exception:
                    v = 0
                if v > 0:
                    vals.append(v)
            total = len(vals)
            if total and rating > 0:
                rank = 1 + sum(1 for v in vals if v > rating)
        except Exception:
            pass
        changed = (rating != self._rating)
        self._rating = max(0, min(5, rating))
        self._rating_total = total
        self._rank = rank
        if pop or changed:
            for i in range(5):
                if i < self._rating:
                    self._star_scale[i].value = float(self._skin().get('pop', 1.2))

    def _set_rating(self, n):
        """Write the rating back through the playlist profile, then re-read it."""
        path = self._track_path
        if not path:
            return
        n = max(0, min(5, int(n)))
        if n == int(self._rating):
            n = 0                                  # clicking the same star clears it
        try:
            profs = getattr(self.main, 'song_profiles', None)
            if profs is not None:
                prof = profs.setdefault(os.path.normpath(str(path)), {})
                prof['rating'] = n
            save = getattr(self.main, '_save_song_profiles_to_disk', None)
            if callable(save):
                save()
            sched = getattr(self.main, '_schedule_save_settings', None)
            if callable(sched):
                sched()
        except Exception:
            return
        self._refresh_rating(force=True, pop=True)
        self.update()

    # ── transport key ────────────────────────────────────────────────────────
    def _paint_key(self, p, r, acc, sk, hot, down, sp, kind):
        """The play/pause key: filled gradient disc, bloom, pressed squash.

        Deliberately the only filled control on the surface — everything else is
        a ghost plate — so the eye lands on it first at any size.
        """
        rr = QRectF(r)
        c = rr.center()
        dia = min(rr.width(), rr.height()) * (0.94 if down else 1.0)
        dia *= 0.94 + 0.06 * sp
        keyrect = QRectF(c.x() - dia / 2.0, c.y() - dia / 2.0, dia, dia)
        key = sk.get('key', 'circle')
        rad = dia / 2.0 if key == 'circle' else dia * 0.22

        if key == 'ring':
            # outlined key: no fill, so it can never fight a themed accent
            glow = float(sk.get('glow', 0.5)) * (1.2 if hot else 0.8)
            halo = QRadialGradient(QPointF(c), dia * 1.0)
            c0 = QColor(acc)
            c0.setAlphaF(0.22 * glow)
            c1 = QColor(acc)
            c1.setAlphaF(0.0)
            halo.setColorAt(0.45, c0)
            halo.setColorAt(1.0, c1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(c), dia * 1.0, dia * 1.0)
            p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 26))
            p.setPen(QPen(QColor(acc.red(), acc.green(), acc.blue(), 210 if hot else 165),
                          max(1.4, dia * 0.06)))
            p.drawEllipse(keyrect)
            self._paint_icon(p, kind, keyrect, QColor(236, 246, 255, 240),
                             scale=0.44 * (1.0 + 0.04 * sp))
            return

        glow = float(sk.get('glow', 0.5)) * (1.45 if hot else 1.0)
        halo = QRadialGradient(QPointF(c), dia * 1.0)
        c0 = QColor(acc)
        c0.setAlphaF(0.30 * glow)
        c1 = QColor(acc)
        c1.setAlphaF(0.0)
        halo.setColorAt(0.50, c0)
        halo.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(c), dia * 1.0, dia * 1.0)

        base = QColor(acc)
        grad = QLinearGradient(keyrect.topLeft(), keyrect.bottomRight())
        grad.setColorAt(0.0, base.lighter(140))
        grad.setColorAt(0.55, base)
        grad.setColorAt(1.0, base.darker(124))
        p.setPen(QPen(QColor(255, 255, 255, 74), 1.0))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(keyrect, rad, rad)

        hi = QRectF(keyrect.left() + dia * 0.13, keyrect.top() + dia * 0.075,
                    dia * 0.74, dia * 0.42)
        hg = QLinearGradient(hi.topLeft(), hi.bottomLeft())
        hg.setColorAt(0.0, QColor(255, 255, 255, 104))
        hg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hg))
        p.drawRoundedRect(hi, rad * 0.8, rad * 0.8)

        if sk.get('orbit') and self.playing:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(acc.red(), acc.green(), acc.blue(), 130),
                          max(1.0, dia * 0.042), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            ar = dia * 0.63
            ang = (self._anim_t * 54.0) % 360.0
            p.drawArc(QRectF(c.x() - ar, c.y() - ar, ar * 2, ar * 2),
                      int(-ang * 16), int(126 * 16))

        self._paint_icon(p, kind, keyrect, QColor(9, 12, 18, 236),
                         scale=0.44 * (1.0 + 0.04 * sp))

    # ── paint ────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        pane, info, seek, grip, hits = self._compute_layout()
        self._pane_rect, self._info_rect, self._seek_rect = pane, info, seek
        self._grip_rect, self._hits = grip, hits

        t = self.t
        w, h = max(1, self.width()), max(1, self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        if self.shape == 'circle':
            self._paint_circle(p, w, h)
            self._paint_grip(p, grip, _qcolor(t.get('accent', '#00e676'), 1.0))
            p.end()
            return

        acc = _qcolor(t.get('accent', '#00e676'), 1.0)

        # ── background: an opaque, theme-coloured card (or glass / clear) ──
        bg_mode = getattr(self, 'bg_mode', 'opaque')
        if bg_mode in ('opaque', 'glass'):
            bg_alpha = 1.0 if bg_mode == 'opaque' else 0.62
            card_path = QPainterPath()
            card_path.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 12, 12)
            card_grad = QLinearGradient(0, 0, w, h)
            c_top = _qcolor(t.get('bg_card', '#131823'), 1.0)
            c_top.setAlphaF(bg_alpha)      # theme rgba() must not thin the card
            c_bot = _qcolor(t.get('bg', '#0d1117'), 1.0)
            c_bot.setAlphaF(bg_alpha)
            card_grad.setColorAt(0.0, c_top)
            card_grad.setColorAt(1.0, c_bot)
            p.setPen(Qt.PenStyle.NoPen)
            p.fillPath(card_path, QBrush(card_grad))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(_qcolor(t.get('border', '#00e676'), 0.45), 1.0))
            p.drawPath(card_path)
        acc2 = _qcolor(t.get('accent2', '#00b0ff'), 1.0)
        txt = _qcolor(t.get('text', '#f8fafc'), 1.0)
        dim = _qcolor(t.get('text_dim', '#94a3b8'), 1.0)


        # ── the pane has no background at all: the visualizer paints its own
        #    bars straight through, so only album art needs a surface ──
        if not self._pane_is_vis():
            self._paint_art(p, pane)


        # ── type ──
        self._paint_info(p, info, txt, dim)

        # ── rating stars for the playing track ──
        self._paint_stars(p, self._star_row, acc, acc2, dim)

        # ── seek + transport + rail + grip ──
        self._paint_seek(p, seek, acc, acc2, dim)
        self._paint_transport(p, hits, acc, dim)
        self._paint_rail(p, hits, acc, dim)
        self._paint_grip(p, grip, acc)

        # ── one thin frame around the whole gadget (thickness adjustable) ──
        bw = max(0.0, float(self.border_w))
        if bw > 0:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(acc.red(), acc.green(), acc.blue(), 140), bw))
            p.drawRoundedRect(QRectF(bw / 2.0, bw / 2.0, w - bw, h - bw), 12, 12)
        p.end()

    def _paint_art(self, p, pane):
        path = QPainterPath()
        path.addRoundedRect(pane, 11, 11)
        p.save()
        p.setClipPath(path)
        if self._art is not None and not self._art.isNull():
            tw, th = max(1, int(pane.width())), max(1, int(pane.height()))
            if self._art_scaled is None or self._art_scaled_for != (tw, th):
                self._art_scaled = self._art.scaled(
                    tw, th,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                self._art_scaled_for = (tw, th)
            if self._art_scaled is not None:
                p.drawPixmap(int(pane.x()), int(pane.y()), self._art_scaled)
        else:
            g = QRadialGradient(pane.center(), max(12.0, pane.width() * 0.62))
            g.setColorAt(0.0, _qcolor(self.t.get('accent', '#00e676'), 0.34))
            g.setColorAt(1.0, _qcolor(self.t.get('accent2', '#00b0ff'), 0.0))
            p.fillRect(pane, QBrush(g))
            f = QFont('Segoe UI', max(11, int(pane.height() * 0.30)))
            f.setWeight(QFont.Weight.Black)
            p.setFont(f)
            p.setPen(_qcolor(self.t.get('text', '#ffffff'), 0.9))
            glyph = (self._title[:1] or '♪').upper()
            p.drawText(pane, Qt.AlignmentFlag.AlignCenter, glyph)
        p.restore()

    def _paint_info(self, p, info, txt, dim):
        avail = max(10.0, info.width())
        f = QFont('Segoe UI', 12 if info.width() > 150 else 11)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        fm = p.fontMetrics()
        title = self._title or 'No media loaded'
        top = info.top() + fm.ascent() + 1
        p.save()
        p.setClipRect(QRectF(info.left(), info.top() - 2, avail, fm.height() + 4))
        tw = fm.horizontalAdvance(title)
        if tw <= avail:
            self._styled_text(p, info.left(), top, title, txt)
        elif self._hover:
            span = tw + 54
            off = (self._anim_t * 26.0) % span
            x = info.left() - off
            self._styled_text(p, x, top, title, txt)
            self._styled_text(p, x + span, top, title, txt)
        else:
            self._styled_text(p, info.left(), top,
                              fm.elidedText(title, Qt.TextElideMode.ElideRight, int(avail)), txt)
        p.restore()

        fa = QFont('Segoe UI', 9)
        p.setFont(fa)
        fm2 = p.fontMetrics()
        y2 = top + fm2.height() + 1
        line = fm2.elidedText(self._artist or '', Qt.TextElideMode.ElideRight, int(avail))
        p.save()
        p.setClipRect(QRectF(info.left(), y2 - fm2.ascent() - 1, avail, fm2.height() + 3))
        self._styled_text(p, info.left(), y2, line, dim)
        p.restore()

    def _paint_seek(self, p, seek, acc, acc2, dim):
        dur = max(1, self.duration_ms)
        frac = max(0.0, min(1.0, self.position_ms / float(dur)))
        buf = max(0.0, min(1.0, self.buffered if self.buffered <= 1.0 else self.buffered / 100.0))

        # no time readouts: the knob and the dial say where we are, and the bar
        # gets the whole row instead of two 34 px text gutters
        bar_x = seek.left()
        bar_w = max(20.0, seek.width())
        cy = seek.center().y()
        th = max(2.0, float(self._track_h.value))
        track = QRectF(bar_x, cy - th / 2, bar_w, th)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 165))
        p.drawRoundedRect(track.adjusted(-0.8, -0.8, 0.8, 0.8), th / 2 + 1.2, th / 2 + 1.2)
        p.setBrush(QColor(255, 255, 255, 26))
        p.drawRoundedRect(track, th / 2, th / 2)
        p.setBrush(QColor(255, 255, 255, 34))
        p.drawRoundedRect(QRectF(track.left() + 2, track.top() + 0.7,
                                 max(1.0, track.width() - 4), 1.0), 0.5, 0.5)
        if buf > 0.01:
            p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 70))
            p.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * buf, track.height()),
                              th / 2, th / 2)

        if frac > 0:
            played = QRectF(track.left(), track.top(), max(1.0, track.width() * frac), track.height())
            g = QLinearGradient(track.left(), 0, track.right(), 0)
            g.setColorAt(0.0, acc)
            g.setColorAt(1.0, acc2)
            # glow under the played portion, painted as widening low-alpha strokes
            for infl, a in ((4.8, 26), (2.7, 54), (1.1, 100)):
                p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), a))
                p.drawRoundedRect(played.adjusted(-infl, -infl, infl, infl),
                                  th / 2 + infl, th / 2 + infl)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(played, th / 2, th / 2)

            # knob
            knob = max(2.6, float(self._thumb.value))
            kx = played.right()
            halo = QRadialGradient(QPointF(kx, cy), knob + 9.0)
            halo.setColorAt(0.0, QColor(acc.red(), acc.green(), acc.blue(), 155))
            halo.setColorAt(1.0, QColor(acc.red(), acc.green(), acc.blue(), 0))
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(kx, cy), knob + 9.0, knob + 9.0)
            p.setBrush(QColor(255, 255, 255, 245))
            p.drawEllipse(QPointF(kx, cy), knob, knob)
            p.setBrush(acc)
            p.drawEllipse(QPointF(kx, cy), knob * 0.50, knob * 0.50)

        # a minute tick every 60 s keeps the scale readable without any numerals
        if seek.width() > 120.0:
            step = max(24.0, track.width() / max(1.0, self.duration_ms / 60000.0))
            x = track.left() + step
            p.setPen(QPen(QColor(255, 255, 255, 40), 1.0))
            while x < track.right() - 3.0:
                p.drawLine(QPointF(x, cy - 2.4), QPointF(x, cy + 2.4))
                x += step

    def _paint_transport(self, p, hits, acc, dim):
        sk = self._skin()
        plate = sk.get('plate', 'glass')
        for name, kind in (('prev', 'prev'), ('play', 'pause' if self.playing else 'play'),
                           ('next', 'next')):
            r = hits.get(name)
            if r is None:
                continue
            sp = self._btn_scale[name].value
            hot = self._hover_hit == name
            down = self._active_hit == name
            if name == 'play':
                self._paint_key(p, r, acc, sk, hot, down, sp, kind)
                continue
            rr = QRectF(r)
            rr.translate(0.0, -0.9 * (sp - 1.0) * 4.0)      # hover lift
            rad = rr.height() * (0.34 if sk.get('key') != 'circle' else 0.5)
            if plate != 'none':
                edge = 58 if hot else (64 if plate == 'hairline' else 32)
                p.setPen(QPen(QColor(255, 255, 255, edge), 1.0))
                p.setBrush(QColor(255, 255, 255, 20 if plate == 'glass' else 0))
                p.drawRoundedRect(rr, rad, rad)
            if hot or down:
                wash = QColor(acc)
                wash.setAlphaF(0.22 if down else 0.16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(wash)
                p.drawRoundedRect(rr.adjusted(-1.0, -1.0, 1.0, 1.0), rad + 1.0, rad + 1.0)
            self._paint_icon(p, kind, rr, acc if hot else dim, scale=0.60 * sp)

        vr = hits.get('vol')
        if vr is not None:
            vol = self._volume()
            hot = self._hover_hit == 'vol' or self._active_hit == 'vol'
            th = max(2.0, float(self._vol_h.value))
            track = QRectF(vr.left(), vr.center().y() - th / 2, vr.width(), th)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 130))
            p.drawRoundedRect(track.adjusted(-0.6, -0.6, 0.6, 0.6), th / 2 + 1, th / 2 + 1)
            p.setBrush(_qcolor(self.t.get('track', '#18202e'), 0.95))
            p.drawRoundedRect(track, th / 2, th / 2)
            filled = QRectF(track.left(), track.top(), max(1.0, track.width() * vol / 100.0), track.height())
            p.setBrush(acc)
            p.drawRoundedRect(filled, th / 2, th / 2)
            knob_x, knob_y = filled.right(), track.center().y()
            kr = max(2.6, th * 0.72)
            if hot:
                halo = QColor(acc)
                halo.setAlphaF(0.34)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(QPointF(knob_x, knob_y), kr * 2.1, kr * 2.1)
            p.setPen(QPen(QColor(255, 255, 255, 214), 1.0))
            p.setBrush(QColor(255, 255, 255, 255 if hot else 208))
            p.drawEllipse(QPointF(knob_x, knob_y), kr, kr)

    def _paint_rail(self, p, hits, acc, dim):
        glass = self._skin().get('plate', 'glass') != 'none'
        for name, kind in (('restore', 'close'), ('pin', 'pin'), ('pane', 'pane'),
                           ('size', 'size'), ('gear', 'gear')):
            r = hits.get(name)
            if r is None:
                continue
            hot = self._hover_hit == name
            on = (name == 'pin' and self.pinned)
            rr = QRectF(r)
            if glass and (hot or on):
                wash = QColor(acc)
                wash.setAlphaF(0.20 if on else 0.13)
                p.setPen(QPen(QColor(255, 255, 255, 58 if on else 40), 1.0))
                p.setBrush(wash)
                p.drawRoundedRect(rr.adjusted(-2.0, -2.0, 2.0, 2.0), 7.0, 7.0)
            col = acc if (hot or on) else dim
            sp = self._btn_scale[name].value
            if name == 'restore':
                self._paint_icon(p, 'close', rr, col, sp)
            else:
                self._paint_icon(p, kind, rr, col, sp, filled=on)

    def _paint_grip(self, p, grip, acc):
        """Resize handle in the bottom-right corner, shown on hover only.
        It appears while the pointer is over the gadget and fades out again when it
        leaves — a spring drives the alpha, so it never pops. Hover is read from the
        real cursor position rather than enter/leave, which churns on Windows every
        time setCursor() runs; that flicker is why an earlier hover-gated grip blinked.
        A dark plate under the accent keeps it readable on any wallpaper, and the
        accent brightens further while the pointer is on the handle or a resize is live.
        """
        a = getattr(self, '_grip_a', None)
        a = max(0.0, min(1.0, float(a.value))) if a is not None else 1.0
        if a <= 0.03:
            return                       # fully faded out: nothing to draw
        hot = self._hover_hit == 'grip' or self._resize_from is not None
        side = 18.0
        r = QRectF(grip.right() - side - 1.0, grip.bottom() - side - 1.0, side, side)
        if hot:
            r.adjust(-1.5, -1.5, 0.0, 0.0)

        # dark plate first: the bare accent washed out on bright wallpapers
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, int((150 if hot else 118) * a)))
        p.drawRoundedRect(r.adjusted(-2.6, -2.6, 2.2, 2.2), 6.0, 6.0)

        tri = QPainterPath()
        tri.moveTo(r.right(), r.top() + 2.0)
        tri.lineTo(r.right(), r.bottom())
        tri.lineTo(r.left() + 2.0, r.bottom())
        tri.closeSubpath()

        p.setPen(QPen(QColor(0, 0, 0, int(200 * a)), 1.3,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        fill = QColor(acc)
        if hot:
            fill = QColor(min(255, acc.red() + 45), min(255, acc.green() + 45),
                          min(255, acc.blue() + 45))
        fill.setAlpha(int((255 if hot else 232) * a))
        p.setBrush(fill)
        p.drawPath(tri)

        # three ribs so the corner reads as a grip, opaque enough to survive
        # the translucent idle state
        dark = QColor(0, 0, 0, int((170 if hot else 145) * a))
        p.setPen(QPen(dark, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for off in (5.5, 10.0, 14.5):
            if off >= side - 1.0:
                continue
            p.drawLine(QPointF(r.right() - off, r.bottom() - 1.5),
                       QPointF(r.right() - 1.5, r.bottom() - off))

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(ms):
        ms = max(0, int(ms or 0))
        s = ms // 1000
        return "%d:%02d" % (s // 60, s % 60)

    def _volume(self):
        try:
            return int(round(self.main.audio_out.volume() * 100))
        except Exception:
            return 70

    def _set_volume(self, v):
        v = max(0, min(100, int(v)))
        try:
            self.main.audio_out.setVolume(v / 100.0)
            self.main.battery_volume.set_volume(v)
        except Exception:
            pass
        self.update()

    def _seek_hit_rect(self):
        # the seek bar spans the row minus the two time labels
        s = self._seek_rect
        label_w = 34.0
        return QRectF(s.left() + label_w, s.center().y() - 7, max(20.0, s.width() - label_w * 2), 14)

    def _seek_from_x(self, x, r):
        frac = 0.0 if r.width() <= 0 else (x - r.left()) / r.width()
        return max(0.0, min(1.0, frac)) * max(0, self.duration_ms)

    def _vol_from_x(self, x, r):
        frac = 0.0 if r.width() <= 0 else (x - r.left()) / r.width()
        return int(round(max(0.0, min(1.0, frac)) * 100))

    def _seek_to(self, ms):
        try:
            self.main.player.setPosition(int(max(0, ms)))
        except Exception:
            pass
        self.position_ms = int(max(0, ms))
        self.update()

    # ── input ────────────────────────────────────────────────────────────────
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._hover_hit = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.position()
        gp = event.globalPosition().toPoint()

        if self.shape == 'circle' and self._circle_press(pos, gp):
            event.accept()
            return

        si = self._star_index_at(pos)
        if si is not None:
            self._set_rating(si + 1)
            event.accept()
            return

        if self._grip_rect.contains(pos):
            self._resize_from = (gp, self.width(), self.height())
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            event.accept()
            return

        for name, r in self._hits.items():
            if r.contains(pos):
                self._active_hit = name
                if name == 'gear':
                    self.open_settings()
                    event.accept()
                    return
                if name == 'vol':
                    self._set_volume(self._vol_from_x(pos.x(), r))
                event.accept()
                return

        seek_r = self._seek_hit_rect()
        if seek_r.contains(pos):
            self._active_hit = 'seek'
            self._seek_to(self._seek_from_x(pos.x(), seek_r))
            event.accept()
            return

        if self._pane_rect.contains(pos):
            self.cycle_pane()
            event.accept()
            return

        self._drag_from = gp - self.frameGeometry().topLeft()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position()
        gp = event.globalPosition().toPoint()

        if self.shape == 'circle' and self._circle_move(pos, gp):
            event.accept()
            return

        if self._resize_from is not None:
            (start_gp, w0, h0) = self._resize_from
            dx = gp.x() - start_gp.x()
            dy = gp.y() - start_gp.y()
            nw = max(self.MIN_W, min(self.MAX_W, w0 + dx))
            nh = max(self.MIN_H, min(self.MAX_H, h0 + dy))
            if self.shape == 'circle':
                nh = nw = max(self.MIN_W, min(self.MAX_W, max(nw, nh)))
            self.resize(int(nw), int(nh))
            self.size_key = 'custom'
            self._custom_wh = (int(nw), int(nh))
            self._layout_pane()
            event.accept()
            return

        if self._active_hit == 'vol':
            r = self._hits.get('vol')
            if r is not None:
                self._set_volume(self._vol_from_x(pos.x(), r))
            event.accept()
            return
        if self._active_hit == 'seek':
            r = self._seek_hit_rect()
            self._seek_to(self._seek_from_x(pos.x(), r))
            event.accept()
            return
        if self._drag_from is not None:
            self.move(gp - self._drag_from)
            event.accept()
            return

        hot = None
        si = self._star_index_at(pos)
        if self._grip_rect.contains(pos):
            hot = 'grip'
        elif si is not None:
            hot = 'star%d' % si
        elif self._seek_hit_rect().contains(pos):
            hot = 'seek'
        else:
            for name, r in self._hits.items():
                if r.contains(pos):
                    hot = name
                    break
        if hot != self._hover_hit:
            self._hover_hit = hot
            if hot == 'grip':
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif hot is not None or self._pane_rect.contains(pos):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.shape == 'circle' and self._circle_release():
            event.accept()
            return
        if self._resize_from is not None:
            self._resize_from = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._save()
            event.accept()
            return

        if self._drag_from is not None:
            self._drag_from = None
            self._user_positioned = True
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if self.snap_edges:
                self._snap()
            self._save()
            event.accept()
            return

        name = self._active_hit
        self._active_hit = None
        if name == 'prev':
            self.main._prev_track()
        elif name == 'next':
            self.main._next_track()
        elif name == 'play':
            self.main._toggle_play()
        elif name == 'restore':
            self.main._exit_gadget_mode()
        elif name == 'pin':
            self.toggle_pin()
        elif name == 'size':
            self.cycle_size()
        elif name == 'pane':
            self.cycle_pane()
        elif name == 'gear':
            pass                       # the settings opened on press already
        elif name in ('vol', 'seek'):
            self._save()
        event.accept()

    def set_shape(self, shape, animate=True):
        """Flip the gadget between the card panel and the circular dial.

        The two shapes want different footprints (the card is a wide panel, the
        dial is square) and different layout tables, so this is a real resize +
        re-layout, not a repaint. Double-click used to assign the attribute
        straight and leave the dial's square frame behind the card.
        """
        shape = 'circle' if shape == 'circle' else 'card'
        if shape == self.shape:
            return False
        self.shape = shape
        keys = [s[0] for s in self.SIZES]
        if self.size_key not in keys:
            self.size_key = 'm'
        self._custom_wh = None          # each shape owns its own footprint
        self._place()
        try:
            self._clamp()
        except Exception:
            pass
        self._layout_pane()
        self._pane_rect = QRectF()
        self.update()
        try:
            self.main._sync_view_mode_from_gadget(self.shape)
        except Exception:
            pass
        self._save()
        return True

    def mouseDoubleClickEvent(self, event):
        if self.shape == 'circle':
            self.set_shape('card')
            event.accept()
            return
        if self._pane_rect.contains(event.position()):
            self.cycle_pane()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        step = event.angleDelta().y() / 120.0
        if step == 0:
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.opacity_val = max(0.35, min(1.0, self.opacity_val + 0.03 * step))
            self.setWindowOpacity(self.opacity_val)
            self._save()
        else:
            self._set_volume(self._volume() + int(2 * step))
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.main._exit_gadget_mode()
            return
        if key == Qt.Key.Key_Space:
            self.main._toggle_play()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            delta = -5000 if key == Qt.Key.Key_Left else 5000
            self._seek_to(max(0, self.position_ms + delta))
            try:
                self.main.player.setPosition(int(max(0, self.position_ms)))
            except Exception:
                pass
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        t = self.t
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:%s;color:%s;border:1px solid %s;border-radius:8px;padding:4px;}"
            "QMenu::item{padding:5px 18px;border-radius:5px;}"
            "QMenu::item:selected{background:%s;}"
            % (t.get('bg', '#0d1117'), t.get('text', '#f8fafc'),
               t.get('accent', '#00e676') + '66', t.get('accent', '#00e676') + '33'))
        for label, mode in (('Visualizer pane', 'vis'), ('Album art pane', 'art'), ('Auto pane', 'auto')):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.pane_mode == mode)
            act.triggered.connect(lambda _=False, mm=mode: (self.set_pane_mode(mm), self._save()))
        menu.addSeparator()
        for label, key in (('Small', 's'), ('Medium', 'm'), ('Large', 'l')):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.size_key == key)
            act.triggered.connect(lambda _=False, kk=key: (self.set_size_key(kk), self._save()))
        menu.addSeparator()
        pin = menu.addAction('Always on top')
        pin.setCheckable(True)
        pin.setChecked(self.pinned)
        pin.triggered.connect(self.toggle_pin)
        snap = menu.addAction('Snap to screen edges')
        snap.setCheckable(True)
        snap.setChecked(self.snap_edges)
        snap.triggered.connect(lambda: (setattr(self, 'snap_edges', not self.snap_edges), self._save()))
        menu.addSeparator()
        bg_menu = menu.addMenu('Background')
        for label, mode in (('Opaque card', 'opaque'), ('Glass', 'glass'),
                            ('Transparent', 'clear')):
            act = bg_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.bg_mode == mode)
            act.triggered.connect(
                lambda _=False, mm=mode: (setattr(self, 'bg_mode', mm), self.update(), self._save()))
        vis_menu = menu.addMenu('Visualizer')
        mode_menu = vis_menu.addMenu('Mode')
        for mode_key in self.VIS_MODES:
            act = mode_menu.addAction(ModernVisualizer.MODE_LABELS.get(mode_key, mode_key))
            act.setCheckable(True)
            act.setChecked(self.vis_mode == mode_key)
            act.triggered.connect(lambda _=False, mm=mode_key: self.set_vis_mode(mm))
        col_menu = vis_menu.addMenu('Colour')
        for key, label, *_rest in GADGET_PALETTES:
            act = col_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.vis_palette == key)
            act.triggered.connect(lambda _=False, kk=key: self.set_vis_palette(kk))
        ring_menu = vis_menu.addMenu('Ring motion')
        on_act = ring_menu.addAction('Rotating')
        on_act.setCheckable(True)
        on_act.setChecked(bool(self.rotate))
        on_act.triggered.connect(lambda _=False: self.set_ring_rotate(True))
        off_act = ring_menu.addAction('Fixed (still)')
        off_act.setCheckable(True)
        off_act.setChecked(not self.rotate)
        off_act.triggered.connect(lambda _=False: self.set_ring_rotate(False))
        ring_menu.addSeparator()
        for label, sp in (('Slow', 6.0), ('Medium', 14.0), ('Fast', 28.0),
                          ('Very fast', 50.0)):
            act = ring_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(abs(self.rot_speed - sp) < 0.6 and self.rotate)
            act.triggered.connect(lambda _=False, sp=sp: self.set_rot_speed(sp))
        border_menu = menu.addMenu('Border')
        for label, bw in (('Off', 0.0), ('Hairline (1 px)', 1.0),
                          ('1.5 px', 1.5), ('2 px', 2.0), ('3 px', 3.0)):
            act = border_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(abs(float(self.border_w) - bw) < 0.01)
            act.triggered.connect(
                lambda _=False, v=bw: (setattr(self, 'border_w', v), self.update(), self._save()))
        menu.addSeparator()
        view_menu = menu.addMenu('Appearance mode')
        for label, mm in (('▣  Full window   ·  Ctrl+1', 'full'),
                          ('▬  Card HUD      ·  Ctrl+2', 'card'),
                          ('◉  Dial HUD      ·  Ctrl+3', 'dial')):
            act = view_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(getattr(self.main, '_view_mode', 'card') == mm)
            act.triggered.connect(lambda _=False, m=mm: self.main.set_view_mode(m))
        menu.addSeparator()
        menu.addAction('Restore main window').triggered.connect(self.main._exit_gadget_mode)
        gp = event.globalPos() if hasattr(event, 'globalPos') else event.globalPosition().toPoint()
        menu.exec(gp)

# ── circular dial (shape == 'circle') ───────────────────────────────────
    @staticmethod
    def _mix(c1, c2, f):
        f = max(0.0, min(1.0, f))
        return QColor(int(c1.red() + (c2.red() - c1.red()) * f),
                      int(c1.green() + (c2.green() - c1.green()) * f),
                      int(c1.blue() + (c2.blue() - c1.blue()) * f))

    def _active_band_count(self):
        """Bands the *dial* can resolve.

        The spoke pattern is mirrored, so only half the ring carries unique
        content and that half-turn should show the whole analysed spectrum. The
        old count came from the hidden visualizer pane's width (``width // 9``,
        floored at 48), which collapsed the dial onto the first ~48 bands --
        25-280 Hz. Everything the ring drew was bass, so all spokes swelled in
        unison with the kick and the dial read as a plain pulsing circle.
        """
        try:
            lobes = max(1, self._spoke_count() // 2)
        except Exception:
            lobes = 96
        return max(48, min(128, lobes))

    def _spoke_count(self):
        R = self._circle_r()
        return 264 if R > 190 else (232 if R > 150 else 200)

    def _update_ring_levels(self, dt):
        """Per-spoke attack/decay so the dial moves like a real meter.

        The frame source is the track's own analysis table, so the ring shows
        the whole log spectrum; the engine's spring-smoothed levels are only a
        stand-in until that buffer exists, and the engine only fills the first
        `active_bands` slots -- so the fallback is mapped across those and never
        indexed past what the engine actually wrote. Neighbouring bands are
        interpolated for a continuous gradient.
        """
        n = self._spoke_count()
        if len(self._lv) < n:
            pad = n - len(self._lv)
            self._lv += [0.0] * pad
            self._pk += [0.0] * pad
            self._pk_hold += [0.0] * pad
        # raw analysis frame first: the engine's springs level everything out,
        # and a flat ring is exactly what we do not want here
        levels = []
        from_frame = False
        try:
            buf = self.vis.audio_buffer
            if buf is not None and self.playing:
                frame = buf.analysis_frame(self.position_ms / 1000.0)
                if frame and frame[0] is not None:
                    levels = [float(v) for v in frame[0]]
                    from_frame = True
        except Exception:
            levels = []

        if not levels:
            try:
                levels = list(self.vis.engine.levels)
            except Exception:
                levels = []
        nb = self._active_band_count()
        if levels:
            nb = max(1, min(nb, len(levels)))
        if not from_frame:
            filled = int(getattr(self.vis.engine, 'active_bands', 0) or 0)
            if filled:
                nb = max(1, min(nb, filled))
        att = 1.0 - math.exp(-max(0.001, dt) / 0.026)
        rel = 1.0 - math.exp(-max(0.001, dt) / 0.34)
        decay = 1.0 - math.exp(-max(0.001, dt) / 0.55)
        for i in range(n):
            f = i / float(n)
            k = f * 2.0
            if k > 1.0:
                k = 2.0 - k
            if levels:
                pos = k * (nb - 1)
                i0 = int(pos)
                fr = pos - i0
                a = levels[i0]
                b = levels[min(nb - 1, i0 + 1)]
                target = a + (b - a) * fr
                # local-mean high pass: pulls peaks up and troughs down so the
                # ring reads as a wave instead of a smooth ramp
                j0 = max(0, i0 - 2)
                j1 = min(nb - 1, i0 + 2)
                loc = sum(levels[j0:j1 + 1]) / float(max(1, j1 - j0 + 1))
                target = loc + (target - loc) * 2.65
            else:
                target = 0.0
            if not self.playing:
                # still: every spoke sinks to a short quiet stub, so the gap
                # between resting and live bands is unmistakable
                target = 0.03
            else:
                # travelling ripple + gain + gamma: deep troughs, tall crests.
                # RING_DRIVE is deliberately below the old 1.85: with the whole
                # spectrum on the dial the extra push clipped over half the
                # spokes to full length, which flattened the crests into a
                # solid circular wall exactly when the music got loud.
                wave = 0.88 + 0.24 * (0.5 + 0.5 * math.sin(i * 0.27 + self._anim_t * 1.7))
                target = min(1.0, (max(0.0, target) ** 0.70) * self.RING_DRIVE * wave)
            target = max(0.0, min(1.0, target))
            cur = self._lv[i]
            step = (target - cur) * (att if target > cur else rel)
            if step > 0:
                step = min(target - cur, step * 1.45)   # whip, not glide
            cur += step
            self._lv[i] = cur
            if cur >= self._pk[i]:
                self._pk[i] = cur
                self._pk_hold[i] = 0.26
            elif self._pk_hold[i] > 0:
                self._pk_hold[i] -= dt
            else:
                self._pk[i] += (cur - self._pk[i]) * decay

    def _ring_colour(self, f):
        # continuous colour sweep around the dial: the gadget's own palette
        # when one is set, otherwise the reference sweep or the app theme
        f = max(0.0, min(1.0, f))
        _, _label, a1, a2, a3 = gadget_palette(self.vis_palette)
        if a1:
            stops = (QColor(a1), QColor(a2), QColor(a3))
        elif self.ring_palette == 'theme':
            t = self.t
            stops = (_qcolor(t.get('accent', '#00e676'), 1.0),
                     _qcolor(t.get('accent2', '#00b0ff'), 1.0),
                     _qcolor(t.get('accent3', '#00f0ff'), 1.0))
        else:
            stops = (QColor('#7b2ff7'), QColor('#c026d3'),
                     QColor('#f43f5e'), QColor('#ff7a18'))
        x = f * (len(stops) - 1)
        i = min(len(stops) - 2, int(x))
        return self._mix(stops[i], stops[i + 1], x - i)

    def _is_hovered(self):
        """True while the pointer is really over the gadget.

        enterEvent/leaveEvent churn on Windows whenever the cursor shape
        changes (every hover-crossing calls setCursor()), and that made the
        resize grip blink. The pointer's actual position is asked at paint
        time first; the enter/leave flag is only a fallback.
        """
        if self._drag_from is not None or self._resize_from is not None:
            return True
        try:
            if self.isVisible():
                local = self.mapFromGlobal(QCursor.pos())
                if self.rect().contains(local):
                    return True
        except Exception:
            pass
        try:
            if self.underMouse():
                return True
        except Exception:
            pass
        return bool(self._hover)

    def _circle_r(self):
        return max(24.0, min(self.width(), self.height()) / 2.0 - 4.0)

    def _ring_radii(self, R):
        return R * 0.60, R * 0.475          # seek ring, volume ring

    def _compute_circle_layout(self):
        w, h = max(1, self.width()), max(1, self.height())
        R = self._circle_r()
        cx, cy = w / 2.0, h / 2.0
        pane = QRectF(0, 0, w, h)

        hits = {}
        # Row 2 (middle): transport row - centered vertically at cy
        ty = cy
        isz = max(8.5, R * 0.076)
        key_r = isz * 1.16
        gap = R * 0.195
        hits['prev'] = QRectF(cx - gap - isz, ty - isz, isz * 2, isz * 2)
        hits['play'] = QRectF(cx - key_r, ty - key_r, key_r * 2, key_r * 2)
        hits['next'] = QRectF(cx + gap - isz, ty - isz, isz * 2, isz * 2)

        # Row 3 (bottom): utility dock - centered horizontally, placed symmetrically below cy
        uy = cy + R * 0.185
        ugap = R * 0.116
        us = max(5.5, R * 0.038)
        hw = ugap * 0.5
        hh = max(10.0, us * 1.45)
        self._util_slots = []
        for k, name in enumerate(('pin', 'pane', 'gear', 'size', 'restore')):
            cxk = cx + (k - 2.0) * ugap
            hit = QRectF(cxk - hw, uy - hh, hw * 2, hh * 2)
            hits[name] = hit
            glyph = QRectF(cxk - us, uy - us, us * 2, us * 2)
            kind = 'close' if name == 'restore' else name
            self._util_slots.append((name, kind, hit, glyph))
        self._util_us = us
        self._util_dock = QRectF(cx - 2.0 * ugap - hw - 3.5, uy - hh - 2.0,
                                 4.0 * ugap + 2.0 * hw + 7.0, 2.0 * hh + 4.0)

        # Row 1 (top): rating row - centered horizontally, placed symmetrically above cy
        ss = max(4.0, R * 0.036)
        sgap = max(1.8, ss * 0.44)
        star_sz = ss * 2.0
        row_w = 5 * star_sz + 4 * sgap
        row_y = cy - R * 0.185
        self._star_row = QRectF(cx - row_w / 2.0, row_y - ss, row_w, star_sz)
        for i in range(5):
            hits['star%d' % i] = QRectF(cx - row_w / 2.0 + i * (star_sz + sgap),
                                        row_y - ss, star_sz, star_sz)

        gw = max(42.0, R * 0.25)
        gh = max(15.0, R * 0.074)
        hits['grab'] = QRectF(cx - gw / 2.0, cy - R * 0.665 - gh / 2.0, gw, gh)

        grip = QRectF(w - self.GRIP - 2, h - self.GRIP - 2, self.GRIP, self.GRIP)
        return pane, QRectF(), QRectF(), grip, hits

    def _circle_angle(self, pos):
        cx, cy = self.width() / 2.0, self.height() / 2.0
        return (math.degrees(math.atan2(pos.y() - cy, pos.x() - cx)) + 360.0) % 360.0

    def _circle_seek(self, pos):
        frac = ((self._circle_angle(pos) - 120.0) % 360.0) / 300.0
        self._seek_to(max(0.0, min(1.0, frac)) * max(0, self.duration_ms))

    def _circle_set_volume(self, pos):
        frac = ((self._circle_angle(pos) - 210.0) % 360.0) / 120.0
        self._set_volume(int(round(max(0.0, min(1.0, frac)) * 100)))

    def _circle_press(self, pos, gp):
        si = self._star_index_at(pos)
        if si is not None:
            self._set_rating(si + 1)
            return True
        gr = self._hits.get('grab')
        if gr is not None and gr.contains(pos):
            self._drag_from = gp - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
        for name, r in self._hits.items():
            if r.contains(pos):
                self._active_hit = name
                if name == 'gear':
                    self.open_settings()
                return True
        R = self._circle_r()
        r_seek, r_vol = self._ring_radii(R)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        rad = math.hypot(pos.x() - cx, pos.y() - cy)
        if abs(rad - r_vol) <= max(9.0, R * 0.035):
            self._active_hit = 'volring'
            self._circle_set_volume(pos)
            return True
        if abs(rad - r_seek) <= max(11.0, R * 0.042):
            self._active_hit = 'seekring'
            self._circle_seek(pos)
            return True
        return False

    def _circle_move(self, pos, gp):
        if self._active_hit == 'seekring':
            self._circle_seek(pos)
            return True
        if self._active_hit == 'volring':
            self._circle_set_volume(pos)
            return True
        if self._drag_from is not None or self._resize_from is not None:
            return False
        hot = None
        if self._grip_rect.contains(pos):
            hot = 'grip'
        else:
            for name, r in self._hits.items():
                if r.contains(pos):
                    hot = name
                    break
            if hot is None:
                R = self._circle_r()
                r_seek, r_vol = self._ring_radii(R)
                cx, cy = self.width() / 2.0, self.height() / 2.0
                rad = math.hypot(pos.x() - cx, pos.y() - cy)
                if abs(rad - r_vol) <= max(9.0, R * 0.035):
                    hot = 'volring'
                elif abs(rad - r_seek) <= max(11.0, R * 0.042):
                    hot = 'seekring'
        if hot != self._hover_hit:
            self._hover_hit = hot
            self._apply_cursor(hot)
            self.update()
        return True

    def _apply_cursor(self, hit):
        if hit == 'grab':
            shape = Qt.CursorShape.SizeAllCursor
        elif hit == 'grip':
            shape = Qt.CursorShape.SizeFDiagCursor
        elif hit:
            shape = Qt.CursorShape.PointingHandCursor
        else:
            shape = Qt.CursorShape.ArrowCursor
        try:
            if self.cursor().shape() != shape:
                self.setCursor(shape)
        except Exception:
            pass

    def _circle_release(self):
        if self._active_hit in ('seekring', 'volring'):
            self._active_hit = None
            self._save()
            return True
        return False

    def _paint_circle(self, p, w, h):
        R = self._circle_r()
        cx, cy = w / 2.0, h / 2.0
        dur = max(1, self.duration_ms)
        frac = max(0.0, min(1.0, self.position_ms / float(dur)))
        vol = self._volume() / 100.0
        r_seek, r_vol = self._ring_radii(R)

        # spectrum: fine dotted spokes, mirrored, per-spoke attack/decay
        n = self._spoke_count()
        r0 = R * 0.715
        max_len = R * 0.270
        base_dot = max(0.62, R * 0.0062)
        C = 16
        buckets = {}
        tips = []
        for i in range(n):
            f = i / float(n)
            th = math.radians(-90.0 + self._rot_phase + 360.0 * f)
            cos_t, sin_t = math.cos(th), math.sin(th)
            lv = self._lv[i]
            pk = self._pk[i]
            ln = max_len * (0.015 + 0.985 * (lv ** 1.18))   # troughs nearly vanish
            dots = 2 + int(15 * lv)             # density follows the band
            ci = min(C - 1, int(f * C))
            for k in range(dots):
                fk = k / float(max(1, dots - 1))
                rad = r0 + ln * fk
                si = 0 if fk < 0.34 else (1 if fk < 0.67 else 2)
                buckets.setdefault((si, ci), []).append(
                    QPointF(cx + cos_t * rad, cy + sin_t * rad))
            if pk > 0.10:
                rad_p = r0 + max_len * (0.015 + 0.985 * (pk ** 1.18))
                tips.append(QPointF(cx + cos_t * rad_p, cy + sin_t * rad_p))

        # constant brightness: the ring is lit the same at any volume; only
        # the spoke lengths react to the music
        gain = 1.38
        bloom = 0.13
        for (si, ci), pts in buckets.items():
            col = self._ring_colour(ci / float(C - 1))
            col = QColor(min(255, int(col.red() * gain)),
                         min(255, int(col.green() * gain)),
                         min(255, int(col.blue() * gain)))
            width = base_dot * (1.75 - 0.42 * si) * 2.0
            lv_avg = min(1.0, len(pts) / 14.0)
            alpha = (0.32 + 0.68 * lv_avg) - 0.10 * si
            alpha = max(0.0, min(1.0, alpha))
            poly = QPolygonF(pts)
            if True:
                halo = QColor(col.red(), col.green(), col.blue(),
                              int(255 * alpha * bloom * 0.55))
                p.setPen(QPen(halo, width * 2.6, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawPoints(poly)
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(255 * alpha)),
                          width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPoints(poly)
        tip_a = 235
        tip_w = max(0.9, base_dot * 1.5)
        p.setPen(QPen(QColor(255, 255, 255, 105), tip_w * 2.2,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPoints(QPolygonF(tips))
        p.setPen(QPen(QColor(255, 255, 255, tip_a), tip_w,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPoints(QPolygonF(tips))

        # circular seek ring
        start_s, sweep_s = 120.0, 300.0
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 46), max(2.4, R * 0.012),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(cx - r_seek, cy - r_seek, r_seek * 2, r_seek * 2),
                  int(-start_s * 16), int(-sweep_s * 16))
        if frac > 0.002:
            cg = QConicalGradient(cx, cy, -start_s)
            cg.setColorAt(0.0, self._ring_colour(0.02))
            cg.setColorAt(0.5, self._ring_colour(0.45))
            cg.setColorAt(1.0, self._ring_colour(0.9))
            p.setPen(QPen(QBrush(cg), max(3.4, R * 0.018),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(cx - r_seek, cy - r_seek, r_seek * 2, r_seek * 2),
                      int(-start_s * 16), int(-sweep_s * frac * 16))
        ka = math.radians(start_s + sweep_s * frac)
        kx, ky = cx + math.cos(ka) * r_seek, cy + math.sin(ka) * r_seek
        halo = QRadialGradient(QPointF(kx, ky), R * 0.075)
        hc = self._ring_colour(frac)
        halo.setColorAt(0.0, QColor(hc.red(), hc.green(), hc.blue(), 150))
        halo.setColorAt(1.0, QColor(hc.red(), hc.green(), hc.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(kx, ky), R * 0.075, R * 0.075)
        p.setBrush(QColor(255, 255, 255, 248))
        p.drawEllipse(QPointF(kx, ky), max(2.2, R * 0.012), max(2.2, R * 0.012))

        # circular volume ring (inner, bottom-left)
        start_v, sweep_v = 210.0, 120.0
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 42), max(1.8, R * 0.009),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(cx - r_vol, cy - r_vol, r_vol * 2, r_vol * 2),
                  int(-start_v * 16), int(-sweep_v * 16))
        if vol > 0.01:
            p.setPen(QPen(QColor(255, 255, 255, 205), max(2.6, R * 0.013),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(cx - r_vol, cy - r_vol, r_vol * 2, r_vol * 2),
                      int(-start_v * 16), int(-sweep_v * vol * 16))
        va = math.radians(start_v + sweep_v * vol)
        vx, vy = cx + math.cos(va) * r_vol, cy + math.sin(va) * r_vol
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(QPointF(vx, vy), max(1.8, R * 0.009), max(1.8, R * 0.009))

        # grab handle at the top of the dial — the obvious "drag me" affordance
        gr = self._hits.get('grab')
        if gr is not None and self._is_hovered():
            hot = self._hover_hit == 'grab' or self._drag_from is not None
            p.setPen(QPen(QColor(255, 255, 255, 120 if not hot else 200), 1.2))
            p.setBrush(QColor(255, 255, 255, 44 if not hot else 86))
            p.drawRoundedRect(gr, gr.height() / 2.0, gr.height() / 2.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 205 if not hot else 255))
            span = max(10.0, gr.width() * 0.26)
            for kk in (-1, 0, 1):
                p.drawEllipse(QPointF(gr.center().x() + kk * span / 2.0, gr.center().y()), 2.0, 2.0)

        # transport inside the circle, each icon with a dark keyline
        acc = self._ring_colour(0.35)
        isz = max(8.5, R * 0.076)
        ty = cy
        gap = R * 0.195
        self._paint_stars(p, self._star_row, acc, self._ring_colour(0.8),
                          QColor(255, 255, 255, 150), chip=False)

        sk = self._skin()
        key_r = isz * 1.16
        self._paint_key(p, QRectF(cx - key_r, ty - key_r, key_r * 2, key_r * 2),
                        acc, sk, self._hover_hit == 'play', self._active_hit == 'play',
                        self._btn_scale['play'].value,
                        'pause' if self.playing else 'play')
        for name, kind, ix in (('prev', 'prev', cx - gap), ('next', 'next', cx + gap)):
            hot = self._hover_hit == name
            rr = QRectF(ix - isz, ty - isz, isz * 2, isz * 2)
            if hot:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 40))
                p.drawEllipse(rr.center(), isz * 1.32, isz * 1.32)
            p.setPen(QPen(QColor(255, 255, 255, 70 if hot else 44), 1.0))
            p.setBrush(QColor(255, 255, 255, 12 if hot else 0))
            p.drawEllipse(rr)
            self._paint_icon(p, kind, rr, acc if hot else QColor(255, 255, 255, 236),
                             scale=0.72 * self._btn_scale[name].value)

        # utility dock: a floating glass capsule, drawn from the SAME rects the
        # press handler tests. Glyph and target are separate rects inside each slot
        # (the target is bigger than the glyph and tiles with its neighbours), so a
        # near-miss still lands on the icon the eye was aiming at.
        slots = getattr(self, '_util_slots', None)
        if not slots:
            self._compute_circle_layout()
            slots = getattr(self, '_util_slots', None) or []
        if slots:
            skd = self._skin()
            us = float(getattr(self, '_util_us', max(5.5, R * 0.038)))
            dock = QRectF(getattr(self, '_util_dock',
                                  QRectF(cx - R * 0.28, cy + R * 0.14, R * 0.56, R * 0.16)))
            hot_any = any(self._hover_hit == nm for nm, _k, _h, _g in slots)
            if skd.get('plate', 'glass') == 'none':
                # vinyl/ember: no plate, just a hairline rule under the cluster
                p.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
                p.drawLine(QPointF(dock.left() + 5.0, dock.bottom() - 1.0),
                           QPointF(dock.right() - 5.0, dock.bottom() - 1.0))
            else:
                p.setPen(QPen(QColor(255, 255, 255, 40 if hot_any else 26), 1.0))
                p.setBrush(QColor(6, 10, 16, 104 if hot_any else 78))
                rad = dock.height() / 2.0
                p.drawRoundedRect(dock, rad, rad)
                p.setPen(QPen(QColor(255, 255, 255, 22 if hot_any else 14), 1.0))
                p.drawLine(QPointF(dock.left() + rad, dock.top() + 1.2),
                           QPointF(dock.right() - rad, dock.top() + 1.2))

            cap = None
            for nm, kind, hir, gr in slots:
                hot = self._hover_hit == nm
                act = (nm == 'pin' and self.pinned) or (nm == 'pane' and self._pane_is_vis())
                sp = self._btn_scale[nm].value if nm in self._btn_scale else 1.0
                if hot or act:
                    wash = QColor(acc)
                    wash.setAlphaF(0.22 if act else 0.15)
                    p.setPen(QPen(QColor(255, 255, 255, 62 if act else 44), 1.0))
                    p.setBrush(wash)
                    p.drawRoundedRect(gr.adjusted(-2.0, -2.0, 2.0, 2.0), 6.0, 6.0)
                if hot:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 34))
                    p.drawEllipse(gr.center(), us * 1.5, us * 1.5)
                    cap = nm
                gg = QRectF(gr.translated(0.0, -0.8 if hot else 0.0))
                if hot or act:
                    col = QColor(min(255, acc.red() + 30), min(255, acc.green() + 30),
                                 min(255, acc.blue() + 30))
                else:
                    col = QColor(255, 255, 255, 175)
                # a soft contact shadow keeps the glyph legible over any wallpaper
                self._paint_icon(p, kind, gg.translated(0.0, 1.0), QColor(0, 0, 0, 130),
                                 scale=1.0 * sp)
                self._paint_icon(p, kind, gg, col, scale=1.0 * sp, filled=act)
                if act:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(col))
                    p.drawEllipse(QPointF(gg.center().x(), gg.bottom() + us * 0.42),
                                  max(1.0, us * 0.14), max(1.0, us * 0.14))

            if cap:
                label = {'pin': 'PIN', 'pane': 'PANE', 'gear': 'SETTINGS',
                         'size': 'SIZE', 'restore': 'CLOSE'}.get(cap, '')
                p.save()
                f = QFont(self.font())
                f.setPixelSize(max(8, int(R * 0.052)))
                f.setBold(True)
                f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
                p.setFont(f)
                fm_ = p.fontMetrics()
                tw = fm_.horizontalAdvance(label) + 12.0
                th = fm_.height() + 3.0
                pill = QRectF(cx - tw / 2.0, dock.bottom() + 3.0, tw, th)
                # the label sits over spokes and wallpaper, so it gets its own plate
                p.setPen(QPen(QColor(255, 255, 255, 38), 1.0))
                p.setBrush(QColor(6, 10, 16, 196))
                p.drawRoundedRect(pill, th / 2.0, th / 2.0)
                p.setPen(QColor(255, 255, 255, 216))
                p.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)
                p.restore()

        # no elapsed readout on the dial: the progress arc + dot carry the position

        # orbiting motes
        groups = {}
        for k in range(44 if R > 150 else 32):
            th_a = math.radians((k * 137.508 + self._anim_t * 22.0) % 360.0)
            rr_ = R * (0.755 + 0.05 * math.sin(k * 1.7 + self._anim_t * 1.7))
            a = 0.12 + 0.18 * (0.5 + 0.5 * math.sin(k * 2.3 - self._anim_t * 2.4))
            groups.setdefault(int(a / 0.12), []).append(
                QPointF(cx + math.cos(th_a) * rr_, cy + math.sin(th_a) * rr_))
        for gi, pts in groups.items():
            p.setPen(QPen(QColor(255, 255, 255, 40 + gi * 30), max(0.7, R * 0.004),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPoints(QPolygonF(pts))

    # ── lifecycle ────────────────────────────────────────────────────────────
    def _fade_in(self):
        try:
            if self._fade is not None:
                self._fade.stop()
            self.setWindowOpacity(0.0)
            self._fade = QVariantAnimation(self)
            self._fade.setDuration(170)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(float(self.opacity_val))
            self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._fade.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))
            self._fade.start()
        except Exception:
            self.setWindowOpacity(self.opacity_val)

    def showEvent(self, event):
        super().showEvent(event)
        self._place()
        self._last_tick = time.perf_counter()
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        self.refresh_track(force=True)
        self._fade_in()
        self.raise_()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._tick_timer.stop()

    def closeEvent(self, event):
        self._tick_timer.stop()
        if not self.suppress_restore:
            self.main._exit_gadget_mode()
        super().closeEvent(event)


class SettingsWindow(QWidget):
    """
    Standalone settings window.

    Everything that used to be crammed into the header / workspace lives here:
    the full theme gallery (every dark variant as a live colour swatch), the
    visualizer mode, the volume-battery animation style, and the view toggles.
    It restyles itself with the parent's theme, so it never looks foreign.
    """

    def __init__(self, main):
        super().__init__(None, Qt.WindowType.Window)
        self.main = main
        self.swatches = {}
        self.setWindowTitle('⚙ Settings — Audio Player Pro')
        self.setMinimumSize(600, 640)
        self.resize(640, 720)
        self._build()

    # ── construction ──
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel('⚙  SETTINGS')
        title.setObjectName('settingsTitle')
        head.addWidget(title)
        head.addStretch(1)
        close_btn = QPushButton('✕')
        close_btn.setObjectName('toolBtn')
        close_btn.setFixedSize(26, 24)
        close_btn.setToolTip('Close settings')
        close_btn.clicked.connect(self.hide)
        head.addWidget(close_btn)
        root.addLayout(head)

        sub = QLabel('Appearance, visualizer and playback behaviour')
        sub.setObjectName('settingsSub')
        root.addWidget(sub)

        # ── themes ──
        root.addWidget(self._section('APPEARANCE  ·  THEME'))
        self.theme_host = QWidget()
        self.theme_grid = QGridLayout(self.theme_host)
        self.theme_grid.setContentsMargins(2, 2, 2, 2)
        self.theme_grid.setSpacing(6)
        scroll = QScrollArea()
        scroll.setObjectName('settingsScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.theme_host)
        scroll.setMinimumHeight(220)
        root.addWidget(scroll, stretch=1)
        self._build_swatches()

        # ── visualizer ──
        root.addWidget(self._section('VISUALIZER'))
        vis_row = QHBoxLayout()
        vis_row.setSpacing(8)
        vis_lbl = QLabel('MODE')
        vis_lbl.setObjectName('settingsKey')
        vis_row.addWidget(vis_lbl)
        self.vis_combo = StickyComboBox()
        self.vis_combo.setObjectName('hudCombo')
        self.vis_combo.setFixedHeight(24)
        for mode_key in ModernVisualizer.MODES:
            self.vis_combo.addItem(ModernVisualizer.MODE_LABELS[mode_key], mode_key)
        try:
            self.vis_combo.setCurrentIndex(
                ModernVisualizer.MODES.index(self.main.vis_mode_combo.currentData()))
        except Exception:
            pass
        self.vis_combo.currentIndexChanged.connect(self.main._on_vis_combo_changed)
        self.main.vis_mode_combo = self.vis_combo      # keep the old handle alive
        vis_row.addWidget(self.vis_combo, stretch=1)
        root.addLayout(vis_row)

        anim_row = QHBoxLayout()
        anim_row.setSpacing(8)
        anim_lbl = QLabel('VOLUME FX')
        anim_lbl.setObjectName('settingsKey')
        anim_row.addWidget(anim_lbl)
        self.anim_combo = StickyComboBox()
        self.anim_combo.setObjectName('hudCombo')
        self.anim_combo.setFixedHeight(24)
        try:
            for entry in self.main.battery_volume.ANIM_STYLES:
                key, label = (entry[0], entry[1]) if len(entry) > 1 else (entry[0], entry[0])
                self.anim_combo.addItem(label, key)
            current = self.main.battery_volume.anim_style
            idx = self.anim_combo.findData(current)
            if idx >= 0:
                self.anim_combo.setCurrentIndex(idx)
        except Exception:
            pass
        self.anim_combo.currentIndexChanged.connect(self._on_anim_style_changed)
        anim_row.addWidget(self.anim_combo, stretch=1)
        root.addLayout(anim_row)

        # ── mini gadget ──
        root.addWidget(self._section('MINI GADGET  ·  MINIMISE-TO-GADGET'))
        self.gadget_check = QCheckBox('Show the floating gadget when minimised')
        self.gadget_check.setObjectName('settingsCheck')
        try:
            self.gadget_check.setChecked(bool(getattr(self.main, 'gadget_enabled', True)))
        except Exception:
            pass
        self.gadget_check.toggled.connect(
            lambda v: self.main.set_gadget_option('enabled', bool(v)))
        root.addWidget(self.gadget_check)

        self.gadget_taskbar_check = QCheckBox('Hide the main window from the taskbar while the gadget is up')
        self.gadget_taskbar_check.setObjectName('settingsCheck')
        try:
            self.gadget_taskbar_check.setChecked(bool(getattr(self.main, 'gadget_hide_taskbar', False)))
        except Exception:
            pass
        self.gadget_taskbar_check.toggled.connect(
            lambda v: self.main.set_gadget_option('hide_taskbar', bool(v)))
        root.addWidget(self.gadget_taskbar_check)

        g_row = QHBoxLayout()
        g_row.setSpacing(8)
        g_lbl = QLabel('GADGET')
        g_lbl.setObjectName('settingsKey')
        g_row.addWidget(g_lbl)

        self.gadget_size_combo = StickyComboBox()
        self.gadget_size_combo.setObjectName('hudCombo')
        self.gadget_size_combo.setFixedHeight(24)
        for _k, _label in (('s', 'SMALL'), ('m', 'MEDIUM'), ('l', 'LARGE')):
            self.gadget_size_combo.addItem(_label, _k)
        try:
            _idx = self.gadget_size_combo.findData(self.main._gadget_state().get('size', 'm'))
            if _idx >= 0:
                self.gadget_size_combo.setCurrentIndex(_idx)
        except Exception:
            pass
        self.gadget_size_combo.currentIndexChanged.connect(
            lambda _i: self.main.set_gadget_option('size', self.gadget_size_combo.currentData()))
        g_row.addWidget(self.gadget_size_combo, stretch=1)

        self.gadget_pane_combo = StickyComboBox()
        self.gadget_pane_combo.setObjectName('hudCombo')
        self.gadget_pane_combo.setFixedHeight(24)
        for _k, _label in (('auto', 'AUTO PANE'), ('vis', 'VISUALIZER'), ('art', 'ALBUM ART')):
            self.gadget_pane_combo.addItem(_label, _k)
        try:
            _idx = self.gadget_pane_combo.findData(self.main._gadget_state().get('pane', 'auto'))
            if _idx >= 0:
                self.gadget_pane_combo.setCurrentIndex(_idx)
        except Exception:
            pass
        self.gadget_pane_combo.currentIndexChanged.connect(
            lambda _i: self.main.set_gadget_option('pane', self.gadget_pane_combo.currentData()))
        g_row.addWidget(self.gadget_pane_combo, stretch=1)
        root.addLayout(g_row)

        # the gadget's visualizer keeps its own colour + ring motion settings,
        # separate from the app's VISUALIZER section above
        g_row2 = QHBoxLayout()
        g_row2.setSpacing(8)
        col_lbl = QLabel('COLOUR')
        col_lbl.setObjectName('settingsKey')
        g_row2.addWidget(col_lbl)

        self.gadget_color_combo = StickyComboBox()
        self.gadget_color_combo.setObjectName('hudCombo')
        self.gadget_color_combo.setFixedHeight(24)
        for _k, _label, *_rest in GADGET_PALETTES:
            self.gadget_color_combo.addItem(_label, _k)
        try:
            _idx = self.gadget_color_combo.findData(
                self.main._gadget_state().get('vis_palette', 'theme'))
            if _idx >= 0:
                self.gadget_color_combo.setCurrentIndex(_idx)
        except Exception:
            pass
        self.gadget_color_combo.currentIndexChanged.connect(
            lambda _i: self.main.set_gadget_option(
                'vis_palette', self.gadget_color_combo.currentData()))
        g_row2.addWidget(self.gadget_color_combo, stretch=1)

        _ring_choices = (('FIXED (STILL)', (False, 0.0)),
                         ('ROTATING · SLOW', (True, 6.0)),
                         ('ROTATING · MEDIUM', (True, 14.0)),
                         ('ROTATING · FAST', (True, 28.0)),
                         ('ROTATING · VERY FAST', (True, 50.0)))
        self.gadget_ring_combo = StickyComboBox()
        self.gadget_ring_combo.setObjectName('hudCombo')
        self.gadget_ring_combo.setFixedHeight(24)
        for _label, _data in _ring_choices:
            self.gadget_ring_combo.addItem(_label, _data)
        try:
            _st = self.main._gadget_state()
            if not bool(_st.get('rotate', True)):
                self.gadget_ring_combo.setCurrentIndex(0)
            else:
                _spd = float(_st.get('rot_speed', 14.0))
                _best, _bestd = 2, 1e9
                for _i, (_lab, (_rot, _s)) in enumerate(_ring_choices):
                    if not _rot:
                        continue
                    _d = abs(_s - _spd)
                    if _d < _bestd:
                        _best, _bestd = _i, _d
                self.gadget_ring_combo.setCurrentIndex(_best)
        except Exception:
            pass
        self.gadget_ring_combo.currentIndexChanged.connect(self._on_gadget_ring_changed)
        g_row2.addWidget(self.gadget_ring_combo, stretch=1)
        root.addLayout(g_row2)

        # star + control treatment: one combo, five complete looks
        g_row3 = QHBoxLayout()
        self.gadget_skin_combo = StickyComboBox()
        self.gadget_skin_combo.setObjectName('hudCombo')
        self.gadget_skin_combo.setFixedHeight(24)
        for _k in GADGET_SKIN_KEYS:
            self.gadget_skin_combo.addItem(GADGET_SKIN_LABELS[_k].upper(), _k)
        try:
            _idx = self.gadget_skin_combo.findData(
                self.main._gadget_state().get('skin', 'nightshift'))
            if _idx >= 0:
                self.gadget_skin_combo.setCurrentIndex(_idx)
        except Exception:
            pass
        self.gadget_skin_combo.currentIndexChanged.connect(
            lambda _i: self.main.set_gadget_option(
                'skin', self.gadget_skin_combo.currentData()))
        g_row3.addWidget(self.gadget_skin_combo, stretch=1)
        root.addLayout(g_row3)

        # ── view ──
        root.addWidget(self._section('VIEW'))
        self.video_check = QCheckBox('Video view instead of the visualizer')
        self.video_check.setObjectName('settingsCheck')
        try:
            self.video_check.setChecked(bool(self.main.video_toggle_btn.isChecked()))
        except Exception:
            pass
        self.video_check.toggled.connect(self._on_video_toggled)
        root.addWidget(self.video_check)

        # ── footer ──
        foot = QHBoxLayout()
        foot.addStretch(1)
        done = QPushButton('Done')
        done.setFixedHeight(26)
        done.setMinimumWidth(96)
        done.clicked.connect(self.hide)
        foot.addWidget(done)
        root.addLayout(foot)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName('settingsSection')
        return lbl

    def _build_swatches(self):
        for btn in self.swatches.values():
            btn.setParent(None)
        self.swatches.clear()
        cols = 3
        for i, (key, theme) in enumerate(THEMES.items()):
            btn = QPushButton(theme.get('name', key))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.setToolTip('%s — click to apply' % theme.get('name', key))
            btn.setStyleSheet(self._swatch_qss(theme))
            btn.clicked.connect(lambda _=False, k=key: self.main._set_theme_key(k))
            self.theme_grid.addWidget(btn, i // cols, i % cols)
            self.swatches[key] = btn
        self.theme_grid.setRowStretch(len(self.swatches) // cols + 1, 1)
        self._sync_checked()

    @staticmethod
    def _swatch_qss(theme):
        return (
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            "      stop:0 %s, stop:0.45 %s, stop:1 %s);"
            "  color: %s;"
            "  border: 1px solid rgba(255,255,255,0.16);"
            "  border-radius: 9px;"
            "  font-size: 10px; font-weight: 800; letter-spacing: 0.4px;"
            "  text-align: left; padding-left: 10px;"
            "}"
            "QPushButton:hover { border: 1px solid %s; }"
            "QPushButton:checked { border: 2px solid #ffffff; }"
            % (theme.get('bg', '#000'), theme.get('accent', '#00f0ff'),
               theme.get('bg_card', '#111'), theme.get('text', '#fff'),
               theme.get('accent', '#00f0ff'))
        )

    # ── behaviour ──
    def _sync_checked(self):
        current = getattr(self.main, 'theme_key', None)
        for key, btn in self.swatches.items():
            btn.blockSignals(True)
            btn.setChecked(key == current)
            btn.blockSignals(False)

    def _on_anim_style_changed(self, _idx):
        key = self.anim_combo.currentData()
        try:
            self.main.battery_volume.set_anim_style(key)
            self.main._save_persisted_settings()
        except Exception:
            pass

    def _on_gadget_ring_changed(self, _idx):
        """Rotating vs. fixed ring: persist both the flag and the speed."""
        data = self.gadget_ring_combo.currentData()
        if not data:
            return
        rotate, speed = data
        try:
            self.main.set_gadget_option('rotate', bool(rotate))
            self.main.set_gadget_option('rot_speed', float(speed))
        except Exception:
            pass

    def _on_video_toggled(self, on):
        try:
            if self.main.video_toggle_btn.isChecked() != bool(on):
                self.main.video_toggle_btn.setChecked(bool(on))
                self.main._toggle_video_view()
        except Exception:
            pass

    # ── theming ──
    def restyle(self, t):
        self.setStyleSheet("""
            QWidget {{
                background: {bg};
                color: {text};
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }}
            QLabel#settingsTitle {{
                color: {text};
                font-size: 17px;
                font-weight: 800;
                letter-spacing: 2px;
            }}
            QLabel#settingsSub {{
                color: {dim};
                font-size: 10.5px;
                margin-bottom: 2px;
            }}
            QLabel#settingsSection {{
                color: {accent};
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1.4px;
                border-top: 1px solid {border_dim};
                padding-top: 5px;
            }}
            QLabel#settingsKey {{
                color: {dim};
                font-size: 9.5px;
                font-weight: 800;
                letter-spacing: 0.8px;
                min-width: 78px;
            }}
            QCheckBox#settingsCheck {{
                color: {text};
                font-size: 11px;
                padding: 3px 0;
            }}
            QCheckBox#settingsCheck::indicator {{
                width: 15px; height: 15px;
                border-radius: 4px;
                border: 1px solid {border};
                background: rgba(255,255,255,0.05);
            }}
            QCheckBox#settingsCheck::indicator:checked {{
                background: {accent};
                border: 1px solid {accent};
            }}
            QScrollArea#settingsScroll {{ background: transparent; border: none; }}
            QPushButton {{
                background: {btn};
                color: {text};
                border: 1px solid {border_dim};
                border-radius: 8px;
                padding: 3px 12px;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {btn_hover}; border: 1px solid {border}; }}
            QComboBox#hudCombo {{
                background: {btn};
                color: {text};
                border: 1px solid {border_dim};
                border-radius: 7px;
                padding: 2px 8px;
                font-size: 11px;
            }}
        """.format(bg=t.get('bg', '#0a0a0a'), text=t.get('text', '#fff'),
                   dim=t.get('text_dim', '#94a3b8'), accent=t.get('accent', '#00f0ff'),
                   btn=t.get('btn', '#1a1a1a'), btn_hover=t.get('btn_hover', '#252525'),
                   border=t.get('border', 'rgba(255,255,255,0.2)'),
                   border_dim=t.get('border_dim', 'rgba(255,255,255,0.08)')))
        self._sync_checked()

    def showEvent(self, event):
        self.restyle(getattr(self.main, 't', THEMES['midnight']))
        super().showEvent(event)

class ViewModeSwitch(QWidget):
    """Segmented appearance switch: Full window ↔ Card HUD ↔ Dial HUD.

    Three ways to change how the app looks used to live in three unrelated
    places — minimise for the gadget, double-click to flip its shape, Escape to
    come back. This one pill owns the whole axis: it animates, it stays legible
    on every theme (dark text on a bright accent pill), and the segment it is
    showing is exactly what the app restores on the next launch.
    """
    modeChanged = pyqtSignal(str)
    MODES = (('full', '▣', 'Full'), ('card', '▬', 'Card'), ('dial', '◉', 'Dial'))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('viewModeSwitch')
        self.setFixedHeight(26)
        self.setMinimumWidth(204)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip('Appearance mode — Ctrl+1 Full window · Ctrl+2 Card HUD · '
                        'Ctrl+3 Dial HUD')
        self._mode = 'full'
        self._hover = -1
        self._pos = 0.0                      # animated pill slot, in segments
        self._accent = QColor('#22d3ee')
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    # ── state ────────────────────────────────────────────────────────────────
    @staticmethod
    def keys():
        return [k for k, _g, _l in ViewModeSwitch.MODES]

    def mode(self):
        return self._mode

    def set_accent(self, colour):
        try:
            self._accent = QColor(colour)
        except Exception:
            self._accent = QColor('#22d3ee')
        self.update()

    def set_mode(self, mode, animate=True):
        """Move the pill. Never emits — callers that own the state stay in charge."""
        if mode not in self.keys():
            return False
        changed = mode != self._mode
        self._mode = mode
        idx = self.keys().index(mode)
        if animate and self.isVisible() and changed:
            self._anim.stop()
            self._anim.setStartValue(float(self._pos))
            self._anim.setEndValue(float(idx))
            self._anim.start()
        else:
            self._pos = float(idx)
            self.update()
        return changed

    def _on_anim(self, value):
        self._pos = float(value)
        self.update()

    # ── geometry ─────────────────────────────────────────────────────────────
    def _pad(self):
        return 3.0

    def _seg_w(self):
        return (self.width() - self._pad() * 2.0) / float(len(self.MODES))

    def _seg_rect(self, i):
        pad = self._pad()
        return QRectF(pad + i * self._seg_w(), pad,
                      self._seg_w(), self.height() - pad * 2.0)

    def _index_at(self, pos):
        pad = self._pad()
        span = self.width() - pad * 2.0
        x = pos.x() - pad
        if x < 0 or x > span or pos.y() < 0 or pos.y() > self.height():
            return -1
        return max(0, min(len(self.MODES) - 1, int(x / self._seg_w())))

    # ── painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2.0

        # trough: dark glass, hairline edge, faint top sheen
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 126))
        p.drawRoundedRect(r, rad, rad)
        p.setBrush(QColor(255, 255, 255, 11))
        p.drawRoundedRect(QRectF(r.left(), r.top(), r.width(), r.height() * 0.5),
                          rad, rad)
        p.setPen(QPen(QColor(255, 255, 255, 32), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, rad, rad)

        # sliding pill + accent bloom
        seg = self._seg_rect(0)
        pill = QRectF(self._pad() + self._pos * self._seg_w(), seg.top(),
                      seg.width(), seg.height())
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(6, 0, -1):
            a = int(30 * (k / 6.0) ** 2)
            p.setBrush(QColor(self._accent.red(), self._accent.green(),
                              self._accent.blue(), a))
            p.drawRoundedRect(pill.adjusted(-k, -k * 0.75, k, k * 0.75),
                              pill.height() / 2.0 + k, pill.height() / 2.0 + k)
        grad = QLinearGradient(pill.topLeft(), pill.bottomLeft())
        grad.setColorAt(0.0, self._accent.lighter(124))
        grad.setColorAt(1.0, self._accent.darker(116))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 160), 1.0))
        p.drawRoundedRect(pill, pill.height() / 2.0, pill.height() / 2.0)

        # labels
        f = QFont('Segoe UI', 8)
        f.setWeight(QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        p.setFont(f)
        for i, (_key, glyph, label) in enumerate(self.MODES):
            active = abs(self._pos - i) < 0.5
            if active:
                col = QColor(9, 16, 24, 242)
            elif i == self._hover:
                col = QColor(255, 255, 255, 245)
            else:
                col = QColor(255, 255, 255, 148)
            p.setPen(col)
            p.drawText(self._seg_rect(i), int(Qt.AlignmentFlag.AlignCenter),
                       '%s  %s' % (glyph, label))

    # ── input ────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        i = self._index_at(event.position())
        if i >= 0:
            key = self.MODES[i][0]
            if key != self._mode:
                self.set_mode(key)
                self.modeChanged.emit(key)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        i = self._index_at(event.position())
        if i != self._hover:
            self._hover = i
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)


class AudioPlayerPro(QMainWindow):
    """Studio-Grade Desktop Audio Workstation with granular controls and full persistence."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('🎵 Audio Player Pro — Studio Workstation')
        self.resize(1380, 920)
        self.setMinimumSize(980, 680)

        # Core State
        self.theme_key = 'midnight'
        self.t = THEMES[self.theme_key]
        self.playlist = []
        self.current_index = -1
        self.current_playing_track = None  # Exact filepath of the song currently active
        self.is_video_mode = False

        # Mini gadget (minimise-to-gadget): created lazily on the first minimise
        self.gadget_enabled = True
        self.gadget_hide_taskbar = False
        self._gadget = None
        self._gadget_active = False
        self._gadget_state_cache = {}
        self._settings_was_open = False
        self._start_in_gadget = False

        # Appearance mode: 'full' (main window), 'card' or 'dial' (gadget HUD)
        self._view_mode = 'full'

        # Library Folders (Multiple directories)
        self.library_folders = [
            str(Path.home() / 'Music'),
            str(Path.home() / 'Music' / 'AudioPlayerDownloads')
        ]

        # Metadata Cache
        self.metadata_cache = {}
        self._meta_cache_file = DATA_DIR / 'metadata_cache.json'
        self._load_meta_cache()

        # Per-Song Profiles (Persistent settings for each song)
        self.song_profiles = {}
        self._profiles_file = DATA_DIR / 'song_profiles.json'
        self._load_song_profiles()
        self._is_applying_profile = False

        # Playback Modes
        self.shuffle_enabled = False
        self.repeat_mode = 'off'

        # A/B Loop State (Clean per song)
        self.loop_a = None  # ms
        self.loop_b = None  # ms
        self.loop_active = False
        self.pending_seek_ms = None
        self.saw_loading = False

        # ── Verified A:B resume seek ──
        # QtMultimedia drops setPosition() calls issued before the new source is
        # actually loaded, and a stale positionChanged() from the previous track
        # used to consume the request first, so the restored A:B loop never
        # started.  The pending seek is now only ever consumed by the guard
        # timer, and only after player.position() is verified to have landed.
        self._seek_attempts = 0
        self._seek_max_attempts = 75          # ~3.75 s of retries at 50 ms
        self._pending_loop = None             # (a_ms, b_ms, active) to re-assert on load
        self._seek_guard_timer = QTimer(self)
        self._seek_guard_timer.setInterval(50)
        self._seek_guard_timer.timeout.connect(self._apply_pending_seek_if_needed)

        # Granular Speed (0.25x to 2.50x in 0.01x steps)
        self.playback_speed = 1.0

        # Playlist visible columns configuration (11 total columns with Rating)
        self.visible_columns = {
            0: True,   # '#'
            1: True,   # '▶'
            2: True,   # 'Rating'
            3: True,   # 'Title'
            4: True,   # 'Artist'
            5: True,   # 'Duration'
            6: True,   # 'Format'
            7: True,   # 'Quality'
            8: True,   # 'Size'
            9: True,   # 'Folder Origin'
            10: True   # 'Saved Settings'
        }

        # Granular 7-Band EQ State (-15.0 to +15.0 dB)
        self.eq_values = {
            'eq_60': 0.0, 'eq_150': 0.0, 'eq_400': 0.0,
            'eq_1000': 0.0, 'eq_2500': 0.0, 'eq_6000': 0.0, 'eq_14000': 0.0
        }
        self.bass_boost = 0.0
        self.pitch_semitones = 0.0
        self.reverb = 0.0
        self.echo = 0.0
        self.eq_sliders = {}
        self.eq_labels = {}
        self.stereo_width = 100.0

        # Audio Output & Player
        self.player = QMediaPlayer(self)
        self._fx_boot()
        self.audio_out = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_out)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        self.settings = QSettings('AudioPlayerPro', 'AudioPlayerPro')
        self._app_settings_file = DATA_DIR / 'app_settings.json'
        self._tui_settings_file = DATA_DIR / 'tui_settings.json'
        self._cached_main_sizes = [232, 124, 400]
        self._cached_top_sizes = [1100, 240]
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save_persisted_settings)

        # Build Interface
        self._init_ui()
        self._bind_shortcuts()
        self._load_persisted_settings()

    # ─────────────────────────────────────────────────────────────────────────
    # UI CONSTRUCTION WITH RESIZABLE SPLITTERS
    # ─────────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        # 1. Top Header Bar
        header = self._create_header_bar()
        root_layout.addWidget(header)

        # 2. Main Vertical Splitter: makes every panel resizable
        self.main_splitter = SmoothSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setObjectName('mainSplitter')

        # Visualizer & Battery Volume Row (Horizontal Splitter: Resizable side-by-side)
        self.top_row_splitter = SmoothSplitter(Qt.Orientation.Horizontal)
        self.top_row_splitter.setObjectName('topRowSplitter')

        # Visualizer Frame
        self.vis_card = QFrame()
        self.vis_card.setObjectName('panoramicVisCard')
        vis_layout = QVBoxLayout(self.vis_card)
        vis_layout.setContentsMargins(0, 0, 0, 0)
        vis_layout.setSpacing(0)

        self.visualizer = ModernVisualizer(self.vis_card)
        self.visualizer.set_player(self.player)
        self.video_widget = QVideoWidget(self.vis_card)
        self.video_widget.setVisible(False)
        vis_layout.addWidget(self.visualizer)
        vis_layout.addWidget(self.video_widget)

        self.top_row_splitter.addWidget(self.vis_card)

        # Battery Volume Card (Allows smooth horizontal and vertical resizing)
        self.vol_card = QFrame()
        self.vol_card.setObjectName('volCard')
        vol_layout = QVBoxLayout(self.vol_card)
        vol_layout.setContentsMargins(4, 4, 4, 4)
        vol_layout.setSpacing(0)

        self.battery_volume = BatteryVolumeWidget(self.vol_card)
        self.battery_volume.volumeChanged.connect(self._on_battery_volume_changed)
        self.battery_volume.muteToggled.connect(self._toggle_mute)
        vol_layout.addWidget(self.battery_volume)

        self.top_row_splitter.addWidget(self.vol_card)

        self.top_row_splitter.setStretchFactor(0, 8)
        self.top_row_splitter.setStretchFactor(1, 1)
        self.main_splitter.addWidget(self.top_row_splitter)

        # Section B: Master Transport & Scrubbing Card (Contains Timeline & Waveform Overview Bar)
        transport_card = self._create_transport_card()
        self.main_splitter.addWidget(transport_card)

        # Section C: Unified Studio Workspace Panel (Songs + EQ/DSP + YouTube + Guide)
        self.tabs = self._create_workspace_panel()
        self.tabs.currentChanged.connect(lambda idx: self._schedule_save_settings())
        self.main_splitter.addWidget(self.tabs)

        self.main_splitter.setSizes([232, 124, 400])
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setStretchFactor(2, 6)

        self.main_splitter.splitterMoved.connect(lambda pos, idx: self._on_splitter_moved())
        self.top_row_splitter.splitterMoved.connect(lambda pos, idx: self._on_splitter_moved())
        self.playlist_table.horizontalHeader().sectionResized.connect(lambda idx, old, new: self._schedule_save_settings())

        root_layout.addWidget(self.main_splitter, stretch=1)
        self._apply_theme()
        self._install_view_shortcuts()

    def _create_header_bar(self):
        frame = QFrame()
        frame.setObjectName('headerBar')
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)

        # Brand Title
        brand = QLabel('🎵 AUDIO PLAYER PRO')
        brand.setObjectName('brandTitle')
        font = QFont('Segoe UI', 11)
        font.setBold(True)
        brand.setFont(font)
        layout.addWidget(brand)

        # Appearance mode switch: Full window / Card HUD / Dial HUD
        self.view_switch = ViewModeSwitch()
        self.view_switch.modeChanged.connect(self.set_view_mode)
        layout.addWidget(self.view_switch)

        # Status Pill
        self.status_pill = QLabel('● READY')
        self.status_pill.setObjectName('statusPill')
        self.status_pill.setFixedHeight(20)
        layout.addWidget(self.status_pill)

        # Now Playing Banner
        self.now_playing_label = QLabel('No media loaded')
        self.now_playing_label.setObjectName('nowPlayingBanner')
        self.now_playing_label.setFixedHeight(20)
        layout.addWidget(self.now_playing_label, stretch=1)

        # Video / Visualizer Toggle
        self.video_toggle_btn = QPushButton('🎬 VIDEO VIEW')
        self.video_toggle_btn.setObjectName('toggleBtn')
        self.video_toggle_btn.setCheckable(True)
        self.video_toggle_btn.setFixedHeight(24)
        self.video_toggle_btn.setToolTip('Toggle Video View / Visualizer View')
        self.video_toggle_btn.clicked.connect(self._toggle_video_view)
        layout.addWidget(self.video_toggle_btn)

        # Visualizer Mode Dropdown (8 Dynamic Modes)
        self.vis_mode_combo = StickyComboBox()
        self.vis_mode_combo.setObjectName('hudCombo')
        self.vis_mode_combo.setFixedHeight(24)
        self.vis_mode_combo.setMinimumWidth(140)
        for mode_key in ModernVisualizer.MODES:
            self.vis_mode_combo.addItem(ModernVisualizer.MODE_LABELS[mode_key], mode_key)
        self.vis_mode_combo.currentIndexChanged.connect(self._on_vis_combo_changed)
        self.vis_mode_combo.hide()      # lives in the settings window now

        # Theme Selector Dropdown
        self.theme_combo = StickyComboBox()
        self.theme_combo.setObjectName('hudCombo')
        self.theme_combo.setFixedHeight(24)
        self.theme_combo.setMinimumWidth(120)
        for k, v in THEMES.items():
            self.theme_combo.addItem(f"🎨 {v['name']}", k)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        # Restyling the window while the popup is up destroys it — that is what
        # made the dropdown slam shut. Apply the theme once the list is closed.
        self.theme_combo.popupClosed.connect(self._apply_pending_theme)
        self.theme_combo.hide()         # lives in the settings window now

        self.settings_btn = QPushButton('⚙')
        self.settings_btn.setObjectName('toolBtn')
        self.settings_btn.setFixedSize(28, 24)
        self.settings_btn.setToolTip('Settings — themes, visualizer, view')
        self.settings_btn.clicked.connect(self._open_settings_window)
        layout.addWidget(self.settings_btn)

        return frame

    def _glow(self, widget, color_hex, blur=18, alpha=170):
        """Attach a soft accent drop-shadow halo to a widget for a lit-from-within look."""
        try:
            fx = QGraphicsDropShadowEffect(widget)
            fx.setBlurRadius(blur)
            fx.setOffset(0, 1)
            col = QColor(color_hex)
            col.setAlpha(alpha)
            fx.setColor(col)
            widget.setGraphicsEffect(fx)
        except Exception:
            pass

    def _create_transport_card(self):
        card = QFrame()
        card.setObjectName('transportCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 5, 12, 6)
        layout.setSpacing(3)

        # ── Row 1: Interactive Song Slider with A/B Drag Pins & Fine Scrubbers ──
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(6)

        btn_nudge_back = QPushButton('⟨⟨')
        btn_nudge_back.setObjectName('transportBtn')
        btn_nudge_back.setFixedSize(34, 26)
        btn_nudge_back.setToolTip('Nudge backward 1 second')
        btn_nudge_back.clicked.connect(lambda: self._seek_relative(-1000))
        timeline_row.addWidget(btn_nudge_back)

        self.time_elapsed_lbl = QLabel('00:00.0')
        self.time_elapsed_lbl.setObjectName('timeLabel')
        self.time_elapsed_lbl.setFixedWidth(50)
        timeline_row.addWidget(self.time_elapsed_lbl)

        self.timeline = TimelineSlider(self)
        self.timeline.setRange(0, 1000)
        self.timeline.seekRequested.connect(self._on_seek_requested)
        self.timeline.loopChanged.connect(self._on_timeline_loop_changed)
        timeline_row.addWidget(self.timeline, stretch=1)

        self.time_total_lbl = QLabel('00:00.0')
        self.time_total_lbl.setObjectName('timeLabel')
        self.time_total_lbl.setFixedWidth(50)
        timeline_row.addWidget(self.time_total_lbl)

        btn_nudge_fwd = QPushButton('⟩⟩')
        btn_nudge_fwd.setObjectName('transportBtn')
        btn_nudge_fwd.setFixedSize(34, 26)
        btn_nudge_fwd.setToolTip('Nudge forward 1 second')
        btn_nudge_fwd.clicked.connect(lambda: self._seek_relative(1000))
        timeline_row.addWidget(btn_nudge_fwd)

        layout.addLayout(timeline_row)

        # ── Row 2: Audio Track Waveform Overview Bar (Directly below main slider) ──
        waveform_row = QHBoxLayout()
        waveform_row.setContentsMargins(50, 0, 50, 1)
        self.waveform_bar = AudioWaveformTrackBar(self)
        self.waveform_bar.seekRequested.connect(self._on_seek_requested)
        self.waveform_bar.audioBufferReady.connect(self._on_audio_buffer_ready)
        waveform_row.addWidget(self.waveform_bar)
        layout.addLayout(waveform_row)

        # ── Row 3: Transport & Granular Control Bar ──
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        # Shuffle & Repeat
        self.shuffle_btn = QPushButton('🔀')
        self.shuffle_btn.setObjectName('transportBtn')
        self.shuffle_btn.setFixedSize(30, 28)
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setToolTip('Toggle Shuffle')
        self.shuffle_btn.clicked.connect(self._toggle_shuffle)
        ctrl_row.addWidget(self.shuffle_btn)

        self.repeat_btn = QPushButton('🔁')
        self.repeat_btn.setObjectName('transportBtn')
        self.repeat_btn.setFixedSize(30, 28)
        self.repeat_btn.setToolTip('Cycle Repeat: Off / All / One')
        self.repeat_btn.clicked.connect(self._cycle_repeat)
        self._update_repeat_btn()
        ctrl_row.addWidget(self.repeat_btn)

        # Transport Navigation
        self.prev_btn = QPushButton('⏮')
        self.prev_btn.setObjectName('stepBtn')
        self.prev_btn.setFixedSize(34, 28)
        self.prev_btn.setToolTip('Previous Track')
        self.prev_btn.clicked.connect(self._prev_track)
        self._glow(self.prev_btn, self.t['accent'], 12, 120)
        ctrl_row.addWidget(self.prev_btn)

        # Main Play/Pause Button
        self.play_btn = QPushButton('▶  PLAY')
        self.play_btn.setObjectName('playBtn')
        self.play_btn.setFixedSize(126, 30)
        self.play_btn.setToolTip('Play / Pause')
        self.play_btn.clicked.connect(self._toggle_play)
        self._glow(self.play_btn, self.t['accent'], 22, 200)
        ctrl_row.addWidget(self.play_btn)

        self.next_btn = QPushButton('⏭')
        self.next_btn.setObjectName('stepBtn')
        self.next_btn.setFixedSize(34, 28)
        self.next_btn.setToolTip('Next Track')
        self.next_btn.clicked.connect(self._next_track)
        self._glow(self.next_btn, self.t['accent'], 12, 120)
        ctrl_row.addWidget(self.next_btn)

        self.stop_btn = QPushButton('⏹')
        self.stop_btn.setObjectName('transportBtn')
        self.stop_btn.setFixedSize(30, 28)
        self.stop_btn.setToolTip('Stop Playback')
        self.stop_btn.clicked.connect(self._stop_playback)
        ctrl_row.addWidget(self.stop_btn)

        # Separator Line
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet('color: rgba(255,255,255,0.15);')
        ctrl_row.addWidget(sep1)

        # A/B Loop Controls
        self.btn_loop_a = QPushButton('[ A ]')
        self.btn_loop_a.setObjectName('chipBtn')
        self.btn_loop_a.setFixedSize(40, 22)
        self.btn_loop_a.setToolTip('Mark Loop Start')
        self.btn_loop_a.clicked.connect(self._set_loop_a)
        ctrl_row.addWidget(self.btn_loop_a)

        self.btn_loop_b = QPushButton('[ B ]')
        self.btn_loop_b.setObjectName('chipBtn')
        self.btn_loop_b.setFixedSize(40, 22)
        self.btn_loop_b.setToolTip('Mark Loop End')
        self.btn_loop_b.clicked.connect(self._set_loop_b)
        ctrl_row.addWidget(self.btn_loop_b)

        self.btn_loop_clr = QPushButton('Clr')
        self.btn_loop_clr.setObjectName('chipBtn')
        self.btn_loop_clr.setFixedSize(32, 22)
        self.btn_loop_clr.setToolTip('Clear Loop')
        self.btn_loop_clr.clicked.connect(self._clear_loop)
        ctrl_row.addWidget(self.btn_loop_clr)

        self.loop_chip = QPushButton('Loop: Off')
        self.loop_chip.setObjectName('chipBtn')
        self.loop_chip.setMinimumWidth(72)
        self.loop_chip.setFixedHeight(22)
        self.loop_chip.setToolTip('Toggle A:B Loop On/Off')
        self.loop_chip.clicked.connect(self._toggle_loop_active)
        ctrl_row.addWidget(self.loop_chip)

        # Separator Line
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet('color: rgba(255,255,255,0.15);')
        ctrl_row.addWidget(sep2)

        # Granular Playback Speed Slider (0.25x - 2.50x in 0.01x steps)
        speed_lbl = QLabel('⚡ Speed:')
        speed_lbl.setStyleSheet('font-weight: 600; color: #94a3b8; font-size: 9.5px;')
        ctrl_row.addWidget(speed_lbl)

        btn_speed_dec = QPushButton('◀')
        btn_speed_dec.setObjectName('transportBtn')
        btn_speed_dec.setFixedSize(22, 22)
        btn_speed_dec.setToolTip('Decrease speed by 0.05x')
        btn_speed_dec.clicked.connect(lambda: self._nudge_speed(-0.05))
        ctrl_row.addWidget(btn_speed_dec)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(25, 250)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(78)
        self.speed_slider.valueChanged.connect(self._on_speed_slider_changed)
        ctrl_row.addWidget(self.speed_slider)

        btn_speed_inc = QPushButton('▶')
        btn_speed_inc.setObjectName('transportBtn')
        btn_speed_inc.setFixedSize(22, 22)
        btn_speed_inc.setToolTip('Increase speed by 0.05x')
        btn_speed_inc.clicked.connect(lambda: self._nudge_speed(0.05))
        ctrl_row.addWidget(btn_speed_inc)

        self.speed_val_lbl = QLabel('1.00x')
        self.speed_val_lbl.setObjectName('speedBadge')
        self.speed_val_lbl.setFixedWidth(42)
        ctrl_row.addWidget(self.speed_val_lbl)

        btn_speed_reset = QPushButton('1.0x')
        btn_speed_reset.setObjectName('chipBtn')
        btn_speed_reset.setFixedSize(40, 22)
        btn_speed_reset.setToolTip('Reset speed to 1.00x')
        btn_speed_reset.clicked.connect(lambda: self.speed_slider.setValue(100))
        ctrl_row.addWidget(btn_speed_reset)

        ctrl_row.addStretch(1)

        layout.addLayout(ctrl_row)
        return card

    def _section_card(self, title, icon_hex, widget):
        """Compact titled sub-section used inside the merged workspace panel."""
        frame = QFrame()
        frame.setObjectName('sectionCard')
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 4, 8, 6)
        lay.setSpacing(3)

        hdr = QLabel(title)
        hdr.setObjectName('sectionHeader')
        hdr.setStyleSheet(f'color: {icon_hex};')
        lay.addWidget(hdr)
        lay.addWidget(widget, stretch=1)
        return frame

    def _init_settings_window(self):
        try:
            self.settings_window = SettingsWindow(self)
        except Exception as exc:
            self.settings_window = None
            print('[settings] window failed to build:', exc)

    def _open_settings_window(self):
        if getattr(self, 'settings_window', None) is None:
            self._init_settings_window()
        sw = getattr(self, 'settings_window', None)
        if sw is None:
            return
        try:
            sw.restyle(self.t)
            sw.show()
            sw.raise_()
            sw.activateWindow()
        except Exception as exc:
            print('[settings] cannot show window:', exc)

    def _set_theme_key(self, key):
        """Apply a theme everywhere: painted widgets, QSS, settings window."""
        if key not in THEMES:
            return
        self.theme_key = key
        self.t = THEMES[key]
        try:
            self.timeline.set_theme_colors(self.t['track'], self.t['accent'], self.t['accent2'])
            self.waveform_bar.set_theme_colors(self.t['track'], self.t['accent'], self.t['accent2'])
            self.visualizer.set_theme(key)
            self.visualizer.update()
        except Exception:
            pass
        try:
            g = getattr(self, '_gadget', None)
            if g is not None:
                g.set_theme_key(key)
        except Exception:
            pass
        try:
            combo = getattr(self, 'theme_combo', None)
            if combo is not None:
                idx = combo.findData(key)
                if idx >= 0:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
        except Exception:
            pass
        try:
            self._apply_theme()
        except Exception as exc:
            print('[theme] apply failed:', exc)
        try:
            self._save_persisted_settings()
        except Exception:
            pass
        sw = getattr(self, 'settings_window', None)
        if sw is not None:
            try:
                sw.restyle(self.t)
            except Exception:
                pass

    def _create_workspace_panel(self):
            """
            ONE unified workspace panel — replaces the previous four-tab QTabWidget.
            Left column  : Songs & Library (folders + rich table + controls)
            Right column : 7-Band EQ & DSP / YouTube Downloader / Shortcuts stacked in
                           a single compact column, all visible at the same time.
            """
            panel = UnifiedWorkspacePanel(self)
            panel.setObjectName('workspacePanel')

            outer = QHBoxLayout(panel)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(4)

            self.workspace_splitter = SmoothSplitter(Qt.Orientation.Horizontal)
            self.workspace_splitter.setObjectName('workspaceSplitter')
            self.workspace_splitter.setChildrenCollapsible(False)

            # ── Column 1: Songs & Library ──
            songs_wrap = self._section_card('📑  SONGS & LIBRARY', '#00f0ff',
                                           self._create_playlist_tab())
            songs_wrap.setMinimumWidth(430)
            self.workspace_splitter.addWidget(songs_wrap)

            # ── Column 2: DSP / YouTube / Shortcuts in one compact stack ──
            side = QWidget()
            side.setObjectName('workspacePanel')
            side_lay = QVBoxLayout(side)
            side_lay.setContentsMargins(0, 0, 2, 0)
            side_lay.setSpacing(4)

            self.side_splitter = side_lay  # kept for compatibility with old references

            side_lay.addWidget(self._section_card('🎚️  REMIX RACK  ·  FX', '#00f0ff',
                                                  self._create_fx_tab()), stretch=0)
            side_lay.addWidget(self._section_card('🌐  YOUTUBE DOWNLOADER', '#ff007f',
                                                  self._create_youtube_tab()), stretch=1)

            side.setMinimumWidth(360)
            # Never clip the stack: scroll the column when the window is short.
            side_scroll = QScrollArea()
            side_scroll.setObjectName('sideScroll')
            side_scroll.setWidgetResizable(True)
            side_scroll.setFrameShape(QFrame.Shape.NoFrame)
            side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            side_scroll.setWidget(side)
            self.workspace_splitter.addWidget(side_scroll)
            self.workspace_splitter.setStretchFactor(0, 8)
            self.workspace_splitter.setStretchFactor(1, 5)
            self.workspace_splitter.setSizes([820, 470])
            self.workspace_splitter.splitterMoved.connect(lambda pos, idx: self._on_splitter_moved())

            outer.addWidget(self.workspace_splitter)
            return panel

    def _create_playlist_tab(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # ── Toolbar 1: Library Folders & File Management (compact icon+label) ──
        folders_bar = QHBoxLayout()
        folders_bar.setSpacing(4)

        self.folders_summary_lbl = QLabel(f"📁 {len(self.library_folders)} folders")
        self.folders_summary_lbl.setStyleSheet(
            'color: #94a3b8; font-size: 10px; font-weight: 600;')
        folders_bar.addWidget(self.folders_summary_lbl)

        add_folder_btn = QPushButton('＋ Folder')
        add_folder_btn.setObjectName('toolBtn')
        add_folder_btn.setFixedHeight(22)
        add_folder_btn.setToolTip('Add a library folder to monitor')
        add_folder_btn.clicked.connect(self._add_library_folder)
        folders_bar.addWidget(add_folder_btn)

        remove_folder_btn = QPushButton('－ Folder')
        remove_folder_btn.setObjectName('toolBtn')
        remove_folder_btn.setFixedHeight(22)
        remove_folder_btn.setToolTip('Stop monitoring a library folder')
        remove_folder_btn.clicked.connect(self._remove_library_folder)
        folders_bar.addWidget(remove_folder_btn)

        rescan_all_btn = QPushButton('🔄')
        rescan_all_btn.setObjectName('toolBtn')
        rescan_all_btn.setFixedSize(26, 22)
        rescan_all_btn.setToolTip('Rescan every library folder')
        rescan_all_btn.clicked.connect(self._scan_all_library_folders)
        folders_bar.addWidget(rescan_all_btn)

        folders_bar.addStretch()

        add_files_btn = QPushButton('＋ Files')
        add_files_btn.setObjectName('toolBtn')
        add_files_btn.setFixedHeight(22)
        add_files_btn.setToolTip('Add individual audio files')
        add_files_btn.clicked.connect(self._add_files)
        folders_bar.addWidget(add_files_btn)

        del_btn = QPushButton('🗑')
        del_btn.setObjectName('toolBtn')
        del_btn.setFixedSize(26, 22)
        del_btn.setToolTip('Remove selected track from playlist')
        del_btn.clicked.connect(self._remove_selected_track)
        folders_bar.addWidget(del_btn)

        clear_btn = QPushButton('✕')
        clear_btn.setObjectName('toolBtn')
        clear_btn.setFixedSize(26, 22)
        clear_btn.setToolTip('Clear the whole playlist')
        clear_btn.clicked.connect(self._clear_playlist)
        folders_bar.addWidget(clear_btn)

        layout.addLayout(folders_bar)

        # ── Toolbar 2: Track Reordering, Sorting, Columns & Filter ──
        controls_bar = QHBoxLayout()
        controls_bar.setSpacing(4)

        btn_top = QPushButton('⏫')
        btn_top.setObjectName('reorderBtn')
        btn_top.setFixedSize(24, 22)
        btn_top.setToolTip('Move selected song to TOP of playlist')
        btn_top.clicked.connect(self._move_selected_track_top)
        controls_bar.addWidget(btn_top)

        btn_up = QPushButton('▲')
        btn_up.setObjectName('reorderBtn')
        btn_up.setFixedSize(24, 22)
        btn_up.setToolTip('Move selected song UP in playlist')
        btn_up.clicked.connect(lambda: self._move_selected_track(-1))
        controls_bar.addWidget(btn_up)

        btn_down = QPushButton('▼')
        btn_down.setObjectName('reorderBtn')
        btn_down.setFixedSize(24, 22)
        btn_down.setToolTip('Move selected song DOWN in playlist')
        btn_down.clicked.connect(lambda: self._move_selected_track(1))
        controls_bar.addWidget(btn_down)

        btn_bottom = QPushButton('⏬')
        btn_bottom.setObjectName('reorderBtn')
        btn_bottom.setFixedSize(24, 22)
        btn_bottom.setToolTip('Move selected song to BOTTOM of playlist')
        btn_bottom.clicked.connect(self._move_selected_track_bottom)
        controls_bar.addWidget(btn_bottom)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color: rgba(255,255,255,0.15);')
        controls_bar.addWidget(sep)

        self.sort_combo = QComboBox()
        self.sort_combo.setFixedHeight(22)
        self.sort_combo.setMinimumWidth(150)
        self.sort_combo.addItems([
            'Custom / Manual (Drag & Drop)',
            '⭐ Rating: High → Low',
            '⭐ Rating: Low → High',
            '🔤 Title: A → Z',
            '🔤 Title: Z → A',
            '👤 Artist: A → Z',
            '👤 Artist: Z → A',
            '⏱️ Duration: Longest First',
            '⏱️ Duration: Shortest First',
            '💾 File Size: Largest First',
            '💾 File Size: Smallest First',
            '📅 Date Modified: Newest First'
        ])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        controls_bar.addWidget(self.sort_combo)

        self.col_btn = QPushButton('⚙')
        self.col_btn.setObjectName('toolBtn')
        self.col_btn.setFixedSize(26, 22)
        self.col_btn.setToolTip('Choose visible columns')
        self.col_btn.clicked.connect(self._show_column_picker_menu)
        controls_bar.addWidget(self.col_btn)

        controls_bar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 Filter title, artist, format...')
        self.search_input.setFixedWidth(190)
        self.search_input.setFixedHeight(22)
        self.search_input.textChanged.connect(self._filter_playlist_table)
        controls_bar.addWidget(self.search_input)

        layout.addLayout(controls_bar)

        # ── Compact Songs Table with Rich Metadata, Rating & Drag-Reorder ──
        self.playlist_table = ReorderablePlaylistTable(self)
        self.playlist_table.setObjectName('playlistTable')
        self.playlist_table.setColumnCount(11)
        self.playlist_table.setHorizontalHeaderLabels([
            '#', '▶', '⭐ Rating', 'Title', 'Artist / Uploader', 'Duration',
            'Format', 'Quality', 'Size', 'Folder Origin', 'Saved Settings'
        ])

        self.playlist_table.verticalHeader().setVisible(False)
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.playlist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.playlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.playlist_table.setShowGrid(False)
        self.playlist_table.setAlternatingRowColors(True)
        self.playlist_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_table.customContextMenuRequested.connect(self._show_track_context_menu)
        self.playlist_table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.playlist_table.rowReordered.connect(self._on_playlist_row_reordered)

        header = self.playlist_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_table_header_clicked)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Interactive)

        self.playlist_table.setColumnWidth(0, 28)
        self.playlist_table.setColumnWidth(1, 22)
        self.playlist_table.setColumnWidth(2, 76)
        self.playlist_table.setColumnWidth(4, 108)
        self.playlist_table.setColumnWidth(5, 52)
        self.playlist_table.setColumnWidth(6, 44)
        self.playlist_table.setColumnWidth(7, 86)
        self.playlist_table.setColumnWidth(8, 54)
        self.playlist_table.setColumnWidth(9, 80)
        self.playlist_table.setColumnWidth(10, 88)

        # Compact row metrics + ellipsis so long titles never blow the layout out
        self.playlist_table.setWordWrap(False)
        self.playlist_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.playlist_table.setIconSize(QSize(13, 13))
        self.playlist_table.verticalHeader().setDefaultSectionSize(17)
        self.playlist_table.verticalHeader().setMinimumSectionSize(14)
        self.playlist_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed)
        self.playlist_table.setHorizontalScrollMode(
            QTableWidget.ScrollMode.ScrollPerPixel)
        self.playlist_table.setVerticalScrollMode(
            QTableWidget.ScrollMode.ScrollPerPixel)
        self.playlist_table.setMinimumHeight(120)
        # Three metadata columns are off by default (still available from the
        # ⚙ column picker). With them shown the fixed widths exceeded the panel
        # width, which produced a horizontal scrollbar and overlapping cells.
        for _hidden_col in (6, 9, 10):
            self.playlist_table.setColumnHidden(_hidden_col, True)
        self.playlist_table.horizontalHeader().setMinimumSectionSize(18)

        layout.addWidget(self.playlist_table, stretch=1)

        self.playlist_stats_lbl = QLabel('0 tracks in library')
        self.playlist_stats_lbl.setStyleSheet('color: #64748b; font-size: 9.5px;')
        self.playlist_stats_lbl.setFixedHeight(14)
        layout.addWidget(self.playlist_stats_lbl)

        return panel

    def _create_fx_tab(self):
        """
        REMIX RACK — real, audible DSP.

        The rack is rendered by ffmpeg and played back through QMediaPlayer, so
        every knob here changes the sound for real (Qt exposes no insert-effect
        chain of its own). PITCH / TEMPO stay on QMediaPlayer.setPlaybackRate:
        they are instant, cost no render, and never alter the file length.
        """
        self.eq_sliders = {}
        self.eq_labels = {}
        self.fx_sliders = {}
        self.fx_labels = {}
        self.fx_reset_btns = {}
        self.fx_values = fx_defaults()

        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(3, 1, 3, 1)
        outer.setSpacing(1)

        # ── toolbar: presets + status ──
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.fx_preset_combo = QComboBox()
        self.fx_preset_combo.setObjectName('hudCombo')
        self.fx_preset_combo.setFixedHeight(20)
        self.fx_preset_combo.addItem('PRESETS ▾')
        for name in FX_PRESETS:
            self.fx_preset_combo.addItem(name)
        self.fx_preset_combo.activated.connect(self._on_fx_preset_picked)
        self.fx_preset_combo.setToolTip('One-click remix recipes')
        bar.addWidget(self.fx_preset_combo, stretch=2)

        self.fx_status_lbl = QLabel('FX: DRY')
        self.fx_status_lbl.setStyleSheet(
            'color: #64748b; font-size: 8.5px; font-weight: 800; letter-spacing: 0.4px;')
        self.fx_status_lbl.setToolTip(
            'DRY = rack untouched · RENDERING = building the remix · LIVE = remix playing')
        bar.addWidget(self.fx_status_lbl, stretch=1)
        outer.addLayout(bar)

        self.fx_warn_lbl = QLabel(
            '⚠ ffmpeg not found — install ffmpeg or put ffmpeg.exe on PATH to hear these FX')
        self.fx_warn_lbl.setStyleSheet('color: #f59e0b; font-size: 8px; font-weight: 700;')
        self.fx_warn_lbl.setWordWrap(True)
        self.fx_warn_lbl.setVisible(not bool(getattr(self, '_fx_ffmpeg', None)))
        outer.addWidget(self.fx_warn_lbl)

        def cell(caption, slider, val_label, reset_key=None):
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(2)
            cap = QLabel(caption)
            cap.setStyleSheet(
                'color: #94a3b8; font-size: 7.5px; font-weight: 800; letter-spacing: 0.4px;')
            head.addWidget(cap)
            head.addStretch()
            if reset_key:
                rst = QPushButton('↺')
                rst.setObjectName('cellReset')
                rst.setFixedSize(12, 12)
                rst.setCursor(Qt.CursorShape.PointingHandCursor)
                rst.setToolTip('Reset %s to its default' % caption.title())
                rst.clicked.connect(lambda _=False, k=reset_key: self._reset_one_fx(k))
                head.addWidget(rst)
                self.fx_reset_btns[reset_key] = rst
            val_label.setStyleSheet('color: #00f0ff; font-size: 7.5px; font-weight: 800;')
            head.addWidget(val_label)
            v.addLayout(head)
            v.addWidget(slider)
            return box

        def mk_slider(lo, hi, val):
            sl = NeonSlider(int(lo), int(hi), int(val),
                            self.t.get('accent', '#00f0ff'), self.t.get('accent2', '#ff007f'))
            sl.setFixedHeight(17)
            sl.setToolTip('Drag, click or use the mouse wheel')
            return sl

        # ── PITCH / TEMPO: instant, no render needed ──
        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        self.fx_pitch_slider = mk_slider(-12, 12, 0)
        self.fx_pitch_slider.setToolTip(
            'Transpose in semitones — pitch only, the song keeps its speed')
        self.fx_pitch_lbl = QLabel('0 st')
        self.fx_pitch_slider.valueChanged.connect(self._on_fx_pitch_changed)
        head_row.addWidget(cell('PITCH', self.fx_pitch_slider, self.fx_pitch_lbl, 'pitch'),
                           stretch=1)
        self.fx_tempo_slider = mk_slider(50, 150, 100)
        self.fx_tempo_lbl = QLabel('1.00x')
        self.fx_tempo_slider.valueChanged.connect(self._on_fx_tempo_changed)
        head_row.addWidget(cell('TEMPO', self.fx_tempo_slider, self.fx_tempo_lbl, 'tempo'),
                           stretch=1)
        outer.addLayout(head_row)

        # ── rack: every control below is rendered through ffmpeg ──
        for group_key, group_title in FX_RACK_GROUPS:
            head = QLabel(group_title)
            head.setStyleSheet(
                'color: %s; font-size: 7.5px; font-weight: 800; letter-spacing: 1px;'
                ' padding-top: 1px; border-top: 1px solid rgba(255,255,255,0.06);'
                % self.t.get('accent', '#00f0ff'))
            outer.addWidget(head)

            pending = None
            for key, caption, grp, lo, hi, dflt, scale in FX_RACK_SPEC:
                if grp != group_key:
                    continue
                slider = mk_slider(lo, hi, dflt)
                label = QLabel(fx_format(key, dflt))
                slider.valueChanged.connect(
                    lambda raw, _k=key: self._on_fx_rack_changed(_k, raw))
                self.fx_sliders[key] = slider
                self.fx_labels[key] = label
                self.fx_values[key] = float(dflt)
                if pending is None:
                    pending = (caption, slider, label, key)
                else:
                    row = QHBoxLayout()
                    row.setSpacing(4)
                    row.addWidget(cell(pending[0], pending[1], pending[2], pending[3]), stretch=1)
                    row.addWidget(cell(caption, slider, label, key), stretch=1)
                    outer.addLayout(row)
                    pending = None
            if pending is not None:
                row = QHBoxLayout()
                row.setSpacing(6)
                row.addWidget(cell(pending[0], pending[1], pending[2], pending[3]), stretch=1)
                row.addStretch(1)
                outer.addLayout(row)

        # ── footer ──
        foot = QHBoxLayout()
        foot.setSpacing(6)
        reset_fx_btn = QPushButton('↺ Reset')
        reset_fx_btn.setObjectName('toolBtn')
        reset_fx_btn.setFixedHeight(20)
        reset_fx_btn.setToolTip('Back to a dry, untouched mix')
        reset_fx_btn.clicked.connect(self._reset_fx)
        foot.addWidget(reset_fx_btn)

        self.fx_bypass_btn = QPushButton('⏻ Bypass')
        self.fx_bypass_btn.setObjectName('toolBtn')
        self.fx_bypass_btn.setFixedHeight(20)
        self.fx_bypass_btn.setCheckable(True)
        self.fx_bypass_btn.setToolTip('Play the original file, rack ignored')
        self.fx_bypass_btn.toggled.connect(self._on_fx_bypass_toggled)
        foot.addWidget(self.fx_bypass_btn)

        render_btn = QPushButton('⟳ Render')
        render_btn.setObjectName('toolBtn')
        render_btn.setFixedHeight(20)
        render_btn.setToolTip('Force a render now instead of waiting for the auto pass')
        render_btn.clicked.connect(lambda: self._start_fx_render())
        foot.addWidget(render_btn)

        foot.addStretch(1)
        outer.addLayout(foot)

        outer.addStretch()
        return panel

    def _reset_one_fx(self, key):
        """Reset a single rack control to its default, leaving the rest alone."""
        if key == 'pitch':
            self.fx_pitch_slider.setValue(0)
            return
        if key == 'tempo':
            self.fx_tempo_slider.setValue(100)
            return
        slider = (getattr(self, 'fx_sliders', None) or {}).get(key)
        if slider is None:
            return
        default = int(round(fx_defaults().get(key, 0.0)))
        if slider.value() != default:
            slider.setValue(default)

    def _sync_fx_reset_states(self):
        """Dim a reset button when its control is already at the default."""
        defaults = fx_defaults()
        for key, btn in (getattr(self, 'fx_reset_btns', None) or {}).items():
            try:
                if key == 'pitch':
                    changed = abs(getattr(self, 'pitch_semitones', 0.0)) > 0.01
                elif key == 'tempo':
                    changed = abs(float(getattr(self, 'playback_speed', 1.0)) - 1.0) > 0.001
                else:
                    slider = (getattr(self, 'fx_sliders', None) or {}).get(key)
                    changed = (slider is not None
                               and abs(slider.value() - int(round(defaults.get(key, 0.0)))) > 0)
                btn.setEnabled(changed)
            except Exception:
                pass

    # ── Remix rack handlers ──
    def _apply_playback_rate(self):
        """Tempo only. Pitch is rendered by the FX stage, so it cannot bend speed."""
        speed = getattr(self, 'playback_speed', 1.0) or 1.0
        rate = max(0.25, min(3.0, speed))
        try:
            if getattr(self, 'player', None) is not None:
                self.player.setPlaybackRate(rate)
        except Exception:
            pass
        return rate

    def _on_fx_pitch_changed(self, val):
        self.pitch_semitones = float(val)
        self.fx_pitch_lbl.setText('0 st' if val == 0 else f'{val:+d} st')
        # rendered, not varispeed: a transpose that keeps the song's speed
        self._sync_fx_reset_states()
        self._fx_status('FX: queued…', '#94a3b8')
        self._schedule_fx_render()

    def _on_fx_tempo_changed(self, val):
        self.playback_speed = val / 100.0
        self.fx_tempo_lbl.setText(f'{self.playback_speed:0.2f}x')
        self._sync_fx_reset_states()
        # keep the transport speed cluster in sync without re-entering this slot
        try:
            if hasattr(self, 'speed_lbl'):
                self.speed_lbl.setText(f'{self.playback_speed:0.2f}x')
            if hasattr(self, 'speed_slider') and self.speed_slider.value() != val:
                self.speed_slider.blockSignals(True)
                self.speed_slider.setValue(val)
                self.speed_slider.blockSignals(False)
        except Exception:
            pass
        self._apply_playback_rate()

    def _on_fx_rack_changed(self, key, raw):
        """A rack knob moved: relabel, remember, and queue a render pass."""
        value = float(raw)
        self.fx_values[key] = value
        lbl = self.fx_labels.get(key)
        if lbl is not None:
            lbl.setText(fx_format(key, value))
        if key == 'drive' or key == 'presence':
            # these sit inside the mastered signal path, so keep the spectrum
            # engine honest about the new dynamics while the render runs
            try:
                self.visualizer.engine.sensitivity = 1.0 + value / 100.0 * 0.12
            except Exception:
                pass
        # the preset name no longer describes the rack
        try:
            if self.fx_preset_combo.currentIndex() > 0:
                self.fx_preset_combo.blockSignals(True)
                self.fx_preset_combo.setCurrentIndex(0)
                self.fx_preset_combo.blockSignals(False)
        except Exception:
            pass
        self._sync_fx_reset_states()
        self._fx_status('FX: queued…', '#94a3b8')
        self._schedule_fx_render()

    def _on_fx_tone_changed(self, *_):
        """Legacy hook kept for compatibility — the rack owns these now."""
        self._schedule_fx_render()

    def _on_fx_preset_picked(self, idx):
        name = self.fx_preset_combo.itemText(idx)
        if idx <= 0 or name not in FX_PRESETS:
            return
        preset = FX_PRESETS[name]
        for key, slider in self.fx_sliders.items():
            wanted = int(round(float(preset.get(key, fx_defaults()[key]))))
            slider.blockSignals(True)
            slider.setValue(wanted)
            slider.blockSignals(False)
            self.fx_values[key] = float(wanted)
            lbl = self.fx_labels.get(key)
            if lbl is not None:
                lbl.setText(fx_format(key, float(wanted)))
        self._sync_fx_reset_states()
        self._fx_status('FX: preset %s' % name, '#a855f7')
        self._start_fx_render()

    def _on_fx_bypass_toggled(self, on):
        self.fx_bypass = bool(on)
        if on:
            self._fx_status('FX: BYPASSED', '#f59e0b')
        else:
            self._fx_status('FX: DRY')
        self._fx_refresh_source()
        if not on:
            self._schedule_fx_render(200)

    def _reset_fx(self):
        for key, slider in self.fx_sliders.items():
            dflt = int(round(fx_defaults()[key]))
            slider.blockSignals(True)
            slider.setValue(dflt)
            slider.blockSignals(False)
            self.fx_values[key] = float(dflt)
            lbl = self.fx_labels.get(key)
            if lbl is not None:
                lbl.setText(fx_format(key, float(dflt)))
        self.fx_pitch_slider.setValue(0)
        self.fx_tempo_slider.setValue(100)
        self.fx_bypass = False
        try:
            if self.fx_bypass_btn.isChecked():
                self.fx_bypass_btn.blockSignals(True)
                self.fx_bypass_btn.setChecked(False)
                self.fx_bypass_btn.blockSignals(False)
            self.fx_preset_combo.setCurrentIndex(0)
        except Exception:
            pass
        self._apply_playback_rate()
        self._sync_fx_reset_states()
        self._fx_status('FX: DRY')
        self._fx_refresh_source()

    # ══ FX render pipeline — debounce, render, swap in ══
    def _fx_values(self):
        vals = dict(getattr(self, 'fx_values', None) or fx_defaults())
        vals['pitch'] = float(getattr(self, 'pitch_semitones', 0.0) or 0.0)
        for key in fx_defaults():
            if key not in vals:
                vals[key] = fx_defaults()[key]
        return vals

    def _fx_status(self, text, colour='#64748b'):
        try:
            self.fx_status_lbl.setText(text)
            self.fx_status_lbl.setStyleSheet(
                'color: %s; font-size: 8.5px; font-weight: 800; letter-spacing: 0.4px;' % colour)
        except Exception:
            pass

    def _schedule_fx_render(self, delay_ms=350):
        try:
            self._fx_render_timer.start(int(delay_ms))
        except Exception:
            pass

    def _fx_current_source(self):
        if self.current_playing_track:
            return self.current_playing_track
        try:
            if 0 <= self.current_index < len(self.playlist):
                return self.playlist[self.current_index]
        except Exception:
            pass
        return None

    def _fx_cache_path(self, src, values):
        return FX_CACHE_DIR / ('%s.wav' % fx_signature(src, values))

    def _start_fx_render(self):
        """Render the current track through the rack, or fall back to the file."""
        src = self._fx_current_source()
        values = self._fx_values()

        if not src:
            return
        if self.fx_bypass:
            self._fx_status('FX: BYPASSED', '#f59e0b')
            self._fx_refresh_source()
            return
        if fx_rack_is_neutral(values):
            self._fx_status('FX: DRY')
            self._fx_refresh_source()
            return
        if not self._fx_ffmpeg:
            self._fx_status('FX off · ffmpeg missing', '#f59e0b')
            return

        try:
            FX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._fx_status('FX off · cache not writable', '#f59e0b')
            return

        out = self._fx_cache_path(src, values)
        part = str(out) + '.part'
        rate = fx_source_rate(src)
        self._fx_pending = (src, str(out), part)
        if out.exists() and out.stat().st_size > 4096:
            self._fx_status('FX: LIVE · cached', '#22c55e')
            self._fx_refresh_source()
            return

        graph = fx_filtergraph(values, rate)
        if not graph:
            self._fx_status('FX: DRY')
            self._fx_refresh_source()
            return
        args = fx_render_args(self._fx_ffmpeg, src, graph, part, rate)
        if self._fx_proc.state() != QProcess.ProcessState.NotRunning:
            self._fx_proc.kill()
            self._fx_proc.waitForFinished(400)
        FX_LAST_RENDER['graph'] = graph
        self._fx_started = time.time()
        self._fx_status('FX: RENDERING…', '#00f0ff')
        self._fx_proc.start(args[0], args[1:])

    def _on_fx_render_done(self, code, _status=None):
        pending = list(self._fx_pending or (None, None, None))
        while len(pending) < 3:
            pending.append(None)
        src, out, part = pending[0], pending[1], pending[2]
        elapsed = time.time() - getattr(self, '_fx_started', time.time())
        err = ''
        try:
            err = bytes(self._fx_proc.readAllStandardError()).decode('utf-8', 'replace').strip()
        except Exception:
            pass
        ok = bool(code == 0 and part and os.path.exists(part)
                  and os.path.getsize(part) > 4096)
        if ok and out:
            try:
                os.replace(part, out)      # publish atomically: no half files
            except OSError as exc:
                ok = False
                err = 'cannot publish render: %s' % exc
        if ok:
            fx_prune_cache()
            FX_LAST_RENDER['seconds'] = elapsed
            FX_LAST_RENDER['error'] = ''
            self._fx_status('FX: LIVE · %.1fs' % elapsed, '#22c55e')
            self._fx_refresh_source()
        else:
            self._fx_status('FX failed · dry', '#ef4444')
            fx_log_error('exit=%s \n%s' % (code, (err or 'unknown')[:600]))
            print('[remix rack] render failed (exit %s): %s' % (code, (err or '')[:400]))
            try:
                if part and os.path.exists(part):
                    os.remove(part)
            except OSError:
                pass
        self._fx_tip()

    def _fx_tip(self):
        """Status chip tooltip: which ffmpeg, how fast, and the last failure."""
        try:
            tip = 'ffmpeg: %s' % (self._fx_ffmpeg or 'NOT FOUND')
            if FX_LAST_RENDER.get('seconds'):
                tip += '\nlast render: %.1fs' % FX_LAST_RENDER['seconds']
            if FX_LAST_RENDER.get('error'):
                tip += '\nlast error: %s' % FX_LAST_RENDER['error'][:300]
            self.fx_status_lbl.setToolTip(tip)
        except Exception:
            pass

    def _fx_resolved_source(self, path):
        """The rendered remix when it exists, else the untouched original."""
        if not path:
            return path
        if getattr(self, 'fx_bypass', False):
            return path
        values = self._fx_values()
        if fx_rack_is_neutral(values):
            return path
        try:
            out = self._fx_cache_path(path, values)
            if out.exists() and out.stat().st_size > 4096:
                return str(out)
        except Exception:
            pass
        return path

    def _fx_refresh_source(self):
        """Swap the player onto (or off) the rendered copy without losing place."""
        path = self.current_playing_track
        if not path:
            return
        resolved = self._fx_resolved_source(path)
        if resolved == getattr(self, '_fx_applied_src', None):
            return
        try:
            was_playing = (self.player.playbackState()
                           == QMediaPlayer.PlaybackState.PlayingState)
            pos = self.player.position()
        except Exception:
            return
        self._fx_applied_src = resolved
        self.player.setSource(QUrl.fromLocalFile(resolved))
        if pos > 0:
            self._begin_pending_seek(pos)
        if was_playing:
            self.player.play()

    def _rack_set(self, key, value):
        """Write a value into a rack slider, clamped, ignoring a missing rack."""
        slider = (getattr(self, 'fx_sliders', None) or {}).get(key)
        if slider is None:
            return
        try:
            v = int(round(float(value)))
        except (TypeError, ValueError):
            return
        slider.setValue(max(slider.minimum(), min(slider.maximum(), v)))

    def _eq_set(self, key, value):
        """Legacy 7-band EQ setter — the panel is gone, so this is a no-op."""
        slider = (getattr(self, 'eq_sliders', None) or {}).get(key)
        if slider is not None:
            try:
                slider.setValue(int(value))
            except (TypeError, ValueError):
                pass

    def _apply_fx_values(self, values):
        """Push a saved dict into the rack without firing 15 renders."""
        if not isinstance(values, dict):
            return
        for key, slider in (getattr(self, 'fx_sliders', None) or {}).items():
            if key not in values:
                continue
            try:
                wanted = int(round(float(values[key])))
            except (TypeError, ValueError):
                continue
            wanted = max(slider.minimum(), min(slider.maximum(), wanted))
            slider.blockSignals(True)
            slider.setValue(wanted)
            slider.blockSignals(False)
            self.fx_values[key] = float(wanted)
            lbl = self.fx_labels.get(key)
            if lbl is not None:
                lbl.setText(fx_format(key, float(wanted)))
        self._sync_fx_reset_states()

    def _fx_boot(self):
        """Find ffmpeg and wire the debounced render timer (called once)."""
        self._fx_pending = (None, None, None)
        self._fx_applied_src = None
        self.fx_bypass = False
        self._fx_ffmpeg = fx_find_ffmpeg()
        self._fx_proc = QProcess(self)
        self._fx_proc.finished.connect(self._on_fx_render_done)
        self._fx_render_timer = QTimer(self)
        self._fx_render_timer.setSingleShot(True)
        self._fx_render_timer.timeout.connect(self._start_fx_render)
        if not self._fx_ffmpeg:
            self._fx_status('FX off · ffmpeg missing', '#f59e0b')
        print('[remix rack] ffmpeg:', self._fx_ffmpeg or 'NOT FOUND - rendered FX disabled')
        self._fx_tip()

    def _create_youtube_tab(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        # Header Title
        title_row = QHBoxLayout()
        yt_title = QLabel('Bulk queue or single track')
        yt_title.setStyleSheet('color: #64748b; font-size: 9.5px;')
        title_row.addWidget(yt_title)
        title_row.addStretch()

        paste_btn = QPushButton('📋 Paste URL / List')
        paste_btn.setObjectName('toolBtn')
        paste_btn.setFixedHeight(22)
        paste_btn.clicked.connect(self._paste_into_yt_input)
        title_row.addWidget(paste_btn)

        clear_btn = QPushButton('🧹 Clear')
        clear_btn.setObjectName('toolBtn')
        clear_btn.setFixedHeight(22)
        clear_btn.clicked.connect(lambda: self.yt_url_input.clear())
        title_row.addWidget(clear_btn)
        layout.addLayout(title_row)

        # Multi-line URL Input for bulk support
        self.yt_url_input = QPlainTextEdit()
        self.yt_url_input.setPlaceholderText(
            "Paste one or multiple YouTube URLs (one URL per line) or playlist links:\n"
            "https://www.youtube.com/watch?v=...\n"
            "https://youtu.be/...\n"
            "https://www.youtube.com/playlist?list=..."
        )
        self.yt_url_input.setFixedHeight(52)
        layout.addWidget(self.yt_url_input)

        opt_row = QHBoxLayout()
        opt_row.setSpacing(6)

        q_lbl = QLabel('Audio Format / Quality:')
        q_lbl.setStyleSheet('color: #94a3b8; font-weight: 600;')
        opt_row.addWidget(q_lbl)

        # Default FLAC Lossless selected by default as requested
        self.yt_quality_combo = QComboBox()
        self.yt_quality_combo.setFixedHeight(22)
        self.yt_quality_combo.addItems([
            'FLAC Lossless Audio (Highest Fidelity - Best Quality)',
            '320 kbps MP3 (Studio Quality)',
            '256 kbps MP3 (High Quality)',
            '192 kbps MP3 (Standard)',
            'Original Audio (Best Available Stream)'
        ])
        self.yt_quality_combo.setCurrentIndex(0)
        opt_row.addWidget(self.yt_quality_combo)

        opt_row.addStretch()

        self.yt_cancel_btn = QPushButton('⏹ Cancel')
        self.yt_cancel_btn.setObjectName('toolBtn')
        self.yt_cancel_btn.setFixedHeight(22)
        self.yt_cancel_btn.setMinimumWidth(95)
        self.yt_cancel_btn.setVisible(False)
        self.yt_cancel_btn.clicked.connect(self._cancel_youtube_download)
        opt_row.addWidget(self.yt_cancel_btn)

        self.yt_dl_btn = QPushButton('⬇  Start Bulk Download')
        self.yt_dl_btn.setObjectName('actionBtn')
        self.yt_dl_btn.setObjectName('actionBtn')
        self.yt_dl_btn.setFixedHeight(22)
        self.yt_dl_btn.setMinimumWidth(205)
        self.yt_dl_btn.clicked.connect(self._start_youtube_download)
        opt_row.addWidget(self.yt_dl_btn)

        layout.addLayout(opt_row)

        self.yt_progress = QProgressBar()
        self.yt_progress.setFixedHeight(6)
        self.yt_progress.setRange(0, 100)
        self.yt_progress.setValue(0)
        self.yt_progress.setVisible(False)
        layout.addWidget(self.yt_progress)

        self.yt_status_lbl = QLabel('Ready to download. Audio files will automatically join your library.')
        self.yt_status_lbl.setStyleSheet('color: #64748b; font-size: 9.5px;')
        layout.addWidget(self.yt_status_lbl)

        layout.addStretch()
        return panel

    def _paste_into_yt_input(self):
        clip = QApplication.clipboard().text()
        if clip:
            cur = self.yt_url_input.toPlainText().strip()
            if cur:
                self.yt_url_input.setPlainText(f"{cur}\n{clip.strip()}")
            else:
                self.yt_url_input.setPlainText(clip.strip())

    # ─────────────────────────────────────────────────────────────────────────
    # STYLESHEET & THEMING
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = self.t
        self.visualizer.set_theme(self.theme_key)
        self.timeline.set_theme_colors(t['track'], t['accent'], t['accent2'])
        self.waveform_bar.set_theme_colors(t['track'], t['accent'], t['accent2'])
        self.battery_volume.set_theme_colors(t['track'], t['accent'], t['accent2'], t['border'])

        qss = f"""
        QMainWindow, QWidget {{
            background-color: {t['bg']};
            color: {t['text']};
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }}
        QFrame#headerBar {{
            background: {t['bg_card']};
            border: 1px solid {t['border']};
            border-radius: {t['radius']};
        }}
        QLabel#brandTitle {{
            color: {t['accent']};
            letter-spacing: 1px;
        }}
        QLabel#statusPill {{
            background: {t['btn']};
            color: {t['accent']};
            border: 1px solid {t['border']};
            border-radius: 4px;
            padding: 3px 8px;
            font-weight: bold;
            font-size: 10px;
        }}
        QLabel#speedBadge {{
            background: {t['btn']};
            color: {t['accent']};
            border: 1px solid {t['border']};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: bold;
            font-size: 11px;
            font-family: 'Consolas', monospace;
        }}
        QLabel#nowPlayingBanner {{
            color: {t['text']};
            font-weight: 600;
            font-size: 12px;
        }}
        QFrame#panoramicVisCard {{
            background: {t['bg_card']};
            border: 1px solid {t['border']};
            border-radius: {t['radius']};
        }}
        QFrame#transportCard {{
            background: {t['bg_card']};
            border: 1px solid {t['border']};
            border-radius: {t['radius']};
        }}
        QLabel#timeLabel {{
            color: {t['text_dim']};
            font-family: 'Consolas', 'Courier New', monospace;
            font-weight: bold;
            font-size: 11px;
        }}
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.20),
                stop:0.045 rgba(255, 255, 255, 0.09),
                stop:0.5 rgba(255, 255, 255, 0.015),
                stop:1.0 rgba(0, 0, 0, 0.34)), {t['btn']};
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.13);
            border-top: 1px solid rgba(255, 255, 255, 0.38);
            border-bottom: 1px solid rgba(0, 0, 0, 0.55);
            border-radius: 9px;
            padding: 4px 11px;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            font-weight: 700;
            font-size: 11.5px;
            letter-spacing: 0.3px;
            outline: none;
        }}
        QPushButton:focus {{
            border: 1px solid {t['accent']}aa;
        }}
        QPushButton#cellReset {{
            background: transparent;
            border: none;
            color: {t['text_sub']};
            font-size: 9px;
            font-weight: 700;
            padding: 0px;
            margin: 0px;
        }}
        QPushButton#cellReset:hover {{
            color: {t['accent']};
        }}
        QPushButton#cellReset:disabled {{
            color: rgba(255, 255, 255, 0.09);
        }}
        QPushButton:disabled {{
            color: rgba(255, 255, 255, 0.32);
            border: 1px solid rgba(255, 255, 255, 0.07);
            background: rgba(255, 255, 255, 0.02);
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {t['accent']}38,
                stop:0.45 {t['accent']}18,
                stop:1.0 {t['btn_hover']});
            border: 1.5px solid {t['accent']};
            border-top: 1.5px solid rgba(255, 255, 255, 0.70);
            border-bottom: 2px solid {t['accent']};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(0, 0, 0, 0.55),
                stop:1.0 {t['accent']}28);
            border: 1.5px solid {t['accent']};
            padding-top: 6px;
            padding-left: 12px;
        }}
        QPushButton:checked {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {t['accent']}65,
                stop:1.0 {t['accent']}30);
            border: 1.5px solid {t['accent']};
            color: {t['accent']};
            font-weight: 800;
        }}
        QPushButton#iconBtn {{
            padding: 0px;
            margin: 0px;
            font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', 'Apple Color Emoji', 'Noto Color Emoji', 'Segoe UI', sans-serif;
            font-size: 13.5px;
            font-weight: bold;
            border-radius: 9px;
            text-align: center;
        }}
        QPushButton#iconBtn:hover {{
            padding: 0px;
        }}
        QPushButton#iconBtn:pressed {{
            padding: 1px 0px 0px 1px;
        }}
        QPushButton#iconBtn:checked {{
            padding: 0px;
        }}
        QPushButton#reorderBtn {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.14),
                stop:1.0 rgba(255, 255, 255, 0.02)), {t['btn']};
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-top: 1px solid rgba(255, 255, 255, 0.30);
            border-radius: 8px;
            color: #ffffff;
            font-weight: 700;
            padding: 3px 8px;
        }}
        QPushButton#reorderBtn:hover {{
            border: 1.5px solid {t['accent']};
            color: {t['accent']};
            background: {t['accent']}28;
        }}
        QPushButton#hudBtn {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 9px;
            padding: 4px 12px;
            color: #ffffff;
            font-weight: 700;
        }}
        QPushButton#hudBtn:hover {{
            background: rgba(255, 255, 255, 0.18);
            border: 1.5px solid {t['accent']};
        }}
        QPushButton#hudBtn:checked {{
            background: {t['accent']}40;
            border: 1.5px solid {t['accent']};
            color: {t['accent']};
        }}
        QPushButton#statusPill {{
            background: rgba(255, 255, 255, 0.06);
            border: 1.5px solid {t['accent']}88;
            border-radius: 12px;
            padding: 2px 10px;
            font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', 'Segoe UI', sans-serif;
            font-size: 11px;
            font-weight: 700;
            color: {t['accent']};
            text-align: center;
        }}
        QPushButton#statusPill:hover {{
            background: {t['accent']}30;
            border: 1.5px solid {t['accent']};
            color: #ffffff;
            padding: 2px 10px;
        }}
        QPushButton#statusPill:pressed {{
            padding: 3px 9px 1px 11px;
        }}
        QPushButton#playBtn {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {t['accent']}, stop:0.55 {t['accent2']}, stop:1.0 {t['accent3'] if 'accent3' in t else t['accent2']});
            color: #030712;
            font-weight: 900;
            font-size: 12.5px;
            letter-spacing: 0.8px;
            border-radius: 16px;
            border: 1.5px solid rgba(255, 255, 255, 0.70);
            padding: 5px 16px;
        }}
        QPushButton#playBtn:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ffffff, stop:0.28 {t['accent']}, stop:0.72 {t['accent2']},
                stop:1.0 #ffffff);
            border: 2px solid #ffffff;
            color: #000000;
            letter-spacing: 1.2px;
        }}
        QPushButton#playBtn:pressed {{
            padding-top: 6px;
            padding-left: 17px;
        }}
        QPushButton#actionBtn {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {t['accent']}, stop:1.0 {t['accent2']});
            color: #030712;
            font-weight: 900;
            font-size: 12px;
            letter-spacing: 0.5px;
            border-radius: 16px;
            border: 1.5px solid rgba(255, 255, 255, 0.65);
            padding: 5px 16px;
        }}
        QPushButton#actionBtn:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ffffff, stop:0.40 {t['accent']}, stop:1.0 {t['accent2']});
            border: 2px solid #ffffff;
            color: #000000;
        }}
        QSplitter::handle {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 2px;
        }}
        QSplitter::handle:hover {{
            background: rgba(0, 240, 255, 0.25);
        }}
        QTableWidget {{
            background-color: {t['track']};
            border: 1px solid {t['border_dim']};
            border-radius: 8px;
            gridline-color: transparent;
            selection-background-color: {t['accent']}33;
            selection-color: {t['accent']};
            font-size: 11px;
        }}
        QTableWidget#playlistTable {{
            font-size: 9.5px;
        }}
        QTableWidget#playlistTable::item {{
            padding: 0px 4px;
        }}
        QScrollArea#sideScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#sideScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QTableWidget::item {{
            padding: 2px 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}
        QTableWidget::item:selected {{
            background-color: {t['accent']}35;
            color: {t['accent']};
            font-weight: bold;
        }}
        QHeaderView::section {{
            background-color: {t['btn']};
            color: {t['text_dim']};
            padding: 4px 6px;
            border: none;
            border-bottom: 1px solid {t['border_dim']};
            font-weight: bold;
            font-size: 10px;
        }}
        QWidget#workspacePanel {{
                    background: transparent;
                }}
                QFrame#sectionCard {{
                    background: {t['bg_card']};
                    border: 1px solid {t['border_dim']};
                    border-radius: 8px;
                }}
                QLabel#sectionHeader {{
                    color: {t['accent']};
                    font-size: 9.5px;
                    font-weight: 800;
                    letter-spacing: 1.2px;
                    padding: 0px;
                }}
                QFrame#sectionDivider {{
                    background: {t['border_dim']};
                    max-height: 1px;
                    border: none;
                }}
                /* ── Revamped transport controls ── */
                QPushButton#transportBtn {{
                    background: rgba(255, 255, 255, 0.035);
                    color: {t['text_dim']};
                    border: 1px solid {t['border_dim']};
                    border-radius: 8px;
                    padding: 0px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton#transportBtn:hover {{
                    background: {t['accent']}22;
                    color: {t['accent']};
                    border: 1px solid {t['accent']}99;
                }}
                QPushButton#transportBtn:pressed {{
                    background: {t['accent']}3d;
                    color: #ffffff;
                }}
                QPushButton#transportBtn:checked {{
                    background: {t['accent']}2e;
                    color: {t['accent']};
                    border: 1px solid {t['accent']};
                }}
                QPushButton#stepBtn {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 255, 255, 0.10),
                        stop:1 rgba(0, 0, 0, 0.30));
                    color: {t['accent']};
                    border: 1px solid {t['accent']}66;
                    border-radius: 17px;
                    font-size: 13px;
                    padding: 0px;
                }}
                QPushButton#stepBtn:hover {{
                    background: {t['accent']}30;
                    color: #ffffff;
                    border: 1px solid {t['accent']};
                }}
                QPushButton#stepBtn:pressed {{
                    background: {t['accent']}55;
                }}
                QPushButton#toolBtn {{
            background: rgba(255, 255, 255, 0.045);
            color: {t['text_dim']};
            border: 1px solid {t['border_dim']};
            border-radius: 6px;
            padding: 0px 7px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.2px;
        }}
        QPushButton#toolBtn:hover {{
            background: {t['accent']}1f;
            color: {t['accent']};
            border: 1px solid {t['accent']}aa;
        }}
        QPushButton#toolBtn:pressed {{
            background: {t['accent']}3d;
            color: #ffffff;
        }}
        QPushButton#chipBtn {{
                    background: rgba(255, 255, 255, 0.04);
                    color: {t['text_dim']};
                    border: 1px solid {t['border_dim']};
                    border-radius: 6px;
                    padding: 0px 6px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton#chipBtn:hover {{
                    color: {t['accent']};
                    border: 1px solid {t['accent']}aa;
                    background: {t['accent']}1f;
                }}
                QPushButton#chipBtn:checked {{
                    color: {t['accent']};
                    border: 1px solid {t['accent']};
                    background: {t['accent']}26;
                }}
                QPushButton#toggleBtn {{
                    background: rgba(255, 255, 255, 0.05);
                    color: {t['text_dim']};
                    border: 1px solid {t['border_dim']};
                    border-radius: 7px;
                    padding: 0px 9px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton#toggleBtn:hover {{
                    color: {t['accent']};
                    border: 1px solid {t['accent']}aa;
                }}
                QPushButton#toggleBtn:checked {{
                    background: {t['accent']}26;
                    color: {t['accent']};
                    border: 1px solid {t['accent']};
                }}
        QLineEdit {{
            background-color: {t['track']};
            color: {t['text']};
            border: 1px solid {t['border_dim']};
            border-radius: 6px;
            padding: 4px 8px;
            selection-background-color: {t['accent']};
        }}
        QLineEdit:focus {{
            border: 1px solid {t['accent']};
        }}
        QComboBox QAbstractItemView {{
            background: {t['bg_card']};
            color: {t['text']};
            border: 1px solid {t['accent']}55;
            border-radius: 8px;
            padding: 3px;
            outline: none;
            selection-background-color: {t['accent']}33;
            selection-color: {t['accent']};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 20px;
            padding: 2px 8px;
            border-radius: 5px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background: {t['accent']}22;
        }}
        QComboBox {{
            background-color: {t['btn']};
            color: {t['text']};
            border: 1px solid {t['border_dim']};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        QSlider::groove:horizontal {{
            background: {t['track']};
            height: 6px;
            border-radius: 3px;
            border: 1px solid {t['border_dim']};
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t['accent']}, stop:1 {t['accent2']});
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.8 #d1d5db, stop:1.0 {t['accent']});
            width: 14px;
            margin: -4px 0;
            border-radius: 7px;
            border: 1px solid rgba(0, 0, 0, 0.4);
        }}
        QSlider::handle:horizontal:hover {{
            background: #ffffff;
            border: 1.5px solid {t['accent']};
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::groove:vertical {{
            background: {t['track']};
            width: 6px;
            border-radius: 3px;
            border: 1px solid {t['border_dim']};
        }}
        QSlider::sub-page:vertical {{
            background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 {t['accent']}, stop:1 {t['accent2']});
            border-radius: 3px;
        }}
        QSlider::handle:vertical {{
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.8 #d1d5db, stop:1.0 {t['accent']});
            height: 14px;
            margin: 0 -4px;
            border-radius: 7px;
            border: 1px solid rgba(0, 0, 0, 0.4);
        }}
        QSlider::handle:vertical:hover {{
            background: #ffffff;
            border: 1.5px solid {t['accent']};
            height: 16px;
            margin: 0 -5px;
            border-radius: 8px;
        }}
        """
        self.setStyleSheet(qss)
        # the mode switch is custom-painted, so it needs the accent pushed (not styled)
        try:
            self.view_switch.set_accent(t['accent'])
        except Exception:
            pass

    def _on_theme_changed(self, idx):
        key = self.theme_combo.currentData()
        if key not in THEMES:
            return
        self.theme_key = key
        self.t = THEMES[key]
        # Live preview of the custom-painted widgets (cheap, no restyle)...
        try:
            self.timeline.set_theme_colors(self.t['track'], self.t['accent'], self.t['accent2'])
            self.waveform_bar.set_theme_colors(self.t['track'], self.t['accent'], self.t['accent2'])
            self.visualizer.set_theme(key)
            self.visualizer.update()
        except Exception:
            pass
        # ...then the full stylesheet once the dropdown is dismissed, so the
        # popup is never torn down mid-selection.
        self._pending_theme = True
        if not self.theme_combo.view().isVisible():
            self._apply_pending_theme()

    def _apply_pending_theme(self):
        if not getattr(self, '_pending_theme', False):
            return
        self._pending_theme = False
        try:
            self._apply_theme()
            self._save_persisted_settings()
        except Exception:
            pass

    def _on_vis_combo_changed(self, idx):
        mode_key = self.vis_mode_combo.currentData()
        if mode_key in ModernVisualizer.MODES:
            self.visualizer.set_mode(mode_key)

    def _toggle_video_view(self):
        self.is_video_mode = self.video_toggle_btn.isChecked()
        if self.is_video_mode:
            self.video_toggle_btn.setText('📊 VISUALIZER VIEW')
            self.visualizer.setVisible(False)
            self.video_widget.setVisible(True)
            self.player.setVideoOutput(self.video_widget)
        else:
            self.video_toggle_btn.setText('🎬 VIDEO VIEW')
            self.player.setVideoOutput(None)
            self.video_widget.setVisible(False)
            self.visualizer.setVisible(True)

    # ─────────────────────────────────────────────────────────────────────────
    # PLAYBACK ENGINE & SIGNALS (CLEAN TRACK SWITCHING)
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.current_index < 0 and self.playlist:
                self.current_index = 0
            if self.current_index >= 0:
                if self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
                    self.player.play()
                else:
                    self._play_current()

    def _play_current(self):
        """
        Surgically load and play selected song:
        1. Saves profile for the PREVIOUS track (without contaminating the new track).
        2. Cleanly clears all loop points and loop states BEFORE touching player.
        3. If this song has customized A:B loop points, restores them and starts playback inside the loop at Point A.
        4. If this song has NO customized loop, starts smoothly at 0:00.
        5. Loads the audio track waveform overview.
        6. Restores song's specific EQ / speed / width settings.
        """
        if 0 <= self.current_index < len(self.playlist):
            new_filepath = self.playlist[self.current_index]

            # 1. Save PREVIOUS song's profile using self.current_playing_track
            if self.current_playing_track and self.current_playing_track != new_filepath:
                self._save_song_profile_for(self.current_playing_track)

            # 2. Update active track pointer
            self.current_playing_track = new_filepath

            # 3. Clean defaults before applying profile
            self.loop_a = None
            self.loop_b = None
            self.loop_active = False
            self.pending_seek_ms = None
            self._pending_loop = None
            self._seek_attempts = 0
            self._seek_guard_timer.stop()
            self.timeline.clear_loop()
            self.waveform_bar.clear_loop()
            self._update_loop_badge()

            # 4. Check if new song has a customized profile (A:B loop, EQ, speed)
            start_pos_ms = 0
            prof = self._get_song_profile(new_filepath)
            if prof:
                saved_a = prof.get('loop_a')
                saved_b = prof.get('loop_b')
                if saved_a is not None and saved_b is not None:
                    self.loop_a = int(saved_a)
                    self.loop_b = int(saved_b)
                    self.loop_active = bool(prof.get('loop_active', True))
                    self._pending_loop = (self.loop_a, self.loop_b, self.loop_active)
                    self.timeline.set_loop_points(self.loop_a, self.loop_b)
                    self.waveform_bar.set_loop_points(self.loop_a, self.loop_b)
                    self._update_loop_badge()
                    if self.loop_active:
                        start_pos_ms = self.loop_a

            # 5. Set source & start playback inside the loop if active, or at 0:00
            #    The seek itself is performed by the verified guard timer, which
            #    only fires once the new source reports LoadedMedia/BufferedMedia,
            #    so a saved A:B point is honoured on every track change.
            self.saw_loading = True
            # Remix rack: play the rendered copy when it already exists,
            # otherwise the untouched original (a render is queued below).
            self._fx_applied_src = self._fx_resolved_source(new_filepath)
            self.player.setSource(QUrl.fromLocalFile(self._fx_applied_src))
            self._schedule_fx_render(150)
            self.player.play()
            self._begin_pending_seek(start_pos_ms)

            p = Path(new_filepath)
            name = p.stem
            ext = p.suffix.upper().replace('.', '')
            self.now_playing_label.setText(f"▶  {name}  [{ext}]")
            self.status_pill.setText('● PLAYING')

            if p.suffix.lower() in VIDEO_EXTS and not self.is_video_mode:
                self.video_toggle_btn.setChecked(True)
                self._toggle_video_view()

            # 6. Clear previous audio buffer and load new waveform overview in background
            self.visualizer.clear_audio_buffer()
            self.waveform_bar.load_track(new_filepath)

            # 7. Apply this specific song's remaining profile (speed, EQ, bass boost)
            self._apply_song_profile(new_filepath)

            self._update_table_status_icons()
            self._save_persisted_settings()

    def _begin_pending_seek(self, ms):
        """Queue an authoritative seek that is retried until it verifiably lands."""
        self._seek_attempts = 0
        self.pending_seek_ms = int(ms) if ms and ms > 0 else None
        if self.pending_seek_ms is not None:
            self._seek_guard_timer.start()
            # Try immediately too — a cached local file may already be loaded.
            self._apply_pending_seek_if_needed()
        else:
            self._seek_guard_timer.stop()
            self.saw_loading = False
            self.timeline.setValue(0)
            self.waveform_bar.set_position(0)
            self.time_elapsed_lbl.setText(self._format_time_ms(0))
            self._reassert_pending_loop()

    def _reassert_pending_loop(self):
        """Re-assert this song's saved A:B loop once the media is actually ready."""
        if not self._pending_loop:
            return
        a_ms, b_ms, active = self._pending_loop
        self.loop_a = a_ms
        self.loop_b = b_ms
        self.loop_active = bool(active)
        self.timeline.set_loop_points(a_ms, b_ms)
        self.waveform_bar.set_loop_points(a_ms, b_ms)
        self._update_loop_badge()

    def _apply_pending_seek_if_needed(self):
        """
        Sole authority for consuming the pending A:B resume seek.

        Retries `setPosition(target)` on every guard tick until the player
        reports a position near the target (or attempts run out), which defeats
        both races that previously made the next song start at 0:00:
          * setPosition() issued before the new source finished loading (dropped)
          * a stale positionChanged() from the old track consuming the request
        """
        if self.pending_seek_ms is None:
            self._seek_guard_timer.stop()
            return

        st = self.player.mediaStatus()
        dur = self.player.duration()
        loaded = st in (QMediaPlayer.MediaStatus.LoadedMedia,
                        QMediaPlayer.MediaStatus.BufferedMedia)
        if not loaded or dur <= 0:
            self._seek_attempts += 1
            if self._seek_attempts > self._seek_max_attempts:
                self._cancel_pending_seek()
            return

        target = int(self.pending_seek_ms)
        target = max(0, min(target, max(0, dur - 200)))
        self._seek_attempts += 1

        try:
            self.player.setPosition(target)
            cur = self.player.position()
        except Exception:
            cur = -1

        settled = abs(cur - target) < 1500
        if settled or self._seek_attempts >= 6:   # always stop spinning eventually
            self._seek_guard_timer.stop()
            self.pending_seek_ms = None
            self.saw_loading = False
            if dur > 0:
                self.timeline.setValue(int((target / dur) * self.timeline.maximum()))
            self.waveform_bar.set_position(target)
            self.time_elapsed_lbl.setText(self._format_time_ms(target))
            self._reassert_pending_loop()

    def _cancel_pending_seek(self):
        self._seek_guard_timer.stop()
        self.pending_seek_ms = None
        self.saw_loading = False
        self._reassert_pending_loop()

    def _stop_playback(self):
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        self._cancel_pending_seek()
        self.player.stop()
        self.status_pill.setText('● STOPPED')
        self.play_btn.setText('▶  PLAY')
        self.visualizer.engine.playing = False
        self.visualizer.clear_audio_buffer()
        
        # When stopped on a looped song, park playhead at Loop A
        reset_pos = self.loop_a if (self.loop_active and self.loop_a is not None) else 0
        dur = self.player.duration()
        self.timeline.setValue(int((reset_pos / max(1, dur)) * 1000) if dur > 0 else 0)
        self.waveform_bar.set_position(reset_pos)
        self.time_elapsed_lbl.setText(self._format_time_ms(reset_pos))
        self._update_table_status_icons()

    def _prev_track(self):
        if not self.playlist:
            return
        if getattr(self, '_is_transitioning_track', False):
            return
        self._is_transitioning_track = True
        try:
            if self.shuffle_enabled and len(self.playlist) > 1:
                self.current_index = random.randint(0, len(self.playlist) - 1)
            else:
                self.current_index = (self.current_index - 1) % len(self.playlist)
            self._play_current()
        finally:
            self._is_transitioning_track = False

    def _next_track(self):
        if not self.playlist:
            return
        if getattr(self, '_is_transitioning_track', False):
            return
        self._is_transitioning_track = True
        try:
            if self.shuffle_enabled and len(self.playlist) > 1:
                self.current_index = random.randint(0, len(self.playlist) - 1)
            else:
                self.current_index = (self.current_index + 1) % len(self.playlist)
            self._play_current()
        finally:
            self._is_transitioning_track = False

    def _seek_relative(self, delta_ms):
        pos = self.player.position() + delta_ms
        pos = max(0, min(self.player.duration(), pos))
        self.player.setPosition(pos)

    def _on_seek_requested(self, val_or_ms):
        dur = self.player.duration()
        if dur > 0:
            if val_or_ms <= 1000 and self.timeline.maximum() == 1000:
                frac = val_or_ms / 1000.0
                target_ms = int(frac * dur)
            else:
                target_ms = val_or_ms
            self.player.setPosition(target_ms)
            self.waveform_bar.set_position(target_ms)

    def _on_audio_buffer_ready(self, filepath, audio_buf):
        if filepath == self.current_playing_track:
            self.visualizer.set_audio_buffer(audio_buf)

    def _on_timeline_loop_changed(self, a_ms, b_ms):
        self.loop_a = a_ms if a_ms >= 0 else None
        self.loop_b = b_ms if b_ms >= 0 else None
        self.loop_active = (self.loop_a is not None and self.loop_b is not None)
        self.waveform_bar.set_loop_points(self.loop_a, self.loop_b)
        self._update_loop_badge()
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)

    def _on_position_changed(self, pos):
        # If a pending seek is queued (A:B start point for next track), do NOT
        # consume it here — early position events fire before the media is fully
        # loaded and the seek would be silently ignored.  Instead, re-apply the
        # seek and suppress the stale position update; the authoritative
        # consumption happens in _apply_pending_seek_if_needed(), which is
        # driven by the guard timer and _on_media_status_changed() once the
        # player is genuinely ready.
        if self.pending_seek_ms is not None:
            st = self.player.mediaStatus()
            dur = self.player.duration()
            loaded = st in (QMediaPlayer.MediaStatus.LoadedMedia,
                            QMediaPlayer.MediaStatus.BufferedMedia)
            # Re-apply only once the NEW source is really loaded.  A stale
            # duration from the previous track must never count as "ready".
            if loaded and dur > 0 and pos < self.pending_seek_ms - 1500:
                self.player.setPosition(int(min(self.pending_seek_ms, max(0, dur - 200))))
            # Never consume the request here — the guard timer owns it.
            return

        dur = self.player.duration()
        if dur > 0:
            frac = pos / dur
            self.timeline.setValue(int(frac * self.timeline.maximum()))
            self.waveform_bar.set_position(pos)
            self.time_elapsed_lbl.setText(self._format_time_ms(pos))

        # A/B Loop Enforcement:
        if self.loop_active and self.loop_a is not None and self.loop_b is not None:
            if pos >= self.loop_b:
                if self.repeat_mode == 'one':
                    # Single song loop: loop back to point A
                    self.player.setPosition(int(self.loop_a))
                else:
                    # Sequential playback (playing song one after another):
                    # Play the specific A:B part, then proceed to the next song!
                    if self.repeat_mode == 'all':
                        self._next_track()
                    elif self.repeat_mode == 'off':
                        if self.current_index < len(self.playlist) - 1:
                            self._next_track()
                        else:
                            self._stop_playback()

    def _on_duration_changed(self, dur):
        self.timeline.set_duration(dur)
        self.waveform_bar.set_duration(dur)
        self.time_total_lbl.setText(self._format_time_ms(dur))
        self._apply_pending_seek_if_needed()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText('⏸  PAUSE')
            self.status_pill.setText('● PLAYING')
            self.visualizer.engine.playing = True
        else:
            self.play_btn.setText('▶  PLAY')
            self.status_pill.setText('● PAUSED')
            self.visualizer.engine.playing = False
        self._update_table_status_icons()

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadingMedia:
            self.saw_loading = True
        elif status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._apply_pending_seek_if_needed()

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop_active and self.loop_a is not None:
                if self.repeat_mode == 'one':
                    self.player.setPosition(int(self.loop_a))
                    self.player.play()
                elif self.repeat_mode == 'all':
                    self._next_track()
                elif self.repeat_mode == 'off':
                    if self.current_index < len(self.playlist) - 1:
                        self._next_track()
                    else:
                        self._stop_playback()
            elif self.repeat_mode == 'one':
                self.player.setPosition(0)
                self.player.play()
            elif self.repeat_mode == 'all':
                self._next_track()
            elif self.repeat_mode == 'off':
                if self.current_index < len(self.playlist) - 1:
                    self._next_track()
                else:
                    self._stop_playback()

    def _on_battery_volume_changed(self, val):
        self.audio_out.setVolume(val / 100.0)
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        self._schedule_save_settings()

    def _toggle_mute(self):
        muted = not self.audio_out.isMuted()
        self.audio_out.setMuted(muted)
        self.battery_volume.set_muted(muted)

    def _on_speed_slider_changed(self, val):
        self.playback_speed = val / 100.0
        self._apply_playback_rate()
        self.speed_val_lbl.setText(f"{self.playback_speed:.2f}x")
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    def _nudge_speed(self, delta):
        cur = self.speed_slider.value()
        new_val = max(25, min(250, cur + int(delta * 100)))
        self.speed_slider.setValue(new_val)

    def _toggle_shuffle(self):
        self.shuffle_enabled = self.shuffle_btn.isChecked()
        self._save_persisted_settings()

    def _cycle_repeat(self):
        modes = ['off', 'all', 'one']
        idx = (modes.index(self.repeat_mode) + 1) % len(modes)
        self.repeat_mode = modes[idx]
        self._update_repeat_btn()
        self._save_persisted_settings()

    def _update_repeat_btn(self):
        if not hasattr(self, 'repeat_btn'):
            return
        icons = {'off': '🔁', 'all': '🔁 ALL', 'one': '🔂 1'}
        self.repeat_btn.setText(icons.get(self.repeat_mode, '🔁'))
        if self.repeat_mode == 'all':
            self.repeat_btn.setFixedWidth(62)
        elif self.repeat_mode == 'one':
            self.repeat_btn.setFixedWidth(48)
        else:
            self.repeat_btn.setFixedWidth(38)

    def _format_time_ms(self, ms):
        s = ms // 1000
        tenth = (ms % 1000) // 100
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        base = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        return f"{base}.{tenth}"

    # ─────────────────────────────────────────────────────────────────────────
    # A/B LOOPING
    # ─────────────────────────────────────────────────────────────────────────

    def _set_loop_a(self):
        self.loop_a = self.player.position()
        if self.loop_b is not None and self.loop_b <= self.loop_a:
            self.loop_b = self.loop_a + 1000
        self.loop_active = (self.loop_a is not None and self.loop_b is not None)
        self.timeline.set_loop_points(self.loop_a, self.loop_b)
        self.waveform_bar.set_loop_points(self.loop_a, self.loop_b)
        self._update_loop_badge()
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)

    def _set_loop_b(self):
        self.loop_b = self.player.position()
        if self.loop_a is not None and self.loop_b <= self.loop_a:
            self.loop_a, self.loop_b = self.loop_b, self.loop_a
        self.loop_active = (self.loop_a is not None and self.loop_b is not None)
        self.timeline.set_loop_points(self.loop_a, self.loop_b)
        self.waveform_bar.set_loop_points(self.loop_a, self.loop_b)
        self._update_loop_badge()
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)

    def _toggle_loop_active(self):
        if self.loop_a is not None and self.loop_b is not None:
            self.loop_active = not self.loop_active
            self._update_loop_badge()
            if self.current_playing_track:
                self._save_song_profile_for(self.current_playing_track)

    def _clear_loop(self):
        self.loop_a = None
        self.loop_b = None
        self.loop_active = False
        self.timeline.clear_loop()
        self.waveform_bar.clear_loop()
        self._update_loop_badge()
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)

    def _update_loop_badge(self):
        if self.loop_a is not None:
            self.btn_loop_a.setStyleSheet("background: rgba(0, 240, 255, 0.25); color: #00f0ff; border: 1.5px solid #00f0ff; font-weight: bold; border-radius: 8px;")
        else:
            self.btn_loop_a.setStyleSheet("")

        if self.loop_b is not None:
            self.btn_loop_b.setStyleSheet("background: rgba(255, 0, 127, 0.25); color: #ff007f; border: 1.5px solid #ff007f; font-weight: bold; border-radius: 8px;")
        else:
            self.btn_loop_b.setStyleSheet("")

        if self.loop_a is not None and self.loop_b is not None:
            ta = self._format_time_ms(self.loop_a)
            tb = self._format_time_ms(self.loop_b)
            if self.loop_active:
                self.loop_chip.setText(f"🔁 ON: {ta} → {tb}")
                self.loop_chip.setStyleSheet("background: rgba(0, 240, 255, 0.25); color: #00f0ff; border: 1.5px solid #00f0ff; font-weight: bold; border-radius: 6px; padding: 2px 10px; font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 11px;")
            else:
                self.loop_chip.setText(f"⏸ OFF: {ta} → {tb}")
                self.loop_chip.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 6px; padding: 2px 10px; font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 11px;")
            self.loop_chip.setMinimumWidth(150)
        elif self.loop_a is not None:
            ta = self._format_time_ms(self.loop_a)
            self.loop_chip.setText(f"A: {ta}")
            self.loop_chip.setStyleSheet("background: rgba(0, 240, 255, 0.15); color: #00f0ff; border: 1.5px solid rgba(0, 240, 255, 0.3); border-radius: 6px; padding: 2px 8px; font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 11px;")
            self.loop_chip.setMinimumWidth(85)
        else:
            self.loop_chip.setText("Loop: Off")
            self.loop_chip.setStyleSheet("")
            self.loop_chip.setMinimumWidth(85)

    # ─────────────────────────────────────────────────────────────────────────
    # GRANULAR 7-BAND EQUALIZER & DSP
    # ─────────────────────────────────────────────────────────────────────────

    def _on_eq_slider_changed(self, key, val):
        db = val / 10.0
        self.eq_values[key] = db
        self.eq_labels[key].setText(f"{db:+0.1f} dB")
        self.visualizer.engine.set_eq_gains(self.eq_values)
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    def _on_bass_boost_changed(self, val):
        self.bass_boost = val / 10.0
        pass  # label lived in the removed EQ panel
        self.eq_values['eq_60'] = min(15.0, self.eq_values.get('eq_60', 0.0) + self.bass_boost * 0.5)
        self.visualizer.engine.set_eq_gains(self.eq_values)
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    def _on_stereo_width_changed(self, val):
        self.stereo_width = float(val)
        pass  # label lived in the removed EQ panel
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    def _reset_eq(self):
        for k, s in self.eq_sliders.items():
            s.setValue(0)
        self._rack_set('bass', 0)
        self._rack_set('width', 100)
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    def _apply_eq_preset(self, preset_name):
        presets = {
            'Flat (Default)': [0, 0, 0, 0, 0, 0, 0],
            'Bass Boost Pro': [70, 60, 30, 0, 0, 10, 20],
            'Club / Dance': [60, 50, 20, 0, 20, 40, 50],
            'Vocal Clarity': [-20, -10, 10, 40, 40, 20, 0],
            'Treble Sparkle': [-10, 0, 0, 10, 30, 60, 80],
            'Acoustic Warmth': [20, 30, 10, 10, 20, 30, 40],
            'Rock / Metal': [50, 40, -10, -10, 10, 40, 60]
        }
        vals = presets.get(preset_name, [0]*7)
        keys = ['eq_60', 'eq_150', 'eq_400', 'eq_1000', 'eq_2500', 'eq_6000', 'eq_14000']
        for k, v in zip(keys, vals):
            if k in self.eq_sliders:
                self._eq_set(k, v)
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        else:
            self._schedule_save_settings()

    # ─────────────────────────────────────────────────────────────────────────
    # PER-SONG SETTINGS PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────────

    def _load_song_profiles(self):
        if self._profiles_file.exists():
            try:
                with open(self._profiles_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    self.song_profiles = {os.path.normpath(k): v for k, v in raw.items()}
            except Exception:
                self.song_profiles = {}

    def _save_song_profiles_to_disk(self):
        try:
            with open(self._profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self.song_profiles, f, indent=2)
        except Exception:
            pass

    def _save_song_profile_for(self, path_str):
        if self._is_applying_profile:
            return
        if not path_str:
            return
        key = os.path.normpath(str(path_str))
        existing = self.song_profiles.get(key, {})
        prof = dict(existing)
        prof.update({
            'speed': round(self.playback_speed, 2),
            'loop_a': self.loop_a,
            'loop_b': self.loop_b,
            'loop_active': self.loop_active,
            'eq_values': {k: round(v, 1) for k, v in self.eq_values.items()},
            'bass_boost': round(self.bass_boost, 1),
            'fx_rack': self._fx_values(),
            'stereo_width': self.stereo_width,
            'volume': self.battery_volume.volume,
            'updated_at': time.time()
        })
        self.song_profiles[key] = prof
        self._save_song_profiles_to_disk()
        for r, p in enumerate(self.playlist):
            if os.path.normpath(str(p)) == key:
                self._update_saved_fx_cell(r)
                break

    def _apply_song_profile(self, path_str):
        self._is_applying_profile = True
        try:
            prof = self._get_song_profile(path_str)
            if prof:
                # 1. Restore Speed
                saved_speed = prof.get('speed', 1.0)
                self.playback_speed = float(saved_speed)
                self._apply_playback_rate()
                self.speed_slider.setValue(int(saved_speed * 100))
                self.speed_val_lbl.setText(f"{self.playback_speed:.2f}x")

                # 2. Restore Volume
                if 'volume' in prof:
                    saved_vol = int(prof.get('volume', 70))
                    self.battery_volume.set_volume(saved_vol)
                    self.audio_out.setVolume(saved_vol / 100.0)

                # 3. Restore EQ & Bass Boost
                saved_eq = prof.get('eq_values', {})
                for k, val in saved_eq.items():
                    if k in self.eq_sliders:
                        self._eq_set(k, int(val * 10))
                        self.eq_values[k] = float(val)
                self.visualizer.engine.set_eq_gains(self.eq_values)

                saved_bb = prof.get('bass_boost', 0.0)
                self.bass_boost = float(saved_bb)
                self._rack_set('bass', saved_bb)
                pass  # label lived in the removed EQ panel

                saved_sw = prof.get('stereo_width', 100.0)
                self.stereo_width = float(saved_sw)
                self._rack_set('width', saved_sw)
                pass  # label lived in the removed EQ panel

                # 4. Restore loop pins onto timeline and activate loop if customized!
                saved_a = prof.get('loop_a')
                saved_b = prof.get('loop_b')
                if saved_a is not None and saved_b is not None:
                    self.loop_a = int(saved_a)
                    self.loop_b = int(saved_b)
                    self.loop_active = prof.get('loop_active', True)
                    self.timeline.set_loop_points(self.loop_a, self.loop_b)
                    self.waveform_bar.set_loop_points(self.loop_a, self.loop_b)
                    self._update_loop_badge()
            else:
                self.speed_slider.setValue(100)
                self._reset_eq()
                self._update_loop_badge()
        finally:
            self._is_applying_profile = False

    # ─────────────────────────────────────────────────────────────────────────
    # METADATA EXTRACTION & CACHING
    # ─────────────────────────────────────────────────────────────────────────

    def _load_meta_cache(self):
        if self._meta_cache_file.exists():
            try:
                with open(self._meta_cache_file, 'r', encoding='utf-8') as f:
                    self.metadata_cache = json.load(f)
            except Exception:
                self.metadata_cache = {}

    def _save_meta_cache_to_disk(self):
        try:
            with open(self._meta_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata_cache, f, indent=2)
        except Exception:
            pass

    def _get_track_metadata(self, filepath):
        if not filepath:
            return {}
        norm = os.path.normpath(str(filepath))
        if norm in self.metadata_cache:
            return self.metadata_cache[norm]
        if filepath in self.metadata_cache:
            return self.metadata_cache[filepath]
        norm_case = os.path.normcase(norm)
        for k, v in self.metadata_cache.items():
            if os.path.normcase(os.path.normpath(str(k))) == norm_case:
                return v

        p = Path(filepath)
        size_mb = 0.0
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
        except Exception:
            pass

        meta = {
            'title': p.stem,
            'artist': 'Unknown',
            'ext': p.suffix.upper().replace('.', ''),
            'size': f"{size_mb:.1f} MB",
            'duration_secs': 0,
            'quality': '',
            'folder': p.parent.name
        }

        f = None
        try:
            f = mutagen.File(filepath)
        except Exception:
            f = None

        if f and hasattr(f, 'info') and f.info:
            meta['duration_secs'] = int(getattr(f.info, 'length', 0))
            sr = getattr(f.info, 'sample_rate', 0)
            bps = getattr(f.info, 'bits_per_sample', 0)
            br = getattr(f.info, 'bitrate', 0)
            if bps and sr:
                meta['quality'] = f"{bps}-bit / {sr//1000}kHz"
            elif br:
                meta['quality'] = f"{br//1000} kbps"
            elif sr:
                meta['quality'] = f"{sr//1000} kHz"

            if hasattr(f, 'tags') and f.tags:
                for k in ['artist', 'ARTIST', 'TPE1']:
                    if k in f.tags:
                        val = f.tags[k]
                        meta['artist'] = str(val[0] if isinstance(val, list) else val)
                        break
                for k in ['title', 'TITLE', 'TIT2']:
                    if k in f.tags:
                        val = f.tags[k]
                        meta['title'] = str(val[0] if isinstance(val, list) else val)
                        break

        elif FFMPEG_DIR:
            try:
                cmd = [
                    f"{FFMPEG_DIR}/ffprobe.exe", '-v', 'error',
                    '-show_entries', 'format=duration,bit_rate:stream=codec_name,sample_rate',
                    '-of', 'json', filepath
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    d = json.loads(res.stdout)
                    meta['duration_secs'] = int(float(d.get('format', {}).get('duration', 0)))
                    streams = d.get('streams', [{}])
                    if streams:
                        codec = streams[0].get('codec_name', '').upper()
                        sr = streams[0].get('sample_rate', '')
                        meta['quality'] = f"{codec} {int(sr)//1000}kHz" if sr else codec
            except Exception:
                pass

        self.metadata_cache[filepath] = meta
        return meta

    # ─────────────────────────────────────────────────────────────────────────
    # MULTI-FOLDER LIBRARY MANAGEMENT & COMPACT TABLE
    # ─────────────────────────────────────────────────────────────────────────

    def _add_library_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Music Folder to Monitor', str(Path.home() / 'Music'))
        if folder and folder not in self.library_folders:
            self.library_folders.append(folder)
            self._scan_all_library_folders()
            self._save_persisted_settings()

    def _remove_library_folder(self):
        if not self.library_folders:
            return
        menu = QMenu(self)
        for folder in self.library_folders:
            action = menu.addAction(f"🗑 {folder}")
            action.triggered.connect(lambda checked, f=folder: self._do_remove_folder(f))
        menu.exec(QCursor.pos())

    def _do_remove_folder(self, folder):
        if folder in self.library_folders:
            self.library_folders.remove(folder)
            self.folders_summary_lbl.setText(f"{len(self.library_folders)} folders monitored")
            self._save_persisted_settings()

    def _scan_all_library_folders(self):
        added = 0
        for folder_path in self.library_folders:
            d = Path(folder_path)
            if d.is_dir():
                for f in d.rglob('*'):
                    if f.is_file() and f.suffix.lower() in MEDIA_EXTS:
                        fstr = os.path.normpath(str(f))
                        if fstr not in self.playlist:
                            self.playlist.append(fstr)
                            added += 1

        self._refresh_playlist_table()
        self._save_meta_cache_to_disk()
        self.folders_summary_lbl.setText(f"{len(self.library_folders)} folders monitored")
        self.playlist_stats_lbl.setText(f"Scan complete: Added {added} new tracks (Total: {len(self.playlist)})")
        self._save_persisted_settings()

    def _refresh_playlist_table(self):
        self.playlist_table.setRowCount(len(self.playlist))
        for row, path_str in enumerate(self.playlist):
            meta = self._get_track_metadata(path_str)
            p = Path(path_str)
            prof = self._get_song_profile(path_str)
            rating_val = prof.get('rating', 0)
            is_active = (row == self.current_index)

            self.playlist_table.setRowHeight(row, 18)

            # Col 0: '#'
            it_num = QTableWidgetItem(f"{row+1:02d}")
            it_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 0, it_num)

            # Col 1: '▶'
            it_status = QTableWidgetItem('▶' if is_active else '')
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 1, it_status)

            # Col 2: five real stars — click to rate, click again to clear
            rate_widget = QWidget()
            rate_layout = QHBoxLayout(rate_widget)
            rate_layout.setContentsMargins(2, 0, 2, 0)
            rate_layout.setSpacing(0)

            stars = StarRating(rating_val)

            def _on_rate_changed(val, ps=path_str):
                norm_ps = os.path.normpath(str(ps))
                p_dict = self.song_profiles.setdefault(norm_ps, {})
                p_dict['rating'] = val
                self._save_song_profiles_to_disk()
                self._schedule_save_settings()

            stars.rated.connect(_on_rate_changed)
            rate_layout.addWidget(stars)
            rate_layout.addStretch(1)
            self.playlist_table.setCellWidget(row, 2, rate_widget)

            # Col 3: Title
            it_title = QTableWidgetItem(meta.get('title') or p.stem)
            it_title.setToolTip(path_str)
            self.playlist_table.setItem(row, 3, it_title)

            # Col 4: Artist
            it_artist = QTableWidgetItem(meta.get('artist', 'Unknown'))
            self.playlist_table.setItem(row, 4, it_artist)

            # Col 5: Duration
            dur_s = meta.get('duration_secs', 0)
            m, s = divmod(dur_s, 60)
            dur_str = f"{m:02d}:{s:02d}" if dur_s > 0 else '--:--'
            it_dur = QTableWidgetItem(dur_str)
            it_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 5, it_dur)

            # Col 6: Format
            it_ext = QTableWidgetItem(meta.get('ext', 'AUDIO'))
            it_ext.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 6, it_ext)

            # Col 7: Quality
            it_qual = QTableWidgetItem(meta.get('quality', ''))
            it_qual.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 7, it_qual)

            # Col 8: Size
            it_size = QTableWidgetItem(meta.get('size', ''))
            it_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.playlist_table.setItem(row, 8, it_size)

            # Col 9: Folder Origin
            it_folder = QTableWidgetItem(meta.get('folder', ''))
            self.playlist_table.setItem(row, 9, it_folder)

            # Col 10: Saved FX Settings
            self._update_saved_fx_cell(row)

            # Contrast Coloring: Selected playing song is bright & vivid, others dim
            self._apply_row_contrast(row, is_active)

        self._apply_column_visibility()
        self.playlist_stats_lbl.setText(f"{len(self.playlist)} tracks in library")

    def _apply_row_contrast(self, row, is_active):
        if is_active:
            title_color = QColor(self.t['accent'])
            artist_color = QColor('#ffffff')
            dur_color = QColor('#ffffff')
            meta_color = QColor(self.t['accent2'])
            bg_color = QColor(self.t['accent'])
            bg_color.setAlpha(36)
        else:
            title_color = QColor(self.t['text'])
            artist_color = QColor(self.t['text_dim'])
            dur_color = QColor(self.t['text_dim'])
            meta_color = QColor(self.t['text_sub'])
            bg_color = QColor(0, 0, 0, 0)

        for c in range(self.playlist_table.columnCount()):
            it = self.playlist_table.item(row, c)
            if it:
                if is_active:
                    it.setBackground(bg_color)
                else:
                    it.setBackground(QColor(0, 0, 0, 0))

                if c == 0:
                    it.setForeground(title_color if is_active else QColor(self.t['text_sub']))
                elif c == 1:
                    it.setForeground(title_color)
                elif c == 3:
                    it.setForeground(title_color)
                    font = it.font()
                    font.setBold(is_active)
                    it.setFont(font)
                elif c == 4:
                    it.setForeground(artist_color)
                elif c == 5:
                    it.setForeground(dur_color)
                elif c in [6, 7, 8]:
                    it.setForeground(meta_color)
                elif c == 9:
                    it.setForeground(QColor(self.t['text_sub']))

    def _apply_column_visibility(self):
        for col, is_vis in self.visible_columns.items():
            if col < self.playlist_table.columnCount():
                self.playlist_table.setColumnHidden(col, not is_vis)

    def _show_column_picker_menu(self):
        menu = QMenu(self)
        col_names = [
            (0, '# Number'), (1, '▶ Status Icon'), (2, '⭐ Rating Slider'),
            (3, 'Title'), (4, 'Artist / Uploader'), (5, 'Duration'),
            (6, 'Format'), (7, 'Quality'), (8, 'Size'), (9, 'Folder Origin'), (10, 'Saved Settings')
        ]
        for col_idx, name in col_names:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(self.visible_columns.get(col_idx, True))
            def _toggle_col(checked, c=col_idx):
                self.visible_columns[c] = checked
                self._apply_column_visibility()
                self._schedule_save_settings()
            act.toggled.connect(_toggle_col)
        menu.exec(self.col_btn.mapToGlobal(QPoint(0, self.col_btn.height())))

    def _get_song_profile(self, path_str):
        if not path_str:
            return {}
        k = os.path.normpath(str(path_str))
        p = self.song_profiles.get(k)
        if not p:
            k_case = os.path.normcase(k)
            for sk, sv in self.song_profiles.items():
                if os.path.normcase(os.path.normpath(str(sk))) == k_case:
                    p = sv
                    break
        return p or {}

    def _get_song_rating(self, path_str):
        p = self._get_song_profile(path_str)
        return int(p.get('rating', 0)) if p else 0

    def _get_song_title(self, path_str):
        meta = self._get_track_metadata(path_str)
        t = meta.get('title')
        if not t or str(t).strip() == '' or str(t) == 'Unknown':
            t = Path(path_str).stem
        return str(t).strip().lower()

    def _get_song_artist(self, path_str):
        meta = self._get_track_metadata(path_str)
        a = meta.get('artist')
        if not a or str(a).strip() == '':
            a = 'Unknown'
        return str(a).strip().lower()

    def _get_song_duration(self, path_str):
        meta = self._get_track_metadata(path_str)
        return int(meta.get('duration_secs', 0))

    def _get_song_size(self, path_str):
        try:
            return os.path.getsize(path_str)
        except Exception:
            return 0

    def _get_song_mtime(self, path_str):
        try:
            return os.path.getmtime(path_str)
        except Exception:
            return 0

    def _sync_sort_combo(self, text):
        if hasattr(self, 'sort_combo'):
            self.sort_combo.blockSignals(True)
            idx = self.sort_combo.findText(text)
            if idx >= 0:
                self.sort_combo.setCurrentIndex(idx)
            self.sort_combo.blockSignals(False)

    def _on_table_header_clicked(self, col):
        if not self.playlist:
            return
        last_col = getattr(self, '_last_header_col', None)
        if last_col == col:
            self._sort_reverse = not getattr(self, '_sort_reverse', False)
        else:
            self._last_header_col = col
            self._sort_reverse = (col in [0, 1, 2, 5, 8, 10])

        current_playing = self.current_playing_track

        if col == 0:  # '#' Number
            self.playlist.reverse()
            self._sync_sort_combo('Custom / Manual (Drag & Drop)')
        elif col == 2:  # Rating
            self.playlist.sort(key=lambda p: (self._get_song_rating(p), self._get_song_title(p)), reverse=self._sort_reverse)
            self._sync_sort_combo('⭐ Rating: High → Low' if self._sort_reverse else '⭐ Rating: Low → High')
        elif col == 3:  # Title
            self.playlist.sort(key=lambda p: self._get_song_title(p), reverse=self._sort_reverse)
            self._sync_sort_combo('🔤 Title: Z → A' if self._sort_reverse else '🔤 Title: A → Z')
        elif col == 4:  # Artist
            self.playlist.sort(key=lambda p: (self._get_song_artist(p), self._get_song_title(p)), reverse=self._sort_reverse)
            self._sync_sort_combo('👤 Artist: Z → A' if self._sort_reverse else '👤 Artist: A → Z')
        elif col == 5:  # Duration
            self.playlist.sort(key=lambda p: self._get_song_duration(p), reverse=self._sort_reverse)
            self._sync_sort_combo('⏱️ Duration: Longest First' if self._sort_reverse else '⏱️ Duration: Shortest First')
        elif col == 6:  # Format
            self.playlist.sort(key=lambda p: (Path(p).suffix.lower(), self._get_song_title(p)), reverse=self._sort_reverse)
        elif col == 7:  # Quality
            self.playlist.sort(key=lambda p: (self._get_track_metadata(p).get('quality', ''), self._get_song_title(p)), reverse=self._sort_reverse)
        elif col == 8:  # Size
            self.playlist.sort(key=lambda p: self._get_song_size(p), reverse=self._sort_reverse)
            self._sync_sort_combo('💾 File Size: Largest First' if self._sort_reverse else '💾 File Size: Smallest First')
        elif col == 9:  # Folder
            self.playlist.sort(key=lambda p: (Path(p).parent.name.lower(), self._get_song_title(p)), reverse=self._sort_reverse)
        elif col == 10: # Saved FX
            self.playlist.sort(key=lambda p: (bool(self._get_song_profile(p)), self._get_song_title(p)), reverse=self._sort_reverse)

        if hasattr(self, 'playlist_table'):
            self.playlist_table.horizontalHeader().setSortIndicatorShown(True)
            self.playlist_table.horizontalHeader().setSortIndicator(col, Qt.SortOrder.DescendingOrder if self._sort_reverse else Qt.SortOrder.AscendingOrder)

        if current_playing:
            norm_curr = os.path.normpath(str(current_playing))
            for i, p in enumerate(self.playlist):
                if os.path.normpath(str(p)) == norm_curr:
                    self.current_index = i
                    break
        self._refresh_playlist_table()
        self._schedule_save_settings()

    def _apply_sort_by_index(self, idx):
        if not self.playlist:
            return
        current_playing = self.current_playing_track

        if idx == 1:  # Rating High to Low
            self.playlist.sort(key=lambda p: (self._get_song_rating(p), self._get_song_title(p)), reverse=True)
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(2, Qt.SortOrder.DescendingOrder)
        elif idx == 2:  # Rating Low to High
            self.playlist.sort(key=lambda p: (self._get_song_rating(p), self._get_song_title(p)))
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(2, Qt.SortOrder.AscendingOrder)
        elif idx == 3:  # Title A-Z
            self.playlist.sort(key=lambda p: self._get_song_title(p))
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(3, Qt.SortOrder.AscendingOrder)
        elif idx == 4:  # Title Z-A
            self.playlist.sort(key=lambda p: self._get_song_title(p), reverse=True)
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(3, Qt.SortOrder.DescendingOrder)
        elif idx == 5:  # Artist A-Z
            self.playlist.sort(key=lambda p: (self._get_song_artist(p), self._get_song_title(p)))
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(4, Qt.SortOrder.AscendingOrder)
        elif idx == 6:  # Artist Z-A
            self.playlist.sort(key=lambda p: (self._get_song_artist(p), self._get_song_title(p)), reverse=True)
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(4, Qt.SortOrder.DescendingOrder)
        elif idx == 7:  # Duration Longest
            self.playlist.sort(key=lambda p: self._get_song_duration(p), reverse=True)
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(5, Qt.SortOrder.DescendingOrder)
        elif idx == 8:  # Duration Shortest
            self.playlist.sort(key=lambda p: self._get_song_duration(p))
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(5, Qt.SortOrder.AscendingOrder)
        elif idx == 9:  # File Size Largest
            self.playlist.sort(key=lambda p: self._get_song_size(p), reverse=True)
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(8, Qt.SortOrder.DescendingOrder)
        elif idx == 10: # File Size Smallest
            self.playlist.sort(key=lambda p: self._get_song_size(p))
            if hasattr(self, 'playlist_table'):
                self.playlist_table.horizontalHeader().setSortIndicator(8, Qt.SortOrder.AscendingOrder)
        elif idx == 11: # Date Modified Newest
            self.playlist.sort(key=lambda p: self._get_song_mtime(p), reverse=True)

        if current_playing:
            norm_curr = os.path.normpath(str(current_playing))
            for i, p in enumerate(self.playlist):
                if os.path.normpath(str(p)) == norm_curr:
                    self.current_index = i
                    break
        self._refresh_playlist_table()
        self._schedule_save_settings()

    def _on_sort_changed(self, idx):
        if idx > 0:
            self._apply_sort_by_index(idx)

    def _update_saved_fx_cell(self, row):
        if row < 0 or row >= len(self.playlist):
            return
        path_str = self.playlist[row]
        prof = self._get_song_profile(path_str)
        badges = []
        if prof.get('speed') and prof['speed'] != 1.0:
            badges.append(f"⚡{prof['speed']:.2f}x")
        if prof.get('loop_a') is not None and prof.get('loop_b') is not None:
            badges.append("🔁A:B")
        if prof.get('bass_boost', 0.0) > 0:
            badges.append(f"+{prof['bass_boost']:.1f}dB")

        fx_str = " ".join(badges) if badges else "-"
        it_fx = QTableWidgetItem(fx_str)
        it_fx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if badges:
            it_fx.setForeground(QColor(self.t['accent']))
        else:
            it_fx.setForeground(QColor(self.t['text_sub']))
        self.playlist_table.setItem(row, 10, it_fx)

    def _update_table_status_icons(self):
        is_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        for r in range(self.playlist_table.rowCount()):
            it = self.playlist_table.item(r, 1)
            is_active = (r == self.current_index)
            if it:
                if is_active:
                    it.setText('▶' if is_playing else '⏸')
                    it.setForeground(QColor(self.t['accent']))
                else:
                    it.setText('')
            self._apply_row_contrast(r, is_active)

    def _on_table_double_clicked(self, item):
        row = item.row()
        if 0 <= row < len(self.playlist):
            self.current_index = row
            self._play_current()

    def _filter_playlist_table(self, query):
        q = query.lower().strip()
        for r in range(self.playlist_table.rowCount()):
            match = False
            if not q:
                match = True
            else:
                for c in [3, 4, 6, 7, 9]:
                    it = self.playlist_table.item(r, c)
                    if it and q in it.text().lower():
                        match = True
                        break
            self.playlist_table.setRowHidden(r, not match)

    def _show_track_context_menu(self, pos):
        item = self.playlist_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        if row < 0 or row >= len(self.playlist):
            return

        track_path = self.playlist[row]
        menu = QMenu(self)

        act_play = menu.addAction('▶ Play Track')
        act_reset_prof = menu.addAction('↺ Reset Song Settings')
        menu.addSeparator()
        act_top = menu.addAction('⏫ Move to Top (Alt+Home)')
        act_up = menu.addAction('▲ Move Up (Alt+Up)')
        act_down = menu.addAction('▼ Move Down (Alt+Down)')
        act_bottom = menu.addAction('⏬ Move to Bottom (Alt+End)')
        if row == 0:
            act_top.setEnabled(False)
            act_up.setEnabled(False)
        if row == len(self.playlist) - 1:
            act_down.setEnabled(False)
            act_bottom.setEnabled(False)
        menu.addSeparator()
        act_explore = menu.addAction('📁 Show in Explorer')
        act_copy = menu.addAction('📋 Copy File Path')
        menu.addSeparator()
        act_remove = menu.addAction('🗑 Remove from Library')

        chosen = menu.exec(self.playlist_table.viewport().mapToGlobal(pos))
        if chosen == act_play:
            self.current_index = row
            self._play_current()
        elif chosen == act_reset_prof:
            if track_path in self.song_profiles:
                del self.song_profiles[track_path]
                self._save_song_profiles_to_disk()
                self._update_saved_fx_cell(row)
        elif chosen == act_top:
            self._move_selected_track_top()
        elif chosen == act_up:
            self._move_selected_track(-1)
        elif chosen == act_down:
            self._move_selected_track(1)
        elif chosen == act_bottom:
            self._move_selected_track_bottom()
        elif chosen == act_explore:
            subprocess.run(['explorer', '/select,', track_path])
        elif chosen == act_copy:
            QApplication.clipboard().setText(track_path)
        elif chosen == act_remove:
            self.playlist.pop(row)
            if self.current_index == row:
                self._stop_playback()
                self.current_index = -1
            elif self.current_index > row:
                self.current_index -= 1
            self._refresh_playlist_table()

    def _on_playlist_row_reordered(self, from_row, to_row):
        if from_row == to_row or from_row < 0 or from_row >= len(self.playlist) or to_row < 0 or to_row >= len(self.playlist):
            return

        current_track = self.current_playing_track

        # Reorder list
        item = self.playlist.pop(from_row)
        self.playlist.insert(to_row, item)

        # Update current playing index
        if current_track and current_track in self.playlist:
            self.current_index = self.playlist.index(current_track)
        elif self.current_index == from_row:
            self.current_index = to_row

        # Switch sort dropdown to custom
        if hasattr(self, 'sort_combo'):
            self.sort_combo.blockSignals(True)
            self.sort_combo.setCurrentIndex(0)
            self.sort_combo.blockSignals(False)
        if hasattr(self, 'playlist_table'):
            self.playlist_table.horizontalHeader().setSortIndicatorShown(False)

        self._refresh_playlist_table()
        self.playlist_table.selectRow(to_row)
        self.playlist_table.setCurrentCell(to_row, 3)
        self._save_persisted_settings()

    def _move_selected_track(self, delta):
        row = self.playlist_table.currentRow()
        if row < 0 or row >= len(self.playlist):
            return
        target = row + delta
        if 0 <= target < len(self.playlist):
            self._on_playlist_row_reordered(row, target)

    def _move_selected_track_top(self):
        row = self.playlist_table.currentRow()
        if 0 < row < len(self.playlist):
            self._on_playlist_row_reordered(row, 0)

    def _move_selected_track_bottom(self):
        row = self.playlist_table.currentRow()
        if 0 <= row < len(self.playlist) - 1:
            self._on_playlist_row_reordered(row, len(self.playlist) - 1)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select Audio or Video Files',
            str(Path.home() / 'Music'),
            'Media Files (*.mp3 *.flac *.wav *.mp4 *.webm *.mkv *.m4a *.ogg *.aac)'
        )
        for f in files:
            norm_f = os.path.normpath(str(f))
            if norm_f not in self.playlist:
                self.playlist.append(norm_f)
        self._refresh_playlist_table()
        self._save_persisted_settings()

    def _remove_selected_track(self):
        row = self.playlist_table.currentRow()
        if 0 <= row < len(self.playlist):
            self.playlist.pop(row)
            if self.current_index == row:
                self._stop_playback()
                self.current_index = -1
            elif self.current_index > row:
                self.current_index -= 1
            self._refresh_playlist_table()
            self._save_persisted_settings()

    def _clear_playlist(self):
        self._stop_playback()
        self.playlist.clear()
        self.current_index = -1
        self._refresh_playlist_table()
        self._save_persisted_settings()

    # ─────────────────────────────────────────────────────────────────────────
    # YOUTUBE INTEGRATION
    # ─────────────────────────────────────────────────────────────────────────

    def _start_youtube_download(self):
        text = self.yt_url_input.toPlainText().strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            self.yt_status_lbl.setText('❌ Please paste one or more valid YouTube URLs first.')
            return

        self.yt_dl_btn.setEnabled(False)
        self.yt_cancel_btn.setVisible(True)
        self.yt_progress.setVisible(True)
        self.yt_progress.setValue(0)
        self.yt_status_lbl.setText(f'Starting extraction for {len(lines)} item(s)...')

        qual = self.yt_quality_combo.currentText().split()[0]
        self.downloader = YouTubeBulkDownloader(lines, quality=qual)
        self.downloader.queueProgress.connect(self._on_yt_queue_progress)
        self.downloader.itemProgress.connect(self._on_yt_progress)
        self.downloader.itemFinished.connect(self._on_yt_item_finished)
        self.downloader.itemError.connect(self._on_yt_item_error)
        self.downloader.allFinished.connect(self._on_yt_all_finished)
        self.downloader.start()

    def _cancel_youtube_download(self):
        if hasattr(self, 'downloader') and self.downloader.isRunning():
            self.downloader.cancel()
            self.yt_status_lbl.setText('Cancelling downloads...')
            self.yt_cancel_btn.setEnabled(False)

    def _on_yt_queue_progress(self, current, total, url):
        self.yt_status_lbl.setText(f"Processing ({current}/{total}): {url[:55]}...")

    def _on_yt_progress(self, pct, speed):
        self.yt_progress.setValue(pct)
        self.yt_status_lbl.setText(f"Downloading... {pct}%  ({speed})")

    def _on_yt_item_finished(self, idx, file_path, meta):
        if file_path not in self.playlist:
            self.playlist.append(file_path)
            self._refresh_playlist_table()
            if self.current_index < 0:
                self.current_index = 0
                self._play_current()

    def _on_yt_item_error(self, idx, url, err):
        self.yt_status_lbl.setText(f"⚠ Item {idx+1} Error: {err[:65]}")

    def _on_yt_all_finished(self, success_cnt, fail_cnt):
        self.yt_dl_btn.setEnabled(True)
        self.yt_cancel_btn.setVisible(False)
        self.yt_cancel_btn.setEnabled(True)
        self.yt_progress.setVisible(False)
        self.yt_url_input.clear()
        self.yt_status_lbl.setText(f"✓ Bulk Download Complete! Success: {success_cnt}, Failed: {fail_cnt}")

    # ─────────────────────────────────────────────────────────────────────────
    # (keyboard shortcuts removed — the app is fully mouse / button driven)
    # ─────────────────────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        """Intentionally empty: every keyboard binding has been removed."""
        return

    def _cycle_vis_mode(self):
        if hasattr(self, 'vis_mode_combo') and self.vis_mode_combo.count() > 0:
            idx = (self.vis_mode_combo.currentIndex() + 1) % self.vis_mode_combo.count()
            self.vis_mode_combo.setCurrentIndex(idx)

    def _cycle_theme(self):
        keys = list(THEMES.keys())
        idx = (keys.index(self.theme_key) + 1) % len(keys)
        self.theme_combo.setCurrentIndex(idx)

    # ─────────────────────────────────────────────────────────────────────────
    # SETTINGS PERSISTENCE & PANEL STATE
    # ─────────────────────────────────────────────────────────────────────────

    def _schedule_save_settings(self):
        if hasattr(self, '_save_timer'):
            self._save_timer.start(250)

    def _on_splitter_moved(self):
        if hasattr(self, 'main_splitter'):
            m_sizes = self.main_splitter.sizes()
            if len(m_sizes) == 3 and all(s > 20 for s in m_sizes):
                self._cached_main_sizes = m_sizes
        if hasattr(self, 'top_row_splitter'):
            t_sizes = self.top_row_splitter.sizes()
            if len(t_sizes) == 2 and all(s > 20 for s in t_sizes):
                self._cached_top_sizes = t_sizes
        self._schedule_save_settings()

    def _restore_splitter_positions(self):
        if hasattr(self, '_cached_main_sizes') and self._cached_main_sizes and hasattr(self, 'main_splitter'):
            self.main_splitter.setSizes(self._cached_main_sizes)
        if hasattr(self, '_cached_top_sizes') and self._cached_top_sizes and hasattr(self, 'top_row_splitter'):
            self.top_row_splitter.setSizes(self._cached_top_sizes)

    def showEvent(self, event):
        super().showEvent(event)
        self._restore_splitter_positions()
        QTimer.singleShot(100, self._restore_splitter_positions)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self._schedule_save_settings()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.isVisible():
            self._schedule_save_settings()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isVisible():
            self._schedule_save_settings()
        if event.type() == QEvent.Type.WindowStateChange:
            # Minimise-to-gadget. Deferred by a single shot because the state
            # change is still in flight here, and _exit_gadget_mode() calls
            # showNormal() — handling both synchronously would bounce.
            if self.isMinimized() and not getattr(self, '_gadget_active', False):
                QTimer.singleShot(0, self._enter_gadget_mode)
            elif (not self.isMinimized()) and getattr(self, '_gadget_active', False):
                QTimer.singleShot(0, self._exit_gadget_mode)

    # ─────────────────────────────────────────────────────────────────────────
    # MINI GADGET  ·  MINIMISE-TO-GADGET
    # ─────────────────────────────────────────────────────────────────────────
    def _ensure_gadget(self):
        """Create the floating gadget once, on the first minimise (not at boot)."""
        g = getattr(self, '_gadget', None)
        if g is None:
            try:
                g = MiniPlayerGadget(self)
            except Exception:
                g = None
            self._gadget = g
            if g is not None:
                try:
                    g.apply_state(dict(getattr(self, '_gadget_state_cache', {}) or {}))
                except Exception:
                    pass
        return g

    def _gadget_state(self):
        g = getattr(self, '_gadget', None)
        if g is not None:
            try:
                return g.state()
            except Exception:
                pass
        return dict(getattr(self, '_gadget_state_cache', {}) or {})

    def _apply_gadget_state(self, d):
        d = dict(d or {})
        self._gadget_state_cache = d
        self.gadget_enabled = bool(d.get('enabled', True))
        self.gadget_hide_taskbar = bool(d.get('hide_taskbar', False))
        # "was in gadget mode when the app last closed" → reopen straight into it
        self._start_in_gadget = bool(d.get('active', False)) and self.gadget_enabled
        g = getattr(self, '_gadget', None)
        if g is not None:
            try:
                g.apply_state(d)
            except Exception:
                pass

    def set_gadget_option(self, key, value):
        """Single entry point for the SettingsWindow gadget controls."""
        st = self._gadget_state()
        st[key] = value
        self._apply_gadget_state(st)
        self._schedule_save_settings()

    # ── appearance modes: ONE switch for the whole axis ──────────────────────
    def set_view_mode(self, mode, remember=True):
        """Switch the app between the full window, the card HUD and the dial HUD.

        Every other path into and out of the gadget (minimise, double-click,
        Escape, the gadget's own ✕) funnels through here too, so the header
        switch and the real window state can never disagree.
        """
        if mode not in ViewModeSwitch.keys():
            return
        if mode == 'full':
            if getattr(self, '_gadget_active', False):
                self._exit_gadget_mode()
            else:
                if self.isMinimized():
                    self.showNormal()
                self.show()
                self.raise_()
                self.activateWindow()
        else:
            g = self._ensure_gadget()
            if g is None:
                return
            if not getattr(self, '_gadget_active', False):
                self._enter_gadget_mode(force=True)
            try:
                g.set_shape('circle' if mode == 'dial' else 'card')
            except Exception:
                pass
            # an explicit switch is a swap, not a minimise: the desk is handed
            # over to the HUD even when the taskbar-hiding option is off
            try:
                self.hide()
                g.show()
                g.raise_()
                g.activateWindow()
            except Exception:
                pass
        self._view_mode = mode
        self._sync_view_switch()
        if remember:
            self._schedule_save_settings()

    def _sync_view_switch(self):
        sw = getattr(self, 'view_switch', None)
        if sw is not None:
            try:
                sw.set_mode(getattr(self, '_view_mode', 'full'))
            except Exception:
                pass

    def _sync_view_mode_from_gadget(self, shape):
        """Called by the gadget whenever its own shape changes (double-click)."""
        self._view_mode = 'dial' if shape == 'circle' else 'card'
        self._sync_view_switch()

    def _install_view_shortcuts(self):
        for seq, mode in (('Ctrl+1', 'full'), ('Ctrl+2', 'card'), ('Ctrl+3', 'dial')):
            try:
                sc = QShortcut(QKeySequence(seq), self)
                sc.activated.connect(lambda m=mode: self.set_view_mode(m))
            except Exception:
                pass

    def _enter_gadget_mode(self, force=False):
        if getattr(self, '_gadget_active', False):
            return
        if not getattr(self, 'gadget_enabled', True) and not force:
            return
        g = self._ensure_gadget()
        if g is None:
            return
        self._gadget_active = True
        self._view_mode = 'dial' if getattr(g, 'shape', 'card') == 'circle' else 'card'
        self._sync_view_switch()
        try:
            self.visualizer.timer.stop()      # one visualizer clock at a time
        except Exception:
            pass
        try:
            sw = getattr(self, 'settings_window', None)
            if sw is not None and sw.isVisible():
                sw.hide()
                self._settings_was_open = True
        except Exception:
            pass
        if getattr(self, 'gadget_hide_taskbar', False):
            self.hide()
        g.refresh_track(force=True)
        g.show()
        g.raise_()
        self._schedule_save_settings()

    def _exit_gadget_mode(self):
        # the gadget needed its settings above it: hand normal stacking back
        # first, before any early return, so the flag can never stick.
        sw = getattr(self, 'settings_window', None)
        if sw is not None and getattr(sw, '_ontop_for_gadget', False):
            try:
                sw._ontop_for_gadget = False
                was_visible = sw.isVisible()
                sw.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
                if was_visible:
                    sw.show()
            except Exception:
                pass
        if not getattr(self, '_gadget_active', False):
            return
        self._gadget_active = False
        g = getattr(self, '_gadget', None)
        if g is not None:
            try:
                g.hide()
            except Exception:
                pass
        try:
            self.visualizer.last_time = time.perf_counter()
            self.visualizer.timer.start(max(4, int(round(self.visualizer.frame_budget_ms))))
        except Exception:
            pass
        try:
            if self.isMinimized():
                self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        if getattr(self, '_settings_was_open', False):
            self._settings_was_open = False
            try:
                sw = getattr(self, 'settings_window', None)
                if sw is not None:
                    sw.show()
            except Exception:
                pass
        self._view_mode = 'full'
        self._sync_view_switch()
        self._schedule_save_settings()

    def _save_persisted_settings(self):
        try:
            # Capture current panel sizes if window is displayed and visible
            if self.isVisible():
                if hasattr(self, 'main_splitter'):
                    m_sizes = self.main_splitter.sizes()
                    if len(m_sizes) == 3 and all(s > 20 for s in m_sizes):
                        self._cached_main_sizes = m_sizes
                if hasattr(self, 'top_row_splitter'):
                    t_sizes = self.top_row_splitter.sizes()
                    if len(t_sizes) == 2 and all(s > 20 for s in t_sizes):
                        self._cached_top_sizes = t_sizes

            # Column widths & visibility
            col_widths = {}
            if hasattr(self, 'playlist_table'):
                for c in range(self.playlist_table.columnCount()):
                    col_widths[str(c)] = self.playlist_table.columnWidth(c)

            geo = {
                'x': self.x(),
                'y': self.y(),
                'w': self.width(),
                'h': self.height(),
                'maximized': self.isMaximized()
            }

            settings_dict = {
                'main_splitter_sizes': self._cached_main_sizes,
                'top_row_splitter_sizes': self._cached_top_sizes,
                'window_geometry': geo,
                'gadget': self._gadget_state(),
                'volume': self.battery_volume.volume if hasattr(self, 'battery_volume') else 70,
                'battery_anim_style': self.battery_volume.anim_style if hasattr(self, 'battery_volume') else 'plasma',
                'theme': self.theme_key,
                'vis_mode': self.visualizer.mode if hasattr(self, 'visualizer') else 'bars',
                'view_mode': getattr(self, '_view_mode', 'full'),
                'active_tab': self.tabs.currentIndex() if hasattr(self, 'tabs') else 0,
                'sort_index': self.sort_combo.currentIndex() if hasattr(self, 'sort_combo') else 0,
                'library_folders': self.library_folders,
                'playlist': self.playlist,
                'visible_columns': {str(k): v for k, v in self.visible_columns.items()},
                'column_widths': col_widths,
                'default_speed': round(self.playback_speed, 2),
                'default_eq': {k: round(v, 1) for k, v in self.eq_values.items()},
                'default_bass_boost': round(self.bass_boost, 1),
                'fx_rack': self._fx_values(),
                'fx_bypass': bool(getattr(self, 'fx_bypass', False)),
                'default_stereo_width': self.stereo_width,
                'repeat_mode': self.repeat_mode,
                'shuffle_enabled': self.shuffle_enabled,
                'current_track': self.current_playing_track,
                'updated_at': time.time()
            }

            # 1. Save directly to app_settings.json
            with open(self._app_settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2)

            # 2. Sync to tui_settings.json
            if self._tui_settings_file.exists():
                try:
                    with open(self._tui_settings_file, 'r', encoding='utf-8') as f:
                        tui_data = json.load(f)
                except Exception:
                    tui_data = {}
                tui_data.update({
                    'volume': float(settings_dict['volume']),
                    'speed': float(settings_dict['default_speed']),
                    'theme': settings_dict['theme'],
                    'vis_mode': settings_dict['vis_mode'],
                    'repeat': settings_dict['repeat_mode'],
                    'shuffle': settings_dict['shuffle_enabled'],
                    'playlist': settings_dict['playlist'],
                    'stereo_width': float(settings_dict['default_stereo_width']),
                    'panel_playlist_w': int(self._cached_main_sizes[2]) if len(self._cached_main_sizes) > 2 else 55
                })
                tui_data.update(settings_dict['default_eq'])
                with open(self._tui_settings_file, 'w', encoding='utf-8') as f:
                    json.dump(tui_data, f, indent=2)

            # 3. Dual-layer QSettings
            self.settings.setValue('library_folders', self.library_folders)
            self.settings.setValue('playlist', self.playlist)
            self.settings.setValue('volume', settings_dict['volume'])
            self.settings.setValue('theme', self.theme_key)
            self.settings.setValue('vis_mode', settings_dict['vis_mode'])
            self.settings.setValue('main_splitter_sizes', self._cached_main_sizes)
            self.settings.setValue('top_row_splitter_sizes', self._cached_top_sizes)
            self.settings.sync()
        except Exception:
            pass

    def _load_persisted_settings(self):
        settings_dict = {}
        if self._app_settings_file.exists():
            try:
                with open(self._app_settings_file, 'r', encoding='utf-8') as f:
                    settings_dict = json.load(f)
            except Exception:
                settings_dict = {}

        if not settings_dict and self._tui_settings_file.exists():
            try:
                with open(self._tui_settings_file, 'r', encoding='utf-8') as f:
                    settings_dict = json.load(f)
            except Exception:
                pass

        # ── Mini Gadget ──
        gd = settings_dict.get('gadget')
        if isinstance(gd, dict):
            self._apply_gadget_state(gd)

        # ── Appearance mode (kept in sync with the header switch) ──
        vm = settings_dict.get('view_mode')
        if vm in ViewModeSwitch.keys():
            # the gadget's own saved shape wins while it is the active surface
            if vm == 'full' or not getattr(self, '_gadget_active', False):
                self._view_mode = vm
        self._sync_view_switch()

        # ── Window Geometry & Position ──
        geo = settings_dict.get('window_geometry')
        if geo and isinstance(geo, dict):
            w = geo.get('w', 1380)
            h = geo.get('h', 920)
            x = geo.get('x')
            y = geo.get('y')
            if w > 400 and h > 300:
                self.resize(w, h)
            if x is not None and y is not None and x > -2000 and y > -2000:
                # Clamp to the current screen: a geometry saved on a larger /
                # disconnected monitor used to reopen the window off-screen,
                # clipping the right-hand panels.
                try:
                    avail = self.screen().availableGeometry() if self.screen() else None
                    if avail is not None:
                        w = min(w, avail.width() - 20)
                        h = min(h, avail.height() - 40)
                        x = max(avail.left(), min(x, avail.right() - w))
                        y = max(avail.top(), min(y, avail.bottom() - h))
                        self.resize(w, h)
                        self.move(x, y)
                    else:
                        self.move(x, y)
                except Exception:
                    self.move(x, y)
            if geo.get('maximized'):
                self.showMaximized()

        # ── Library Folders ──
        saved_folders = settings_dict.get('library_folders') or self.settings.value('library_folders', None)
        if saved_folders and isinstance(saved_folders, list):
            self.library_folders = [f for f in saved_folders if os.path.exists(f)]
        self.folders_summary_lbl.setText(f"{len(self.library_folders)} folders monitored")

        # ── Playlist ──
        saved_playlist = settings_dict.get('playlist') or self.settings.value('playlist', None)
        if saved_playlist and isinstance(saved_playlist, list):
            self.playlist = [os.path.normpath(f) for f in saved_playlist if os.path.exists(f)]
        else:
            self._scan_all_library_folders()

        # ── Volume ──
        vol = settings_dict.get('volume', self.settings.value('volume', 70, type=int))
        self.battery_volume.set_volume(int(vol))
        self.audio_out.setVolume(int(vol) / 100.0)

        # ── Battery Animation Style ──
        if 'battery_anim_style' in settings_dict:
            anim_style = settings_dict.get('battery_anim_style', 'plasma')
            valid_keys = [s[0] for s in self.battery_volume.ANIM_STYLES]
            if anim_style in valid_keys:
                self.battery_volume.set_anim_style(anim_style)

        # ── Theme ──
        th = settings_dict.get('theme') or self.settings.value('theme', 'midnight', type=str)
        if th in THEMES:
            self._set_theme_key(th)

        # ── Visualizer Mode ──
        vm = settings_dict.get('vis_mode') or self.settings.value('vis_mode', 'bars', type=str)
        if vm in ModernVisualizer.MODES:
            self.visualizer.set_mode(vm)
            idx = ModernVisualizer.MODES.index(vm)
            self.vis_mode_combo.setCurrentIndex(idx)

        # ── Speed ──
        if 'default_speed' in settings_dict or 'speed' in settings_dict:
            sp = float(settings_dict.get('default_speed', settings_dict.get('speed', 1.0)))
            self.playback_speed = sp
            self.speed_slider.setValue(int(sp * 100))

        # ── Global Default EQ, Bass Boost, Stereo Width ──
        saved_eq = settings_dict.get('default_eq')
        if saved_eq and isinstance(saved_eq, dict):
            for k, val in saved_eq.items():
                if k in self.eq_sliders:
                    self._eq_set(k, int(val * 10))
        if 'default_bass_boost' in settings_dict:
            self._rack_set('bass', float(settings_dict['default_bass_boost']))
        if isinstance(settings_dict.get('fx_rack'), dict) and getattr(self, 'fx_sliders', None):
            self._apply_fx_values(settings_dict['fx_rack'])
            if settings_dict.get('fx_bypass') and hasattr(self, 'fx_bypass_btn'):
                self.fx_bypass_btn.setChecked(True)
            self._schedule_fx_render(700)
        if 'default_stereo_width' in settings_dict:
            self._rack_set('width', float(settings_dict['default_stereo_width']))

        # ── Shuffle & Repeat ──
        if 'shuffle_enabled' in settings_dict:
            self.shuffle_enabled = bool(settings_dict['shuffle_enabled'])
            self.shuffle_btn.setChecked(self.shuffle_enabled)
        if 'repeat_mode' in settings_dict:
            self.repeat_mode = str(settings_dict['repeat_mode'])
            self._update_repeat_btn()

        # ── Sort Mode ──
        saved_sort = settings_dict.get('sort_index')
        if saved_sort is not None and hasattr(self, 'sort_combo'):
            try:
                s_idx = int(saved_sort)
                if 0 <= s_idx < self.sort_combo.count():
                    self.sort_combo.blockSignals(True)
                    self.sort_combo.setCurrentIndex(s_idx)
                    self.sort_combo.blockSignals(False)
                    if s_idx > 0:
                        self._apply_sort_by_index(s_idx)
            except Exception:
                pass

        # ── Visible Columns ──
        vis_cols = settings_dict.get('visible_columns')
        if vis_cols and isinstance(vis_cols, dict):
            for k_str, is_vis in vis_cols.items():
                try:
                    c_idx = int(k_str)
                    self.visible_columns[c_idx] = bool(is_vis)
                except ValueError:
                    pass

        # ── Column Widths ──
        col_widths = settings_dict.get('column_widths')
        if col_widths and isinstance(col_widths, dict):
            for k_str, w_val in col_widths.items():
                try:
                    c_idx = int(k_str)
                    if c_idx < self.playlist_table.columnCount() and int(w_val) > 10:
                        self.playlist_table.setColumnWidth(c_idx, int(w_val))
                except ValueError:
                    pass

        # ── Active Tab ──
        if 'active_tab' in settings_dict and hasattr(self, 'tabs'):
            t_idx = int(settings_dict['active_tab'])
            if 0 <= t_idx < self.tabs.count():
                self.tabs.setCurrentIndex(t_idx)

        # ── Panel Sizes (Splitters) ──
        main_sizes = settings_dict.get('main_splitter_sizes')
        if main_sizes and isinstance(main_sizes, list) and len(main_sizes) == 3 and all(s > 20 for s in main_sizes):
            self._cached_main_sizes = [int(s) for s in main_sizes]
            self.main_splitter.setSizes(self._cached_main_sizes)

        top_sizes = settings_dict.get('top_row_splitter_sizes')
        if top_sizes and isinstance(top_sizes, list) and len(top_sizes) == 2 and all(s > 20 for s in top_sizes):
            self._cached_top_sizes = [int(s) for s in top_sizes]
            self.top_row_splitter.setSizes(self._cached_top_sizes)

        self._refresh_playlist_table()

        # Re-apply panel sizes once window has displayed (prevents Qt initial layout override)
        QTimer.singleShot(150, self._restore_splitter_positions)

    def closeEvent(self, event):
        if hasattr(self, '_save_timer'):
            self._save_timer.stop()
        g = getattr(self, '_gadget', None)
        if g is not None:
            try:
                g.suppress_restore = True     # quitting the app, not restoring it
                g.close()
            except Exception:
                pass
        if self.current_playing_track:
            self._save_song_profile_for(self.current_playing_track)
        self._save_persisted_settings()
        self._save_song_profiles_to_disk()
        self._save_meta_cache_to_disk()
        self.player.stop()
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('AudioPlayerPro')
    app.setOrganizationName('AudioPlayerPro')
    window = AudioPlayerPro()
    if getattr(window, '_start_in_gadget', False):
        window.showMinimized()      # last session ended in gadget mode
    else:
        window.show()
        _mode = getattr(window, '_view_mode', 'full')
        if _mode in ('card', 'dial'):
            QTimer.singleShot(0, lambda: window.set_view_mode(_mode))
        else:
            window._sync_view_switch()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
