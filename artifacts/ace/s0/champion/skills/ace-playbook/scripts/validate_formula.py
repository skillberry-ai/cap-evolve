def check_formula(f):
    """Validate an Excel formula string for quote parity and paren balance.
    Returns (True, 'ok') or (False, reason)."""
    if not isinstance(f, str) or not f.startswith('='):
        return False, 'formula must be a string starting with ='
    depth = 0
    in_str = False
    i = 0
    while i < len(f):
        ch = f[i]
        if in_str:
            if ch == '"':
                if i + 1 < len(f) and f[i+1] == '"':
                    i += 2
                    continue
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth < 0:
                    return False, 'unbalanced ) at index %d' % i
        i += 1
    if in_str:
        return False, 'unterminated string literal'
    if depth != 0:
        return False, 'unbalanced parentheses (depth=%d)' % depth
    if f.rstrip(')').endswith('"\'') or '\"\'' in f:
        return False, 'suspicious quote sequence (possible corrupted empty-string fallback)'
    return True, 'ok'
