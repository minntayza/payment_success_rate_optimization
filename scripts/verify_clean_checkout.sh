#!/usr/bin/env bash

set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
revision="${1:-HEAD}"
export_root="$(mktemp -d "${TMPDIR:-/tmp}/payment-dashboard-clean.XXXXXX")"
environment_path="${export_root}/.venv"
server_log="${export_root}/streamlit.log"
server_pid=""

cleanup() {
	if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
		kill "${server_pid}" 2>/dev/null || true
		wait "${server_pid}" 2>/dev/null || true
	fi
	rm -rf "${export_root}"
}
trap cleanup EXIT

git -C "${repository_root}" archive "${revision}" | tar -x -C "${export_root}"

python3 -m venv "${environment_path}"
"${environment_path}/bin/python" -m pip install --editable "${export_root}[dev]"

(
	cd /tmp
	"${environment_path}/bin/python" -c \
		"from payment_dashboard.app import render_app; assert callable(render_app)"
)

server_port="$(
	"${environment_path}/bin/python" -c \
		"import socket; s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()"
)"

(
	cd "${export_root}"
	"${environment_path}/bin/python" -m streamlit run payment_dashboard/app.py \
		--server.address 127.0.0.1 \
		--server.headless true \
		--server.port "${server_port}"
) >"${server_log}" 2>&1 &
server_pid="$!"

for _ in {1..40}; do
	if ! kill -0 "${server_pid}" 2>/dev/null; then
		wait "${server_pid}" || true
		sed -n '1,160p' "${server_log}" >&2
		exit 1
	fi
	if grep -Eq "(Local URL:|URL: http://)" "${server_log}"; then
		echo "Clean export installed and launched on port ${server_port}."
		exit 0
	fi
	sleep 0.25
done

sed -n '1,160p' "${server_log}" >&2
echo "Streamlit did not report a local URL before the verification timeout." >&2
exit 1
