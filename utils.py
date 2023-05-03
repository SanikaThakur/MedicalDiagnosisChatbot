# This function returns a dictionary required for the suggest query
def get_suggest_request(evidence, age, sex):
    request = dict()
    request["sex"] = sex
    request["age"] = age
    request["evidence"] = evidence
    request["suggest"] = "red_flags"
    return request


# This function returns questions returned by the suggest response
def get_suggest_questions(suggest_response):
    questions = dict()
    questions["type"] = "group_multiple"
    questions[
        "text"
    ] = "Do you experience any of these symptoms? (Select all that apply)"
    questions["items"] = []
    for suggestion in suggest_response:
        q = dict()
        q["id"] = suggestion["id"]
        q["name"] = suggestion["common_name"]
        q["choices"] = []
        questions["items"].append(q)
    return questions


# This function extracts symptoms from mentions
def mentions_to_evidence(mentions):
    init_symptoms = dict()
    for mention in mentions:
        init_symptoms["id"] = mention["id"]
        init_symptoms["choice_id"] = mention["choice_id"]
        init_symptoms["source"] = "initial"
    return init_symptoms


# This function formats the response to evidence
def format_response_to_evidence(evidence, response):
    updated_evidence = evidence
    for key, value in response.items():
        if len(value[1]):
            updated_evidence.append(
                {"id": key, "choice_id": value[0], "source": value[1]}
            )
        else:
            updated_evidence.append({"id": key, "choice_id": value[0]})
    return updated_evidence


# This function calculates Indian Diabetes Risk Score
def calc_idrs(age, sex, waist, exercise, sw, history):
    rs = 0

    if age in range(35, 51):
        rs += 20
    elif age > 50:
        rs += 30

    if sex == "female":
        if waist in range(80, 90):
            rs += 10
        elif waist >= 90:
            rs += 20
    else:
        if waist in range(90, 100):
            rs += 10
        elif waist >= 100:
            rs += 20

    if exercise or sw:
        rs += 20
    elif not exercise and not sw:
        rs += 30

    if history == 1:
        rs += 10
    elif history > 1:
        rs += 20

    return rs
