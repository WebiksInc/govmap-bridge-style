# For now, this is limited to compound labels using the python, VB or Arcade syntax
import re
from ..geostyler.custom_properties import WellKnownText
from .constants import PROPERTY_NAME_PATTERN


def convertExpression(expression, engine, tolowercase, numericFields=None):
    if engine == "Arcade":
        expression = convertArcadeExpression(expression)
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
