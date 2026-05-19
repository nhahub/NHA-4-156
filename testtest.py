import os
from ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline()
index = pipeline.run("https://github.com/Heba2627/SudokuGame")

print("Indexing complete.")
# print(index)
# for i, node in enumerate(index.nodes[:3]):
#     print(f"\n--- Node {i+1} ---")
#     print(f"File:{node.metadata.get('file_name')}")
#     print(f"Content:\n{node.get_content()[:300]}")  