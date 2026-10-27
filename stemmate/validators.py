# PURE VALIDATION FUNCTIONS: no flask, no db
# Checks input and returns problems as a list

def unknown_fields(data, allowed):
    #Names in data that are not allowed (PR-01: reject unknown fields)
    return sorted(set(data) - set(allowed))


def validate_login(data):
    #Return list of {"field", "message"} problems (empty list = valid)
    problems = []
    for name, label in (("username", "username"), ("password", "password")):
        value = data.get(name)
        if not isinstance(value, str) or not value.strip():
            problems.append({"field": name, "message": f"Enter your {label}."})
    return problems