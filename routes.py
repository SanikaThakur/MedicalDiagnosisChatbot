import json
from main import app
from flask import request, render_template, make_response
import infermedica_api
from utils import (
    get_suggest_request,
    get_suggest_questions,
    mentions_to_evidence,
    format_response_to_evidence,
    calc_idrs,
)
import time
from datetime import datetime
from pytz import timezone

import pydf

api = infermedica_api.APIv3Connector(
    app_id="YOUR APP ID", app_key="YOUR APP KEY"
)
initial_questions = [
    {
        "type": "text",
        "text": "What is your age (in years)?",
        "items": [{"id": "initAge", "choices": []}],
    },
    {
        "type": "single",
        "text": "What is your gender?",
        "items": [
            {
                "id": "initSex",
                "choices": [
                    {"id": "male", "label": "Male"},
                    {"id": "female", "label": "Female"},
                    {"id": "unknown", "label": "Don't Know"},
                ],
            }
        ],
    },
    {
        "type": "single",
        "text": "Region of Residence",
        "items": [
            {
                "id": "initLoc",
                "choices": [
                    {"id": "p_13", "label": "North America without Mexico"},
                    {"id": "p_14", "label": "Latin and South America"},
                    {"id": "p_15", "label": "Europe"},
                    {"id": "p_16", "label": "Northern Africa"},
                    {"id": "p_17", "label": "Central Africa"},
                    {"id": "p_18", "label": "Southern Africa"},
                    {"id": "p_19", "label": "Australia and Oceania"},
                    {"id": "p_20", "label": "Russia, Kazakhstan and Mongolia"},
                    {"id": "p_21", "label": "Middle East"},
                    {
                        "id": "p_236",
                        "label": "Asia excluding Middle East, Russia, Kazakhstan and Mongolia",
                    },
                ],
            }
        ],
    },
    {
        "type": "text",
        "text": "How can I help you today?",
        "items": [{"id": "initQ", "choices": []}],
    },
]

drs_questions = [
    {
        "type": "text",
        "text": "What is your age (in years)?",
        "items": [{"id": "age", "choices": []}],
    },
    {
        "type": "single",
        "text": "What is your gender?",
        "items": [
            {
                "id": "sex",
                "choices": [
                    {"id": "male", "label": "Male"},
                    {"id": "female", "label": "Female"},
                    {"id": "unknown", "label": "Don't Know"},
                ],
            }
        ],
    },
    {
        "type": "single",
        "text": "Do you exercise regularly?",
        "items": [
            {
                "id": "exercise",
                "choices": [
                    {"id": "yes", "label": "Yes"},
                    {"id": "no", "label": "No"},
                ],
            }
        ],
    },
    {
        "type": "single",
        "text": "Do you perform strenous work?",
        "items": [
            {
                "id": "sw",
                "choices": [
                    {"id": "yes", "label": "Yes"},
                    {"id": "no", "label": "No"},
                ],
            }
        ],
    },
    {
        "type": "single",
        "text": "Did your parents have/had diabetes?",
        "items": [
            {
                "id": "history",
                "choices": [
                    {"id": "0", "label": "No Parent"},
                    {"id": "1", "label": "Either Parent"},
                    {"id": "2", "label": "Both Parents"},
                ],
            }
        ],
    },
    {
        "type": "text",
        "text": "What is your waist circumference (in cms)?",
        "items": [{"id": "waist", "choices": []}],
    },
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bot_say", methods=["GET", "POST"])
def cont_diag():
    evidence = []

    if request.method == "GET":
        return render_template(
            "test.html",
            questionset=initial_questions,
        )

    # Get data sent from JS
    response = json.loads(request.form["formdata"])
    initialEvidence = json.loads(request.form["initial_evidence"])

    if len(response["initialEvidence"]) < 3:
        # Initial Questions

        # Get Response
        age = int(response["initAge"])
        sex = response["initSex"]
        loc = response["initLoc"]
        initq = response["initQ"]

        # Add Location in Evidence
        loc_evidence = {"id": loc, "choice_id": "present", "source": "predefined"}
        evidence.append(loc_evidence)

        # Parse it using the API parse endpoint
        api_response = api.parse(initq, age=age)

        # Input clear
        if api_response["obvious"] or len(api_response["mentions"]):
            # Convert to acceptable format
            initEvidence = mentions_to_evidence(api_response["mentions"])
            # Add it to evidence list
            evidence.append(initEvidence)
            # Prepare request for suggest endpoint of API
            suggest_request = get_suggest_request(evidence=evidence, age=age, sex=sex)
            # Ask suggested questions based on red_flags
            suggests = api.suggest(**suggest_request)
            # Convert to acceptable format
            suggests_q = get_suggest_questions(suggests)

            return {
                "next_question": suggests_q,
                "initial_evidence": [loc_evidence, initEvidence],
                "source": "red_flags",
                "stop_flag": "False",
            }
        # UNCLEAR INPUT, ASK AGAIN
        else:
            chief_complaint = {
                "type": "text",
                "text": "Your input was not clear, could you elaborate more? ( Be more specific )",
                "items": [{"id": "initQ", "choices": []}],
            }
            return {
                "next_question": chief_complaint,
                "initial_evidence": {},
                "source": "",
                "stop_flag": "False",
            }

    # Infermedica API Continues
    else:
        # Remove Unnecessary Data
        age = int(response.pop("initAge"))
        sex = response.pop("initSex")
        loc = response.pop("initLoc")
        response.pop("initQ")
        response.pop("initialEvidence")

        # Get the initial evidence i.e. location and first question
        initial_evidence = initialEvidence

        # Update evidence with form response
        evidence = format_response_to_evidence(evidence, response)
        evidence = initial_evidence + evidence
        # print(f"Evidence: {evidence}")

        # Call API with the data
        diag = api.diagnosis(evidence=evidence, age=age, sex=sex)
        # print(f"Diagnosis: {diag}")

        # Check if diagnosis is completed
        if diag["has_emergency_evidence"] or diag["should_stop"]:

            recommended_specialist = api.specialist_recommender(
                **{"sex": sex, "age": age, "evidence": evidence}
            )
            explained = api.explain(
                **{
                    "sex": sex,
                    "age": age,
                    "evidence": evidence,
                    "target_id": diag["conditions"][0]["id"],
                }
            )

            return {
                "doctor": recommended_specialist["recommended_specialist"]["name"],
                "conditions": diag["conditions"],
                "emergency": diag["has_emergency_evidence"],
                "explained": explained,
                "stop_flag": "True",
            }

        # Continue Diagnosis
        else:
            return {
                "next_question": diag["question"],
                "initial_evidence": initialEvidence,
                "source": "",
                "stop_flag": "False",
            }


@app.route("/down")
def download():
    return render_template("down.html")


@app.route("/report", methods=["POST"])
def gen_report():

    try:
        print(request.get_json())
    except:
        print("request.get_json() FAILED")

    response = request.get_json()
    # Get Explained data
    explained = json.loads(response["explained"])
    print(f"Explained: {explained}")
    # Get Patient data
    pd = json.loads(response["pd"])
    pd["date"] = datetime.now(timezone("Asia/Kolkata"))
    print(f"PD: {pd}")
    # Get Conditions data
    patientConditions = json.loads(response["conditions"])
    print(f"Conditions: {patientConditions}")
    # Prepare Data
    evi_dict = {}
    for evidence in explained:
        if len(explained[evidence]) > 0:
            evi_name = " ".join([word.title() for word in evidence.split("_")])
            evi_dict[evi_name] = []
            for e in explained[evidence]:
                evi_dict[evi_name].append(e["common_name"])
    # Render the Report Page
    print(f"Evi Dict: {evi_dict}")
    page = render_template(
        "download.html", evid=evi_dict, patient_details=pd, conditions=patientConditions
    )
    print(page)
    pdf = pydf.generate_pdf(page)
    # Send the Report Page
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=report.pdf"
    print(response)
    return response


@app.route("/report_test", methods=["POST"])
def gen_report_test():

    page = render_template("rep_temp_3.html")
    print(page)
    pdf = pydf.generate_pdf(page)
    print(f"PDF: {pdf}")
    # Send the Report Page
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=report.pdf"
    print(response)
    return response


@app.route("/drs", methods=["GET", "POST"])
def diabetes():

    if request.method == "GET":
        return render_template("drs.html", questionset=drs_questions)
    response = json.loads(request.form["formdata"])
    age = int(response["age"])
    sex = response["sex"]
    waist = int(response["waist"])
    if response["exercise"] == "yes":
        exercise = True
    else:
        exercise = False
    if response["sw"] == "yes":
        sw = True
    else:
        sw = False
    history = int(response["history"])
    # print(age,sex,waist,exercise,sw, history)
    score = calc_idrs(age, sex, waist, exercise, sw, history)
    # print(score)
    return {
        "idrs_score": score,
    }


@app.route("/sleep", methods=["POST"])
def go_to_sleep():
    if request.method == "POST":
        try:
            print(request.form)
            sleep_time = json.loads(request.form["sleep_time"])
            time.sleep(int(sleep_time))
            return {"redirect": True}
        except:
            print("Form Method Not Found")

        try:
            print(request.get_json())
            response = request.get_json()
            sleep_time = response["sleep_time"]
            time.sleep(int(sleep_time))
            return {"redirect": True}
        except:
            print("GET_JSON Method Not Found")
