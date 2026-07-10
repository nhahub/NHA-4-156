import shutil
import subprocess
import time
from pathlib import Path
import stat
import re
from urllib.parse import urlparse

from ingestion.exceptions import IngestionCancelled

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

# How often (seconds) to poll a running git subprocess for a stop request.
GIT_POLL_INTERVAL = 0.3


def force_rmtree(path: Path):
    if not path.exists():
        return
    for file in path.rglob("*"):
        if file.is_file():
            try:
                file.chmod(stat.S_IWRITE)
            except Exception:
                pass
    shutil.rmtree(path)


class RepositoryPreprocessor:
    def __init__(self, output_folder: str = "data/processed"):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def prepare(self, repo_url_or_path: str, stop_event=None) -> tuple[str, bool]:
        repo_path = Path(repo_url_or_path)
        if repo_path.exists():
            return self._prepare_local(repo_path, stop_event=stop_event)
        else:
            return self._prepare_remote(repo_url_or_path, stop_event=stop_event)

    @staticmethod
    def generate_repo_id(url: str) -> str:
        path = urlparse(url).path.strip('/')
        parts = path.split('/')
        if len(parts) >= 2:
            repo = parts[1].replace('.git', '')
            return f"{parts[0]}__{repo}".lower().replace('-', '_')
        return re.sub(r'[^a-zA-Z0-9]', '_', path.replace('.git', '')).lower()

    def _authenticated_url(self, url: str) -> str:
        """Inject GITHUB_TOKEN into the clone URL so private repos work too."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if token and url.startswith("https://github.com/"):
            return url.replace("https://github.com/", f"https://{token}@github.com/")
        return url

    def _run_git_cancelable(self, cmd: list[str], stop_event=None, timeout: float | None = None, cwd=None) -> subprocess.CompletedProcess:
        """Run a git command in a subprocess, polling so it can be killed if
        stop_event gets set mid-run. Raises IngestionCancelled if stopped,
        or subprocess.CalledProcessError / subprocess.TimeoutExpired to match
        the behavior callers previously got from subprocess.run(check=True)."""
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        start = time.monotonic()

        while True:
            try:
                stdout, stderr = process.communicate(timeout=GIT_POLL_INTERVAL)
                break
            except subprocess.TimeoutExpired:
                if stop_event is not None and stop_event.is_set():
                    process.kill()
                    process.communicate()
                    raise IngestionCancelled()
                if timeout is not None and (time.monotonic() - start) > timeout:
                    process.kill()
                    process.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                # neither cancelled nor timed out yet, keep polling
                continue

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)

        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

    def _prepare_remote(self, url: str, stop_event=None) -> tuple[str, bool]:
        repo_name = self.generate_repo_id(url)
        raw_dest = Path("data/raw") / repo_name
        proc_dest = self.output_folder / repo_name
        raw_dest.parent.mkdir(parents=True, exist_ok=True)

        auth_url = self._authenticated_url(url)

        if stop_event is not None and stop_event.is_set():
            raise IngestionCancelled()

        if not raw_dest.exists():
            print(f"Cloning '{url}'")
            try:
                self._run_git_cancelable(
                    ["git", "clone", auth_url, str(raw_dest)],
                    stop_event=stop_event,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or "").lower()
                if "repository not found" in stderr or "could not read username" in stderr or "authentication failed" in stderr:
                    raise RuntimeError(
                        "This repository is private or does not exist. "
                        "If it's a private repo you have access to, make sure GITHUB_TOKEN "
                        "in your .env has 'repo' scope and belongs to an account that's a "
                        "collaborator on it."
                    )
                raise RuntimeError(f"Failed to clone '{url}': {e.stderr or 'unknown git error'}")
            self._sync_processed(raw_dest, proc_dest, stop_event=stop_event)
            return str(proc_dest), True

        # mawgoda
        remote_hash = self._get_remote_head(auth_url)
        local_hash = self._get_local_head(raw_dest)

        if remote_hash and local_hash and remote_hash == local_hash:
            print(f"No updates for '{url}'. Reusing existing processed data.")
            return str(proc_dest), False  # nothing changed

        if stop_event is not None and stop_event.is_set():
            raise IngestionCancelled()

        # changed
        print(f"Updates detected for '{url}'. Pulling latest changes.")
        self._run_git_cancelable(["git", "-C", str(raw_dest), "pull"], stop_event=stop_event)
        self._sync_processed(raw_dest, proc_dest, stop_event=stop_event)
        return str(proc_dest), True  # must re-embed

    def _prepare_local(self, path: Path, stop_event=None) -> tuple[str, bool]:
        dest = self.output_folder / path.name
        if not dest.exists():
            print(f"Processing local repo at '{path}'")
            self._sync_processed(path, dest, stop_event=stop_event)
            return str(dest), True

        local_hash = self._get_local_head(path)
        snapshot_hash = self._read_snapshot_hash(dest)
        if local_hash and snapshot_hash and local_hash == snapshot_hash:
            return str(dest), False

        if stop_event is not None and stop_event.is_set():
            raise IngestionCancelled()

        print(f"Processing updates for local repo at '{path}'")
        self._sync_processed(path, dest, stop_event=stop_event)
        return str(dest), True

    def _sync_processed(self, src: Path, dest: Path, stop_event=None):
        if stop_event is not None and stop_event.is_set():
            raise IngestionCancelled()

        if dest.exists():
            self._force_rmtree(dest)
        shutil.copytree(src, dest)
        self._clean(dest)
        # persist the commit hash so future runs can compare
        local_hash = self._get_local_head(src)
        if local_hash:
            self._write_snapshot_hash(dest, local_hash)

    def _clean(self, folder: Path):
        git_dir = folder / ".git"
        if git_dir.exists():
            self._force_rmtree(git_dir)

        for item in list(folder.rglob("*")):
            if item.is_dir() and any(skip in item.parts for skip in SKIP_DIRS):
                if item.exists():
                    self._force_rmtree(item)

        for item in folder.rglob("*"):
            if item.is_file() and item.suffix not in SUPPORTED_EXTENSIONS:
                item.unlink(missing_ok=True)

    @staticmethod
    def _get_remote_head(url: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "ls-remote", url, "HEAD"],
                capture_output=True, text=True, timeout=15
            )
            line = result.stdout.strip()
            return line.split()[0] if line else None
        except Exception as e:
            print(f"Could not fetch remote HEAD: {e}")
            return None

    @staticmethod
    def _get_local_head(repo_path: Path) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                capture_output=True, text=True
            )
            h = result.stdout.strip()
            return h if h else None
        except Exception:
            return None

    @staticmethod
    def _snapshot_file(processed_path: Path) -> Path:
        return processed_path / ".repo_snapshot_hash"

    def _write_snapshot_hash(self, processed_path: Path, commit_hash: str):
        self._snapshot_file(processed_path).write_text(commit_hash)

    def _read_snapshot_hash(self, processed_path: Path) -> str | None:
        f = self._snapshot_file(processed_path)
        return f.read_text().strip() if f.exists() else None

    def _force_rmtree(self, path: Path):
        force_rmtree(path)