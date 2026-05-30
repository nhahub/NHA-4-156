import os
from ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline(init_global_settings=True)
index = pipeline.run(
    repo_url_or_path="https://github.com/Heba2627/depi_final_project_testing",
    repo_id="testing1"
)
