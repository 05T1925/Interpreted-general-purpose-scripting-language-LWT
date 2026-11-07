"""Static language features for LWT documents; this module never executes LWT."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import ast_nodes as ast
from .analyzer import Diagnostic as StaticDiagnostic
from .analyzer import analyze_module_graph
from .builtin_signatures import BUILTIN_ARITIES
from .errors import LwtError, SourceLocation
from .lexer import Token, TokenKind, scan
from .lsp_documents import (
    TextDocument,
    file_uri,
    make_range,
    normalized_source_lines,
    path_key,
    path_from_file_uri,
    source_position,
    utf16_character_to_codepoint,
)
from .modules import ModuleGraph, ModuleUnit, load_module_graph, resolve_module_call


SYMBOL_KIND = {
    "module": 2,
    "function": 12,
    "variable": 13,
    "field": 8,
    "record": 23,
}

KEYWORD_HOVER = {
    "record": "LWT record type declaration.",
    "fn": "LWT function declaration.",
    "let": "Declare a block scoped variable.",
    "when": "Conditional statement; the condition must be boolean.",
    "otherwise": "Alternative branch of a when statement.",
    "while": "Repeat a block while its boolean condition is true.",
    "each": "Iterate over the entry-time shallow snapshot of an array.",
    "in": "Separates an each loop variable from its array expression.",
    "return": "Return from the current LWT function.",
    "emit": "Write the string conversion of a value and a newline.",
    "true": "Boolean literal true.",
    "false": "Boolean literal false.",
    "null": "The LWT null value.",
    "and": "Boolean conjunction with short-circuit evaluation.",
    "or": "Boolean disjunction with short-circuit evaluation.",
    "not": "Boolean negation.",
    "break": "Exit the nearest while or each loop.",
    "continue": "Continue the nearest while or each loop.",
    "import": "Statically import a function library module.",
    "attempt": "Run a block and recover a RuntimeError with the following handler.",
    "recover": "Handle a RuntimeError caught by the preceding attempt.",
}

BUILTIN_HOVER = {
    "input": "built-in input() -> string | null",
    "args": "built-in args() -> array of program argument strings",
    "read_text": "built-in read_text(path) -> string",
    "len": "built-in len(string_or_array) -> integer",
    "split": "built-in split(text, separator) -> array of strings",
    "trim": "built-in trim(text) -> string",
    "to_int": "built-in to_int(text) -> integer | null",
    "str": "built-in str(value) -> string",
    "push": "built-in push(array, value) -> null",
    "fail": "built-in fail(message) -> never; raises RuntimeError",
}


@dataclass(frozen=True, slots=True)
class Definition:
    path: Path
    line: int
    column: int
    length: int


@dataclass(slots=True)
class Symbol:
    name: str
    kind: int
    definition: Definition
    hover: str
    detail: str = ""
    children: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class DocumentFeatures:
    path: Path
    text: str
    tokens: list[Token]
    symbols: list[dict[str, object]]
    hovers: dict[tuple[int, int], str]
    definitions: dict[tuple[int, int], Definition]


@dataclass(slots=True)
class _Scope:
    parent: _Scope | None
    definitions: dict[str, Definition] = field(default_factory=dict)

    def resolve(self, name: str, *, hidden_here: str | None = None) -> Definition | None:
        scope: _Scope | None = self
        first = True
        while scope is not None:
            if name in scope.definitions and not (first and hidden_here == name):
                return scope.definitions[name]
            first = False
            scope = scope.parent
        return None


def _identifier_range(definition: Definition, text: str) -> dict[str, dict[str, int]]:
    return make_range(text, definition.line, definition.column, definition.length)


def _token_key(token: Token) -> tuple[int, int]:
    return token.line, token.column


def _span_end(tokens: list[Token], start_index: int, *, block: bool) -> int:
    if block:
        opening = next(
            (i for i in range(start_index, len(tokens)) if tokens[i].kind is TokenKind.LEFT_BRACE),
            start_index,
        )
        depth = 0
        for i in range(opening, len(tokens)):
            if tokens[i].kind is TokenKind.LEFT_BRACE:
                depth += 1
            elif tokens[i].kind is TokenKind.RIGHT_BRACE:
                depth -= 1
                if depth == 0:
                    return i
        return max(start_index, len(tokens) - 1)
    parens = brackets = braces = 0
    for i in range(start_index, len(tokens)):
        kind = tokens[i].kind
        if kind is TokenKind.LEFT_PAREN:
            parens += 1
        elif kind is TokenKind.RIGHT_PAREN:
            parens -= 1
        elif kind is TokenKind.LEFT_BRACKET:
            brackets += 1
        elif kind is TokenKind.RIGHT_BRACKET:
            brackets -= 1
        elif kind is TokenKind.LEFT_BRACE:
            braces += 1
        elif kind is TokenKind.RIGHT_BRACE:
            braces -= 1
        elif kind is TokenKind.SEMICOLON and parens == brackets == braces == 0:
            return i
    return max(start_index, len(tokens) - 1)


def _token_span_range(start: Token, end: Token, text: str) -> dict[str, dict[str, int]]:
    start_pos = source_position(start.line, start.column, text)
    end_pos = source_position(end.line, end.column + len(end.lexeme), text)
    if (end_pos["line"], end_pos["character"]) < (start_pos["line"], start_pos["character"]):
        end_pos = dict(start_pos)
    return {"start": start_pos, "end": end_pos}


class LanguageService:
    """Synchronous static analysis and symbol lookup over open-document overlays."""

    def __init__(self) -> None:
        self.documents: dict[str, TextDocument] = {}
        self.features: dict[str, DocumentFeatures] = {}

    def open_document(
        self, uri: str, language_id: str, version: int, text: str
    ) -> TextDocument:
        path = path_from_file_uri(uri)
        if path.suffix.lower() != ".lwt" or language_id != "lwt":
            raise ValueError("only languageId 'lwt' for .lwt files is supported")
        key = path_key(path)
        document = TextDocument(file_uri(path), key, path, language_id, version, text)
        if key in self.documents:
            raise ValueError("document is already open")
        self.documents[key] = document
        return document

    def change_document(self, uri: str, version: int, text: str) -> TextDocument:
        path = path_from_file_uri(uri)
        key = path_key(path)
        document = self.documents.get(key)
        if document is None:
            raise ValueError("document is not open")
        if version <= document.version:
            raise ValueError("document version must increase")
        document.version = version
        document.text = text
        return document

    def close_document(self, uri: str) -> TextDocument | None:
        path = path_from_file_uri(uri)
        document = self.documents.pop(path_key(path), None)
        self.features.pop(path_key(path), None)
        return document

    def _overlays(self) -> dict[Path, str]:
        return {document.path: document.text for document in self.documents.values()}

    def analyze_open_documents(self) -> dict[str, list[dict[str, object]]]:
        """Analyze every open root; aggregate module diagnostics deterministically."""
        diagnostics: dict[str, list[dict[str, object]]] = {
            document.uri: [] for document in self.documents.values()
        }
        self.features.clear()
        for document in sorted(self.documents.values(), key=lambda item: item.uri):
            try:
                graph = load_module_graph(
                    str(document.path),
                    source_overlays=self._overlays(),
                    include_sources=True,
                )
            except LwtError as error:
                uri = self._error_uri(document, error)
                diagnostics.setdefault(uri, []).append(
                    self._lwt_error_diagnostic(document, error)
                )
                continue
            for unit in graph.modules:
                source = self._source_for(unit)
                self.features[path_key(unit.canonical_path)] = _build_features(
                    unit, source
                )
            for diagnostic in analyze_module_graph(graph, str(document.path)):
                uri = self._static_uri(document, graph, diagnostic)
                diagnostics.setdefault(uri, []).append(
                    self._static_diagnostic(uri, diagnostic)
                )
        for uri, values in diagnostics.items():
            values.sort(key=lambda item: (
                item["range"]["start"]["line"],
                item["range"]["start"]["character"],
            ))
            unique: list[dict[str, object]] = []
            seen: set[tuple[object, ...]] = set()
            for item in values:
                identity = (
                    item["range"]["start"]["line"],
                    item["range"]["start"]["character"],
                    item["range"]["end"]["line"],
                    item["range"]["end"]["character"],
                    item["code"],
                    item["message"],
                )
                if identity not in seen:
                    unique.append(item)
                    seen.add(identity)
            diagnostics[uri] = unique
        return diagnostics

    def _source_for(self, unit: ModuleUnit) -> str:
        if unit.source_text is not None:
            return unit.source_text
        raise RuntimeError("source text was not retained by the language loader")

    @staticmethod
    def _static_uri(
        entry_document: TextDocument, graph: ModuleGraph, diagnostic: StaticDiagnostic
    ) -> str:
        if diagnostic.source is None:
            return entry_document.uri
        source = Path(diagnostic.source)
        if source.is_absolute():
            return file_uri(source)
        for unit in graph.modules:
            if unit.display_path == diagnostic.source:
                return file_uri(unit.canonical_path)
        return entry_document.uri

    @staticmethod
    def _error_uri(document: TextDocument, error: LwtError) -> str:
        source = error.location.source_path if error.location is not None else None
        if source is None:
            return document.uri
        path = Path(source)
        if path.is_absolute():
            return file_uri(path)
        candidate = (document.path.parent / path).resolve(strict=False)
        return file_uri(candidate)

    def _lwt_error_diagnostic(
        self, document: TextDocument, error: LwtError
    ) -> dict[str, object]:
        location = error.location or SourceLocation(1, 1)
        uri = self._error_uri(document, error)
        text = self._text_for_uri(uri, document)
        lines = normalized_source_lines(text)
        eof_line = len(lines)
        eof_column = len(lines[-1]) + 1
        length = 0 if (location.line, location.column) == (eof_line, eof_column) else 1
        messages = {
            "LexError": ("LEX001", error.message),
            "SyntaxError": ("PAR001", error.message),
            "ImportError": ("MOD001", "cannot load or link imported module"),
            "FileError": ("SRC001", "cannot read UTF-8 source file"),
        }
        code, message = messages.get(error.category, ("SRC001", "source analysis failed"))
        return {
            "range": make_range(text, location.line, location.column, length),
            "severity": 1,
            "code": code,
            "source": "lwt",
            "message": message,
        }

    def _text_for_uri(self, uri: str, fallback: TextDocument) -> str:
        try:
            path = path_from_file_uri(uri)
            opened = self.documents.get(path_key(path))
            if opened is not None:
                return opened.text
            feature = self.features.get(path_key(path))
            if feature is not None:
                return feature.text
            return path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError, ValueError):
            return fallback.text

    def _static_diagnostic(self, uri: str, diagnostic: StaticDiagnostic) -> dict[str, object]:
        text = self._text_for_uri(uri, next(iter(self.documents.values())))
        location_line = diagnostic.line or 1
        location_column = diagnostic.column or 1
        length = _source_token_length(text, location_line, location_column)
        return {
            "range": make_range(text, location_line, location_column, length),
            "severity": 1,
            "code": diagnostic.code,
            "source": "lwt",
            "message": diagnostic.message,
        }

    def symbols(self, uri: str) -> list[dict[str, object]]:
        feature = self._feature(uri)
        return list(feature.symbols) if feature is not None else []

    def hover(self, uri: str, line: int, character: int) -> dict[str, object] | None:
        feature = self._feature(uri)
        document = self._document(uri)
        if feature is None or document is None:
            return None
        cp = _token_at(feature.tokens, document.text, line, character)
        if cp is None:
            return None
        token, _ = cp
        position = (token.line, token.column)
        content = feature.hovers.get(position)
        if content is None:
            content = KEYWORD_HOVER.get(token.lexeme) or BUILTIN_HOVER.get(token.lexeme)
        if content is None:
            return None
        return {"contents": {"kind": "plaintext", "value": content}}

    def definition(self, uri: str, line: int, character: int) -> dict[str, object] | None:
        feature = self._feature(uri)
        document = self._document(uri)
        if feature is None or document is None:
            return None
        found = _token_at(feature.tokens, document.text, line, character)
        if found is None:
            return None
        token, _ = found
        target = feature.definitions.get((token.line, token.column))
        if target is None:
            return None
        target_uri = file_uri(target.path)
        target_text = self._source_for_path(target.path)
        target_range = _identifier_range(target, target_text)
        return {"uri": target_uri, "range": target_range}

    def _source_for_path(self, path: Path) -> str:
        document = self.documents.get(path_key(path))
        if document is not None:
            return document.text
        feature = self.features.get(path_key(path))
        if feature is not None:
            return feature.text
        return path.read_text(encoding="utf-8", errors="strict")

    def _feature(self, uri: str) -> DocumentFeatures | None:
        try:
            return self.features.get(path_key(path_from_file_uri(uri)))
        except ValueError:
            return None

    def _document(self, uri: str) -> TextDocument | None:
        try:
            return self.documents.get(path_key(path_from_file_uri(uri)))
        except ValueError:
            return None


def uri_to_path(uri: str) -> Path:
    return path_from_file_uri(uri)


def _source_token_length(text: str, line: int, column: int) -> int:
    try:
        tokens = scan(text)
    except LwtError:
        return 1
    token = next(
        (token for token in tokens if token.line == line and token.column == column and token.kind is not TokenKind.EOF),
        None,
    )
    return max(1, len(token.lexeme)) if token is not None else 1


def _token_at(
    tokens: list[Token], text: str, line: int, character: int
) -> tuple[Token, int] | None:
    lines = normalized_source_lines(text)
    if line < 0 or line >= len(lines):
        return None
    column = utf16_character_to_codepoint(lines[line], character)
    if column is None:
        return None
    one_based = column + 1
    for token in tokens:
        if token.line != line + 1 or token.kind is TokenKind.EOF:
            continue
        if token.column <= one_based <= token.column + max(0, len(token.lexeme) - 1):
            return token, one_based
    return None


def _build_features(unit: ModuleUnit, text: str) -> DocumentFeatures:
    tokens = scan(text, unit.display_path)
    by_name: dict[str, ast.FunctionDeclaration] = {
        item.name.name: item for item in unit.program.items if isinstance(item, ast.FunctionDeclaration)
    }
    records = {
        item.name.name: item for item in unit.program.items if isinstance(item, ast.RecordDeclaration)
    }
    hovers: dict[tuple[int, int], str] = {}
    definitions: dict[tuple[int, int], Definition] = {}
    symbols: list[dict[str, object]] = []
    path = unit.canonical_path

    def definition(identifier: ast.Identifier) -> Definition:
        return Definition(path, identifier.location.line, identifier.location.column, len(identifier.name))

    def add_decl(identifier: ast.Identifier, hover: str) -> Definition:
        ref = definition(identifier)
        hovers[(ref.line, ref.column)] = hover
        definitions[(ref.line, ref.column)] = ref
        return ref

    def add_use(identifier: ast.Identifier, scope: _Scope, *, hidden_here: str | None = None) -> None:
        ref = scope.resolve(identifier.name, hidden_here=hidden_here)
        if ref is not None:
            definitions[(identifier.location.line, identifier.location.column)] = ref
            hovers[(identifier.location.line, identifier.location.column)] = f"variable {identifier.name}"

    def range_for(start: SourceLocation, *, block: bool = False) -> dict[str, dict[str, int]]:
        index = next((i for i, token in enumerate(tokens) if (token.line, token.column) == (start.line, start.column)), len(tokens) - 1)
        end_index = _span_end(tokens, index, block=block)
        return _token_span_range(tokens[index], tokens[end_index], text)

    # Module level declarations are collected before references so function
    # bodies can resolve later-declared functions, records, imports and globals.
    root = _Scope(None)
    import_refs: dict[str, Definition] = {}
    for item in unit.program.items:
        if isinstance(item, ast.ImportDeclaration):
            ref = add_decl(item.alias, f"module {item.alias.name} -> {item.path}")
            import_refs[item.alias.name] = ref
            symbols.append({"name": item.alias.name, "kind": SYMBOL_KIND["module"], "detail": item.path,
                            "range": range_for(item.location), "selectionRange": make_range(text, item.alias.location.line, item.alias.location.column, len(item.alias.name))})
        elif isinstance(item, ast.RecordDeclaration):
            hover = "record " + item.name.name + "{" + ", ".join(field.name for field in item.fields) + "}"
            add_decl(item.name, hover)
            children = []
            for field_item in item.fields:
                field_ref = add_decl(field_item, f"field {item.name.name}.{field_item.name}")
                children.append({"name": field_item.name, "kind": SYMBOL_KIND["field"], "detail": "record field",
                                 "range": _identifier_range(field_ref, text), "selectionRange": _identifier_range(field_ref, text)})
            symbols.append({"name": item.name.name, "kind": SYMBOL_KIND["record"], "detail": hover,
                            "range": range_for(item.location), "selectionRange": make_range(text, item.name.location.line, item.name.location.column, len(item.name.name)), "children": children})
        elif isinstance(item, ast.FunctionDeclaration):
            hover = _function_hover(item)
            add_decl(item.name, hover)
            children = []
            for parameter in item.parameters:
                parameter_ref = add_decl(parameter, f"parameter {parameter.name} of {item.name.name}")
                children.append({"name": parameter.name, "kind": SYMBOL_KIND["variable"], "detail": "parameter",
                                 "range": _identifier_range(parameter_ref, text), "selectionRange": _identifier_range(parameter_ref, text)})
            symbols.append({"name": item.name.name, "kind": SYMBOL_KIND["function"], "detail": hover,
                            "range": range_for(item.location, block=True), "selectionRange": make_range(text, item.name.location.line, item.name.location.column, len(item.name.name)), "children": children})

    # Program items can contain any statement; exclude declarations explicitly.
    top_statements = [item for item in unit.program.items if not isinstance(item, (ast.ImportDeclaration, ast.RecordDeclaration, ast.FunctionDeclaration))]
    for item in top_statements:
        if isinstance(item, ast.LetStatement) and item.name.name not in root.definitions:
            root.definitions[item.name.name] = definition(item.name)
            ref = definition(item.name)
            hovers[(ref.line, ref.column)] = f"variable {item.name.name}"
            definitions[(ref.line, ref.column)] = ref
            symbols.append({"name": item.name.name, "kind": SYMBOL_KIND["variable"], "detail": "top-level let",
                            "range": range_for(item.location), "selectionRange": make_range(text, item.name.location.line, item.name.location.column, len(item.name.name))})

    def visit_expression(expression: ast.Expression, scope: _Scope, hidden_here: str | None = None) -> None:
        if isinstance(expression, ast.VariableExpression):
            add_use(expression.name, scope, hidden_here=hidden_here)
        elif isinstance(expression, ast.ArrayExpression):
            for element in expression.elements: visit_expression(element, scope, hidden_here)
        elif isinstance(expression, ast.DictExpression):
            for entry in expression.entries:
                visit_expression(entry.key, scope, hidden_here)
                visit_expression(entry.value, scope, hidden_here)
        elif isinstance(expression, ast.RecordConstructionExpression):
            record = records.get(expression.type_name.name)
            if record is not None:
                ref = definition(record.name)
                definitions[(expression.type_name.location.line, expression.type_name.location.column)] = ref
                hovers[(expression.type_name.location.line, expression.type_name.location.column)] = "record " + record.name.name + "{" + ", ".join(f.name for f in record.fields) + "}"
            for initializer in expression.fields: visit_expression(initializer.value, scope, hidden_here)
        elif isinstance(expression, ast.SpawnExpression):
            # S43: keep LSP node traversal total (no crash on spawn). Provide
            # hover/definition for the target function like a normal call.
            name = expression.callee.name
            if expression.alias is not None:
                alias_ref = import_refs.get(expression.alias.name)
                if alias_ref is not None:
                    definitions[(expression.alias.location.line, expression.alias.location.column)] = alias_ref
                    hovers[(expression.alias.location.line, expression.alias.location.column)] = hovers[(alias_ref.line, alias_ref.column)]
                resolution = resolve_module_call(unit, expression)  # type: ignore[arg-type]
                target_decl = resolution.declaration
                if target_decl is not None:
                    ref = definition(target_decl.name)
                    definitions[(expression.callee.location.line, expression.callee.location.column)] = ref
                    hovers[(expression.callee.location.line, expression.callee.location.column)] = _function_hover(target_decl)
            else:
                declaration = by_name.get(name)
                if name in BUILTIN_ARITIES:
                    hovers[(expression.callee.location.line, expression.callee.location.column)] = BUILTIN_HOVER[name]
                elif declaration is not None:
                    ref = definition(declaration.name)
                    definitions[(expression.callee.location.line, expression.callee.location.column)] = ref
                    hovers[(expression.callee.location.line, expression.callee.location.column)] = _function_hover(declaration)
            for argument in expression.arguments: visit_expression(argument, scope, hidden_here)
        elif isinstance(expression, ast.CallExpression):
            name = expression.callee.name
            declaration = by_name.get(name)
            if name in BUILTIN_ARITIES:
                hovers[(expression.callee.location.line, expression.callee.location.column)] = BUILTIN_HOVER[name]
            elif declaration is not None:
                ref = definition(declaration.name)
                definitions[(expression.callee.location.line, expression.callee.location.column)] = ref
                hovers[(expression.callee.location.line, expression.callee.location.column)] = _function_hover(declaration)
            for argument in expression.arguments: visit_expression(argument, scope, hidden_here)
        elif isinstance(expression, ast.ModuleCallExpression):
            alias_ref = import_refs.get(expression.alias.name)
            if alias_ref is not None:
                definitions[(expression.alias.location.line, expression.alias.location.column)] = alias_ref
                hovers[(expression.alias.location.line, expression.alias.location.column)] = hovers[(alias_ref.line, alias_ref.column)]
            resolution = resolve_module_call(unit, expression)
            if resolution.declaration is not None:
                target = resolution.target
                target_path = target.canonical_path
                target_def = Definition(target_path, resolution.declaration.name.location.line, resolution.declaration.name.location.column, len(resolution.declaration.name.name))
                definitions[(expression.member.location.line, expression.member.location.column)] = target_def
                hovers[(expression.member.location.line, expression.member.location.column)] = _function_hover(resolution.declaration)
            for argument in expression.arguments: visit_expression(argument, scope, hidden_here)
        elif isinstance(expression, ast.UnaryExpression): visit_expression(expression.operand, scope, hidden_here)
        elif isinstance(expression, ast.BinaryExpression):
            visit_expression(expression.left, scope, hidden_here); visit_expression(expression.right, scope, hidden_here)
        elif isinstance(expression, ast.AssignmentExpression): visit_expression(expression.target, scope, hidden_here); visit_expression(expression.value, scope, hidden_here)
        elif isinstance(expression, ast.IndexExpression): visit_expression(expression.object, scope, hidden_here); visit_expression(expression.index, scope, hidden_here)
        elif isinstance(expression, ast.FieldExpression): visit_expression(expression.object, scope, hidden_here)

    # Revisit bodies with expression hooks that build call/record indexes. The
    # first pass above handles lexical variable resolution and nested scopes.
    for item in unit.program.items:
        if isinstance(item, ast.FunctionDeclaration):
            activation = _Scope(root, {parameter.name: definition(parameter) for parameter in item.parameters})
            _visit_statement_list_full(item.body.statements, activation, visit_expression, add_use, definition, hovers, definitions)
    _visit_statement_list_full(top_statements, root, visit_expression, add_use, definition, hovers, definitions)

    # Add syntax-only keyword hover entries and local built-ins.
    for token in tokens:
        if token.kind is not TokenKind.IDENT and token.lexeme in KEYWORD_HOVER:
            hovers.setdefault(_token_key(token), KEYWORD_HOVER[token.lexeme])
        elif token.kind is TokenKind.IDENT and token.lexeme in BUILTIN_HOVER:
            hovers.setdefault(_token_key(token), BUILTIN_HOVER[token.lexeme])
    symbols.sort(key=lambda symbol: (
        symbol["range"]["start"]["line"], symbol["range"]["start"]["character"]
    ))
    return DocumentFeatures(path, text, tokens, symbols, hovers, definitions)


def _function_hover(declaration: ast.FunctionDeclaration) -> str:
    params = ", ".join(parameter.name for parameter in declaration.parameters)
    return f"fn {declaration.name.name}({params})"


def _visit_statement_list_full(statements, scope, visit_expression, add_use, definition, hovers, definitions):
    direct_lets = [s for s in statements if isinstance(s, ast.LetStatement)]
    preexisting = set(scope.definitions)
    encountered: set[str] = set()
    for item in direct_lets:
        ref = scope.definitions.setdefault(item.name.name, definition(item.name))
        key = (item.name.location.line, item.name.location.column)
        definitions[key] = ref
        hovers.setdefault(key, f"variable {item.name.name}")
    for statement in statements:
        if isinstance(statement, ast.LetStatement):
            duplicate = statement.name.name in preexisting or statement.name.name in encountered
            visit_expression(
                statement.initializer,
                scope,
                hidden_here=None if duplicate else statement.name.name,
            )
            encountered.add(statement.name.name)
        else:
            _visit_statement_full(statement, scope, visit_expression, add_use, definition, hovers, definitions)


def _visit_statement_full(statement, scope, visit_expression, add_use, definition, hovers, definitions):
    if isinstance(statement, ast.Block):
        _visit_statement_list_full(statement.statements, _Scope(scope), visit_expression, add_use, definition, hovers, definitions)
    elif isinstance(statement, ast.AttemptStatement):
        _visit_statement_full(statement.body, scope, visit_expression, add_use, definition, hovers, definitions)
        error_ref = definition(statement.error_name)
        error_key = (error_ref.line, error_ref.column)
        definitions[error_key] = error_ref
        hovers[error_key] = f"variable {statement.error_name.name} (recover error)"
        handler = _Scope(scope, {statement.error_name.name: error_ref})
        _visit_statement_list_full(statement.recover_body.statements, _Scope(handler), visit_expression, add_use, definition, hovers, definitions)
        if statement.finally_body is not None:
            _visit_statement_full(statement.finally_body, scope, visit_expression, add_use, definition, hovers, definitions)
    elif isinstance(statement, ast.ThrowStatement):
        visit_expression(statement.value, scope)
    elif isinstance(statement, ast.EachStatement):
        visit_expression(statement.iterable, scope)
        loop_ref = definition(statement.variable)
        loop_key = (loop_ref.line, loop_ref.column)
        definitions[loop_key] = loop_ref
        hovers[loop_key] = f"variable {statement.variable.name} (each item)"
        iteration = _Scope(scope, {statement.variable.name: loop_ref})
        _visit_statement_list_full(statement.body.statements, _Scope(iteration), visit_expression, add_use, definition, hovers, definitions)
    elif isinstance(statement, ast.WhenStatement):
        visit_expression(statement.condition, scope)
        _visit_statement_full(statement.then_branch, scope, visit_expression, add_use, definition, hovers, definitions)
        if statement.otherwise_branch: _visit_statement_full(statement.otherwise_branch, scope, visit_expression, add_use, definition, hovers, definitions)
    elif isinstance(statement, ast.WhileStatement):
        visit_expression(statement.condition, scope)
        _visit_statement_full(statement.body, scope, visit_expression, add_use, definition, hovers, definitions)
    elif isinstance(statement, (ast.EmitStatement, ast.ReturnStatement, ast.ExpressionStatement)):
        expression = statement.value if isinstance(statement, (ast.EmitStatement, ast.ReturnStatement)) else statement.expression
        if expression is not None: visit_expression(expression, scope)
