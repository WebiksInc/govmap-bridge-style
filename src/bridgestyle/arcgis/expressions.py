# For now, this is limited to compound labels using the python, VB or Arcade syntax
import re
from ..geostyler.custom_properties import WellKnownText
from .constants import PROPERTY_NAME_PATTERN


def convertExpression(expression, engine, tolowercase, numericFields=None):
    if engine == "Arcade":
        expression = convertArcadeExpression(expression)
    elif engine == "VBScript":
        expression = convertVBScriptExpression(expression)
    if tolowercase:
        expression = expression.lower()
    if "+" in expression or "&" in expression:
        separator = "+" if "+" in expression else "&"
        addends = []
        for token in expression.split(separator):
            if "[" in token:
                addends.append(propertyExpression(token, numericFields))
            else:
                literal = replaceSpecialLiteral(token.strip().replace('"', ""))
                if not literal:
                    continue
                # Merge consecutive literals (e.g. a newline followed by text) into a
                # single one: whitespace-only SLD literals are dropped by GeoServer
                # when an XML rewrite strips the CDATA sections.
                if addends and isinstance(addends[-1], str):
                    addends[-1] += literal
                else:
                    addends.append(literal)
        if not addends:
            return ""
        allOps = addends[-1]
        for attr in addends[-2::-1]:
            allOps = ["Concatenate", attr, allOps]
        expression = allOps
    else:
        expression = propertyExpression(expression, numericFields)
    return expression


def replaceSpecialLiteral(literal):
    if literal.lower() in ("vbnewline", "vbcrlf", "vblf"):
        return WellKnownText.NEW_LINE
    return literal


def propertyExpression(token, numericFields=None):
    name = processPropertyName(token)
    expression = ["PropertyName", name]
    pattern = (numericFields or {}).get(name.lower())
    if pattern:
        # Numeric fields are labelled as-is by ArcGIS ("10"), while GeoServer renders
        # the raw double ("10.0" or "1.1E7"); numberFormat reproduces the ArcGIS look.
        return ["numberFormat", pattern, expression]
    return expression


def processPropertyName(token):
    return token.replace("[", "").replace("]", "").strip()


def convertArcadeExpression(expression):
    return expression.replace("$feature.", "")


# Matches a whole `Function <name> ( ... ) ... End Function` block (case-insensitive,
# spanning multiple lines).
_VB_FUNCTION_BLOCK = re.compile(
    r"Function\s+(?P<name>\w+)\s*\(.*?\).*?End\s+Function",
    re.IGNORECASE | re.DOTALL,
)

# VBScript line continuation: an underscore at the end of a line.
_VB_LINE_CONTINUATION = re.compile(r"_[ \t]*[\r\n]+")

# VBScript type-cast/wrapper functions whose only effect here is coercion, e.g.
# CStr([FOO]) -> [FOO]. The opening paren is matched; its partner is found by
# scanning for balanced parentheses so nested casts are handled too.
_VB_CAST = re.compile(
    r"\bC(?:Str|Int|Lng|Dbl|Sng|Cur|Bool|Byte|Date|Var)\s*\(",
    re.IGNORECASE,
)


def convertVBScriptExpression(expression):
    """Normalise a VBScript label expression to the inline form the rest of this
    module already understands. Handles both inline expressions (returned as-is)
    and multi-line `Function ... End Function` blocks, from which the core return
    expression is extracted. VBScript type-cast wrappers such as ``CStr(...)`` are
    stripped in either case."""
    expression = _extractVBFunctionExpression(expression)
    expression = _stripVBCasts(expression)
    return expression


def _extractVBFunctionExpression(expression):
    match = _VB_FUNCTION_BLOCK.search(expression)
    if not match:
        # Inline expression; nothing to unwrap.
        return expression
    name = match.group("name")
    body = _VB_LINE_CONTINUATION.sub(" ", match.group(0))
    # The return value is whatever is assigned to the function name, e.g.
    # `FindLabel = [CITY] & ...`. The signature uses `(`, not `=`, so it is
    # never matched here.
    assignment = re.search(
        rf"\b{re.escape(name)}\s*=\s*(.+)", body, re.IGNORECASE
    )
    if not assignment:
        return expression
    core = re.split(r"\bEnd\s+Function\b", assignment.group(1), flags=re.IGNORECASE)[0]
    return core.strip()


def _stripVBCasts(expression):
    while True:
        match = _VB_CAST.search(expression)
        if not match:
            return expression
        openParen = match.end() - 1
        depth = 0
        closeParen = None
        for i in range(openParen, len(expression)):
            if expression[i] == "(":
                depth += 1
            elif expression[i] == ")":
                depth -= 1
                if depth == 0:
                    closeParen = i
                    break
        if closeParen is None:
            # Unbalanced parentheses; leave the expression untouched.
            return expression
        inner = expression[openParen + 1:closeParen]
        expression = expression[:match.start()] + inner + expression[closeParen + 1:]


def isValidPropertyName(token):
    return bool(PROPERTY_NAME_PATTERN.match(token))


def stringToParameter(s, tolowercase):
    s = s.strip()
    if "'" in s or '"' in s:
        return s.strip("'\"")
    else:
        if isValidPropertyName(s):
            if tolowercase:
                s = s.lower()
            return ["PropertyName", s]
        else:
            return s


# For now, limited to = or IN statements
# There is no formal parsing, just a naive conversion
def convertWhereClause(clause, tolowercase):
    if clause.startswith("(") and clause.endswith(")"):
        clause = clause[1:-1]
    if " AND " in clause:
        expression = ["And"]
        subexpressions = [s.strip() for s in clause.split(" AND ")]
        expression.extend([convertWhereClause(s, tolowercase) for s in subexpressions])
        return expression
    if "=" in clause:
        tokens = [t.strip() for t in clause.split("=")]
        expression = [
            "PropertyIsEqualTo",
            stringToParameter(tokens[0], tolowercase),
            stringToParameter(tokens[1], tolowercase),
        ]
        return expression
    if "<>" in clause:
        tokens = [t.strip() for t in clause.split("<>")]
        expression = [
            "PropertyIsNotEqualTo",
            stringToParameter(tokens[0], tolowercase),
            stringToParameter(tokens[1], tolowercase),
        ]
        return expression
    if ">" in clause:
        tokens = [t.strip() for t in clause.split(">")]
        expression = [
            "PropertyIsGreaterThan",
            stringToParameter(tokens[0], tolowercase),
            stringToParameter(tokens[1], tolowercase),
        ]
        return expression
    elif " in " in clause.lower():
        clause = clause.replace(" IN ", " in ")
        tokens = clause.split(" in ")
        attribute = tokens[0]
        values = tokens[1].strip("() ").split(",")
        subexpressions = []
        for v in values:
            subexpressions.append(
                [
                    "PropertyIsEqualTo",
                    stringToParameter(attribute, tolowercase),
                    stringToParameter(v, tolowercase),
                ]
            )
        expression = []
        if len(values) == 1:
            return subexpressions[0]
        else:
            accum = ["Or", subexpressions[0], subexpressions[1]]
            for subexpression in subexpressions[2:]:
                accum = ["Or", accum, subexpression]
            return accum

    return clause


def processRotationExpression(expression, rotationType, tolowercase):
    if "$feature" in expression:
        field = convertArcadeExpression(expression)
    else:
        field = processPropertyName(expression)
    propertyNameExpression = ["PropertyName", field.lower() if tolowercase else field]
    if rotationType == "Arithmetic":
        return [
            "Mul",
            propertyNameExpression,
            -1,
        ]
    elif rotationType == "Geographic":
        return [
            "Sub",
            propertyNameExpression,
            90,
        ]
