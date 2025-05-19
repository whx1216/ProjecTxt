# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('frontend', 'frontend'),  # 包含整个前端文件夹
        ('history.json', '.'),     # 包含历史记录文件
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,       # 包含二进制文件
    a.datas,          # 包含数据文件
    [],
    name='ProjectTxt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,    # 如需调试可改为True
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,        # 可以指定应用程序图标
)

# 如果在Mac平台上需要创建.app，则保留以下代码
# 对于单文件模式，通常不需要这一部分
'''
app = BUNDLE(
    exe,
    name='ProjectTxt.app',
    icon=None,
    bundle_identifier=None,
)
'''