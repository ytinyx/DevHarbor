"""Keep unit tests independent of developer credentials and running services."""

import os


# Apply before test collection imports the application's singleton settings.
# Individual tests can opt into mocked services with monkeypatch.
os.environ.update(
    {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "MILVUS_ENABLED": "false",
        "AUTO_SYNC_ENABLED": "false",
        "EMBEDDING_PROVIDER": "deterministic",
        "EMBEDDING_MODEL": "deterministic-test",
        "EMBEDDING_DIMENSIONS": "128",
        "RAG_LLM_ENABLED": "false",
        "RAGAS_ENABLED": "false",
        "LLM_API_KEY": "",
        "GITHUB_TOKEN": "",
        "RAGAS_JUDGE_API_KEY": "",
        "EMBEDDING_API_KEY": "",
        "DASHSCOPE_API_KEY": "",
        "RERANK_API_KEY": "",
        "FEISHU_FEEDBACK_WEBHOOK_URL": "",
        "OPENAI_API_KEY": "",
        "LANGSMITH_API_KEY": "",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "RAGAS_DO_NOT_TRACK": "true",
    }
)
