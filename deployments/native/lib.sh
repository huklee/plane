# Shared by the native scripts: load $PLANE_RUNTIME/native.env (PLANE_RUNTIME defaults to ~/plane-runtime).
PLANE_RUNTIME="${PLANE_RUNTIME:-$HOME/plane-runtime}"
[ -f "$PLANE_RUNTIME/native.env" ] || { echo "missing $PLANE_RUNTIME/native.env (see env.example)" >&2; exit 1; }
set -a; source "$PLANE_RUNTIME/native.env"; set +a
export PLANE_RUNTIME PLANE_SRC PLANE_PUBLIC_URL
