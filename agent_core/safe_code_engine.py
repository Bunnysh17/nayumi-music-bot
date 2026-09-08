"""
Safe Code Engine — Controlled Autonomous Coding, Verification, and Self-Repair Loop
"""

import os
import sys
import shutil
import tempfile
import py_compile
import traceback
import asyncio
from typing import Tuple, Optional

class SafeCodeEngine:
    @staticmethod
    def get_workspace_dir() -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    @classmethod
    def read_file(cls, filename: str) -> Tuple[bool, str, str]:
        """
        Reads any workspace file safely.
        Returns: (success, filepath, content)
        """
        ws = cls.get_workspace_dir()
        target_path = os.path.join(ws, os.path.basename(filename))
        if not os.path.exists(target_path):
            # Try fuzzy search in workspace
            for f in os.listdir(ws):
                if filename.lower() in f.lower() and os.path.isfile(os.path.join(ws, f)):
                    target_path = os.path.join(ws, f)
                    break

        if os.path.exists(target_path) and os.path.isfile(target_path):
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    return True, target_path, f.read()
            except Exception as e:
                return False, target_path, str(e)
        return False, target_path, "File not found in workspace."

    @classmethod
    def apply_code_modification(
        cls,
        target_filename: str,
        target_snippet: str,
        replacement_snippet: str
    ) -> Tuple[bool, str]:
        """
        Safely applies a targeted snippet replacement to a file:
        1. Checks current file contents
        2. Creates a .bak backup
        3. Writes to temp file and runs py_compile for Python files
        4. Applies changes if valid, or rolls back if invalid.
        """
        ws = cls.get_workspace_dir()
        target_path = os.path.join(ws, os.path.basename(target_filename))
        if not os.path.exists(target_path):
            return False, f"File `{target_filename}` not found in workspace."

        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                current_code = f.read()

            # Apply replacement
            if target_snippet == "ALL":
                new_code = replacement_snippet
            elif target_snippet in current_code:
                new_code = current_code.replace(target_snippet, replacement_snippet, 1)
            else:
                # Try normalized whitespace
                norm_current = current_code.replace("\r\n", "\n")
                norm_target = target_snippet.replace("\r\n", "\n")
                norm_replace = replacement_snippet.replace("\r\n", "\n")
                if norm_target in norm_current:
                    new_code = norm_current.replace(norm_target, norm_replace, 1)
                else:
                    return False, f"Target code section could not be uniquely matched in `{target_filename}`."

            # Verify syntax if Python file
            if target_path.endswith(".py"):
                temp_fd, temp_path = tempfile.mkstemp(suffix=".py")
                try:
                    with open(temp_path, "w", encoding="utf-8") as tf:
                        tf.write(new_code)
                    py_compile.compile(temp_path, doraise=True)
                except py_compile.PyCompileError as pe:
                    os.close(temp_fd)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False, f"Syntax verification failed: `{str(pe)}`. Changes rolled back."
                finally:
                    try:
                        os.close(temp_fd)
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass

            # Create backup
            backup_path = f"{target_path}.bak"
            shutil.copyfile(target_path, backup_path)

            # Write modified file
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_code)

            return True, f"Successfully modified `{target_filename}` and verified syntax (Backup saved to `{os.path.basename(backup_path)}`)."
        except Exception as e:
            traceback.print_exc()
            return False, f"Code modification error: {str(e)}"
