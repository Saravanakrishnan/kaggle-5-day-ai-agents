import pytest
from app.agent import redeem_discount, _discount_store

@pytest.fixture(autouse=True)
def reset_discount_store():
    """Reset the in‑memory discount store before each test to ensure isolation."""
    # Preserve original values but reset redeemed flags
    for entry in _discount_store.values():
        entry["redeemed"] = False
    yield

def test_redeem_valid_code_success():
    user_id = "user123"
    code = "welcome50"
    result = redeem_discount(code, user_id)
    assert "Successfully redeemed" in result
    assert user_id in result
    # Verify the code is now marked as redeemed
    assert _discount_store[code.upper()]["redeemed"] is True

def test_redeem_same_code_twice_fails():
    user_id = "user123"
    code = "WELCOME50"
    # First redemption should succeed
    first = redeem_discount(code, user_id)
    assert "Successfully redeemed" in first
    # Second redemption should be blocked
    second = redeem_discount(code, user_id)
    assert "already been used" in second

def test_redeem_invalid_code():
    result = redeem_discount("INVALIDCODE", "user123")
    assert "is invalid" in result

def test_redeem_code_is_case_insensitive():
    # Store entry is uppercase, but we pass lowercase
    result = redeem_discount("summer20", "user456")
    assert "Successfully redeemed" in result
    # Ensure the stored entry is marked redeemed
    assert _discount_store["SUMMER20"]["redeemed"] is True

def test_single_use_across_multiple_users():
    # User A redeems code
    redeem_discount("WELCOME50", "userA")
    # User B attempts same code – should be rejected
    result = redeem_discount("WELCOME50", "userB")
    assert "already been used" in result

def test_no_unintended_state_mutation():
    # Capture snapshot of store before any operation
    original = {k: v.copy() for k, v in _discount_store.items()}
    redeem_discount("WELCOME50", "userX")
    # Only the redeemed flag of the used code should change
    for code, entry in _discount_store.items():
        if code == "WELCOME50":
            assert entry["redeemed"] is True
        else:
            assert entry == original[code]
