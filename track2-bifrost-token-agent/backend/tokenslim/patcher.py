import re


class Patcher:
    """Applies minimal token diffs (SEARCH/REPLACE blocks or unified diffs) to full code."""

    @staticmethod
    def extract_and_apply_patch(original_code: str, patch_text: str) -> tuple[str, bool, str]:
        """
        Parses search-and-replace blocks and updates the original code.
        Returns: (updated_code, success_bool, status_message)
        """
        # Pattern 1: Aider-style <<<<<<< SEARCH ... ======= ... >>>>>>>
        search_replace_pattern = re.compile(
            r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>>",
            re.DOTALL
        )
        matches = list(search_replace_pattern.finditer(patch_text))

        if matches:
            updated_code = original_code
            applied_count = 0
            for m in matches:
                search_block = m.group(1)
                replace_block = m.group(2)

                # Direct match
                if search_block in updated_code:
                    updated_code = updated_code.replace(search_block, replace_block, 1)
                    applied_count += 1
                else:
                    # Strip trailing whitespaces per line and try fuzzy match
                    clean_search = "\n".join(l.rstrip() for l in search_block.splitlines())
                    clean_orig_lines = [l.rstrip() for l in updated_code.splitlines()]
                    clean_orig = "\n".join(clean_orig_lines)
                    if clean_search in clean_orig:
                        # Find indices and replace
                        updated_code = clean_orig.replace(clean_search, replace_block, 1)
                        applied_count += 1

            if applied_count > 0:
                return updated_code, True, f"Successfully applied {applied_count} search/replace block(s)."
            else:
                return original_code, False, "Search block not found in original code."

        # Pattern 2: Markdown code fence with entire modified snippet or function
        code_fence_match = re.search(r"```(?:python|py|js|ts)?\s*\n(.*?)\n```", patch_text, re.DOTALL)
        if code_fence_match:
            candidate = code_fence_match.group(1).strip()
            # If candidate contains def/class, check if it replaces an existing function
            func_match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", candidate)
            if func_match:
                func_name = func_match.group(1)
                # Find matching function in original code
                orig_func_pattern = re.compile(rf"(def\s+{func_name}\s*\(.*?\n)(?:[ \t]+.*?\n)*", re.MULTILINE)
                if orig_func_pattern.search(original_code):
                    updated_code = orig_func_pattern.sub(candidate + "\n", original_code, count=1)
                    return updated_code, True, f"Replaced target function '{func_name}'."

        # If model returned pure code without markers
        if "def " in patch_text or "class " in patch_text:
            func_match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", patch_text)
            if func_match:
                func_name = func_match.group(1)
                orig_func_pattern = re.compile(rf"(def\s+{func_name}\s*\(.*?\n)(?:[ \t]+.*?\n)*", re.MULTILINE)
                if orig_func_pattern.search(original_code):
                    updated_code = orig_func_pattern.sub(patch_text.strip() + "\n", original_code, count=1)
                    return updated_code, True, f"Replaced target function '{func_name}'."

        return original_code, False, "No valid patch markers found."
