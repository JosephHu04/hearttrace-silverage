from fastapi.testclient import TestClient


def start(
    client: TestClient,
    headers: dict[str, str],
    instrument: str,
    *,
    share_family: bool = False,
    share_care_team: bool = False,
):
    return client.post(
        "/api/elder/screenings",
        headers=headers,
        json={
            "instrumentCode": instrument,
            "consentConfirmed": True,
            "shareWithFamily": share_family,
            "shareWithCareTeam": share_care_team,
        },
    )


def answer_all(client: TestClient, headers: dict[str, str], session: dict, values: list[str]) -> dict:
    current = session
    for value in values:
        question = current["currentQuestion"]
        response = client.post(
            f"/api/elder/screenings/{session['id']}/answers",
            headers=headers,
            json={"itemCode": question["itemCode"], "value": value},
        )
        assert response.status_code == 200
        current = response.json()
    return current


def test_screening_requires_explicit_consent(client: TestClient, elder_headers: dict[str, str]):
    response = client.post(
        "/api/elder/screenings",
        headers=elder_headers,
        json={"instrumentCode": "gds15", "consentConfirmed": False},
    )
    assert response.status_code == 409


def test_gds15_is_scored_deterministically_and_retry_is_idempotent(
    client: TestClient, elder_headers: dict[str, str]
):
    response = start(client, elder_headers, "gds15")
    assert response.status_code == 201
    session = response.json()
    first = session["currentQuestion"]

    once = client.post(
        f"/api/elder/screenings/{session['id']}/answers",
        headers=elder_headers,
        json={"itemCode": first["itemCode"], "value": "no"},
    )
    assert once.status_code == 200
    retry = client.post(
        f"/api/elder/screenings/{session['id']}/answers",
        headers=elder_headers,
        json={"itemCode": first["itemCode"], "value": "no"},
    )
    assert retry.status_code == 200
    assert retry.json()["progressAnswered"] == 1
    conflict = client.post(
        f"/api/elder/screenings/{session['id']}/answers",
        headers=elder_headers,
        json={"itemCode": first["itemCode"], "value": "yes"},
    )
    assert conflict.status_code == 409

    current = retry.json()
    pathological = ["yes"] * 14
    for index in (3, 5, 9, 11):
        pathological[index] = "no"
    completed = answer_all(client, elder_headers, current, pathological)
    assert completed["status"] == "completed"
    assert completed["result"]["totalScore"] == 15
    assert completed["result"]["band"] == "high"
    assert "不构成精神疾病诊断" in completed["result"]["notice"]


def test_elder_can_correct_previous_answer_before_completion(
    client: TestClient, elder_headers: dict[str, str], family_headers: dict[str, str]
):
    session = start(client, elder_headers, "gad7").json()
    first_code = session["currentQuestion"]["itemCode"]
    first = client.post(
        f"/api/elder/screenings/{session['id']}/answers",
        headers=elder_headers,
        json={"itemCode": first_code, "value": "3"},
    ).json()
    assert first["answeredQuestions"][0]["selectedValue"] == "3"
    preflight = client.options(
        f"/api/elder/screenings/{session['id']}/answers/{first_code}",
        headers={
            "Origin": "http://127.0.0.1:3002",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert "PATCH" in preflight.headers["access-control-allow-methods"]

    correction = client.patch(
        f"/api/elder/screenings/{session['id']}/answers/{first_code}",
        headers=elder_headers,
        json={"value": "0"},
    )
    assert correction.status_code == 200
    corrected = correction.json()
    assert corrected["progressAnswered"] == 1
    assert corrected["currentQuestion"]["number"] == 2
    assert corrected["answeredQuestions"][0]["selectedValue"] == "0"
    assert client.patch(
        f"/api/elder/screenings/{session['id']}/answers/{first_code}",
        headers=family_headers,
        json={"value": "3"},
    ).status_code in (403, 404)
    assert client.patch(
        f"/api/elder/screenings/{session['id']}/answers/{first_code}",
        headers=elder_headers,
        json={"value": "invalid"},
    ).status_code == 400

    completed = answer_all(client, elder_headers, corrected, ["0"] * 6)
    assert completed["result"]["totalScore"] == 0
    assert len(completed["answeredQuestions"]) == 7
    assert client.patch(
        f"/api/elder/screenings/{session['id']}/answers/{first_code}",
        headers=elder_headers,
        json={"value": "3"},
    ).status_code == 409


def test_shared_high_screening_enters_staff_queue_without_exposing_answers_to_family(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    no_access_family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    response = start(
        client,
        elder_headers,
        "gad7",
        share_family=True,
        share_care_team=True,
    )
    assert response.status_code == 201
    completed = answer_all(client, elder_headers, response.json(), ["3"] * 7)
    assert completed["result"]["totalScore"] == 21
    assert completed["result"]["band"] == "high"

    family = client.get(
        "/api/family/elders/elder-demo-001/screenings",
        headers=family_headers,
    )
    assert family.status_code == 200
    item = family.json()["items"][0]
    assert item["band"] == "high"
    assert "totalScore" not in item
    assert "answers" not in item
    assert "answeredQuestions" not in item

    denied = client.get(
        "/api/family/elders/elder-demo-001/screenings",
        headers=no_access_family_headers,
    )
    assert denied.status_code == 403

    staff = client.get("/api/admin/screenings?band=high", headers=admin_headers)
    assert staff.status_code == 200
    assert staff.json()["total"] == 1
    assert staff.json()["items"][0]["instrumentCode"] == "gad7"

    risks = client.get("/api/admin/risk-events", headers=admin_headers)
    assert risks.status_code == 200
    screening_risks = [item for item in risks.json()["items"] if item["id"].startswith("risk-screening-")]
    assert len(screening_risks) == 1
    detail = client.get(f"/api/admin/risk-events/{screening_risks[0]['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["evidence"][0]["sourceType"] == "screening"


def test_unshared_screening_remains_private(
    client: TestClient,
    elder_headers: dict[str, str],
    family_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    response = start(client, elder_headers, "gad7")
    completed = answer_all(client, elder_headers, response.json(), ["0"] * 7)
    assert completed["result"]["band"] == "normal"
    assert client.get(
        "/api/family/elders/elder-demo-001/screenings",
        headers=family_headers,
    ).json()["items"] == []
    assert client.get("/api/admin/screenings", headers=admin_headers).json()["items"] == []
