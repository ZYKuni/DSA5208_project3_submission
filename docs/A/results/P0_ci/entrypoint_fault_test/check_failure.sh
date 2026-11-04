#!/usr/bin/env bash
set -euo pipefail
mkdir -p /tmp/p0-fault
cat > /tmp/p0-fault/ctest <<'SHIM'
#!/usr/bin/env bash
mkdir -p mpi-validation/injected-failure
printf 'Intentional test failure for archive contract\n' > mpi-validation/injected-failure/stderr.log
echo 'Intentional CTest failure, exit 23'
exit 23
SHIM
chmod +x /tmp/p0-fault/ctest
set +e
PATH="/tmp/p0-fault:$PATH" bash /src/scripts/verify_linux.sh /evidence/failure-check serial > /evidence/failure-check-driver.log 2>&1
status=$?
set -e
test "$status" = 23
test "$(cat /evidence/failure-check/exit_code.txt)" = 23
test -f /evidence/failure-check/mpi-validation/injected-failure/stderr.log
grep -q 'Intentional CTest failure' /evidence/failure-check/ctest.log
set +e
bash /src/scripts/verify_linux.sh /evidence/failure-check serial > /evidence/reuse-check.log 2>&1
reuse=$?
bash /src/scripts/verify_linux.sh /evidence/invalid-mode invalid > /evidence/invalid-mode-check.log 2>&1
invalid=$?
set -e
test "$reuse" != 0
test "$invalid" = 2
test ! -e /evidence/invalid-mode
printf 'PASS: injected exit 23 preserved; failure log archived; existing output and invalid mode rejected.\n' > /evidence/entrypoint_contract.txt
