import shutil
import subprocess
from pathlib import Path
import stat

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".vscode", ".idea", "target", "out", "bin", "obj"}
SUPPORTED_EXTENSIONS = {
    # code
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cpp", ".c", ".h", ".cs",
    ".go", ".rs", ".rb", ".php", ".swift",
    ".kt", ".kts", ".scala", ".lua", ".sql",
    ".vue", ".graphql", ".gql", ".r",
    # text / config
    ".md", ".txt", ".json", ".yml", ".yaml",
    ".toml", ".rst", ".env",
    ".html", ".css", ".xml", ".sh", ".bash", ".zsh",
}

class RepositoryPreprocessor:
    def __init__(self, output_folder: str = "data/processed"):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def prepare(self, repo_url_or_path: str) -> str:
        repo_path = Path(repo_url_or_path)
        if repo_path.exists():
            return self._copy_repo(repo_path)
        else:
            return self._clone_repo(repo_url_or_path)

    def _clone_repo(self, url: str) -> str:
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        dest = self.output_folder / repo_name
        if dest.exists():
            self._force_rmtree(dest)
        subprocess.run(["git", "clone", url, str(dest)], check=True)
        self._clean(dest)
        return str(dest)

    def _copy_repo(self, path: Path) -> str:
        dest = self.output_folder / path.name
        if dest.exists():
            self._force_rmtree(dest)
        shutil.copytree(path, dest)
        self._clean(dest)
        return str(dest)

    def _clean(self, folder: Path):
        git_dir = folder / ".git"
        if git_dir.exists():
            self._force_rmtree(git_dir)

        for item in folder.rglob("*"):
            if item.is_dir() and any(skip in item.parts for skip in SKIP_DIRS):
                if item.exists():
                    self._force_rmtree(item)

        for item in folder.rglob("*"):
            if item.is_file() and item.suffix not in SUPPORTED_EXTENSIONS:
                item.unlink()

    def _force_rmtree(self, path: Path):
        for file in path.rglob("*"):
            if file.is_file():
                file.chmod(stat.S_IWRITE)
        shutil.rmtree(path)