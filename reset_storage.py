import os
import shutil
import sys

PATHS_TO_DELETE = [
    "repo_illustrator.db",
    "data",
    "chroma_db"
]

def reset_storage():
    print("WARNING: You are about to permanently delete all persistent storage.")
    print("This includes the SQLite database, cloned repositories, and ChromaDB vector embeddings.")
    print("\nThe following paths will be wiped:")
    for path in PATHS_TO_DELETE:
        abspath = os.path.abspath(path)
        print(f" - {path} ({abspath})")
    
    # Prompt for explicit confirmation
    confirmation = input("\nAre you absolutely sure you want to proceed? Type 'yes' to confirm: ")
    
    if confirmation.strip().lower() != 'yes':
        print("\nReset cancelled. No files were deleted.")
        sys.exit(0)
        
    print("\nResetting storage...")
    
    for path in PATHS_TO_DELETE:
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"[DELETED] Directory: {path}")
                else:
                    os.remove(path)
                    print(f"[DELETED] File: {path}")
            except Exception as e:
                print(f"[ERROR] Failed to delete {path}: {e}")
        else:
            print(f"[SKIPPED] {path} (does not exist)")
            
    print("\nStorage reset successfully! You have a clean slate.")

if __name__ == "__main__":
    reset_storage()