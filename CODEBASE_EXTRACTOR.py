#!/usr/bin/env python3
"""
Script to generate a codebase tree representation and collect code files.

Usage:
    python CODEBASE_EXTRACT.py <directory>

The script will:
1. Traverse the provided directory and subdirectories.
2. Ignore certain folders (e.g. __pycache__, node_modules, venv, .venv, etc.)
   and files (e.g. package-lock.json, yarn.lock, or files with extensions like .csv, .db, .parquet)
   that are typically not part of the codebase.
3. Skip any file larger than 300 KB.
4. Generate a tree diagram of the directory structure.
5. Create an output file called "output.md" in the provided directory that contains:
   - The tree diagram (wrapped in triple backticks)
   - The contents of each accepted code file (each with its own header and wrapped in triple backticks)
"""

import os
import sys

# Define sets of directories and files to ignore.
IGNORED_DIRS = {"__pycache__", "node_modules", "venv", ".venv", "data", "dist", "build", ".git", "workspace"}
IGNORED_FILES = {"package-lock.json", "yarn.lock", "requirements.txt"}  # adjust as needed

# Define file extensions that are considered non-code (commonly data or binary files)
IGNORED_EXTENSIONS = {".csv", ".db", ".parquet", ".sqlite", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".zip", ".tar", ".gz"}

# Maximum file size to include (in bytes)
MAX_FILE_SIZE = 300 * 1024  # 300 KB

def should_ignore_dir(dirname):
    """
    Returns True if the directory name should be ignored.
    """
    return dirname in IGNORED_DIRS

def should_ignore_file(filename, filepath):
    """
    Returns True if the file should be ignored based on name, extension, or file size.
    """
    base = os.path.basename(filename)
    if base in IGNORED_FILES:
        return True

    # Ignore by file extension.
    ext = os.path.splitext(filename)[1].lower()
    if ext in IGNORED_EXTENSIONS:
        return True

    # Check file size. If file size cannot be determined, assume it is acceptable.
    try:
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            return True
    except Exception as e:
        # In case of error, simply do not ignore the file based on size.
        pass

    return False

def generate_tree(start_path):
    """
    Recursively generate a tree representation of the directory structure starting at start_path.
    
    Returns:
        tree_str: A string with the tree diagram.
        code_files: A list of file paths that have been accepted (not ignored).
    """
    tree_lines = []
    code_files = []

    def inner(current_path, prefix=""):
        try:
            items = sorted(os.listdir(current_path))
        except Exception as e:
            # Skip directories that cannot be accessed.
            return

        # Filter out items that need to be ignored if they are directories.
        filtered_items = []
        for item in items:
            item_path = os.path.join(current_path, item)
            if os.path.isdir(item_path) and should_ignore_dir(item):
                continue
            filtered_items.append(item)

        for index, item in enumerate(filtered_items):
            item_path = os.path.join(current_path, item)
            connector = "├── "
            if index == len(filtered_items) - 1:
                connector = "└── "

            if os.path.isdir(item_path):
                tree_lines.append(prefix + connector + item + "/")
                new_prefix = prefix + ("    " if index == len(filtered_items) - 1 else "│   ")
                inner(item_path, new_prefix)
            else:
                if should_ignore_file(item, item_path):
                    continue
                tree_lines.append(prefix + connector + item)
                code_files.append(item_path)

    root = os.path.abspath(start_path)
    tree_lines.append(root)
    inner(start_path)
    tree_str = "\n".join(tree_lines)
    return tree_str, code_files

def main():
    if len(sys.argv) < 2:
        print("Usage: python CODEBASE_EXTRACT.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print("Error: The provided path is not a directory.")
        sys.exit(1)
    
    tree_diagram, code_files = generate_tree(directory)
    
    output_content = []
    output_content.append("# CODEBASE\n")
    output_content.append("## Directory Tree:\n")
    output_content.append("### " + os.path.abspath(directory) + "\n")
    output_content.append("```\n" + tree_diagram + "\n```\n")
    output_content.append("## Code Files\n")
    
    for file_path in code_files:
        rel_path = os.path.relpath(file_path, directory)
        full_path = os.path.join(os.path.abspath(directory), rel_path)
        output_content.append("\n### " + full_path + "\n")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        except Exception as e:
            code = "Error reading file: " + str(e)
        output_content.append("```\n" + code + "\n```\n")
    
    output_file_path = os.path.join(directory, "output.md")
    try:
        with open(output_file_path, "w", encoding="utf-8") as out_file:
            out_file.write("\n".join(output_content))
        print("Output successfully saved to:", output_file_path)
    except Exception as e:
        print("Failed to write output file:", str(e))

if __name__ == "__main__":
    main()
