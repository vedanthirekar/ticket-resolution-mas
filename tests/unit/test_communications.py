from luma.services.communications import build_final_email


def test_final_email_wraps_case_specific_resolution() -> None:
    response = (
        "We reviewed the $60 cancellation fee. The appointment was cancelled four hours "
        "before its scheduled start, so no refund is due under the applicable policy."
    )

    subject, body = build_final_email(
        case_reference="CASE-B46FF10EA3BE",
        customer_response=response,
    )

    assert subject == "Resolution for your Luma Wellness case CASE-B46FF10EA3BE"
    assert response in body
    assert "Case reference: CASE-B46FF10EA3BE" in body
    assert body.endswith("Luma Wellness Support")
