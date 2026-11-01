import ast
import re


class ASTPruner:
    """Intelligently prunes code to minimize tokens while preserving semantic context."""

    @staticmethod
    def identify_target_symbol(code: str, prompt: str) -> str:
        """Find the most likely function or class name mentioned in the prompt."""
        # Extract function definitions first
        func_names = re.findall(r"def\s+([a-zA-Z0-9_]+)", code)
        class_names = re.findall(r"class\s+([a-zA-Z0-9_]+)", code)
        
        prompt_lower = prompt.lower()
        
        # Priority 1: Exact function name mention in prompt
        for fn in func_names:
            if re.search(rf"\b{re.escape(fn.lower())}\b", prompt_lower):
                return fn
                
        # Priority 2: Function name fuzzy/partial overlap
        words = set(re.findall(r"\w+", prompt_lower))
        best_func = None
        best_overlap = 0
        for fn in func_names:
            parts = set(fn.lower().split("_"))
            overlap = len(words.intersection(parts))
            if overlap > best_overlap:
                best_overlap = overlap
                best_func = fn

        if best_func and best_overlap > 0:
            return best_func

        # Priority 3: Class name mention
        for cl in class_names:
            if re.search(rf"\b{re.escape(cl.lower())}\b", prompt_lower):
                return cl

        return func_names[0] if func_names else (class_names[0] if class_names else "")

    @staticmethod
    def skeletonize_python(code: str, target_symbol: str = "") -> tuple[str, dict]:
        """Prunes Python code by keeping signatures/docstrings and eliding non-target bodies."""
        try:
            tree = ast.parse(code)
        except Exception:
            return ASTPruner.skeletonize_generic(code, target_symbol)

        lines = code.splitlines(keepends=True)
        elided_nodes = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                self._handle_func(node)

            def visit_AsyncFunctionDef(self, node):
                self._handle_func(node)

            def _handle_func(self, node):
                # If this function is the target, DO NOT elide its body!
                if target_symbol and node.name == target_symbol:
                    return

                if len(node.body) > 1 or (len(node.body) == 1 and not isinstance(node.body[0], ast.Pass)):
                    docstring = ast.get_docstring(node)
                    start_body_line = node.body[0].lineno - 1
                    end_body_line = node.end_lineno - 1

                    if docstring and len(node.body) > 1:
                        start_body_line = node.body[1].lineno - 1

                    if start_body_line <= end_body_line:
                        body_indent = " " * (node.body[0].col_offset)
                        elided_nodes.append((start_body_line, end_body_line, f"{body_indent}... # [body elided to save tokens]\n"))

        visitor = Visitor()
        visitor.visit(tree)

        # Sort in reverse line order to apply replacements cleanly
        elided_nodes.sort(key=lambda x: x[0], reverse=True)
        new_lines = list(lines)
        pruned_count = len(elided_nodes)

        for start, end, placeholder in elided_nodes:
            new_lines[start : end + 1] = [placeholder]

        skeleton = "".join(new_lines)
        stats = {
            "target_symbol": target_symbol,
            "elided_functions_count": pruned_count,
            "original_lines": len(lines),
            "pruned_lines": len(skeleton.splitlines()),
        }
        return skeleton, stats

    @staticmethod
    def skeletonize_generic(code: str, target_symbol: str = "") -> tuple[str, dict]:
        """Generic fallback for JS/TS/Go or unparseable code."""
        lines = code.splitlines()
        pruned_lines = []
        inside_function = False
        elided_count = 0

        for line in lines:
            stripped = line.strip()
            sym_match = re.search(r"\b(def|function|class|func)\s+([a-zA-Z0-9_]+)", stripped)
            if sym_match:
                sym = sym_match.group(2)
                if target_symbol and sym == target_symbol:
                    inside_function = False
                    pruned_lines.append(line)
                    continue
                else:
                    inside_function = True
                    pruned_lines.append(line)
                    indent = len(line) - len(stripped) + 4
                    pruned_lines.append(" " * indent + "... // [body elided to save tokens]")
                    elided_count += 1
                    continue

            if inside_function:
                if stripped.startswith("}") or (len(line) - len(stripped) == 0 and stripped):
                    inside_function = False
                    pruned_lines.append(line)
            else:
                pruned_lines.append(line)

        skeleton = "\n".join(pruned_lines)
        stats = {
            "target_symbol": target_symbol,
            "elided_functions_count": elided_count,
            "original_lines": len(lines),
            "pruned_lines": len(pruned_lines),
        }
        return skeleton, stats
