# Repo-Illustrator

## Running the API

Start the FastAPI server using Uvicorn. To prevent the server from restarting and reloading the heavy embeddings model when ingestion saves files locally, use the `--reload-exclude` flags:

```bash
uvicorn api.main:app --reload --reload-exclude "data/*" --reload-exclude "chroma_db/*"
```

(Note: You can omit the `--reload` flags entirely for production).

## Troubleshooting & Known Issues

### 1. `TypeError: source : bytes object is not an instance of str` (CodeSplitter / tree-sitter version conflict)
LlamaIndex's `CodeSplitter` has a known incompatibility with certain versions of `tree-sitter` 
related to a `bytes`/`str` API change introduced in `0.21+`. If you encounter:

    TypeError: argument 'source': 'bytes' object is not an instance of 'str'

This is a tree-sitter version mismatch. Resolution depends on your environment — 
pinning `tree-sitter==0.20.4` with individual language packages works in some setups. 
If that fails, check the installed version of `llama-index-core` and match the 
tree-sitter version it expects. Do not fix what's not broken :))
