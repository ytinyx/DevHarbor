# -*- mode: python ; coding: utf-8 -*-
"""Freeze the private desktop sidecar; never collect workspace data or .env."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_delvewheel_libs_directory, copy_metadata


backend_root = Path(SPECPATH).resolve()
project_root = backend_root.parent

# Explicit application resources only. Python code is analyzed from desktop.py.
datas = [
    (str(backend_root / "app" / "skills"), "app/skills"),
    (str(project_root / "docs" / "examples" / "evals"), "docs/examples/evals"),
]
for package in ("langchain_core", "langchain_openai", "langgraph", "langgraph_sdk", "tiktoken"):
    datas += collect_data_files(package, includes=["**/*.json", "**/*.tiktoken", "**/*.yaml"])
for distribution in (
    "langchain-core", "langchain-openai", "langgraph", "langgraph-checkpoint",
    "langgraph-prebuilt", "langgraph-sdk", "langsmith", "openai", "psycopg", "tiktoken",
):
    datas += copy_metadata(distribution)

# The Windows psycopg-binary wheel keeps libpq and its DLLs beside the package.
datas, binaries = collect_delvewheel_libs_directory("psycopg_binary", datas=datas)

hiddenimports = [
    "app.main", "app.mcp.memory_server", "uvicorn.lifespan.on",
    "uvicorn.protocols.http.h11_impl", "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql.psycopg", "psycopg", "psycopg_binary",
    "psycopg_binary.pq", "psycopg_binary._psycopg", "tiktoken_ext.openai_public",
]

# Desktop PostgreSQL uses psycopg and SQL calls to the server's pgvector extension.
# Milvus, local neural models, and the evaluation stack stay outside the installer.
excludes = [
    "torch", "torchvision", "torchaudio", "tensorflow", "keras", "jax", "jaxlib",
    "sentence_transformers", "transformers", "datasets", "pyarrow", "ragas",
    "pymilvus", "milvus_lite", "psycopg2", "pgvector",
    "matplotlib", "IPython", "notebook", "pytest", "scipy", "sklearn",
]

a = Analysis(
    [str(backend_root / "desktop.py")], pathex=[str(backend_root)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=excludes, noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="devharbor-core",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="devharbor-core")
