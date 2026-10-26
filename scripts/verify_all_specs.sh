#!/bin/bash
BASE="http://127.0.0.1:8000"

echo "===================================================="
echo "1. AUTHENTICATION & TOKENS"
echo "===================================================="
ADMIN_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@eduskills.com","password":"AdminPassword123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
ALICE_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"alice@example.com","password":"MemberPassword123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
BOB_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"bob@example.com","password":"MemberPassword123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
CHARLIE_TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"charlie@example.com","password":"MemberPassword123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Tokens acquired for Admin, Alice, Bob, and Charlie!"

echo -e "\n===================================================="
echo "2. SECURITY & STATUS CODES (401, 403, 422, 404, 409)"
echo "===================================================="
echo "[Test 401 No Token on /me]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/me"

echo "[Test 403 Member on Admin Route]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/admin/list" -H "Authorization: Bearer $BOB_TOKEN"

echo "[Test 422 Invalid Referral Code Format]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "!@#"}'

echo "[Test 404 Unknown Referral Code]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "UNKNOWN9"}'

echo "[Test 409 Self-Referral (Alice using ALICE100)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "ALICE100"}'

echo -e "\n===================================================="
echo "3. MEMBER API: CREATE REFERRAL & DUPLICATE BLOCK"
echo "===================================================="
echo "[Bob submits Alice's code ALICE100 (Expect 201 PENDING)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "ALICE100"}'

echo "[Bob submits a referral code a second time (Expect 409 DUPLICATE)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $BOB_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "ALICE100"}'

echo "[Charlie submits Alice's code ALICE100 (Expect 201 PENDING)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals" -H "Authorization: Bearer $CHARLIE_TOKEN" -H "Content-Type: application/json" -d '{"referral_code": "ALICE100"}'

echo -e "\n===================================================="
echo "4. ADMIN APIs: LIST, APPROVE, IDEMPOTENCY & REJECT"
echo "===================================================="
echo "[Admin lists PENDING referrals (Expect 200 with 2 items)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/admin/list?status=PENDING" -H "Authorization: Bearer $ADMIN_TOKEN"

echo "[Admin approves Bob (user_id=3) (Expect 200 SUCCESSFUL, +100 pts to Alice)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals/admin/approve/3" -H "Authorization: Bearer $ADMIN_TOKEN"

echo "[Admin tries to approve Bob AGAIN (Expect 409 Conflict, no double credit)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals/admin/approve/3" -H "Authorization: Bearer $ADMIN_TOKEN"

echo "[Admin rejects Charlie (user_id=4) (Expect 200 REJECTED, 0 pts)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals/admin/reject/4" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"reason": "Incomplete KYC"}'

echo -e "\n===================================================="
echo "5. MEMBER APIs: /me, /milestones, /transactions (ALICE)"
echo "===================================================="
echo "[Alice checks /me dashboard (Expect balance=100, successful=1, rejected=1)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/me" -H "Authorization: Bearer $ALICE_TOKEN"

echo "[Alice checks /milestones (Expect Pioneer IN_PROGRESS, 4 remaining)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/milestones" -H "Authorization: Bearer $ALICE_TOKEN"

echo "[Alice checks /transactions ledger (Expect 1 REFERRAL_CREDIT +100)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/transactions" -H "Authorization: Bearer $ALICE_TOKEN"

echo -e "\n===================================================="
echo "6. ADMIN API: REVERSAL & APPEND-ONLY LEDGER"
echo "===================================================="
echo "[Admin reverses Bob's approved referral (user_id=3) (Expect 200 REVERSED)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals/admin/reverse/3" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"reason": "Order cancelled"}'

echo "[Alice checks /transactions after reversal (Expect 2 rows: +100 and -100, balance_after=0)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/transactions" -H "Authorization: Bearer $ALICE_TOKEN"

echo -e "\n===================================================="
echo "7. ADMIN APIs: RECONCILIATION & OPTIONAL AUDIT APIS"
echo "===================================================="
echo "[Admin runs reconciliation (Expect 200 CLEAN, 0 discrepancies)]:"
curl -s -w " -> HTTP %{http_code}\n" -X POST "$BASE/api/v1/referrals/admin/reconcile" -H "Authorization: Bearer $ADMIN_TOKEN"

echo "[Optional API 1: Admin fetches Referral #1 lifecycle history (APPROVE -> REVERSE)]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/admin/1" -H "Authorization: Bearer $ADMIN_TOKEN"

echo "[Optional API 2: Admin fetches persisted Reconciliation Report #1]:"
curl -s -w " -> HTTP %{http_code}\n" "$BASE/api/v1/referrals/admin/reconciliation-report/1" -H "Authorization: Bearer $ADMIN_TOKEN"
