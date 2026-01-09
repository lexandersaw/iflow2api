"""打包脚本 - 使用 PyInstaller 打包为 exe"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    """打包应用"""
    print("=" * 50)
    print("  iflow2api 打包脚本")
    print("=" * 50)
    print()

    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"[OK] PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[错误] PyInstaller 未安装")
        print("请运行: pip install pyinstaller")
        sys.exit(1)

    # 检查 flet
    try:
        import flet
        print(f"[OK] Flet 版本: {flet.__version__}")
    except ImportError:
        print("[错误] Flet 未安装")
        print("请运行: pip install flet")
        sys.exit(1)

    # 项目路径
    project_dir = Path(__file__).parent
    src_dir = project_dir / "src" / "iflow2api"
    dist_dir = project_dir / "dist"
    build_dir = project_dir / "build"

    # 清理旧的构建
    if dist_dir.exists():
        print("[清理] 删除旧的 dist 目录...")
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        print("[清理] 删除旧的 build 目录...")
        shutil.rmtree(build_dir)

    # 使用 flet pack 命令打包
    print()
    print("[打包] 使用 flet pack 打包...")
    print()

    # 创建入口脚本
    entry_script = project_dir / "gui_entry.py"
    entry_script.write_text('''"""GUI 入口脚本"""
import flet as ft
from iflow2api.gui import main

if __name__ == "__main__":
    ft.app(target=main)
''', encoding="utf-8")

    try:
        # 使用 flet pack
        cmd = [
            sys.executable, "-m", "flet", "pack",
            str(entry_script),
            "--name", "iflow2api",
            "--add-data", f"{src_dir};iflow2api",
        ]

        print(f"[命令] {' '.join(cmd)}")
        print()

        result = subprocess.run(cmd, cwd=project_dir)

        if result.returncode == 0:
            print()
            print("=" * 50)
            print("  打包完成!")
            print("=" * 50)
            print()
            print(f"输出目录: {dist_dir}")

            # 列出生成的文件
            if dist_dir.exists():
                for f in dist_dir.iterdir():
                    size = f.stat().st_size / (1024 * 1024)
                    print(f"  - {f.name} ({size:.1f} MB)")
        else:
            print()
            print("[错误] 打包失败")
            sys.exit(1)

    finally:
        # 清理入口脚本
        if entry_script.exists():
            entry_script.unlink()


def build_pyinstaller():
    """使用 PyInstaller 直接打包（备选方案）"""
    print("=" * 50)
    print("  iflow2api PyInstaller 打包")
    print("=" * 50)
    print()

    project_dir = Path(__file__).parent
    src_dir = project_dir / "src" / "iflow2api"

    # 创建入口脚本
    entry_script = project_dir / "gui_entry.py"
    entry_script.write_text('''"""GUI 入口脚本"""
import flet as ft
from iflow2api.gui import main

if __name__ == "__main__":
    ft.app(target=main)
''', encoding="utf-8")

    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name", "iflow2api",
            "--onefile",
            "--windowed",
            "--add-data", f"{src_dir};iflow2api",
            "--hidden-import", "iflow2api",
            "--hidden-import", "iflow2api.gui",
            "--hidden-import", "iflow2api.app",
            "--hidden-import", "iflow2api.config",
            "--hidden-import", "iflow2api.proxy",
            "--hidden-import", "iflow2api.server",
            "--hidden-import", "iflow2api.settings",
            "--collect-all", "flet",
            "--collect-all", "flet_core",
            "--collect-all", "flet_runtime",
            str(entry_script),
        ]

        print(f"[命令] 运行 PyInstaller...")
        print()

        result = subprocess.run(cmd, cwd=project_dir)

        if result.returncode == 0:
            print()
            print("打包完成! 输出: dist/iflow2api.exe")
        else:
            print("[错误] 打包失败")
            sys.exit(1)

    finally:
        if entry_script.exists():
            entry_script.unlink()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="iflow2api 打包脚本")
    parser.add_argument(
        "--method",
        choices=["flet", "pyinstaller"],
        default="flet",
        help="打包方法: flet (推荐) 或 pyinstaller",
    )

    args = parser.parse_args()

    if args.method == "flet":
        build()
    else:
        build_pyinstaller()
